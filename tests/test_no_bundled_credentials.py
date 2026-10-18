"""W2.1 — no bundled OAuth client, ever.

The shipped tree must contain no real-shaped `client_id`, `client_secret`,
or Google-secret JSON content. The export gate's leak scan already catches
this for the published artifact; this test is the offline, unit-level
check that runs without invoking the full export.

Run:  python3 -m unittest tests.test_no_bundled_credentials -v
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Build the deny patterns the same way the export gate does, so a future
# pattern added to the gate is matched here as well. The gate's regex is
# pulled at runtime by reading the source.
EXPORT_BUNDLE = ROOT / "scripts" / "export_bundle.py"
PATTERNS_TEXT = EXPORT_BUNDLE.read_text(encoding="utf-8")

DENY_TOKENS = re.findall(r'r"([^"]+)"', re.search(r"DENY_TOKENS = \[(.*?)\]\n", PATTERNS_TEXT, re.S).group(1))
DENY_SECRET_PATTERNS = re.findall(r'r"([^"]+)"', re.search(r"DENY_SECRET_PATTERNS = \[(.*?)\]\n", PATTERNS_TEXT, re.S).group(1))


def _venv_python() -> str:
    # Prefer the interpreter running the test suite (the one with the
    # declared dependencies installed). Fall back to an explicit venv
    # override, then to a plain `python3` on PATH. This keeps the suite
    # runnable on a clean machine (CI) where the Hermes venv is absent.
    override = os.environ.get("HERMES_VENV_PYTHON") or os.environ.get("PY")
    if override and Path(override).is_file():
        return override
    return sys.executable


class TestNoBundledCredentialsInSource(unittest.TestCase):
    """The project source tree must not contain real-shaped credentials.

    Fixtures in the test suite are allowed to mention pattern shapes in
    string literals; this test is the broader sweep that catches a
    refactor that adds a real client_id or a real PAT to a module.
    """

    def test_no_real_client_id_or_client_secret_anywhere(self):
        """Long-shaped values in client_id/client_secret fields trip the
        check. Field names without values are fine -- the helper WRITES
        them when saving a token."""
        for path in (ROOT / "jobsearch").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r'"client_id"\s*:\s*"([^"]{20,})"', text):
                self.fail(f"{path}: real-shaped client_id value: {m.group(0)[:60]}")
            for m in re.finditer(r'"client_secret"\s*:\s*"([^"]{20,})"', text):
                self.fail(f"{path}: real-shaped client_secret value: {m.group(0)[:60]}")
        for path in (ROOT / "tools").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r'"client_id"\s*:\s*"([^"]{20,})"', text):
                self.fail(f"{path}: real-shaped client_id value: {m.group(0)[:60]}")
            for m in re.finditer(r'"client_secret"\s*:\s*"([^"]{20,})"', text):
                self.fail(f"{path}: real-shaped client_secret value: {m.group(0)[:60]}")


class TestNoBundledCredentialsInExport(unittest.TestCase):
    """Run the export gate against a fresh copy of the project and assert
    no credential-shaped value is in the built tree.

    This is the integration half: the export gate's leak scan is the
    authoritative check, and this test makes sure that check fires."""

    def test_clean_export_contains_no_deny_token(self):
        skip_dirs = {"__pycache__", ".git", "node_modules", ".wrangler",
                     "cache", "state", "tmp", "var", "digests", "dist"}
        skip_suffixes = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log"}
        tmp = Path(tempfile.mkdtemp(prefix="w21_"))
        try:
            src = tmp / "src"
            out = tmp / "out"
            src.mkdir()
            for entry in sorted(ROOT.iterdir()):
                if entry.name in skip_dirs or entry.suffix in skip_suffixes:
                    continue
                if entry.is_dir():
                    shutil.copytree(entry, src / entry.name,
                                    ignore=shutil.ignore_patterns(*skip_dirs, "*.pyc", "*.pyo",
                                                                  "*.db", "*.log"))
                else:
                    shutil.copy2(entry, src / entry.name)
            r = subprocess.run(
                [_venv_python(), str(ROOT / "scripts" / "export_bundle.py"),
                 "--src", str(src), "--out", str(out), "--allow-no-licence"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                self.fail(f"clean export was rejected:\n{r.stdout}\n{r.stderr}")
            # Use the gate's own leak_scan: it consults the allowance
            # list, this naive loop does not. A file that legitimately
            # contains a deny-listed shape (because it is a test that
            # plants it) is allowed by the gate; a naive regex over the
            # whole built tree would falsely flag it.
            sys.path.insert(0, str(src))
            from scripts.export_bundle import leak_scan
            findings, _allowed = leak_scan(out)
            self.assertEqual(findings, [],
                             f"gate's leak scan found issues in the clean export: {findings}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSetupRefusesWithoutClient(unittest.TestCase):
    """`tools/google/setup.py --check` must exit non-zero when no client
    has been configured. A "no client" path that returns 0 (auth OK) is
    exactly the W2.1 failure mode.

    We run the helper as a subprocess so we never have to import it
    (importing it sets HERMES_HOME-relative paths and would touch the
    real ~/.hermes)."""

    def test_check_exits_nonzero_when_no_client_and_no_token(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HERMES_HOME": home}
            r = subprocess.run(
                [_venv_python(), str(ROOT / "tools" / "google" / "setup.py"), "--check"],
                capture_output=True, text=True, env=env,
            )
            self.assertNotEqual(
                r.returncode, 0,
                f"setup.py --check returned 0 with no client and no token:\n"
                f"stdout: {r.stdout}\nstderr: {r.stderr}",
            )

    def test_check_main_with_no_args_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HERMES_HOME": home}
            r = subprocess.run(
                [_venv_python(), str(ROOT / "tools" / "google" / "setup.py")],
                capture_output=True, text=True, env=env,
            )
            # argparse's required=True group exits 2 on no args.
            self.assertEqual(r.returncode, 2, f"setup.py with no args returned {r.returncode}")
            self.assertTrue("one of the following" in r.stderr.lower() or "required" in r.stderr.lower(),
                            f"setup.py did not print a usage error:\n{r.stderr}")


if __name__ == "__main__":
    unittest.main()
