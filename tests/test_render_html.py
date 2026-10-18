"""Acceptance tests for the static HTML report (offline)."""
from __future__ import annotations

import html as html_mod
import tempfile
import unittest
from pathlib import Path

from jobsearch import db as db_mod
from jobsearch import render_html as rh_mod


class RenderHtmlTests(unittest.TestCase):
    def _seed(self, con):
        con.execute(
            "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,"
            "description,description_state,salary_text,status,"
            "first_seen_at,last_seen_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("k1", "AI Automation Engineer", "Example Labs", "Remote", "remote",
             "https://example.com/j/1", "We build agent workflows with TypeScript.",
             "complete", "80000", "open",
             "2026-01-01T00:00:00", "2026-01-01T00:00:00",
             "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        con.commit()

    def test_renders_valid_html_with_job(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                self._seed(con)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                html = rh_mod.render_html(con, limit=10)
                self.assertIn("<!DOCTYPE html>", html)
                self.assertIn("AI Automation Engineer", html)
                self.assertIn("</html>", html)
                # verdict string present
                self.assertTrue("potential" in html.lower() or "strong" in html.lower() or "needs" in html.lower())
            finally:
                con.close()

    def test_write_html(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            out = Path(td) / "report.html"
            con = db_mod.connect(db)
            try:
                self._seed(con)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                path = rh_mod.write_html(con, out, limit=10)
                self.assertTrue(path.is_file())
                content = path.read_text(encoding="utf-8")
                self.assertIn("<!DOCTYPE html>", content)
            finally:
                con.close()

    def test_xss_escaping(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            con = db_mod.connect(db)
            try:
                con.execute(
                    "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,"
                    "description,description_state,salary_text,status,"
                    "first_seen_at,last_seen_at,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("k2", "Backend Engineer", "<script>alert(1)</script>", "Remote", "remote",
                     "https://example.com/j/2", "desc", "complete", "100", "open",
                     "2026-01-01T00:00:00", "2026-01-01T00:00:00",
                     "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
                )
                con.commit()
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                html = rh_mod.render_html(con, limit=10)
                self.assertNotIn("<script>alert(1)</script>", html)
                self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            finally:
                con.close()

    def test_main_runs(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            out = Path(td) / "r.html"
            con = db_mod.connect(db)
            try:
                self._seed(con)
                con.close()
            except Exception:
                pass
            con = db_mod.connect(db)
            try:
                rc = rh_mod.main(["--db", str(db), "--out", str(out)])
                self.assertEqual(rc, 0)
                self.assertTrue(out.is_file())
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
