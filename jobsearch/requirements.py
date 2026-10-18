"""Requirement model + a deterministic first-pass extractor.

Two layers, deliberately separated:

  Requirement / JobPosting   the data model. This is the contract between the
                             deterministic rules engine and whatever produces
                             the requirements (today: regexes below; later: an
                             LLM adapter that fills the SAME structure).
  extract()                  a conservative, deterministic extractor that finds
                             the requirements that actually drive decisions
                             (minimum years, location restrictions, language,
                             seniority, essential technologies).

Why a deterministic extractor at all: these are the signals that can *reject* a
job, so they must be inspectable and testable without a model in the loop. The
LLM's job later is to find the requirements these patterns miss -- never to
override them silently.

Every Requirement carries `text`: the literal substring it came from. A rule that
cannot cite a quote is not allowed to fail a job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MUST_WORDS = re.compile(
    r"\b(required|requires?|must|essential|mandatory|minimum|need(?:ed)?)\b", re.I
)
NICE_WORDS = re.compile(
    r"\b(preferred|nice to have|plus|bonus|desirable|advantage|ideally)\b", re.I
)
# Wording that makes a hard years bar negotiable.
FLEX_WORDS = re.compile(
    r"\b(or equivalent|or similar|or comparable|or demonstrable|"
    r"equivalent experience|demonstrable experience|or relevant experience)\b",
    re.I,
)

TECHNOLOGIES = (
    "typescript", "javascript", "react", "next.js", "nextjs", "node.js", "node",
    "express", "mongodb", "postgres", "postgresql", "python", "sql", "graphql",
 "api", "playwright", "jest", "vitest", "docker", "git", "linux",
 "redis", "tailwind", "aws", "gcp", "azure", "terraform", "kubernetes", "k8s",
 "spark", "databricks", "php", "laravel", "wordpress", "swift", "kotlin",
 "unity", "unreal", "solidity", "ethereum", "web3", "llm", "agent",
 "openai", "langchain", "rag", "n8n", "zapier",
 )
SPECIALIST_TRAPS = {
    "spark", "databricks", "php", "laravel", "wordpress", "swift", "kotlin",
    "unity", "unreal", "kubernetes", "k8s", "terraform",
}
LANGUAGES = ("english", "dutch", "german", "french", "spanish", "norwegian",
             "russian", "italian", "polish")

_YEARS = re.compile(
    r"(?P<n>\d{1,2})\s*(?:\+|plus)?\s*(?:to\s*\d{1,2}\s*)?"
    r"(?:years?|yrs?)\b(?P<after>[^.\n]{0,80})",
    re.I,
)
# Scoped case-insensitive verbs keep the PLACE itself case-sensitive, so the
# capture stops at the first lowercase word ("Authorised to work in the United
# States required." -> "United States", not "United States required").
_LOC = (
    (re.compile(
        r"(?i:must\s+)?(?i:be\s+)?(?i:based|located|residing|resident)\s+"
        r"(?i:in)\s+(?i:the\s+)?"
        r"(?P<place>[A-Z][A-Za-z\-]*(?:\s+[A-Z][A-Za-z\-]*){0,2})"), "reside_in"),
    (re.compile(
        r"(?i:authori[sz]ed|eligible|permitted)\s+(?i:to)\s+(?i:work)\s+"
        r"(?i:in)\s+(?i:the\s+)?"
        r"(?P<place>[A-Z][A-Za-z\-]*(?:\s+[A-Z][A-Za-z\-]*){0,2})"), "work_auth"),
    (re.compile(
        r"(?i:\b)(?P<place>US|USA|U\.S\.|United States|Canada|Australia|India|"
        r"Brazil|UK|United Kingdom|EU|Europe|EMEA|Worldwide|Anywhere)"
        r"(?i:[\s-]*(?:only|based|residents?))"), "country_only"),
    (re.compile(r"(?i:\bremote\b)[^.\n]{0,25}?\((?P<place>[A-Za-z .\-]{2,20})\)"),
     "remote_scope"),
    (re.compile(r"(?i:\b)(?P<place>worldwide|anywhere|global)(?i:\b)"), "remote_scope"),
)


@dataclass
class Requirement:
    kind: str           # experience_years | location | language | seniority | technology | other
    polarity: str       # must | nice
    text: str           # the literal quote this came from
    value: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class JobPosting:
    title: str
    company: str = ""
    description: str = ""
    url: str = ""
    location: str = ""
    remote: str | None = None
    salary_text: str | None = None
    requirements: list[Requirement] = field(default_factory=list)

    @property
    def haystack(self) -> str:
        return f"{self.title}\n{self.location}\n{self.description}"


def _polarity(quote: str, fallback_box: str = "") -> str:
    if NICE_WORDS.search(quote):
        return "nice"
    if MUST_WORDS.search(quote):
        return "must"
    if NICE_WORDS.search(fallback_box):
        return "nice"
    if MUST_WORDS.search(fallback_box):
        return "must"
    return "nice"  # unmarked statements are not treated as hard requirements


def extract_years(posting: JobPosting) -> list[Requirement]:
    out: list[Requirement] = []
    for m in _YEARS.finditer(posting.haystack):
        n = int(m.group("n"))
        if n == 0 or n > 20:
            continue
        sentence = m.group(0) + m.group("after")
        flex = bool(FLEX_WORDS.search(sentence))
        out.append(
            Requirement(
                kind="experience_years", polarity=_polarity(sentence),
                text=sentence.strip(), value=str(n),
                meta={"flexible": flex},
            )
        )
    return out


def extract_location(posting: JobPosting) -> list[Requirement]:
    out: list[Requirement] = []
    seen: set[str] = set()
    for pattern, kind in _LOC:
        for m in pattern.finditer(posting.haystack):
            place = (m.group("place") or "").strip().rstrip(".,;")
            key = f"{kind}:{place.casefold()}"
            if not place or key in seen:
                continue
            seen.add(key)
            out.append(
                Requirement(kind="location", polarity="must",
                            text=m.group(0).strip(), value=place,
                            meta={"loc_kind": kind})
            )
    return out


def extract_languages(posting: JobPosting,
                      extra_terms: "set[str] | tuple[str, ...]" = ()) -> list[Requirement]:
    """Languages named in the posting.

    `extra_terms` extends the built-in vocabulary with the languages the
    candidate's own profile declares. Without it, a requirement phrased in a
    language outside LANGUAGES is not seen at all -- a silent blind spot for any
    candidate whose languages its authors did not anticipate.

    NOTE: callers must pass *language* terms here and technology terms to
    extract_technologies. Passing a technology through this function would turn
    "TypeScript required" into a language requirement, and an unheld one is a
    hard failure -- i.e. it would silently reject every posting mentioning it.
    test_portability pins this shut.
    """
    out: list[Requirement] = []
    vocabulary = list(LANGUAGES) + [
        str(t).casefold() for t in extra_terms if str(t).strip()
    ]
    for lang in vocabulary:
        m = re.search(
            rf"\b(fluent|native|professional|business|good|strong|excellent)?\s*"
            rf"{lang}\b([^.\n]{{0,40}})",
            posting.haystack, re.I,
        )
        if not m:
            continue
        quote = m.group(0).strip()
        out.append(Requirement(kind="language", polarity=_polarity(quote),
                               text=quote, value=lang))
    return out


def extract_seniority(posting: JobPosting) -> list[Requirement]:
    m = re.search(r"\b(senior|staff|principal|lead|head of|director)\b",
                  posting.title, re.I)
    if not m:
        return []
    return [Requirement(kind="seniority", polarity="must",
                        text=posting.title.strip(), value=m.group(1).casefold())]


def extract_technologies(
    posting: JobPosting, extra_terms: "set[str] | tuple[str, ...]" = ()
) -> list[Requirement]:
    """Technologies named in the posting.

    `extra_terms` extends the fixed vocabulary with tokens supplied by the
    caller -- in practice the candidate profile's own stack. Without it the
    extractor can only see the 48 technologies hardcoded in TECHNOLOGIES, so a
    candidate whose stack is outside that list would find their own skills
    invisible and every requirement mentioning them silently unanswered. Adding
    them from the profile is what makes this work for a stack its authors never
    anticipated.
    """
    out: list[Requirement] = []
    seen: set[str] = set()
    hay = posting.haystack.casefold()
    vocabulary = list(TECHNOLOGIES) + [
        str(t).casefold() for t in extra_terms if str(t).strip()
    ]
    for tech in vocabulary:
        # trailing 's?' so plurals match ("APIs", "LLMs", "agents").
        rx = rf"(?<![a-z0-9]){re.escape(tech)}s?(?![a-z0-9])"
        if not re.search(rx, hay) or tech in seen:
            continue
        seen.add(tech)
        # Capture up to 240 chars of surrounding text so the
        # gate's evidence strings can carry a real quote (W3.2
        # requires every failure to cite the posting, not a
        # single keyword).
        box = ""
        for m in re.finditer(rx, hay):
            box += " " + hay[max(0, m.start() - 120): m.end() + 120]
        # Pick the FIRST sentence from the box that actually
        # contains the technology keyword.  That sentence is
        # the real evidence: it is what the posting said about
        # the technology, in the posting's own words, and the
        # reader can verify it by reading the posting.  We
        # don't try to merge overlapping boxes -- that produces
        # a doubled-up context window the reader cannot parse.
        evidence = ""
        for s in re.split(r"(?<=[.!?])\s+", box):
            s = s.strip()
            if s and tech in s:
                evidence = s
                break
        # If no sentence contains the tech (the box may have
        # lost the keyword to a case-fold or boundary strip),
        # fall back to the technology name so the quote is
        # never zero-length.
        if not evidence:
            evidence = tech
        out.append(
            Requirement(
                kind="technology", polarity=_polarity(box),
                text=tech, value=tech,
                meta={"specialist_trap": tech in SPECIALIST_TRAPS,
                      "evidence": evidence},
            )
        )
    return out


def extract(posting: JobPosting, extra_terms: "set[str] | tuple[str, ...]" = (),
            extra_languages: "set[str] | tuple[str, ...]" = ()) -> JobPosting:
    """Populate posting.requirements deterministically (idempotent).

    `extra_terms` and `extra_languages` are kept separate on purpose: they extend
    different vocabularies, and mixing them turns a held technology into a
    failed language requirement (see extract_languages).
    """
    posting.requirements = (
        extract_seniority(posting)
        + extract_years(posting)
        + extract_location(posting)
        + extract_languages(posting, extra_languages)
        + extract_technologies(posting, extra_terms)
    )
    return posting
