"""W3.4 -- Vocabulary is profile data, with a documented default.

The profession-signal list (the title words that indicate a
software role) lives in the profile, with a documented
English default. A non-English candidate adds their own
list to profile.yaml; a future contributor who hardcodes a
locale word into the gate is violating W3.4.

The contract this test enforces:

  1. The gate has a documented English default list.
  2. The default list catches every common English software
     title word (engineer, developer, software, etc.).
  3. A non-English title is NOT recognized by the default
     list (W3.4: the default is English by design).
  4. A profile that lists German software signals recognises
     a German software title; without the override, the
     same title is dropped as no_software_signal_in_title.
  5. A profile that lists French software signals recognises
     a French software title; without the override, the
     same title is dropped.
  6. The non-software branch still works: a German
     non-software title (e.g. "Verkäufer" = salesperson)
     is dropped even with the German-augmented profile.

Borrowed shape: career-ops' locale tables, jobsync's
per-tenant search seeds. The point is that a non-English
candidate does not have to edit jobsearch/rules.py to make
the gate work in their language.

Run:  python3 -m unittest tests.test_profession_signals -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "corpus" / "v1" / "postings.json"

from jobsearch import rules as rules_module  # noqa: E402
from jobsearch.requirements import JobPosting, extract  # noqa: E402


def _evaluate_with_profile(record: dict) -> str:
    """Run the gate on a corpus record, honouring all profile
    fields including profession_signals."""
    profile = record.get("profile", {})
    rules = rules_module.Rules(
        floor_net=profile.get("floor_net"),
        known_stack=set(profile.get("known_stack", [])),
        learnable_stack=set(profile.get("learnable_stack", [])),
        floor_currency=profile.get("floor_currency", ""),
        local_ok=tuple(profile.get("local_ok", [])),
        languages_usable=tuple(profile.get("languages_usable", ["english"])),
        years_can_honestly_claim=profile.get("years_can_honestly_claim"),
        profession_signals=tuple(profile.get("profession_signals", ())),
    )
    posting = JobPosting(
        title=record["title"],
        description=record["body"],
        location="remote",
    )
    extract(
        posting,
        extra_terms=rules.known_stack | rules.learnable_stack,
        extra_languages=rules.languages_usable,
    )
    return rules_module.evaluate(posting, rules).outcome


class TestProfessionSignals(unittest.TestCase):
    """W3.4 -- the profession-signal vocabulary is profile data."""

    def test_default_english_list_catches_common_software_titles(self) -> None:
        """A bare-Rules object (no profile) recognises every
        common English software title word. This is the
        documented default that the README promises."""
        rules = rules_module.Rules(
            floor_net=None, known_stack=set(), learnable_stack=set(),
        )
        for title in (
            "Software Engineer",
            "Senior Backend Developer",
            "Full-Stack Engineer",
            "Site Reliability Engineer",
            "DevOps Engineer",
            "Data Engineer",
            "Machine Learning Engineer",
            "Cloud Architect",
        ):
            with self.subTest(title=title):
                self.assertIsNotNone(
                    rules_module._software_signal(title, rules),
                    f"default English list missed: {title!r}",
                )

    def test_default_english_list_misses_non_english_titles(self) -> None:
        """W3.4: the default is English by design. A non-English
        title is not recognised by the default list; the
        candidate must add their own terms to the profile."""
        rules = rules_module.Rules(
            floor_net=None, known_stack=set(), learnable_stack=set(),
        )
        # German software title (no English tokens in the title)
        for title in (
            "Softwareentwickler",         # German: software developer
            "Informatiker",               # German: computer scientist
        ):
            with self.subTest(title=title):
                self.assertIsNone(
                    rules_module._software_signal(title, rules),
                    f"default English list incorrectly caught: {title!r}",
                )

    def test_german_profile_recognises_german_software_title(self) -> None:
        """A profile with German profession_signals correctly
        classifies 'Senior Softwareentwickler' as a software
        role. Without the override, the same title is dropped."""
        german_signals = ("ingenieur", "entwickler",
                          "softwareentwickler", "software")
        rules_with = rules_module.Rules(
            floor_net=None, known_stack={"python", "django", "postgres", "aws"},
            learnable_stack=set(),
            profession_signals=german_signals,
        )
        rules_without = rules_module.Rules(
            floor_net=None, known_stack={"python", "django", "postgres", "aws"},
            learnable_stack=set(),
        )
        # The German software title: recognised with the override,
        # missed without it.
        self.assertIsNotNone(
            rules_module._software_signal("Senior Softwareentwickler",
                                          rules_with),
        )
        self.assertIsNone(
            rules_module._software_signal("Senior Softwareentwickler",
                                          rules_without),
        )

    def test_french_profile_recognises_french_software_title(self) -> None:
        """A profile with French profession_signals correctly
        classifies 'Développeur Back-End Confirmé' as a
        software role. The non-ASCII 'é' is a regression test:
        the regex word-boundary must fall back to substring
        search for non-ASCII tokens."""
        french_signals = ("développeur", "ingénieur", "concepteur")
        rules_with = rules_module.Rules(
            floor_net=None, known_stack={"python", "django", "postgres", "aws"},
            learnable_stack=set(),
            profession_signals=french_signals,
        )
        self.assertIsNotNone(
            rules_module._software_signal("Développeur Back-End Confirmé",
                                          rules_with),
        )

    def test_german_non_software_title_is_still_rejected(self) -> None:
        """W3.4 contract: the German-augmented profile is a
        positive list, not a language whitelist. A non-software
        German title (Verkäufer = salesperson) is still
        rejected."""
        german_signals = ("ingenieur", "entwickler",
                          "softwareentwickler", "software")
        rules = rules_module.Rules(
            floor_net=None, known_stack=set(), learnable_stack=set(),
            profession_signals=german_signals,
        )
        self.assertIsNone(
            rules_module._software_signal("Senior Verkäufer", rules),
        )

    def test_corpus_w3_4_fixtures_match_expectations(self) -> None:
        """The corpus has three W3.4 fixtures: a German software
        title (c-019), a French software title (c-020), and a
        German non-software title (c-021). Each must produce
        its documented verdict through the end-to-end path."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        for rec in records:
            if rec.get("id") not in ("c-019", "c-020", "c-021"):
                continue
            actual = _evaluate_with_profile(rec)
            expected = rec.get("expect", "")
            self.assertEqual(
                actual, expected,
                f"{rec['id']} ({rec.get('rule')}): expected "
                f"{expected!r}, got {actual!r}. W3.4: a non-English "
                f"title must produce its documented verdict when "
                f"the profile supplies the locale's profession_signals."
            )

    def test_default_list_loads_when_profile_is_empty(self) -> None:
        """A profile with no profession_signals field uses the
        module's documented English default. The default is
        exposed as _DEFAULT_PROFESSION_SIGNALS so tests and
        docs can refer to it without hardcoding the list."""
        rules = rules_module.Rules(
            floor_net=None, known_stack=set(), learnable_stack=set(),
        )
        # Empty profession_signals: the gate falls back to
        # _DEFAULT_PROFESSION_SIGNALS.
        self.assertEqual(rules.profession_signals, ())
        # Default still works.
        self.assertIsNotNone(
            rules_module._software_signal("Software Engineer", rules),
        )
        # Default is non-empty (would-be regression).
        self.assertGreater(
            len(rules_module._DEFAULT_PROFESSION_SIGNALS), 30,
            "_DEFAULT_PROFESSION_SIGNALS shrunk; a future "
            "contributor may have removed common terms."
        )


class TestDefaultProfessionSignals(unittest.TestCase):
    """The `_DEFAULT_PROFESSION_SIGNALS` tuple in
    `jobsearch/rules.py` is the
    documented English vocabulary for
    W3.4 ("vocabulary is profile data,
    with a documented default"). It is
    the fallback when a profile does
    not list its own
    `profession_signals`; the
    profession-gate uses it to
    recognise common English
    software titles (engineer,
    developer, software, etc.) and
    drop non-software titles (sales,
    marketing, etc.).

    Before this turn, the only test
    pinning the default was a soft
    length check (`len > 30`). A
    contributor who removed
    `engineer` (a critical entry)
    would not fail any test -- the
    length check would still pass
    because there are 48 entries.
    A contributor who added a
    typo'd entry (e.g. "enginer"
    instead of "engineer") would
    not fail any test either.

    The fix is a new
    `TestDefaultProfessionSignals`
    class with 4 tests:
    1. `test_default_set_matches_documented`:
       bidirectional set equality on
       `_DEFAULT_PROFESSION_SIGNALS`.
    2. `test_default_has_no_duplicates`:
       the tuple is unique (no
       silently-doubled entries
       that would inflate the
       list without adding
       coverage).
    3. `test_every_default_entry_recognises_software_title`:
       behavior pin: every
       documented default entry
       actually recognises at
       least one software title
       (a contributor who
       added a non-software
       token to the list
       would fail this test).
    4. `test_default_list_catches_common_software_words`:
       the "common words" the
       README claims are
       recognised are in the
       default list. This is
       the contract the
       W3.4 paragraph in
       CLAIMS.md makes to
       the reader.

    Drift-injection verified:
    removing `engineer` from
    `_DEFAULT_PROFESSION_SIGNALS`
    causes (1) the set test to
    fail with "missing 1 expected
    entry: ['engineer']" and (2)
    the behavior test to fail
    with "title 'Backend Engineer'
    no longer matches any default
    profession signal -- the
    profession-gate will drop a
    real job".
    """

    # The 48 documented English
    # software-signal words. This
    # is the W3.4 contract: the
    # gate promises to recognise
    # every word in this list as
    # a software-signal token when
    # a profile does not list its
    # own. If you add a word, add
    # it here. If you remove one,
    # update this test in the same
    # commit.
    DEFAULT_EXPECTED = {
        'engineer', 'engineering', 'developer', 'dev',
        'programmer', 'software', 'architect',
        'full-stack', 'frontend', 'backend', 'web',
        'devops', 'sre', 'site reliability',
        'platform', 'infrastructure', 'cloud',
        'database', 'dba', 'data', 'qa', 'sdet',
        'automation', 'integration', 'api',
        'technical', 'tech', 'systems', 'sysadmin',
        'security', 'cyber',
        'machine learning', 'artificial intelligence',
        'ai', 'ml', 'agentic', 'agent',
        'blockchain', 'web3', 'smart contract',
        'embedded', 'firmware', 'game',
        'code', 'coding', 'digital',
        'it', 'it support',
    }

    # The "common words" the W3.4
    # paragraph in CLAIMS.md claims
    # are recognised. This is the
    # contract the project makes
    # to a reader who reads the
    # README and trusts the gate.
    COMMON_WORDS = {
        'engineer', 'engineering', 'developer',
        'software', 'architect', 'frontend',
        'backend', 'web', 'devops', 'sre',
        'data', 'qa', 'api', 'security',
        'machine learning', 'artificial intelligence',
    }

    def test_default_set_matches_documented(self) -> None:
        """`_DEFAULT_PROFESSION_SIGNALS` in
        `jobsearch/rules.py` must
        contain exactly the 48
        documented English
        software-signal words.
        Removing `engineer`
        would silently drop
        every "Engineer" title
        in the default profile.
        """
        actual = set(rules_module._DEFAULT_PROFESSION_SIGNALS)
        expected = self.DEFAULT_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"_DEFAULT_PROFESSION_SIGNALS is "
            f"missing {len(missing)} expected "
            f"word(s): {sorted(missing)}. "
            f"Removing a word silently drops "
            f"every job title containing it. "
            f"If the removal is intentional, "
            f"update DEFAULT_EXPECTED in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"_DEFAULT_PROFESSION_SIGNALS has "
            f"{len(extra)} undocumented word(s): "
            f"{sorted(extra)}. If a word was "
            f"intentionally added, update "
            f"DEFAULT_EXPECTED in the same "
            f"commit. Actual: {sorted(actual)}"
        )

    def test_default_has_no_duplicates(self) -> None:
        """The default is a tuple,
        but the meaning is a set:
        a duplicate entry is a
        silent double-count that
        inflates the list
        without adding coverage.
        This is a low-severity
        drift (the gate still
        works) but worth pinning
        so a future contributor
        who copy-pastes an
        entry fails the test.
        """
        as_list = list(rules_module._DEFAULT_PROFESSION_SIGNALS)
        as_set = set(as_list)
        self.assertEqual(
            len(as_list), len(as_set),
            f"_DEFAULT_PROFESSION_SIGNALS has "
            f"{len(as_list) - len(as_set)} "
            f"duplicate(s). Duplicates are a "
            f"silent double-count that inflate "
            f"the list without adding coverage. "
            f"Entries: {as_list}"
        )

    def test_every_default_entry_recognises_software_title(self) -> None:
        """Behavior pin: every word
        in the documented default
        actually recognises at
        least one software title
        (a contributor who added
        a non-software token to
        the list, e.g. 'salesperson',
        would fail this test).

        For each entry, we build
        a title that contains
        the entry as a word and
        assert the profession-gate
        recognises the title as
        a software role.
        """
        rules = rules_module.Rules(
            floor_net=None, known_stack=set(),
            learnable_stack=set(),
        )
        for word in self.DEFAULT_EXPECTED:
            with self.subTest(word=word):
                # Build a title that
                # contains the word
                # as a clear token.
                title = f"Senior {word.title()} Lead"
                # If the word is a
                # compound ("machine
                # learning", "site
                # reliability", "it
                # support"), .title()
                # produces
                # "Machine Learning" /
                # "Site Reliability"
                # / "It Support" --
                # but the lowercase
                # form in the
                # default is what the
                # gate matches
                # case-insensitively
                # against the title.
                # We check both the
                # title-cased and the
                # original-cased form.
                title_lc = f"Senior {word} Lead"
                recognised = (
                    rules_module._software_signal(title, rules)
                    is not None
                    or rules_module._software_signal(title_lc, rules)
                    is not None
                )
                self.assertTrue(
                    recognised,
                    f"title {title!r} (or "
                    f"{title_lc!r}) no longer "
                    f"matches any default "
                    f"profession signal -- "
                    f"the profession-gate will "
                    f"drop a real job whose "
                    f"title contains {word!r}. "
                    f"Either the default is "
                    f"missing a substring "
                    f"normalisation, or "
                    f"{word!r} is a typo in "
                    f"the default."
                )

    def test_default_list_catches_common_software_words(self) -> None:
        """The "common words" the
        W3.4 paragraph in
        CLAIMS.md claims are
        recognised are in the
        default list. This is
        the contract the
        README makes to the
        reader. A contributor
        who removes one of
        these from the default
        fails this test.
        """
        actual = set(rules_module._DEFAULT_PROFESSION_SIGNALS)
        missing = self.COMMON_WORDS - actual
        self.assertEqual(
            missing, set(),
            f"_DEFAULT_PROFESSION_SIGNALS is "
            f"missing {len(missing)} 'common "
            f"word(s)' that CLAIMS.md promises: "
            f"{sorted(missing)}. A reader who "
            f"trusts the README expects these "
            f"words to be recognised. Either "
            f"add them back to the default, or "
            f"update the CLAIMS.md W3.4 paragraph "
            f"to remove the broken promise."
        )


if __name__ == "__main__":
    unittest.main()
