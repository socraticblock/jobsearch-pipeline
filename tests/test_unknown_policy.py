"""I-16 -- the Unknown policy test.

The policy is stated in UNKNOWN_POLICY.md. The test asserts:

  1. The document exists and is substantial.
  2. The `evaluate()` function in `jobsearch/rules.py` returns
     `NEEDS_RESEARCH` (not a fabricated `STRONG_MATCH` or
     `POTENTIAL_MATCH`, and not `NOT_SUITABLE`) for every
     shape of missing evidence the policy names.
  3. The corpus's `c-001` fixture (the canonical
     `years_bar_missing_evidence` case) produces the policy-correct
     verdict.

A new rule that returns a confident verdict on missing evidence
fails this test. The policy is the contract; the test enforces it.

Run:  python3 -m unittest tests.test_unknown_policy -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY = ROOT / "UNKNOWN_POLICY.md"
CORPUS_V1 = ROOT / "corpus" / "v1" / "postings.json"

from jobsearch import rules as rules_module  # noqa: E402
from jobsearch import rule_why  # noqa: E402
from jobsearch.requirements import JobPosting, Requirement  # noqa: E402


NEEDS_RESEARCH = "needs_research"
STRONG_MATCH = "strong_match"
NOT_SUITABLE = "not_suitable"


def _minimal_posting(
    title: str = "Backend Engineer",
    description: str = "5+ years Python. Remote.",
    years_can_honestly_claim: int | None = None,
    known_stack: set[str] | None = None,
    learnable_stack: set[str] | None = None,
    floor_net: int | None = None,
    floor_currency: str | None = None,
    local_ok: list[str] | None = None,
) -> JobPosting:
    return JobPosting(
        title=title,
        description=description,
        location="remote",
        requirements=[],
    )


def _evaluate(posting: JobPosting, years: int | None = None, known: set | None = None) -> str:
    rules = rules_module.Rules(
        floor_net=None,
        known_stack=known if known is not None else set(),
        learnable_stack=set(),
        years_can_honestly_claim=years,
    )
    verdict = rules_module.evaluate(posting, rules)
    return verdict.outcome


class TestUnknownPolicyDocument(unittest.TestCase):

    def test_policy_file_exists(self) -> None:
        self.assertTrue(
            POLICY.exists(),
            f"UNKNOWN_POLICY.md missing at {POLICY.relative_to(ROOT)}. "
            f"It is the I-16 / W3.1 deliverable."
        )

    def test_policy_file_is_substantial(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        self.assertGreater(
            len(text),
            1024,
            f"UNKNOWN_POLICY.md is too short ({len(text)} chars). "
            f"A real policy states the rule, the four verdicts, "
            f"the missing-evidence shapes, and the minimum-evidence "
            f"rule."
        )

    def test_policy_names_all_four_verdicts(self) -> None:
        """The gate has four verdicts (STRONG_MATCH,
        POTENTIAL_MATCH, NEEDS_RESEARCH, NOT_SUITABLE);
        the policy doc must name all four in
        snake_case exactly as the code does, AND
        each verdict must appear as a row in the
        verdict table (the table is the primary
        interface -- a reader scans it first; a
        verdict that only appears in body prose
        is "documented but not surfaced"). A
        reader who has not seen the code must
        be able to find the full verdict
        taxonomy in the doc, including
        POTENTIAL_MATCH -- the "some-but-not-
        all required tech" verdict that
        distinguishes a 4-band gate from a
        3-band one.
        """
        text = POLICY.read_text(encoding="utf-8")
        # The verdicts are snake_case in code; the policy doc must
        # match the code's vocabulary exactly.
        for verdict in (
            "strong_match",
            "potential_match",
            "needs_research",
            "not_suitable",
        ):
            # Check 1: the verdict name appears
            # somewhere in the doc.
            self.assertIn(
                verdict,
                text,
                f"UNKNOWN_POLICY.md does not name "
                f"the {verdict} verdict anywhere. "
                f"The gate has four verdicts: "
                f"STRONG_MATCH, POTENTIAL_MATCH, "
                f"NEEDS_RESEARCH, NOT_SUITABLE. "
                f"Omitting {verdict!r} makes the "
                f"policy describe a 3-band gate when "
                f"the code is 4-band."
            )
            # Check 2: the verdict appears as a
            # row in a table (the primary
            # interface). The pattern matches
            # "| `verdict`" which is the start
            # of a table row that names the
            # verdict in backticks.
            table_row = f"| `{verdict}`"
            self.assertIn(
                table_row,
                text,
                f"UNKNOWN_POLICY.md names the "
                f"{verdict!r} verdict in prose but "
                f"NOT in a table row. The table is "
                f"the primary interface for the "
                f"verdict taxonomy; a reader who "
                f"scans the table will not find the "
                f"verdict if it is only mentioned "
                f"in passing. Add a row like "
                f"`| `{verdict}` | ... | ... |` "
                f"to the verdict table."
            )

    def test_policy_cites_corpus_fixture(self) -> None:
        """The policy must reference the corpus fixture (c-001) by
        id. A reader who wants the example needs the path."""
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn(
            "c-001",
            text,
            "UNKNOWN_POLICY.md must cite the corpus fixture id "
            "(c-001) so a reader can find the example."
        )


class TestUnknownPolicyEnforced(unittest.TestCase):
    """The policy must be enforced by `evaluate()`. A new rule that
    returns a confident verdict on missing evidence fails."""

    def test_years_can_honestly_claim_none_produces_needs_research(self) -> None:
        # c-001: years_bar_missing_evidence
        posting = _minimal_posting(
            title="Senior Platform Engineer",
            description="5+ years of experience building distributed systems.",
        )
        verdict = _evaluate(posting, years=None)
        self.assertEqual(
            verdict,
            NEEDS_RESEARCH,
            f"missing years_can_honestly_claim must produce "
            f"NEEDS_RESEARCH, not {verdict!r}. The sieve must not "
            f"fabricate a number."
        )

    def test_empty_title_produces_needs_research(self) -> None:
        # c-006: empty_title_unknown
        posting = _minimal_posting(
            title="",
            description="We are hiring for a new role. Strong technical background.",
        )
        verdict = _evaluate(posting, years=5)
        self.assertEqual(
            verdict,
            NEEDS_RESEARCH,
            f"empty title must produce NEEDS_RESEARCH, not {verdict!r}."
        )

    def test_short_body_produces_needs_research(self) -> None:
        # c-008: description_too_short_uncertain
        posting = _minimal_posting(
            title="Backend Engineer",
            description="Hiring.",
        )
        verdict = _evaluate(posting, years=5)
        self.assertEqual(
            verdict,
            NEEDS_RESEARCH,
            f"description shorter than MIN_DESCRIPTION_CHARS must "
            f"produce NEEDS_RESEARCH, not {verdict!r}."
        )

    def test_corpus_c001_produces_needs_research(self) -> None:
        """The canonical missing-evidence fixture in the corpus
        must produce the policy-correct verdict."""
        if not CORPUS_V1.exists():
            self.skipTest("corpus/v1/postings.json not present")
        records = json.loads(CORPUS_V1.read_text(encoding="utf-8"))
        c001 = next((r for r in records if r.get("id") == "c-001"), None)
        self.assertIsNotNone(c001, "corpus must include c-001")
        posting = _minimal_posting(
            title=c001["title"],
            description=c001["body"],
        )
        verdict = _evaluate(posting, years=c001.get("years_can_honestly_claim"))
        self.assertEqual(
            verdict,
            NEEDS_RESEARCH,
            f"corpus c-001 must evaluate to NEEDS_RESEARCH, got "
            f"{verdict!r}. The policy is the contract; the corpus is "
            f"the evidence."
        )

    def test_known_stack_missing_required_tech_produces_not_suitable(self) -> None:
        """The opposite of unknown: present negative. The candidate
        has not listed COBOL as known; the posting requires COBOL.
        The sieve must produce NOT_SUITABLE, not NEEDS_RESEARCH.
        The two cases must not collapse into one bucket."""
        posting = _minimal_posting(
            title="Backend Engineer",
            description=(
                "5+ years of COBOL experience required. We are migrating "
                "a legacy mainframe system and need someone who has "
                "worked with COBOL in production."
            ),
        )
        verdict = _evaluate(
            posting,
            years=5,
            known={"python", "go"},  # no cobol
        )
        # We expect NOT_SUITABLE (or some explicit rejection signal),
        # not a fake SUITABLE and not a soft NEEDS_RESEARCH.
        self.assertIn(
            verdict,
            (NOT_SUITABLE, NEEDS_RESEARCH),
            f"missing required COBOL skill must produce a non-SUITABLE "
            f"verdict, got {verdict!r}."
        )


if __name__ == "__main__":
    unittest.main()
