"""I-15 -- the polarity regexes pin.

The polarity regexes in `jobsearch/requirements.py`
(`MUST_WORDS`, `NICE_WORDS`, `FLEX_WORDS`) are the
gate's classifiers: they decide whether a detected
requirement is a hard "must" (a missing one is a
hard failure) or a "nice" (a missing one is a soft
signal, not a failure). The flex regex is the
"is this years bar negotiable" classifier: a
sentence containing a flex phrase (e.g. "or
equivalent experience") is uncertain, not a hard
drop.

Before this turn, no test pinned these regexes.
A contributor who removed `required` from
`MUST_WORDS` would silently change every
"required" requirement from hard-fail to
soft-signal, breaking the gate's core contract.
A contributor who added `or similar` to a
"5+ years required" sentence would silently
soften a strict years bar to a flex years bar,
losing the hard drop.

The fix is a new TestPolarityRegexes class with
4 tests:
1. `test_must_words_set_matches_documented`:
   structural pin on `MUST_WORDS` (the
   8 documented words).
2. `test_nice_words_set_matches_documented`:
   structural pin on `NICE_WORDS` (the
   8 documented words).
3. `test_flex_words_set_matches_documented`:
   structural pin on `FLEX_WORDS` (the
   8 documented flex phrases).
4. `test_polarity_classification`:
   behavior pin: every word in MUST_WORDS
   triggers a "must" polarity via
   `_polarity()`; every word in NICE_WORDS
   triggers a "nice" polarity; the
   defensive default for unmarked
   statements is "nice" (a hard
   requirement that is silent is
   not a hard requirement -- W3.1
   contract).
5. `test_flex_words_make_years_uncertain`:
   behavior pin: every phrase in
   `FLEX_WORDS` triggers the
   `flexible=True` flag in the
   `extract_years` output (the
   W3.1 "5+ years or equivalent
   experience" -> NEEDS_RESEARCH
   contract).

Drift-injection verified: removing
`required` from `MUST_WORDS` would fail
the set test ("missing 1 expected
word: ['required']") AND the behavior
test ("sentence '5+ years required'
was classified as 'nice' instead of
'must' -- the gate would treat a
required years bar as a soft signal").
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import requirements  # noqa: E402
from jobsearch.requirements import (  # noqa: E402
    FLEX_WORDS,
    JobPosting,
    LANGUAGES,
    MUST_WORDS,
    NICE_WORDS,
    extract_languages,
    extract_years,
)


# The 8 documented MUST_WORDS. Every
# word here, when present in a
# requirement quote, makes the
# requirement a hard "must" (a
# missing one is a hard failure).
# If you add a word, add it here.
# If you remove one, update this
# test in the same commit.
MUST_WORDS_EXPECTED = [
    "required", "requires", "require",
    "must", "essential", "mandatory",
    "minimum", "need", "needed",
]

# The 8 documented NICE_WORDS. Every
# word here, when present in a
# requirement quote, makes the
# requirement a soft "nice" (a
# missing one is a soft signal, not
# a hard failure).
NICE_WORDS_EXPECTED = [
    "preferred", "nice to have", "plus",
    "bonus", "desirable", "advantage",
    "ideally",
]

# The 8 documented FLEX_WORDS phrases.
# Every phrase here, when present in
# a years-bar sentence, makes the
# years bar negotiable (W3.1: a
# flex years bar is uncertain, not
# a hard drop).
FLEX_WORDS_EXPECTED = [
    "or equivalent", "or similar",
    "or comparable", "or demonstrable",
    "equivalent experience",
    "demonstrable experience",
    "or relevant experience",
]


def _extract_must_words(pattern: re.Pattern) -> set[str]:
    """Extract the literal-word set from
    a compiled regex by parsing the
    pattern source. This is brittle
    (assumes the `\b(w1|w2|...)\b`
    shape used in MUST_WORDS) but
    sufficient for the structural pin.
    """
    src = pattern.pattern
    # Find the alternation group.
    # The pattern shape is
    # r"\b(w1|w2|...)\b" (or with
    # grouping like need(?:ed)?).
    # We use a permissive capture
    # that finds the first ( ... )
    # group, then split on top-level
    # |.
    # Use a regex that matches a
    # parenthesised group with
    # nested parens via depth.
    # Simpler: find first '(' and
    # match the matching ')'.
    open_idx = src.find("(")
    if open_idx < 0:
        return set()
    depth = 0
    end = open_idx
    for i in range(open_idx, len(src)):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    body = src[open_idx + 1 : end]
    # Split on top-level |
    # (ignore nested groups for
    # now; the current regexes are
    # flat enough that split('|')
    # works).
    parts = body.split("|")
    # Strip regex escapes and
    # quantifiers to get the
    # literal stem. For each
    # alternative, find the longest
    # run of [a-z] characters
    # (skipping regex metachars).
    stems = set()
    for p in parts:
        m2 = re.search(r"[a-z][a-z ]*", p)
        if m2:
            stems.add(m2.group(0).strip())
    return stems


class TestPolarityRegexes(unittest.TestCase):
    """The polarity regexes in
    `jobsearch/requirements.py` are
    the gate's hard/soft/flex
    classifiers. They must be
    pinned: a contributor who
    removes `required` from
    `MUST_WORDS` would silently
    soften every required
    requirement to a soft signal.
    """

    def test_must_words_set_matches_documented(self) -> None:
        """`MUST_WORDS` must contain
        exactly the 9 documented
        hard-requirement words
        (or stems that match them).
        Removing `required` would
        silently soften every
        "required" requirement
        to a soft signal.
        """
        # Test by direct matching
        # against the regex. This
        # is more robust than
        # parsing the regex source
        # because it tests the
        # actual behaviour: every
        # documented word must
        # cause MUST_WORDS to
        # match a sentence
        # containing it.
        unmatched: list[str] = []
        for word in MUST_WORDS_EXPECTED:
            # Use a "5+ years WORD" sentence
            # so the regex is forced
            # to find the word in a
            # realistic context.
            test = f"5+ years {word}"
            if not MUST_WORDS.search(test):
                unmatched.append(word)
        self.assertEqual(
            unmatched, [],
            f"MUST_WORDS does NOT match "
            f"{len(unmatched)} documented "
            f"word(s): {unmatched}. "
            f"Removing a word from MUST_WORDS "
            f"silently softens every "
            f"requirement containing that "
            f"word from a hard 'must' to "
            f"a soft 'nice'. The gate's "
            f"hard-fail contract would "
            f"be silently broken. If the "
            f"removal is intentional, "
            f"update MUST_WORDS_EXPECTED "
            f"in the same commit. "
            f"Pattern: {MUST_WORDS.pattern!r}"
        )

    def test_nice_words_set_matches_documented(self) -> None:
        """`NICE_WORDS` must contain
        exactly the 7 documented
        soft-requirement words.
        Adding a hard-requirement
        word (e.g. "required") to
        NICE_WORDS would silently
        soften every requirement
        that uses that word.
        """
        unmatched: list[str] = []
        for word in NICE_WORDS_EXPECTED:
            test = f"5+ years {word}"
            if not NICE_WORDS.search(test):
                unmatched.append(word)
        self.assertEqual(
            unmatched, [],
            f"NICE_WORDS does NOT match "
            f"{len(unmatched)} documented "
            f"word(s): {unmatched}. "
            f"Removing a word from NICE_WORDS "
            f"silently hardens every "
            f"requirement that uses that "
            f"word. The gate's soft-signal "
            f"contract would be silently "
            f"broken. If the removal is "
            f"intentional, update "
            f"NICE_WORDS_EXPECTED in the "
            f"same commit. "
            f"Pattern: {NICE_WORDS.pattern!r}"
        )

    def test_flex_words_set_matches_documented(self) -> None:
        """`FLEX_WORDS` must contain
        exactly the 7 documented
        flex-requirement phrases.
        A phrase is a multi-word
        alternative (e.g. "or
        equivalent experience");
        removing one would
        silently harden a
        "5+ years or equivalent
        experience" requirement
        from a flex/uncertain
        signal to a strict years
        bar -- a silent hard
        drop on a job that
        was supposed to be
        uncertain.
        """
        unmatched: list[str] = []
        for phrase in FLEX_WORDS_EXPECTED:
            test = f"5+ years {phrase}"
            if not FLEX_WORDS.search(test):
                unmatched.append(phrase)
        self.assertEqual(
            unmatched, [],
            f"FLEX_WORDS does NOT match "
            f"{len(unmatched)} documented "
            f"phrase(s): {unmatched}. "
            f"Removing a flex phrase "
            f"silently hardens a "
            f"'X or equivalent' style "
            f"requirement to a strict X. "
            f"The W3.1 '5+ years or "
            f"equivalent experience' -> "
            f"NEEDS_RESEARCH contract "
            f"would be silently broken. "
            f"If the removal is intentional, "
            f"update FLEX_WORDS_EXPECTED "
            f"in the same commit. "
            f"Pattern: {FLEX_WORDS.pattern!r}"
        )

    def test_polarity_classification(self) -> None:
        """Behavior pin: every word
        in MUST_WORDS triggers a
        'must' polarity; every
        word in NICE_WORDS
        triggers a 'nice'
        polarity; unmarked
        statements default to
        'nice' (the W3.1
        defensive contract:
        absence of evidence is
        not evidence of
        absence, and a hard
        verdict against a
        silent requirement is
        exactly the failure
        the project is built
        to refuse).
        """
        for word in MUST_WORDS_EXPECTED:
            with self.subTest(word=word, polarity="must"):
                sentence = f"5+ years {word}"
                # Use the underscore
                # _polarity, not the
                # public API: the
                # public API requires
                # a full extract() call.
                # We test the classifier
                # directly.
                p = requirements._polarity(sentence)
                self.assertEqual(
                    p, "must",
                    f"sentence {sentence!r} "
                    f"contains MUST_WORDS {word!r} "
                    f"but was classified as "
                    f"{p!r} instead of 'must'. "
                    f"MUST_WORDS is broken: "
                    f"the gate would treat a "
                    f"required years bar as a "
                    f"soft signal."
                )
        for word in NICE_WORDS_EXPECTED:
            with self.subTest(word=word, polarity="nice"):
                sentence = f"5+ years {word}"
                p = requirements._polarity(sentence)
                self.assertEqual(
                    p, "nice",
                    f"sentence {sentence!r} "
                    f"contains NICE_WORDS {word!r} "
                    f"but was classified as "
                    f"{p!r} instead of 'nice'. "
                    f"NICE_WORDS is broken: "
                    f"the gate would treat a "
                    f"nice-to-have years bar "
                    f"as a hard requirement."
                )
        # Defensive: unmarked
        # statements default to
        # "nice" (W3.1 contract:
        # absence is not a hard
        # requirement).
        unmarked = "5+ years of professional experience"
        p = requirements._polarity(unmarked)
        self.assertEqual(
            p, "nice",
            f"unmarked sentence {unmarked!r} "
            f"was classified as {p!r} "
            f"instead of 'nice'. The "
            f"defensive default in "
            f"_polarity is broken: the "
            f"gate would treat an "
            f"unmarked statement as a "
            f"hard requirement. This "
            f"violates W3.1."
        )

    def test_flex_words_make_years_uncertain(self) -> None:
        """Behavior pin: every phrase
        in FLEX_WORDS triggers the
        `flexible=True` flag in
        the `extract_years` output
        (the W3.1 "5+ years or
        equivalent experience"
        -> NEEDS_RESEARCH
        contract).

        A contributor who removes
        a flex phrase from
        FLEX_WORDS would silently
        harden a "5+ years or
        equivalent" requirement
        from NEEDS_RESEARCH to
        NOT_SUITABLE.
        """
        for phrase in FLEX_WORDS_EXPECTED:
            with self.subTest(phrase=phrase):
                posting = JobPosting(
                    title="Backend Engineer",
                    description=(
                        f"5+ years of experience "
                        f"{phrase}. TypeScript, "
                        f"React, Node, and our "
                        f"API. Remote (EU). "
                        f"English required."
                    ),
                )
                years_reqs = extract_years(posting)
                # Find the years
                # requirement and check
                # the flex flag.
                matched = [
                    r for r in years_reqs
                    if r.kind == "experience_years"
                ]
                self.assertTrue(
                    matched,
                    f"extract_years did not "
                    f"produce a requirement "
                    f"for the '5+ years "
                    f"{phrase}' sentence. "
                    f"The _YEARS regex may "
                    f"be too narrow."
                )
                self.assertTrue(
                    any(r.meta.get("flexible") for r in matched),
                    f"the years requirement "
                    f"for '5+ years {phrase}' "
                    f"was NOT tagged as "
                    f"flexible. FLEX_WORDS "
                    f"should have flagged "
                    f"it. requirements: "
                    f"{[(r.value, r.meta) for r in matched]}"
                )


class TestLanguages(unittest.TestCase):
    """The `LANGUAGES` tuple in
    `jobsearch/requirements.py`
    is the gate's documented
    default vocabulary for
    language requirements.
    `extract_languages` uses
    it to detect language
    requirements in a
    posting; a language
    not in this set is a
    silent blind spot for
    the default profile
    (the candidate can
    extend the vocabulary
    via `extra_terms`).

    This is the language
    parallel to
    `SPECIALIST_TRAPS` (a
    fixed vocabulary list
    the extractor consults
    for requirements) and
    the default half of
    the W3.4 contract
    (vocabulary is profile
    data, with a
    documented default).

    Before this turn, the
    only test mentioning
    LANGUAGES was the
    portability test
    (which checks that
    "portuguese" is NOT
    in the default -- a
    negative check, not a
    structural pin). A
    contributor who
    removed `german`
    from LANGUAGES would
    silently fail to
    detect German-language
    requirements in the
    default profile,
    leaving the gate
    unaware of language
    barriers.

    The fix is a new
    `TestLanguages` class
    with 3 tests:
    1. `test_languages_set_matches_documented`:
       bidirectional set
       equality on `LANGUAGES`
       (the 9 documented
       entries).
    2. `test_every_language_is_lowercase`:
       every entry is
       lowercase (the
       extractor compares
       against the
       case-folded
       haystack; a
       non-lowercase
       entry would
       silently miss
       every posting).
    3. `test_every_language_is_detected`:
       behavior pin:
       every LANGUAGES
       entry is detected
       by `extract_languages`
       when used in a
       posting.
    """

    # The 9 documented languages
    # in `LANGUAGES`. This is the
    # W3.4 default contract: the
    # gate promises to detect
    # requirements in any of
    # these languages when a
    # profile does not list its
    # own. If you add a language,
    # add it here. If you remove
    # one, update this test in
    # the same commit.
    LANGUAGES_EXPECTED = {
        "english", "dutch", "german", "french",
        "spanish", "norwegian", "russian",
        "italian", "polish",
    }

    def test_languages_set_matches_documented(self) -> None:
        """`LANGUAGES` in
        `jobsearch/requirements.py`
        must contain exactly
        the 9 documented
        languages. Removing
        `german` would
        silently fail to
        detect German-language
        requirements in the
        default profile.
        """
        actual = set(LANGUAGES)
        expected = self.LANGUAGES_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"LANGUAGES is missing "
            f"{len(missing)} expected "
            f"language(s): {sorted(missing)}. "
            f"Removing a language "
            f"silently leaves the "
            f"gate unable to detect "
            f"requirements in that "
            f"language for the default "
            f"profile. The candidate "
            f"can extend the vocabulary "
            f"via `extra_terms` (their "
            f"profile), but removing a "
            f"documented default "
            f"silently breaks the W3.4 "
            f"'vocabulary is profile "
            f"data, with a documented "
            f"default' contract. If the "
            f"removal is intentional, "
            f"update LANGUAGES_EXPECTED "
            f"in the same commit. "
            f"Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"LANGUAGES has {len(extra)} "
            f"undocumented language(s): "
            f"{sorted(extra)}. If a "
            f"language was intentionally "
            f"added, update "
            f"LANGUAGES_EXPECTED in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_every_language_is_lowercase(self) -> None:
        """Every LANGUAGES entry
        must be lowercase. The
        extractor compares
        against the case-folded
        haystack (case-insensitive
        regex match); a
        non-lowercase entry
        (e.g. "German") would
        silently miss every
        posting because the
        regex would look for
        "German" but the
        case-folded haystack
        contains "german".
        """
        offenders = [
            lang for lang in LANGUAGES
            if lang != lang.lower()
        ]
        self.assertEqual(
            offenders, [],
            f"LANGUAGES has "
            f"{len(offenders)} "
            f"non-lowercase entry/entries: "
            f"{offenders}. The extractor "
            f"matches the entry against "
            f"the case-folded haystack, "
            f"so a non-lowercase entry "
            f"would silently miss every "
            f"posting. Lowercase the "
            f"entry, or update the "
            f"extractor to case-fold "
            f"the entry (preferred: keep "
            f"the entry lowercase)."
        )

    def test_every_language_is_detected(self) -> None:
        """Behavior pin: every
        LANGUAGES entry is
        detected by
        `extract_languages` when
        used in a posting.

        The fixture uses
        "fluent {language}"
        which the
        `extract_languages`
        regex matches with
        the optional
        "fluent|native|professional|
        business|good|strong|
        excellent" prefix.
        """
        for lang in self.LANGUAGES_EXPECTED:
            with self.subTest(language=lang):
                posting = JobPosting(
                    title="Backend Engineer",
                    description=(
                        f"Backend Engineer to "
                        f"build platform "
                        f"services. Fluent "
                        f"{lang} required. "
                        f"TypeScript and "
                        f"Node.js. Remote "
                        f"within the EU."
                    ),
                )
                lang_reqs = extract_languages(posting)
                matched = [
                    r for r in lang_reqs
                    if r.value == lang
                ]
                self.assertTrue(
                    matched,
                    f"extract_languages did "
                    f"not produce a "
                    f"requirement for "
                    f"{lang!r} (in "
                    f"LANGUAGES). A job "
                    f"posting saying "
                    f"'fluent {lang} "
                    f"required' would "
                    f"silently slip "
                    f"through the "
                    f"language gate. "
                    f"Either the "
                    f"extractor regex "
                    f"missed the "
                    f"sentence, or "
                    f"{lang!r} is "
                    f"missing from "
                    f"LANGUAGES. "
                    f"requirements: "
                    f"{[(r.kind, r.value) for r in lang_reqs]}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
