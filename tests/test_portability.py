"""Portability tests: the pipeline must work for someone who is not its author.

Run:  python3 -m unittest discover -s tests -v
      python3 -O -m unittest discover -s tests      # must behave IDENTICALLY

These tests exist because "someone else can copy and use this" is a claim, and a
claim needs evidence. They cover the four ways a copy silently does not work for
its new owner:

  1. Their stack is outside the built-in vocabulary, so their own skills never
     match anything and every posting looks unknown.
  2. Their profile lives somewhere other than this checkout.
  3. No profile at all -- which must be LOUD, not silently "no skills held".
  4. The shipped template rots: a field renamed in code but not in the example.

unittest assertion methods only, never bare `assert` (see tests/test_m1.py).
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import notify                                         # noqa: E402
from jobsearch.requirements import LANGUAGES, TECHNOLOGIES, JobPosting  # noqa: E402
from jobsearch.rules import load_rules, evaluate                     # noqa: E402

EXAMPLE = ROOT / "profile" / "profile.example.yaml"

# Identifiers that must never appear in anything intended to be shared. Kept
# deliberately narrow: words that are personal here but might legitimately
# appear in a stranger's profile (e.g. a city) are not in this list.
# The real values live in `scripts/export_bundle.py` DENY_TOKENS (excluded
# from the public bundle); we derive the marker strings at test time so
# the test source itself contains no personal values.
def _personal_markers() -> tuple[str, ...]:
    import sys
    from pathlib import Path as _P
    _root = _P(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    if str(_root / "tools") not in sys.path:
        sys.path.insert(0, str(_root / "tools"))
    from export_bundle import DENY_TOKENS
    return tuple(
        p.replace(r"\b", "").replace("\\", "")
        for p in DENY_TOKENS
    )


class TestProfileResolution(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("JOBSEARCH_PROFILE")
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("JOBSEARCH_PROFILE", None)
        else:
            os.environ["JOBSEARCH_PROFILE"] = self._saved
        self._tmp.cleanup()

    def test_explicit_argument_wins(self):
        p = self.tmp / "explicit.yaml"
        p.write_text("compensation:\n  floor: '1234 EUR'\n", encoding="utf-8")
        rules = load_rules(p)
        self.assertEqual(rules.floor_net, 1234.0)
        self.assertEqual(rules.profile_path, str(p))

    def test_env_var_is_honoured(self):
        p = self.tmp / "env.yaml"
        p.write_text("compensation:\n  floor: '2222 EUR'\n", encoding="utf-8")
        os.environ["JOBSEARCH_PROFILE"] = str(p)
        rules = load_rules()
        self.assertEqual(rules.floor_net, 2222.0)
        self.assertEqual(rules.profile_path, str(p))

    def test_explicit_argument_beats_the_env_var(self):
        env_p = self.tmp / "env.yaml"
        env_p.write_text("compensation:\n  floor: '1111 EUR'\n", encoding="utf-8")
        arg_p = self.tmp / "arg.yaml"
        arg_p.write_text("compensation:\n  floor: '3333 EUR'\n", encoding="utf-8")
        os.environ["JOBSEARCH_PROFILE"] = str(env_p)
        self.assertEqual(load_rules(arg_p).floor_net, 3333.0)

    def test_missing_profile_reports_none_rather_than_pretending(self):
        os.environ["JOBSEARCH_PROFILE"] = str(self.tmp / "does-not-exist.yaml")
        rules = load_rules()
        self.assertIsNone(rules.profile_path)
        self.assertIsNone(rules.floor_net)
        self.assertEqual(rules.known_stack, set())

    def test_missing_profile_is_stated_in_the_digest(self):
        os.environ["JOBSEARCH_PROFILE"] = str(self.tmp / "absent.yaml")
        import sqlite3

        from jobsearch import db as db_mod

        con = db_mod.connect(self.tmp / "jobs.db")
        try:
            text = notify.render_digest(con)
        finally:
            con.close()
        self.assertIn("no candidate profile found", text)
        self.assertIn("profile/profile.example.yaml", text)


class TestVocabularyExtensibility(unittest.TestCase):
    """A stack the original authors never anticipated must still work."""

    def test_stack_outside_the_builtin_vocabulary_is_matched(self):
        self.assertNotIn("elixir", TECHNOLOGIES)
        posting = JobPosting(
            title="Backend Engineer",
            description=(
                "Backend Engineer. You will build services in Elixir and own them "
                "in production. Remote from anywhere."
            ),
            location="Remote (worldwide)",
        )
        rules = load_rules(EXAMPLE)
        # Give the candidate Elixir, as a real profile would.
        rules.known_stack.add("elixir")
        verdict = evaluate(posting, rules)
        held = [s for s in verdict.satisfied if "elixir" in s]
        self.assertEqual(len(held), 1, verdict.satisfied)
        self.assertEqual(verdict.failed_essential, [])

    def test_builtin_vocabulary_still_works(self):
        posting = JobPosting(
            title="Backend Engineer",
            description=(
                "Backend Engineer. We are looking for an engineer to build and "
                "operate our platform services. TypeScript and Node.js required. "
                "Remote from anywhere."
            ),
            location="Remote (worldwide)",
        )
        verdict = evaluate(posting, load_rules(EXAMPLE))
        held = [s for s in verdict.satisfied if "technology held" in s]
        self.assertGreaterEqual(len(held), 2)
        self.assertIn(verdict.outcome, ("strong_match", "potential_match"))

    def test_language_outside_the_builtin_vocabulary_is_matched(self):
        """A candidate whose language is not in LANGUAGES must not be blind."""
        self.assertNotIn("portuguese", LANGUAGES)
        posting = JobPosting(
            title="Backend Engineer",
            description=(
                "Backend Engineer to build platform services. Portuguese required. "
                "TypeScript and Node.js. Remote within the EU."
            ),
            location="Remote (EU)",
        )
        rules = load_rules(EXAMPLE)
        rules.languages_usable = tuple(rules.languages_usable) + ("portuguese",)
        verdict = evaluate(posting, rules)
        self.assertTrue(
            any("portuguese" in s.casefold() for s in verdict.satisfied),
            verdict.satisfied,
        )
        self.assertNotEqual(verdict.outcome, "not_suitable")

    def test_a_technology_word_never_becomes_a_language_requirement(self):
        """Pin shut the trap in extending the language vocabulary.

        If profile stack tokens were fed to the language extractor, a posting
        mentioning TypeScript would raise "typescript" as an unheld LANGUAGE --
        a hard failure -- and the gate would silently drop every such posting.
        """
        posting = JobPosting(
            title="Backend Engineer",
            description=(
                "Backend Engineer to build platform services. TypeScript and "
                "Node.js required. English required. Remote within the EU."
            ),
            location="Remote (EU)",
        )
        verdict = evaluate(posting, load_rules(EXAMPLE))
        lang_failures = [
            f for f in verdict.failed_essential
            if any(t in f.casefold() for t in ("typescript", "node", "react"))
        ]
        self.assertEqual(lang_failures, [], lang_failures)
        self.assertNotEqual(verdict.outcome, "not_suitable")


class TestShippedTemplate(unittest.TestCase):
    """The template is a deliverable, so it is tested like one."""

    def test_example_profile_exists_and_parses(self):
        self.assertTrue(EXAMPLE.is_file())
        import yaml

        data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_template_carries_the_keys_the_gate_reads(self):
        import yaml

        data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("compensation", data)
        self.assertIn("floor", data["compensation"])
        self.assertIn("stack", data)
        self.assertTrue(data["stack"])
        for entry in data["stack"]:
            self.assertIn("skill", entry)
            self.assertIn("status", entry)
        # The status vocabulary the gate understands -- a typo here would make
        # every listed skill silently LEARNABLE instead of held.
        known_statuses = {
            "corroborated", "corroborated_weak", "private_evidence",
            "learning", "aspirational",
        }
        used = {entry["status"] for entry in data["stack"]}
        self.assertTrue(used <= known_statuses, used - known_statuses)

    def test_template_documents_the_hard_rule(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("hard_rule", text)
        self.assertIn("NEVER send an application", text)

    def test_template_contains_no_personal_data(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        found = [m for m in _personal_markers() if m in text]
        self.assertEqual(found, [], f"personal markers in the shared template: {found}")

    def test_template_profile_produces_usable_rules(self):
        rules = load_rules(EXAMPLE)
        self.assertIsNotNone(rules.floor_net)
        self.assertTrue(rules.known_stack)
        self.assertTrue(rules.languages_usable)


class TestSelfDescriptionConsistency(unittest.TestCase):
    def test_example_profile_floor_is_read_from_the_same_field_as_the_real_one(self):
        """Guard against the template documenting a field the code ignores."""
        import yaml

        src = EXAMPLE.read_text(encoding="utf-8")
        # The gate reads compensation.floor; make sure the template's value is
        # actually numeric-extractable, not prose the regex cannot see.
        data = yaml.safe_load(src)
        draft = JobPosting(title="x", description="y")
        self.assertIsInstance(draft.title, str)
        floor = str(data["compensation"]["floor"])
        self.assertIsNotNone(re.search(r"\d", floor))


if __name__ == "__main__":
    unittest.main(verbosity=2)
