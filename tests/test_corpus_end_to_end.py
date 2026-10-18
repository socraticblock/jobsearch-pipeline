"""I-04 QA test -- every corpus fixture is exercised end-to-end.

The corpus at `corpus/v1/postings.json` is the contract: each record
specifies an `expect` (one of strong_match / potential_match /
needs_research / not_suitable) and a `profile` (the candidate's
profile to evaluate against). This test loads every record,
populates the `requirements` field via `extract()`, calls
`evaluate()`, and asserts the outcome equals the record's `expect`.

A single mismatch fails the build. The corpus is the gate's
published behaviour; the gate is the implementation; this test is
the bridge.

This is the test that makes the corpus useful: a fixture that
documents `expect: not_suitable` but actually produces
`strong_match` is a build failure, not a documentation drift.

Run:  python3 -m unittest tests.test_corpus_end_to_end -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS_V1 = ROOT / "corpus" / "v1" / "postings.json"

from jobsearch import rules as rules_module  # noqa: E402
from jobsearch.requirements import JobPosting, extract  # noqa: E402


def _load_corpus() -> list[dict]:
    if not CORPUS_V1.exists():
        return []
    return json.loads(CORPUS_V1.read_text(encoding="utf-8"))


def _evaluate_fixture(record: dict) -> str:
    """Run the gate end-to-end on a corpus record. Returns the
    outcome string."""
    profile = record.get("profile", {})
    # One builder for the dict-shaped profile, shared with tools/demo_sieve.py,
    # so the corpus and the demo cannot drift on which fields reach the gate.
    rules = rules_module.rules_from_profile(profile)
    posting = JobPosting(
        title=record["title"],
        description=record["body"],
        location=record.get("location", "remote"),
    )
    extract(
        posting,
        extra_terms=rules.known_stack | rules.learnable_stack,
        extra_languages=rules.languages_usable,
    )
    verdict = rules_module.evaluate(posting, rules)
    return verdict.outcome


class TestCorpusEndToEnd(unittest.TestCase):
    """Every corpus fixture must produce the documented verdict."""

    def test_corpus_exists(self) -> None:
        if not _load_corpus():
            self.skipTest(f"No corpus at {CORPUS_V1.relative_to(ROOT)}")

    def test_every_fixture_produces_documented_expect(self) -> None:
        records = _load_corpus()
        failures: list[str] = []
        for rec in records:
            rid = rec.get("id", "?")
            expected = rec.get("expect", "")
            try:
                actual = _evaluate_fixture(rec)
            except Exception as e:  # noqa: BLE001
                failures.append(
                    f"  {rid} ({rec.get('rule', '?')}): evaluate() "
                    f"raised {type(e).__name__}: {e}"
                )
                continue
            if actual != expected:
                failures.append(
                    f"  {rid} ({rec.get('rule', '?')}): expected "
                    f"{expected!r}, got {actual!r}"
                )
        if failures:
            self.fail(
                "The corpus says one thing; the gate does another. "
                "Either the fixture's `expect` is wrong (update the "
                "corpus) or the gate's logic has drifted (update the "
                "rule). Failures:\n" + "\n".join(failures)
            )

    def test_every_fixture_has_profile(self) -> None:
        """A fixture without a profile is a build failure: the QA
        test cannot run without it, and a contributor cannot
        reproduce the expected verdict."""
        records = _load_corpus()
        offenders: list[str] = []
        for rec in records:
            if "profile" not in rec:
                offenders.append(rec.get("id", "?"))
        if offenders:
            self.fail(
                "The following corpus records are missing the "
                "`profile` field that the QA test reads:\n  "
                + "\n  ".join(offenders)
                + "\nAdd a profile dict to each record; the default "
                "profile is a senior Python+Go engineer with 5 "
                "years."
            )

    def test_every_fixture_is_reproducible(self) -> None:
        """The same fixture evaluated twice must produce the same
        outcome. The gate is deterministic; a flake is a bug."""
        records = _load_corpus()
        for rec in records:
            first = _evaluate_fixture(rec)
            second = _evaluate_fixture(rec)
            self.assertEqual(
                first, second,
                f"{rec.get('id', '?')}: gate is non-deterministic; "
                f"first={first!r}, second={second!r}. The gate must "
                f"be a pure function of (posting, rules)."
            )


if __name__ == "__main__":
    unittest.main()
