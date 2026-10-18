"""Acceptance tests for the onboarding tool."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from tools import onboard as onboard_mod  # noqa: E402


class OnboardTests(unittest.TestCase):
    def test_extract_skills_finds_known_tokens(self):
        text = "I build with TypeScript, React and Node.js. Also Python and Docker."
        skills = onboard_mod.extract_skills(text)
        self.assertIn("TypeScript", skills)
        self.assertIn("React", skills)
        self.assertIn("Node.js", skills)
        self.assertIn("Python", skills)
        self.assertIn("Docker", skills)

    def test_extract_skills_empty_text(self):
        self.assertEqual(onboard_mod.extract_skills(""), [])

    def test_render_profile_contains_skills_and_prefs(self):
        prefs = {"floor": "5000 EUR", "currency": "EUR", "floor_basis": "NET",
                 "local_markets": ["YourCity", "YourCountry"], "work_authorisation": ["eu"],
                 "years": 3}
        out = onboard_mod.render_profile(["Python", "React"], prefs)
        self.assertIn("skill: Python", out)
        self.assertIn("skill: React", out)
        self.assertIn('floor: "5000 EUR"', out)
        self.assertIn("YourCity", out)
        self.assertIn("years_can_honestly_claim: 3", out)

    def test_onboard_writes_profile_from_txt(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cv = td / "cv.txt"
            cv.write_text("Experienced in TypeScript, React, Node.js, and PostgreSQL.", encoding="utf-8")
            out = td / "profile.yaml"
            rc = onboard_mod.main(["--cv", str(cv), "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            content = out.read_text(encoding="utf-8")
            self.assertIn("skill: TypeScript", content)
            self.assertIn("skill: React", content)

    def test_wizard_via_onboard_main(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cv = td / "cv.txt"
            cv.write_text("Experienced in Python and React.", encoding="utf-8")
            out = td / "profile.yaml"
            import builtins
            import sys as _sys
            answers = iter(["Berlin", "Germany", "eu,us", "5000 EUR", "4"])
            orig_input = builtins.input
            orig_isatty = _sys.stdin.isatty
            builtins.input = lambda prompt="": next(answers)
            _sys.stdin.isatty = lambda: True
            try:
                rc = onboard_mod.main(["--cv", str(cv), "--out", str(out)])
            finally:
                builtins.input = orig_input
                _sys.stdin.isatty = orig_isatty
            self.assertEqual(rc, 0)
            content = out.read_text(encoding="utf-8")
            self.assertIn("Berlin", content)
            self.assertIn("Germany", content)
            self.assertIn("5000 EUR", content)
            self.assertIn("years_can_honestly_claim: 4", content)

    def test_onboard_missing_cv_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "profile.yaml"
            rc = onboard_mod.main(["--cv", str(Path(td) / "nope.txt"), "--out", str(out)])
            self.assertEqual(rc, 1)

    def test_onboard_no_interactive_uses_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cv = td / "cv.txt"
            cv.write_text("Experienced in Python.", encoding="utf-8")
            out = td / "profile.yaml"
            rc = onboard_mod.main(["--cv", str(cv), "--out", str(out), "--no-interactive"])
            self.assertEqual(rc, 0)
            content = out.read_text(encoding="utf-8")
            self.assertIn("Your city", content)


if __name__ == "__main__":
    unittest.main()
