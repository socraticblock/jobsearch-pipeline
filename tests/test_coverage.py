"""W3.3 -- Coverage is printed, not implied.

The digest must state how many postings had a description,
how many could not be judged, and why. A reader who sees a
shortlist cannot tell whether the gate is silent because
every posting passed, or because the gate never had a
description to evaluate.

The contract this test enforces:

  1. `collect()` returns a 5-tuple: (surfaced, dropped,
     not_judged, stats, include_unsuitable).
  2. `stats` always includes the four counts the reader
     needs: read, with_description, not_judged, surfaced,
     dropped.
  3. A posting with `description_state != "complete"` goes
     to `not_judged`, not to `surfaced` or `dropped`. The
     gate's verdict is irrelevant: the gate never had a
     description to evaluate.
  4. The `_text_report` and `render_pdf` coverage line
     includes the `not_judged` count and a one-line reason.
  5. The NOT YET RETRIEVED section appears when there is at
     least one unretrieved posting, and lists each with its
     reason and link.

Borrowed shape: career-ops' coverage line ("X of Y
evaluated; Z skipped because <reason>"), and the layout
test in jobsync's digest (the headline line matches the
ledger count).

Run:  python3 -m unittest tests.test_coverage -v
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import render_pdf  # noqa: E402

NOW = datetime.now().isoformat(timespec="seconds")


def _add_job(con, *, title, company="Acme Ltd",
             location="Lisbon, Portugal",
             url="https://example.invalid/jobs/1",
             description=None,
             description_state="complete",
             salary_text=None) -> int:
    cur = con.execute(
        """INSERT INTO jobs (dedupe_key, title, company, location, remote, url,
           external_job_id, description, description_state, salary_text,
           status, first_seen_at, last_seen_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"dedupe:{title}:{url}", title, company, location, None, url, None,
         description, description_state, salary_text, "open",
         NOW, NOW, NOW, NOW),
    )
    con.commit()
    return int(cur.lastrowid)


class _RenderFixture(unittest.TestCase):
    """A fresh ledger for each test."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.db"
        # Use the project's schema so the ledger is realistic.
        from jobsearch.db import connect
        self.con = connect(self.db)

    def tearDown(self) -> None:
        self.con.close()
        self.tmp.cleanup()


class TestCoverageContract(_RenderFixture):
    """W3.3 -- the digest's coverage line is honest."""

    def test_collect_returns_five_tuple(self) -> None:
        """W3.3 contract: `collect()` returns (surfaced,
        dropped, not_judged, stats, include_unsuitable)."""
        result = render_pdf.collect(self.db, False, None)
        self.assertEqual(
            len(result), 5,
            f"collect() should return 5 values, got {len(result)}: "
            f"{tuple(type(r).__name__ for r in result)}"
        )

    def test_stats_has_four_counts(self) -> None:
        """The stats dict must always carry the four counts the
        reader needs: read, with_description, not_judged,
        surfaced, dropped. A future contributor who drops a
        field is failing the contract."""
        _add_job(self.con, title="A")
        _, _, _, stats, _ = render_pdf.collect(self.db, False, None)
        for field in ("read", "with_description", "not_judged",
                      "surfaced", "dropped"):
            self.assertIn(
                field, stats,
                f"stats dict missing the W3.3 count: {field!r}. "
                f"The digest's coverage line is dishonest "
                f"without it."
            )
            self.assertIsInstance(
                stats[field], int,
                f"stats[{field!r}] is not an integer"
            )

    def test_incomplete_posting_goes_to_not_judged(self) -> None:
        """A posting with description_state != "complete" is
        not a verdict. The digest must route it to the
        `not_judged` bucket, NOT to `surfaced` (where it would
        surface as a misleading needs_research) or `dropped`
        (where it would look like a rejection)."""
        _add_job(self.con, title="Backend Engineer",
                 description_state="incomplete",
                 description="")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        self.assertEqual(len(surfaced), 0)
        self.assertEqual(len(dropped), 0)
        self.assertEqual(len(not_judged), 1)
        self.assertEqual(stats["not_judged"], 1)
        self.assertEqual(stats["surfaced"], 0)
        self.assertEqual(stats["dropped"], 0)
        # Reason is non-empty.
        self.assertTrue(
            not_judged[0][1],
            "not_judged entry should carry a reason string"
        )

    def test_complete_posting_goes_to_surfaced_or_dropped(self) -> None:
        """A posting with description_state='complete' and a
        body goes through the gate and is judged. With
        description_state='complete' the digest's not_judged
        count is zero."""
        _add_job(self.con, title="Backend Engineer",
                 description="Python required. Django required. "
                             "5+ years of experience required.")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        self.assertEqual(len(not_judged), 0)
        self.assertEqual(stats["not_judged"], 0)
        # The posting is either surfaced or dropped, never
        # silently skipped.
        self.assertEqual(
            len(surfaced) + len(dropped), 1
        )

    def test_text_report_coverage_line_includes_not_judged(self) -> None:
        """The text-report coverage line must show the
        not_judged count, not just surfaced and dropped. A
        reader of the digest is owed the truth about how
        many postings were left unjudged."""
        _add_job(self.con, title="Backend Engineer",
                 description_state="incomplete",
                 description="",
                 url="https://example.invalid/1")
        _add_job(self.con, title="Frontend Engineer",
                 description="Python required. 5+ years required.",
                 description_state="complete",
                 url="https://example.invalid/2")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        text = render_pdf._text_report(surfaced, dropped, not_judged,
                                       stats, False)
        # The coverage line is the second line of the report.
        head = text.splitlines()[1]
        self.assertIn("not yet retrieved", head.lower(),
                      f"coverage line missing 'not yet retrieved' "
                      f"phrase: {head!r}")
        self.assertIn("1", head,
                      f"coverage line missing the count '1' for "
                      f"the one unretrieved posting: {head!r}")

    def test_text_report_has_not_judged_section(self) -> None:
        """When not_judged is non-empty, the text report must
        include a "NOT YET RETRIEVED" section listing each
        unretrieved posting with its link."""
        _add_job(self.con, title="Backend Engineer",
                 description_state="incomplete",
                 description="",
                 url="https://example.invalid/jobs/42")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        text = render_pdf._text_report(surfaced, dropped, not_judged,
                                       stats, False)
        self.assertIn("NOT YET RETRIEVED", text)
        self.assertIn("Backend Engineer", text)
        self.assertIn("https://example.invalid/jobs/42", text)

    def test_mixed_fixture_counts_match_the_ledger(self) -> None:
        """Mixed fixture: 3 postings (1 complete, 1
        incomplete, 1 with a known hard-avoid title). The
        coverage counts must add up exactly."""
        _add_job(self.con, title="Backend Engineer",
                 description="Python required.",
                 description_state="complete",
                 url="https://example.invalid/1")
        _add_job(self.con, title="Some Title",
                 description="",
                 description_state="incomplete",
                 url="https://example.invalid/2")
        _add_job(self.con, title="Account Executive",
                 description="Sell things.",
                 description_state="complete",
                 url="https://example.invalid/3")
        surfaced, dropped, not_judged, stats, _ = (
            render_pdf.collect(self.db, False, None)
        )
        # 3 postings read
        self.assertEqual(stats["read"], 3)
        # 2 have a description retrieved
        self.assertEqual(stats["with_description"], 2)
        # 1 not yet retrieved
        self.assertEqual(stats["not_judged"], 1)
        # 1 surfaced (Backend), 1 dropped (Account Executive)
        self.assertEqual(stats["surfaced"] + stats["dropped"], 2)
        # The five categories partition `read` exactly.
        self.assertEqual(
            stats["with_description"] + stats["not_judged"], 3
        )


if __name__ == "__main__":
    unittest.main()
