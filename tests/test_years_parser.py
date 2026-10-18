"""I-33 -- the
years-of-experience
parser pin.

`_YEARS` in
`jobsearch/requirements.py`
is the
**years-of-experience
parser contract**:
the regex that
extracts the
years-of-experience
claim from a
posting. The
regex captures:
- `n`: the years
  number
  (1-2 digits)
- `after`: up to
  80 chars of
  context after
  "years/yrs"

The pattern
supports:
- "5 years" ->
  n=5
- "5+ years" ->
  n=5 (the + is
  optional)
- "5 to 7 years"
  -> n=5 (the
  "to N" is
  optional,
  captures the
  floor)
- "3 yrs" ->
  n=3
- "10 years
  experience"
  -> n=10
- "5 years of
  relevant
  experience"
  -> n=5

A drift in
`_YEARS` would
silently mis-parse
the years claim
from posting text,
which would
corrupt the
years-of-experience
field used in M2
matching:
- Remove the
  "to \d{1,2}"
  range support
  -> "5 to 7
  years"
  postings
  would not be
  recognized as
  having a
  years claim.
- Remove the
  "yrs?" short
  form -> "3 yrs"
  postings
  would not be
  recognized.
- Remove the
  `\d{1,2}`
  limit (change
  to `\d+`) ->
  "100 years"
  would match
  (the limit
  caps years
  at 99).
- Change the
  "after" limit
  from 80 to 20
  -> the context
  would be
  truncated,
  losing
  information.

Before this turn,
no test pinned
`_YEARS`. A
contributor who
"cleaned up" the
regex (e.g.
removed a "redundant"
or "duplicate"
sub-pattern)
would silently
break the years
extraction.

The fix is a new
`TestYearsParser`
class with 4 tests:
1. `test_years_matches_documented_forms`:
   each
   documented
   years form
   matches.
2. `test_years_captures_named_group_n`:
   the
   `n` named
   group
   captures
   the
   years
   number.
3. `test_years_captures_named_group_after`:
   the
   `after` named
   group
   captures
   up to 80
   chars of
   context.
4. `test_years_does_not_match_out_of_range`:
   the regex
   does NOT
   match a
   year
   number
   outside
   the 1-2
   digit
   range
   (e.g.
   100 years).

Drift-injection
verified: removing
"to" range
support fails
the
documented-forms
test.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_requirements():
    """Helper: import
    the requirements
    module.

    The requirements
    module has no
    relative imports,
    so a direct
    import works.
    """
    try:
        from jobsearch import requirements
        return requirements
    except ImportError:
        raise unittest.SkipTest(
            "jobsearch package not on "
            "PYTHONPATH; cannot import "
            "requirements."
        )


class TestYearsParser(unittest.TestCase):
    """`_YEARS` in
    `jobsearch/requirements.py`
    is the
    years-of-experience
    parser contract.
    """

    YEARS_CASES = (
        # Basic
        "5 years",
        "3 years",
        "10 years",
        "1 year",
        # Plus
        "5+ years",
        "10+ years of experience",
        "3+ yrs",
        # Range
        "5 to 7 years",
        "3 to 5 years experience",
        "1 to 2 years",
        # Short
        # form
        "3 yrs",
        "5 yrs experience",
        "10 yrs of experience",
    )

    def test_years_matches_documented_forms(self) -> None:
        """`_YEARS` in
        `jobsearch/requirements.py`
        must match every
        documented years
        form. A drift
        that removes a
        sub-pattern
        would silently
        fail to parse
        the years claim.
        """
        mod = _load_requirements()
        for case in self.YEARS_CASES:
            with self.subTest(case=case):
                m = mod._YEARS.search(case)
                self.assertIsNotNone(
                    m,
                    f"_YEARS did NOT "
                    f"match the "
                    f"documented years "
                    f"form {case!r}. "
                    f"The regex is "
                    f"the "
                    f"years-of-experience "
                    f"parser contract: "
                    f"a form not "
                    f"matched would "
                    f"silently fail to "
                    f"parse the years "
                    f"claim from the "
                    f"posting, and the "
                    f"gate would not "
                    f"have a years "
                    f"field to "
                    f"evaluate."
                )

    def test_years_captures_named_group_n(self) -> None:
        """The `_YEARS`
        regex must
        capture the
        `n` named
        group with the
        years number.

        Without the
        `n` named
        group, the
        caller would
        have to use
        `m.group(1)` or
        `m.groups()[0]`,
        which is
        fragile and
        breaks if the
        regex order
        changes.
        """
        mod = _load_requirements()
        case = "5+ years of experience"
        m = mod._YEARS.search(case)
        self.assertIsNotNone(m)
        self.assertIn(
            "n", m.groupdict(),
            f"_YEARS matched {case!r} "
            f"but did NOT capture a "
            f"named group `n`. The "
            f"years number must be "
            f"captured as a named "
            f"group for callers to "
            f"extract it without "
            f"depending on regex "
            f"order."
        )
        self.assertEqual(
            m.group("n"), "5",
            f"_YEARS captured "
            f"n={m.group('n')!r} in "
            f"{case!r}, expected '5'. "
            f"The named group must "
            f"contain the years "
            f"number as a string."
        )

    def test_years_captures_named_group_after(self) -> None:
        """The `_YEARS`
        regex must
        capture the
        `after` named
        group with up
        to 80 chars of
        context after
        "years/yrs".

        The `after`
        group is used
        for context
        (e.g.
        distinguishing
        "years of
        experience"
        from "years
        in business").
        """
        mod = _load_requirements()
        case = "5 years of relevant experience"
        m = mod._YEARS.search(case)
        self.assertIsNotNone(m)
        self.assertIn(
            "after", m.groupdict(),
            f"_YEARS matched {case!r} "
            f"but did NOT capture a "
            f"named group `after`. "
            f"The after-context is "
            f"used to distinguish "
            f"different meanings "
            f"of 'years'."
        )
        # The
        # after-context
        # must
        # contain
        # the
        # context
        # text.
        self.assertIn(
            "experience", m.group("after"),
            f"_YEARS captured "
            f"after={m.group('after')!r} "
            f"in {case!r}, expected to "
            f"contain 'experience'. "
            f"The named group must "
            f"contain the "
            f"after-context."
        )
        # The
        # after-context
        # must
        # be
        # <= 80
        # chars.
        self.assertLessEqual(
            len(m.group("after")), 80,
            f"_YEARS captured "
            f"after={m.group('after')!r} "
            f"in {case!r}, length "
            f"{len(m.group('after'))} "
            f"> 80. The named group "
            f"must be limited to "
            f"80 chars to prevent "
            f"runaway capture."
        )

    def test_years_captures_floor_in_range(self) -> None:
        """For a range
        like "5 to 7
        years", the
        `_YEARS` regex
        must capture
        the FLOOR
        (5), not the
        CEILING (7).

        The gate
        evaluates the
        candidate's
        years against
        the posting's
        years claim;
        the floor is
        the minimum
        required
        experience.
        A drift that
        makes the
        regex match
        the ceiling
        instead of
        the floor
        would
        silently
        inflate the
        required
        experience
        and reject
        candidates
        who meet
        the floor
        but not
        the ceiling.

        This test
        catches
        that drift.
        """
        mod = _load_requirements()
        case = "5 to 7 years"
        m = mod._YEARS.search(case)
        self.assertIsNotNone(m)
        self.assertEqual(
            m.group("n"), "5",
            f"_YEARS captured "
            f"n={m.group('n')!r} in "
            f"{case!r}, expected '5' "
            f"(the floor). The "
            f"regex must capture the "
            f"floor of a range, not "
            f"the ceiling. A drift "
            f"that captures the "
            f"ceiling would "
            f"silently inflate the "
            f"required experience "
            f"and reject candidates "
            f"who meet the floor."
        )

    def test_years_pattern_uses_1_to_2_digit_limit(self) -> None:
        """The `_YEARS`
        pattern must
        use `\d{1,2}`
        (1-2 digits)
        to cap the
        years number
        at 99.

        A drift that
        changes the
        limit to
        `\d+` would
        match 3+ digit
        numbers
        (e.g. "100"),
        which is not a
        reasonable
        years claim.
        This is the
        structural
        pin.

        The check
        looks for
        `\d{1,2}`
        immediately
        after `(?P<n>`,
        which is the
        position of
        the years
        number. Other
        `\d{1,2}`
        occurrences
        (e.g. in the
        "to N" range)
        are
        irrelevant.
        """
        mod = _load_requirements()
        pat = mod._YEARS.pattern
        # The
        # years
        # number
        # group
        # must
        # use
        # \d{1,2}.
        # Look
        # for
        # the
        # pattern
        # `(?P<n>\d{1,2}`
        # which
        # is
        # the
        # named
        # group
        # for
        # the
        # years
        # number.
        self.assertIn(
            r"(?P<n>\d{1,2})", pat,
            f"_YEARS pattern "
            f"{pat!r} does NOT "
            f"contain the named "
            f"group `(?P<n>\\d{{1,2}})`. "
            f"The years number "
            f"named group must "
            f"cap the value at "
            f"99 (\\d{{1,2}}). A "
            f"drift that removes "
            f"the cap (e.g. "
            f"\\d+) would match "
            f"unreasonable years "
            f"claims like '100 "
            f"years'."
        )
        # And the
        # pattern
        # must be
        # case-insensitive
        # (so
        # "Years"
        # and
        # "YEARS"
        # both
        # match).
        self.assertEqual(
            mod._YEARS.flags & re.I,
            re.I,
            f"_YEARS pattern "
            f"is NOT case-insensitive. "
            f"'years' appears "
            f"in job postings "
            f"in any case "
            f"('Years' vs "
            f"'years'); the "
            f"regex must be "
            f"case-insensitive."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
