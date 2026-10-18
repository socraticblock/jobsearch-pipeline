"""Acceptance tests for the Remotive adapter (offline, injected fetcher)."""
from __future__ import annotations

import json
import unittest

from jobsearch.sources import base, remotive

NOTICE = {"job-count": 2, "total-job-count": 2}

FULL = {
    "id": "2069746",
    "title": "Tech Lead Full-Stack Rails Engineer",
    "company_name": "Mitre Media",
    "candidate_required_location": "USA, Canada, USA timezones",
    "salary": "$170k - $200k",
    "publication_date": "2026-10-14T20:33:44",
    "url": "https://remotive.com/remote-jobs/software-development/tech-lead",
    "description": "<p class=\"h1\">We build <b>agent workflows</b> with TypeScript.</p>",
}

NO_DESC = {
    "id": "2",
    "title": "Backend Engineer",
    "company_name": "Acme",
    "candidate_required_location": "",
    "salary": "",
    "publication_date": "2026-10-14T20:33:44",
    "url": "https://remotive.com/remote-jobs/backend",
    "description": "",
}

NO_IDENTITY = {"title": "Mystery", "company_name": "", "url": None, "description": ""}


def board(*elements):
    return json.dumps({"job-count": len(elements), "total-job-count": len(elements),
                       "jobs": list(elements)})


def fetcher_returning(body):
    return lambda url: (200, body)


class RemotiveAdapterTests(unittest.TestCase):
    def fetch(self, body):
        return remotive.fetch(fetcher=fetcher_returning(body))

    def test_full_description_captured(self):
        listings, run = self.fetch(board(FULL))
        self.assertEqual(run.status, "ok")
        self.assertEqual(run.items, 1)
        self.assertTrue(listings[0].has_description)
        self.assertIn("agent workflows", listings[0].description)
        self.assertNotIn("<p", listings[0].description)
        self.assertEqual(run.items_with_description, 1)

    def test_empty_description_stays_none(self):
        listings, run = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].description)
        self.assertFalse(listings[0].has_description)
        self.assertEqual(run.items_with_description, 0)

    def test_salary_kept_verbatim(self):
        listings, _ = self.fetch(board(FULL))
        self.assertEqual(listings[0].salary_text, "$170k - $200k")

    def test_empty_salary_is_none(self):
        listings, _ = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].salary_text)

    def test_empty_location_is_none(self):
        listings, _ = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].location)

    def test_location_kept_verbatim(self):
        listings, _ = self.fetch(board(FULL))
        self.assertEqual(listings[0].location, "USA, Canada, USA timezones")

    def test_unidentifiable_counted(self):
        listings, run = self.fetch(board(NO_IDENTITY))
        self.assertEqual(run.items, 1)
        self.assertEqual(run.items_missing_identity, 1)

    def test_http_failure_is_failed_run(self):
        def boom(url):
            raise base.FetchError("HTTP 503", status=503)

        listings, run = remotive.fetch(fetcher=boom)
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.http_status, 503)

    def test_non_json_body_is_failure(self):
        listings, run = self.fetch("<html>maintenance</html>")
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("not JSON", run.error)

    def test_missing_jobs_list_is_failure(self):
        listings, run = self.fetch(json.dumps({"foo": []}))
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("no 'jobs' list", run.error)

    def test_reingest_adds_no_rows(self):
        import tempfile
        from pathlib import Path
        from jobsearch import db as db_mod, ingest as ingest_mod

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                listings, _ = self.fetch(board(FULL))
                ingest_mod.ingest_listings(
                    con, listings, source_kind=remotive.SPEC.kind,
                    source_name=remotive.SPEC.name,
                    external_ref=remotive.SPEC.external_ref,
                )
                before = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                listings2, _ = self.fetch(board(FULL))
                ingest_mod.ingest_listings(
                    con, listings2, source_kind=remotive.SPEC.kind,
                    source_name=remotive.SPEC.name,
                    external_ref=remotive.SPEC.external_ref,
                )
                after = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                self.assertEqual(before, after)
                self.assertEqual(before, 1)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
