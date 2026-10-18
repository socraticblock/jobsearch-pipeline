"""The README and CLAIMS.md count claims for the shipped corpus
must match the actual corpus file. Two places make the claim:

  - README.md "the 22-fixture shipped corpus
    and prints a digest-style"
  - CLAIMS.md "The corpus ships 22 fixtures covering all four
    verdict bands"

A future contributor who adds or removes a fixture would see
this test fail with a precise error message naming the file,
line, claimed number, and actual count. The error makes the
fix one operation: bump the number in the prose, run the
suite, and the test goes green.

The contract: a single test class, no fixtures, no shell-out.
The test reads the corpus from disk and the count claims from
the public docs and asserts they match.

Why this matters: the corpus is the gate's documented behaviour.
The "21-fixture" claim is a promise a reader of the README
takes home. If the count drifts, a careful reader can be
misled into thinking the corpus is larger or smaller than it
is. The contract web (test_readme_count, test_cl_005, etc.)
already covers bundle size, test count, and claim range; this
test closes the corpus-size hole so the count is honest across
the public surface.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "v1" / "postings.json"


def _read_corpus_count() -> int:
    """Count the records in the shipped corpus. The
    file is a JSON array of records, each with an
    `id` field. The count is the number of records.
    """
    records = json.loads(CORPUS.read_text(encoding="utf-8"))
    return len(records)


def _read_claim(text: str, claim_kind: str) -> int:
    """Find the corpus count claim in the given text. The
    patterns are:
      - 'N-fixture shipped corpus' (in README.md)
      - 'corpus ships N fixtures' (in CLAIMS.md)
    Returns the number, or raises AssertionError if the
    pattern is not present.
    """
    if claim_kind == "readme":
        m = re.search(r"the\s+(\d+)-fixture\s+shipped\s+corpus", text)
    elif claim_kind == "claims":
        m = re.search(r"corpus\s+ships\s+(\d+)\s+fixtures", text)
    else:
        raise ValueError(f"unknown claim_kind: {claim_kind!r}")
    if not m:
        raise AssertionError(
            f"No '{claim_kind}' corpus count claim found in text. "
            f"Either add the claim or fix this test."
        )
    return int(m.group(1))


class TestCorpusCountClaim(unittest.TestCase):
    """The README's and CLAIMS.md's corpus count claim
    equals the actual count of records in the shipped
    corpus. If they differ, the public docs are stale.
    """

    def test_readme_corpus_count_matches_shipped_corpus(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        claimed = _read_claim(readme, "readme")
        actual = _read_corpus_count()
        self.assertEqual(
            claimed, actual,
            f"README.md claims the shipped corpus has "
            f"{claimed} fixtures (line matching 'the N-fixture "
            f"shipped corpus'), but the corpus file has {actual} "
            f"records. Update the prose, or restore the corpus to "
            f"the claimed size."
        )

    def test_claims_md_corpus_count_matches_shipped_corpus(self) -> None:
        claims = (ROOT / "CLAIMS.md").read_text(encoding="utf-8")
        claimed = _read_claim(claims, "claims")
        actual = _read_corpus_count()
        self.assertEqual(
            claimed, actual,
            f"CLAIMS.md claims the shipped corpus has "
            f"{claimed} fixtures (line matching 'corpus ships N "
            f"fixtures'), but the corpus file has {actual} "
            f"records. Update the prose, or restore the corpus to "
            f"the claimed size."
        )

    def test_corpus_actually_has_four_verdict_bands_covered(self) -> None:
        """CL-007 also claims the corpus covers all four
        verdict bands. A future contributor who accidentally
        drops one band (e.g. adds only `strong_match`
        fixtures) would silently shrink the band coverage.
        This test pins the band coverage so a band can only
        be lost by an explicit code change that drops the
        test, not by accident.
        """
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        bands = {r.get("expect", "") for r in records}
        for band in (
            "strong_match",
            "potential_match",
            "needs_research",
            "not_suitable",
        ):
            self.assertIn(
                band, bands,
                f"The corpus no longer covers the {band!r} band. "
                f"CL-007 claims all four bands are covered. Add a "
                f"fixture with `expect: {band}` and the band name "
                f"in its `why` field, or remove the band from the "
                f"claim."
            )


if __name__ == "__main__":
    unittest.main()
