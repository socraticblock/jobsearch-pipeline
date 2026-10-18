"""Acceptance tests for enrich retry queue + resume (offline)."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jobsearch import db as db_mod
from jobsearch import enrich as enrich_mod

from jobsearch.enrich import RateLimited


def _seed_incomplete(con, jid=1, url="https://www.linkedin.com/jobs/view/1"):
    con.execute(
        "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,"
        "external_job_id,description,description_state,salary_text,status,"
        "first_seen_at,last_seen_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"k{jid}", "T", "C", "Remote", "remote", url, str(jid), None,
         "incomplete", None, "open",
         "2026-01-01T00:00:00", "2026-01-01T00:00:00",
         "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
    )
    con.commit()


class EnrichResumeTests(unittest.TestCase):
    def test_backoff_progression(self):
        self.assertEqual(enrich_mod._backoff_seconds(1), 45)
        self.assertEqual(enrich_mod._backoff_seconds(2), 300)
        self.assertEqual(enrich_mod._backoff_seconds(3), 1800)
        self.assertEqual(enrich_mod._backoff_seconds(4), 86400)
        self.assertEqual(enrich_mod._backoff_seconds(10), 86400)

    def test_resume_skips_complete_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                _seed_incomplete(con, 1)
                # mark complete
                con.execute("UPDATE jobs SET description='x', description_state='complete' WHERE id=1")
                con.commit()
                # complete job should not appear in pending (incomplete filter)
                pending = enrich_mod._pending(con, 10, None)
                self.assertEqual(len(pending), 0)
                # incomplete seed for a second job
                _seed_incomplete(con, 2, "https://www.linkedin.com/jobs/view/2")
                pending2 = enrich_mod._pending(con, 10, None)
                self.assertEqual(len(pending2), 1)
            finally:
                con.close()

    def test_queue_eligibility_blocks_future(self):
        now = datetime.now(timezone.utc)
        future = (now + timedelta(hours=1)).isoformat(timespec="seconds")
        rec = {"job_id": 1, "state": "pending", "next_try_at": future}
        self.assertFalse(enrich_mod._eligible(rec, now))
        past = (now - timedelta(hours=1)).isoformat(timespec="seconds")
        rec2 = {"job_id": 1, "state": "pending", "next_try_at": past}
        self.assertTrue(enrich_mod._eligible(rec2, now))

    def test_rate_limited_cooldown(self):
        now = datetime.now(timezone.utc)
        future = (now + timedelta(hours=1)).isoformat(timespec="seconds")
        rec = {"job_id": 1, "state": "rate_limited", "rate_limited_until": future}
        self.assertFalse(enrich_mod._eligible(rec, now))
        past = (now - timedelta(hours=1)).isoformat(timespec="seconds")
        rec2 = {"job_id": 1, "state": "rate_limited", "rate_limited_until": past}
        self.assertTrue(enrich_mod._eligible(rec2, now))

    def test_queue_write_on_429(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            qpath = Path(td) / "queue.jsonl"
            con = db_mod.connect(db)
            try:
                _seed_incomplete(con, 1)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                # monkeypatch enrich_one to raise RateLimited
                with patch("jobsearch.enrich.enrich_one", side_effect=RateLimited("HTTP 429")):
                    rc = enrich_mod.main(["--db", str(db), "--limit", "3", "--queue-path", str(qpath)])
                self.assertEqual(rc, 6)
                self.assertTrue(qpath.is_file())
                lines = qpath.read_text().strip().splitlines()
                self.assertEqual(len(lines), 1)
                rec = json.loads(lines[0])
                self.assertEqual(rec["job_id"], 1)
                self.assertEqual(rec["state"], "pending")
                self.assertEqual(rec["attempt"], 1)
                self.assertIn("next_try_at", rec)
            finally:
                con.close()

    def test_resume_skips_rate_limited_job(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            qpath = Path(td) / "queue.jsonl"
            con = db_mod.connect(db)
            try:
                _seed_incomplete(con, 1)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                # write a rate_limited record far in the future
                future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
                qpath.write_text(json.dumps({"job_id": 1, "state": "rate_limited",
                                            "rate_limited_until": future, "attempt": 5}) + "\n")
                pending = enrich_mod._pending(con, 10, None, resume=True,
                                            queue_path=qpath, now=datetime.now(timezone.utc))
                self.assertEqual(len(pending), 0)
            finally:
                con.close()

    def test_404_marks_expired_in_main(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                _seed_incomplete(con, 1)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                from jobsearch.enrich import FetchError
                with patch("jobsearch.enrich.enrich_one", side_effect=FetchError("HTTP 404 from url")):
                    rc = enrich_mod.main(["--db", str(db), "--limit", "3"])
                self.assertEqual(rc, 7)
                row = con.execute("SELECT status FROM jobs WHERE id=1").fetchone()
                self.assertEqual(row["status"], "expired")
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
