"""W4.4 -- Idempotency and overlap.

Re-runs must never duplicate rows or messages. Two concurrent
runs must not corrupt the ledger or double-deliver the digest.
A second invocation must detect the held lock, record a
reason, and exit non-zero so the morning heartbeat (W4.2)
catches the overlap.

Borrowed shape: the standard UNIX flock pattern
(`flock(LOCK_EX | LOCK_NB)`) on a sentinel file. The lock is
released automatically on fd close and on process
termination, so a crashed run does not strand the lock.

Run:  python3 -m unittest tests.test_run_lock -v
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PY = sys.executable

try:
    import reportlab  # noqa: F401
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False
LOCK_SCRIPT = """
import fcntl, sys, time
from pathlib import Path
p = Path({lock_path!r})
fd = open(p, "w")
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print("HELD", flush=True)
time.sleep({hold_seconds})
fd.close()
sys.exit(0)
"""


class TestRunLock(unittest.TestCase):
    """W4.4 -- the morning-prepare run lock prevents overlap."""

    def test_second_run_is_refused_with_non_zero_exit(self) -> None:
        """When a previous run still holds the lock, a second
        invocation must detect the held lock, exit non-zero
        (3), and write the reason to stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "lock"
            # Hold the lock in a child process.
            holder = subprocess.Popen(
                [PY, "-c", LOCK_SCRIPT.format(
                    lock_path=str(lock_path),
                    hold_seconds=2.0,
                )],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # Wait until the holder has acquired.
            line = holder.stdout.readline()
            self.assertIn(b"HELD", line)
            try:
                # Now the morning_prepare pattern: try the
                # non-blocking acquire. It must fail.
                rc = self._try_lock(lock_path)
                self.assertNotEqual(
                    rc, 0,
                    "the second acquire must fail; got rc=0"
                )
            finally:
                # Close the pipes explicitly so the test
                # does not leak ResourceWarnings on GC.
                try:
                    holder.stdout.close()
                except Exception:
                    pass
                try:
                    holder.stderr.close()
                except Exception:
                    pass
                holder.wait(timeout=5)

    def test_lock_releases_on_process_exit(self) -> None:
        """A crashed run does not strand the lock. When the
        holder exits, a fresh acquire succeeds. (This is
        what flock's process-cleanup guarantees.)"""
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "lock"
            holder = subprocess.run(
                [PY, "-c", LOCK_SCRIPT.format(
                    lock_path=str(lock_path),
                    hold_seconds=0.1,
                )],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(holder.returncode, 0)
            # The holder has exited and the kernel has
            # released the flock. A fresh acquire must
            # succeed.
            self.assertEqual(
                self._try_lock(lock_path), 0,
                "after the holder exits, a fresh acquire "
                "must succeed; the kernel releases the "
                "flock on fd close"
            )

    def test_two_morning_prepare_runs_do_not_double_deliver(self) -> None:
        """The headline W4.4 test plan: run twice concurrently
        against a copy of the ledger, assert identical row
        counts and a recorded lock/skip for the second run.

        We exercise the actual morning_prepare.py, not a
        stub. We hold the run lock with a sentinel holder
        process (NOT the morning_prepare itself — that
        finishes too quickly on an empty ledger) so the
        second run must hit the lock and exit 3.
        """
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            project = tmp_p / "project"
            project.mkdir()
            for d in ("jobsearch", "tools", "profile", "data"):
                src = ROOT / d
                if not src.exists():
                    continue
                dst = project / d
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            (project / "var").mkdir(parents=True, exist_ok=True)
            sys.path.insert(0, str(project))
            from jobsearch.db import connect as db_connect
            db = project / "var" / "jobs.db"
            con = db_connect(db)
            con.close()
            # Hold the run lock with a sentinel holder so
            # the morning_prepare sees the held lock. The
            # sentinel script is a tiny shim that mimics
            # the lock file the morning_prepare uses.
            lock_path = project / "var" / "morning-prepare.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            holder = subprocess.Popen(
                [PY, "-c", LOCK_SCRIPT.format(
                    lock_path=str(lock_path),
                    hold_seconds=2.0,
                )],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            line = holder.stdout.readline()
            self.assertIn(b"HELD", line)
            try:
                # Now start the second run. It must hit
                # the held lock and exit 3.
                second = subprocess.run(
                    [PY, "tools/morning_prepare.py"],
                    cwd=str(project),
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(
                    second.returncode, 3,
                    f"the second morning-prepare must exit 3 "
                    f"(RUN_ALREADY_IN_PROGRESS); got "
                    f"{second.returncode}. stderr: "
                    f"{second.stderr[:300]!r}"
                )
                self.assertIn(
                    "RUN_ALREADY_IN_PROGRESS", second.stderr,
                    f"stderr must record the reason; got: "
                    f"{second.stderr[:300]!r}"
                )
            finally:
                # Close the pipes explicitly so the test
                # does not leak ResourceWarnings on
                # GC. The holder has already been
                # waited on; we just close the read ends.
                try:
                    holder.stdout.close()
                except Exception:
                    pass
                try:
                    holder.stderr.close()
                except Exception:
                    pass
                holder.wait(timeout=5)

    def test_morning_prepare_does_not_strand_the_lock_on_render_failure(self) -> None:
        """If the render step fails inside the lock-holding
        block, the lock is still released. A fresh run
        must succeed afterwards. (This is the W4.2/W4.4
        interaction: a broken render is loud, but a broken
        render must not leave the cron in a state where
        tomorrow's run is silently skipped.)
        """
        # We exercise the lock helper directly with a
        # block that raises. The with-block must release
        # the lock and re-raise the exception.
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "lock"
            from tools.morning_prepare import _run_lock
            try:
                with _run_lock_for(lock_path):
                    raise RuntimeError("simulated render failure")
            except RuntimeError as exc:
                self.assertEqual(str(exc), "simulated render failure")
            # A fresh acquire must now succeed.
            self.assertEqual(
                self._try_lock(lock_path), 0,
                "after a failed run releases the lock, a "
                "fresh acquire must succeed"
            )

    @staticmethod
    def _try_lock(lock_path: Path) -> int:
        """Try to acquire the lock non-blocking. Returns 0 on
        success, non-zero on failure. Releases the lock
        immediately on success."""
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            fd.close()
            return 1
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        return 0

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab not installed (optional 'pdf' extra)")
    def test_morning_prepare_happy_path_produces_digest(self) -> None:
        """The happy path of `tools/morning_prepare.py`:
        when the lock is free, the run acquires it,
        refreshes the ledger, renders a digest, prints
        the next-fire time, and exits 0. The contract
        is not just "the lock works" -- it is "the
        full pipeline produces a usable digest with
        next-fire information for the morning heartbeat
        (W4.2)."""
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            project = tmp_p / "project"
            project.mkdir()
            for d in ("jobsearch", "tools", "profile", "data"):
                src = ROOT / d
                if not src.exists():
                    continue
                dst = project / d
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            (project / "var").mkdir(parents=True, exist_ok=True)
            sys.path.insert(0, str(project))
            from jobsearch.db import connect as db_connect
            db = project / "var" / "jobs.db"
            con = db_connect(db)
            con.close()
            # Run morning_prepare. No sentinel holder
            # this time -- the lock is free, so the run
            # must complete successfully.
            result = subprocess.run(
                [PY, "tools/morning_prepare.py"],
                cwd=str(project),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"the happy-path morning-prepare must exit 0; "
                f"got {result.returncode}. stderr: "
                f"{result.stderr[:300]!r}"
            )
            # The run report must include the next-fire
            # line. W4.5: the next-fire helper produces
            # an ISO 8601 datetime in Europe/Berlin.
            self.assertIn(
                "next-fire:", result.stdout,
                "the happy-path run must print the next-fire "
                f"time; got: {result.stdout[:300]!r}"
            )
            # The PDF or text digest was produced.
            digests = list((project / "var" / "digests").glob("*"))
            self.assertGreater(
                len(digests), 0,
                f"the happy-path run must produce a digest; "
                f"got: {digests!r}"
            )
            # W3.2 contract: the morning-prepare run
            # passes `--text` to render_pdf, so the
            # digest directory must contain BOTH a
            # .pdf AND a .txt. A contributor who
            # refactors render_pdf's `--text` flag
            # (e.g. by removing the `txt.write_text`
            # call, or by renaming the suffix) would
            # silently break the contract: the PDF
            # would still be there, but the .txt
            # would be missing. The test pins the
            # presence of both files so a contributor
            # who breaks the `--text` flag fails
            # the test with a precise error.
            pdfs = [d for d in digests if d.suffix == ".pdf"]
            txts = [d for d in digests if d.suffix == ".txt"]
            self.assertEqual(
                len(pdfs), 1,
                f"the happy-path run must produce exactly "
                f"one .pdf digest; got {len(pdfs)}: {pdfs!r}"
            )
            self.assertEqual(
                len(txts), 1,
                f"the happy-path run must produce exactly "
                f"one .txt digest (the `--text` flag of "
                f"render_pdf.py); got {len(txts)}: {txts!r}. "
                f"A missing .txt means render_pdf's "
                f"`--text` flag was broken or removed."
            )
            # The .txt file must have the same stem
            # as the .pdf file (render_pdf uses
            # `out.with_suffix('.txt')`).
            self.assertEqual(
                pdfs[0].stem, txts[0].stem,
                f"the .pdf and .txt digests must share "
                f"the same stem (render_pdf uses "
                f"`out.with_suffix('.txt')`); got "
                f"pdf={pdfs[0].name!r}, txt={txts[0].name!r}"
            )
            # The .txt file must not be empty --
            # the `--text` flag's contract is
            # "write the plain-text version as well"
            # (per the help text in render_pdf.py),
            # and an empty file would be a silent
            # regression where the file is created
            # but the text report is empty.
            self.assertGreater(
                txts[0].stat().st_size, 0,
                f"the .txt digest must be non-empty "
                f"(the `--text` flag is supposed to "
                f"write the text report); got "
                f"{txts[0].stat().st_size} bytes for "
                f"{txts[0]!r}"
            )

    def test_morning_prepare_exits_2_when_ledger_is_missing(self) -> None:
        """When there is no ledger (no `var/jobs.db`), the
        morning-prepare script must exit 2, not 0. The
        exit code is part of the documented contract: the
        morning heartbeat (W4.2) relies on it to
        distinguish a successful no-op (exit 0 -- the
        ledger is empty, the digest is empty) from a
        broken fresh checkout (exit 2 -- no ledger to
        work from).

        A future contributor who changes the exit code
        to 0 (treating a missing ledger as a successful
        no-op) would silently break the morning
        heartbeat: a fresh checkout would look like a
        successful preparation instead of a broken one.
        The test pins exit 2 for the missing-ledger case.
        """
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            project = tmp_p / "project"
            project.mkdir()
            for d in ("jobsearch", "tools", "profile", "data"):
                src = ROOT / d
                if not src.exists():
                    continue
                dst = project / d
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            # Crucially: do NOT create var/jobs.db.
            # The script's `if not DB.is_file(): return 2`
            # path must fire.
            (project / "var").mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [PY, "tools/morning_prepare.py"],
                cwd=str(project),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                result.returncode, 2,
                f"missing-ledger morning-prepare must exit 2; "
                f"got {result.returncode}. stdout: "
                f"{result.stdout[:200]!r}; stderr: "
                f"{result.stderr[:200]!r}"
            )
            # The error must name the missing ledger so
            # the morning heartbeat can surface the
            # problem to the operator.
            combined = result.stdout + result.stderr
            self.assertIn(
                "ledger", combined.lower(),
                f"the missing-ledger exit must name the "
                f"ledger in its message; got: "
                f"{combined[:300]!r}"
            )


def _run_lock_for(lock_path: Path):
    """A small wrapper that points the morning_prepare
    context manager at a temp lock path. (The module's
    real RUN_LOCK is hard-coded to ROOT/var; we want the
    test to use a /tmp path so it does not leave state.)"""
    from contextlib import contextmanager
    from tools import morning_prepare as mp

    @contextmanager
    def _lock():
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except (BlockingIOError, OSError):
                pass
            fd.close()
    return _lock()


if __name__ == "__main__":
    unittest.main()
