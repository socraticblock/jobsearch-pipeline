"""M1 ingest: alert email (file) -> parsed listings -> deduped ledger rows.

Read-only with respect to the outside world: this module never touches Gmail.
It reads .eml files from a directory. Wiring it to Gmail is a later, separately
authorised step that must produce the same ParsedMessage shape.

Idempotency has two independent guards:
  1. messages.message_id UNIQUE      -> an email is ingested at most once
  2. jobs.dedupe_key UNIQUE + sightings UNIQUE -> a listing is stored at most once
So a re-run, a crash-and-retry, or a duplicate delivery all add zero rows.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import db as db_mod
from .normalize import content_hash, dedupe_key
from .parse_alert import ParsedMessage, parse_message

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_source(con: sqlite3.Connection, kind: str, name: str, ref: str = "") -> int:
    con.execute(
        "INSERT OR IGNORE INTO sources(kind, name, external_ref) VALUES (?,?,?)",
        (kind, name, ref),
    )
    row = con.execute(
        "SELECT id FROM sources WHERE kind=? AND name=? AND external_ref=?",
        (kind, name, ref),
    ).fetchone()
    return int(row["id"])


def ingest_message(
    con: sqlite3.Connection,
    raw: bytes,
    *,
    raw_ref: str = "",
    source_kind: str = "email_alert",
    now: str | None = None,
) -> dict:
    """Ingest one raw alert email. Returns a stats dict. Fully idempotent."""
    now = now or _now()
    pm: ParsedMessage = parse_message(raw)

    if con.execute(
        "SELECT 1 FROM messages WHERE message_id=?", (pm.message_id,)
    ).fetchone():
        return {"message_id": pm.message_id, "skipped": True, "new_jobs": 0, "seen_jobs": 0}

    source_id = _get_source(con, source_kind, pm.source_name)
    new_jobs = seen_jobs = 0

    for listing in pm.listings:
        _job_id, is_new = _upsert_listing(
            con,
            source_id=source_id,
            source_name=pm.source_name,
            listing=listing,
            now=now,
            raw_ref=raw_ref or pm.message_id,
        )
        if is_new:
            new_jobs += 1
        else:
            seen_jobs += 1

    con.execute(
        """INSERT INTO messages(message_id,source_id,subject,processed_at,
                listing_count,content_hash) VALUES (?,?,?,?,?,?)""",
        (pm.message_id, source_id, pm.subject, now, len(pm.listings), pm.content_hash),
    )
    # W4.6 -- the commit is the only place a half-written row could leak past
    # the transaction boundary, so a commit failure rolls back and re-raises
    # (shared with the adapter path in `_commit_or_rollback`).
    _commit_or_rollback(con)
    return {
        "message_id": pm.message_id, "skipped": False,
        "new_jobs": new_jobs, "seen_jobs": seen_jobs,
    }


class ListingLike(Protocol):
    """The fields every listing must expose, whatever produced it.

    Both ``parse_alert.Listing`` (email path) and ``sources.SourceListing``
    (adapter path) satisfy this, which is what lets one upsert serve both.
    """

    external_job_id: str | None
    url: str | None
    title: str | None
    company: str | None
    location: str | None

    @property
    def remote(self) -> str | None: ...


def _upsert_listing(
    con: sqlite3.Connection,
    *,
    source_id: int,
    source_name: str,
    listing: ListingLike,
    now: str,
    raw_ref: str = "",
    description: str | None = None,
    salary_text: str | None = None,
) -> tuple[int, bool]:
    """Write one listing to the ledger. Returns ``(job_id, is_new)``.

    One implementation for every source, because the rules that make the ledger
    trustworthy are properties of this function rather than of any adapter:

    * identity comes from the source's own id when it has one (strong form),
      and falls back to a labelled content hash otherwise (weak form);
    * a field is only ever filled when it is currently blank -- a known value
      is never overwritten with a guess;
    * a description is stored only if one was actually supplied, and then
      ``description_state`` becomes ``complete``. Without one it stays
      ``incomplete`` and the gate answers NEEDS_RESEARCH, which is the correct
      answer to "we have no text to judge".

    ``listing`` is duck-typed: both the email parser's ``Listing`` and a source
    adapter's ``SourceListing`` satisfy it.
    """
    key = dedupe_key(
        source_name=source_name,
        external_job_id=listing.external_job_id,
        title=listing.title,
        company=listing.company,
        location=listing.location,
    )
    chash = content_hash(
        {
            "title": listing.title,
            "company": listing.company,
            "location": listing.location,
            "url": listing.url,
            "remote": listing.remote,
        }
    )
    has_description = bool(description and description.strip())
    state = "complete" if has_description else "incomplete"

    row = con.execute("SELECT * FROM jobs WHERE dedupe_key=?", (key,)).fetchone()
    if row is None:
        con.execute(
            """INSERT INTO jobs(dedupe_key,title,company,location,remote,url,
                    external_job_id,description,description_state,salary_text,status,
                    first_seen_at,last_seen_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'open',?,?,?,?)""",
            (
                key, listing.title, listing.company, listing.location,
                listing.remote, listing.url, listing.external_job_id,
                description if has_description else None, state, salary_text,
                now, now, now, now,
            ),
        )
        job_id = int(con.execute(
            "SELECT id FROM jobs WHERE dedupe_key=?", (key,)
        ).fetchone()["id"])
        is_new = True
    else:
        job_id = int(row["id"])
        is_new = False
        # Fill blanks only; never overwrite a known value with a guess.
        updates, params = [], []
        for col, val in (
            ("title", listing.title), ("company", listing.company),
            ("location", listing.location), ("remote", listing.remote),
            ("url", listing.url), ("salary_text", salary_text),
        ):
            if val and not row[col]:
                updates.append(f"{col}=?")
                params.append(val)
        if has_description and not row["description"]:
            updates.extend(("description=?", "description_state=?"))
            params.extend((description, "complete"))
        updates.append("last_seen_at=?")
        params.append(now)
        params.append(job_id)
        con.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id=?", params)

    con.execute(
        """INSERT OR IGNORE INTO sightings(job_id,source_id,seen_at,content_hash,raw_ref)
           VALUES (?,?,?,?,?)""",
        (job_id, source_id, now, chash, raw_ref),
    )
    return job_id, is_new


def _commit_or_rollback(con: sqlite3.Connection) -> None:
    """Commit, or roll the transaction back so the ledger stays pre-failure."""
    try:
        con.commit()
    except sqlite3.OperationalError:
        try:
            con.rollback()
        except sqlite3.OperationalError:
            # No transaction open, or rollback itself failed; the original
            # error is the actionable one, so re-raise that.
            pass
        raise


def ingest_listings(
    con: sqlite3.Connection,
    listings: list,
    *,
    source_kind: str,
    source_name: str,
    external_ref: str = "",
    raw_ref: str = "",
    now: str | None = None,
) -> dict:
    """Ingest listings supplied by a source adapter (no email involved).

    Deliberately the same ledger rules as the email path -- ``_upsert_listing``
    is shared -- so the two paths cannot drift apart on identity, dedupe or the
    fill-blanks-only rule.

    A listing the adapter could not identify at all (no external id AND no
    title+company) is **skipped and counted**, never written as an anonymous
    ledger row: a row nobody can identify is a row nobody can act on.
    """
    now = now or _now()
    source_id = _get_source(con, source_kind, source_name, external_ref)
    new_jobs = seen_jobs = skipped = 0

    for listing in listings:
        if not (getattr(listing, "external_job_id", None)
                or (getattr(listing, "title", None) and getattr(listing, "company", None))):
            skipped += 1
            continue
        _job_id, is_new = _upsert_listing(
            con,
            source_id=source_id,
            source_name=source_name,
            listing=listing,
            now=now,
            raw_ref=raw_ref or f"{source_name}:{now}",
            description=getattr(listing, "description", None),
            salary_text=getattr(listing, "salary_text", None),
        )
        if is_new:
            new_jobs += 1
        else:
            seen_jobs += 1

    _commit_or_rollback(con)
    return {
        "source": source_name, "listings": len(listings),
        "new_jobs": new_jobs, "seen_jobs": seen_jobs,
        "skipped_unidentifiable": skipped,
        "unique_jobs": con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
    }


def ingest_directory(
    con: sqlite3.Connection, email_dir: str | Path, *, source_kind: str = "email_alert"
) -> dict:
    """Ingest every *.eml in a directory, oldest filename first."""
    email_dir = Path(email_dir)
    files = sorted(email_dir.glob("*.eml"))
    totals = {"files": len(files), "skipped": 0, "new_jobs": 0, "seen_jobs": 0}
    for path in files:
        stats = ingest_message(
            con, path.read_bytes(), raw_ref=path.name, source_kind=source_kind
        )
        if stats["skipped"]:
            totals["skipped"] += 1
        totals["new_jobs"] += stats["new_jobs"]
        totals["seen_jobs"] += stats["seen_jobs"]
    totals["unique_jobs"] = con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    return totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 ingest: .eml directory -> job ledger")
    ap.add_argument("email_dir", type=Path)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args(argv)
    con = db_mod.connect(args.db)
    try:
        stats = ingest_directory(con, args.email_dir)
        print(f"db={args.db}")
        for k in ("files", "skipped", "new_jobs", "seen_jobs", "unique_jobs"):
            print(f"  {k}: {stats[k]}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
