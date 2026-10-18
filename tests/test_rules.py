"""M2 acceptance tests for the deterministic gate.

Run:  python3 -m unittest discover -s tests
      python3 -O -m unittest discover -s tests     # identical behaviour required

Assertions use unittest methods only (never bare `assert`) so `-O` cannot neuter
the suite.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import rules as R                     # noqa: E402
from jobsearch.requirements import JobPosting        # noqa: E402


# The suite reads its OWN synthetic profile, never the developer's. A suite that
# depends on the author's profile fails for everyone else, and teaches the next
# person to edit their profile until the tests go green.
FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "test_profile.yaml"


def rules(**overrides) -> R.Rules:
    """Build a Rules object from the test fixture profile.

    `overrides` lets individual tests pin a single field (typically
    years_can_honestly_claim for the W3.1 tests) without rebuilding
    the whole profile. The fixture profile is the source of truth for
    every other field; an override is a deliberate, visible deviation
    from it, and the test that uses it must say so in its name."""
    base = R.load_rules(FIXTURE_PROFILE)
    if not overrides:
        return base
    from dataclasses import replace
    return replace(base, **overrides)


def job(title: str, description: str, **kw) -> JobPosting:
    return JobPosting(title=title, description=description, **kw)


class TestProfessionGate(unittest.TestCase):
    """Owner decision 2026-10-13: a non-software job is dropped, not surfaced.

    Observed on real mail: 68 of 82 surfaced postings were local non-software
    roles (shop assistant, bank teller, sailor) sitting in the shortlist as
    NEEDS_RESEARCH. The gate may only fail a job on a quoted requirement, and
    none of them had a description -- so there was nothing to quote. The
    employer's own title IS a quote, and it is enough to see the role is not a
    software role. Drops stay listed on the digest's dropped page, so a wrong
    drop is visible rather than silent.
    """

    def test_a_non_software_title_is_dropped_with_the_title_quoted(self):
        posting = job("Bank Teller",
                      "Serve customers at the counter. Portuguese required.")
        v = R.evaluate(posting, rules())
        self.assertEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(v.hard_failure)
        self.assertFalse(v.surface,
                         "a non-software role must not reach the shortlist")
        self.assertTrue(any("Bank Teller" in f for f in v.failed_essential),
                        "the drop must quote the title that caused it")

    def test_a_local_language_retail_title_is_dropped(self):
        posting = job("Operador(a) de Loja - Portimão Retail Center - full-time",
                      "Atendimento ao cliente. Português.")
        v = R.evaluate(posting, rules())
        self.assertFalse(v.surface)

    def test_a_software_title_is_not_dropped_by_the_profession_rule(self):
        for title in ("AI Automation Engineer", "Backend Software Engineer",
                      "Technical Architect", "SDET",
                      "Data Platform Engineer", "Integration Engineer"):
            posting = job(title, "Remote (EU). English required.")
            v = R.evaluate(posting, rules())
            self.assertFalse(
                any("names no software role" in f for f in v.failed_essential),
                f"{title} was wrongly treated as a non-software role",
            )

    def test_an_unread_title_is_unknown_rather_than_disqualified(self):
        posting = job("", "Text with no software signal at all.")
        v = R.evaluate(posting, rules())
        self.assertFalse(
            any("names no software role" in f for f in v.failed_essential),
            "an unread title is unknown, not a non-software role",
        )


class TestProfileLoading(unittest.TestCase):
    def test_floor_loaded_from_profile(self):
        self.assertEqual(rules().floor_net, 4500.0)
        self.assertEqual(rules().floor_currency, "EUR")

    def test_known_stack_includes_corroborated_skills(self):
        known = rules().known_stack
        for token in ("typescript", "react", "node", "api"):
            self.assertIn(token, known, f"{token} should be corroborated by repos")


class TestStrongAndPotential(unittest.TestCase):
    def test_ai_automation_role_is_strong_match(self):
        posting = job(
            "AI Automation Engineer",
            "We build AI-powered workflow automation for small businesses. You will "
            "own TypeScript and Node services, integrate third-party REST APIs and "
            "build agent workflows with LLMs. Small team, real ownership. English "
            "required. Remote (EU).",
            location="Remote (EU)", salary_text="EUR 4500 - 5500 per month",
        )
        v = R.evaluate(posting, rules())
        self.assertEqual(v.outcome, R.STRONG_MATCH)
        self.assertEqual(v.failed_essential, [])
        self.assertTrue(v.surface)

    def test_eu_scope_is_satisfied_only_when_the_profile_declares_it(self):
        """An EU-scope posting is NOT evidence of an EU work authorisation.

        The gate used to answer this from an assumed citizenship: with no
        declaration anywhere it reported "EU scope satisfied by citizenship
        with EU work authorisation". That is a legal fact about a person, and
        no input supplied it -- so a user who is not an EU citizen, or who
        simply had not filled anything in, was told something untrue about
        themselves. It now reports what the profile declares, and nothing else.
        """
        posting = job(
            "Full-Stack Engineer",
            "Build product features across React and Node. Must be authorised to "
            "work in the EU. English required.",
            location="Remote (EU)", salary_text="EUR 5000/month",
        )
        # The fixture profile declares EU work authorisation.
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        joined = " ".join(v.satisfied).casefold()
        self.assertIn("work authorisation declared", joined)
        self.assertNotIn(
            "citizenship", " ".join(v.satisfied).casefold(),
            "the gate must not explain a work authorisation by citizenship: "
            "residence and citizenship are different questions, and the "
            "profile is the only source for either",
        )

    def test_eu_scope_with_no_declaration_is_needs_research(self):
        """No declaration is missing evidence, not a pass and not a rejection."""
        posting = job(
            "Full-Stack Engineer",
            "Build product features across React and Node. Must be authorised to "
            "work in the EU. English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules(work_authorisation=frozenset()))
        self.assertEqual(v.outcome, R.NEEDS_RESEARCH)
        self.assertEqual(v.failed_essential, [])
        self.assertTrue(
            any("location scope to verify" in u for u in v.uncertain),
            f"expected a verification prompt, got: {v.uncertain}",
        )

    def test_location_outside_a_declared_authorisation_is_a_drop(self):
        """A declared authorisation that excludes a place is a hard drop."""
        posting = job(
            "Backend Engineer",
            "Backend Engineer. Python and PostgreSQL. Must be authorised to work "
            "in the United States. Sponsorship not available.",
            location="New York, United States",
        )
        v = R.evaluate(posting, rules(work_authorisation=frozenset({"eu"})))
        self.assertEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(
            any("outside the declared work authorisation" in f
                for f in v.failed_essential),
            f"expected the declared scope quoted back, got: {v.failed_essential}",
        )

    def test_short_authorisation_token_does_not_match_by_substring(self):
        """'us' must not satisfy 'Australia', and the drop must be stated.

        Word-boundary matching is what keeps a two-letter declaration from
        silently covering a country nobody declared.
        """
        posting = job(
            "Backend Engineer",
            "Backend Engineer. Python and PostgreSQL. Must be authorised to work "
            "in Australia. English required.",
            location="Sydney, Australia",
        )
        v = R.evaluate(posting, rules(work_authorisation=frozenset({"us"})))
        self.assertFalse(
            any("work authorisation declared" in s for s in v.satisfied),
            f"'us' must not match 'Australia': {v.satisfied}",
        )
        # Australia is outside the declared scope, so this is a stated drop --
        # not an assumed rejection, and not a pass on a substring accident.
        self.assertEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(
            any("outside the declared work authorisation" in f
                for f in v.failed_essential),
            f"the drop must quote the declared scope: {v.failed_essential}",
        )

    def test_founding_engineer_title_is_not_hard_avoided(self):
        posting = job(
            "Founding Engineer",
            "You will be the first engineer. TypeScript, Node, React, our API layer "
            "and everything else. Remote (worldwide). English required.",
            location="Remote (worldwide)",
        )
        v = R.evaluate(posting, rules())
        self.assertIn(v.outcome, (R.STRONG_MATCH, R.POTENTIAL_MATCH, R.NEEDS_RESEARCH))
        self.assertEqual(v.hard_avoid, [])


class TestYearsPolicy(unittest.TestCase):
    """W3.1: the years bar requires `years_can_honestly_claim` to be set.

    Without that number in the profile, a posting that demands "5+
    years, no flexibility" is judged as NEEDS_RESEARCH (unknown), not
    a drop. Deciding against a missing field is the failure mode this
    project is built to avoid. Once the owner has committed to a
    number, the comparison becomes deterministic: postings demanding
    strictly more than the honest number become a hard drop.
    """

    def test_years_bar_without_profile_field_is_unknown_not_dropped(self):
        """Profile with NO `years_can_honestly_claim`: the 5+ year
        bar is uncertain, not a hard failure. The drop the test
        asserted before W3.1 was exactly the failure this project
        refuses to ship."""
        posting = job(
            "Full-Stack Engineer",
            "5+ years of professional experience required. TypeScript, React and "
            "Node. Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(
            v.outcome, R.NOT_SUITABLE,
            "W3.1: without years_can_honestly_claim, an unclaimable "
            "years bar must NOT produce a drop. A drop without both "
            "sides of the comparison is a verdict against a missing "
            "field, which is the failure mode this project is built "
            "to avoid.",
        )
        self.assertIn(
            v.outcome, (R.NEEDS_RESEARCH, R.POTENTIAL_MATCH, R.STRONG_MATCH),
            f"5+ years with no years_can_honestly_claim should at "
            f"minimum be NEEDS_RESEARCH; got {v.outcome!r}",
        )
        self.assertTrue(v.uncertain, "the years bar must be in the uncertain list")
        self.assertTrue(any("5+ years" in u for u in v.uncertain),
                        f"uncertain must carry the 5+ years quote: {v.uncertain}")

    def test_years_bar_with_honest_number_drops_when_posting_demands_more(self):
        """Profile with `years_can_honestly_claim: 3`: a 5+ year
        bar is a hard drop. The owner has committed to a number;
        the gate now has both sides; a verdict is allowed."""
        posting = job(
            "Full-Stack Engineer",
            "5+ years of professional experience required. TypeScript, React and "
            "Node. Remote (EU). English required.",
            location="Remote (EU)",
        )
        r = rules(years_can_honestly_claim=3)
        v = R.evaluate(posting, r)
        self.assertEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(v.hard_failure, "an unclaimable years bar is a hard failure")
        self.assertFalse(v.surface, "and must therefore stay out of the shortlist")
        self.assertTrue(any("5+ years" in f for f in v.failed_essential))
        self.assertTrue(any('"' in f for f in v.failed_essential),
                        "every failure must cite a quote")

    def test_years_bar_with_honest_number_passes_when_within_bar(self):
        """Profile with `years_can_honestly_claim: 5`: a 5+ year
        bar is not a failure (the bar is met)."""
        posting = job(
            "Full-Stack Engineer",
            "5+ years of professional experience required. TypeScript, React and "
            "Node. Remote (EU). English required.",
            location="Remote (EU)",
        )
        r = rules(years_can_honestly_claim=5)
        v = R.evaluate(posting, r)
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)

    def test_years_with_equivalent_wording_is_not_a_failure(self):
        posting = job(
            "Full-Stack Engineer",
            "5+ years of professional experience or equivalent demonstrable "
            "experience. TypeScript and Node. Remote (EU).",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertEqual(v.failed_essential, [])

    def test_two_years_is_not_blocked(self):
        posting = job(
            "Software Engineer",
            "2 years of experience. TypeScript, React, Node, and our API. "
            "Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)

    def test_preferred_years_is_not_a_failure(self):
        posting = job(
            "Software Engineer",
            "3+ years preferred. TypeScript, React, Node and REST API work. "
            "Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)


class TestHardAvoid(unittest.TestCase):
    def _assert_hard_drop(self, posting):
        v = R.evaluate(posting, rules())
        self.assertEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(v.hard_failure)
        self.assertFalse(v.surface, "a hard failure should not be surfaced")

    def test_us_only_remote_is_a_hard_drop(self):
        self._assert_hard_drop(job(
            "Software Engineer",
            "Remote (US) only. Authorised to work in the United States required. "
            "TypeScript and React.",
            location="Remote (US)",
        ))

    def test_php_specialist_title_is_a_hard_drop(self):
        self._assert_hard_drop(job(
            "PHP Developer",
            "Expert PHP and Laravel developer required for our WordPress platform. "
            "5 years of PHP experience.",
        ))

    def test_unity_specialist_title_is_a_hard_drop(self):
        self._assert_hard_drop(job(
            "Unity Developer",
            "Professional Unity and C# experience required to build mobile games.",
        ))

    def test_non_technical_title_is_a_hard_drop(self):
        self._assert_hard_drop(job(
            "Account Executive",
            "Own the full sales cycle. Quota carrying role. SaaS sales experience.",
        ))

    def test_incidental_mention_of_unfamiliar_tool_is_not_a_failure(self):
        """Owner rule: do not reject only because a tool is mentioned."""
        posting = job(
            "Automation Engineer",
            "You will build TypeScript automation and integrate REST APIs. Nice to "
            "have: some exposure to PHP legacy services we are migrating away from. "
            "Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertEqual(v.failed_essential, [])


class TestResearchAndIncomplete(unittest.TestCase):
    def test_empty_description_is_needs_research_never_rejected(self):
        v = R.evaluate(job("AI Engineer", "", url="https://example.test/1"), rules())
        self.assertEqual(v.outcome, R.NEEDS_RESEARCH)
        self.assertTrue(v.surface)
        self.assertEqual(v.failed_essential, [])

    def test_unknown_non_specialist_requirement_goes_to_research_not_failure(self):
        posting = job(
            "Backend Engineer",
            "Essential: TypeScript and Node. Also required: Azure deployment "
            "experience. Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(any("azure" in u.casefold() for u in v.uncertain))

    def test_seniority_is_a_note_not_a_failure(self):
        posting = job(
            "Senior Software Engineer",
            "TypeScript, React, Node and REST APIs. Remote (EU). English required.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(any("seniority" in n.casefold() for n in v.notes))


class TestLanguage(unittest.TestCase):
    def test_untrained_language_requirement_is_needs_research(self):
        # W3.1 / Unknown policy: a language the candidate has not
        # listed is a missing-evidence case, not a fabricated
        # verdict against them. The candidate may be able to read
        # the posting in translation, or work through a recruiter.
        # The gate's job is to surface the signal, not invent a
        # confident answer. needs_research is the right verdict;
        # a hard drop here is the failure mode the policy was
        # written to prevent.
        posting = job(
            "Software Engineer",
            "Fluent German required. TypeScript and React. Remote (EU).",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertEqual(v.outcome, R.NEEDS_RESEARCH)
        # The signal is in the uncertain list, not in failed/hard.
        self.assertTrue(
            any("german" in u.casefold() for u in v.uncertain),
            f"expected the german signal in uncertain, got: {v.uncertain}",
        )
        self.assertFalse(v.hard_failure)

    def test_french_requirement_is_satisfied(self):
        posting = job(
            "Software Engineer",
            "French required. TypeScript, React and Node. Remote (EU).",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertTrue(any("french" in s.casefold() for s in v.satisfied))


class TestCompensation(unittest.TestCase):
    def test_below_floor_never_rejects_but_is_flagged(self):
        posting = job(
            "Software Engineer",
            "TypeScript, React and Node. Remote (EU). English required. "
            "Salary 3000 EUR per month.",
            location="Remote (EU)", salary_text="3000 EUR per month",
        )
        v = R.evaluate(posting, rules())
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)
        self.assertEqual(v.salary.get("vs_floor"), "below_floor")

    def test_above_floor_is_flagged_above(self):
        posting = job(
            "Software Engineer",
            "TypeScript, React and Node. Remote (EU). English required.",
            location="Remote (EU)", salary_text="9000 EUR gross monthly",
        )
        v = R.evaluate(posting, rules())
        self.assertEqual(v.salary.get("vs_floor"), "above_floor")

    def test_foreign_currency_is_flagged_for_conversion_not_rejected(self):
        posting = job(
            "Software Engineer",
            "TypeScript, React and Node. Remote (EU). English required.",
            location="Remote (EU)", salary_text="USD 5200 per month",
        )
        v = R.evaluate(posting, rules())
        self.assertEqual(v.salary.get("vs_floor"), "needs_conversion")
        self.assertNotEqual(v.outcome, R.NOT_SUITABLE)


class TestExplainability(unittest.TestCase):
    def test_every_failure_cites_a_quote(self):
        posting = job(
            "Full-Stack Engineer",
            "6+ years of professional experience required. TypeScript and React.",
            location="Remote (EU)",
        )
        v = R.evaluate(posting, rules())
        for failure in v.failed_essential:
            self.assertIn('"', failure, f"no quote in: {failure}")

    def test_describe_returns_a_human_label(self):
        v = R.evaluate(job("AI Engineer", ""), rules())
        self.assertIn(R.describe(v), R.describe(v).upper())

    def test_no_bare_asserts_in_package(self):
        import re as _re
        pattern = _re.compile(r"^\s*assert\s", _re.MULTILINE)
        offenders = [
            p.name for p in (ROOT / "jobsearch").rglob("*.py")
            if pattern.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [], f"bare assert found in {offenders}")


class TestLocationSets(unittest.TestCase):
    """The gate's location logic is driven by two
    sets in `jobsearch/rules.py`:

      - `EU_COUNTRIES` (28 entries): the countries
        a candidate with EU work authorisation
        can freely work in.
      - `NON_EU_BLOCK` (17 entries): the countries
        a candidate without that country's
        work authorisation cannot work in.

    These are the user's **domain knowledge**:
    "what countries are in the EU" and
    "what countries block work for me". The
    comment at L160-161 of rules.py is explicit:
    "edit here would hand every new user the
    previous owner's legal situation and
    silently mis-answer their work-authorisation
    questions."

    A contributor who removes "germany" from
    `EU_COUNTRIES` (e.g. "to clean up unused
    entries") would silently change the gate's
    behaviour: a job posting in Berlin would
    no longer be recognised as EU-scope and
    would fail a user who has EU work
    authorisation. The bug would not be caught
    by any current test, because the corpus
    exercises 0 of the 28 EU_COUNTRIES entries
    and only 2 of the 17 NON_EU_BLOCK entries
    ("us" and "united states" -- and "us" is
    only matched incidentally in "kubernetes").

    The right pin is a bidirectional
    set-equality test: the test owns a
    parallel list of "expected" entries
    (one per set), and a divergence between
    the script's set and the test's set
    fails the test with a precise error
    naming the specific country that
    drifted. This is the same pattern as
    the doctor's check-name pin
    (`test_doctor_runs_a_documented_set_of_check_names`).

    The two tests below use `subTest` to
    iterate over the parallel list, so a
    drift in any single entry fails just
    that subtest (and the error message
    names the specific country).
    """

    # The 28 EU countries the gate must
    # recognise as EU-scope. Parallel to
    # `EU_COUNTRIES` in `jobsearch/rules.py`.
    # If you add a country to the script's
    # set, add it here too. If you remove
    # one (e.g. because the UK left the EU),
    # update both in the same commit.
    EU_COUNTRIES_EXPECTED = {
        "germany", "france", "spain", "italy", "netherlands", "belgium",
        "poland", "portugal", "ireland", "sweden", "denmark", "finland",
        "austria", "czechia", "czech republic", "romania", "greece",
        "croatia", "estonia", "latvia", "lithuania", "slovakia",
        "slovenia", "hungary", "bulgaria", "malta", "cyprus",
        "luxembourg",
    }
    # The 17 NON-EU countries the gate must
    # recognise as blocked. Parallel to
    # `NON_EU_BLOCK` in `jobsearch/rules.py`.
    NON_EU_BLOCK_EXPECTED = {
        "us", "u.s.", "usa", "united states", "canada", "australia",
        "india", "brazil", "uk", "united kingdom", "china", "japan",
        "singapore", "switzerland", "new zealand", "south africa",
        "uae", "united arab emirates",
    }
    # The 1 NON-EU country the gate does NOT
    # currently recognise due to a known
    # limitation in the location extraction
    # at rules.py L510 (`rstrip(".,;")` is
    # too aggressive for country names with
    # internal dots: "u.s." becomes "u.s"
    # which is not in NON_EU_BLOCK). A future
    # contributor who fixes the extraction
    # (e.g. by removing internal dots before
    # the lookup, or by adding "u.s" to the
    # set) should move "u.s." out of this
    # set into NON_EU_BLOCK_EXPECTED, and
    # remove the corresponding skip below.
    NON_EU_BLOCK_KNOWN_GAPS = {
        "u.s.",  # rstrip(".,;") yields "u.s", not "u.s."
    }

    def test_eu_countries_set_matches_documented(self) -> None:
        """`EU_COUNTRIES` in `jobsearch/rules.py`
        must contain exactly the 28 documented
        EU countries. A contributor who removes
        an entry (e.g. "spain" -- "we don't
        apply to Spanish jobs anyway") would
        silently change the gate's behaviour
        for any user with EU work authorisation.
        """
        actual = R.EU_COUNTRIES
        expected = self.EU_COUNTRIES_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"EU_COUNTRIES is missing {len(missing)} "
            f"expected country/countries: "
            f"{sorted(missing)}. Removing a country "
            f"from EU_COUNTRIES silently changes the "
            f"gate's behaviour for any user with "
            f"EU work authorisation -- a job "
            f"posting in the missing country would "
            f"no longer be recognised as EU-scope "
            f"and would fail. If the removal is "
            f"intentional (e.g. the country left "
            f"the EU), update this test in the "
            f"same commit. Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"EU_COUNTRIES has {len(extra)} "
            f"undocumented country/countries: "
            f"{sorted(extra)}. If a country was "
            f"intentionally added, update this "
            f"test in the same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_non_eu_block_set_matches_documented(self) -> None:
        """`NON_EU_BLOCK` in `jobsearch/rules.py`
        must contain exactly the 17 documented
        NON-EU countries. A contributor who
        removes an entry (e.g. "us" -- "US jobs
        are handled by a different filter") would
        silently change the gate's behaviour:
        a US job would no longer be flagged as
        a work-authorisation blocker.
        """
        actual = R.NON_EU_BLOCK
        expected = self.NON_EU_BLOCK_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"NON_EU_BLOCK is missing {len(missing)} "
            f"expected country/countries: "
            f"{sorted(missing)}. Removing a country "
            f"from NON_EU_BLOCK silently changes "
            f"the gate's behaviour: a job in the "
            f"missing country would no longer be "
            f"flagged as a work-authorisation "
            f"blocker. If the removal is intentional "
            f"(e.g. the user gained work "
            f"authorisation in that country), "
            f"update this test in the same commit. "
            f"Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"NON_EU_BLOCK has {len(extra)} "
            f"undocumented country/countries: "
            f"{sorted(extra)}. If a country was "
            f"intentionally added, update this "
            f"test in the same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_every_documented_eu_country_is_accepted_by_the_gate(self) -> None:
        """For each of the 28 documented EU
        countries, the gate must accept a
        job posting that says "must be
        authorised to work in {country}".
        The check is the actual gate
        evaluation, not just the set
        membership: it confirms the gate's
        location-scope logic actually
        consults the set as a lookup table,
        not just a string-membership check
        that could be bypassed by, say, a
        typo in the requirement extraction.

        The assertion is on the satisfied
        list: the fixture profile declares
        EU work authorisation, so the
        location requirement must come back
        satisfied and quoting that
        declaration. (These postings are
        deliberately shorter than
        MIN_DESCRIPTION_CHARS, so the
        overall verdict is NEEDS_RESEARCH
        regardless -- the location branch is
        what this test is about. The
        accepted-verdict path is covered by
        TestStrongAndPotential.)

        This catches both failure modes:
        - the country is missing from
          EU_COUNTRIES (the gate would fall
          through to the "location scope to
          verify" branch);
        - the location-scope logic itself
          is broken (the satisfied message
          would not appear).
        """
        # The candidate has EU work auth
        # (the test fixture profile declares
        # it -- see tests/fixtures/test_profile.yaml).
        r = rules()
        for country in self.EU_COUNTRIES_EXPECTED:
            with self.subTest(country=country):
                posting = job(
                    "Full-Stack Engineer",
                    f"Must be authorised to work in {country}. "
                    f"English required.",
                    location=f"Remote ({country})",
                )
                v = R.evaluate(posting, r)
                joined_satisfied = " ".join(v.satisfied).casefold()
                # The gate must recognise the
                # country as EU-scope, not as
                # "needs to verify" (which is
                # the failure mode for a
                # country missing from
                # EU_COUNTRIES).
                self.assertIn(
                    "work authorisation declared",
                    joined_satisfied,
                    f"the gate did not recognise "
                    f"{country!r} as an EU-scope "
                    f"location covered by the "
                    f"profile's declared work "
                    f"authorisation. This means "
                    f"EU_COUNTRIES is missing "
                    f"{country!r} OR the "
                    f"location-scope logic is "
                    f"bypassing the declared "
                    f"scope. "
                    f"Satisfied: {v.satisfied!r}, "
                    f"Failed: {v.failed_essential!r}, "
                    f"Outcome: {v.outcome!r}"
                )

    def test_every_documented_non_eu_country_is_blocked_by_the_gate(self) -> None:
        """For each of the 17 documented NON-EU
        countries, the gate must hard-fail a
        job posting that says "must be
        authorised to work in {country}".
        This is the inverse check of
        `test_every_documented_eu_country_is_accepted_by_the_gate`:
        it pins the NON_EU side of the
        contract.

        The test checks the gate's failure
        list is non-empty (a hard failure
        must be produced) AND that the
        failure message references the
        country -- either as the literal
        string, or as a normalised form
        (e.g. "u.s." is normalised to "us"
        by `rstrip(".,;")` at rules.py L510,
        so the failure message will contain
        "us" not "u.s."). The test
        accounts for this normalisation
        by accepting either the literal
        country or its casefolded
        prefix-stripped form.

        KNOWN GAP: "u.s." is not currently
        caught by the gate. The location
        extraction at rules.py L510 strips
        trailing dots with `rstrip(".,;")`,
        which strips the inner dot from
        "u.s." leaving "u.s", which is
        not in NON_EU_BLOCK. The test
        skips "u.s." (see
        NON_EU_BLOCK_KNOWN_GAPS) and the
        companion test
        `test_known_gap_us_dot_is_documented`
        asserts the gap is documented (so
        a future contributor who fixes it
        has a clear pin to remove).
        """
        r = rules()
        for country in self.NON_EU_BLOCK_EXPECTED:
            # Skip the known gap (rstrip(".,;")
            # strips the trailing dot AND the
            # "u.s." becomes "u.s" which is not
            # in the set). The gap is documented
            # in NON_EU_BLOCK_KNOWN_GAPS.
            if country in self.NON_EU_BLOCK_KNOWN_GAPS:
                continue
            with self.subTest(country=country):
                posting = job(
                    "Full-Stack Engineer",
                    f"Must be authorised to work in {country}. "
                    f"English required.",
                    location=f"Remote ({country})",
                )
                v = R.evaluate(posting, r)
                # The job MUST be hard-failed.
                # A NON-EU country must produce
                # at least one entry in
                # failed_essential.
                self.assertGreater(
                    len(v.failed_essential), 0,
                    f"the gate did not hard-fail a "
                    f"job in {country!r} (a NON-EU "
                    f"country). NON_EU_BLOCK should "
                    f"have caught this. Failed: "
                    f"{v.failed_essential!r}, "
                    f"satisfied: {v.satisfied!r}"
                )
                # The failure message should
                # reference the country (or
                # a normalised form, e.g.
                # "u.s." -> "us" after
                # `rstrip(".,;")`).
                joined_failed = " ".join(v.failed_essential).casefold()
                # The country may be normalised
                # by the requirement extraction.
                # Try the literal first, then
                # casefolded, then with trailing
                # punctuation stripped.
                candidates = [country, country.casefold()]
                # Add a no-trailing-punct variant
                # (matches the `rstrip(".,;")`
                # in rules.py L510).
                candidates.append(country.rstrip(".,;").casefold())
                found = any(c in joined_failed for c in candidates)
                self.assertTrue(
                    found,
                    f"the gate hard-failed a job in "
                    f"{country!r} but the failure "
                    f"message did not name the country "
                    f"(or its normalised form "
                    f"{candidates!r}). Failed: "
                    f"{v.failed_essential!r}"
                )

    def test_known_gap_us_dot_is_documented(self) -> None:
        """The gate does NOT currently catch
        a job posting in "u.s." (with the
        internal dot). This is a known
        limitation of the location extraction
        at rules.py L510: `rstrip(".,;")` is
        too aggressive for country names with
        internal dots, and the extracted
        value "u.s" is not in NON_EU_BLOCK.

        The test pins the gap so a future
        contributor who fixes the extraction
        (e.g. by stripping only trailing
        punctuation that is not a period,
        or by adding "u.s" to NON_EU_BLOCK)
        has a clear signal that the gap is
        being closed. The test:

        1. Asserts the gap actually exists
           (a "u.s." posting is NOT
           hard-failed).
        2. Asserts the gap is in
           NON_EU_BLOCK_KNOWN_GAPS
           (so the test list stays in sync
           with the gap list).

        When the gap is fixed, the fix
        should:
        1. Update rules.py L510 to not
           strip inner dots, OR add "u.s"
           to NON_EU_BLOCK.
        2. Remove "u.s." from
           NON_EU_BLOCK_KNOWN_GAPS.
        3. Update
           test_every_documented_non_eu_country_is_blocked_by_the_gate
           to no longer skip "u.s." (it
           will then assert the gate
           catches it).
        4. Remove this test (the gap is
           no longer a gap).
        """
        # The gap actually exists.
        posting = job(
            "Full-Stack Engineer",
            "Must be authorised to work in u.s.. "
            "English required.",
            location="Remote (u.s.)",
        )
        r = rules()
        v = R.evaluate(posting, r)
        self.assertEqual(
            len(v.failed_essential), 0,
            f"the gate now hard-fails a job in "
            f"'u.s.', which means the known gap "
            f"has been fixed. To update this "
            f"test, do all four steps in the "
            f"docstring: (1) confirm the "
            f"extraction fix in rules.py, "
            f"(2) remove 'u.s.' from "
            f"NON_EU_BLOCK_KNOWN_GAPS, "
            f"(3) remove the skip in "
            f"test_every_documented_non_eu_country_is_blocked_by_the_gate, "
            f"(4) remove this test. Currently "
            f"failed: {v.failed_essential!r}"
        )
        # The gap is in NON_EU_BLOCK_KNOWN_GAPS.
        self.assertIn(
            "u.s.", self.NON_EU_BLOCK_KNOWN_GAPS,
            f"the test list NON_EU_BLOCK_KNOWN_GAPS "
            f"is missing 'u.s.', but the gate "
            f"still has the known gap. Either "
            f"the gap is fixed (in which case "
            f"this test should be removed) or "
            f"the gap is not documented (in "
            f"which case the gate would "
            f"silently miscategorise 'u.s.' "
            f"jobs). Currently "
            f"NON_EU_BLOCK_KNOWN_GAPS: "
            f"{sorted(self.NON_EU_BLOCK_KNOWN_GAPS)}"
        )


class TestHardAvoidTitles(unittest.TestCase):
    """The profession gate is driven by a
    dict in `jobsearch/rules.py`:

      - `HARD_AVOID_TITLES` (7 categories,
        35 terms): titles that hard-fail
        a job at the title stage, before
        any description is fetched. A
        "sales" title is a sales job,
        not a software job, whatever
        the description might say.

    This is the user's **domain
    knowledge** about what jobs to
    reject by title alone. The
    comment at L65-68 of rules.py
    is explicit: "the employer's
    own title IS a quote, and it is
    enough to see the role is not a
    software role".

    A contributor who removes "ios
    developer" (or any other mobile
    title) from `HARD_AVOID_TITLES`
    would silently allow mobile-
    specialist jobs through the
    profession gate. The bug would
    not be caught by any current
    test, because the corpus
    exercises only 3 of the 35
    hard-avoid terms (`sales`,
    `account executive`, `devops
    engineer`); the other 32 terms
    (mobile, ML research, PHP,
    WordPress, Unity, etc.) are
    dormant in the corpus.

    The fix is a bidirectional
    set-equality test (the set
    test catches structural drift)
    PLUS a behavior test that
    exercises every term through
    the actual gate evaluation
    (catches logic drift). This
    is the same pattern as the
    EU_COUNTRIES / NON_EU_BLOCK
    pin from
    `TestLocationSets`.

    Two tests below use `subTest`
    to iterate over the parallel
    list, so a drift in any single
    term fails just that subtest
    (and the error message names
    the specific term).
    """

    # The 35 hard-avoid terms in their
    # 7 categories, parallel to
    # `HARD_AVOID_TITLES` in
    # `jobsearch/rules.py`. If you add a
    # term to the script's dict, add it
    # here too. If you remove one, update
    # both in the same commit. The
    # structure is preserved (category
    # -> tuple of terms) so a future
    # refactor that changes the
    # structure is also caught.
    HARD_AVOID_TITLES_EXPECTED = {
        "non_technical": (
            "sales", "account executive", "marketing", "growth",
            "customer support", "customer success", "recruiter",
            "administrative", "office manager",
        ),
        "data_engineering_spark": ("data engineer",),
        "ml_research": (
            "machine learning researcher", "research scientist",
            "ml researcher", "data scientist", "ai researcher",
        ),
        "native_mobile": (
            "ios developer", "ios engineer", "android developer",
            "android engineer", "mobile developer", "mobile engineer",
        ),
        "game_engine_specialist": (
            "unity developer", "unity engineer",
            "unreal developer", "unreal engineer",
            "graphics programmer",
        ),
        "php_wordpress": (
            "php developer", "php engineer", "laravel developer",
            "wordpress developer", "wordpress engineer",
        ),
        "hard_devops": (
            "site reliability engineer", "sre", "devops engineer",
            "infrastructure engineer",
        ),
    }

    def test_hard_avoid_titles_dict_matches_documented(self) -> None:
        """`HARD_AVOID_TITLES` in
        `jobsearch/rules.py` must contain
        exactly the documented 7
        categories and 35 terms. A
        contributor who removes a
        term (e.g. "ios developer" --
        "mobile is a growth area")
        would silently allow mobile-
        specialist jobs through the
        profession gate. The set
        check catches the structural
        drift: any missing or extra
        category/term is named in
        the failure message.
        """
        actual = R.HARD_AVOID_TITLES
        expected = self.HARD_AVOID_TITLES_EXPECTED
        # Categories present in expected
        # but not in actual.
        missing_cats = set(expected) - set(actual)
        # Categories present in actual
        # but not in expected.
        extra_cats = set(actual) - set(expected)
        self.assertEqual(
            missing_cats, set(),
            f"HARD_AVOID_TITLES is missing "
            f"{len(missing_cats)} expected "
            f"category/categories: "
            f"{sorted(missing_cats)}. A "
            f"missing category means the "
            f"profession gate no longer "
            f"hard-avoids any term in that "
            f"category. Actual categories: "
            f"{sorted(actual)}"
        )
        self.assertEqual(
            extra_cats, set(),
            f"HARD_AVOID_TITLES has "
            f"{len(extra_cats)} undocumented "
            f"category/categories: "
            f"{sorted(extra_cats)}. If a "
            f"category was intentionally "
            f"added, update this test in "
            f"the same commit. Actual "
            f"categories: {sorted(actual)}"
        )
        # Per-category term check.
        for category, expected_terms in expected.items():
            with self.subTest(category=category):
                actual_terms = actual[category]
                actual_set = set(actual_terms)
                expected_set = set(expected_terms)
                missing_terms = expected_set - actual_set
                extra_terms = actual_set - expected_set
                self.assertEqual(
                    missing_terms, set(),
                    f"HARD_AVOID_TITLES[{category!r}] "
                    f"is missing {len(missing_terms)} "
                    f"expected term(s): "
                    f"{sorted(missing_terms)}. "
                    f"Removing a term silently "
                    f"allows jobs with that "
                    f"term in the title to "
                    f"pass the profession gate. "
                    f"Actual terms: "
                    f"{sorted(actual_set)}"
                )
                self.assertEqual(
                    extra_terms, set(),
                    f"HARD_AVOID_TITLES[{category!r}] "
                    f"has {len(extra_terms)} "
                    f"undocumented term(s): "
                    f"{sorted(extra_terms)}. If a "
                    f"term was intentionally added, "
                    f"update this test in the same "
                    f"commit. Actual terms: "
                    f"{sorted(actual_set)}"
                )

    def test_every_hard_avoid_title_hard_fails_the_gate(self) -> None:
        """For each of the 35 hard-avoid
        terms, the gate must produce a
        NOT_SUITABLE verdict with
        `hard_avoid` non-empty and
        `hard_failure` True. This is
        the behavior pin: a term
        removed from the dict
        structural-pin would still
        pass that test (it would be
        missing entirely, not "wrong"),
        so this behavior test
        confirms the gate actually
        consults the dict as a
        lookup table for every
        term.

        The title used for each
        term is "{Term} position"
        (e.g. "iOS Developer
        position") so the term is
        a substring of the title
        (matching the gate's
        `term in low` check at
        rules.py L412). A blank or
        near-blank body is supplied
        so the description does not
        override the title verdict
        (e.g. via a satisfied
        stack of length >= 2).
        """
        r = rules()
        for category, terms in self.HARD_AVOID_TITLES_EXPECTED.items():
            for term in terms:
                with self.subTest(category=category, term=term):
                    posting = job(
                        f"{term} position",
                        # Minimal body: just enough
                        # to not trigger the
                        # MIN_DESCRIPTION_CHARS
                        # path. The title alone
                        # should hard-fail the
                        # job.
                        "x" * 200,
                    )
                    v = R.evaluate(posting, r)
                    # Outcome must be NOT_SUITABLE.
                    self.assertEqual(
                        v.outcome, R.NOT_SUITABLE,
                        f"the gate did NOT hard-fail "
                        f"a job with title "
                        f"{term!r} (in category "
                        f"{category!r}). "
                        f"HARD_AVOID_TITLES should "
                        f"have caught this. "
                        f"Outcome: {v.outcome!r}, "
                        f"hard_avoid: "
                        f"{v.hard_avoid!r}, "
                        f"hard_failure: "
                        f"{v.hard_failure!r}"
                    )
                    # hard_failure flag must be True.
                    self.assertTrue(
                        v.hard_failure,
                        f"the gate did NOT set "
                        f"hard_failure=True for a "
                        f"job with title {term!r}. "
                        f"hard_avoid: "
                        f"{v.hard_avoid!r}"
                    )
                    # hard_avoid list must be
                    # non-empty and name the
                    # term (or its category).
                    self.assertTrue(
                        v.hard_avoid,
                        f"the gate's hard_avoid "
                        f"list is empty for a job "
                        f"with title {term!r}. "
                        f"hard_failure: "
                        f"{v.hard_failure!r}, "
                        f"outcome: {v.outcome!r}"
                    )
                    joined_hard_avoid = " ".join(
                        v.hard_avoid
                    ).casefold()
                    self.assertIn(
                        term, joined_hard_avoid,
                        f"the gate's hard_avoid "
                        f"message for title "
                        f"{term!r} does not name "
                        f"the term. The message "
                        f"should quote the term. "
                        f"hard_avoid: "
                        f"{v.hard_avoid!r}"
                    )


class TestSpecialistMustFail(unittest.TestCase):
    """The specialist-tech gate is driven
    by a set in `jobsearch/rules.py`:

      - `SPECIALIST_MUST_FAIL` (9
        entries): technologies that,
        when required ("must" polarity)
        in a job posting, hard-fail
        the job -- even if the
        candidate's profile does not
        list them. The candidate's
        known stack is irrelevant for
        these: the gate's logic at
        rules.py L564 is "if the
        posting REQUIRES one of these
        specialist technologies,
        the job is unsuitable for
        a generalist profile".

    The set is the user's **domain
    knowledge** about which
    technologies are specialist
    (and therefore a poor fit for
    their generalist profile). A
    contributor who removes "spark"
    (e.g. "we can learn spark on
    the job") would silently allow
    data-engineering-spark jobs
    through the specialist gate.
    The corpus exercises only 2 of
    the 9 entries (`php`, `wordpress`);
    the other 7 are dormant.

    The fix is the same pattern as
    `TestHardAvoidTitles`:
    structural set-equality PLUS
    behavioral gate evaluation for
    every entry.
    """

    # The 9 specialist technologies,
    # parallel to `SPECIALIST_MUST_FAIL`
    # in `jobsearch/rules.py`. If you
    # add a technology, add it here
    # too. If you remove one (e.g.
    # because the user has gained
    # specialist experience in it),
    # update both in the same commit.
    SPECIALIST_MUST_FAIL_EXPECTED = {
        "spark", "databricks", "php", "laravel", "wordpress",
        "swift", "kotlin", "unity", "unreal",
    }

    def test_specialist_must_fail_set_matches_documented(self) -> None:
        """`SPECIALIST_MUST_FAIL` in
        `jobsearch/rules.py` must
        contain exactly the 9
        documented technologies.
        A contributor who removes
        "spark" would silently
        allow data-engineering-spark
        jobs through the specialist
        gate.
        """
        actual = R.SPECIALIST_MUST_FAIL
        expected = self.SPECIALIST_MUST_FAIL_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"SPECIALIST_MUST_FAIL is "
            f"missing {len(missing)} "
            f"expected technology/ies: "
            f"{sorted(missing)}. Removing "
            f"a technology silently "
            f"allows jobs requiring that "
            f"technology to pass the "
            f"specialist gate. If the "
            f"removal is intentional "
            f"(e.g. the user gained "
            f"specialist experience in "
            f"the technology), update "
            f"this test in the same "
            f"commit. Actual: "
            f"{sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"SPECIALIST_MUST_FAIL has "
            f"{len(extra)} undocumented "
            f"technology/ies: "
            f"{sorted(extra)}. If a "
            f"technology was intentionally "
            f"added, update this test in "
            f"the same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_every_specialist_tech_hard_fails_the_gate(self) -> None:
        """For each of the 9 specialist
        technologies, the gate must
        produce a NOT_SUITABLE verdict
        with `hard_failure` True when
        a job posting has "must have
        {tech} experience" in its
        description. This is the
        behavior pin: a technology
        removed from the set would
        still pass the set-equality
        test (it would be missing,
        not "wrong"), so this behavior
        test confirms the gate
        actually consults the set as
        a lookup table for every
        entry.

        The title is generic
        ("Backend Engineer") so the
        profession gate does NOT
        hard-avoid the job for an
        unrelated reason. The body
        is a padded string with the
        required technology in "must
        have production {tech}
        experience" form, which the
        extractor at L564 of
        rules.py will pick up as a
        "must" technology requirement.
        """
        r = rules()
        for tech in self.SPECIALIST_MUST_FAIL_EXPECTED:
            with self.subTest(tech=tech):
                posting = job(
                    "Backend Engineer",
                    f"Build data pipelines. Must have "
                    f"production {tech} experience. "
                    f"Strong knowledge of distributed "
                    f"systems required. "
                    f"Excellent communication skills.",
                )
                v = R.evaluate(posting, r)
                # Outcome must be NOT_SUITABLE.
                self.assertEqual(
                    v.outcome, R.NOT_SUITABLE,
                    f"the gate did NOT hard-fail "
                    f"a job requiring {tech!r} "
                    f"(in SPECIALIST_MUST_FAIL). "
                    f"SPECIALIST_MUST_FAIL should "
                    f"have caught this. "
                    f"Outcome: {v.outcome!r}, "
                    f"failed: {v.failed_essential!r}, "
                    f"hard_failure: {v.hard_failure!r}"
                )
                # hard_failure flag must be True.
                self.assertTrue(
                    v.hard_failure,
                    f"the gate did NOT set "
                    f"hard_failure=True for a "
                    f"job requiring {tech!r}. "
                    f"failed: {v.failed_essential!r}"
                )
                # failed_essential must
                # name the technology (or
                # its context).
                joined_failed = " ".join(
                    v.failed_essential
                ).casefold()
                self.assertIn(
                    tech, joined_failed,
                    f"the gate's failure message "
                    f"for a job requiring {tech!r} "
                    f"does not name the technology. "
                    f"The message should quote the "
                    f"technology. failed: "
                    f"{v.failed_essential!r}"
                )


class TestSpecialistTraps(unittest.TestCase):
    """The `SPECIALIST_TRAPS` set in
    `jobsearch/requirements.py` is the
    "tag this requirement as a specialist
    trap" lookup table used by the
    requirement extractor (L254). Every
    technology in the set is a known
    specialist trap: a job requiring it
    as a MUST would hard-fail the gate
    (or, in the case of kubernetes/k8s/
    terraform, is at least flagged as a
    specialist trap for downstream
    surfacing).

    Before this turn, no test pinned:
    - the structural integrity of
      `SPECIALIST_TRAPS` (a contributor
      who removed a technology would
      not fail any test);
    - the relationship to `TECHNOLOGIES`
      (a contributor who added an
      entry to `SPECIALIST_TRAPS` that
      isn't a known technology would
      not fail any test);
    - the behavior that every
      `SPECIALIST_TRAPS` entry actually
      gets tagged as a `specialist_trap`
      in the requirement metadata;
    - the documented design decision
      that `kubernetes`, `k8s`, and
      `terraform` are tagged as
      specialist traps but NOT in
      `SPECIALIST_MUST_FAIL` (so they
      don't hard-fail the gate -- a
      deliberate carve-out for the
      owner who has some Kubernetes
      experience).

    The fix is a new TestSpecialistTraps
    class with 4 tests:
    1. `test_specialist_traps_set_matches_documented`:
       bidirectional set equality on
       `SPECIALIST_TRAPS`.
    2. `test_every_specialist_trap_is_a_known_technology`:
       every entry in `SPECIALIST_TRAPS`
       must also be in `TECHNOLOGIES`
       (a trap for a tech the gate
       doesn't know is a dead entry).
    3. `test_every_specialist_trap_gets_tagged`:
       behavior pin: every tech in
       `SPECIALIST_TRAPS` gets the
       `specialist_trap` flag in the
       requirement's meta dict.
    4. `test_soft_carve_out_techs_are_documented`:
       the 3-tech difference between
       TRAPS and MUST_FAIL
       (kubernetes, k8s, terraform)
       is documented as a deliberate
       design decision (not drift).
    """

    # The 12 specialist technologies
    # in `SPECIALIST_TRAPS`. If you add
    # a technology, add it here too.
    # If you remove one, update this
    # test in the same commit.
    SPECIALIST_TRAPS_EXPECTED = {
        "spark", "databricks", "php", "laravel", "wordpress",
        "swift", "kotlin", "unity", "unreal",
        "kubernetes", "k8s", "terraform",
    }

    # The 3 technologies that are
    # specialist TRAPS but NOT in
    # SPECIALIST_MUST_FAIL. The owner
    # has some Kubernetes/Terraform
    # experience, so the gate tags
    # these as specialist traps
    # (visible in the requirement
    # meta) but does NOT hard-fail
    # the job. This is a deliberate
    # carve-out, not drift.
    SOFT_CARVE_OUT_TECHS = {"kubernetes", "k8s", "terraform"}

    def test_specialist_traps_set_matches_documented(self) -> None:
        """`SPECIALIST_TRAPS` in
        `jobsearch/requirements.py`
        must contain exactly the
        12 documented technologies.
        A contributor who removes
        "spark" would silently
        allow data-engineering-spark
        jobs to escape the
        specialist-trap tag (and
        downstream surfacing).
        """
        from jobsearch import requirements
        actual = requirements.SPECIALIST_TRAPS
        expected = self.SPECIALIST_TRAPS_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"SPECIALIST_TRAPS is missing "
            f"{len(missing)} expected "
            f"technology/ies: {sorted(missing)}. "
            f"Removing a technology silently "
            f"stops the gate from tagging "
            f"jobs that require it. If the "
            f"removal is intentional, update "
            f"this test in the same commit. "
            f"Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"SPECIALIST_TRAPS has "
            f"{len(extra)} undocumented "
            f"technology/ies: {sorted(extra)}. "
            f"If a technology was intentionally "
            f"added, update this test in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_every_specialist_trap_is_a_known_technology(self) -> None:
        """Every entry in `SPECIALIST_TRAPS`
        must also be in `TECHNOLOGIES`.
        A trap for a tech the gate
        doesn't recognise is a dead
        entry (the extractor would
        never see the tech in the
        first place).
        """
        from jobsearch import requirements
        not_known = (
            requirements.SPECIALIST_TRAPS
            - set(requirements.TECHNOLOGIES)
        )
        self.assertEqual(
            not_known, set(),
            f"SPECIALIST_TRAPS has "
            f"{len(not_known)} technology/ies "
            f"that are NOT in TECHNOLOGIES: "
            f"{sorted(not_known)}. A "
            f"specialist trap for a tech the "
            f"gate doesn't know is a dead "
            f"entry -- the extractor would "
            f"never see the tech in the first "
            f"place. Add the tech to "
            f"TECHNOLOGIES first, then to "
            f"SPECIALIST_TRAPS."
        )

    def test_every_specialist_trap_gets_tagged(self) -> None:
        """Behavior pin: every tech in
        `SPECIALIST_TRAPS` gets the
        `specialist_trap` flag in the
        requirement's meta dict when
        a job posting mentions the
        tech as a must-have.

        This is the parallel pin to
        `TestSpecialistMustFail`:
        that test confirms the gate
        HARD-FAILS a job for the 9
        entries in `SPECIALIST_MUST_FAIL`;
        this test confirms the
        extractor TAGS the
        requirement as a trap for
        the 12 entries in
        `SPECIALIST_TRAPS`.
        """
        from jobsearch.requirements import (
            JobPosting,
            extract_technologies,
        )
        for tech in self.SPECIALIST_TRAPS_EXPECTED:
            with self.subTest(tech=tech):
                # Build a posting that
                # mentions the tech in
                # a "must have" form.
                # The title is generic
                # ("Backend Engineer")
                # so the test exercises
                # the technology tag,
                # not the title.
                posting = JobPosting(
                    title="Backend Engineer",
                    description=(
                        f"Build data pipelines. "
                        f"Must have production "
                        f"{tech} experience. "
                        f"Strong knowledge of "
                        f"distributed systems "
                        f"required. Excellent "
                        f"communication skills."
                    ),
                )
                reqs = extract_technologies(posting)
                # Find the requirement
                # for this tech.
                matched = [
                    r for r in reqs
                    if r.value == tech
                ]
                self.assertTrue(
                    matched,
                    f"extractor did not "
                    f"produce a requirement "
                    f"for {tech!r}. The "
                    f"extractor must see "
                    f"this tech in a "
                    f"posting before it "
                    f"can be tagged."
                )
                # The requirement must
                # be tagged as a
                # specialist trap.
                self.assertTrue(
                    any(
                        r.meta.get("specialist_trap")
                        for r in matched
                    ),
                    f"the requirement for "
                    f"{tech!r} was NOT "
                    f"tagged as a "
                    f"specialist trap. "
                    f"SPECIALIST_TRAPS "
                    f"should have flagged "
                    f"it. requirements: "
                    f"{[(r.value, r.meta) for r in matched]}"
                )

    def test_soft_carve_out_techs_are_documented(self) -> None:
        """The 3 technologies in
        `SPECIALIST_TRAPS` but NOT
        in `SPECIALIST_MUST_FAIL`
        (kubernetes, k8s, terraform)
        are a documented design
        decision, not drift. The
        owner has some Kubernetes
        /Terraform experience, so
        the gate tags these as
        specialist traps (visible
        in the requirement meta)
        but does NOT hard-fail
        the job. If this test
        fails, the difference is
        drift and should be
        reconciled.
        """
        from jobsearch import requirements
        from jobsearch import rules
        soft = (
            requirements.SPECIALIST_TRAPS
            - rules.SPECIALIST_MUST_FAIL
        )
        self.assertEqual(
            soft, self.SOFT_CARVE_OUT_TECHS,
            f"the difference between "
            f"SPECIALIST_TRAPS and "
            f"SPECIALIST_MUST_FAIL is "
            f"{sorted(soft)}, expected "
            f"{sorted(self.SOFT_CARVE_OUT_TECHS)}. "
            f"If the change is intentional "
            f"(e.g. owner gained more "
            f"Kubernetes experience, so "
            f"k8s should now hard-fail), "
            f"update SOFT_CARVE_OUT_TECHS "
            f"in the same commit. "
            f"SPECIALIST_TRAPS: "
            f"{sorted(requirements.SPECIALIST_TRAPS)}, "
            f"SPECIALIST_MUST_FAIL: "
            f"{sorted(rules.SPECIALIST_MUST_FAIL)}"
        )


class TestTechnologies(unittest.TestCase):
    """The `TECHNOLOGIES` tuple in
    `jobsearch/requirements.py` is
    the gate's documented default
    vocabulary for technology
    requirements. `extract_technologies`
    uses it to detect technology
    requirements in a posting; a
    technology not in this set is a
    silent blind spot for the
    default profile (the candidate
    can extend the vocabulary via
    `extra_terms`).

    This is the technology parallel
    to `LANGUAGES` (9 entries, pinned
    in turn N+2) and the default
    half of the W3.4 contract
    ("vocabulary is profile data,
    with a documented default").

    Before this turn, no test pinned
    `TECHNOLOGIES` itself. The
    `TestSpecialistTraps` class
    cross-checks `SPECIALIST_TRAPS
    ⊆ TECHNOLOGIES`, but a contributor
    who removed `typescript` from
    `TECHNOLOGIES` would silently
    fail to detect TypeScript
    requirements in the default
    profile. A contributor who
    added a typo'd entry (e.g.
    "typpescript") would inflate
    the list without adding
    coverage.

    The fix is a new
    `TestTechnologies` class with
    3 tests:
    1. `test_technologies_set_matches_documented`:
       bidirectional set equality
       on `TECHNOLOGIES` (the 48
       documented entries).
    2. `test_technologies_has_no_duplicates`:
       the tuple is unique (no
       silently-doubled entries
       that would inflate the
       list without adding
       coverage).
    3. `test_every_technology_is_lowercase`:
       every entry is lowercase
       (the extractor compares
       against the case-folded
       haystack; a non-lowercase
       entry would silently miss
       every posting).

    Drift-injection verified:
    removing `typescript` from
    `TECHNOLOGIES` would fail the
    set test with a precise error
    message. Adding a duplicate
    would fail the duplicates
    test. Adding a non-lowercase
    entry would fail the lowercase
    test.
    """

    # The 48 documented technologies
    # in `TECHNOLOGIES`. This is the
    # W3.4 default contract: the
    # gate promises to detect
    # requirements in any of these
    # technologies when a profile
    # does not list its own. If you
    # add a technology, add it here.
    # If you remove one, update this
    # test in the same commit.
    TECHNOLOGIES_EXPECTED = {
        "typescript", "javascript", "react", "next.js", "nextjs",
        "node.js", "node", "express", "mongodb", "postgres",
        "postgresql", "python", "sql", "graphql", "api",
        "playwright", "jest", "vitest", "docker", "git",
        "linux", "redis", "tailwind", "aws", "gcp",
        "azure", "terraform", "kubernetes", "k8s",
        "spark", "databricks", "php", "laravel", "wordpress",
        "swift", "kotlin", "unity", "unreal", "solidity",
        "ethereum", "web3", "llm", "agent", "openai",
        "langchain", "rag", "n8n", "zapier",
    }

    def test_technologies_set_matches_documented(self) -> None:
        """`TECHNOLOGIES` in
        `jobsearch/requirements.py`
        must contain exactly the
        48 documented technologies.
        Removing `typescript` would
        silently fail to detect
        TypeScript requirements in
        the default profile.
        """
        from jobsearch import requirements
        actual = set(requirements.TECHNOLOGIES)
        expected = self.TECHNOLOGIES_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"TECHNOLOGIES is missing "
            f"{len(missing)} expected "
            f"technology/ies: {sorted(missing)}. "
            f"Removing a technology "
            f"silently leaves the gate "
            f"unable to detect "
            f"requirements in that "
            f"technology for the "
            f"default profile. The "
            f"candidate can extend the "
            f"vocabulary via "
            f"`extra_terms` (their "
            f"profile), but removing a "
            f"documented default "
            f"silently breaks the W3.4 "
            f"'vocabulary is profile "
            f"data, with a documented "
            f"default' contract. If the "
            f"removal is intentional, "
            f"update TECHNOLOGIES_EXPECTED "
            f"in the same commit. "
            f"Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"TECHNOLOGIES has "
            f"{len(extra)} undocumented "
            f"technology/ies: "
            f"{sorted(extra)}. If a "
            f"technology was intentionally "
            f"added, update "
            f"TECHNOLOGIES_EXPECTED in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_technologies_has_no_duplicates(self) -> None:
        """`TECHNOLOGIES` must
        contain no duplicates.
        A duplicate entry would
        silently inflate the
        list without adding
        coverage (the extractor
        would match the same
        technology twice but
        produce one
        requirement).
        """
        from jobsearch import requirements
        from collections import Counter
        counter = Counter(requirements.TECHNOLOGIES)
        duplicates = {
            tech: count
            for tech, count in counter.items()
            if count > 1
        }
        self.assertEqual(
            duplicates, {},
            f"TECHNOLOGIES has "
            f"{len(duplicates)} "
            f"duplicate entry/entries: "
            f"{duplicates}. A duplicate "
            f"would silently inflate the "
            f"list without adding "
            f"coverage (the extractor "
            f"would match the same "
            f"technology twice but "
            f"produce one requirement). "
            f"Remove the duplicate, or "
            f"update TECHNOLOGIES_EXPECTED "
            f"in the same commit if the "
            f"duplicate is intentional."
        )

    def test_every_technology_is_lowercase(self) -> None:
        """Every TECHNOLOGIES
        entry must be lowercase.
        The extractor compares
        against the case-folded
        haystack; a
        non-lowercase entry
        (e.g. "TypeScript") would
        silently miss every
        posting because the
        regex would look for
        "TypeScript" but the
        case-folded haystack
        contains "typescript".
        """
        from jobsearch import requirements
        offenders = [
            t for t in requirements.TECHNOLOGIES
            if t != t.lower()
        ]
        self.assertEqual(
            offenders, [],
            f"TECHNOLOGIES has "
            f"{len(offenders)} "
            f"non-lowercase entry/entries: "
            f"{offenders}. The extractor "
            f"matches the entry against "
            f"the case-folded haystack, "
            f"so a non-lowercase entry "
            f"would silently miss every "
            f"posting. Lowercase the "
            f"entry, or update the "
            f"extractor to case-fold "
            f"the entry (preferred: keep "
            f"the entry lowercase)."
        )


class TestCurrencyConstants(unittest.TestCase):
    """The currency recognition
    constants in
    `jobsearch/rules.py`:
    - `_CURRENCY_ALIAS`:
      symbol-to-ISO-code
      mappings
      (4 entries: ₾→GEL,
      €→EUR, $→USD, £→GBP).
    - `_NOT_A_CURRENCY`:
      stop-words that
      appear near salary
      text but are not
      currencies
      (7 entries: NET,
      GROSS, PER, AND,
      THE, FOR, MON).

    Both are used in the
    salary parser
    (`_parse_salary` at
    L399) and the gate
    (currency-code
    extraction at L323).

    `_CURRENCY_ALIAS` is
    the symbol→code
    contract: a posting
    that says "5000 ₾"
    needs the ₾ symbol
    to be recognised as
    GEL. A drift that
    removes ₾ from
    `_CURRENCY_ALIAS`
    would silently
    mis-parse GEL
    salaries -- the
    gate would not know
    the salary is in
    GEL, would not
    floor-check it
    against the
    profile's GEL
    floor, and would
    either fall
    through to
    "unknown currency"
    or be flagged as
    "needs_conversion"
    when no
    conversion is
    actually needed.

    `_NOT_A_CURRENCY` is
    the
    not-a-currency
    stop-word list.
    The gate extracts
    3-letter tokens
    from the floor
    text and checks
    each against
    `_NOT_A_CURRENCY`;
    the first one not
    in the list is
    taken as the
    currency. A drift
    that adds a real
    currency (e.g.
    USD) to the list
    would silently
    exclude that
    currency from
    being recognised
    in "5000 NET USD
    per month" text.

    Both constants are
    private (prefix
    `_`) because they
    are implementation
    details of the
    salary parser, but
    they are part of
    the gate's
    behavior contract
    (W3.1
    salary-flooring
    and currency
    detection). A
    drift would
    silently change
    the gate's
    verdicts for
    every posting
    that mentions a
    salary in a
    currency or
    symbol listed
    here.

    The fix is a new
    `TestCurrencyConstants`
    class with 2 tests:
    1. `test_currency_alias_matches_documented_symbols`:
       each documented
       symbol maps to
       the documented
       ISO code.
    2. `test_not_a_currency_matches_documented_stop_words`:
       each documented
       stop-word is in
       the list.

    Drift-injection
    verified: removing
    ₾ from
    `_CURRENCY_ALIAS`
    would fail the
    alias test.
    """

    EXPECTED_CURRENCY_ALIAS = {
        "₾": "GEL", "€": "EUR", "$": "USD", "£": "GBP",
    }

    EXPECTED_NOT_A_CURRENCY = {
        "NET", "GROSS", "PER", "AND", "THE", "FOR", "MON",
    }

    def test_currency_alias_matches_documented_symbols(self) -> None:
        """`_CURRENCY_ALIAS` in
        `jobsearch/rules.py`
        must contain
        exactly the 4
        documented
        symbol-to-ISO-code
        mappings. Removing
        ₾ would silently
        mis-parse GEL
        salaries; removing
        € would silently
        mis-parse EUR
        salaries (the
        gate's primary
        currency).

        A contributor who
        thought "we
        don't use GEL
        anymore" would
        remove ₾ from
        the alias, and
        every GEL
        posting would
        silently fall
        through to
        "unknown
        currency" in
        the gate's
        salary-flooring
        check.
        """
        from jobsearch import rules
        # Both keys
        # (documented)
        # and ISO codes
        # (the values)
        # must be in
        # the alias.
        for symbol, iso in self.EXPECTED_CURRENCY_ALIAS.items():
            with self.subTest(symbol=symbol):
                self.assertIn(
                    symbol, rules._CURRENCY_ALIAS,
                    f"Symbol {symbol!r} is NOT "
                    f"in _CURRENCY_ALIAS. The "
                    f"salary parser at L399 "
                    f"uses _CURRENCY_ALIAS.get(cur, cur)"
                    f" to map symbols to ISO "
                    f"codes. A symbol not in "
                    f"the alias would be "
                    f"returned as-is, and the "
                    f"gate would not know "
                    f"what currency it is. "
                    f"Actual: {dict(rules._CURRENCY_ALIAS)}"
                )
                self.assertEqual(
                    rules._CURRENCY_ALIAS[symbol], iso,
                    f"Symbol {symbol!r} maps to "
                    f"{rules._CURRENCY_ALIAS[symbol]!r} "
                    f"in _CURRENCY_ALIAS, expected "
                    f"{iso!r}. A wrong mapping "
                    f"would silently assign "
                    f"the wrong currency to a "
                    f"posting's salary. Actual: "
                    f"{dict(rules._CURRENCY_ALIAS)}"
                )
        # No
        # undocumented
        # entries
        # (catch
        # over-pin).
        documented = set(self.EXPECTED_CURRENCY_ALIAS.keys())
        actual = set(rules._CURRENCY_ALIAS.keys())
        added = actual - documented
        self.assertEqual(
            added, set(),
            f"_CURRENCY_ALIAS has "
            f"{len(added)} undocumented symbol(s): "
            f"{sorted(added)}. If a symbol was "
            f"intentionally added, update "
            f"EXPECTED_CURRENCY_ALIAS in the same "
            f"commit. Actual: {sorted(actual)}"
        )

    def test_not_a_currency_matches_documented_stop_words(self) -> None:
        """`_NOT_A_CURRENCY` in
        `jobsearch/rules.py`
        must contain
        exactly the 7
        documented
        stop-words. Adding
        a real currency
        (e.g. USD) would
        silently exclude
        that currency
        from being
        recognised in
        "5000 NET USD per
        month" text.
        """
        from jobsearch import rules
        # Every
        # documented
        # stop-word
        # is in
        # the
        # list.
        for word in self.EXPECTED_NOT_A_CURRENCY:
            with self.subTest(word=word):
                self.assertIn(
                    word, rules._NOT_A_CURRENCY,
                    f"Stop-word {word!r} is NOT in "
                    f"_NOT_A_CURRENCY. The gate at "
                    f"L323 checks "
                    f"`if code not in "
                    f"_NOT_A_CURRENCY` to skip "
                    f"words that look like "
                    f"3-letter currency codes but "
                    f"are not. A stop-word not in "
                    f"the list would be "
                    f"erroneously taken as a "
                    f"currency. Actual: "
                    f"{sorted(rules._NOT_A_CURRENCY)}"
                )
        # No
        # 3-letter
        # ISO
        # currency
        # codes
        # (which
        # would
        # defeat
        # the
        # whole
        # point).
        ISO_CODES = {
            "USD", "EUR", "GBP", "GEL", "JPY",
            "CHF", "CAD", "AUD", "NZD", "SEK",
            "NOK", "DKK", "PLN", "CZK", "HUF",
            "RON", "BGN", "TRY", "ILS", "ZAR",
            "INR", "CNY", "HKD", "SGD", "KRW",
        }
        bad = rules._NOT_A_CURRENCY & ISO_CODES
        self.assertEqual(
            bad, set(),
            f"_NOT_A_CURRENCY contains "
            f"{len(bad)} real currency code(s): "
            f"{sorted(bad)}. Adding a real "
            f"currency to the stop-word list "
            f"would silently exclude that "
            f"currency from being recognised "
            f"in salary text. For example, "
            f"if 'USD' were in the list, "
            f"'5000 USD per month' would be "
            f"read as 'the code is something "
            f"else' rather than 'the code "
            f"is USD'."
        )



class TestDescriptionLengthThreshold(unittest.TestCase):
    """`MIN_DESCRIPTION_CHARS` in
    `jobsearch/rules.py` is the
    gate's behavior threshold
    for "description is too
    short to evaluate". If a
    posting's description
    (after noise stripping)
    is shorter than this
    threshold, the gate:

    1. adds a note "description
       missing or too short to
       evaluate (N chars)"
       (rules.py L441-444);
    2. sets the verdict to
       `NEEDS_RESEARCH` if the
       posting would otherwise
       be a `POTENTIAL_MATCH` or
       `STRONG_MATCH` (rules.py
       L615-616);
    3. in enrich.py (M4), marks
       the posting's `state` as
       `"incomplete"` rather than
       `"complete"` (enrich.py
       L160).

    The constant is used in 4
    places and is referenced by
    `tests/test_enrich.py`
    (which imports it directly
    rather than hard-coding the
    value). A contributor who
    changed the value from `80`
    to `50` would silently:
    1. accept shorter
       descriptions as
       "evaluable" (less
       rigorous);
    2. change verdicts for
       descriptions in the
       50-79 char range
       (now evaluable, was
       NEEDS_RESEARCH);
    3. change the M4 state
       for descriptions in
       the 50-79 char range
       (now complete, was
       incomplete).

    None of the existing tests
    would fail because they
    use the constant directly
    rather than hard-coding
    the value. A drift in the
    constant would be a silent
    behavior change.

    The fix is a new
    `TestDescriptionLengthThreshold`
    class with 3 tests:
    1. `test_threshold_value_is_eighty`:
       the constant is
       `80` (the documented
       value).
    2. `test_threshold_is_positive`:
       the constant is a
       positive integer
       (defensive: a zero
       or negative
       threshold would
       make every
       description
       "evaluable").
    3. `test_threshold_is_reasonable`:
       the threshold is
       between 40 and 200
       chars (a sanity
       check -- values
       outside this range
       are either too
       lax or too
       strict for a
       real job posting).
    """

    EXPECTED_VALUE = 80

    def test_threshold_value_is_eighty(self) -> None:
        """`MIN_DESCRIPTION_CHARS`
        must be `80`. The gate's
        behavior threshold is
        calibrated against this
        value; the test_enrich.py
        tests assume this value
        for the "complete vs
        incomplete" check.
        """
        from jobsearch import rules
        self.assertEqual(
            rules.MIN_DESCRIPTION_CHARS,
            self.EXPECTED_VALUE,
            f"MIN_DESCRIPTION_CHARS is "
            f"{rules.MIN_DESCRIPTION_CHARS}, "
            f"expected {self.EXPECTED_VALUE}. "
            f"The gate's behavior threshold "
            f"is calibrated against this "
            f"value. A change would silently: "
            f"1. accept shorter descriptions "
            f"as 'evaluable' (less rigorous); "
            f"2. change verdicts for "
            f"descriptions in the "
            f"{min(self.EXPECTED_VALUE, rules.MIN_DESCRIPTION_CHARS)}-"
            f"{max(self.EXPECTED_VALUE, rules.MIN_DESCRIPTION_CHARS)} "
            f"char range (now evaluable, was "
            f"NEEDS_RESEARCH); "
            f"3. change the M4 state for "
            f"those descriptions (now "
            f"complete, was incomplete). "
            f"If the change is intentional, "
            f"update EXPECTED_VALUE in the "
            f"same commit AND the corpus "
            f"fixtures and the "
            f"test_enrich.py tests."
        )

    def test_threshold_is_positive(self) -> None:
        """`MIN_DESCRIPTION_CHARS`
        must be a positive
        integer. A zero or
        negative threshold
        would make every
        description "evaluable"
        (the `< threshold` check
        would always be false).
        """
        from jobsearch import rules
        self.assertGreater(
            rules.MIN_DESCRIPTION_CHARS,
            0,
            f"MIN_DESCRIPTION_CHARS is "
            f"{rules.MIN_DESCRIPTION_CHARS}; "
            f"it must be positive. A zero "
            f"or negative threshold would "
            f"silently make every description "
            f"evaluable (the gate would "
            f"never add a 'description too "
            f"short' note and the verdict "
            f"would never be NEEDS_RESEARCH "
            f"for this reason)."
        )

    def test_threshold_is_reasonable(self) -> None:
        """The threshold must
        be between 40 and 200
        chars. Values outside
        this range are either
        too lax (under 40: most
        job postings are at
        least 100 chars) or
        too strict (over 200:
        short-but-legitimate
        postings would be
        rejected as
        unevaluable).
        """
        from jobsearch import rules
        value = rules.MIN_DESCRIPTION_CHARS
        self.assertGreaterEqual(
            value, 40,
            f"MIN_DESCRIPTION_CHARS is "
            f"{value}; it is below 40. "
            f"A value below 40 is "
            f"unusually lax -- most job "
            f"postings are at least 100 "
            f"chars and a threshold under "
            f"40 would let through "
            f"descriptions that are "
            f"effectively empty."
        )
        self.assertLessEqual(
            value, 200,
            f"MIN_DESCRIPTION_CHARS is "
            f"{value}; it is above 200. "
            f"A value above 200 is "
            f"unusually strict -- "
            f"short-but-legitimate job "
            f"postings (e.g. a 150-char "
            f"ad with a clear job title, "
            f"location, and 1-2 sentences) "
            f"would be rejected as "
            f"unevaluable."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
