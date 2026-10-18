"""Source adapters — public, account-free listing feeds.

Why this package exists
-----------------------
M1/M2 proved the gate but starved it: the only wired source was a LinkedIn
alert mailbox, so 84 of 86 postings arrived with no description and the gate
could do nothing but answer "needs research". A sieve with no grain is not a
sieve.

Every adapter here obeys the same contract, and the contract is the point:

* **Account-free.** No key, no login, no OAuth. A stranger can run it.
* **Descriptions are captured when the source publishes them**, because the
  evaluation gate can only judge text it actually has.
* **Nothing is ever invented.** A field the source did not supply stays None,
  and a posting with no description keeps ``description_state='incomplete'``.
* **Terms are recorded, not assumed.** Each source carries the attribution /
  redistribution conditions that were actually read, with the date they were
  read, because "it returned HTTP 200" is not a licence.
* **Failures are evidence.** A dead endpoint produces a ``SourceRun`` with a
  status and an error, never an empty list that looks like "no jobs today".
"""

from .base import (
    FetchError,
    SourceListing,
    SourcePolicy,
    SourceRun,
    SourceSpec,
    fetch_json,
    html_to_text,
    record_run,
    required_attribution,
)
from . import arbeitnow, hn_hiring, remoteok, remotive

__all__ = [
    "FetchError",
    "SourceListing",
    "SourcePolicy",
    "SourceRun",
    "SourceSpec",
    "fetch_json",
    "html_to_text",
    "record_run",
    "required_attribution",
    "arbeitnow",
    "hn_hiring",
    "remoteok",
    "remotive",
]
