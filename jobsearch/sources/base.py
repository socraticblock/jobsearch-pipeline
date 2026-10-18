"""The adapter contract: specs, policy metadata, listings, run evidence.

Design notes that are decisions, not style:

* ``SourcePolicy`` records what the source's terms actually say. RemoteOK, for
  example, requires a link back with a followable (non-nofollow) link and a
  named mention, and says it will suspend API access otherwise. That is a
  build-time constraint on any published artifact that renders its postings,
  so it is carried next to the adapter instead of living in someone's memory.
  ``verified_on`` exists because terms change and a stale reading is worse
  than a labelled one.
* ``SourceRun`` is returned even when the fetch fails. "Zero listings because
  the endpoint 500'd" and "zero listings because there was nothing new" must
  never look the same to the operator — that is the M1 fail-safe rule applied
  to the network instead of to parsing.
* ``fetch_json`` accepts an injected ``fetcher`` so the whole package is
  testable without a single byte of network, exactly as ``enrich`` does with
  its page fetcher.
"""

from __future__ import annotations

import json
import re
import html as html_mod
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..normalize import classify_remote

DEFAULT_TIMEOUT = 30
DEFAULT_UA = "jobsearch/0.1 (+local, single-user; contact via the repository)"


class FetchError(RuntimeError):
    """A source could not be read. Carries the HTTP status when there was one."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class SourcePolicy:
    """The source's actual terms, as read — not as assumed.

    ``attribution_required`` is deliberately a hard boolean: if it is True, any
    artifact that renders these postings must carry the attribution, and the
    text to carry is in ``attribution_text``.
    """

    terms_url: str
    verified_on: str                      # ISO date the terms were read
    attribution_required: bool
    attribution_text: str = ""            # exactly what must appear, if required
    terms_quote: str = ""                 # the source's own words, unedited
    redistribution_note: str = "unverified — no explicit redistribution grant read"
    poll_min_minutes: int | None = None   # a courtesy floor; None = not stated


@dataclass(frozen=True)
class SourceSpec:
    """Identity of one source. ``kind``/``name`` are the ledger's source row."""

    kind: str            # feed_api | ats_board | email_alert | manual
    name: str            # e.g. remoteok
    external_ref: str    # endpoint or board identifier
    homepage: str
    policy: SourcePolicy


@dataclass
class SourceListing:
    """One posting as the source published it. Absent means None, never a guess."""

    external_job_id: str | None = None
    url: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None       # full text only if the source supplied it
    salary_text: str | None = None
    published_at: str | None = None

    @property
    def remote(self) -> str | None:
        return classify_remote(self.location, self.title)

    @property
    def has_description(self) -> bool:
        return bool(self.description and self.description.strip())


@dataclass
class SourceRun:
    """What one fetch actually did — the evidence a diagnosis needs."""

    source_name: str
    started_at: str
    finished_at: str = ""
    status: str = "ok"                    # ok | failed
    http_status: int | None = None
    error: str = ""
    items: int = 0
    items_with_description: int = 0
    items_missing_identity: int = 0        # no external id AND no title+company
    missing_required_attribution: bool = False

    def as_dict(self) -> dict:
        return {
            "source": self.source_name,
            "status": self.status,
            "http_status": self.http_status,
            "error": self.error,
            "items": self.items,
            "items_with_description": self.items_with_description,
            "items_missing_identity": self.items_missing_identity,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str]:
    """Default fetcher. http(s) only — a source is never a file or a socket."""
    if not re.match(r"^https?://", url or "", re.I):
        raise FetchError(f"refusing non-http(s) source url: {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=ssl.create_default_context()
        ) as response:
            return int(response.status), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        raise FetchError(f"HTTP {err.code} for {url}", status=int(err.code)) from err
    except urllib.error.URLError as err:
        raise FetchError(f"network error for {url}: {err.reason}") from err


def fetch_json(url: str, *, fetcher=None, timeout: int = DEFAULT_TIMEOUT):
    """Return ``(status, parsed)`` from a JSON endpoint.

    Raises ``FetchError`` on any failure — including "the body was not JSON",
    which is the failure mode that silently produces zero listings if it is
    allowed to return an empty list instead.
    """
    get = fetcher or _http_get
    status, text = get(url, timeout) if fetcher is None else get(url)
    try:
        return status, json.loads(text)
    except (ValueError, TypeError) as err:
        raise FetchError(f"source body was not JSON: {str(err)[:120]}", status=status) from err


_BLOCK_CLOSERS = re.compile(r"(?i)</\s*(p|li|ul|ol|div|h[1-6]|section|tr)\s*>")


def html_to_text(fragment: str | None) -> str | None:
    """Block-aware HTML -> text. None in, None out; never an empty-string fake."""
    if not fragment:
        return None
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", fragment)
    text = _BLOCK_CLOSERS.sub("\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    cleaned = text.strip()
    return cleaned or None


def salary_text(minimum, maximum, *, currency: str = "", period: str = "year") -> str | None:
    """Human-readable pay band from what the source published, or None.

    No conversion, no interpolation, no assumed currency: the M1 rule that a
    number we did not read is never a number we state applies to money too.
    """
    def fmt(value) -> str | None:
        if value in (None, "", 0):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return f"{number:,}"

    low, high = fmt(minimum), fmt(maximum)
    if low is None and high is None:
        return None
    prefix = f"{currency} " if currency else ""
    suffix = f" per {period}" if period else ""
    if low and high:
        return f"{prefix}{low}–{high}{suffix}"
    return f"{prefix}{low or high}{suffix}"


def required_attribution(specs: list[SourceSpec]) -> list[str]:
    """The attribution lines an artifact rendering these sources owes.

    Terms are conditions of access, not courtesies: Remote OK states it will
    suspend API access if a consumer does not link back with a followable link
    and name it as the source. So the digest renderer asks this function rather
    than trusting whoever edits the template to remember.

    An empty list means "no source we read required it" — never "attribution is
    unnecessary". The difference matters when a new source is added.
    """
    lines: list[str] = []
    for spec in specs:
        text = spec.policy.attribution_text
        if spec.policy.attribution_required and text and text not in lines:
            lines.append(text)
    return lines


def record_run(run: SourceRun, path: str | Path) -> None:
    """Append one run to the evidence log (JSONL). Append-only, never rewritten."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run.as_dict(), sort_keys=True) + "\n")
