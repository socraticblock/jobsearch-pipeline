"""The version a user sees must be the version that was shipped.

`pyproject.toml` is what the packaging layer reports and what PyPI publishes;
`jobsearch.__version__` is what `python -c "import jobsearch"` reports and what
an issue reporter will paste. If the two drift, the installed package answers a
different question from the one the index answered, and a bug report becomes
unreproducible -- the published 1.0.0 wheel shipped `__version__ = "0.1.0"`.

This test pins the two together. It parses `pyproject.toml` with a regex rather
than `tomllib` because the package supports Python 3.10, where `tomllib` does
not exist.
"""

import re
import unittest
from pathlib import Path

import jobsearch

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    path = ROOT / "pyproject.toml"
    if not path.is_file():
        # `pyproject.toml` is source-only: `scripts/export_bundle.py` EXCLUDEs it,
        # so the exported copy of this suite has no metadata file to compare
        # against. Skipping there is not a pass -- in the source tree, where the
        # packaging actually happens, the comparison below always runs.
        raise unittest.SkipTest(
            "pyproject.toml is source-only and not present in the export bundle")
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise AssertionError("pyproject.toml has no top-level version line")
    return match.group(1)


class TestVersionIdentity(unittest.TestCase):
    def test_dunder_version_matches_pyproject(self):
        self.assertEqual(
            jobsearch.__version__,
            _pyproject_version(),
            "jobsearch.__version__ and pyproject.toml version disagree; an "
            "installed user would report a version the index never published",
        )

    def test_version_is_not_a_placeholder(self):
        version = jobsearch.__version__
        self.assertNotIn("dev", version)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
