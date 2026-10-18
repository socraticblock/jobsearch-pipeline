"""Hacker News "Who is hiring" adapter — account-free, full text.

The monthly "Ask HN: Who is hiring?" thread is posted by the `whoishiring`
user. Each top-level comment is a job posting in free-form text, usually
shaped like ``Company | url | location | REMOTE/ONSITE | Full Time`` followed
by a description. We fetch the latest thread and its top-level comments.

Honesty rules:
* No login, no key. The HN Firebase API is public.
* Title is rarely a job title in these posts, so it stays None rather than
  being invented from the first line.
* Company is the first pipe-separated segment of the first line, when present;
  otherwise None.
* Location is not parsed from free text (too unreliable); the full posting
  text is kept in ``description`` so the gate can read whatever location the
  poster stated.
* A thread with zero readable comments is a failed run, not "no jobs today".
"""
from __future__ import annotations

import json
import re

from .base import (
    FetchError,
    SourceListing,
    SourcePolicy,
    SourceRun,
    SourceSpec,
    html_to_text,
    now_iso,
)

USER_URL = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

SPEC = SourceSpec(
    kind="feed_api",
    name="hn_hiring",
    external_ref="https://hacker-news.firebaseio.com/v0",
    homepage="https://news.ycombinator.com",
    policy=SourcePolicy(
        terms_url="https://github.com/HackerNews/API",
        verified_on="2026-10-17",
        attribution_required=False,
        attribution_text="",
        terms_quote="",
        redistribution_note=(
            "unverified — the HN API is public and unauthenticated; no explicit "
            "redistribution terms were read. Attribute HN as the source when "
            "republishing."
        ),
        poll_min_minutes=60,
    ),
)


def _default_limit(limit):
    if limit is None:
        return 50
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return 50
    return n if n > 0 else 50


def _fetch_json(fetcher, url):
    status, text = fetcher(url)
    try:
        return status, json.loads(text)
    except (ValueError, TypeError) as err:
        raise FetchError(f"source body was not JSON: {str(err)[:120]}", status=status) from err


def fetch(*, fetcher=None, timeout: int = 30, limit=None):
    get = fetcher
    if get is None:
        def get(url):
            import urllib.request, ssl
            req = urllib.request.Request(url, headers={"User-Agent": "jobsearch/0.1"})
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
                return int(resp.status), resp.read().decode("utf-8", "replace")

    started = now_iso()
    run = SourceRun(source_name=SPEC.name, started_at=started)
    cap = _default_limit(limit)

    # 1. find the latest "Who is hiring" thread.
    thread_id = None
    try:
        status, profile = _fetch_json(get, USER_URL)
        for sid in (profile.get("submitted") or [])[:10]:
            try:
                st, item = _fetch_json(get, ITEM_URL.format(id=sid))
            except FetchError:
                continue
            if isinstance(item, dict) and "who is hiring" in (item.get("title") or "").lower():
                thread_id = sid
                break
    except FetchError as err:
        run.status = "failed"
        run.http_status = err.status
        run.error = str(err)
        run.finished_at = now_iso()
        return [], run

    if thread_id is None:
        run.status = "failed"
        run.error = "could not find a 'Who is hiring' thread"
        run.finished_at = now_iso()
        return [], run

    # 2. fetch the thread to get its comment ids.
    try:
        status, thread = _fetch_json(get, ITEM_URL.format(id=thread_id))
    except FetchError as err:
        run.status = "failed"
        run.http_status = err.status
        run.error = str(err)
        run.finished_at = now_iso()
        return [], run
    run.http_status = status

    kids = thread.get("kids") or []
    kids = kids[:cap]

    listings: list[SourceListing] = []
    for kid in kids:
        try:
            st, comment = _fetch_json(get, ITEM_URL.format(id=kid))
        except FetchError:
            continue
        if not isinstance(comment, dict) or comment.get("type") != "comment":
            continue
        text = html_to_text(comment.get("text"))
        if not text:
            continue
        # company = first pipe segment of the first line
        first_line = text.splitlines()[0] if text else ""
        company = None
        if "|" in first_line:
            company = first_line.split("|", 1)[0].strip() or None
        elif first_line:
            company = first_line.strip()[:80] or None
        listing = SourceListing(
            external_job_id=str(comment.get("id")) if comment.get("id") is not None else None,
            url=f"https://news.ycombinator.com/item?id={comment.get('id')}",
            title=None,
            company=company,
            location=None,
            description=text,
            salary_text=None,
            published_at=None,
        )
        listings.append(listing)
        if listing.has_description:
            run.items_with_description += 1
        if not (listing.external_job_id or (listing.title and listing.company)):
            run.items_missing_identity += 1

    run.items = len(listings)
    if run.items == 0:
        run.status = "failed"
        run.error = "thread had no readable comments"
    run.finished_at = now_iso()
    return listings, run
