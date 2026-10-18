"""Normalisation and identity rules.

Two different problems, two different functions:

  dedupe_key()   decides whether two listings are the SAME job. Prefer the
                 source's own job id (strong, exact). Fall back to a hash of the
                 normalised (title, company, location) triple only when no id is
                 available -- and label that key weaker so mismatches are visible.
  content_hash() decides whether a listing CHANGED between sightings.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

_WS = re.compile(r"\s+")

# Legal-form suffixes stripped ONLY for the fallback key, and only as whole words.
_LEGAL_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|gmbh|bv|nv|plc|sa|sarl|ag|oy|ab|as|co|corp|corporation)\b\.?",
    re.IGNORECASE,
)

_REMOTE_PATTERNS = (
    (re.compile(r"\bfully\s+remote\b|\b100%\s+remote\b|\bremote\b", re.I), "remote"),
    (re.compile(r"\bhybrid\b|\bpartially\s+remote\b", re.I), "hybrid"),
    (re.compile(r"\bon-?site\b|\bin-?office\b|\bin\s+office\b", re.I), "onsite"),
)


def clean(value: str | None) -> str | None:
    """Collapse whitespace and normalise unicode. None/empty -> None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = _WS.sub(" ", text).strip()
    return text or None


def _key_part(value: str | None) -> str:
    """Aggressive fold used ONLY inside the fallback dedupe key."""
    text = clean(value) or ""
    text = text.casefold()
    text = _LEGAL_SUFFIX.sub(" ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _WS.sub(" ", text).strip()


def classify_remote(*texts: str | None) -> str | None:
    """Best-effort remote/hybrid/onsite from free text. None when unstated."""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    for pattern, label in _REMOTE_PATTERNS:
        if pattern.search(blob):
            return label
    return None


def dedupe_key(
    *,
    source_name: str,
    external_job_id: str | None,
    title: str | None,
    company: str | None,
    location: str | None,
) -> str:
    """Stable identity for a listing.

    Strong form  : '<source_family>:id:<external id>'  (exact, cross-source merge
                   is only safe when the id itself is globally unique, which is
                   what LinkedIn/tracking ids are).
    Weak form    : 'hash:<sha256>' of the folded triple. Labelled 'hash:' so a
                   weak identity is always distinguishable from a strong one.
    """
    if external_job_id:
        family = source_name.split("_")[0] or source_name
        return f"{family}:id:{external_job_id}"
    payload = "|".join(
        [_key_part(title), _key_part(company), _key_part(location)]
    )
    return "hash:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def content_hash(payload: dict) -> str:
    """Hash of the fields that matter for 'did this listing change?'."""
    material = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
