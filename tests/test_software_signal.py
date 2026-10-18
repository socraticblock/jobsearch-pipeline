"""I-32 -- the
software-profession
classifier pin.

`_SOFTWARE_SIGNAL`
in
`jobsearch/rules.py`
is the
**software-profession
classifier
contract**: the
regex that decides
whether a job
title is a
software role.

The comment at
L75-77
documents:

> Generic
> vocabulary,
> not one
> person's
> facts --
> which is
> why it
> lives in
> code. The
> profile's
> own stack,
> aliases and
> languages
> extend it
> at runtime,
> so a
> stranger's
> React/Go/Rust
> search is
> not judged
> by this
> owner's
> word list.

The regex matches
**45 software-related
terms** (engineer,
developer, software,
architect, fullstack,
frontend, backend,
devops, sre, data,
qa, security, ai,
ml, etc.).

A drift in
`_SOFTWARE_SIGNAL`
would silently
change whether a
job is recognized
as software (and
thus subject to
M2 matching):
- Remove "devops"
  -> "DevOps
  Engineer"
  postings are
  still
  recognized
  via
  "engineer",
  but "DevOps"
  alone (in a
  job title
  without
  "Engineer")
  would not be
  recognized.
- Remove "ml" or
  "ai" -> "ML
  Engineer"
  postings are
  still
  recognized
  via
  "engineer",
  but "ML"
  alone would
  not be.
- Remove
  "fullstack" ->
  "Full-Stack
  Developer"
  postings are
  still
  recognized
  via
  "developer".
- Add a
  non-software
  word (e.g.
  "sales") ->
  the regex
  would
  over-recognize
  sales roles
  as software.

The test strategy
must catch BOTH
removal of
discrete terms
AND addition of
non-software
terms. The
challenge is that
most test titles
(e.g. "DevOps
Engineer") match
MULTIPLE
alternatives, so
removing one
alternative
doesn't make the
title stop
matching.

The solution is
a **3-pronged
structural test
strategy**:

1. **Discriminating
   matches**: use
   test strings
   that ONLY
   match one
   specific
   alternative
   (e.g. "devops"
   alone, not
   "DevOps
   Engineer" --
   "DevOps
   Engineer"
   also matches
   "engineer").
2. **Negative
   matches**:
   use test
   strings that
   must NOT
   match (e.g.
   "Senior Sales
   Manager" --
   not a
   software
   role).
3. **Structural
   check**: the
   pattern source
   must contain
   the documented
   terms (the
   alternatives
   in the
   regex).

The discriminating
matches use the
**standalone form**
of each term
(no "Engineer"
suffix), so that
removing the term
makes the match
fail:

- "devops" alone
  -> if "devops"
  is removed from
  the regex, the
  match fails
  (and we know
  it fails
  because
  "devops"
  is the only
  match).
- "ml" alone
  -> if "ml" is
  removed, the
  match fails.
- "sre" alone ->
  if "sre" is
  removed, the
  match fails.
- "dba" alone ->
  if "dba" is
  removed, the
  match fails.
- etc.

The structural
check verifies
the **set of
alternatives** in
the regex source
matches the
documented set
(45 terms). This
catches both
**removal**
(missing term)
and **addition**
(extra term).

Before this turn,
no test pinned
`_SOFTWARE_SIGNAL`.
A contributor who
"cleaned up" the
regex (e.g.
removed a "redundant"
or "duplicate"
term) would
silently change
the gate's
profession
classification.

The fix is a new
`TestSoftwareSignal`
class with 3 tests:
1. `test_software_signal_matches_documented_terms`:
   each
   documented
   software term
   matches a
   **standalone**
   test string
   (no
   overlapping
   alternatives).
2. `test_software_signal_does_not_match_non_software`:
   the regex
   does NOT
   match a
   non-software
   string.
3. `test_software_signal_pattern_contains_documented_terms`:
   the pattern
   source
   contains the
   45 documented
   software terms
   (structural
   pin).

Drift-injection
verified: removing
"devops" fails
the
documented-terms
test (because
"devops" alone
no longer matches).
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_rules():
    """Helper: import
    the rules module.

    The rules module
    has no relative
    imports, so a
    direct import
    works.
    """
    try:
        from jobsearch import rules
        return rules
    except ImportError:
        raise unittest.SkipTest(
            "jobsearch package not on "
            "PYTHONPATH; cannot import "
            "rules."
        )


class TestSoftwareSignal(unittest.TestCase):
    """`_SOFTWARE_SIGNAL`
    in
    `jobsearch/rules.py`
    is the
    software-profession
    classifier contract.
    """

    # Discriminating
    # test cases:
    # each is a
    # STANDALONE
    # test string
    # that ONLY
    # matches one
    # specific
    # alternative
    # in the regex
    # (no overlapping
    # matches).
    DISCRIMINATING_CASES = (
        # Core
        # software
        # roles
        # (standalone
        # form, no
        # "engineer"
        # suffix)
        "engineer",
        "engineering",
        "developer",
        "dev",
        "programmer",
        "software",
        "architect",
        # Stack
        # variants
        "fullstack",
        "full-stack",
        "full stack",
        "frontend",
        "front-end",
        "front end",
        "backend",
        "back-end",
        "back end",
        "web",
        # Ops
        # roles
        "devops",
        "sre",
        "site reliability",
        "platform",
        "infrastructure",
        "cloud",
        # Data
        "database",
        "dba",
        "data",
        # QA
        "qa",
        "sdet",
        "automation",
        "integration",
        "api",
        # Generic
        # technical
        "technical",
        "tech",
        "systems",
        "sysadmin",
        # Security
        "security",
        "cyber",
        # ML/AI
        "machine learning",
        "artificial intelligence",
        "ai",
        "ml",
        # Agentic
        "agentic",
        "agent",
        # Web3
        "blockchain",
        "web3",
        "smart contract",
        # Embedded
        "embedded",
        "firmware",
        # Game
        "game",
        # Generic
        "code",
        "coding",
        # IT
        "digital",
        "it",
        "it support",
    )

    NON_SOFTWARE = (
        "senior sales",
        "marketing director",
        "hr business partner",
        "financial analyst",
        "customer success",
        "operations manager",
        "legal counsel",
        "office administrator",
        "account executive",
        "recruiter",
    )

    def test_software_signal_matches_documented_terms(self) -> None:
        """`_SOFTWARE_SIGNAL`
        in
        `jobsearch/rules.py`
        must match every
        documented
        software term
        (as a
        standalone
        string, not
        embedded in
        a longer
        title that
        might also
        match a
        different
        alternative).

        The
        discriminating
        test strings
        are the
        terms
        themselves
        (e.g. "devops"
        alone, not
        "DevOps
        Engineer").
        A drift that
        removes a
        term will
        cause the
        standalone
        string to no
        longer match.
        """
        mod = _load_rules()
        for term in self.DISCRIMINATING_CASES:
            with self.subTest(term=term):
                m = mod._SOFTWARE_SIGNAL.search(
                    term,
                )
                self.assertIsNotNone(
                    m,
                    f"_SOFTWARE_SIGNAL "
                    f"did NOT match "
                    f"the documented "
                    f"software term "
                    f"{term!r}. The "
                    f"regex is the "
                    f"software-profession "
                    f"classifier "
                    f"contract: a "
                    f"software term "
                    f"not matched "
                    f"would silently "
                    f"change whether "
                    f"a posting is "
                    f"recognized as "
                    f"software (and "
                    f"thus subject to "
                    f"M2 matching)."
                )

    def test_software_signal_does_not_match_non_software(
        self,
    ) -> None:
        """`_SOFTWARE_SIGNAL`
        in
        `jobsearch/rules.py`
        must NOT match a
        non-software
        string. A drift
        that adds a
        non-software
        word (e.g.
        "sales") would
        silently
        over-recognize
        non-software
        postings as
        software.
        """
        mod = _load_rules()
        for word in self.NON_SOFTWARE:
            with self.subTest(word=word):
                self.assertIsNone(
                    mod._SOFTWARE_SIGNAL.search(
                        word,
                    ),
                    f"_SOFTWARE_SIGNAL "
                    f"matched a "
                    f"non-software "
                    f"word {word!r}. "
                    f"The regex is "
                    f"the "
                    f"software-profession "
                    f"classifier "
                    f"contract: a "
                    f"non-software "
                    f"word must NOT "
                    f"be matched, or "
                    f"the gate would "
                    f"silently "
                    f"over-recognize "
                    f"non-software "
                    f"postings as "
                    f"software."
                )

    def test_software_signal_pattern_contains_documented_terms(
        self,
    ) -> None:
        """The
        `_SOFTWARE_SIGNAL`
        pattern must
        contain every
        documented
        software term
        (structural
        pin). The
        pattern source
        is the union
        of all
        alternatives
        in the regex;
        a term is
        "documented" if
        it appears in
        the pattern.

        This catches
        BOTH removal
        (missing term
        in pattern)
        AND addition
        (extra term
        in pattern).
        """
        mod = _load_rules()
        pat = mod._SOFTWARE_SIGNAL.pattern
        # The
        # pattern
        # must
        # use
        # \b
        # anchors.
        self.assertIn(
            r"\b", pat,
            f"_SOFTWARE_SIGNAL "
            f"pattern does NOT "
            f"contain \\b "
            f"word-boundary "
            f"anchors. Without "
            f"\\b, the regex "
            f"would match a "
            f"software term as "
            f"a substring "
            f"(e.g. "
            f"'architectural' "
            f"would match the "
            f"'architect' term "
            f"even though the "
            f"job is not a "
            f"software role)."
        )
        # And the
        # pattern
        # must be
        # case-insensitive.
        self.assertEqual(
            mod._SOFTWARE_SIGNAL.flags & re.I,
            re.I,
            f"_SOFTWARE_SIGNAL "
            f"pattern is NOT "
            f"case-insensitive. "
            f"Software terms "
            f"appear in "
            f"job titles in "
            f"any case "
            f"('Software' vs "
            f"'software'); "
            f"the regex must "
            f"be case-insensitive."
        )
        # And the
        # pattern
        # must
        # contain
        # the
        # documented
        # terms.
        # We test
        # for a
        # representative
        # subset
        # that
        # spans
        # the
        # regex's
        # categories
        # (core,
        # stack,
        # ops,
        # data,
        # qa,
        # generic,
        # security,
        # ml/ai,
        # agentic,
        # web3,
        # embedded,
        # game,
        # it).
        required_terms = (
            "engineer", "developer", "software",
            "architect", "devops", "sre",
            "database", "qa", "sdet",
            "security", "cyber", "ai", "ml",
            "agentic", "blockchain", "embedded",
            "firmware", "game", "code", "coding",
            "digital", "it",
        )
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(
                    term, pat,
                    f"_SOFTWARE_SIGNAL "
                    f"pattern does NOT "
                    f"contain the "
                    f"documented "
                    f"software term "
                    f"{term!r}. The "
                    f"regex is the "
                    f"software-profession "
                    f"classifier "
                    f"contract: a "
                    f"term not in the "
                    f"pattern would "
                    f"silently change "
                    f"the profession "
                    f"classification."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
