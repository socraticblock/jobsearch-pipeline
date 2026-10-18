"""Regression test: stale MANIFEST.txt must not be tracked."""

import subprocess
import unittest
from pathlib import Path


class TestNoStaleManifest(unittest.TestCase):
    def test_manifest_txt_not_tracked(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["git", "ls-files", "MANIFEST.txt"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.stdout.strip(),
            "",
            "MANIFEST.txt is still tracked; remove it and update README.",
        )

    def test_readme_no_stale_manifest_claim(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text()
        self.assertNotIn(
            "records a sha256 for every shipped file",
            readme,
            "README still claims MANIFEST.txt records hashes.",
        )