"""The CL-XXX range in CHANGELOG.md matches the CL-XXX range
in CLAIMS.md.

CHANGELOG.md is supposed to say something like
"CL-001..CL-023" -- the full set of claims. If a
contributor adds CL-024 to CLAIMS.md but forgets to
update CHANGELOG.md, the catalogue claim is stale.

This test enforces: the maximum CL-XXX in CLAIMS.md
equals the upper bound of every "CL-001..CL-NNN" range
in CHANGELOG.md (and other public-facing .md files).

The reason this matters: a reader of CHANGELOG.md who
sees "all 23 claims shipped" can verify by reading
CLAIMS.md, and the contract is: the CHANGELOG.md claim
agrees with the actual count.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# Public-facing documents where a "CL-001..CL-NNN" claim
# would be made. The exported set of these files is
# smaller; this is the set we enforce.
PUBLIC_FACING_MD = [
    "CHANGELOG.md",
]


def _read_claim_ids() -> list[int]:
    """Return the sorted list of CL-XXX claim IDs in CLAIMS.md."""
    claims = (ROOT / "CLAIMS.md").read_text(encoding="utf-8")
    return sorted({int(n) for n in re.findall(r"^#### CL-(\d+)", claims, re.M)})


def _read_range_claims_in(path: Path) -> list[tuple[int, int, int]]:
    """Find every "CL-001..CL-NNN" range in the given file
    and return a list of (start, end, line_no) tuples."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    results = []
    for m in re.finditer(r"CL-0*(\d+)\.\.CL-0*(\d+)", text):
        line_no = text[:m.start()].count(chr(10)) + 1
        results.append((int(m.group(1)), int(m.group(2)), line_no))
    return results


class TestClaimRangeConsistency(unittest.TestCase):
    """Every "CL-XXX..CL-YYY" range in public-facing docs
    must agree with the actual claim catalogue."""

    def test_every_range_matches_claim_catalogue(self) -> None:
        ids = _read_claim_ids()
        self.assertGreater(len(ids), 10, "CLAIMS.md has too few claims to enforce a range")
        actual_start, actual_end = ids[0], ids[-1]
        mismatches = []
        for filename in PUBLIC_FACING_MD:
            path = ROOT / filename
            for start, end, line_no in _read_range_claims_in(path):
                if start != actual_start or end != actual_end:
                    mismatches.append(
                        f"{filename}:{line_no}: "
                        f"claims CL-{start:03d}..CL-{end:03d} but "
                        f"the actual range is "
                        f"CL-{actual_start:03d}..CL-{actual_end:03d}"
                    )
        self.assertEqual(
            mismatches, [],
            "the following CL-range claims are stale:\n  "
            + "\n  ".join(mismatches)
        )


if __name__ == "__main__":
    unittest.main()
