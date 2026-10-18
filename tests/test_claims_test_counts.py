"""The per-test-file counts in CLAIMS.md are honest.

CLAIMS.md has many claims of the form
    `tests/test_xxx.py` (N tests)
or
    `tests/test_xxx.py` (N cases)
where N is supposed to be the actual count of tests in
that file. A future contributor who adds a test case to
a test file without updating the matching claim line in
CLAIMS.md would leave a small lie in the public surface
of the project.

This test enforces: every numeric test count in CLAIMS.md
matches the actual count produced by `unittest.TestLoader`.

The reason this matters: CLAIMS.md is the project's
constitution. A reader who reads "tests/test_xxx.py (7
tests)" and then sees 6 tests in the actual file would
lose trust in the rest of the document. The counts must
stay honest.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))


def _read_claims() -> str:
    return (ROOT / "CLAIMS.md").read_text(encoding="utf-8")


def _actual_test_count(test_path: str) -> int:
    """Return the count of tests in the given test file,
    using the same loader the suite uses. The file path
    is the one that appears in CLAIMS.md (e.g.
    'tests/test_xxx.py'); we turn it into the dotted
    module name unittest understands.

    Implementation note: this function depends on
    `tests/` being importable as a Python package.
    The standard `unittest discover` invocation works
    without `__init__.py` (it walks the directory
    directly), but `loadTestsFromName` requires the
    package to be on `sys.path`. `tools/verify.sh`
    exports `PYTHONPATH=$ROOT` before running the
    suite, which makes `tests/` importable as a
    namespace package and lets this function work.
    Running this test outside `verify.sh` (or any
    other runner that does not put the project root
    on `sys.path`) will return 1 for every file --
    the `_FailedTest` that `loadTestsFromName`
    returns when the dotted name cannot be
    imported.

    The fix for "I want to run this test without
    verify.sh": invoke with `PYTHONPATH=. python
    -m unittest discover -s tests`, or run
    `bash tools/verify.sh`, which sets the
    path for you.
    """
    rel = test_path.removeprefix("tests/").removesuffix(".py")
    module_name = f"tests.{rel}"
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)
    return suite.countTestCases()


def _parse_test_count_claims(claims: str) -> list[tuple[str, int, int]]:
    """Find every line in CLAIMS.md of the form
        `tests/test_xxx.py` (N tests)
    or
        `tests/test_xxx.py` (N cases)
    and return a list of (test_path, claimed_count, line_no)
    tuples.
    """
    results = []
    for m in re.finditer(
        r"`?(tests/test_\w+\.py)`?\s*\(\s*(\d+)\s+(tests?|cases?)\b",
        claims,
    ):
        line_no = claims[:m.start()].count(chr(10)) + 1
        results.append((m.group(1), int(m.group(2)), line_no))
    return results


class TestClaimsTestCountsAreHonest(unittest.TestCase):
    """For every numeric test count in CLAIMS.md, the actual
    count of tests in the named file must match the claim.
    """

    def test_each_named_test_count_matches_actual(self) -> None:
        claims = _read_claims()
        results = _parse_test_count_claims(claims)
        # We expect at least a handful of claims -- if the
        # test finds zero, the regex is broken and the
        # project has a silent gap.
        self.assertGreater(
            len(results), 5,
            "the regex did not find any test-count claims "
            "in CLAIMS.md; either the claims format has "
            "drifted or this test is broken"
        )
        mismatches = []
        for test_path, claimed, line_no in results:
            actual = _actual_test_count(test_path)
            if actual != claimed:
                mismatches.append(
                    f"L{line_no}: {test_path} claims {claimed} "
                    f"tests but actually has {actual}"
                )
        self.assertEqual(
            mismatches, [],
            "the following CLAIMS.md test counts are stale:\n  "
            + "\n  ".join(mismatches)
        )


if __name__ == "__main__":
    unittest.main()
