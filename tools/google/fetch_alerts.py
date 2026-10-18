#!/usr/bin/env python3
"""Fetch job-alert emails from a Gmail mailbox into .eml files. READ-ONLY.

Why a separate step: `jobsearch/ingest.py` never touches the network, so the
ledger stays reproducible from files on disk and a parser bug can never be
mistaken for a missing email. This tool is the only part of the pipeline that
talks to Google, and it only ever calls `messages.list` and `messages.get`. It
cannot send, label, archive or delete -- the token it uses grants
`gmail.readonly` and nothing else, and it refuses to run at all if the token it
finds carries a write scope.

Designed against a documented requirement (HANDOFF.md §13): a job that cannot
read the mailbox must FAIL LOUDLY. Reporting "no new jobs" when the mailbox was
never read is the one outcome this tool must never produce. So a healthy run
prints `mailbox=READ_OK` and distinguishes `messages_matched=0` from failure,
and every failure path exits non-zero with a reason.

Usage (the token store is selected exactly as gws.sh does it):
    JOBSEARCH_GWS_HOME=$PWD/var/gws-home-linkedin \\
        python3 tools/google/fetch_alerts.py --out var/inbox-linkedin
    python3 -m jobsearch.ingest var/inbox-linkedin

Exit codes: 0 read OK | 2 no usable token | 3 refresh failed | 4 API error |
            5 token carries a write scope (refused).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# W4.3 -- bounded retries on transient API failures, with
# exponential backoff. The retry applies to the Gmail API
# call itself, NOT to the URL fetch (CL-013: one attempt per
# source, no retry). A 429 or 5xx is a transient signal from
# the API; a 4xx (other than 429) is a hard fail.
#
# Why we never proxy-rotate, UA-spoof, or solve a challenge:
# the owner's rule (CL-014) and the platform's terms of
# service both forbid it. The retry loop is the only thing
# this code does to recover from rate limits.
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt


def _api_call_with_retry(call, *, label: str, stats: dict) -> object:
    """Call a Gmail API method with bounded exponential
    backoff. `call` is a zero-arg thunk that performs the
    API request. Returns the response on success; raises
    SystemExit(4) with a recorded reason on hard failure.

    Records `stats["retried"]` (the count of attempts that
    were 429/5xx and were retried) and
    `stats["retry_exhausted"]` (the count of attempts that
    hit the cap). The stats dict is mutated in place; the
    caller prints it in the run report.
    """
    stats.setdefault("retried", 0)
    stats.setdefault("retry_exhausted", 0)
    delay = RETRY_BASE_DELAY
    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:
            # googleapiclient.errors.HttpError has a status_code
            # attribute; urllib/socket errors do not. We catch
            # broadly so a DNS blip also gets a backoff.
            status = getattr(exc, "status_code", None)
            transient = (
                status in RETRY_STATUSES
                or isinstance(exc, (TimeoutError, ConnectionError))
            )
            if not transient:
                # Hard fail: the API told us something
                # authorization- or quota-shaped. No retry.
                raise
            stats["retried"] += 1
            if attempt >= RETRY_MAX_ATTEMPTS:
                stats["retry_exhausted"] += 1
                reason = (
                    f"API_RETRY_EXHAUSTED: {label} failed "
                    f"{attempt} times "
                    f"(last status={status}); backing off "
                    f"is no longer safe"
                )
                print(reason, file=sys.stderr)
                raise SystemExit(4)
            print(
                f"API_RETRY: {label} attempt {attempt} "
                f"failed (status={status}); sleeping "
                f"{delay:.1f}s before retry "
                f"({RETRY_MAX_ATTEMPTS - attempt} left)",
                file=sys.stderr,
            )
            time.sleep(delay)
            delay *= 2
    # unreachable; the loop either returns or raises
    raise RuntimeError("_api_call_with_retry exited without returning")

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
# Any of these means the token can change the mailbox. The owner's standing rule
# is `gmail.readonly` only, so their presence is a stop condition, not a warning.
WRITE_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.insert",
    "https://mail.google.com/",
)
# LinkedIn's alert senders. Overridable with --query for other boards.
DEFAULT_QUERY = (
    "from:(jobalerts-noreply@linkedin.com OR jobs-listings@linkedin.com "
    "OR jobs-noreply@linkedin.com)"
)


def token_path() -> Path:
    """Mirror gws.sh: JOBSEARCH_GWS_HOME wins, else the project token store."""
    home = os.environ.get("JOBSEARCH_GWS_HOME") or str(ROOT / "var" / "gws-home")
    return Path(home) / "google_token.json"


def load_credentials(path: Path):
    if not path.exists():
        print(f"NO_TOKEN: {path} does not exist", file=sys.stderr)
        print("  run tools/google/gws.sh --auth-url, then --auth-code", file=sys.stderr)
        raise SystemExit(2)

    info = json.loads(path.read_text(encoding="utf-8"))
    granted = info.get("scopes") or []

    if READONLY_SCOPE not in granted:
        print(f"WRONG_SCOPE: token does not grant {READONLY_SCOPE}", file=sys.stderr)
        print(f"  granted: {granted}", file=sys.stderr)
        raise SystemExit(5)
    offending = [s for s in granted if s in WRITE_SCOPES]
    if offending:
        print(f"REFUSED: token grants mailbox-write scope(s) {offending}", file=sys.stderr)
        print("  the owner rule is gmail.readonly only; re-auth before fetching", file=sys.stderr)
        raise SystemExit(5)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_info(info, scopes=granted)
    if not creds.valid:
        if not creds.refresh_token:
            print("NO_REFRESH_TOKEN: stored token cannot be renewed", file=sys.stderr)
            raise SystemExit(2)
        try:
            creds.refresh(Request())
        except Exception as exc:  # RefreshError and friends
            # The 7-day Testing-mode cliff surfaces exactly here. Say so: this is
            # the failure the cron job must never swallow.
            print(f"REFRESH_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("  re-consent with tools/google/gws.sh --auth-url", file=sys.stderr)
            raise SystemExit(3)
    return creds


def fetch(query: str, outdir: Path, max_results: int, dry_run: bool) -> dict:
    creds = load_credentials(token_path())

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    # W4.3: the list call gets bounded exponential backoff on
    # 429/5xx. A 4xx other than 429 (e.g. 401, 403) is a hard
    # fail: the token is broken or revoked, and retrying just
    # wastes the user's quota.
    listed = _api_call_with_retry(
        lambda: (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        ),
        label="messages.list",
        stats=stats,
    )

    ids = [m["id"] for m in listed.get("messages", [])]
    stats = {"matched": len(ids), "written": 0, "already_present": 0,
             "retried": stats.get("retried", 0),
             "retry_exhausted": stats.get("retry_exhausted", 0)}
    if dry_run:
        return stats

    outdir.mkdir(parents=True, exist_ok=True)
    for msg_id in ids:
        dest = outdir / f"{msg_id}.eml"
        if dest.exists():
            stats["already_present"] += 1
            continue
        # W4.3: the per-message get() call also gets bounded
        # backoff. We carry the retry counters in stats so the
        # run report shows how many 429s we absorbed.
        raw = _api_call_with_retry(
            lambda: (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="raw")
                .execute()
            ),
            label=f"messages.get[{msg_id}]",
            stats=stats,
        )
        payload = raw.get("raw")
        if not payload:
            # Never silently skip: a message we cannot read is a fact the caller
            # has to see, not a quiet zero.
            print(f"API_ERROR: message {msg_id} returned no raw payload", file=sys.stderr)
            raise SystemExit(4)
        dest.write_bytes(base64.urlsafe_b64decode(payload))
        # Same permissions the token store uses; the mailbox is the owner's.
        dest.chmod(0o600)
        stats["written"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Gmail alert fetch -> .eml files")
    ap.add_argument("--out", type=Path, default=ROOT / "var" / "inbox")
    ap.add_argument("--query", default=DEFAULT_QUERY)
    ap.add_argument("--max", type=int, default=50, help="cap on messages per run")
    ap.add_argument("--dry-run", action="store_true", help="count matches, write nothing")
    args = ap.parse_args(argv)

    stats = fetch(args.query, args.out, args.max, args.dry_run)
    print("mailbox=READ_OK")
    print(f"query={args.query}")
    print(f"messages_matched={stats['matched']}")
    print(f"written={stats['written']}")
    print(f"already_present={stats['already_present']}")
    # W4.3: the run report names the retry counts. A reader
    # who sees "retried=3" knows the API was unhappy; a
    # reader who sees "retry_exhausted=1" knows the run
    # was deliberately killed because the limit was hit.
    print(f"retried={stats.get('retried', 0)}")
    print(f"retry_exhausted={stats.get('retry_exhausted', 0)}")
    if not args.dry_run:
        print(f"out={args.out}")
        if stats["written"] == 0 and stats["matched"] == 0:
            # Distinct from failure on purpose: the mailbox WAS read.
            print("note=mailbox read fine; no message matched the query")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
