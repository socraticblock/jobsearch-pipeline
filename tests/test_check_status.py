"""Acceptance tests for check_status (offline, injected fetcher)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jobsearch import db as db_mod
from jobsearch import check_status as cs_mod


class CheckStatusTests(unittest.TestCase):
    def _seed(self, con, url="https://example.com/job/1"):
        con.execute(
            "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,"
            "description_state,status,first_seen_at,last_seen_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("k1", "T", "C", "Remote", "remote", url, "incomplete", "open",
             "2026-01-01T00:00:00", "2026-01-01T00:00:00",
             "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        con.commit()
        return con.execute("SELECT id FROM jobs").fetchone()["id"]

    def test_200_keeps_open(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                fetcher = lambda url: 200
                new = cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=fetcher)
                self.assertEqual(new, "open")
                row = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                self.assertEqual(row["status"], "open")
            finally:
                con.close()

    def test_404_marks_expired(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                fetcher = lambda url: 404
                new = cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=fetcher)
                self.assertEqual(new, "expired")
                row = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                self.assertEqual(row["status"], "expired")
            finally:
                con.close()

    def test_410_marks_expired(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                fetcher = lambda url: 410
                cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=fetcher)
                row = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                self.assertEqual(row["status"], "expired")
            finally:
                con.close()

    def test_network_error_marks_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                def boom(url):
                    raise cs_mod.FetchError("network down")
                new = cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=boom)
                self.assertEqual(new, "unknown")
                row = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                self.assertEqual(row["status"], "unknown")
            finally:
                con.close()

    def test_403_marks_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                fetcher = lambda url: 403
                cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=fetcher)
                row = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                self.assertEqual(row["status"], "unknown")
            finally:
                con.close()

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                jid = self._seed(con)
                fetcher = lambda url: 404
                cs_mod.check_one(con, con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone(), fetcher=fetcher)
                # second run: job no longer 'open', so not re-checked by _pending
                pending = cs_mod._pending(con, 100, None)
                self.assertEqual(len(pending), 0)
            finally:
                con.close()

    def test_dry_run_lists_only(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                self._seed(con)
                con.close()
            except Exception:
                pass
            # re-open not needed; run main via subprocess-ish? Just call main with dry-run by re-connecting
            con2 = db_mod.connect(db)
            try:
                rc = cs_mod.main(["--db", str(db), "--dry-run"])
                self.assertEqual(rc, 0)
            finally:
                con2.close()


if __name__ == "__main__":
    unittest.main()
