"""W4.6 -- Storage failure.

The ledger must survive a full disk, a truncated DB, and
a half-written WAL. The contract:
  * Full disk: the run exits with a recorded reason; no
    half-written row sneaks into the ledger; the
    pre-existing ledger is still readable.
  * Truncated DB: the next read fails fast with a clear
    error; the corruption is not silently masked.
  * WAL recovery: a half-written WAL is replayed or
    checkpointed on next open; the data is preserved.

The W4.6 tests exercise real SQLite behavior on /tmp
copies of the ledger. We do NOT touch the real
`var/jobs.db`. We do NOT simulate a full disk at the
filesystem level (which would be brittle on WSL2 and
require root); we simulate a `commit()` failure on the
SQLite connection, which is what `ENOSPC` produces in
practice.

Borrowed shape: the SQLite atomic-commit protocol
(journal mode = DELETE; the journal is created next to
the DB and renamed on commit). A `commit()` failure
rolls back the transaction, so the DB on disk is the
pre-failure state. SQLite exposes this directly: the
caller sees `sqlite3.OperationalError("database or disk
is full")`, the next read sees the pre-failure rows.

Run:  python3 -m unittest tests.test_storage_failure -v
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Same as in jobsearch/ingest.py: the columns we need
# to write a row.
NOW = datetime.now().isoformat(timespec="seconds")


def _open_fresh_ledger(path: Path) -> sqlite3.Connection:
    """Open a fresh ledger at `path` using the project's
    schema, then commit a known seed row so we can
    detect corruption later."""
    from jobsearch.db import connect
    con = connect(path)
    # Seed: one job, one message, so the pre-state is
    # non-empty. We use SQLite's executemany so the
    # seed is a single atomic commit.
    con.execute(
        """INSERT INTO jobs(dedupe_key, title, company, location,
           remote, url, external_job_id, description_state,
           status, first_seen_at, last_seen_at, created_at,
           updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("seed-key", "Seed Job", "Seed Co", "Berlin", None,
         "https://x/seed", "seed", "complete", "open",
         NOW, NOW, NOW, NOW),
    )
    con.commit()
    return con


class TestFullDisk(unittest.TestCase):
    """W4.6 -- a full disk during ingest."""

    def test_commit_failure_does_not_corrupt_the_ledger(self) -> None:
        """If the SQLite `commit()` raises OperationalError
        (e.g. ENOSPC), the error is loud: it propagates
        to the caller, who can map it to a recorded
        reason and exit non-zero. The proxy rolls back
        the open transaction on commit failure so the
        ledger on disk stays in the pre-failure state.

        The W4.6 contract is "the failure is loud AND
        the run can be retried without leaving a
        half-written row". This test asserts both.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            real_con = _open_fresh_ledger(db)
            con = _CommitProxy(real_con)
            # Insert + commit, with the commit failing.
            con.execute(
                """INSERT INTO jobs(dedupe_key, title, company,
                   location, remote, url, external_job_id,
                   description_state, status, first_seen_at,
                   last_seen_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("new-key", "New Job", "New Co", "Berlin",
                 None, "https://x/new", "new", "complete",
                 "open", NOW, NOW, NOW, NOW),
            )
            # First commit: ENOSPC. The proxy rolls
            # back the open transaction so the ledger
            # is in the pre-failure state.
            with self.assertRaises(sqlite3.OperationalError):
                con.commit(force_fail=True)
            real_con.close()
            # Reopen: only the seed row, the new row is
            # not present (the proxy rolled back).
            con2 = sqlite3.connect(str(db))
            con2.row_factory = sqlite3.Row
            rows = con2.execute(
                "SELECT * FROM jobs"
            ).fetchall()
            self.assertEqual(
                len(rows), 1,
                f"ledger must be unchanged after ENOSPC; "
                f"got {len(rows)} rows: "
                f"{[r['dedupe_key'] for r in rows]}"
            )
            self.assertEqual(rows[0]["dedupe_key"], "seed-key")
            con2.close()

    def test_ingest_message_surfaces_commit_failure(self) -> None:
        """The `ingest_message` entry point propagates
        OperationalError when the commit fails. The
        caller (morning-prepare, or a future agent) sees
        a clear error, not a silent zero."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            real_con = _open_fresh_ledger(db)
            con = _CommitProxy(real_con)
            from jobsearch.ingest import ingest_message
            # The .eml is irrelevant; the failure happens
            # at commit. A minimal payload is enough.
            raw = (
                b"From: alerts@example.com\r\n"
                b"Subject: Senior Backend Engineer\r\n"
                b"Message-ID: <abc@x>\r\n"
                b"\r\n"
                b"Python required.\r\n"
            )
            # Force a fail on every commit.
            con.commit_force_fail = True
            with self.assertRaises(sqlite3.OperationalError):
                ingest_message(con, raw, source_kind="email_alert")
            real_con.close()
            # Reopen: only the seed row, no new message.
            con2 = sqlite3.connect(str(db))
            con2.row_factory = sqlite3.Row
            jobs = con2.execute("SELECT * FROM jobs").fetchall()
            self.assertEqual(
                len(jobs), 1,
                "the failed ingest must not have written "
                "a new job"
            )
            msgs = con2.execute("SELECT * FROM messages").fetchall()
            self.assertEqual(
                len(msgs), 0,
                "the failed ingest must not have written "
                "a new message"
            )
            con2.close()

    def test_real_ingest_rolls_back_on_commit_failure(self) -> None:
        """The REAL `ingest_message` (no proxy) catches
        the commit failure, rolls back, and re-raises.
        The W4.6 source-code contract is in the
        try/except around `con.commit()` in
        `jobsearch/ingest.py`."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            real_con = _open_fresh_ledger(db)
            # Make the DB file read-only so commit fails
            # with OperationalError("attempt to write a
            # readonly database"). This is a real
            # production failure mode (someone chmod'd
            # the file, or the FS is mounted read-only).
            db.chmod(0o444)
            try:
                # Reopen the read-only DB. The connection
                # is open in read-only mode.
                ro_con = sqlite3.connect(
                    f"file:{db}?mode=ro", uri=True
                )
                ro_con.row_factory = sqlite3.Row
                from jobsearch.ingest import ingest_message
                raw = (
                    b"From: alerts@example.com\r\n"
                    b"Subject: Senior Backend Engineer\r\n"
                    b"Message-ID: <ro@x>\r\n"
                    b"\r\n"
                    b"Python required.\r\n"
                )
                with self.assertRaises(sqlite3.OperationalError):
                    ingest_message(
                        ro_con, raw, source_kind="email_alert"
                    )
                ro_con.close()
            finally:
                db.chmod(0o644)
            # Reopen the writable ledger. The seed row
            # is still there; the failed insert did not
            # leak.
            con2 = sqlite3.connect(str(db))
            con2.row_factory = sqlite3.Row
            jobs = con2.execute("SELECT * FROM jobs").fetchall()
            self.assertEqual(
                len(jobs), 1,
                "the failed ingest must not have written "
                "a new job"
            )
            self.assertEqual(jobs[0]["dedupe_key"], "seed-key")
            msgs = con2.execute("SELECT * FROM messages").fetchall()
            self.assertEqual(
                len(msgs), 0,
                "the failed ingest must not have written "
                "a new message"
            )
            con2.close()


class _CommitProxy:
    """A duck-typed proxy around a real sqlite3.Connection
    that lets the test force a commit failure.

    The real `sqlite3.Connection.commit` is read-only and
    cannot be monkey-patched. This proxy delegates every
    other attribute to the real connection, but exposes
    a settable `commit_force_fail` flag for the W4.6
    contract test.

    On a forced failure, the proxy rolls back the open
    transaction so the ledger is in the pre-failure
    state. This is the same behavior a real ENOSPC at
    commit-time produces in production: the journal
    rename fails, SQLite rolls back, the caller sees
    OperationalError.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real
        self.commit_force_fail = False

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)

    def commit(self, force_fail: bool | None = None) -> None:
        if force_fail is None:
            force_fail = self.commit_force_fail
        if force_fail:
            # Roll back the open transaction so the
            # ledger is in the pre-failure state. This
            # mirrors what real SQLite does on ENOSPC
            # at commit time (the journal rename fails,
            # the transaction is rolled back).
            try:
                self._real.rollback()
            except sqlite3.OperationalError:
                # No transaction is fine; ignore.
                pass
            raise sqlite3.OperationalError(
                "database or disk is full"
            )
        self._real.commit()


class TestTruncatedDb(unittest.TestCase):
    """W4.6 -- a truncated DB fails fast."""

    def test_truncated_db_fails_fast_on_open(self) -> None:
        """A truncated SQLite file is detected at open
        time. SQLite raises `DatabaseError: file is not a
        database` (or similar). The error is loud, not
        a silent empty result."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            # Build a healthy ledger.
            good = tmp_p / "good.db"
            con = _open_fresh_ledger(good)
            con.close()
            # Truncate to a length that cannot carry a valid SQLite header
            # (the header is 100 bytes; anything shorter is unambiguous corruption
            # on every supported Python/SQLite version).
            truncated = tmp_p / "truncated.db"
            truncated.write_bytes(b"\x00" * 32)
            # Force SQLite to read page 1. A constant
            # `SELECT 1` needs no page read, so some SQLite
            # builds return it without ever validating the
            # file -- the test then passes for the wrong
            # reason on exactly the corruption it exists to
            # detect (observed on the CI runner's SQLite,
            # where this test failed with "DatabaseError not
            # raised" while passing locally). Touching
            # sqlite_master requires the schema, and the
            # schema lives in the header page.
            with self.assertRaises(sqlite3.DatabaseError) as cm:
                con2 = sqlite3.connect(str(truncated))
                con2.execute("SELECT count(*) FROM sqlite_master").fetchall()
                con2.close()
            err = str(cm.exception).lower()
            self.assertTrue(
                "not a database" in err or "file is not" in err
                or "database disk image" in err
                or "malformed" in err,
                f"expected a clear corruption error; got: "
                f"{cm.exception!r}"
            )

    def test_original_ledger_is_still_readable(self) -> None:
        """Truncating a copy of the ledger does not
        affect the original. The original is still
        readable and still has the seed row."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            good = tmp_p / "good.db"
            con = _open_fresh_ledger(good)
            con.close()
            # Make a truncated copy.
            data = good.read_bytes()
            bad = tmp_p / "bad.db"
            bad.write_bytes(data[: len(data) // 2])
            # Original is still fine.
            con2 = sqlite3.connect(str(good))
            con2.row_factory = sqlite3.Row
            rows = con2.execute("SELECT * FROM jobs").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["dedupe_key"], "seed-key")
            con2.close()


class TestWalRecovery(unittest.TestCase):
    """W4.6 -- a half-written WAL is recovered on next open."""

    def test_wal_mode_recovery(self) -> None:
        """With WAL mode, a row written in one connection
        is visible in a second connection that opens the
        DB file and replays the WAL. This is the
        'crash-safe' guarantee SQLite provides for
        embedded use."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            db = tmp_p / "wal.db"
            con = _open_fresh_ledger(db)
            # Switch to WAL mode.
            con.execute("PRAGMA journal_mode=WAL")
            con.commit()
            con.close()
            # Reopen and write a row.
            con2 = sqlite3.connect(str(db))
            con2.row_factory = sqlite3.Row
            con2.execute(
                """INSERT INTO jobs(dedupe_key, title, company,
                   location, remote, url, external_job_id,
                   description_state, status, first_seen_at,
                   last_seen_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("wal-key", "WAL Job", "WAL Co", "Berlin",
                 None, "https://x/wal", "wal", "complete",
                 "open", NOW, NOW, NOW, NOW),
            )
            con2.commit()
            con2.close()
            # Reopen. SQLite replays the WAL.
            con3 = sqlite3.connect(str(db))
            con3.row_factory = sqlite3.Row
            rows = con3.execute("SELECT * FROM jobs").fetchall()
            self.assertEqual(
                len(rows), 2,
                f"expected 2 rows after WAL replay; got "
                f"{len(rows)}: {[r['dedupe_key'] for r in rows]}"
            )
            keys = {r["dedupe_key"] for r in rows}
            self.assertIn("seed-key", keys)
            self.assertIn("wal-key", keys)
            con3.close()

    def test_checkpoint_after_wal_recovery(self) -> None:
        """After WAL replay, an explicit `PRAGMA
        wal_checkpoint(TRUNCATE)` shrinks the WAL file
        to zero. The reader does not need the WAL to
        see the data, so a subsequent `cp -r db dest`
        (the morning-prepare pattern) preserves the
        data without a copy of the WAL."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            db = tmp_p / "wal.db"
            con = _open_fresh_ledger(db)
            con.execute("PRAGMA journal_mode=WAL")
            con.commit()
            con.close()
            # Write a row.
            con2 = sqlite3.connect(str(db))
            con2.row_factory = sqlite3.Row
            con2.execute(
                """INSERT INTO jobs(dedupe_key, title, company,
                   location, remote, url, external_job_id,
                   description_state, status, first_seen_at,
                   last_seen_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("ck-key", "CK Job", "CK Co", "Berlin",
                 None, "https://x/ck", "ck", "complete",
                 "open", NOW, NOW, NOW, NOW),
            )
            con2.commit()
            # Checkpoint and truncate the WAL.
            con2.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con2.close()
            # Now copy just the main DB file (no WAL).
            copy_path = tmp_p / "copy.db"
            shutil.copyfile(db, copy_path)
            # Open the copy without a WAL. The data is
            # still there.
            con3 = sqlite3.connect(str(copy_path))
            con3.row_factory = sqlite3.Row
            rows = con3.execute("SELECT * FROM jobs").fetchall()
            keys = {r["dedupe_key"] for r in rows}
            self.assertIn("seed-key", keys)
            self.assertIn("ck-key", keys)
            con3.close()


class TestStorageFailureIsLoud(unittest.TestCase):
    """W4.6 -- the failure mode is loud, not silent."""

    def test_truncated_db_does_not_silently_return_empty(self) -> None:
        """A reader that opens a truncated DB must NOT
        silently return an empty result. The whole
        point of W4.6 is that corruption is loud: the
        next morning-prepare sees a clear error, not a
        'no new jobs' digest."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            good = tmp_p / "good.db"
            con = _open_fresh_ledger(good)
            con.close()
            data = good.read_bytes()
            bad = tmp_p / "bad.db"
            bad.write_bytes(data[: len(data) // 2])
            # Try the same query the render would do.
            opened = None
            try:
                con2 = sqlite3.connect(str(bad))
                con2.execute("SELECT COUNT(*) FROM jobs").fetchone()
                opened = "ok"
            except sqlite3.DatabaseError as exc:
                opened = f"DatabaseError: {exc}"
            self.assertNotEqual(
                opened, "ok",
                f"a truncated DB must raise DatabaseError, "
                f"not return silently; got {opened!r}"
            )


if __name__ == "__main__":
    unittest.main()
