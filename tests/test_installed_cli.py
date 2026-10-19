"""Genuine isolated installation tests for pip-installed CLI.

These tests build the sdist and wheel, install each into a fresh target
directory, and verify that the installed commands work outside the source
checkout.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestIsolatedInstall(unittest.TestCase):
    """Install sdist and wheel into isolated dirs and verify CLI commands."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.dist = cls.root / "dist"
        if not list(cls.dist.glob("*.whl")) or not list(cls.dist.glob("*.tar.gz")):
            subprocess.run(
                [sys.executable, "-m", "build"],
                cwd=str(cls.root),
                check=True,
                capture_output=True,
            )
        cls.whl = sorted(cls.dist.glob("*.whl"))[-1]
        cls.sdist = sorted(cls.dist.glob("*.tar.gz"))[-1]

    def _install(self, artifact):
        tmpdir = tempfile.mkdtemp()
        target = Path(tmpdir) / "target"
        target.mkdir()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--target", str(target), str(artifact)],
            check=True,
            capture_output=True,
        )
        # Verify importable from target
        result = subprocess.run(
            [sys.executable, "-c", "import jobsearch; print('OK')"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            env={"PYTHONPATH": str(target)},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Package not importable: {result.stderr}")
        return tmpdir, target

    def _run(self, target, *args):
        env = {"PYTHONPATH": str(target)}
        # Try console script
        bin_dir = target / "bin"
        jobsearch_bin = bin_dir / "jobsearch"
        if jobsearch_bin.exists():
            cmd = [str(jobsearch_bin), *args]
        else:
            cmd = [sys.executable, "-m", "jobsearch.cli", *args]
            env["PYTHONPATH"] = str(target)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd="/tmp",
            env=env,
        )
        return result

    def _cleanup(self, tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_wheel_help(self):
        tmpdir, target = self._install(self.whl)
        try:
            result = self._run(target, "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("jobsearch", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_wheel_onboard_help(self):
        tmpdir, target = self._install(self.whl)
        try:
            result = self._run(target, "onboard", "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("--cv", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_wheel_render_help(self):
        tmpdir, target = self._install(self.whl)
        try:
            result = self._run(target, "render", "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("--text", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_wheel_render_text_no_db(self):
        tmpdir, target = self._install(self.whl)
        try:
            result = self._run(target, "render", "--text")
            self.assertEqual(result.returncode, 2)
            self.assertIn("no ledger", result.stderr)
        finally:
            self._cleanup(tmpdir)

    def test_wheel_doctor_requires_checkout(self):
        tmpdir, target = self._install(self.whl)
        try:
            result = self._run(target, "doctor")
            self.assertEqual(result.returncode, 2)
            self.assertIn("repository checkout", result.stderr)
            self.assertIn("git clone", result.stderr)
        finally:
            self._cleanup(tmpdir)

    def test_sdist_help(self):
        tmpdir, target = self._install(self.sdist)
        try:
            result = self._run(target, "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("jobsearch", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_sdist_onboard_help(self):
        tmpdir, target = self._install(self.sdist)
        try:
            result = self._run(target, "onboard", "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("--cv", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_sdist_render_help(self):
        tmpdir, target = self._install(self.sdist)
        try:
            result = self._run(target, "render", "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("--text", result.stdout)
        finally:
            self._cleanup(tmpdir)

    def test_sdist_doctor_requires_checkout(self):
        tmpdir, target = self._install(self.sdist)
        try:
            result = self._run(target, "doctor")
            self.assertEqual(result.returncode, 2)
            self.assertIn("repository checkout", result.stderr)
        finally:
            self._cleanup(tmpdir)