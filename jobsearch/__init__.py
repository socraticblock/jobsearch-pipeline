"""jobsearch — M1 read-only job-alert ingestion core.

Design constraints:
  * stdlib only (sqlite3 / email / hashlib / html.parser / json / dataclasses).
    Fewer dependencies = smaller audit surface for a component that will later
    sit next to Gmail credentials.
  * Never invents data. A field we could not read is recorded as unknown
    (NULL) and the listing is marked incomplete -- never filled plausibly.
  * Idempotent by construction: every write path is guarded by a uniqueness
    key, so a re-run or a crash-and-retry adds zero rows.
"""

__all__ = ["db", "normalize", "parse_alert", "ingest"]
__version__ = "0.1.0"
