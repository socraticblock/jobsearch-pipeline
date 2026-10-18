"""Acceptance tests for merge_candidates (offline)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jobsearch import db as db_mod
from jobsearch import merge_candidates as mc_mod


class MergeCandidatesTests(unittest.TestCase):
    def _seed(self, con, title, company, url):
        con.execute(
            "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,"
            "description_state,status,first_seen_at,last_seen_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{title}|{company}", title, company, "Remote", "remote", url,
             "incomplete", "open", "2026-01-01T00:00:00", "2026-01-01T00:00:00",
             "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        con.commit()

    def test_finds_duplicate_group(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                self._seed(con, "Backend Engineer", "Acme", "https://a.com/1")
                self._seed(con, "Backend Engineer II", "Acme", "https://b.com/2")
                self._seed(con, "Frontend Dev", "Other", "https://c.com/3")
                groups = mc_mod.find_candidates(con, threshold=0.6)
                self.assertEqual(len(groups), 1)
                self.assertEqual(len(groups[0]), 2)
            finally:
                con.close()

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                self._seed(con, "Backend Engineer", "Acme", "https://a.com/1")
                self._seed(con, "Frontend Dev", "Other", "https://c.com/3")
                groups = mc_mod.find_candidates(con, threshold=0.6)
                self.assertEqual(len(groups), 0)
            finally:
                con.close()

    def test_main_runs(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                self._seed(con, "Backend Engineer", "Acme", "https://a.com/1")
                con.close()
            except Exception:
                pass
            con2 = db_mod.connect(db)
            try:
                rc = mc_mod.main(["--db", str(db)])
                self.assertEqual(rc, 0)
            finally:
                con2.close()


if __name__ == "__main__":
    unittest.main()
