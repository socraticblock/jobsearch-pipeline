"""I-30 -- the alert-parser
constants pin.

The 7 alert-parser
constants in
`jobsearch/parse_alert.py`:
- `_JOB_URL`: matches
  LinkedIn job URLs
  (used to extract
  external_job_id).
- `_ANY_URL`: matches
  any HTTP(S) URL
  (for source URLs).
- `_SEP`: matches
  separators between
  company and
  location in alert
  text
  (`·`, `•`, `|`,
  `—`, `–`).
- `_VIEW_LABEL`:
  matches "view/see
  this job" labels.
- `_BLOCK_SEP`:
  matches the block
  separator between
  job cards
  (5+ dashes,
  equals, or
  asterisks).
- `_BOILERPLATE`:
  matches LinkedIn
  badges (the
  **alert-injection
  contract** --
  prevents a badge
  from being
  misread as a job
  title).
- `_CARD_MARK`:
  matches the HTML
  job-card marker
  (`data-test-id="job-card"`).

The most
contract-critical
of these is
`_BOILERPLATE`.
The comment at
L46-48 documents a
real production
bug that would
resurface if any
of its 10
sub-patterns
drifts:

> Badges, not job
> titles. LinkedIn
> puts these inside
> every card and
> above every "View
> job" link in the
> text part.
> Reading one as a
> title INVENTS a
> job: on the first
> real alert tested,
> 9 of 12 extracted
> rows were this
> badge, each
> carrying a real
> job id, so each
> would have entered
> the ledger as a
> distinct job.

A drift that
removes a single
pattern (e.g.
"actively hiring")
from `_BOILERPLATE`
would silently
inject 9 phantom
jobs per alert
into the ledger.
This is the
**alert-injection
contract** -- the
regex that
prevents the
ledger from being
flooded with
phantom jobs.

`_JOB_URL` is the
external_job_id
extractor. LinkedIn
job URLs come in
3 shapes:
- `https://www.linkedin.com/jobs/view/4012345678/`
- `https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=...`
- `https://www.linkedin.com/jobs/view/some-slug-4012345678?refId=...`

A drift that
narrows the
regex (e.g.
removes the
`[a-z0-9-]*-`
slug prefix)
would silently
fail to extract
job ids from
URLs with slugs.

`_CARD_MARK` is
the HTML job-card
detector. LinkedIn
serves job cards
as HTML elements
with
`data-test-id="job-card"`.
A drift that
removes the
`job-card` value
would silently
fail to detect
cards in the
HTML part of an
alert.

`_BLOCK_SEP` is
the block
separator. A
drift that
narrows the
character class
(e.g. removes
`=`) would
silently fail to
split blocks
separated by
`=====` lines.

Before this turn,
no test pinned
these 7
constants. A
contributor who
"cleaned up" a
"duplicate" or
"redundant"
sub-pattern in
`_BOILERPLATE`
would silently
inject phantom
jobs.

The fix is a new
`TestParseAlertConstants`
class with 5 tests:
1. `test_boilerplate_matches_documented_badges`:
   each documented
   boilerplate
   sub-pattern
   matches a
   documented
   badge line.
2. `test_boilerplate_does_not_match_real_titles`:
   the regex
   does NOT
   match a real
   job title.
3. `test_job_url_matches_documented_shapes`:
   each
   documented
   LinkedIn URL
   shape
   matches.
4. `test_card_mark_matches_documented_html`:
   the
   documented
   HTML marker
   matches.
5. `test_block_sep_matches_documented_separators`:
   each
   documented
   block
   separator
   matches
   (dashes,
   equals,
   asterisks).

Drift-injection
verified: removing
"actively hiring"
from
`_BOILERPLATE`
fails the
boilerplate test.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_parse_alert():
    """Helper: import the
    parse_alert module.

    The module has a
    relative import
    (`from .normalize
    import ...`), so
    we must import it
    as part of the
    `jobsearch`
    package (not
    exec the file in
    isolation). The
    import is guarded
    to fail gracefully
    if `jobsearch` is
    not on the path --
    in that case, the
    tests skip with an
    explanatory
    message.
    """
    try:
        from jobsearch import parse_alert
        return parse_alert
    except ImportError:
        # If the import
        # fails (e.g. the
        # test is run
        # without the
        # jobsearch
        # package on the
        # path), skip the
        # class.
        raise unittest.SkipTest(
            "jobsearch package not on "
            "PYTHONPATH; cannot import "
            "parse_alert (which has a "
            "relative import)."
        )


class TestParseAlertConstants(unittest.TestCase):
    """The 7 alert-parser
    constants in
    `jobsearch/parse_alert.py`
    are the M2 alert-parser
    contract. The most
    critical is
    `_BOILERPLATE`, which
    prevents phantom-job
    injection.
    """

    # Documented
    # boilerplate
    # patterns --
    # one per
    # sub-pattern
    # in the
    # regex.
    # Each must
    # match a
    # line that
    # is a badge,
    # not a job
    # title.
    BOILERPLATE_CASES = (
        "This company is actively hiring",
        "Actively recruiting",
        "Actively hiring",
        "Be an early applicant",
        "Be one of the first 25 applicants",
        "Early applicant",
        "Promoted",
        "Promoted by LinkedIn",
        "Easy apply",
        "Apply now",
        "View this job",
        "View job",
        "See this job",
        "See job",
        "Show more",
        "See more",
        "Unsubscribe",
        "Your job alert for Software Engineer",
        "You'll receive notifications for similar jobs",
        "See all jobs",
        "View all your job alerts",
        "Manage your job alerts",
        "25 applicants",
        "10 alumni",
        "5 connections",
        "100 employees",
    )

    BOILERPLATE_NON_MATCHES = (
        "Software Engineer",
        "Senior Backend Developer",
        "Full Stack Engineer",
        "TypeScript Developer",
        "Python Engineer",
    )

    # LinkedIn
    # job URL
    # shapes
    # documented
    # in
    # parse_alert.py
    # L28-31.
    JOB_URL_CASES = (
        "https://www.linkedin.com/jobs/view/4012345678/",
        "https://www.linkedin.com/jobs/view/4012345678",
        "https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc",
        "https://www.linkedin.com/jobs/view/some-slug-4012345678?refId=xyz",
        "https://www.linkedin.com/jobs/view/senior-engineer-4012345678/",
    )

    # Card mark
    # cases.
    CARD_MARK_CASES = (
        '<div data-test-id="job-card">',
        '<div data-test-id=\'job-card\'>',
        '<div DATA-TEST-ID="job-card">',
    )

    # Block
    # separator
    # cases.
    BLOCK_SEP_CASES = (
        "-----",
        "======",
        "******",
        "________",
        "     -----     ",
        "----------",
    )

    def test_boilerplate_matches_documented_badges(self) -> None:
        """`_BOILERPLATE` in
        `jobsearch/parse_alert.py`
        must match every
        documented badge
        line. The regex
        is the
        **alert-injection
        contract**: a
        drift that
        removes a single
        sub-pattern
        would silently
        inject phantom
        jobs into the
        ledger.
        """
        mod = _load_parse_alert()
        for case in self.BOILERPLATE_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod._BOILERPLATE.match(case),
                    f"_BOILERPLATE did NOT match "
                    f"the documented badge "
                    f"line {case!r}. The regex "
                    f"is the alert-injection "
                    f"contract: a line that "
                    f"is a badge (not a job "
                    f"title) must be matched "
                    f"and excluded from "
                    f"becoming a job title. "
                    f"Without this match, the "
                    f"line would be read as "
                    f"a job title and the "
                    f"ledger would be flooded "
                    f"with phantom jobs."
                )

    def test_boilerplate_does_not_match_real_titles(self) -> None:
        """`_BOILERPLATE` in
        `jobsearch/parse_alert.py`
        must NOT match a
        real job title.
        A real job title
        is not a badge
        and must be
        read as a job
        title.
        """
        mod = _load_parse_alert()
        for case in self.BOILERPLATE_NON_MATCHES:
            with self.subTest(case=case):
                self.assertIsNone(
                    mod._BOILERPLATE.match(case),
                    f"_BOILERPLATE matched a "
                    f"real job title {case!r}. "
                    f"The regex is the "
                    f"alert-injection contract: "
                    f"a real job title must NOT "
                    f"be matched, or the gate "
                    f"would silently reject "
                    f"real jobs as boilerplate."
                )

    def test_job_url_matches_documented_shapes(self) -> None:
        """`_JOB_URL` in
        `jobsearch/parse_alert.py`
        must match every
        documented
        LinkedIn job URL
        shape:
        - `/jobs/view/ID/`
          (basic)
        - `/comm/jobs/view/ID/`
          (comm subdomain)
        - `/jobs/view/slug-ID`
          (slugged)

        A drift that
        narrows the
        regex would
        silently fail to
        extract job ids
        from real
        LinkedIn URLs.
        """
        mod = _load_parse_alert()
        for case in self.JOB_URL_CASES:
            with self.subTest(case=case):
                m = mod._JOB_URL.search(case)
                self.assertIsNotNone(
                    m,
                    f"_JOB_URL did NOT match "
                    f"the documented LinkedIn "
                    f"URL {case!r}. The regex "
                    f"is the external_job_id "
                    f"extractor; a narrow regex "
                    f"would silently fail to "
                    f"extract job ids from "
                    f"real LinkedIn URLs."
                )
                # The
                # named
                # group
                # `id`
                # must
                # be
                # captured.
                self.assertIn(
                    "id", m.groupdict(),
                    f"_JOB_URL matched {case!r} "
                    f"but did NOT capture a "
                    f"named group `id`. The "
                    f"external_job_id is "
                    f"extracted from "
                    f"m.group('id'); without "
                    f"the named group, the "
                    f"extraction fails."
                )

    def test_card_mark_matches_documented_html(self) -> None:
        """`_CARD_MARK` in
        `jobsearch/parse_alert.py`
        must match the
        documented HTML
        marker
        `data-test-id="job-card"`.
        A drift that
        removes the
        `job-card` value
        would silently
        fail to detect
        cards in the
        HTML part of an
        alert.
        """
        mod = _load_parse_alert()
        for case in self.CARD_MARK_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod._CARD_MARK.search(case),
                    f"_CARD_MARK did NOT match "
                    f"the documented HTML "
                    f"marker {case!r}. The "
                    f"regex is the HTML "
                    f"job-card detector; "
                    f"without this match, "
                    f"the HTML part of an "
                    f"alert would not be "
                    f"parsed."
                )

    def test_block_sep_matches_documented_separators(self) -> None:
        """`_BLOCK_SEP` in
        `jobsearch/parse_alert.py`
        must match every
        documented block
        separator:
        5+ dashes,
        equals,
        underscores,
        or asterisks.
        A drift that
        narrows the
        character class
        would silently
        fail to split
        blocks.
        """
        mod = _load_parse_alert()
        for case in self.BLOCK_SEP_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod._BLOCK_SEP.search(case),
                    f"_BLOCK_SEP did NOT match "
                    f"the documented block "
                    f"separator {case!r}. The "
                    f"regex is the block "
                    f"separator detector; "
                    f"without this match, "
                    f"the alert's plain-text "
                    f"part would not be split "
                    f"into individual job "
                    f"cards."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
