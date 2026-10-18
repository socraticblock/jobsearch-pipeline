"""SQLite schema and connection handling for the job ledger.

One database file holds the whole pipeline: sources, canonical jobs, per-source
sightings, processed messages, decisions (M3) and an outbound action audit (M5).
Creating the M3/M5 tables now avoids a migration later; nothing writes to them
until those milestones are authorised.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Where a listing came from. One row per (kind, name, external_ref).
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,          -- email_alert | recruiter_email | manual | company_page
    name         TEXT NOT NULL,          -- e.g. linkedin_job_alert
    external_ref TEXT NOT NULL DEFAULT '',
    UNIQUE (kind, name, external_ref)
);

-- The canonical listing. dedupe_key is the stable identity across sources.
CREATE TABLE IF NOT EXISTS jobs (
    id                 INTEGER PRIMARY KEY,
    dedupe_key         TEXT NOT NULL UNIQUE,
    title              TEXT,             -- NULL = not read from source (never guessed)
    company            TEXT,
    location           TEXT,
    remote             TEXT,             -- remote | hybrid | onsite | NULL (unknown)
    url                TEXT,
    external_job_id    TEXT,
    description        TEXT,             -- full text ONLY if actually retrieved
    description_state  TEXT NOT NULL DEFAULT 'incomplete',  -- complete | incomplete
    salary_text        TEXT,
    status             TEXT NOT NULL DEFAULT 'open',        -- open | expired | closed | unknown
    first_seen_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

-- Every observation of a listing: provenance, change tracking, source linkage.
CREATE TABLE IF NOT EXISTS sightings (
    id           INTEGER PRIMARY KEY,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    seen_at      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_ref      TEXT NOT NULL DEFAULT '',   -- message-id / filename
    UNIQUE (job_id, source_id, content_hash)
);

-- Email-level idempotency: a message is ingested at most once.
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY,
    message_id    TEXT NOT NULL UNIQUE,
    source_id     INTEGER REFERENCES sources(id),
    subject       TEXT,
    processed_at  TEXT NOT NULL,
    listing_count INTEGER NOT NULL DEFAULT 0,
    content_hash  TEXT NOT NULL
);

-- M3: owner decisions, bound to exactly one job + action.
CREATE TABLE IF NOT EXISTS decisions (
    id         INTEGER PRIMARY KEY,
    job_id     INTEGER NOT NULL REFERENCES jobs(id),
    action     TEXT NOT NULL,   -- approve | reject | research | save
    decided_at TEXT NOT NULL,
    actor      TEXT NOT NULL DEFAULT 'owner',
    note       TEXT,
    UNIQUE (job_id, action)
);

-- M5: outbound action audit. idempotency_key is the duplicate-submission guard.
CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY,
    job_id          INTEGER REFERENCES jobs(id),
    action          TEXT NOT NULL,     -- send_application | send_followup | ...
    target          TEXT,              -- recipient / destination
    performed_at    TEXT NOT NULL,
    result          TEXT,              -- provider-confirmed result
    idempotency_key TEXT UNIQUE,
    detail          TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_seen     ON jobs(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_sightings_job ON sightings(job_id);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) the ledger with the schema applied."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    con.commit()
    return con
