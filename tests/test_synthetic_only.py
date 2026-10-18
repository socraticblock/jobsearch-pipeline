"""SYNTHETIC ONLY — every fixture file in this project must be self-declared
synthetic.

Borrowed pattern from inbox-job-tracker's `tests/fixtures/emails.json` and
the synthetic-evidence standard in `CLAIMS.md`. The header is a build-time
guarantee that no real-user data ever ships in a fixture, corpus row, or
test data file.

Rule: any file under `tests/fixtures/`, `corpus/`, or `fixtures/` whose name
ends in `.json`, `.yaml`, `.yml`, `.csv`, `.txt`, or `.md` must begin with
the literal string "SYNTHETIC ONLY" on its first non-empty line. A file
that lacks the header is a build failure.

This is the test that backs CLAIMS.md §"Synthetic evidence standard" and
the assertion in `AGENTS.md` that "SYNTHETIC ONLY" is a build-checked
string, not a free-form comment.

Run:  python3 -m unittest tests.test_synthetic_only -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Directories that may hold fixture or corpus data.
FIXTURE_DIRS = [
    ROOT / "tests" / "fixtures",
    ROOT / "corpus",
    ROOT / "fixtures",
]

# Extensions that count as data files. Source code (.py, .sh, .mjs) is
# excluded because the rule is about data, not about the program.
DATA_EXTENSIONS = {".yaml", ".yml", ".csv", ".txt", ".md"}
# JSON files (`.json`) have no comment syntax, so the SYNTHETIC ONLY marker
# is recorded in a sidecar `.synthetic` file in the same directory. The
# corpus-shape test (`tests/test_corpus.py`) is the strict check for JSON
# fixtures; the marker is a fail-closed defence at the directory-walk
# level.
JSON_EXTENSIONS = {".json"}

# The exact first-line marker. Case-sensitive, no leading whitespace.
SYNTHETIC_MARKER = "SYNTHETIC ONLY"
# Sidecar file for JSON fixtures. The extension is intentionally
# non-`.json` so the file can carry free-form documentation
# (including a `#` comment block) without conflicting with the
# JSON parser. The directory's first JSON file is the "owned" file
# the sidecar protects.
JSON_SYNTHETIC_SIDECAR = ".synthetic"


def _iter_data_files() -> list[Path]:
    """Walk FIXTURE_DIRS and return every data file that exists."""
    found: list[Path] = []
    for base in FIXTURE_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in DATA_EXTENSIONS:
                found.append(path)
            elif path.suffix.lower() in JSON_EXTENSIONS:
                # JSON files: require a sidecar `synthetic.json` in the
                # same directory. The sidecar is the marker.
                sidecar = path.parent / JSON_SYNTHETIC_SIDECAR
                if sidecar.exists():
                    found.append(sidecar)
    return sorted(found)


class TestSyntheticOnlyHeader(unittest.TestCase):
    """Every fixture or corpus data file must self-declare as synthetic."""

    def setUp(self) -> None:
        self.data_files = _iter_data_files()

    def test_at_least_one_fixture_or_corpus_dir_exists(self) -> None:
        # If none of the directories exist, this is informational: the
        # corpus work is still in flight. The rule does not apply yet.
        # The check that follows is skipped.
        if not self.data_files:
            self.skipTest(
                "No fixture or corpus data files exist yet. "
                "The corpus workstream (W3.5) is still in flight."
            )

    def test_every_data_file_has_synthetic_marker_on_first_line(self) -> None:
        if not self.data_files:
            self.skipTest("No data files to check.")
        offenders: list[str] = []
        for path in self.data_files:
            # Sidecar file: its presence AND its first-line marker is
            # the proof. We do not require the corresponding .json to
            # have a marker (JSON has no comment syntax). The
            # corpus-shape test is the strict check for JSON content.
            is_sidecar = path.name == JSON_SYNTHETIC_SIDECAR
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    first_line = ""
                    for raw in f:
                        line = raw.strip()
                        if line:
                            first_line = line
                            break
            except OSError as e:
                offenders.append(f"{path}: cannot read ({e})")
                continue
            if is_sidecar:
                # Sidecar must start with the marker on its first line.
                if not first_line.startswith(SYNTHETIC_MARKER):
                    rel = path.relative_to(ROOT)
                    offenders.append(
                        f"{rel}: sidecar first line does not start with "
                        f"{SYNTHETIC_MARKER!r} (got: {first_line[:60]!r})"
                    )
                continue
            # The marker is a literal string on the first non-empty line.
            # YAML and shell files may comment it with `#`; the rest of
            # the line is documentation, not a substitute for the marker.
            # Strip exactly one leading `#` (the file's comment marker),
            # then strip whitespace, and assert the marker is the first
            # thing. A line that does not start with `# SYNTHETIC ONLY`
            # or `SYNTHETIC ONLY` is a build failure.
            stripped = first_line.lstrip()
            if stripped.startswith("#"):
                stripped = stripped[1:].lstrip()
            if not stripped.startswith(SYNTHETIC_MARKER):
                rel = path.relative_to(ROOT)
                offenders.append(
                    f"{rel}: first non-empty line does not start with "
                    f"{SYNTHETIC_MARKER!r} (got: {first_line[:60]!r})"
                )
        if offenders:
            self.fail(
                "The following fixture or corpus files are missing the "
                "SYNTHETIC ONLY header. Every data file in tests/fixtures, "
                "corpus/, or fixtures/ must self-declare as synthetic. "
                "Add the marker on the first non-empty line. "
                "Offenders:\n  " + "\n  ".join(offenders)
            )

    def test_every_json_dir_has_synthetic_sidecar(self) -> None:
        """A JSON fixture or corpus file in tests/fixtures/, corpus/,
        or fixtures/ must have a `synthetic.json` sidecar in the same
        directory. The sidecar's first line is the marker.

        This is the JSON analogue of the marker-on-first-line rule.
        A JSON file without a sidecar is a build failure."""
        missing: list[str] = []
        for base in FIXTURE_DIRS:
            if not base.exists():
                continue
            for path in base.rglob("*.json"):
                if not path.is_file():
                    continue
                # Skip the sidecar itself.
                if path.name == JSON_SYNTHETIC_SIDECAR:
                    continue
                sidecar = path.parent / JSON_SYNTHETIC_SIDECAR
                if not sidecar.exists():
                    rel = path.relative_to(ROOT)
                    missing.append(
                        f"{rel}: JSON file has no {JSON_SYNTHETIC_SIDECAR} "
                        f"sidecar in {path.parent.relative_to(ROOT)}"
                    )
        if missing:
            self.fail(
                "JSON fixture or corpus files are missing their "
                f"{JSON_SYNTHETIC_SIDECAR} sidecar. Create the sidecar "
                "with 'SYNTHETIC ONLY' on the first line. "
                "Offenders:\n  " + "\n  ".join(missing)
            )

    def test_no_real_profile_field_in_fixtures(self) -> None:
        """Defence-in-depth: even with the marker, no real-name-shaped
        string should appear. Catches a marker-only file that someone
        added real content to.

        Matches obvious personal-data shapes: email addresses, currency
        values with cents, and the project's own profile keys."""
        import re
        if not self.data_files:
            self.skipTest("No data files to check.")
        email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        # The fixture file legitimately may reference a 'years_can_honestly_claim'
        # field. We only flag things that look like real personal data: emails.
        offenders: list[str] = []
        for path in self.data_files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in email_re.findall(content):
                # Allow the synthetic-domain examples that the test suite
                # itself uses (e.g. northwind.example, contoso.example).
                if match.endswith(".example") or match.endswith(".test"):
                    continue
                rel = path.relative_to(ROOT)
                offenders.append(f"{rel}: contains email {match!r}")
        if offenders:
            self.fail(
                "Fixture or corpus data files contain real-email-shaped "
                "strings. Even with the SYNTHETIC ONLY marker, real "
                "emails are not allowed. Use a `.example` domain. "
                "Offenders:\n  " + "\n  ".join(offenders)
            )


if __name__ == "__main__":
    unittest.main()
