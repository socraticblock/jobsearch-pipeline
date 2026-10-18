"""I-24 -- the location-scope regex pin.

`EU_SCOPE` and `WORLD_OK` in
`jobsearch/rules.py` are the
regex-based location detectors
that complement `EU_COUNTRIES`
(set of 28 country names) and
`NON_EU_BLOCK` (set of 17
non-EU country names). Where
`EU_COUNTRIES` / `NON_EU_BLOCK`
detect *country names*, the
regexes detect *scope
descriptions* like "EU",
"EMEA", "worldwide", "anywhere",
"global".

A contributor who removed
"emea" from `EU_SCOPE` would
silently miss EMEA-marketed
jobs (the gate would treat
them as not-EU-scope, falling
through to `non_eu_block`
checks -- a false positive).
A contributor who removed
"anywhere" from `WORLD_OK`
would silently miss "remote
from anywhere" jobs (the
gate would treat them as
not-world-ok, falling through
to NON_EU_BLOCK -- a false
negative that could be a
NEEDS_RESEARCH when the job
is actually open to
anywhere).

The location-scope resolution
order is:
1. place in `local_ok` ->
   satisfied (own market)
2. `reside_in` -> uncertain
   (an EOR or relocation route
   may exist)
3. `WORLD_OK` matches ->
   satisfied (remote from
   anywhere)
4. the profile's declared
   `work_authorisation` covers
   the place -> satisfied
5. EU scope / `EU_COUNTRIES`:
   satisfied if the profile
   declared an EU-wide scope,
   otherwise a drop (a declared
   scope that excludes it) or
   uncertain (nothing declared)
6. place in `NON_EU_BLOCK`:
   drop when a declared scope
   excludes it, uncertain when
   nothing is declared
7. else -> uncertain
   (NEEDS_RESEARCH)

Nothing in this order reads a
citizenship, a residence, or a
country name out of the profile
prose: a work authorisation is
only ever what the candidate
declared. A contributor who
removed "emea" from `EU_SCOPE`
would silently miss EMEA-marketed
jobs (the gate would treat them as
not-EU-scope, falling through to
`non_eu_block` checks -- a false
positive). A contributor who
removed "anywhere" from `WORLD_OK`
would silently miss "remote from
anywhere" jobs (the gate would
treat them as not-world-ok,
falling through to NON_EU_BLOCK --
a false negative that could be a
NEEDS_RESEARCH when the job is
actually open to anywhere).

A drift in the regexes would
silently shift jobs between
these branches. The
`TestLocationSets` class
pins the country sets; this
class pins the regexes. The
direct matching is the same
pattern as the polarity
regexes (turn N-2): for
each documented entry, build
a sentence and assert the
regex matches it.

The fix is a new
`TestLocationScopeRegexes`
class with 3 tests:
1. `test_eu_scope_matches_documented_stems`:
   every documented stem
   matches the regex in a
   sentence.
2. `test_world_ok_matches_documented_stems`:
   every documented stem
   matches the regex in a
   sentence.
3. `test_eu_scope_does_not_match_world_ok_stems`:
   the two regexes do not
   overlap (a job saying
   "worldwide" should not
   also satisfy EU_SCOPE).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch.rules import EU_SCOPE, WORLD_OK  # noqa: E402


# Documented stems (lowercased; the
# regexes are case-insensitive).
# Removing any entry would silently
# miss jobs that use that scope
# description.
EU_SCOPE_EXPECTED_STEMS = [
    "eu", "europe", "european union", "emea",
]

WORLD_OK_EXPECTED_STEMS = [
    "worldwide", "anywhere", "global",
]


class TestLocationScopeRegexes(unittest.TestCase):
    """The location-scope regexes
    (`EU_SCOPE`, `WORLD_OK`) in
    `jobsearch/rules.py` are the
    regex-based location
    detectors that complement
    `EU_COUNTRIES` /
    `NON_EU_BLOCK`. They detect
    *scope descriptions*, not
    country names.
    """

    def test_eu_scope_matches_documented_stems(self) -> None:
        """`EU_SCOPE` must match
        every documented stem
        in a sentence.

        The regex is case-insensitive
        (it uses `re.I`), so the
        test lowercases the stem
        for direct matching.
        """
        for stem in EU_SCOPE_EXPECTED_STEMS:
            with self.subTest(stem=stem):
                sentence = (
                    f"this role is open to "
                    f"candidates across the {stem}"
                )
                self.assertIsNotNone(
                    EU_SCOPE.search(sentence),
                    f"EU_SCOPE did NOT match "
                    f"the documented stem "
                    f"{stem!r} in the sentence "
                    f"{sentence!r}. A job "
                    f"advertising {stem!r} as "
                    f"the location scope would "
                    f"silently fall through to "
                    f"the NON_EU_BLOCK check "
                    f"(false positive -- a job "
                    f"that should be marked "
                    f"'satisfied' would be "
                    f"marked 'uncertain' or "
                    f"'failed'). If the stem "
                    f"was intentionally removed, "
                    f"update "
                    f"EU_SCOPE_EXPECTED_STEMS "
                    f"in the same commit."
                )

    def test_world_ok_matches_documented_stems(self) -> None:
        """`WORLD_OK` must match
        every documented stem
        in a sentence.
        """
        for stem in WORLD_OK_EXPECTED_STEMS:
            with self.subTest(stem=stem):
                sentence = (
                    f"this is a {stem} remote "
                    f"position open to candidates "
                    f"in any country"
                )
                self.assertIsNotNone(
                    WORLD_OK.search(sentence),
                    f"WORLD_OK did NOT match "
                    f"the documented stem "
                    f"{stem!r} in the sentence "
                    f"{sentence!r}. A job "
                    f"advertising {stem!r} as "
                    f"the location scope would "
                    f"silently fall through to "
                    f"the NON_EU_BLOCK check "
                    f"(false negative -- a job "
                    f"that should be marked "
                    f"'satisfied' would be "
                    f"marked 'uncertain' or "
                    f"'failed'). If the stem "
                    f"was intentionally removed, "
                    f"update "
                    f"WORLD_OK_EXPECTED_STEMS "
                    f"in the same commit."
                )

    def test_eu_scope_does_not_match_world_ok_stems(self) -> None:
        """`EU_SCOPE` and
        `WORLD_OK` must not
        overlap: a job saying
        "worldwide" should not
        also satisfy `EU_SCOPE`,
        and a job saying "EU"
        should not also satisfy
        `WORLD_OK`. The branches
        are mutually exclusive:
        the first match wins.
        """
        for stem in WORLD_OK_EXPECTED_STEMS:
            with self.subTest(stem=stem):
                sentence = (
                    f"this is a {stem} remote "
                    f"position"
                )
                self.assertIsNone(
                    EU_SCOPE.search(sentence),
                    f"EU_SCOPE matched a "
                    f"WORLD_OK stem {stem!r} "
                    f"in the sentence "
                    f"{sentence!r}. The two "
                    f"regexes overlap, which "
                    f"means the location-scope "
                    f"resolution order "
                    f"(EU_SCOPE -> WORLD_OK "
                    f"-> NON_EU_BLOCK -> "
                    f"uncertain) cannot "
                    f"work as designed. The "
                    f"first matching regex "
                    f"wins, but a job that "
                    f"should be classified as "
                    f"'worldwide' would be "
                    f"classified as 'EU' "
                    f"instead -- a silent "
                    f"misclassification that "
                    f"affects the W3.1 "
                    f"honesty contract (the "
                    f"gate must say what it "
                    f"actually decided)."
                )
        for stem in EU_SCOPE_EXPECTED_STEMS:
            with self.subTest(stem=stem):
                sentence = (
                    f"this role is open to "
                    f"candidates across the {stem}"
                )
                self.assertIsNone(
                    WORLD_OK.search(sentence),
                    f"WORLD_OK matched an "
                    f"EU_SCOPE stem {stem!r} "
                    f"in the sentence "
                    f"{sentence!r}. The two "
                    f"regexes overlap, which "
                    f"means the location-scope "
                    f"resolution order "
                    f"cannot work as designed."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
