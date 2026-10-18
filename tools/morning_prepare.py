"""Morning preparation: refresh the ledger, then render the shortlist PDF.

This is the script half of the daily delivery. It is deliberately dumb: it runs
the existing ingest and the existing renderer, prints where the PDF landed and
what it contains, and stops. Delivering the file is a separate agent step, the
same split as `notify.py` (which renders but cannot send).

Why a script rather than a longer prompt: a cron agent that has to remember the
right commands will eventually run the wrong ones. Here the pipeline is fixed and
the only variable is the date.

Exit codes: 0 prepared (even if the PDF is empty), 2 nothing to work from,
3 another run is already in progress (W4.4: a second invocation must not
silently double-deliver; it must shout and exit non-zero so the morning
heartbeat catches the overlap).
"""

from __future__ import annotations

import fcntl
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The tools/ tree has no __init__.py, so we cannot
# `from tools.render_pdf import ...` like a normal package.
# We add tools/ to sys.path and import the module directly.
sys.path.insert(0, str(ROOT / "tools"))
from render_pdf import main as render_main  # noqa: E402
from next_fire import next_fire  # noqa: E402

DB = ROOT / "var" / "jobs.db"
# W4.4 -- the run lock. Two morning-prepare runs must never
# overlap. The lock is a flock on a sentinel file in var/;
# the second invocation detects the held lock, records the
# reason, and exits non-zero (3) so the morning heartbeat
# catches the overlap.
RUN_LOCK = ROOT / "var" / "morning-prepare.lock"


@contextmanager
def _run_lock():
    """Acquire an exclusive non-blocking lock on the run
    sentinel. If the lock is held by another process, the
    second caller exits 3 with a recorded reason.

    The lock is held for the duration of the with-block
    and released on exit. flock is released automatically
    when the file descriptor is closed (end of the
    with-block) and on process termination (the kernel
    reclaims the fd), so a crashed run does not strand
    the lock.
    """
    RUN_LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = open(RUN_LOCK, "w")
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, OSError):
            # The lock is held by another process. We do
            # NOT close `fd` here: closing it would trip
            # the contextmanager generator-exit cleanup
            # with `ValueError: I/O operation on closed
            # file`, which would mask the real
            # BlockingIOError. The finally clause below
            # closes the fd cleanly.
            pass
        if not acquired:
            # Re-raise the BlockingIOError so the caller's
            # `try/except (BlockingIOError, OSError)`
            # block can map it to a recorded reason and
            # exit 3.
            raise BlockingIOError(
                f"another run holds the lock at {RUN_LOCK}"
            )
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except (BlockingIOError, OSError):
                pass
        fd.close()


def refresh_ledger() -> str:
    """Ingest any local alert mail. Idempotent: re-reading changes nothing."""
    inboxes = sorted(p for p in (ROOT / "var").glob("inbox*") if p.is_dir())
    notes = []
    for inbox in inboxes:
        proc = subprocess.run(
            [sys.executable, "-m", "jobsearch.ingest", str(inbox), "--db", str(DB)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        last = (proc.stdout or proc.stderr or "").strip().splitlines()
        notes.append(f"{inbox.name}: {last[-1] if last else f'exit {proc.returncode}'}")
    if not inboxes:
        notes.append("no local inbox directories — ledger unchanged")
    return "; ".join(notes)


def main() -> int:
    if not DB.is_file():
        print(f"no ledger at {DB}", file=sys.stderr)
        return 2

    # W4.4 -- the run lock. If another morning-prepare is
    # already in progress (e.g. a previous run got stuck),
    # shout and exit non-zero. This is the half that makes
    # the heartbeat (W4.2) see the overlap.
    try:
        with _run_lock():
            return _do_run()
    except (BlockingIOError, OSError):
        print(
            "RUN_ALREADY_IN_PROGRESS: another morning-prepare "
            "is holding the run lock; refusing to start a second "
            "run. If the first run is stuck, remove "
            f"{RUN_LOCK.relative_to(ROOT)} and re-run.",
            file=sys.stderr,
        )
        return 3


def _do_run() -> int:
    print(f"morning-prepare {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"refresh: {refresh_ledger()}")

    stamp = datetime.now().strftime("%Y-%m-%d")
    out = ROOT / "var" / "digests" / f"jobsearch-{stamp}.pdf"
    rc = render_main(["--db", str(DB), "--out", str(out), "--include-unsuitable",
                      "--text"])
    if rc != 0:
        print(f"render failed (exit {rc})", file=sys.stderr)
        return rc

    # W4.5 -- the next fire time. The morning heartbeat
    # (W4.2) prints this so an operator who reads the
    # log knows when the next run is expected, including
    # across a DST boundary (the helper handles the
    # spring/fall transition correctly).
    nxt = next_fire(datetime.now().astimezone())
    print(f"next-fire: {nxt.isoformat(timespec='seconds')}")

    print(f"PDF: {out}")
    print(f"TEXT: {out.with_suffix('.txt')}")
    print("Deliver the PDF to the owner. Do not re-run the pipeline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
