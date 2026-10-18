"""M-source fetch orchestrator: run account-free source adapters and ingest.

One command to widen the sieve: it runs every (or one) registered adapter,
ingests the result into the ledger through the same `_upsert_listing` path
the email and adapter tests exercise, records a SourceRun per source, and
prints a summary an operator can read.

    python3 -m jobsearch.fetch                      # all sources
    python3 -m jobsearch.fetch --source remotive     # one source
    python3 -m jobsearch.fetch --db var/jobs.db --limit 50

Exit codes: 0 all sources ok (or no sources selected) | 1 at least one source
failed | 2 bad usage / missing db parent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

from . import db as db_mod
from . import ingest as ingest_mod
from .sources import arbeitnow, base, hn_hiring, remoteok, remotive

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"

REGISTRY: dict[str, Any] = {
    "remoteok": remoteok,
    "remotive": remotive,
    "arbeitnow": arbeitnow,
    "hn_hiring": hn_hiring,
}

RUN_LOG = Path(__file__).resolve().parents[1] / "var" / "source-runs.jsonl"


def _adapter_fetch(adapter, *, fetcher=None, timeout: int = 30, limit=None):
    kwargs = {"timeout": timeout}
    if limit is not None:
        kwargs["limit"] = limit
    if fetcher is not None:
        kwargs["fetcher"] = fetcher
    return adapter.fetch(**kwargs)


def run(
    *,
    db_path: Path,
    sources: list[str],
    fetcher_for: Callable[[str], object] | None = None,
    timeout: int = 30,
    record: bool = True,
    limit: int | None = None,
) -> dict:
    con = db_mod.connect(db_path)
    totals = {"sources": [], "ok": 0, "failed": 0, "new_jobs": 0, "seen_jobs": 0}
    try:
        for name in sources:
            adapter = REGISTRY[name]
            fetcher = fetcher_for(name) if fetcher_for else None
            try:
                listings, run = _adapter_fetch(adapter, fetcher=fetcher, timeout=timeout, limit=limit)
            except Exception as exc:  # never let one source abort the whole run
                run = base.SourceRun(source_name=name, started_at=base.now_iso())
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
                run.finished_at = base.now_iso()
                listings = []
            if run.status == "ok":
                stats = ingest_mod.ingest_listings(
                    con,
                    listings,
                    source_kind=adapter.SPEC.kind,
                    source_name=adapter.SPEC.name,
                    external_ref=adapter.SPEC.external_ref,
                    raw_ref=f"{adapter.SPEC.name}:{run.started_at}",
                )
                run_record = {
                    "source": name,
                    "status": run.status,
                    "http_status": run.http_status,
                    "items": run.items,
                    "items_with_description": run.items_with_description,
                    "new_jobs": stats["new_jobs"],
                    "seen_jobs": stats["seen_jobs"],
                    "skipped_unidentifiable": stats["skipped_unidentifiable"],
                    "error": run.error,
                }
                totals["new_jobs"] += stats["new_jobs"]
                totals["seen_jobs"] += stats["seen_jobs"]
                totals["ok"] += 1
            else:
                run_record = {
                    "source": name,
                    "status": run.status,
                    "http_status": run.http_status,
                    "items": run.items,
                    "items_with_description": run.items_with_description,
                    "new_jobs": 0,
                    "seen_jobs": 0,
                    "skipped_unidentifiable": 0,
                    "error": run.error,
                }
                totals["failed"] += 1
            totals["sources"].append(run_record)
            if record:
                base.record_run(run, RUN_LOG)
        return totals
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch account-free job sources into the ledger.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument(
        "--source",
        action="append",
        choices=sorted(REGISTRY),
        help="limit to one source (repeatable)",
    )
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--limit", type=int, default=None, help="max postings per source (HN only; others ignore)")
    args = ap.parse_args(argv)

    sources = args.source if args.source else sorted(REGISTRY)
    if not args.db.parent.exists():
        try:
            args.db.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"cannot create db directory {args.db.parent}: {exc}", file=sys.stderr)
            return 2
    totals = run(db_path=args.db, sources=sources, timeout=args.timeout, limit=args.limit)
    print(f"db={args.db}")
    for rec in totals["sources"]:
        print(
            f"  {rec['source']}: status={rec['status']} items={rec['items']} "
            f"with_desc={rec['items_with_description']} new={rec['new_jobs']} "
            f"seen={rec['seen_jobs']} skipped={rec['skipped_unidentifiable']}"
            + (f" error={rec['error']}" if rec["error"] else "")
        )
    print(f"totals: ok={totals['ok']} failed={totals['failed']} "
          f"new_jobs={totals['new_jobs']} seen_jobs={totals['seen_jobs']}")
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
