"""M4 enrichment: fetch a job's posting page and store its description and
the pay statement it states, if any.

Why this exists: an alert email carries a title, a company and a location --
nothing else. With no description, `rules.py` cannot judge fit, so every job
comes back NEEDS RESEARCH and the gate is decorative. This stage fills that gap.

The pay statement is stored for the same reason: `jobs.salary_text` is what the
gate ranks and flags from, and until this stage wrote it, every posting read
"no salary published" however plainly the page stated a figure -- so the
below-floor and foreign-currency flags could never fire.

Three rules it will not bend:

  * **Never guess.** A description is stored only if it was actually retrieved.
    `description_state` stays `incomplete` otherwise, so the gate keeps saying
    NEEDS RESEARCH rather than passing a job on invented text.
  * **A rate limit is not an absence.** HTTP 429/999 raises `RateLimited`, which
    stops the run and says so. Recording "no description" when LinkedIn actually
    said "slow down" would be exactly the silent-zero failure §13 warns about.
  * **Stay off the apply path.** `/jobs/view/externalApply/` is the one job URL
    LinkedIn's robots.txt disallows; it is refused before any request is made.

Stdlib only (`urllib`), so the package keeps its zero-dependency promise and the
tests can drive it with a fake fetcher, offline.

Usage:
    python3 -m jobsearch.enrich --limit 3 --spacing 45
    python3 -m jobsearch.enrich --job-id 42 --dry-run

Exit codes: 0 done | 6 rate limited (stop, retry later) | 7 some fetch failed.
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import db as db_mod

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"
QUEUE_PATH = Path(__file__).resolve().parents[1] / "var" / "enrich-queue.jsonl"
BACKOFF_SECONDS = [45, 300, 1800, 86400]
MAX_ATTEMPTS_BEFORE_COOLDOWN = 5
# rules.py owns this threshold; importing it keeps one source of truth.
from .rules import MIN_DESCRIPTION_CHARS, find_salary_text  # noqa: E402

# LinkedIn serves the description to browser-like clients; a bot UA gets a stub.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# The real markup (verified against a live page on 2026-10-13):
#   <div class="description__text description__text--rich">
#     <section class="show-more-less-html" data-max-lines="20">
#       <div class="show-more-less-html__markup ...clamp-after-20...">
#         <p><strong>Company,</strong> a subsidiary of ... </p>
_MARKUP_RE = re.compile(
    r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', re.S
)
_SECTION_RE = re.compile(r'<div class="description__text[^"]*"[^>]*>(.*?)</section>', re.S)
# Guest pages clamp the text; worth surfacing rather than pretending it is whole.
_CLAMP_RE = re.compile(r"clamp-after-\d+")
_APPLY_PATH = "/jobs/view/externalApply/"


class RateLimited(RuntimeError):
    """LinkedIn asked us to slow down. Never treat this as 'no description'."""


class FetchError(RuntimeError):
    """The page could not be retrieved at all."""


class DisallowedURL(ValueError):
    """The URL is outside what this tool is willing to request."""


def _assert_allowed(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise DisallowedURL(f"non-http(s) scheme: {parts.scheme!r}")
    host = (parts.hostname or "").lower()
    if not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        raise DisallowedURL(f"not a LinkedIn host: {host!r}")
    if _APPLY_PATH in parts.path:
        raise DisallowedURL("robots-disallowed apply path -- never requested")


def _html_to_text(fragment: str) -> str:
    """Block-level closers become newlines; everything else is stripped."""
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", fragment)
    text = re.sub(r"(?i)</\s*(p|li|ul|ol|div|h[1-6]|section)\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    text = text.replace("\u00a0", " ")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line:
            out.append(line)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out).strip()


def extract_description(page_html: str) -> tuple[str | None, bool]:
    """Return (description_text, was_clamped).

    `was_clamped` is True when the page served a clamped guest version, so the
    caller can say "this is the first N lines" instead of implying completeness.
    """
    for pattern in (_MARKUP_RE, _SECTION_RE):
        match = pattern.search(page_html)
        if not match:
            continue
        text = _html_to_text(match.group(1))
        if text:
            return text, bool(_CLAMP_RE.search(page_html))
    return None, False


def fetch_html(url: str, *, timeout: int = 25, user_agent: str = DEFAULT_UA) -> str:
    _assert_allowed(url)
    request = Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")
    except HTTPError as exc:
        if exc.code in (429, 999):
            raise RateLimited(f"HTTP {exc.code} from {url}") from exc
        raise FetchError(f"HTTP {exc.code} from {url}") from exc
    except URLError as exc:
        raise FetchError(f"{type(exc).__name__} for {url}: {exc.reason}") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def enrich_one(con: sqlite3.Connection, row: sqlite3.Row, *, fetcher=fetch_html) -> dict:
    """Fetch one job's page and store its description. Idempotent by state."""
    job_id = int(row["id"])
    url = row["url"] or ""
    if not url:
        return {"job_id": job_id, "state": "no_url", "chars": 0, "clamped": False}

    page = fetcher(url)
    text, clamped = extract_description(page)
    if not text:
        # Retrieved the page, found no description container: say so, change
        # nothing, and do NOT mark it complete.
        return {"job_id": job_id, "state": "no_description", "chars": 0, "clamped": clamped}

    state = "complete" if len(text) >= MIN_DESCRIPTION_CHARS else "incomplete"
    # The posting's own pay statement, if it states one. This is the only
    # thing that fills `jobs.salary_text`, which the gate ranks and flags
    # from: without it every posting read "no salary published" no matter
    # what the page said, so the below-floor and foreign-currency flags
    # could never fire. It is copied verbatim, never converted.
    salary_text = find_salary_text(text)
    con.execute(
        "UPDATE jobs SET description=?, description_state=?, "
        "salary_text=COALESCE(?, salary_text) WHERE id=?",
        (text, state, salary_text, job_id),
    )
    con.commit()
    return {
        "job_id": job_id,
        "state": state,
        "chars": len(text),
        "clamped": clamped,
        "salary_text": salary_text,
    }


def _read_queue(path) -> dict[int, dict]:
    """Return {job_id: last record} from the queue file (last wins)."""
    records: dict[int, dict] = {}
    if not path.is_file():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            jid = rec.get("job_id")
            if jid is not None:
                records[int(jid)] = rec
    except OSError:
        pass
    return records


def _append_queue(path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        from datetime import datetime, timezone

        # Accept both 'Z' and offset forms.
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _eligible(record: dict | None, now) -> bool:
    """Whether a job may be fetched now, given its queue record."""
    if record is None:
        return True
    state = record.get("state", "pending")
    if state == "rate_limited":
        until = _parse_iso(record.get("rate_limited_until"))
        if until is None or now < until:
            return False
        # cooldown expired: allow one more try
        return True
    # pending
    nxt = _parse_iso(record.get("next_try_at"))
    if nxt is not None and now < nxt:
        return False
    return True


def _backoff_seconds(attempt: int) -> int:
    idx = min(max(attempt - 1, 0), len(BACKOFF_SECONDS) - 1)
    return BACKOFF_SECONDS[idx]


def _pending(con, limit, job_id, *, resume: bool = False, queue_path=None, now=None):
    sql = """
        SELECT id, url, title FROM jobs
        WHERE url LIKE '%linkedin.com/jobs/view%'
          AND (description IS NULL OR description_state != 'complete')
    """
    params: list = []
    if job_id is not None:
        sql += " AND id = ?"
        params.append(job_id)
    sql += " ORDER BY id LIMIT ?"
    params.append(limit if limit is not None else 10**9)
    rows = con.execute(sql, params).fetchall()
    if not resume:
        return rows
    if now is None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
    queue = _read_queue(queue_path if queue_path is not None else QUEUE_PATH)
    out = []
    for row in rows:
        rec = queue.get(int(row["id"]))
        if _eligible(rec, now):
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="M4: fetch job descriptions (LinkedIn guest pages, read-only)"
    )
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=3, help="max jobs this run (be polite)")
    ap.add_argument("--spacing", type=float, default=45.0, help="seconds between page fetches")
    ap.add_argument("--job-id", type=int, default=None, help="enrich exactly this job")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched")
    ap.add_argument("--resume", action="store_true",
                    help="re-attempt only incomplete jobs eligible per the retry queue")
    ap.add_argument("--queue-path", type=Path, default=QUEUE_PATH,
                    help="path to the enrich retry queue (JSONL)")
    args = ap.parse_args(argv)

    queue_path = args.queue_path
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    con = db_mod.connect(args.db)
    try:
        pending = _pending(con, args.limit, args.job_id, resume=args.resume,
                           queue_path=queue_path, now=now)
        print(f"db={args.db}")
        print(f"pending={len(pending)} (limit {args.limit})" + (" (resume)" if args.resume else ""))
        for row in pending:
            print(f"  would fetch #{row['id']} {(row['title'] or '(no title)')[:44]} {row['url']}")
        if args.dry_run or not pending:
            return 0

        done = failed = 0
        rate_limited = False
        for index, row in enumerate(pending):
            if index:
                time.sleep(args.spacing)
            try:
                result = enrich_one(con, row)
            except RateLimited as exc:
                # Record the retry in the queue; do not silently drop it.
                from datetime import timedelta

                queue = _read_queue(queue_path)
                rec = queue.get(int(row["id"]), {})
                attempt = int(rec.get("attempt", 0)) + 1
                cooldown = attempt >= MAX_ATTEMPTS_BEFORE_COOLDOWN
                now2 = datetime.now(timezone.utc)
                if cooldown:
                    until = now2 + timedelta(seconds=BACKOFF_SECONDS[-1])
                    new_rec = {
                        "job_id": int(row["id"]),
                        "attempt": attempt,
                        "state": "rate_limited",
                        "last_status": 429,
                        "rate_limited_until": until.isoformat(timespec="seconds"),
                        "next_try_at": until.isoformat(timespec="seconds"),
                    }
                else:
                    delay = _backoff_seconds(attempt)
                    nxt = now2 + timedelta(seconds=delay)
                    new_rec = {
                        "job_id": int(row["id"]),
                        "attempt": attempt,
                        "state": "pending",
                        "last_status": 429,
                        "next_try_at": nxt.isoformat(timespec="seconds"),
                    }
                _append_queue(queue_path, new_rec)
                rate_limited = True
                print(f"RATE_LIMITED #{row['id']} after {done} ok: {exc} "
                      f"(attempt {attempt}, next try {new_rec['next_try_at']})",
                      file=sys.stderr)
                # Stop the whole run on 429, as before.
                print("enriched=%d rate_limited=yes -- run again later" % done)
                return 6
            except (FetchError, DisallowedURL) as exc:
                # A 404 on the posting page means the listing is gone.
                msg = str(exc)
                if "HTTP 404" in msg:
                    try:
                        con.execute("UPDATE jobs SET status='expired' WHERE id=?", (int(row["id"]),))
                        con.commit()
                        print(f"  #{row['id']} marked expired (404)")
                    except Exception:
                        pass
                print(f"FAILED #{row['id']}: {exc}", file=sys.stderr)
                failed += 1
                continue
            clamp_note = " (clamped guest view -- may be partial)" if result["clamped"] else ""
            pay_note = "  pay=stated" if result.get("salary_text") else ""
            print(
                f"  #{result['job_id']} state={result['state']} chars={result['chars']}{clamp_note}{pay_note}"
            )
            # Clear any queue record on success.
            try:
                if queue_path.is_file():
                    # Rewrite queue without this job's records (success).
                    remaining = [r for r in _read_queue(queue_path).values()
                                 if int(r.get("job_id")) != int(row["id"])]
                    queue_path.write_text(
                        "".join(json.dumps(r, sort_keys=True) + "\n" for r in remaining),
                        encoding="utf-8",
                    )
            except OSError:
                pass
            done += 1

        print(f"enriched={done} failed={failed} rate_limited=no")
        return 7 if failed else 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
