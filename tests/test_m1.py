"""M1 acceptance tests: parsing, normalisation, dedupe, idempotency.

Run:  python3 -m unittest discover -s tests -v
      python3 -O -m unittest discover -s tests      # must behave IDENTICALLY

Failure signalling uses unittest assertion METHODS, never bare `assert`, so the
suite cannot be silently neutered by `python -O` (bare asserts are stripped under
-O). test_package_contains_no_bare_asserts enforces that rule for the package too.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import db as db_mod                      # noqa: E402
from jobsearch.ingest import ingest_directory, ingest_message  # noqa: E402
from jobsearch.normalize import classify_remote, dedupe_key    # noqa: E402
from jobsearch.parse_alert import parse_message         # noqa: E402

FIXTURES = ROOT / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestParsing(unittest.TestCase):
    def test_alert_001_yields_three_jobs_with_fields(self):
        pm = parse_message(fixture("alert_001.eml"))
        self.assertEqual(len(pm.listings), 3)
        by_id = {l.external_job_id: l for l in pm.listings}
        self.assertEqual(set(by_id), {"4012345678", "4012345679", "4012345680"})
        self.assertEqual(by_id["4012345678"].title, "Software Engineer")
        self.assertEqual(by_id["4012345678"].company, "Acme Systems")
        self.assertEqual(by_id["4012345678"].location, "Dublin, Ireland")
        self.assertEqual(by_id["4012345679"].remote, "remote")
        self.assertEqual(by_id["4012345680"].remote, "hybrid")
        self.assertEqual(pm.source_name, "linkedin_job_alert")

    def test_link_with_no_readable_title_stays_none(self):
        pm = parse_message(fixture("alert_003_no_title.eml"))
        self.assertEqual(len(pm.listings), 2)
        for listing in pm.listings:
            self.assertIsNone(listing.title, "must not invent a title")
            self.assertIsNotNone(listing.external_job_id)

    def test_plain_only_layout_pairs_title_and_link(self):
        pm = parse_message(fixture("alert_004_plain_only.eml"))
        by_id = {l.external_job_id: l for l in pm.listings}
        self.assertEqual(by_id["4012345900"].title, "Automation Engineer")
        self.assertEqual(by_id["4012345900"].company, "Northwind")
        self.assertEqual(by_id["4012345900"].location, "Remote")

    def test_non_job_email_yields_nothing(self):
        pm = parse_message(fixture("not_a_job.eml"))
        self.assertEqual(pm.listings, [])
        self.assertEqual(pm.source_name, "email_alert")

    def test_message_id_is_stable_across_reparse(self):
        a = parse_message(fixture("alert_001.eml")).message_id
        b = parse_message(fixture("alert_001.eml")).message_id
        self.assertEqual(a, b)


class TestNormalize(unittest.TestCase):
    def test_strong_key_prefers_external_id(self):
        key = dedupe_key(
            source_name="linkedin_job_alert", external_job_id="4012345678",
            title="A", company="B", location="C",
        )
        self.assertEqual(key, "linkedin:id:4012345678")

    def test_weak_key_is_labelled_and_stable(self):
        one = dedupe_key(source_name="company_page", external_job_id=None,
                         title="Senior Engineer", company="Acme Systems, Inc.",
                         location="Remote")
        two = dedupe_key(source_name="company_page", external_job_id=None,
                         title="senior   engineer", company="Acme Systems Inc",
                         location="remote")
        self.assertTrue(one.startswith("hash:"))
        self.assertEqual(one, two, "folded triple must match across cosmetic differences")

    def test_different_jobs_get_different_weak_keys(self):
        one = dedupe_key(source_name="company_page", external_job_id=None,
                         title="Engineer", company="Acme", location="Berlin")
        two = dedupe_key(source_name="company_page", external_job_id=None,
                         title="Engineer", company="Acme", location="Lisbon")
        self.assertNotEqual(one, two)

    def test_remote_classification(self):
        self.assertEqual(classify_remote("Remote"), "remote")
        self.assertEqual(classify_remote("Fully remote (EU)"), "remote")
        self.assertEqual(classify_remote("Hybrid — Dublin"), "hybrid")
        self.assertEqual(classify_remote("On-site, Berlin"), "onsite")
        self.assertIsNone(classify_remote("Dublin, Ireland"))


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "jobs.db"
        self.con = db_mod.connect(self.db_path)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _count(self, table: str) -> int:
        return self.con.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]

    def test_ingest_creates_rows_and_is_idempotent(self):
        first = ingest_directory(self.con, FIXTURES)
        # These counts track the shipped fixture set (fixtures/*.eml): 6 alert
        # emails carrying 10 distinct jobs. Adding a fixture moves them.
        self.assertEqual(first["files"], 6)
        self.assertEqual(first["new_jobs"], 10)
        self.assertEqual(first["unique_jobs"], 10)
        self.assertEqual(self._count("messages"), 6)

        second = ingest_directory(self.con, FIXTURES)
        self.assertEqual(second["skipped"], 6, "every email recognised as already processed")
        self.assertEqual(second["new_jobs"], 0, "re-run must add zero rows")
        self.assertEqual(second["unique_jobs"], 10)

    def test_same_job_from_two_emails_is_one_row(self):
        ingest_directory(self.con, FIXTURES)
        rows = self.con.execute(
            "SELECT id FROM jobs WHERE dedupe_key='linkedin:id:4012345678'"
        ).fetchall()
        self.assertEqual(len(rows), 1, "one job id must never become two rows")
        sightings = self.con.execute(
            "SELECT COUNT(*) c FROM sightings WHERE job_id=?", (rows[0]["id"],)
        ).fetchone()["c"]
        self.assertEqual(sightings, 1, "identical repeat sightings are deduped")

    def test_no_description_is_ever_invented(self):
        ingest_directory(self.con, FIXTURES)
        invented = self.con.execute(
            "SELECT COUNT(*) c FROM jobs WHERE description IS NOT NULL"
        ).fetchone()["c"]
        self.assertEqual(invented, 0)
        states = {r["description_state"] for r in
                  self.con.execute("SELECT description_state FROM jobs")}
        self.assertEqual(states, {"incomplete"})

    def test_unreadable_titles_are_null_not_guessed(self):
        ingest_directory(self.con, FIXTURES)
        nulls = self.con.execute(
            "SELECT COUNT(*) c FROM jobs WHERE title IS NULL"
        ).fetchone()["c"]
        self.assertEqual(nulls, 2, "only the two empty-anchor listings")

    def test_crash_retry_does_not_duplicate(self):
        raw = fixture("alert_001.eml")
        ingest_message(self.con, raw, raw_ref="a.eml")
        before = self._count("jobs")
        ingest_message(self.con, raw, raw_ref="a.eml")   # simulated retry
        self.assertEqual(self._count("jobs"), before)

    def test_decisions_and_actions_tables_exist_for_later_milestones(self):
        tables = {r["name"] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"decisions", "actions", "sightings", "messages"} <= tables)


class TestOptimisedSafety(unittest.TestCase):
    """`python -O` strips bare asserts; the pipeline must not depend on them."""

    def test_package_contains_no_bare_asserts(self):
        pattern = re.compile(r"^\s*assert\s", re.MULTILINE)
        offenders = []
        for path in (ROOT / "jobsearch").rglob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        self.assertEqual(offenders, [], f"bare assert found in {offenders}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
