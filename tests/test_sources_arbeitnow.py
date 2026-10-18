"""Acceptance tests for the Arbeitnow adapter (offline, injected fetcher)."""
from __future__ import annotations

import json
import unittest

from jobsearch.sources import base, arbeitnow

FULL = {
    "slug": "tech-lead-remote-123",
    "title": "Tech Lead",
    "company_name": "Example GmbH",
    "location": "Berlin",
    "remote": "True",
    "url": "https://www.arbeitnow.com/jobs/companies/example/tech-lead-123",
    "description": "<p>Build <b>agent workflows</b> with TypeScript.</p>",
    "tags": "['typescript', 'react']",
    "job_types": "['Full-time']",
    "created_at": 1700000000,
}

ONSITE = {
    "slug": "junior-tiktok-456",
    "title": "Junior TikTok Shop Manager",
    "company_name": "ADBAKER",
    "location": "Cologne",
    "remote": "False",
    "url": "https://www.arbeitnow.com/jobs/companies/adbaaker/junior-456",
    "description": "<h2>join the team</h2>",
    "tags": "['Marketing']",
    "job_types": "['Unbefristeter arbeitsvertrag']",
    "created_at": 1700000000,
}

NO_DESC = {
    "slug": "no-desc-789",
    "title": "Backend Engineer",
    "company_name": "Acme",
    "location": "",
    "remote": "False",
    "url": "https://www.arbeitnow.com/jobs/companies/acme/backend-789",
    "description": "",
    "tags": "[]",
    "job_types": "[]",
    "created_at": None,
}

NO_IDENTITY = {"title": "Mystery", "company_name": "", "url": None, "description": "", "remote": "False"}


def board(*elements):
    return json.dumps({"data": list(elements), "links": {}, "meta": {}})


def fetcher_returning(body):
    return lambda url: (200, body)


class ArbeitnowAdapterTests(unittest.TestCase):
    def fetch(self, body):
        return arbeitnow.fetch(fetcher=fetcher_returning(body))

    def test_full_description_captured(self):
        listings, run = self.fetch(board(FULL))
        self.assertEqual(run.status, "ok")
        self.assertEqual(run.items, 1)
        self.assertTrue(listings[0].has_description)
        self.assertIn("agent workflows", listings[0].description)
        self.assertIn("Tags: typescript, react", listings[0].description)
        self.assertIn("Job types: Full-time", listings[0].description)
        self.assertEqual(run.items_with_description, 1)

    def test_remote_flag_carried_into_location(self):
        listings, _ = self.fetch(board(FULL))
        self.assertIn("remote", listings[0].location)
        self.assertEqual(listings[0].remote, "remote")

    def test_onsite_stays_not_remote(self):
        listings, _ = self.fetch(board(ONSITE))
        self.assertEqual(listings[0].location, "Cologne")
        self.assertIsNone(listings[0].remote)

    def test_empty_location_is_none(self):
        listings, _ = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].location)

    def test_empty_description_stays_none(self):
        listings, run = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].description)
        self.assertFalse(listings[0].has_description)
        self.assertEqual(run.items_with_description, 0)

    def test_created_at_converted_to_iso(self):
        listings, _ = self.fetch(board(FULL))
        self.assertIsNotNone(listings[0].published_at)
        self.assertIn("2023", listings[0].published_at)

    def test_missing_created_at_is_none(self):
        listings, _ = self.fetch(board(NO_DESC))
        self.assertIsNone(listings[0].published_at)

    def test_salary_is_none(self):
        listings, _ = self.fetch(board(FULL))
        self.assertIsNone(listings[0].salary_text)

    def test_unidentifiable_counted(self):
        listings, run = self.fetch(board(NO_IDENTITY))
        self.assertEqual(run.items, 1)
        self.assertEqual(run.items_missing_identity, 1)

    def test_http_failure_is_failed_run(self):
        def boom(url):
            raise base.FetchError("HTTP 503", status=503)

        listings, run = arbeitnow.fetch(fetcher=boom)
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.http_status, 503)

    def test_non_json_body_is_failure(self):
        listings, run = self.fetch("<html>maintenance</html>")
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("not JSON", run.error)

    def test_missing_data_list_is_failure(self):
        listings, run = self.fetch(json.dumps({"foo": []}))
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("no 'data' list", run.error)

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
                    con, listings, source_kind=arbeitnow.SPEC.kind,
                    source_name=arbeitnow.SPEC.name,
                    external_ref=arbeitnow.SPEC.external_ref,
                )
                before = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                listings2, _ = self.fetch(board(FULL))
                ingest_mod.ingest_listings(
                    con, listings2, source_kind=arbeitnow.SPEC.kind,
                    source_name=arbeitnow.SPEC.name,
                    external_ref=arbeitnow.SPEC.external_ref,
                )
                after = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                self.assertEqual(before, after)
                self.assertEqual(before, 1)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
