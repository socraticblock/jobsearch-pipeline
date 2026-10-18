"""RemoteOK adapter — the discovery-breadth source (99 current postings, full text).

Why this one first
------------------
Measured 2026-10-15 from this host: the public endpoint needs no key and no
login, and *every* posting carried a real description (shortest 542 characters,
median 3,705, longest 25,279 across 99 postings). That combination — breadth
plus text — is what the account-free promise needs, and it is the exact thing
the LinkedIn-alert path could not deliver (84 of 86 postings arrived empty).

What the terms say, recorded rather than assumed
------------------------------------------------
The endpoint's first array element is its own terms notice, quoted verbatim in
``SPEC.policy.terms_quote``. It requires a link back that is followable (not
``nofollow``) plus a named mention of Remote OK, and states access will be
suspended otherwise. Any artifact that renders these postings therefore owes an
attribution line — see ``base.required_attribution`` — and that is a build
constraint, not a nicety.

Honesty rules that shaped this mapping
--------------------------------------
* ``location`` is empty on many postings. Empty stays ``None``; a posting is
  never labelled "remote" because the source said nothing, only because the
  text actually said so (``classify_remote`` reads the text it is given).
* ``salary_min``/``salary_max`` are integers with **no currency and no period
  published in the payload**, so the stored text says exactly that rather than
  inventing "USD per year", which would be a fabricated fact about money.
* Descriptions are kept verbatim, including RemoteOK's own anti-scraping
  token line ("Please mention the word ..."). Editing source text would
  destroy the evidence the gate is required to cite.
"""

from __future__ import annotations

from .base import (
    FetchError,
    SourceListing,
    SourcePolicy,
    SourceRun,
    SourceSpec,
    fetch_json,
    html_to_text,
    now_iso,
    salary_text,
)

ENDPOINT = "https://remoteok.com/api"

SPEC = SourceSpec(
    kind="feed_api",
    name="remoteok",
    external_ref=ENDPOINT,
    homepage="https://remoteok.com",
    policy=SourcePolicy(
        terms_url="https://remoteok.com/api",
        verified_on="2026-10-15",
        attribution_required=True,
        attribution_text=(
            "Remote OK — name Remote OK as the source and link back to the posting URL "
            "with a followable (do-follow) link."
        ),
        terms_quote=(
            "API Terms of Service: Please link back (with follow, and without nofollow!) "
            "to the URL on Remote OK and mention Remote OK as a source, so we get traffic "
            "back from your site. If you do not we'll have to suspend API access.\n\n"
            "Please don't use the Remote OK logo without written permission as it's a "
            "registered trademark, please DO use our name Remote OK though."
        ),
        redistribution_note=(
            "Link-back and named mention are required conditions of API access. No explicit "
            "grant to republish postings in bulk was read; treat bulk republishing as "
            "unauthorized until verified. Logo use is excluded; the name is allowed."
        ),
    ),
)


def _listing_from(raw: dict) -> SourceListing:
    """Map one payload element. Missing stays None; nothing is inferred."""
    location = (raw.get("location") or "").strip() or None
    external_id = raw.get("id")
    salary = salary_text(raw.get("salary_min"), raw.get("salary_max"), period="")
    if salary:
        # The payload states no currency and no period: say so instead of guessing one.
        salary = f"{salary} (as published; currency and period not stated)"
    return SourceListing(
        external_job_id=str(external_id) if external_id not in (None, "") else None,
        url=raw.get("url") or None,
        title=(raw.get("position") or "").strip() or None,
        company=(raw.get("company") or "").strip() or None,
        location=location,
        description=html_to_text(raw.get("description")),
        salary_text=salary,
        published_at=raw.get("date") or None,
    )


def fetch(*, fetcher=None, timeout: int = 30) -> tuple[list[SourceListing], SourceRun]:
    """Read the board. Returns ``(listings, run)`` — a failure is a run, not an exception."""
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
    if not isinstance(payload, list):
        run.status = "failed"
        run.error = f"expected a JSON array, got {type(payload).__name__}"
        run.finished_at = now_iso()
        return [], run

    listings: list[SourceListing] = []
    for raw in payload:
        # The first element is the terms notice; it has no 'position'.
        if not isinstance(raw, dict) or not raw.get("position"):
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
