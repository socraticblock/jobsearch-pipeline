"""Remotive adapter — account-free remote job feed (remote roles, full text).

Remotive publishes a public JSON API with full descriptions. Terms require a
link back to the posting URL plus a named mention of Remotive as the source,
and forbid submission to third-party aggregators (Jooble, Neuvoo, Google Jobs,
LinkedIn Jobs). Excessive requests are blocked; the API is meant to be polled
a couple of times a day at most.

Honesty rules:
* ``candidate_required_location`` is kept verbatim as ``location``. Empty
  stays None; we never rewrite \"Worldwide\" into a country.
* ``salary`` is free text as published (e.g. \"$170k - $200k\"); it is stored
  verbatim and never converted or re-stated as a number.
* Descriptions are kept verbatim (HTML converted to text).
"""
from __future__ import annotations

import re

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

ENDPOINT = "https://remotive.com/api/remote-jobs"

SPEC = SourceSpec(
    kind="feed_api",
    name="remotive",
    external_ref=ENDPOINT,
    homepage="https://remotive.com",
    policy=SourcePolicy(
        terms_url="https://remotive.com/api-documentation",
        verified_on="2026-10-17",
        attribution_required=True,
        attribution_text=(
            "Remotive — name Remotive as the source and link back to the posting "
            "URL with a followable link."
        ),
        terms_quote=(
            "Please link back to the URL found on Remotive AND mention Remotive as "
            "a source in order to Remotive to get traffic from your listing. If you "
            "don't do that, we'll terminate your API access, sorry! ... Please do "
            "not submit Remotive jobs to third Party websites, including but not "
            "limited to: Jooble, Neuvoo, Google Jobs, LinkedIn Jobs."
        ),
        redistribution_note=(
            "Link-back and named mention are required. Submission to third-party "
            "aggregators is forbidden. Excessive requests are blocked; poll at most "
            "a few times per day."
        ),
        poll_min_minutes=360,
    ),
)


def _listing_from(raw: dict) -> SourceListing:
    location = (raw.get("candidate_required_location") or "").strip() or None
    external_id = raw.get("id")
    salary = (raw.get("salary") or "").strip() or None
    return SourceListing(
        external_job_id=str(external_id) if external_id not in (None, "") else None,
        url=raw.get("url") or None,
        title=(raw.get("title") or "").strip() or None,
        company=(raw.get("company_name") or "").strip() or None,
        location=location,
        description=html_to_text(raw.get("description")),
        salary_text=salary,
        published_at=raw.get("publication_date") or None,
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

    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        run.status = "failed"
        run.error = "payload has no 'jobs' list"
        run.finished_at = now_iso()
        return [], run

    listings: list[SourceListing] = []
    for raw in jobs:
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
