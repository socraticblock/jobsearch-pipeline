"""Acceptance tests for the HN hiring adapter (offline, injected fetcher)."""
from __future__ import annotations

import json
import unittest

from jobsearch.sources import base, hn_hiring

USER_PAYLOAD = {"submitted": [1002, 1001]}

STORY_OLD = {"id": 1001, "type": "story", "title": "Ask HN: Who is hiring? (September 2026)", "kids": [2001]}
STORY_NEW = {"id": 1002, "type": "story", "title": "Ask HN: Who is hiring? (October 2026)", "kids": [2002, 2003]}

COMMENT_2002 = {"id": 2002, "type": "comment",
                "text": "Acme Corp | https://acme.example | Remote | Full Time<p>We build things with TypeScript and React."}
COMMENT_2003 = {"id": 2003, "type": "comment", "text": ""}


def make_fetcher():
    data = {
        "https://hacker-news.firebaseio.com/v0/user/whoishiring.json": (200, json.dumps(USER_PAYLOAD)),
        "https://hacker-news.firebaseio.com/v0/item/1001.json": (200, json.dumps(STORY_OLD)),
        "https://hacker-news.firebaseio.com/v0/item/1002.json": (200, json.dumps(STORY_NEW)),
        "https://hacker-news.firebaseio.com/v0/item/2001.json": (200, json.dumps({"id": 2001, "type": "comment", "text": "old post"})),
        "https://hacker-news.firebaseio.com/v0/item/2002.json": (200, json.dumps(COMMENT_2002)),
        "https://hacker-news.firebaseio.com/v0/item/2003.json": (200, json.dumps(COMMENT_2003)),
    }

    def fetcher(url):
        if url in data:
            return data[url]
        raise base.FetchError(f"HTTP 404 for {url}", status=404)

    return fetcher


class HnHiringAdapterTests(unittest.TestCase):
    def test_picks_latest_hiring_thread(self):
        listings, run = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
        self.assertEqual(run.status, "ok")
        # only comments from the October thread (2002, 2003); 2003 empty -> skipped
        self.assertEqual(run.items, 1)
        self.assertEqual(listings[0].company, "Acme Corp")
        self.assertIn("TypeScript", listings[0].description)

    def test_has_description(self):
        listings, run = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
        self.assertTrue(listings[0].has_description)
        self.assertEqual(run.items_with_description, 1)

    def test_external_id_set(self):
        listings, _ = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
        self.assertEqual(listings[0].external_job_id, "2002")

    def test_url_points_to_hn(self):
        listings, _ = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
        self.assertIn("news.ycombinator.com", listings[0].url)

    def test_title_is_none(self):
        listings, _ = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
        self.assertIsNone(listings[0].title)

    def test_http_failure_is_failed_run(self):
        def boom(url):
            raise base.FetchError("HTTP 503", status=503)

        listings, run = hn_hiring.fetch(fetcher=boom)
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")

    def test_limit_caps_comments(self):
        listings, run = hn_hiring.fetch(fetcher=make_fetcher(), limit=1)
        # limit=1 fetches only first kid of the thread (2002)
        self.assertEqual(run.items, 1)

    def test_reingest_adds_no_rows(self):
        import tempfile
        from pathlib import Path
        from jobsearch import db as db_mod, ingest as ingest_mod

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                listings, _ = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
                ingest_mod.ingest_listings(
                    con, listings, source_kind=hn_hiring.SPEC.kind,
                    source_name=hn_hiring.SPEC.name,
                    external_ref=hn_hiring.SPEC.external_ref,
                )
                before = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                listings2, _ = hn_hiring.fetch(fetcher=make_fetcher(), limit=10)
                ingest_mod.ingest_listings(
                    con, listings2, source_kind=hn_hiring.SPEC.kind,
                    source_name=hn_hiring.SPEC.name,
                    external_ref=hn_hiring.SPEC.external_ref,
                )
                after = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
                self.assertEqual(before, after)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
