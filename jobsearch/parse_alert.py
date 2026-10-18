"""Extract job listings from job-alert emails.

Deliberately conservative: we extract what the email text actually contains and
nothing more. A listing whose title we could not read keeps title=None -- it is
NOT inferred from the URL, the subject line, or a "similar jobs" guess. M2 marks
such rows incomplete and routes them to manual review rather than judging them.

Primary signal is the job *link*, because alert emails always carry one even when
the marketing layout changes. Text near the link supplies title/company/location.

SCOPE (M1): only LinkedIn job URLs are recognised. Other sources (recruiter
mail, company pages) are a deliberate, separate adapter -- until one exists, a
non-LinkedIn listing is simply not extracted, it is never guessed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import Message
from email.utils import parseaddr
from html.parser import HTMLParser

from .normalize import classify_remote, clean

# Job id from a LinkedIn job URL, in any of its shapes:
#   https://www.linkedin.com/jobs/view/4012345678/
#   https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=...
#   https://www.linkedin.com/jobs/view/some-slug-4012345678?refId=...
_JOB_URL = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:comm/)?jobs/view/"
    r"(?:[a-z0-9-]*-)?(?P<id>\d{6,})(?:[/?][^\s\"'<>]*)?",
    re.IGNORECASE,
)
_ANY_URL = re.compile(r"https?://[^\s\"'<>)]+")
# Separators LinkedIn uses between company and location in alert text.
_SEP = re.compile(r"\s*[·•|]\s*|\s+[—–]\s+")
_VIEW_LABEL = re.compile(r"^\s*(view|see)\s+(this\s+)?job\b.*$", re.IGNORECASE)
# LinkedIn's separator line between job blocks in the plain-text part. Splitting
# on blank lines is wrong here: real alerts separate jobs with a run of dashes,
# which is why a badge line ended up being read as the next job's title.
_BLOCK_SEP = re.compile(r"^[ \t]*[-=_*·]{5,}[ \t]*$", re.MULTILINE)
# Badges, not job titles. LinkedIn puts these inside every card and above every
# "View job" link in the text part. Reading one as a title INVENTS a job: on the
# first real alert tested, 9 of 12 extracted rows were this badge, each carrying a
# real job id, so each would have entered the ledger as a distinct job.
_BOILERPLATE = re.compile(
    r"^(?:"
    r"this company is actively hiring|"
    r"actively (?:recruiting|hiring)|"
    r"be an early applicant|be one of the first \d+ applicants?|early applicant|"
    r"promoted(?: by .*)?|easy apply|apply(?: now)?|"
    r"view (?:this )?job|see (?:this )?job|"
    r"show more|see more|unsubscribe|"
    r"your job alert.*|"
    r"you[’']?ll receive notifications.*|"
    r"(?:see|view|manage) (?:all )?(?:jobs|your job alerts).*|"
    r"\d+\s+(?:applicants?|alumni|connections?|employees?)"
    r")$",
    re.IGNORECASE,
)


def _is_boilerplate(text: str | None) -> bool:
    """True when this line is LinkedIn furniture rather than a job title."""
    value = clean(text)
    return bool(value) and _BOILERPLATE.match(value) is not None



@dataclass
class Listing:
    external_job_id: str | None = None
    url: str | None = None
    source_url: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None

    @property
    def remote(self) -> str | None:
        return classify_remote(self.location, self.title)


@dataclass
class ParsedMessage:
    message_id: str
    subject: str | None
    sender: str | None
    source_name: str
    listings: list[Listing] = field(default_factory=list)
    content_hash: str = ""

    def as_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "source_name": self.source_name,
            "listings": [vars(listing) for listing in self.listings],
        }


def _canonical_job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def _split_company_location(text: str | None) -> tuple[str | None, str | None]:
    """'Acme Systems · Manchester, United Kingdom' -> ('Acme Systems', 'Manchester, United Kingdom')."""
    text = clean(text)
    if not text:
        return None, None
    parts = [p for p in _SEP.split(text) if p.strip()]
    if len(parts) >= 2:
        return clean(parts[0]), clean(" ".join(parts[1:]))
    return (clean(parts[0]) if parts else None), None


class _AlertHTMLParser(HTMLParser):
    """Collect flat anchors and table rows as (cell text, cell href) pairs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str | None]]] = []
        self.anchors: list[tuple[str, str]] = []
        self._row: list[tuple[str, str | None]] | None = None
        self._cell: list[str] | None = None
        self._cell_href: str | None = None
        self._href: str | None = None
        self._a_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._href = a["href"]
            self._a_text = []
            if self._cell is not None and self._cell_href is None:
                self._cell_href = a["href"]
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._cell_href = None

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, clean("".join(self._a_text)) or ""))
            self._href, self._a_text = None, []
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append((clean("".join(self._cell)) or "", self._cell_href))
            self._cell = None
            self._cell_href = None
        elif tag == "tr" and self._row is not None:
            if any(text for text, _ in self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._href is not None:
            self._a_text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def _listing_for(href: str, job_id: str) -> Listing:
    return Listing(
        external_job_id=job_id,
        url=_canonical_job_url(job_id),
        source_url=href,
    )


def _listings_from_rows(rows: list[list[tuple[str, str | None]]]) -> list[Listing]:
    out: list[Listing] = []
    seen: set[str] = set()
    for row in rows:
        hits = [(text, href) for text, href in row if href and _JOB_URL.search(href)]
        if not hits:
            continue
        cell_text, href = hits[0]
        job_id = _JOB_URL.search(href).group("id")
        if job_id in seen:
            continue
        seen.add(job_id)
        listing = _listing_for(href, job_id)
        # A badge is not a title. Leave it unset so this row is routed to manual
        # review, instead of inventing a job that does not exist.
        listing.title = None if _is_boilerplate(cell_text) else clean(cell_text)
        extras = [
            t for t, h in row
            if t and (t, h) != (cell_text, href) and not _is_boilerplate(t)
        ]
        if extras:
            listing.company, listing.location = _split_company_location(" · ".join(extras))
        out.append(listing)
    return out


def _listings_from_anchors(anchors: list[tuple[str, str]]) -> list[Listing]:
    out: list[Listing] = []
    seen: set[str] = set()
    for href, text in anchors:
        m = _JOB_URL.search(href)
        if not m:
            continue
        job_id = m.group("id")
        if job_id in seen:
            continue
        seen.add(job_id)
        listing = _listing_for(href, job_id)
        listing.title = None if _is_boilerplate(text) else clean(text)
        out.append(listing)
    return out


_CARD_MARK = re.compile(r"data-test-id\s*=\s*[\"']job-card[\"']", re.IGNORECASE)


class _CardParser(HTMLParser):
    """Ordered visible text of ONE job card, plus the job ids it links to.

    LinkedIn nests three tables and several anchors per card, so a row/cell view
    merges unrelated text: the company-logo anchor carries no text of its own and
    the posting anchor wraps everything. What is stable across alert revisions is
    the ORDER of visible text inside a card: title, then "Company · Location",
    then a badge.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.texts: list[str] = []
        self.hrefs: list[str] = []
        self.alts: list[str] = []
        self._in_style = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("style", "script"):
            self._in_style += 1
            return
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag == "img" and a.get("alt"):
            self.alts.append(a["alt"])

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._in_style:
            self._in_style -= 1

    def handle_data(self, data):
        if self._in_style:
            return
        text = clean(data)
        if text and len(text) > 1:
            self.texts.append(text)


def _listings_from_cards(html: str) -> list[Listing]:
    """Per-card extraction -- the primary path.

    Only this view keeps each title next to its own company and location, and it
    is the only one that can tell a card's badge from its title.
    """
    starts = []
    for mark in _CARD_MARK.finditer(html):
        # Back up to the start of the enclosing tag: slicing inside a tag makes
        # the tag's remainder parse as visible text.
        start = html.rfind("<", 0, mark.start())
        if start >= 0:
            starts.append(start)
    if not starts:
        return []

    out: list[Listing] = []
    seen: set[str] = set()
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        card = _CardParser()
        try:
            card.feed(html[start:end])
        except Exception:
            continue

        job_id = job_href = None
        for href in card.hrefs:
            match = _JOB_URL.search(href)
            if match:
                job_id, job_href = match.group("id"), href
                break
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)

        listing = _listing_for(job_href.split("?", 1)[0], job_id)
        lines = [t for t in card.texts if not _ANY_URL.search(t) and not _is_boilerplate(t)]
        if lines:
            listing.title = lines[0]
            for candidate in lines[1:3]:
                company, location = _split_company_location(candidate)
                if company:
                    listing.company, listing.location = company, location
                    break
        if not listing.company:
            # The company logo's alt text is the fallback when the card renders no
            # "Company · Location" line. UI assets ("radar icon") are not companies.
            listing.company = next(
                (alt for alt in card.alts if not re.search(r"\bicon\b", alt, re.IGNORECASE)),
                None,
            )
        out.append(listing)
    return out


def _listings_from_html(html: str) -> list[Listing]:
    parser = _AlertHTMLParser()
    parser.feed(html)
    # Cards first. Rows and anchors run after and can only FILL fields the cards
    # left empty (see the merge in parse_message), never overwrite a good title.
    return (
        _listings_from_cards(html)
        + _listings_from_rows(parser.rows)
        + _listings_from_anchors(parser.anchors)
    )


def _context_lines(block: str) -> list[str]:
    lines = [clean(line) for line in block.splitlines()]
    return [
        line for line in lines
        if line
        and not _ANY_URL.search(line)
        and not _VIEW_LABEL.match(line)
        and not _is_boilerplate(line)
    ]


def _listings_from_text(text: str) -> list[Listing]:
    """Three layouts occur in the wild:
        title / company / View job: <url>            (link in the same block)
        title / company \\n\\n View job: <url>         (link in the NEXT block)
        title / company / location / View job: <url> (real alerts: one job per
                                                      block, blocks divided by a
                                                      run of dashes, badge line
                                                      between location and link)

    Fail-safe rule: borrow the previous block's text ONLY when this block holds
    exactly one link. If a block holds several links and no text of its own, we
    cannot tell which card each link belongs to -- so we leave title=None (the row
    is then marked incomplete) instead of attaching the wrong job's title.
    """
    # Real alerts divide jobs with dashes, not blank lines. Splitting on blank
    # lines there merges jobs and hands each link the wrong neighbour's text.
    if _BLOCK_SEP.search(text):
        blocks = _BLOCK_SEP.split(text)
    else:
        blocks = re.split(r"\n\s*\n", text)

    out: list[Listing] = []
    seen: set[str] = set()
    for i, block in enumerate(blocks):
        matches = list(_JOB_URL.finditer(block))
        for match in matches:
            job_id = match.group("id")
            if job_id in seen:
                continue
            seen.add(job_id)
            listing = _listing_for(match.group(0), job_id)
            context = _context_lines(block)
            if not context and len(matches) == 1 and i > 0:
                context = _context_lines(blocks[i - 1])
            if context:
                listing.title = context[0]
                if len(context) >= 3:
                    # Company and location are separate lines here. Without this
                    # the location came out empty on every real alert, which
                    # silently disabled the location/remote gate downstream.
                    # Take the location line alone: joining whatever follows
                    # appended badges like "Be one of the first 5 applicants".
                    listing.company = context[1]
                    listing.location = clean(context[2])
                elif len(context) >= 2:
                    listing.company, listing.location = _split_company_location(context[1])
            out.append(listing)
    return out


def _source_name(sender: str | None, subject: str | None) -> str:
    blob = f"{sender or ''} {subject or ''}".casefold()
    if "linkedin" in blob:
        return "linkedin_job_alert"
    return "email_alert"


def parse_message(raw: bytes) -> ParsedMessage:
    """Parse one raw alert email (.eml bytes) into a ParsedMessage."""
    msg: Message = message_from_bytes(raw, policy=policy.default)
    sender = parseaddr(msg.get("From", ""))[1] or None
    subject = clean(msg.get("Subject"))
    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        # Deterministic fallback so re-processing the same file is idempotent.
        message_id = "sha256:" + hashlib.sha256(raw).hexdigest()

    listings: list[Listing] = []
    index: dict[str, Listing] = {}

    def merge(items: list[Listing]) -> None:
        for item in items:
            key = item.external_job_id or (item.source_url or "")
            if key in index:
                existing = index[key]
                for attr in ("title", "company", "location"):
                    if not getattr(existing, attr) and getattr(item, attr):
                        setattr(existing, attr, getattr(item, attr))
            else:
                index[key] = item
                listings.append(item)

    # HTML is merged FIRST, deliberately. It carries the per-card structure that
    # keeps a title beside its own company and location. The plain-text part is a
    # fallback: its lines can only be guessed at, so anything it produces must not
    # outrank a card. (msg.walk() yields parts in MIME order, which put the text
    # part first and let its guess win -- so this ordering is explicit.)
    html_parts: list[Message] = []
    text_parts: list[Message] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html":
            html_parts.append(part)
        elif ctype == "text/plain":
            text_parts.append(part)

    for part in html_parts:
        merge(_listings_from_html(part.get_content()))
    for part in text_parts:
        merge(_listings_from_text(part.get_content()))

    pm = ParsedMessage(
        message_id=message_id,
        subject=subject,
        sender=sender,
        source_name=_source_name(sender, subject),
        listings=listings,
    )
    pm.content_hash = hashlib.sha256(repr(pm.as_dict()).encode("utf-8")).hexdigest()
    return pm
