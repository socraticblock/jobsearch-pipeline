"""Arbeitnow adapter — account-free EU job board (full text).

Arbeitnow publishes a public JSON API with full descriptions and a remote
flag. No key or login is required. No explicit terms or redistribution
conditions were published in the payload, so attribution is recorded as
unverified rather than assumed.

Honesty rules:
* ``remote`` is a string (\"True\"/\"False\") in the payload. When it is
  \"True\" the source's own word is carried into the stored location text so
  ``classify_remote`` can read it; the city, when published, is kept too.
* ``tags`` and ``job_types`` arrive as stringified Python lists. They are
  parsed defensively and joined into the description only when present; nothing
  is invented when parsing fails.
* ``created_at`` is a Unix timestamp (seconds); it is converted to an ISO-8601
  string. A missing or unparseable value stays None rather than becoming 0.
"""
from __future__ import annotations

import ast
import datetime

from .base import (
    FetchError,
    SourceListing,
    SourcePolicy,
    SourceRun,
    SourceSpec,
    fetch_json,
    html_to_text,
    now_iso,
)

ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"

SPEC = SourceSpec(
    kind="feed_api",
    name="arbeitnow",
    external_ref=ENDPOINT,
    homepage="https://www.arbeitnow.com",
    policy=SourcePolicy(
        terms_url="https://www.arbeitnow.com/api/job-board-api",
        verified_on="2026-10-17",
        attribution_required=False,
        attribution_text="",
        terms_quote="",
        redistribution_note=(
            "unverified — no explicit redistribution or attribution terms were read "
            "in the payload or on the endpoint; treat bulk republishing as "
            "unauthorized until verified."
        ),
        poll_min_minutes=None,
    ),
)


def _to_iso(value) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        return datetime.datetime.fromtimestamp(int(value), tz=datetime.timezone.utc).isoformat(
            timespec="seconds"
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _parse_stringified_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return [value.strip()]
    if isinstance(parsed, list):
        return [str(x).strip() for x in parsed if str(x).strip()]
    return [str(parsed).strip()]


def _listing_from(raw: dict) -> SourceListing:
    location_raw = (raw.get("location") or "").strip() or None
    remote_flag = str(raw.get("remote")).strip().lower()
    if remote_flag == "true":
        location = f"{location_raw} remote" if location_raw else "remote"
    else:
        location = location_raw

    description = html_to_text(raw.get("description"))
    tags = _parse_stringified_list(raw.get("tags"))
    job_types = _parse_stringified_list(raw.get("job_types"))
    extra_lines: list[str] = []
    if tags:
        extra_lines.append("Tags: " + ", ".join(tags))
    if job_types:
        extra_lines.append("Job types: " + ", ".join(job_types))
    if extra_lines and description:
        description = description + "\n\n" + "\n".join(extra_lines)
    elif extra_lines and not description:
        description = "\n".join(extra_lines)

    external_id = raw.get("slug")
    return SourceListing(
        external_job_id=str(external_id).strip() if external_id not in (None, "") else None,
        url=raw.get("url") or None,
        title=(raw.get("title") or "").strip() or None,
        company=(raw.get("company_name") or "").strip() or None,
        location=location,
        description=description,
        salary_text=None,
        published_at=_to_iso(raw.get("created_at")),
    )


def fetch(*, fetcher=None, timeout: int = 30) -> tuple[list[SourceListing], SourceRun]:
    started = now_iso()
    run = SourceRun(source_name=SPEC.name, started_at=started)
    try:
        status, payload = fetch_json(ENDPOINT, fetcher=fetcher, timeout=timeout)
    except FetchError as err:
        run.status = "failed"
        run.http_status = err.status
        run.error = str(err)
        run.finished_at = now_iso()
        return [], run

    run.http_status = status
    if not isinstance(payload, dict):
        run.status = "failed"
        run.error = f"expected a JSON object, got {type(payload).__name__}"
        run.finished_at = now_iso()
        return [], run

    data = payload.get("data")
    if not isinstance(data, list):
        run.status = "failed"
        run.error = "payload has no 'data' list"
        run.finished_at = now_iso()
        return [], run

    listings: list[SourceListing] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        listing = _listing_from(raw)
        listings.append(listing)
        if listing.has_description:
            run.items_with_description += 1
        if not (listing.external_job_id or (listing.title and listing.company)):
            run.items_missing_identity += 1

    run.items = len(listings)
    run.finished_at = now_iso()
    return listings, run
