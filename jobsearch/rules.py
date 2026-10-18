"""The deterministic hard-requirement gate.

Policy in, verdict out. No model in the loop: every decision this module makes is
inspectable, testable and reproducible. An LLM may later *add* requirements or
*suggest* a fit score, but it can never turn a hard failure into a pass here.

Design commitments tied to the owner's brief:

  * A job may only be failed on an EXPLICIT essential requirement, and the failure
    must cite the exact quote. No quote -> no failure.
  * "3+ years with no flexibility" fails, but it is a SOFT failure: the row is
    still surfaced to the owner ("generally unsuitable", not "invisible").
  * An incomplete description NEVER fails a job; it becomes NEEDS_RESEARCH.
  * Compensation NEVER fails a job; it only ranks and flags.
  * Mentioning an unfamiliar tool is not a failure -- only an essential,
    specialist requirement is.

Scope note: this module decides; it does not fetch. Description retrieval and LLM
extraction are separate, later stages feeding the same structures.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .requirements import JobPosting, Requirement, extract

# Outcome vocabulary -- the owner's four, verbatim.
STRONG_MATCH = "strong_match"
POTENTIAL_MATCH = "potential_match"
NEEDS_RESEARCH = "needs_research"
NOT_SUITABLE = "not_suitable"

MIN_DESCRIPTION_CHARS = 80

# Specialist domains the owner does not have and does not intend to claim.
# A match here is only a FAILURE when the requirement is essential (polarity
# 'must'); a passing mention is not.
HARD_AVOID_TITLES = {
    "non_technical": ("sales", "account executive", "marketing", "growth",
                      "customer support", "customer success", "recruiter",
                      "administrative", "office manager"),
    "data_engineering_spark": ("data engineer",),
    "ml_research": ("machine learning researcher", "research scientist",
                    "ml researcher", "data scientist", "ai researcher"),
    "native_mobile": ("ios developer", "ios engineer", "android developer",
                      "android engineer", "mobile developer", "mobile engineer"),
    "game_engine_specialist": ("unity developer", "unity engineer",
                               "unreal developer", "unreal engineer",
                               "graphics programmer"),
    "php_wordpress": ("php developer", "php engineer", "laravel developer",
                      "wordpress developer", "wordpress engineer"),
    "hard_devops": ("site reliability engineer", "sre", "devops engineer",
                    "infrastructure engineer"),
}
SPECIALIST_MUST_FAIL = {"spark", "databricks", "php", "laravel", "wordpress",
                        "swift", "kotlin", "unity", "unreal"}

# "Is this a software role at all?" -- the profession test.
#
# The hard-avoid list above only names specialist things to AVOID (spark, php,
# unity...). It said nothing about a shop assistant, a bank teller or a sailor,
# and those reached the shortlist as NEEDS_RESEARCH -- because the gate may only
# fail a job on a quoted requirement, and with no description fetched there was
# nothing to quote. Observed 2026-10-13: 68 of 82 surfaced jobs were non-software
# local roles, so the shortlist read as a phone book.
#
# This is a positive test instead: a posting whose own TITLE carries no software
# signal is not a software job, and no description is needed to see that. The
# title is the employer's own summary of the role, so it is quotable evidence.
#
# Generic vocabulary, not one person's facts -- which is why it lives in code.
# The profile's own stack, aliases and languages extend it at runtime, so a
# stranger's React/Go/Rust search is not judged by this owner's word list.
_SOFTWARE_SIGNAL = re.compile(
    r"\b(engineer|engineering|developer|dev|programmer|software|architect|"
    r"full[- ]?stack|front[- ]?end|back[- ]?end|web|devops|sre|"
    r"site reliability|platform|infrastructure|cloud|database|dba|data|qa|"
    r"sdet|automation|integration|api|technical|tech|systems|sysadmin|"
    r"security|cyber|machine learning|artificial intelligence|ai|ml|agentic|"
    r"agent|blockchain|web3|smart contract|embedded|firmware|game|code|"
    r"coding|digital|it|it support)\b",
    re.I,
)


def _software_signal(title: str | None, rules: "Rules") -> str | None:
    """Return the software-role signal in a title, or None if there is none.

    W3.4: the profession-signal vocabulary is profile data with a
    documented English default. A non-English candidate can extend
    the list in profile.yaml without editing this file. The default
    below is preserved in `_DEFAULT_PROFESSION_SIGNALS` so the rule
    set still works when the profile is absent or empty.
    """
    if not title:
        return None
    low = title.casefold()
    # If the profile supplied its own list, use it; otherwise
    # the default English list.
    vocab = rules.profession_signals or _DEFAULT_PROFESSION_SIGNALS
    if any(_word_in(signal, low) for signal in vocab):
        # Return the first matching signal so the gate's
        # failure string names what was found.
        for signal in vocab:
            if _word_in(signal, low):
                return signal
    for token in rules.known_stack | rules.learnable_stack:
        if token and token in low:
            return token
    return None


def _word_in(token: str, haystack: str) -> bool:
    """True iff `token` is a whole word in `haystack`.

    The token may contain hyphens or non-ASCII letters; this
    function uses \b only for ASCII boundaries and falls back
    to substring search for non-ASCII tokens (e.g. German
    "Ingenieur" or "Softwareentwickler").
    """
    if not token:
        return False
    # If the token has any non-ASCII letter, use substring
    # search; \b does not behave reliably across Unicode scripts.
    if any(ord(c) > 127 for c in token):
        return token in haystack
    rx = re.compile(rf"\b{re.escape(token)}\b", re.I)
    return rx.search(haystack) is not None


# W3.4 default profession signals. English by design: this
# project's owner is the only person whose defaults are real,
# and the README documents the override path. A non-English
# candidate copies profile.example.yaml to profile/profile.yaml
# and adds their own `profession_signals:` list.
_DEFAULT_PROFESSION_SIGNALS = (
    "engineer", "engineering", "developer", "dev", "programmer",
    "software", "architect", "full-stack", "frontend", "backend",
    "web", "devops", "sre", "site reliability", "platform",
    "infrastructure", "cloud", "database", "dba", "data", "qa",
    "sdet", "automation", "integration", "api", "technical",
    "tech", "systems", "sysadmin", "security", "cyber",
    "machine learning", "artificial intelligence", "ai", "ml",
    "agentic", "agent", "blockchain", "web3", "smart contract",
    "embedded", "firmware", "game", "code", "coding", "digital",
    "it", "it support",
)

# Location policy. Citizenship that carries EU work authorisation satisfies
# "authorised to work in <EU country>"; it does NOT satisfy "must reside in X",
# which goes to needs_research because an employer-of-record or relocation route
# may still exist.
#
# Both the candidate's citizenship and their own local markets come from the
# profile. They are facts about a person, not about this code: hardcoding them
# here would hand every new user the previous owner's legal situation and
# silently mis-answer their work-authorisation questions.
EU_SCOPE = re.compile(r"\b(eu|europe|european union|emea)\b", re.I)
WORLD_OK = re.compile(r"\b(worldwide|anywhere|global)\b", re.I)
EU_COUNTRIES = {
    "germany", "france", "spain", "italy", "netherlands", "belgium", "poland",
    "portugal", "ireland", "sweden", "denmark", "finland", "austria", "czechia",
    "czech republic", "romania", "greece", "croatia", "estonia", "latvia",
    "lithuania", "slovakia", "slovenia", "hungary", "bulgaria", "malta", "cyprus",
    "luxembourg",
}
NON_EU_BLOCK = {
    "us", "u.s.", "usa", "united states", "canada", "australia", "india", "brazil",
    "uk", "united kingdom", "china", "japan", "singapore", "switzerland",
    "new zealand", "south africa", "uae", "united arab emirates",
}


def _is_known(tech: str, rules: "Rules") -> bool:
    known = rules.known_stack
    return (
        tech in known
        or f"{tech}s" in known
        or (tech.endswith("s") and tech[:-1] in known)
    )

_SALARY = re.compile(
    r"(?P<cur>GEL|₾|EUR|€|USD|\$|GBP|£)\s*(?P<amt>\d[\d,\.]{2,9})"
    r"|(?P<amt2>\d[\d,\.]{2,9})\s*(?P<cur2>GEL|EUR|USD|GBP)",
    re.I,
)
_CURRENCY_ALIAS = {"₾": "GEL", "€": "EUR", "$": "USD", "£": "GBP"}
# Three-letter words that appear near a salary but are not currencies. Without
# this, "5000 NET per month" would be read as being paid in NET.
_NOT_A_CURRENCY = {"NET", "GROSS", "PER", "AND", "THE", "FOR", "MON"}


@dataclass
class Rules:
    floor_net: float | None
    known_stack: set[str]
    learnable_stack: set[str]
    # Everything below is filled from the profile. The defaults are empty on
    # purpose: a default naming a real country or a real currency is the
    # previous owner's facts wearing the costume of a default, and a derivative
    # copy would inherit them without ever being told.
    #
    # `local_ok` (casefolded place names that count as the candidate's own
    # market) is here rather than in the module because it is geographic fact
    # about one person, and the gate compared it against parsed locations.
    floor_currency: str = ""
    local_ok: tuple[str, ...] = ()
    # `work_authorisation` (casefolded scopes the candidate has declared they
    # may work in: "eu", "ireland", "usa", ...). Empty means "nothing was
    # declared", which is not the same as "nothing is allowed": with an empty
    # set the gate may not claim a scope is satisfied, and it may not claim a
    # posting is out of reach either. Both would be facts about a person that
    # no input supplied. It reports NEEDS_RESEARCH instead.
    #
    # This exists because citizenship is the one thing the gate used to assume:
    # an EU-scope posting was reported as "EU scope satisfied by citizenship
    # with EU work authorisation" for every user, including users who had told
    # the profile nothing and users who are not EU citizens at all.
    work_authorisation: frozenset[str] = frozenset()
    languages_usable: tuple[str, ...] = ("english",)
    # `years_can_honestly_claim` (W3.1): the number of years of
    # professional experience the candidate can defend. None means the
    # candidate has not yet committed to a number. While None, a posting
    # that demands a years bar with no flexibility evaluates to
    # NEEDS_RESEARCH, not a drop -- deciding against missing evidence
    # is exactly the failure mode this project refuses to ship.
    years_can_honestly_claim: int | None = None
    # Where these rules were read from, or None when no profile was found and
    # the defaults above are in force. Callers use it to warn instead of
    # silently evaluating everything against an empty rule set.
    profile_path: str | None = None
    # W3.4: profession signals (lowercase title words that indicate
    # a software role in the candidate's locale). An empty tuple
    # means "use the documented English default", which is the
    # module constant _DEFAULT_PROFESSION_SIGNALS. A non-English
    # candidate sets this in profile.yaml to extend the list.
    # Borrowed shape: profile-driven vocabularies (career-ops'
    # locale tables, jobsync's per-tenant search seeds).
    profession_signals: tuple[str, ...] = ()


@dataclass
class Verdict:
    outcome: str
    surface: bool
    failed_essential: list[str] = field(default_factory=list)
    satisfied: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    hard_avoid: list[str] = field(default_factory=list)
    salary: dict = field(default_factory=dict)
    hard_failure: bool = False


# Profile skill names -> technology tokens the extractor can actually see.
# Only mappings the owner's evidence supports; nothing aspirational.
SKILL_ALIASES = {
    "typescript": ("typescript",),
    "javascript": ("javascript",),
    "react": ("react",),
    "next.js": ("next.js", "nextjs"),
    "node.js": ("node.js", "node"),
    "express": ("express",),
    "mongodb": ("mongodb",),
    "apis / integration": ("api", "rest", "graphql"),
    "automated testing": ("vitest", "jest", "testing"),
    "playwright": ("playwright",),
    "git / github": ("git",),
    "linux": ("linux",),
    "ai-agent tools and workflows": ("agents", "agent", "llm"),
    "game systems": (),
}


def load_rules(profile_path: str | Path | None = None) -> Rules:
    """Build the rule set from the owner profile, with safe defaults.

    Resolution order: an explicit argument, then the JOBSEARCH_PROFILE
    environment variable, then profile/profile.yaml beside this package. The env
    override lets a copy of this repo keep its profile outside the checkout, so
    code can be shared or updated without moving personal data.
    """
    known: set[str] = set()
    learnable: set[str] = set()
    floor: float | None = None
    currency = ""
    local_ok: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    years_value: int | None = None  # W3.1: see load_rules body for semantics
    # W3.4: default to empty so the gate falls back to the
    # module's _DEFAULT_PROFESSION_SIGNALS when the profile is
    # absent. The load body overwrites this when the profile
    # supplies a list.
    profession_signals: tuple[str, ...] = ()
    # Work authorisation: the scopes the candidate has declared. Empty means
    # nothing was declared -- see the Rules field comment for why that is
    # NEEDS_RESEARCH rather than a pass or a rejection.
    work_authorisation: frozenset[str] = frozenset()
    if profile_path:
        path = Path(profile_path).expanduser()
    else:
        env = os.environ.get("JOBSEARCH_PROFILE", "").strip()
        path = Path(env).expanduser() if env else (
            Path(__file__).resolve().parents[1] / "profile" / "profile.yaml"
        )
    if path.is_file():
        import yaml

        profile = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in profile.get("stack", []):
            skill = str(entry.get("skill", "")).strip().casefold()
            status = entry.get("status", "")
            if not skill:
                continue
            aliases = SKILL_ALIASES.get(skill, (skill,))
            if status in ("corroborated", "corroborated_weak", "private_evidence"):
                known.update(aliases)
            else:
                learnable.update(aliases)
        raw_floor = str(profile.get("compensation", {}).get("floor", ""))
        m = re.search(r"([\d,\.]+)", raw_floor.replace(",", ""))
        if m:
            try:
                floor = float(m.group(1))
            except ValueError:
                floor = None
        # The floor's currency comes from the profile too. An explicit
        # `currency:` field wins; otherwise take the first three-letter code in
        # the floor text, skipping words that look like codes but are not.
        explicit = str(profile.get("compensation", {}).get("currency", "")).strip().upper()
        if explicit:
            currency = explicit
        else:
            for code in re.findall(r"\b([A-Z]{3})\b", raw_floor):
                if code not in _NOT_A_CURRENCY:
                    currency = code
                    break

        # Local markets: the places that count as "home" for ranking. Explicit,
        # because inferring them from prose is how a gate ends up deciding that
        # a job in a country the candidate has never lived in is local.
        raw_local = (profile.get("location_and_arrangement", {}) or {}).get(
            "local_markets"
        )
        if isinstance(raw_local, (list, tuple)):
            local_ok = tuple(str(x).casefold().strip() for x in raw_local if str(x).strip())

        # Languages come from the profile, not from a default list: a default
        # would silently grant every user the ability to speak the previous
        # owner's languages, turning an essential language requirement into a
        # pass they cannot actually satisfy. Both a mapping ({english: "..."})
        # and a plain list ([english, dutch]) are accepted.
        raw_langs = profile.get("location_and_arrangement", {}).get("languages")
        if isinstance(raw_langs, dict):
            languages = tuple(str(k).casefold() for k in raw_langs if str(k).strip())
        elif isinstance(raw_langs, (list, tuple)):
            languages = tuple(str(v).casefold() for v in raw_langs if str(v).strip())

        # W3.1: years_can_honestly_claim. The owner may leave it unset;
        # the gate then returns NEEDS_RESEARCH for years-bar postings
        # instead of dropping them. We accept a top-level field or one
        # under `experience:` -- both shapes are documented in
        # profile.example.yaml.
        years_raw = profile.get("years_can_honestly_claim")
        if years_raw is None:
            years_raw = (profile.get("experience") or {}).get("years_can_honestly_claim")
        if years_raw is not None:
            try:
                parsed = int(years_raw)
                if parsed >= 0:
                    years_value = parsed
            except (TypeError, ValueError):
                pass

        # W3.4: profession signals. A non-English candidate adds
        # their own list at the top level (or under
        # `location_and_arrangement:`). Empty/absent means the
        # module's English default is used.
        raw_signals = profile.get("profession_signals")
        if raw_signals is None:
            raw_signals = (
                profile.get("location_and_arrangement", {}) or {}
            ).get("profession_signals")
        profession_signals: tuple[str, ...] = ()
        if isinstance(raw_signals, (list, tuple)):
            profession_signals = tuple(
                str(s).casefold().strip() for s in raw_signals
                if str(s).strip()
            )

        # Work authorisation: the scopes the candidate has DECLARED they may
        # work in. Read from `location_and_arrangement.authorization.
        # work_authorisation` (the documented home) or a top-level
        # `work_authorisation`. Nothing here is inferred from citizenship
        # prose, from residence, or from a country name in the profile: a
        # permission is only ever what the candidate wrote down.
        raw_auth = (
            (profile.get("location_and_arrangement", {}) or {}).get(
                "authorization", {})
        )
        raw_auth = raw_auth.get("work_authorisation") if isinstance(
            raw_auth, dict) else None
        if raw_auth is None:
            raw_auth = profile.get("work_authorisation")
        if isinstance(raw_auth, (list, tuple)):
            work_authorisation = frozenset(
                str(a).casefold().strip() for a in raw_auth if str(a).strip()
            )
        elif isinstance(raw_auth, str) and raw_auth.strip():
            work_authorisation = frozenset({raw_auth.casefold().strip()})
    return Rules(
        floor_net=floor,
        known_stack=known,
        learnable_stack=learnable,
        floor_currency=currency,
        local_ok=local_ok,
        work_authorisation=work_authorisation,
        languages_usable=languages or Rules.languages_usable,
        years_can_honestly_claim=years_value,
        profile_path=str(path) if path.is_file() else None,
        profession_signals=profession_signals,
    )


# Scopes that cover every EU country and any "EU / Europe / EMEA" posting.
# A declaration of any of these is what makes an EU-scope posting satisfiable;
# nothing else is allowed to imply it.
EU_WIDE_SCOPES = frozenset({"eu", "europe", "european union", "eea", "emea"})

# Words in a scope that carry no place meaning, so a declaration containing
# one of them must not match a posting by substring accident.
_AUTH_STOPWORDS = frozenset({"the", "and", "work", "authorisation",
                             "authorization", "permit", "visa"})


def _declared(token: str, text: str) -> bool:
    """Word-boundary containment, so 'us' never matches 'australia'."""
    return re.search(
        rf"(?<![a-z]){re.escape(token)}(?![a-z])", text
    ) is not None


def authorisation_covers(
    declared: frozenset[str], place: str, text: str
) -> bool:
    """True only when the candidate's declared authorisation covers `place`.

    `declared` comes from the profile and is the sole source of truth: an EU
    scope is satisfied because the profile says so, never because an EU country
    was named in a posting.
    """
    if not declared:
        return False
    place_cf = (place or "").casefold()
    for token in declared:
        if not token or token in _AUTH_STOPWORDS:
            continue
        if place_cf and _declared(token, place_cf):
            return True
    if EU_WIDE_SCOPES & declared:
        if EU_SCOPE.search(place or "") or EU_SCOPE.search(text or ""):
            return True
        if place_cf in EU_COUNTRIES:
            return True
    return False


def authorisation_label(declared: frozenset[str]) -> str:
    """The profile's declaration, as the digest should quote it back."""
    return ", ".join(sorted(declared)) if declared else "none declared"


def find_salary_text(text: str | None, *, limit: int = 200) -> str | None:
    """Return the posting's own pay statement, or None.

    Enrichment calls this to copy a pay line out of the text it actually
    fetched into `jobs.salary_text`, which is the field the gate ranks and
    flags from. It is a *finder*, never a converter: it returns the posting's
    words, trimmed, with no normalisation and no exchange-rate arithmetic --
    a foreign currency stays foreign so the gate can flag `needs_conversion`
    instead of inventing a rate.
    """
    if not text:
        return None
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # A line can hold several sentences; test each of them, so a pay
        # statement buried mid-paragraph is still found without dragging the
        # whole paragraph into the digest.
        parts = re.split(r"(?<=[.!?;])\s+", line) or [line]
        candidates.extend(part.strip() for part in parts if part.strip())
    for candidate in candidates:
        if _parse_salary(candidate).get("parsed"):
            return candidate[:limit]
    return None


def rules_from_profile(profile: dict | None) -> Rules:
    """Build a Rules from a profile-shaped dict.

    `load_rules` is the file-shaped entry point; this is the dict-shaped
    mirror, and every key a verdict depends on must be read HERE too. That
    matters because the callers that judge a posting from a dict -- the
    corpus runner and the demo -- each used to hand-copy this mapping, so a
    new field could be added, documented, unit-tested in isolation, and still
    never reach them. `work_authorisation` was exactly that field.
    """
    profile = profile or {}
    raw_auth = profile.get("work_authorisation")
    if isinstance(raw_auth, str):
        raw_auth = [raw_auth]
    return Rules(
        floor_net=profile.get("floor_net"),
        known_stack=set(profile.get("known_stack", [])),
        learnable_stack=set(profile.get("learnable_stack", [])),
        floor_currency=profile.get("floor_currency", ""),
        local_ok=tuple(profile.get("local_ok", [])),
        work_authorisation=frozenset(
            str(a).casefold().strip() for a in (raw_auth or []) if str(a).strip()
        ),
        languages_usable=tuple(profile.get("languages_usable", ["english"])),
        years_can_honestly_claim=profile.get("years_can_honestly_claim"),
        profession_signals=tuple(profile.get("profession_signals", ())),
    )


def _parse_salary(text: str | None) -> dict:
    if not text:
        return {}
    m = _SALARY.search(text)
    if not m:
        return {"raw": text.strip(), "parsed": False}
    cur = (m.group("cur") or m.group("cur2") or "").strip()
    amt = (m.group("amt") or m.group("amt2") or "").replace(",", "")
    cur = _CURRENCY_ALIAS.get(cur, cur).upper()
    try:
        amount = float(amt)
    except ValueError:
        return {"raw": text.strip(), "parsed": False}
    return {"raw": text.strip(), "parsed": True, "currency": cur, "amount": amount}


def _title_hits(title: str) -> list[tuple[str, str]]:
    low = title.casefold()
    hits = []
    for category, terms in HARD_AVOID_TITLES.items():
        for term in terms:
            if term in low:
                hits.append((category, term))
    return hits


def _strip_noise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def evaluate(posting: JobPosting, rules: Rules) -> Verdict:
    if not posting.requirements:
        # The candidate's own stack and languages extend the built-in
        # vocabularies, so skills and languages the original authors never
        # anticipated are still matched. The two are passed separately: mixing
        # them would make a technology word look like an unheld language.
        extract(
            posting,
            extra_terms=rules.known_stack | rules.learnable_stack,
            extra_languages=rules.languages_usable,
        )

    failed: list[str] = []
    satisfied: list[str] = []
    uncertain: list[str] = []
    notes: list[str] = []
    avoid: list[str] = []
    hard = False

    # --- 0. Is there a description at all? --------------------------------
    if len(_strip_noise(posting.description)) < MIN_DESCRIPTION_CHARS:
        notes.append(
            "description missing or too short to evaluate "
            f"({len(_strip_noise(posting.description))} chars)"
        )

    # --- 1. Hard-avoid by TITLE (the role IS the specialist thing) --------
    for category, term in _title_hits(posting.title):
        avoid.append(f"title matches hard-avoid '{term}' ({category})")
        hard = True

    # --- 1b. Is this a software role at all? ------------------------------
    # No signal in the title means not a software job, whatever a description
    # might say, and nothing needs fetching to see it. An EMPTY title is
    # unknown rather than disqualifying, so it falls through to needs_research.
    if posting.title and not _software_signal(posting.title, rules):
        failed.append(
            f"title names no software role: \"{_strip_noise(posting.title)}\""
        )
        hard = True

    # --- 2. Requirements ------------------------------------------------
    for req in posting.requirements:
        if req.kind == "experience_years":
            n = int(req.value or 0)
            flexible = req.meta.get("flexible", False)
            if req.polarity == "must" and n >= 3:
                if flexible:
                    uncertain.append(
                        f"stated {n}+ years, but the wording allows equivalent"
                        f" experience: \"{req.text}\""
                    )
                else:
                    # W3.1: the years bar is a real rule, but it requires
                    # an honest number to compare against. While that
                    # number is unset in the profile, the outcome is
                    # NEEDS_RESEARCH (a labelled "we don't know"), not
                    # NOT_SUITABLE (a verdict against the candidate).
                    # A verdict built on a missing field is the failure
                    # mode this project is built to avoid.
                    if rules.years_can_honestly_claim is None:
                        uncertain.append(
                            f"{n}+ years professional experience required with no "
                            f"flexibility: \"{req.text}\" — cannot judge without "
                            f"years_can_honestly_claim in the profile; the candidate "
                            f"has not yet committed to a number (W3.1)"
                        )
                    elif n > rules.years_can_honestly_claim:
                        failed.append(
                            f"{n}+ years professional experience required with no "
                            f"flexibility: \"{req.text}\""
                        )
                        # The owner has committed to a number, the posting
                        # demands strictly more than that, and the gate
                        # now has both sides of the comparison. A hard
                        # drop is the right verdict.
                        hard = True
                    else:
                        # The candidate's honest number meets the bar.
                        # Surface it; do not flag.
                        pass
            elif n >= 3:
                notes.append(
                    f"{n}+ years mentioned as preferred, not required: \"{req.text}\""
                )
        elif req.kind == "seniority":
            notes.append(f"seniority signal in title: '{req.value}' (deprioritise)")

        elif req.kind == "location":
            place = (req.value or "").strip().rstrip(".,;")
            place_cf = place.casefold()
            loc_kind = req.meta.get("loc_kind", "")
            declared = rules.work_authorisation
            if place_cf in rules.local_ok:
                satisfied.append(f"local market: \"{req.text}\"")
            elif loc_kind == "reside_in":
                uncertain.append(
                    f"requires residing in {place}: an EOR or relocation route may "
                    f"exist, but citizenship does not satisfy it — \"{req.text}\""
                )
            elif WORLD_OK.search(place) or WORLD_OK.search(req.text):
                satisfied.append(f"open location scope: \"{req.text}\"")
            elif authorisation_covers(declared, place, req.text):
                satisfied.append(
                    f"work authorisation declared for this scope "
                    f"({authorisation_label(declared)}): \"{req.text}\""
                )
            elif (EU_SCOPE.search(place) or EU_SCOPE.search(req.text)
                  or place_cf in EU_COUNTRIES):
                # An EU-scope posting is not evidence of an EU work
                # authorisation. It is only satisfied when the profile
                # declared one (handled above); with no declaration this is
                # missing evidence, which is NEEDS_RESEARCH, and with a
                # declaration that excludes it the posting is out of reach --
                # on the candidate's stated terms, not on an assumed
                # citizenship.
                if declared:
                    failed.append(
                        f"location outside the declared work authorisation "
                        f"({authorisation_label(declared)}): \"{req.text}\""
                    )
                    hard = True
                else:
                    uncertain.append(
                        f"location scope to verify: the profile declares no "
                        f"work authorisation for it — \"{req.text}\""
                    )
            elif place_cf in NON_EU_BLOCK:
                if declared:
                    failed.append(
                        f"location restricted to {place}, outside the declared "
                        f"work authorisation ({authorisation_label(declared)}): "
                        f"\"{req.text}\""
                    )
                    hard = True
                else:
                    uncertain.append(
                        f"location scope to verify: {place} is outside the EU "
                        f"and the profile declares no work authorisation — "
                        f"\"{req.text}\""
                    )
            else:
                uncertain.append(f"location scope to verify: \"{req.text}\"")

        elif req.kind == "language":
            lang = (req.value or "").casefold()
            if req.polarity == "must" and lang not in rules.languages_usable:
                # W3.1 / Unknown policy: an essential language the
                # candidate has not listed is a missing-evidence
                # case, not a fabricated verdict against them.
                # The candidate may be able to read the posting in
                # translation, or work through a recruiter. The
                # gate's job is to surface the signal, not invent
                # a confident answer. `needs_research` is the
                # right verdict; a hard drop here is exactly the
                # failure mode the Unknown policy was written to
                # prevent.
                uncertain.append(
                    f"essential language not in the candidate's "
                    f"languages_usable ({lang}): \"{req.text}\" — "
                    f"the candidate may still be able to apply via "
                    f"translation or a recruiter; surface the signal, "
                    f"do not invent a verdict (W3.1)"
                )
            elif lang in rules.languages_usable:
                satisfied.append(f"language available ({lang}): \"{req.text}\"")

        elif req.kind == "technology":
            tech = (req.value or "").casefold()
            if _is_known(tech, rules):
                satisfied.append(f"technology held: {tech}")
            elif req.polarity == "must" and tech in SPECIALIST_MUST_FAIL:
                # W3.2 -- No verdict without quoted evidence.
                # The failure string must cite the posting, not
                # just the technology name. The evidence field
                # is the 240-char context window the extractor
                # captured when the technology was found.
                evidence = (req.meta or {}).get("evidence", req.text)
                failed.append(
                    f"essential specialist technology not held: {tech} "
                    f"(context: \"{evidence}\")"
                )
                hard = True
            elif req.polarity == "must":
                evidence = (req.meta or {}).get("evidence", req.text)
                uncertain.append(
                    f"essential technology not evidenced in the profile: {tech} "
                    f"(context: \"{evidence}\"; learnable unless the role "
                    f"is a specialist in it)"
                )
            else:
                notes.append(f"optional technology mentioned: {tech}")

    # --- 3. Compensation (never fails) ----------------------------------
    salary = _parse_salary(posting.salary_text)
    if salary.get("parsed") and rules.floor_net:
        if salary["currency"] == rules.floor_currency:
            salary["vs_floor"] = (
                "above_floor" if salary["amount"] >= rules.floor_net
                else "below_floor"
            )
        else:
            salary["vs_floor"] = "needs_conversion"
            salary["note"] = (
                f"{salary['currency']} quoted; convert to {rules.floor_currency} net "
                f"before comparing with the {rules.floor_net:.0f} "
                f"{rules.floor_currency} net floor"
            )
    elif posting.salary_text:
        salary.setdefault("vs_floor", "unknown")
    # Carry the configured currency out to the renderer, so the digest says
    # "below the net floor" in the owner's own currency rather than in one
    # hardcoded here.
    salary.setdefault("floor_currency", rules.floor_currency)

    # --- 4. Outcome assembly --------------------------------------------
    if hard:
        outcome, surface = NOT_SUITABLE, False
    elif failed:
        # Soft-only failures: years bar. Owner said "generally unsuitable" --
        # so it fails, but visibly.
        outcome, surface = NOT_SUITABLE, True
    elif len(_strip_noise(posting.description)) < MIN_DESCRIPTION_CHARS:
        outcome, surface = NEEDS_RESEARCH, True
    elif uncertain:
        outcome, surface = NEEDS_RESEARCH, True
    else:
        if satisfied and not failed:
            enough = sum(1 for s in satisfied if s.startswith("technology held")) >= 2
            outcome = STRONG_MATCH if enough else POTENTIAL_MATCH
        else:
            outcome = NEEDS_RESEARCH
        surface = outcome != NOT_SUITABLE

    return Verdict(
        outcome=outcome, surface=surface, failed_essential=failed,
        satisfied=satisfied, uncertain=uncertain, notes=notes,
        hard_avoid=avoid, salary=salary, hard_failure=hard,
    )


def describe(verdict: Verdict) -> str:
    """One-line human summary (used by the M3 notification layer)."""
    label = {
        STRONG_MATCH: "STRONG MATCH",
        POTENTIAL_MATCH: "POTENTIAL MATCH",
        NEEDS_RESEARCH: "NEEDS RESEARCH",
        NOT_SUITABLE: "NOT SUITABLE",
    }[verdict.outcome]
    if verdict.outcome == NOT_SUITABLE and verdict.surface:
        label += " (surfaced: fail is soft)"
    return label
