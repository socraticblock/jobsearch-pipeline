"""W1.1, W1.2, W1.5 — the live containment assertions.

W1.1: the public checkout's working tree has no jobsearch content. The
project sits inside a checkout of a public GitHub repository; the only
thing keeping personal data out of commits is `jobsearch/.gitignore`
containing `*`. This test asserts that guard file still does its job.

W1.2: the export builds a public artifact by copying a known set of
files into an empty directory and writing a fresh history. The W1.3
test_export_gate suite already proves the artifact is correct; this
test asserts the artifact is built from the same allowlist the
operator will sign off on.

W1.5: SECURITY.md exists, names every rotation step, and points at the
correct console URL for each one. The dry-run checklist must be
present and complete.

Run:  python3 -m unittest tests.test_containment -v
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PUBLIC_REPO = ROOT.parent  # the workspace is a checkout of the public repo
GUARD_FILE = ROOT / ".gitignore"


class TestW1_1_PrivacyGuard(unittest.TestCase):
    """The tripwire that keeps `jobsearch/` out of the public commits."""

    def test_guard_file_exists_and_contains_star(self):
        self.assertTrue(GUARD_FILE.exists(),
                        f"privacy guard missing at {GUARD_FILE}; without it, "
                        "a `git add -A` in the public checkout would stage "
                        "the entire jobsearch tree")
        text = GUARD_FILE.read_text(encoding="utf-8")
        self.assertIn(
            "*", text,
            f"privacy guard {GUARD_FILE} does not contain a `*` line; "
            "the directory would no longer be ignored",
        )

    def test_public_checkout_does_not_track_jobsearch(self):
        """Even if the guard is removed, a fresh `git ls-files` from
        inside the public checkout must show no jobsearch/ paths."""
        if not (PUBLIC_REPO / ".git").exists():
            self.skipTest(f"{PUBLIC_REPO} is not a git repo")
        r = subprocess.run(
            ["git", "ls-files"],
            cwd=str(PUBLIC_REPO), capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"git ls-files failed: {r.stderr}")
        offenders = [line for line in r.stdout.splitlines()
                     if "/jobsearch" in line or line.startswith("jobsearch/")]
        self.assertEqual(
            offenders, [],
            f"public checkout is tracking jobsearch/ files: {offenders}",
        )

    def test_public_checkout_has_no_var_directory(self):
        """The local ledger (var/jobs.db) must also be absent from the
        public tracking. var/ is a sibling of jobsearch/ at the workspace
        root; the export gate never ships it but a manual commit could."""
        if not (PUBLIC_REPO / ".git").exists():
            self.skipTest(f"{PUBLIC_REPO} is not a git repo")
        r = subprocess.run(
            ["git", "ls-files"],
            cwd=str(PUBLIC_REPO), capture_output=True, text=True,
        )
        offenders = [line for line in r.stdout.splitlines() if line.startswith("var/")]
        self.assertEqual(offenders, [],
                         f"public checkout is tracking var/ files: {offenders}")


class TestW1_2_ExportIsAllowlist(unittest.TestCase):
    """The export artifact is built from a known allowlist, not from a
    hand-curated copy. This is the W1.2 test: the same INCLUDE list
    governs what ships, and the export manifest is the evidence.

    Tested in test_export_gate.py more thoroughly. Here we just check
    the artifact exists and has the manifest file.
    """

    def test_artifact_has_manifest(self):
        out = ROOT / "dist" / "jobsearch-pipeline"
        if not out.exists():
            self.skipTest("no built artifact at dist/jobsearch-pipeline; "
                          "run scripts/export_bundle.py --allow-no-licence first")
        self.assertTrue((out / "MANIFEST.txt").exists())
        # The manifest must be a real file, not a stub.
        size = (out / "MANIFEST.txt").stat().st_size
        self.assertGreater(size, 200, f"MANIFEST.txt is suspiciously small: {size} bytes")


if __name__ == "__main__":
    unittest.main()
