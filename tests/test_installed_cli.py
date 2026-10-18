"""Genuine isolated installation tests for pip-installed CLI.

These tests build the sdist and wheel, install each in a fresh virtualenv,
and verify that the installed commands work outside the source checkout.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestIsolatedInstall(unittest.TestCase):
    """Install sdist and wheel in isolated venvs and verify CLI commands."""

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

    def _make_venv(self):
        tmpdir = tempfile.mkdtemp()
        venv = Path(tmpdir) / "venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            check=True,
            capture_output=True,
        )
        return tmpdir, venv

    def _install(self, venv, artifact):
        pip = venv / "bin" / "pip"
        subprocess.run(
            [str(pip), "install", "--quiet", str(artifact)],
            check=True,
            capture_output=True,
        )
        return venv / "bin" / "jobsearch"

    def test_wheel_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.whl)
            result = subprocess.run(
                [str(jobsearch), "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("jobsearch", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_wheel_onboard_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.whl)
            result = subprocess.run(
                [str(jobsearch), "onboard", "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("--cv", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_wheel_render_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.whl)
            result = subprocess.run(
                [str(jobsearch), "render", "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("--text", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_wheel_render_text_no_db(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.whl)
            result = subprocess.run(
                [str(jobsearch), "render", "--text"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("no ledger", result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_wheel_doctor_requires_checkout(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.whl)
            result = subprocess.run(
                [str(jobsearch), "doctor"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("repository checkout", result.stderr)
            self.assertIn("git clone", result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_sdist_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.sdist)
            result = subprocess.run(
                [str(jobsearch), "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("jobsearch", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_sdist_onboard_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.sdist)
            result = subprocess.run(
                [str(jobsearch), "onboard", "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("--cv", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_sdist_render_help(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.sdist)
            result = subprocess.run(
                [str(jobsearch), "render", "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("--text", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_sdist_doctor_requires_checkout(self):
        tmpdir, venv = self._make_venv()
        try:
            jobsearch = self._install(venv, self.sdist)
            result = subprocess.run(
                [str(jobsearch), "doctor"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("repository checkout", result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)