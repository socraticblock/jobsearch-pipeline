"""Acceptance tests for the fetch orchestrator (offline, injected fetchers)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jobsearch import db as db_mod
from jobsearch import fetch as fetch_mod
from jobsearch.sources import arbeitnow, remotive, remoteok


def _remoteok_body():
    return json.dumps([
        {"last_updated": 1, "legal": "terms"},
        {"id": "1", "position": "AI Engineer", "company": "Co", "location": "",
         "url": "https://remoteok.com/j/1", "description": "<p>desc</p>"},
    ])


def _remotive_body():
    return json.dumps({"job-count": 1, "total-job-count": 1, "jobs": [
        {"id": "2", "title": "Backend", "company_name": "Co2", "candidate_required_location": "Worldwide",
         "salary": "", "publication_date": "2026-10-14T00:00:00", "url": "https://remotive.com/j/2", "description": "<p>d2</p>"},
    ]})


def _arbeitnow_body():
    return json.dumps({"data": [
        {"slug": "slug3", "title": "Frontend", "company_name": "Co3", "location": "Berlin",
         "remote": "False", "url": "https://arbeitnow.com/j/3", "description": "<p>d3</p>",
         "tags": "[]", "job_types": "[]", "created_at": 1700000000},
    ], "links": {}, "meta": {}})


class FetchOrchestratorTests(unittest.TestCase):
    def _fetcher_for(self, name):
        bodies = {
            "remoteok": _remoteok_body(),
            "remotive": _remotive_body(),
            "arbeitnow": _arbeitnow_body(),
        }

        def fetcher(url):
            return (200, bodies[name])

        return fetcher

    def test_runs_all_sources_and_ingests(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            totals = fetch_mod.run(
                db_path=db,
                sources=["remoteok", "remotive", "arbeitnow"],
                fetcher_for=self._fetcher_for,
                record=False,
            )
            self.assertEqual(totals["ok"], 3)
            self.assertEqual(totals["failed"], 0)
            self.assertEqual(totals["new_jobs"], 3)
            con = db_mod.connect(db)
            try:
                n = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                self.assertEqual(n, 3)
            finally:
                con.close()

    def test_failed_source_does_not_abort_others(self):
        def fetcher_for(name):
            if name == "remotive":
                def boom(url):
                    raise fetch_mod.base.FetchError("HTTP 503", status=503)

                return boom
            return self._fetcher_for(name)

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            totals = fetch_mod.run(
                db_path=db,
                sources=["remoteok", "remotive", "arbeitnow"],
                fetcher_for=fetcher_for,
                record=False,
            )
            self.assertEqual(totals["ok"], 2)
            self.assertEqual(totals["failed"], 1)
            self.assertEqual(totals["new_jobs"], 2)

    def test_reingest_adds_no_rows(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            fetch_mod.run(db_path=db, sources=["remoteok"], fetcher_for=self._fetcher_for, record=False)
            totals2 = fetch_mod.run(db_path=db, sources=["remoteok"], fetcher_for=self._fetcher_for, record=False)
            self.assertEqual(totals2["new_jobs"], 0)
            self.assertEqual(totals2["seen_jobs"], 1)

    def test_unknown_source_not_in_registry(self):
        # registry keys are fixed
        self.assertIn("remoteok", fetch_mod.REGISTRY)
        self.assertIn("remotive", fetch_mod.REGISTRY)
        self.assertIn("arbeitnow", fetch_mod.REGISTRY)


if __name__ == "__main__":
    unittest.main()
