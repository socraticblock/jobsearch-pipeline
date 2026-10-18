"""The starter profile must actually work, and stay free of real data.

`profile/profile.starter.yaml` is the front door for a reader who does not want
to read nine pages of reference before seeing a verdict. Two things can go
wrong with it, and both are silent without this test:

  1. It stops loading. The loader treats a missing or malformed field as
     "unknown", so a starter that had drifted into a field name the gate does
     not read would look fine and quietly decide less.
  2. It grows personal data. A template that carries a real city, a real
     currency figure or a real name is a publication hazard in the artifact
     that ships (the export gate scans it too; this test is the local one).

The starter is also the promise that a five-field profile is enough: the
assertions below are that promise, not a smoke test.

Run:  python3 -m unittest tests.test_starter_profile -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch.rules import load_rules, rules_from_profile  # noqa: E402
from jobsearch.requirements import JobPosting, extract  # noqa: E402
from jobsearch import rules as R  # noqa: E402

STARTER = ROOT / "profile" / "profile.starter.yaml"
EXAMPLE = ROOT / "profile" / "profile.example.yaml"

# The fields the starter is allowed to carry, and which the gate must read.
# A starter that needs more than this has stopped being a starter.
STARTER_KEYS = {
    "stack", "compensation", "location_and_arrangement",
    "years_can_honestly_claim",
}


class TestStarterProfile(unittest.TestCase):

    def test_starter_exists(self) -> None:
        self.assertTrue(
            STARTER.is_file(),
            f"missing {STARTER.relative_to(ROOT)}. The README points a new "
            f"reader at it as the fast path into a working profile.",
        )

    def test_starter_parses_and_declares_what_the_gate_reads(self) -> None:
        import yaml
        data = yaml.safe_load(STARTER.read_text(encoding="utf-8")) or {}
        extra = set(data) - STARTER_KEYS
        self.assertEqual(
            extra, set(),
            f"the starter carries keys the gate does not read: "
            f"{sorted(extra)}. Either wire them or move them to "
            f"profile.example.yaml -- a starter field that decides nothing "
            f"is a trap for the reader who fills it in.",
        )
        self.assertIn("stack", data)
        self.assertIn("compensation", data)

    def test_the_starter_reaches_the_gate_as_written(self) -> None:
        """Five fields, read by the real loader, producing real rule values."""
        rules = load_rules(STARTER)
        self.assertIsNotNone(rules.profile_path, "the starter did not load")
        self.assertIn("python", rules.known_stack)
        self.assertIn("postgresql", rules.known_stack)
        self.assertNotIn(
            "react", rules.known_stack,
            "'learning' must not count as HELD: the status vocabulary is the "
            "one thing the reader has to get right",
        )
        self.assertEqual(rules.floor_net, 6000)
        self.assertEqual(rules.floor_currency, "EUR")
        self.assertEqual(rules.years_can_honestly_claim, 5)
        self.assertEqual(rules.work_authorisation, frozenset({"eu"}))
        self.assertTrue(rules.local_ok, "the starter declares a local market")

    def test_a_five_field_profile_judges_a_posting(self) -> None:
        """The promise: the starter, unchanged, produces a real verdict."""
        rules = load_rules(STARTER)
        posting = JobPosting(
            title="Backend Engineer",
            description=(
                "Backend Engineer for a logistics platform. You will own Python "
                "services and PostgreSQL schemas, keep the query plans honest, "
                "and work with the analysts who use them. Remote within the EU. "
                "English required."
            ),
            location="Remote (EU)",
            salary_text="7000 EUR per month",
        )
        extract(
            posting,
            extra_terms=rules.known_stack | rules.learnable_stack,
            extra_languages=rules.languages_usable,
        )
        verdict = R.evaluate(posting, rules)
        held = [s for s in verdict.satisfied if "technology held" in s]
        self.assertGreaterEqual(len(held), 2, verdict.satisfied)
        self.assertIn(verdict.outcome, ("strong_match", "potential_match"))
        self.assertEqual(verdict.failed_essential, [])
        self.assertEqual(verdict.salary.get("vs_floor"), "above_floor")

    def test_the_starter_carries_no_personal_data(self) -> None:
        """A shipped template names nobody, and prices nothing real."""
        # The deny-list (with the *real* values) lives in
        # `scripts/export_bundle.py` (excluded from the public
        # bundle). We read it at test time and derive the
        # marker strings by stripping the regex syntax, so
        # the test source itself contains no personal values.
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "tools"))
        from export_bundle import DENY_TOKENS
        markers = [
            p.replace(r"\b", "").replace("\\", "").casefold()
            for p in DENY_TOKENS
        ]
        text = STARTER.read_text(encoding="utf-8")
        lowered = text.casefold()
        for marker in markers:
            self.assertNotIn(
                marker, lowered,
                f"the starter names {marker!r}. It ships in the public "
                f"artifact; a template with real data in it is a leak.",
            )
        # The floor must be visibly a placeholder the reader replaces, not a
        # figure that reads as someone's actual pay.
        self.assertIn("6000", text)

    def test_the_loader_ignores_a_near_miss_field_silently(self) -> None:
        """Documents the failure mode the starter's key check protects."""
        rules = rules_from_profile({"work_authorisation_typo": ["eu"]})
        self.assertEqual(
            rules.work_authorisation, frozenset(),
            "a misspelled authorisation key must not be guessed at; an empty "
            "declaration is NEEDS_RESEARCH, which is the safe direction",
        )

    def test_the_long_form_reference_still_exists_and_documents_the_field(self) -> None:
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn(
            "work_authorisation", text,
            "profile.example.yaml must document the authorisation field: it "
            "is the reference a reader consults when the starter is not "
            "enough, and the field decides location verdicts.",
        )


if __name__ == "__main__":
    unittest.main()
