"""M-status: re-check open job URLs and mark expired ones.

Alert emails and source feeds point at postings that vanish: we already saw
two 404s in the first 3 fetched. A shortlist full of dead links is worse than
an empty one, so this pass HEAD-requests each open job URL and updates
``jobs.status``:

    200..299  -> open   (still there)
    404, 410  -> expired (gone for good)
    anything else (incl. network error, 403, 5xx) -> unknown (do not guess)

Stdlib only. Polite by default: one request per second.

Usage:
    python3 -m jobsearch.check_status --limit 20 --spacing 1.0
    python3 -m jobsearch.check_status --db var/jobs.db --dry-run
"""
from __future__ import annotations

import argparse
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import db as db_mod
from .sources.base import FetchError

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"
DEFAULT_UA = "jobsearch/0.1 (+local, single-user; contact via the repository)"


def _head(url: str, *, timeout: int = 20) -> int:
    if not url:
        raise FetchError("no url")
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": DEFAULT_UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        # Some hosts reject HEAD with 405; fall back to a ranged GET.
        if exc.code == 405:
            req2 = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
            try:
                with urllib.request.urlopen(req2, timeout=timeout, context=ssl.create_default_context()) as resp2:
                    return int(resp2.status)
            except urllib.error.HTTPError as exc2:
                return int(exc2.code)
            except urllib.error.URLError as exc2:
                raise FetchError(f"network error for {url}: {exc2.reason}") from exc2
        return int(exc.code)
    except urllib.error.URLError as exc:
        raise FetchError(f"network error for {url}: {exc.reason}")


def check_one(con, row, *, fetcher=_head) -> str:
    """Return the new status string; also writes it to the ledger."""
    job_id = int(row["id"])
    url = row["url"] or ""
    if not url:
        return "unknown"
    try:
        status = int(fetcher(url))
    except (FetchError, Exception) as exc:  # never crash the whole run
        new_status = "unknown"
        try:
            con.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
            con.commit()
        except Exception:
            pass
        return new_status
    if 200 <= status < 300:
        new_status = "open"
    elif status in (404, 410):
        new_status = "expired"
    else:
        new_status = "unknown"
    try:
        con.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
        con.commit()
    except Exception:
        pass
    return new_status


def _pending(con, limit, job_id):
    sql = "SELECT id, url, title, status FROM jobs WHERE status='open'"
    params: list = []
    if job_id is not None:
        sql += " AND id = ?"
        params.append(job_id)
    sql += " ORDER BY id LIMIT ?"
    params.append(limit if limit is not None else 10**9)
    return con.execute(sql, params).fetchall()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-check open job URLs and mark expired ones.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=20, help="max jobs this run")
    ap.add_argument("--spacing", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--job-id", type=int, default=None, help="check exactly this job")
    ap.add_argument("--dry-run", action="store_true", help="list what would be checked")
    args = ap.parse_args(argv)

    con = db_mod.connect(args.db)
    try:
        pending = _pending(con, args.limit, args.job_id)
        print(f"db={args.db}")
        print(f"to_check={len(pending)}")
        for row in pending:
            print(f"  would check #{row['id']} {row['url']}")
        if args.dry_run or not pending:
            return 0

        counts = {"open": 0, "expired": 0, "unknown": 0}
        for index, row in enumerate(pending):
            if index:
                time.sleep(args.spacing)
            new_status = check_one(con, row)
            counts[new_status] = counts.get(new_status, 0) + 1
            print(f"  #{row['id']} -> {new_status}")
        print(f"totals: open={counts['open']} expired={counts['expired']} unknown={counts['unknown']}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
