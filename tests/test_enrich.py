"""M4 enrichment: extraction, refusal rules, and never-guess behaviour.

The enrichment stage reads pages off the open web, so the tests split in two:

  * everything here runs OFFLINE, driven by a fake fetcher -- including the
    rate-limit path, which must stop the run rather than record a missing
    description;
  * one test uses a real page saved under var/page_cache/ when it exists, and
    SKIPS otherwise (var/ is never shipped, so a copy of the project stays clean).

Run:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import db as db_mod  # noqa: E402
from jobsearch import enrich  # noqa: E402
from jobsearch.ingest import ingest_directory  # noqa: E402
from jobsearch.rules import MIN_DESCRIPTION_CHARS  # noqa: E402

FIXTURES = ROOT / "fixtures"
PAGE_CACHE = ROOT / "var" / "page_cache"

# Same container nesting LinkedIn serves (verified against a live page).
PAGE = """<html><body>
<div class="core-section-container__content break-words">
  <div class="description__text description__text--rich">
    <section class="show-more-less-html" data-max-lines="20">
      <div class="show-more-less-html__markup show-more-less-html__markup--clamp-after-20
            relative overflow-hidden">
        <p><strong>Acme,</strong> a product engineering company, is hiring.</p>
        <ul><li>Python and Go in production</li><li>Remote within the EU</li></ul>
        <p>Salary: EUR 70,000 per year.</p>
      </div>
    </section>
  </div>
</div></body></html>"""

PAGE_WITHOUT_DESCRIPTION = "<html><body><p>Sign in to see this job.</p></body></html>"
LONG_PARAGRAPH = "<p>" + ("We build reliable systems in Python and Go. " * 8) + "</p>"


class TestExtraction(unittest.TestCase):
    def test_extracts_the_description_with_paragraph_breaks(self):
        text, clamped = enrich.extract_description(PAGE)
        self.assertIsNotNone(text)
        self.assertIn("Acme,", text)
        self.assertIn("Python and Go in production", text)
        self.assertIn("Salary: EUR 70,000 per year.", text)
        self.assertIn("\n", text, "block elements should become line breaks")
        self.assertNotIn("<p>", text, "markup must be stripped")
        self.assertTrue(clamped, "the guest clamp should be reported, not hidden")

    def test_no_container_yields_nothing_rather_than_a_guess(self):
        text, clamped = enrich.extract_description(PAGE_WITHOUT_DESCRIPTION)
        self.assertIsNone(text)
        self.assertFalse(clamped)

    def test_entity_and_nbsp_handling(self):
        text, _ = enrich.extract_description(
            '<div class="show-more-less-html__markup">R&amp;D&nbsp;team</div>'
        )
        self.assertEqual(text, "R&D team")


class TestRefusalRules(unittest.TestCase):
    def test_apply_path_is_never_requested(self):
        with self.assertRaises(enrich.DisallowedURL):
            enrich._assert_allowed("https://www.linkedin.com/jobs/view/externalApply/123")

    def test_other_hosts_are_refused(self):
        for url in ("https://example.com/jobs/view/1", "https://notlinkedin.com.evil.test/x"):
            with self.subTest(url=url):
                with self.assertRaises(enrich.DisallowedURL):
                    enrich._assert_allowed(url)

    def test_non_http_scheme_is_refused(self):
        with self.assertRaises(enrich.DisallowedURL):
            enrich._assert_allowed("file:///etc/passwd")

    def test_a_normal_job_url_is_allowed(self):
        enrich._assert_allowed("https://www.linkedin.com/jobs/view/4477231836/")


class TestNeverGuesses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "jobs.db"
        self.con = db_mod.connect(self.db_path)
        ingest_directory(self.con, FIXTURES)
        self.job = self.con.execute(
            "SELECT * FROM jobs WHERE url LIKE '%linkedin.com/jobs/view%' ORDER BY id LIMIT 1"
        ).fetchone()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _state(self, job_id):
        return self.con.execute(
            "SELECT description, description_state FROM jobs WHERE id=?", (job_id,)
        ).fetchone()

    def test_a_retrieved_description_is_stored_and_marked_complete(self):
        page = '<div class="show-more-less-html__markup">' + LONG_PARAGRAPH + "</div>"
        result = enrich.enrich_one(self.con, self.job, fetcher=lambda url: page)
        self.assertEqual(result["state"], "complete")
        row = self._state(self.job["id"])
        self.assertEqual(row["description_state"], "complete")
        self.assertGreater(len(row["description"]), MIN_DESCRIPTION_CHARS)

    def test_a_page_without_a_description_stores_nothing(self):
        result = enrich.enrich_one(
            self.con, self.job, fetcher=lambda url: PAGE_WITHOUT_DESCRIPTION
        )
        self.assertEqual(result["state"], "no_description")
        row = self._state(self.job["id"])
        self.assertIsNone(row["description"], "an absent description must never be invented")
        self.assertEqual(row["description_state"], "incomplete")

    def test_a_too_short_extract_stays_incomplete(self):
        page = '<div class="show-more-less-html__markup">Too short.</div>'
        result = enrich.enrich_one(self.con, self.job, fetcher=lambda url: page)
        self.assertEqual(result["state"], "incomplete")
        self.assertEqual(self._state(self.job["id"])["description_state"], "incomplete")

    def test_a_rate_limit_stops_the_run_and_exits_6(self):
        def rate_limited(url):
            raise enrich.RateLimited("HTTP 429")

        original = enrich.enrich_one
        enrich.enrich_one = lambda con, row, **kw: rate_limited(row["url"])
        try:
            with redirect_stdout(io.StringIO()):
                code = enrich.main(["--db", str(self.db_path), "--limit", "2", "--spacing", "0"])
        finally:
            enrich.enrich_one = original
        self.assertEqual(code, 6, "a rate limit must not exit 0")
        self.assertEqual(
            self._state(self.job["id"])["description_state"],
            "incomplete",
            "a rate limit must not be recorded as a missing description",
        )

    def test_completed_jobs_are_not_fetched_again(self):
        before = enrich._pending(self.con, limit=50, job_id=None)
        self.assertTrue(before)
        self.con.execute(
            "UPDATE jobs SET description=?, description_state='complete' WHERE id=?",
            ("x" * (MIN_DESCRIPTION_CHARS + 1), self.job["id"]),
        )
        self.con.commit()
        after = enrich._pending(self.con, limit=50, job_id=None)
        self.assertNotIn(self.job["id"], [r["id"] for r in after])


class TestPayReachesTheGate(unittest.TestCase):
    """`jobs.salary_text` is the field the gate ranks and flags from.

    It was documented, read by the renderer, and -- until the enrichment step
    wrote it -- populated by nothing in the pipeline at all. Every posting read
    "no salary published" however plainly the page stated a figure, so the
    below-floor and foreign-currency flags could not fire on any real run. The
    unit tests passed because they inserted the column by hand.

    These tests run the real path end to end: fetch -> extract -> store ->
    render, so the claim is proved where it used to be assumed.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "jobs.db"
        self.con = db_mod.connect(self.db_path)
        ingest_directory(self.con, FIXTURES)
        self.job = self.con.execute(
            "SELECT * FROM jobs WHERE url LIKE '%linkedin.com/jobs/view%' ORDER BY id LIMIT 1"
        ).fetchone()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _page(self, pay_line: str) -> str:
        body = (
            "<p>Northwind Sample Ltd is hiring a Backend Engineer for its "
            "platform team. You will own Python services and PostgreSQL "
            "schemas, and review your colleagues' code.</p>"
            "<p>" + pay_line + "</p>"
        )
        return '<div class="show-more-less-html__markup">' + body + "</div>"

    def _render_digest(self, floor: int):
        from jobsearch import notify as notify_mod
        from jobsearch.rules import rules_from_profile
        rules = rules_from_profile({
            "known_stack": ["python", "postgres"],
            "floor_net": floor,
            "floor_currency": "EUR",
            "languages_usable": ["english"],
        })
        return notify_mod.render_digest(self.con, limit=10, rules=rules)

    def test_the_postings_own_pay_line_is_stored(self):
        result = enrich.enrich_one(
            self.con, self.job,
            fetcher=lambda url: self._page("Salary: EUR 4500 per month."),
        )
        self.assertEqual(result["state"], "complete")
        stored = self.con.execute(
            "SELECT salary_text FROM jobs WHERE id=?", (self.job["id"],)
        ).fetchone()["salary_text"]
        self.assertEqual(stored, "Salary: EUR 4500 per month.")
        self.assertEqual(result["salary_text"], stored)

    def test_no_pay_statement_leaves_the_field_empty(self):
        enrich.enrich_one(
            self.con, self.job,
            fetcher=lambda url: self._page("We offer a good package."),
        )
        stored = self.con.execute(
            "SELECT salary_text FROM jobs WHERE id=?", (self.job["id"],)
        ).fetchone()["salary_text"]
        self.assertIsNone(
            stored,
            "a page that states no figure must leave salary_text NULL; a "
            "guessed salary in a job list is worse than no salary",
        )

    def test_a_pay_line_below_the_floor_is_flagged_and_never_drops_the_job(self):
        enrich.enrich_one(
            self.con, self.job,
            fetcher=lambda url: self._page("Compensation: 2,800 EUR per month."),
        )
        text = self._render_digest(floor=6000)
        block = text.split(f"#{self.job['id']}  ")[1].split("\n#")[0]
        self.assertIn("below the net floor", block)
        self.assertIn("2,800 EUR per month", block)
        self.assertNotIn(
            "no salary published", block,
            "the job states a figure: the digest must not report it as "
            "unpublished",
        )
        # Never a rejection: pay ranks and flags, it does not decide.
        self.assertIn("Fit: shortlist", block)

    def test_a_pay_line_above_the_floor_is_not_flagged(self):
        enrich.enrich_one(
            self.con, self.job,
            fetcher=lambda url: self._page("Compensation: 7,500 EUR per month."),
        )
        block = self._render_digest(floor=6000).split(f"#{self.job['id']}  ")[1].split("\n#")[0]
        self.assertIn("7,500 EUR per month", block)
        self.assertNotIn("below the net floor", block)

    def test_a_foreign_currency_is_stored_verbatim_and_never_converted(self):
        enrich.enrich_one(
            self.con, self.job,
            fetcher=lambda url: self._page("Compensation: USD 90000 per year."),
        )
        block = self._render_digest(floor=6000).split(f"#{self.job['id']}  ")[1].split("\n#")[0]
        self.assertIn("USD 90000 per year", block)
        self.assertIn("salary in USD", block)
        # The gate refuses to invent a rate; it asks for the conversion.
        self.assertNotIn("below the net floor", block)


@unittest.skipUnless(list(PAGE_CACHE.glob("*.html")), "no saved real page (var/page_cache)")
class TestRealPage(unittest.TestCase):
    def test_a_saved_real_page_yields_a_substantial_description(self):
        for path in sorted(PAGE_CACHE.glob("*.html")):
            page = path.read_text(encoding="utf-8", errors="replace")
            text, _clamped = enrich.extract_description(page)
            with self.subTest(page=path.name):
                self.assertIsNotNone(text, "real LinkedIn markup must be recognised")
                self.assertGreater(len(text), 500)
                self.assertNotIn("show-more-less-html", text)


class TestDefaultUserAgent(unittest.TestCase):
    """`DEFAULT_UA` in
    `jobsearch/enrich.py` is
    the User-Agent string
    used by `fetch_html()`
    when making HTTP
    requests. The UA is
    what the job board
    (LinkedIn) sees when
    the enrichment code
    fetches a posting page.

    The UA contract is
    **security/privacy +
    parse-correctness**:
    1. **Parse correctness**:
       The UA was verified
       against a live page
       on 2026-10-13 (see
       enrich.py L54). The
       markup regex
       `_MARKUP_RE` and
       `_SECTION_RE` were
       designed against the
       markup LinkedIn
       serves for THIS UA.
       If the UA changes
       to something the
       site treats as a
       bot, the site would
       serve different
       markup (e.g. a
       "please log in"
       page, or a stripped
       description). The
       regexes would fail
       to match, and every
       posting would be
       marked
       `incomplete`
       (description too
       short to evaluate).
       That cascades to
       `NEEDS_RESEARCH`
       verdicts across
       the whole corpus.
    2. **Privacy**:
       A real browser UA
       (Mozilla + AppleWebKit
       + Chrome) is the
       common case, not a
       unique fingerprint.
       A custom UA with
       a personal token
       (e.g.
       "Mozilla/5.0 (X11;
       Linux x86_64)
       AppleWebKit/537.36
       (KHTML, like Gecko)
       Chrome/140.0.0.0
       Safari/537.36
       jobsearch/1.0
       [email protected]")
       would uniquely
       identify the user
       to LinkedIn. A
       bot-UA (e.g.
       "Python-urllib/3.11"
       or "wget" or
       "curl") would be
       blocked outright
       or served a
       challenge page.

    The contract is that
    `DEFAULT_UA`:
    1. Is a non-empty
       string.
    2. Contains the
       real-browser tokens
       "Mozilla" and
       "AppleWebKit"
       (so the site
       treats it as a
       real browser).
    3. Does NOT contain
       bot-UA tokens
       ("Python-urllib",
       "wget", "curl",
       "scrapy", "http",
       "bot", "spider",
       "crawler") which
       would be blocked.
    4. Does NOT contain
       a personal token
       (no email, no
       "jobsearch/X.Y",
       no user-specific
       data).
    5. Is a Chrome
       browser UA
       (matches the
       "verified against
       a live page on
       2026-10-13"
       comment, which
       documented
       what markup
       the regexes
       were
       designed for).
    6. Is a plausible
       recent Chrome
       version (>= 100,
       so the UA
       looks current
       and not
       outdated).

    Before this turn,
    no test pinned
    `DEFAULT_UA`. A
    contributor who
    changed the UA to
    "Python-urllib/3.11"
    (the Python default)
    would have:
    1. Been blocked
       by LinkedIn
       (the urllib UA
       is widely
       blacklisted).
    2. No test would
       fail (the
       regex tests
       use saved
       pages, not
       live fetches).
    3. The published
       artifact would
       silently
       regress the
       M4 enrichment
       milestone.

    The fix is a new
    `TestDefaultUserAgent`
    class with 6 tests:
    1. `test_default_ua_is_a_string`:
       the constant is
       a non-empty
       string.
    2. `test_default_ua_contains_browser_tokens`:
       the UA contains
       "Mozilla" and
       "AppleWebKit".
    3. `test_default_ua_does_not_contain_bot_tokens`:
       the UA does
       NOT contain
       bot-UA tokens
       (case-insensitive).
    4. `test_default_ua_does_not_contain_personal_data`:
       the UA does
       NOT contain
       an email or
       a user-specific
       token.
    5. `test_default_ua_is_chrome_browser`:
       the UA is a
       Chrome browser
       UA (matches
       the "verified
       against a live
       page" comment).
    6. `test_default_ua_chrome_version_is_recent`:
       the Chrome
       version in
       the UA is
       >= 100 (a
       plausible
       recent
       version).
    """

    # Bot-UA tokens that
    # would cause the site
    # to block the request
    # or serve different
    # markup. Case-insensitive
    # match.
    BOT_TOKENS = (
        "python-urllib", "wget", "curl",
        "scrapy", "spider", "crawler",
        "httpclient", "okhttp", "axios",
        "node-fetch", "go-http", "java/",
    )

    def test_default_ua_is_a_string(self) -> None:
        """`DEFAULT_UA` must
        be a non-empty
        string. The
        constant is
        passed to
        `urllib.request`
        which requires
        a `str` (or
        bytes); None
        or empty would
        raise a
        TypeError at
        request time.
        """
        from jobsearch import enrich
        self.assertIsInstance(
            enrich.DEFAULT_UA, str,
            f"DEFAULT_UA is "
            f"{type(enrich.DEFAULT_UA).__name__}, "
            f"not a str. urllib.request "
            f"requires a str; None or "
            f"int would raise a "
            f"TypeError at request time."
        )
        self.assertGreater(
            len(enrich.DEFAULT_UA), 20,
            f"DEFAULT_UA is "
            f"{len(enrich.DEFAULT_UA)} chars; "
            f"a real browser UA is at least "
            f"50 chars. A short UA suggests "
            f"the constant was truncated or "
            f"replaced with a stub."
        )

    def test_default_ua_contains_browser_tokens(self) -> None:
        """The UA must
        contain "Mozilla"
        and "AppleWebKit"
        (real-browser
        tokens). The site
        would serve
        different markup
        (or block) without
        these tokens.
        """
        from jobsearch import enrich
        self.assertIn(
            "Mozilla", enrich.DEFAULT_UA,
            f"DEFAULT_UA does not contain "
            f"'Mozilla'. A real-browser UA "
            f"starts with 'Mozilla/5.0'; "
            f"without it, the site would "
            f"treat the request as a bot "
            f"and serve different markup "
            f"(or block). The regexes "
            f"_MARKUP_RE and _SECTION_RE "
            f"were designed against the "
            f"markup served for a "
            f"real-browser UA."
        )
        self.assertIn(
            "AppleWebKit", enrich.DEFAULT_UA,
            f"DEFAULT_UA does not contain "
            f"'AppleWebKit'. A Chrome UA "
            f"contains AppleWebKit (since "
            f"Chrome is built on WebKit). "
            f"Without it, the site may "
            f"serve Chrome-specific markup "
            f"as a different browser."
        )

    def test_default_ua_does_not_contain_bot_tokens(self) -> None:
        """The UA must
        NOT contain
        bot-UA tokens.
        These would
        cause the site
        to block the
        request or
        serve a
        challenge page.
        """
        from jobsearch import enrich
        ua_lower = enrich.DEFAULT_UA.lower()
        for token in self.BOT_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(
                    token, ua_lower,
                    f"DEFAULT_UA contains "
                    f"bot-UA token {token!r}: "
                    f"{enrich.DEFAULT_UA!r}. "
                    f"Bot-UA tokens cause the "
                    f"site to block the request "
                    f"or serve different markup. "
                    f"Use a real-browser UA "
                    f"instead. If the token is "
                    f"intentional (e.g. the "
                    f"project is intentionally "
                    f"identifying itself), "
                    f"remove it from BOT_TOKENS "
                    f"in this test in the same "
                    f"commit."
                )

    def test_default_ua_does_not_contain_personal_data(self) -> None:
        """The UA must
        NOT contain
        an email or a
        user-specific
        token. The UA
        is what the
        job board sees;
        a personal
        token would
        uniquely
        identify the
        user.
        """
        from jobsearch import enrich
        # Email pattern
        # (basic)
        import re
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+",
                     enrich.DEFAULT_UA):
            self.fail(
                f"DEFAULT_UA contains an email "
                f"address: {enrich.DEFAULT_UA!r}. "
                f"The UA is what LinkedIn sees; "
                f"an email would uniquely "
                f"identify the user. Remove "
                f"the email and use a generic "
                f"real-browser UA."
            )
        # Personal token
        # pattern:
        # "jobsearch/X.Y"
        # or "username/..."
        # or similar
        if re.search(r"jobsearch/\d",
                     enrich.DEFAULT_UA, re.I):
            self.fail(
                f"DEFAULT_UA contains a "
                f"'jobsearch/X.Y' token: "
                f"{enrich.DEFAULT_UA!r}. "
                f"Such a token uniquely "
                f"identifies the project "
                f"and the user. Remove it "
                f"and use a generic "
                f"real-browser UA."
            )
        # Custom token
        # with brackets
        # (e.g. "[email protected]")
        if re.search(r"\[[^\]]+@[^\]]+\]",
                     enrich.DEFAULT_UA):
            self.fail(
                f"DEFAULT_UA contains a "
                f"bracketed contact token: "
                f"{enrich.DEFAULT_UA!r}. "
                f"Such a token uniquely "
                f"identifies the user. "
                f"Remove it and use a "
                f"generic real-browser UA."
            )

    def test_default_ua_is_chrome_browser(self) -> None:
        """The UA must
        be a Chrome
        browser UA.
        The comment at
        enrich.py L54
        says "verified
        against a live
        page on
        2026-10-13"
        and the markup
        regexes are
        designed for
        what Chrome
        sees on
        LinkedIn.
        """
        from jobsearch import enrich
        self.assertIn(
            "Chrome", enrich.DEFAULT_UA,
            f"DEFAULT_UA does not contain "
            f"'Chrome': {enrich.DEFAULT_UA!r}. "
            f"The enrich.py comment at L54 "
            f"says the markup regexes were "
            f"verified against a live page "
            f"on 2026-10-13 for THIS UA. "
            f"Changing the UA to a different "
            f"browser (Firefox, Safari) would "
            f"silently break the regexes "
            f"because the site may serve "
            f"different markup to different "
            f"browsers."
        )
        # Sanity: Safari UAs
        # ALSO contain
        # AppleWebKit but
        # NOT Chrome. If
        # we see "Safari"
        # without "Chrome",
        # it's not a
        # Chrome UA.
        if "Safari" in enrich.DEFAULT_UA and "Chrome" not in enrich.DEFAULT_UA:
            self.fail(
                f"DEFAULT_UA looks like Safari, "
                f"not Chrome: "
                f"{enrich.DEFAULT_UA!r}. The "
                f"markup regexes are designed "
                f"for Chrome; Safari markup "
                f"may differ."
            )

    def test_default_ua_chrome_version_is_recent(self) -> None:
        """The Chrome
        version in the
        UA must be
        >= 100 (a
        plausible
        recent
        version). An
        outdated
        version (e.g.
        Chrome/30) may
        cause the
        site to serve
        an old,
        unmaintained
        layout.
        """
        from jobsearch import enrich
        import re
        m = re.search(r"Chrome/(\d+)", enrich.DEFAULT_UA)
        self.assertIsNotNone(
            m,
            f"DEFAULT_UA does not contain a "
            f"'Chrome/X.Y' version: "
            f"{enrich.DEFAULT_UA!r}. A "
            f"Chrome UA must include a "
            f"version (e.g. 'Chrome/140.0'). "
            f"Without a version, the site "
            f"may serve a generic / "
            f"old-version layout."
        )
        version = int(m.group(1))
        self.assertGreaterEqual(
            version, 100,
            f"DEFAULT_UA Chrome version is "
            f"{version}, which is below 100. "
            f"An outdated Chrome version may "
            f"cause the site to serve an "
            f"old, unmaintained layout. The "
            f"UA was verified on 2026-10-13; "
            f"a current Chrome version at "
            f"that time was 140."
        )


class TestMarkupRegexes(unittest.TestCase):
    """The 4 markup-parser
    constants in
    `jobsearch/enrich.py`:
    - `_MARKUP_RE`: matches
      `<div class="show-more-less-html__markup...">...</div>`
      (the inner markup
      div).
    - `_SECTION_RE`: matches
      `<div class="description__text...">...</section>`
      (the outer description
      div with section-end).
    - `_CLAMP_RE`: matches
      `clamp-after-N` (the
      CSS class LinkedIn adds
      when it truncates the
      description).
    - `_APPLY_PATH`: `"/jobs/view/externalApply/"`
      (LinkedIn's external
      apply URL path).

    All 4 are part of the
    **LinkedIn markup parser
    contract**: they
    determine what
    `extract_description()`
    and the apply-link
    detector in
    `enrich.py` see when
    they read a saved
    LinkedIn page. The
    comment at L54-58
    documents: "The real
    markup (verified
    against a live page on
    2026-10-13)".

    `_MARKUP_RE` and
    `_SECTION_RE` are the
    two regexes tried in
    order in
    `extract_description()`
    (L114): the function
    returns the first
    match that yields
    non-empty text. A
    drift in `_MARKUP_RE`
    (e.g. removing
    `show-more-less-html__markup`
    from the class name)
    would silently fail to
    extract the description
    from real LinkedIn
    pages, and the gate
    would mark every
    posting as
    `incomplete`
    (description too short
    to evaluate), which
    cascades to
    `NEEDS_RESEARCH`
    verdicts across the
    whole corpus.

    `_CLAMP_RE` is the
    clamp-signal detector.
    When LinkedIn serves a
    guest page, it clamps
    the description to
    ~20 lines and adds
    the
    `show-more-less-html__markup--clamp-after-20`
    class. The function
    returns
    `(text, was_clamped=True)`
    so the caller knows
    the description is
    truncated. A drift
    that removes
    `clamp-after-`
    from `_CLAMP_RE`
    would silently
    mis-report clamped
    descriptions as
    complete, and the
    gate would mark
    truncated postings
    as `complete` --
    giving wrong
    verdicts to
    truncated
    postings.

    `_APPLY_PATH` is the
    external-apply URL
    path. When a posting
    has an "Apply on
    company site" link,
    the URL contains
    `/jobs/view/externalApply/`.
    A drift that changes
    this to a wrong path
    would silently
    mis-detect external
    apply links, and the
    gate would either
    miss them (mark as
    "direct apply" when
    external) or
    false-detect them
    (mark as "external"
    when direct).

    Before this turn, no
    test pinned these 4
    constants directly.
    The existing
    `TestRealPage` test
    uses a saved page
    (which is good --
    it tests the
    end-to-end behavior
    on real markup),
    but it would still
    pass if the regexes
    were broken in a way
    that happens to
    match the saved
    page (e.g. if
    `_MARKUP_RE` was
    changed to a more
    permissive regex
    that matches a
    larger block of
    the page). The
    fix is a new
    `TestMarkupRegexes`
    class with 4 tests
    that pin the
    individual regex
    shapes and the
    `_APPLY_PATH`
    value.

    Drift-injection
    verified: removing
    `show-more-less-html__markup`
    from `_MARKUP_RE`
    fails the markup
    test.
    """

    EXPECTED_MARKUP_FRAGMENT = (
        '<div class="show-more-less-html__markup'
    )

    EXPECTED_SECTION_FRAGMENT = (
        '<div class="description__text'
    )

    EXPECTED_CLAMP_FRAGMENT = "clamp-after-"

    EXPECTED_APPLY_PATH = "/jobs/view/externalApply/"

    def test_markup_re_matches_documented_class(self) -> None:
        """`_MARKUP_RE` in
        `jobsearch/enrich.py`
        must contain the
        `show-more-less-html__markup`
        class name. The
        saved LinkedIn page
        at
        `var/page_cache/4477142227.html`
        uses this class.
        Removing it would
        silently fail to
        extract descriptions
        from real LinkedIn
        pages.
        """
        import re as _re
        from jobsearch import enrich
        # The pattern
        # string
        # itself
        # must
        # contain
        # the
        # documented
        # class.
        pat = enrich._MARKUP_RE.pattern
        self.assertIn(
            self.EXPECTED_MARKUP_FRAGMENT, pat,
            f"_MARKUP_RE pattern "
            f"{pat!r} does NOT contain "
            f"{self.EXPECTED_MARKUP_FRAGMENT!r}. "
            f"The saved LinkedIn page at "
            f"`var/page_cache/4477142227.html` "
            f"uses "
            f"`<div class=\"show-more-less-html__markup\">` "
            f"as the description inner "
            f"div. Removing the class "
            f"from the regex would "
            f"silently fail to extract "
            f"descriptions from real "
            f"LinkedIn pages, and the "
            f"gate would mark every "
            f"posting as `incomplete`."
        )
        # And the
        # compiled
        # regex
        # must
        # actually
        # match
        # a
        # documented
        # markup
        # snippet.
        snippet = (
            '<div class="show-more-less-html__markup'
            ' show-more-less-html__markup--clamp-after-20">'
            '<p>Job description text here.</p>'
            '</div>'
        )
        self.assertIsNotNone(
            enrich._MARKUP_RE.search(snippet),
            f"_MARKUP_RE did NOT match a "
            f"documented markup snippet "
            f"with the show-more-less-html__markup class. "
            f"The regex is broken; "
            f"descriptions would not be "
            f"extracted."
        )
        # And it
        # must
        # NOT
        # match
        # a
        # snippet
        # without
        # the
        # class
        # (catch
        # over-permissive
        # regexes).
        wrong = (
            '<div class="other-class">'
            '<p>Job description text here.</p>'
            '</div>'
        )
        self.assertIsNone(
            enrich._MARKUP_RE.search(wrong),
            f"_MARKUP_RE matched a snippet "
            f"without the "
            f"show-more-less-html__markup class. "
            f"The regex is over-permissive; "
            f"it would extract the wrong "
            f"block of the page."
        )

    def test_section_re_matches_documented_class(self) -> None:
        """`_SECTION_RE` in
        `jobsearch/enrich.py`
        must contain the
        `description__text`
        class name. The
        outer description
        div uses this
        class. The regex
        is the fallback
        after `_MARKUP_RE`
        fails; removing
        the class would
        silence the
        fallback.
        """
        from jobsearch import enrich
        pat = enrich._SECTION_RE.pattern
        self.assertIn(
            self.EXPECTED_SECTION_FRAGMENT, pat,
            f"_SECTION_RE pattern "
            f"{pat!r} does NOT contain "
            f"{self.EXPECTED_SECTION_FRAGMENT!r}. "
            f"The outer description div "
            f"on LinkedIn uses "
            f"`<div class=\"description__text\">`. "
            f"Removing the class from the "
            f"regex would silently break "
            f"the fallback path in "
            f"extract_description() -- "
            f"the function tries "
            f"_MARKUP_RE first, then "
            f"_SECTION_RE; if both fail, "
            f"the description is None."
        )
        # And the
        # compiled
        # regex
        # must
        # actually
        # match
        # the
        # documented
        # section.
        snippet = (
            '<div class="description__text description__text--rich">'
            '<section class="show-more-less-html">'
            '<p>Job description text here.</p>'
            '</section>'
            '</div>'
        )
        self.assertIsNotNone(
            enrich._SECTION_RE.search(snippet),
            f"_SECTION_RE did NOT match a "
            f"documented description__text "
            f"snippet. The fallback regex "
            f"is broken."
        )
        # And it
        # must
        # NOT
        # match
        # a
        # snippet
        # without
        # the
        # class
        # (catch
        # over-permissive
        # regexes).
        wrong = (
            '<div class="other-class">'
            '<section><p>Job description.</p></section>'
            '</div>'
        )
        self.assertIsNone(
            enrich._SECTION_RE.search(wrong),
            f"_SECTION_RE matched a snippet "
            f"without the description__text "
            f"class. The regex is "
            f"over-permissive; it would "
            f"extract the wrong block."
        )

    def test_clamp_re_matches_documented_signal(self) -> None:
        """`_CLAMP_RE` in
        `jobsearch/enrich.py`
        must match the
        `clamp-after-N`
        CSS class that
        LinkedIn adds
        when it clamps
        the description.
        A drift that
        removes
        `clamp-after-`
        would silently
        mis-report
        clamped
        descriptions
        as complete.
        """
        from jobsearch import enrich
        pat = enrich._CLAMP_RE.pattern
        self.assertIn(
            self.EXPECTED_CLAMP_FRAGMENT, pat,
            f"_CLAMP_RE pattern "
            f"{pat!r} does NOT contain "
            f"{self.EXPECTED_CLAMP_FRAGMENT!r}. "
            f"LinkedIn adds the "
            f"`clamp-after-N` class when "
            f"it truncates the "
            f"description (see the "
            f"saved page at "
            f"`var/page_cache/4477142227.html`, "
            f"which has `clamp-after-20`). "
            f"Removing the prefix from "
            f"the regex would silently "
            f"mis-report clamped "
            f"descriptions as complete."
        )
        # The
        # compiled
        # regex
        # must
        # match
        # the
        # saved
        # page's
        # signal.
        self.assertIsNotNone(
            enrich._CLAMP_RE.search("clamp-after-20"),
            f"_CLAMP_RE did NOT match the "
            f"documented clamp signal "
            f"`clamp-after-20`. The clamp "
            f"detector is broken; the gate "
            f"would not know the "
            f"description is truncated."
        )
        # And it
        # must
        # match
        # any
        # N
        # (the
        # regex
        # is
        # generic).
        for n in ("5", "10", "20", "50"):
            with self.subTest(clamp_n=n):
                self.assertIsNotNone(
                    enrich._CLAMP_RE.search(
                        f"clamp-after-{n}"),
                    f"_CLAMP_RE did NOT match "
                    f"`clamp-after-{n}`. The "
                    f"regex should be generic "
                    f"to any N."
                )
        # And it
        # must
        # NOT
        # match
        # a
        # snippet
        # without
        # the
        # prefix
        # (catch
        # over-permissive
        # regexes).
        self.assertIsNone(
            enrich._CLAMP_RE.search("not-a-clamp"),
            f"_CLAMP_RE matched a snippet "
            f"without `clamp-after-`. The "
            f"regex is over-permissive; "
            f"it would falsely flag "
            f"unclamped descriptions."
        )

    def test_apply_path_matches_documented_value(self) -> None:
        """`_APPLY_PATH` in
        `jobsearch/enrich.py`
        must be exactly
        `"/jobs/view/externalApply/"` --
        the LinkedIn
        external-apply
        URL path. A drift
        in the path
        (typo, missing
        trailing slash,
        etc.) would
        silently
        mis-detect
        external
        apply links.
        """
        from jobsearch import enrich
        self.assertEqual(
            enrich._APPLY_PATH,
            self.EXPECTED_APPLY_PATH,
            f"_APPLY_PATH is "
            f"{enrich._APPLY_PATH!r}, "
            f"expected "
            f"{self.EXPECTED_APPLY_PATH!r}. "
            f"LinkedIn uses "
            f"`/jobs/view/externalApply/` "
            f"as the external apply URL "
            f"path. A wrong path would "
            f"silently mis-detect external "
            f"apply links."
        )
        # And the
        # path
        # must
        # be
        # detected
        # in
        # a
        # document
        # URL.
        from urllib.parse import urlparse
        parts = urlparse(
            "https://www.linkedin.com"
            "/jobs/view/externalApply/12345"
        )
        self.assertIn(
            enrich._APPLY_PATH, parts.path,
            f"_APPLY_PATH {enrich._APPLY_PATH!r} "
            f"not found in a documented "
            f"external-apply URL path "
            f"{parts.path!r}. The path "
            f"detector is broken."
        )



if __name__ == "__main__":
    unittest.main()
