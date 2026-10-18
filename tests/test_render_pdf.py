"""Tests for the PDF delivery renderer (tools/render_pdf.py).

What these lock down, and why each one matters for a delivery the owner reads
every morning:

  * the output is a real PDF with an embedded link -- not a text file wearing a
    .pdf extension, which is what a rendering mistake produces;
  * a description that was never retrieved is REPORTED as missing, never filled
    in;
  * pay is printed when the posting states it and reported as "not stated"
    otherwise -- a guessed salary in a job list is worse than no salary;
  * a hard-avoid role is counted as dropped, and named when asked for --
    dropping is fine, hiding is not;
  * a job the owner already decided on is never offered again.

The profile is pointed at a path that does not exist so the rules are the empty
defaults: the same tests then behave identically on the owner's machine and in a
stranger's checkout, and cannot start failing because his profile changed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import reportlab  # noqa: F401
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False

from jobsearch import db as jobdb  # noqa: E402
from jobsearch import notify  # noqa: E402
from tools import render_pdf  # noqa: E402

NOW = "2026-10-13T00:00:00+00:00"

# The PDF renderer degrades to plain text when reportlab is absent, so the
# three tests below that assert a real PDF are skipped on a minimal install.
# Install the optional extra to run them: pip install 'jobsearch-pipeline[pdf]'.
_RENDER_PDF_SKIP = unittest.skipUnless(
    _HAS_REPORTLAB, "reportlab not installed (optional 'pdf' extra)"
)


def _add_job(con, *, title, company="Acme Ltd", location="Lisbon, Portugal",
             url="https://example.invalid/jobs/1", description=None,
             # W3.3: default to "complete" so existing tests
             # behave as before. Tests that need to exercise
             # the not_judged path pass description_state
             # explicitly.
             description_state="complete", salary_text=None) -> int:
    cur = con.execute(
        """INSERT INTO jobs (dedupe_key, title, company, location, remote, url,
             external_job_id, description, description_state, salary_text,
             status, first_seen_at, last_seen_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"dedupe:{title}", title, company, location, None, url, None,
         description, description_state, salary_text, "open", NOW, NOW, NOW, NOW),
    )
    con.commit()
    return int(cur.lastrowid)


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._prev_profile = os.environ.get("JOBSEARCH_PROFILE")
        os.environ["JOBSEARCH_PROFILE"] = str(
            Path(self.tmp.name) / "absent-profile.yaml"
        )
        self.addCleanup(self._restore_profile)
        self.db = Path(self.tmp.name) / "jobs.db"
        self.con = jobdb.connect(self.db)

    def _restore_profile(self) -> None:
        if self._prev_profile is None:
            os.environ.pop("JOBSEARCH_PROFILE", None)
        else:
            os.environ["JOBSEARCH_PROFILE"] = self._prev_profile

    # ---------------------------------------------------------------- shape

    @_RENDER_PDF_SKIP
    def test_output_is_a_real_pdf_with_a_clickable_link(self) -> None:
        _add_job(self.con, title="Backend Engineer",
                 url="https://example.invalid/jobs/42")
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        self.assertEqual(len(surfaced), 1)
        self.assertEqual(len(dropped), 0)

        out = Path(self.tmp.name) / "digest.pdf"
        render_pdf.render_pdf(surfaced, dropped, not_judged, stats, False, out, 200)

        data = out.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"), "not a PDF file")
        self.assertIn(b"/URI", data, "the posting link is not embedded as a link")
        self.assertGreater(len(data), 1000)

    def test_header_counts_match_the_ledger(self) -> None:
        _add_job(self.con, title="Backend Engineer")
        _add_job(self.con, title="Sales Manager")  # hard-avoid -> dropped
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        self.assertEqual(stats["read"], 2)
        self.assertEqual(stats["surfaced"], 1)
        self.assertEqual(stats["dropped"], 1)

    # ------------------------------------------------------ honesty in print

    def test_missing_description_is_reported_not_invented(self) -> None:
        _add_job(self.con, title="Backend Engineer", description=None)
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        text = render_pdf._text_report(surfaced, dropped, not_judged, stats, False)
        self.assertIn("not yet retrieved", text)

    def test_the_description_label_appears_exactly_once(self) -> None:
        """Regression: a doubled prefix shipped once ("Description: Description:")."""
        _add_job(self.con, title="Backend Engineer", description=None)
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        text = render_pdf._text_report(surfaced, dropped, not_judged, stats, False)
        self.assertIn("Description: not yet retrieved", text)
        self.assertNotIn("Description: Description:", text)

    def test_a_retrieved_description_is_printed_verbatim(self) -> None:
        body = "We are looking for a backend engineer with SQLite experience."
        _add_job(self.con, title="Backend Engineer", description=body,
                 description_state="complete")
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        text = render_pdf._text_report(surfaced, dropped, not_judged, stats, False)
        self.assertIn("SQLite experience", text)

    def test_pay_is_printed_only_when_the_posting_states_it(self) -> None:
        # Synthetic fixture value, deliberately not a real
        # salary. The test asserts that the renderer prints
        # the posting's own pay line verbatim and falls back
        # to "not stated in the posting" for jobs that carry
        # no salary_text at all.
        _add_job(self.con, title="Backend Engineer",
                 salary_text="9,999 EUR per month")
        _add_job(self.con, title="Frontend Engineer")  # nothing stated
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, False, None)
        text = render_pdf._text_report(surfaced, dropped, not_judged, stats, False)
        self.assertIn("9,999 EUR per month", text)
        self.assertIn("not stated in the posting", text)

    # ------------------------------------------------- dropped, not hidden

    def test_hard_avoid_role_is_dropped_and_named_when_listed(self) -> None:
        _add_job(self.con, title="Sales Manager", company="Retail Co")
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, True, None)
        self.assertEqual(len(surfaced), 0)
        self.assertEqual(len(dropped), 1)

        hidden = render_pdf._text_report(surfaced, dropped, not_judged, stats, False)
        self.assertNotIn("Retail Co", hidden, "dropped jobs must not appear by default")

        listed = render_pdf._text_report(surfaced, dropped, not_judged, stats, True)
        self.assertIn("DROPPED", listed)
        self.assertIn("Sales Manager", listed)

    def test_a_decided_job_is_never_offered_again(self) -> None:
        job_id = _add_job(self.con, title="Backend Engineer")
        notify.record_decision(self.con, job_id, "reject")

        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, True, None)
        self.assertEqual(len(surfaced), 0, "an already-decided job resurfaced")
        self.assertEqual(len(dropped), 0, "a decided job was re-counted as dropped")

    @_RENDER_PDF_SKIP
    def test_pdf_includes_dropped_jobs_when_include_unsuitable(self) -> None:
        """The PDF renderer's `include_unsuitable=True` branch
        must list the dropped jobs in the report. The text
        branch is tested by
        `test_hard_avoid_role_is_dropped_and_named_when_listed`,
        but the PDF branch (line 262 of render_pdf.py:
        `if include_unsuitable and dropped:`) was not.

        A future contributor who refactors the PDF
        rendering to a single code path that ignores
        `include_unsuitable` would silently break the
        CLI flag -- the text report would still list
        dropped jobs (covered) but the PDF would hide
        them (not covered). This test pins the PDF
        branch by checking that a hard-avoid job's
        title is embedded in the PDF when the flag is
        set, and is NOT embedded when the flag is
        unset.

        The PDF text is compressed via FlateDecode +
        ASCII85Decode, so a bytewise `assertIn` would
        miss the strings. The test decodes every
        stream in the PDF and asserts on the decoded
        text, which is the actual rendered content
        a reader sees. If ReportLab ever changes its
        compression scheme, this helper is the one
        place that needs to change -- the assertions
        stay stable.
        """
        import base64
        import re
        import zlib

        def _pdf_text(data: bytes) -> str:
            """Decode every ASCII85+FlateDecode stream
            in a ReportLab PDF and return the
            concatenated text. A noop if the PDF has
            no streams."""
            chunks = []
            for block in re.findall(
                    rb"stream(.*?)endstream", data, re.S):
                s = block.lstrip(b"\r\n").rstrip(b"\r\n")
                if s.endswith(b"~>"):
                    s = s[:-2]
                try:
                    decoded = base64.a85decode(s, adobe=False)
                    decoded = zlib.decompress(decoded)
                    chunks.append(
                        decoded.decode("latin-1", errors="replace"))
                except Exception:
                    try:
                        decoded = zlib.decompress(s)
                        chunks.append(
                            decoded.decode("latin-1", errors="replace"))
                    except Exception:
                        continue
            return "\n".join(chunks)

        # Two jobs: one surfaces, one is hard-avoid.
        _add_job(self.con, title="Backend Engineer")
        _add_job(self.con, title="Sales Manager", company="Retail Co")
        surfaced, dropped, not_judged, stats, _ = render_pdf.collect(self.db, True, None)
        self.assertEqual(len(surfaced), 1, "Backend Engineer should surface")
        self.assertEqual(len(dropped), 1, "Sales Manager should be dropped")
        # Build the PDF with include_unsuitable=True
        # -- the dropped job should appear in the PDF.
        out_included = Path(self.tmp.name) / "included.pdf"
        render_pdf.render_pdf(
            surfaced, dropped, not_judged, stats,
            True, out_included, 200,
        )
        included_text = _pdf_text(out_included.read_bytes())
        # A defence-in-depth check: the PDF should
        # contain the "Dropped by the gate" header
        # that the include_unsuitable branch emits.
        # If this assertion passes but the per-job
        # check below fails, the bug is in the loop,
        # not the header.
        self.assertIn(
            "Dropped by the gate", included_text,
            f"include_unsuitable=True PDF must have a "
            f"Dropped header; got: {included_text[:300]!r}"
        )
        # The dropped job's title and company must
        # appear in the PDF text.
        self.assertIn(
            "Sales Manager", included_text,
            f"include_unsuitable=True PDF must list the "
            f"dropped job; got: {included_text[:300]!r}"
        )
        self.assertIn(
            "Retail Co", included_text,
            f"include_unsuitable=True PDF must list the "
            f"dropped job's company; got: "
            f"{included_text[:300]!r}"
        )
        # Now build the PDF with include_unsuitable=False
        # -- the dropped job should NOT appear.
        out_hidden = Path(self.tmp.name) / "hidden.pdf"
        render_pdf.render_pdf(
            surfaced, dropped, not_judged, stats,
            False, out_hidden, 200,
        )
        hidden_text = _pdf_text(out_hidden.read_bytes())
        self.assertNotIn(
            "Sales Manager", hidden_text,
            f"include_unsuitable=False PDF must hide the "
            f"dropped job; got: {hidden_text[:300]!r}"
        )
        self.assertNotIn(
            "Retail Co", hidden_text,
            f"include_unsuitable=False PDF must hide the "
            f"dropped job's company; got: "
            f"{hidden_text[:300]!r}"
        )

    @_RENDER_PDF_SKIP
    def test_pdf_includes_not_judged_section(self) -> None:
        """The PDF renderer's `not_judged` branch
        (line 276 of render_pdf.py: `if not_judged:`)
        must produce a "Not yet retrieved" section
        that names each not-judged job's title and
        company. The text-mode branch is tested by
        `test_missing_description_is_reported_not_invented`
        and `test_the_description_label_appears_exactly_once`,
        but the PDF branch (line 276) was not.

        W3.3: not_judged is its own section, NOT a
        verdict. A reader who sees this list knows
        the next step is to fetch the description,
        not to evaluate a verdict the gate never
        made. A future contributor who refactors the
        PDF rendering and drops the not_judged
        section would silently hide the jobs that
        need fetching -- the worst possible
        failure mode, because the user thinks
        there's nothing to do.

        The test decodes the PDF's ASCII85+FlateDecode
        streams (same helper as
        test_pdf_includes_dropped_jobs_when_include_unsuitable)
        and asserts that the section header, the
        not-judged job's title, and the company are
        all present in the rendered text.
        """
        import base64
        import re
        import zlib

        def _pdf_text(data: bytes) -> str:
            chunks = []
            for block in re.findall(
                    rb"stream(.*?)endstream", data, re.S):
                s = block.lstrip(b"\r\n").rstrip(b"\r\n")
                if s.endswith(b"~>"):
                    s = s[:-2]
                try:
                    decoded = base64.a85decode(s, adobe=False)
                    decoded = zlib.decompress(decoded)
                    chunks.append(
                        decoded.decode("latin-1", errors="replace"))
                except Exception:
                    continue
            return "".join(chunks)

        # A job with description_state='not_yet_retrieved'
        # (or no description) ends up in not_judged.
        _add_job(
            self.con, title="Backend Engineer (No Description)",
            company="Mystery Co",
            description=None,
            description_state="not_yet_retrieved",
        )
        # Add a normal job too so the PDF is non-trivial.
        _add_job(self.con, title="Backend Engineer (Normal)")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        # The not-judged job is in not_judged.
        self.assertEqual(
            len(not_judged), 1,
            f"expected exactly one not-judged entry; "
            f"got {len(not_judged)}. Test setup wrong."
        )
        # Render the PDF and decode it.
        out = Path(self.tmp.name) / "not_judged.pdf"
        render_pdf.render_pdf(
            surfaced, dropped, not_judged, stats,
            False, out, 200,
        )
        pdf_text = _pdf_text(out.read_bytes())
        # The section header is the primary
        # signal. A contributor who removes the
        # header (e.g. by inlining the not-judged
        # rows into the surfaced list) would
        # silently break W3.3's "its own section,
        # not a verdict" contract.
        self.assertIn(
            "Not yet retrieved", pdf_text,
            f"PDF must include the 'Not yet retrieved' "
            f"section header; got: {pdf_text[:500]!r}"
        )
        # The not-judged job's title must be in
        # the PDF. A contributor who filters the
        # not_judged list (e.g. by reusing the
        # 'surfaced' list) would silently drop
        # the not-judged rows.
        # ReportLab escapes parens in PDF text
        # strings (a left-paren becomes \( and
        # a right-paren becomes \)), so the
        # decoded stream contains the *escaped*
        # form. We assert on the escaped form
        # so the parens are part of the match
        # and the title is uniquely identified.
        self.assertIn(
            r"\(No Description\)",
            pdf_text,
            f"PDF must include the not-judged job's "
            f"title (escaped form); got: "
            f"{pdf_text[:500]!r}"
        )
        # The not-judged job's company must be in
        # the PDF. A contributor who broke the
        # row format (e.g. forgot to interpolate
        # the company) would silently make the
        # section useless to the reader.
        self.assertIn(
            "Mystery Co", pdf_text,
            f"PDF must include the not-judged job's "
            f"company; got: {pdf_text[:500]!r}"
        )
        # The normal (surfaced) job is in the
        # same PDF, so a contributor who broke
        # the PDF entirely would fail this
        # assertion (regression).
        self.assertIn(
            r"\(Normal\)",
            pdf_text,
            f"PDF must also include the surfaced "
            f"job's title (escaped form, regression "
            f"check); got: {pdf_text[:500]!r}"
        )

    def test_limit_caps_the_surfaced_jobs(self) -> None:
        """`collect(..., limit=N)` must return at most N
        surfaced jobs, ranked by fit. The cap is what
        the `--limit` CLI flag relies on; a future
        contributor who changes the sort order without
        thinking about the cap could break the morning
        PDF's "first 10 jobs" contract.

        The test is the contract pin for the CLI flag
        -- it asserts the count exactly so a future
        contributor who quietly drops the cap
        (`surfaced = surfaced[:limit]`) fails the test
        with a precise "got 3, want 2" message.

        A note on the limit=0 case: the current
        implementation is `if limit:` (a truthy
        check), so `--limit 0` is treated as "no
        limit" and returns all jobs. This is a
        Python idiom footgun -- a future contributor
        who switches to `if limit is not None:`
        would change the behaviour, and the test
        would fail with a precise error message.
        The test documents the *current* contract
        (limit=0 == no limit) so a contributor who
        wants to change the behaviour has to update
        the test in the same commit.
        """
        # Three jobs that surface (NEEDS RESEARCH is the
        # weakest band, so all three rank).
        for title in ("Backend Engineer",
                      "Backend Engineer (Senior)",
                      "Backend Engineer (Staff)"):
            _add_job(self.con, title=title)
        # No limit -- all three surface.
        surfaced_all, _, _, _, _ = render_pdf.collect(self.db, False, None)
        self.assertEqual(
            len(surfaced_all), 3,
            f"all three jobs should surface with no limit; "
            f"got {len(surfaced_all)}"
        )
        # Limit=2 -- only the first two (by fit rank) surface.
        surfaced_lim, _, _, stats, _ = render_pdf.collect(
            self.db, False, 2,
        )
        self.assertEqual(
            len(surfaced_lim), 2,
            f"limit=2 must cap surfaced to 2; "
            f"got {len(surfaced_lim)}"
        )
        # The cap does NOT change the read stat --
        # the ledger still had 3 postings; the cap
        # is a presentation-only thing. A future
        # contributor who conflates "read" with
        # "surfaced" fails this assertion.
        self.assertEqual(
            stats["read"], 3,
            f"limit must not change the read count; "
            f"got stats={stats!r}"
        )
        # Limit=1 is the edge case where exactly one
        # job survives.
        surfaced_one, _, _, _, _ = render_pdf.collect(
            self.db, False, 1,
        )
        self.assertEqual(
            len(surfaced_one), 1,
            f"limit=1 must cap surfaced to 1; "
            f"got {len(surfaced_one)}"
        )
        # Limit=0 documents the current footgun:
        # `if limit:` treats 0 as falsy, so limit=0
        # means "no limit" (all jobs survive). A
        # contributor who wants `--limit 0` to
        # produce an empty digest must change the
        # cap to `if limit is not None:` and update
        # this assertion in the same change.
        surfaced_zero, _, _, _, _ = render_pdf.collect(
            self.db, False, 0,
        )
        self.assertEqual(
            len(surfaced_zero), 3,
            f"limit=0 currently means 'no limit' (the "
            f"`if limit:` truthy check); got "
            f"{len(surfaced_zero)}. If you intended to "
            f"change this to 'empty digest', update the "
            f"cap in render_pdf.py: `if limit is not "
            f"None:` and change this assertion to 0 "
            f"in the same commit."
        )


if __name__ == "__main__":
    unittest.main()
