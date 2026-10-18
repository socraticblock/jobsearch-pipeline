#!/usr/bin/env python3
"""Verify the Google token grants read-only Gmail access and nothing more.

Run it after the OAuth exchange:

    tools/google/check_scopes.py

Exit 0  -> every granted scope is within the read-only allowlist.
Exit 1  -> something broader was granted. The message names it. Revoke and redo
           with `gws.sh --revoke` then `gws.sh --auth-url`.

This exists because "we asked for read-only" and "we got read-only" are
different claims. A consent screen can return more than the client requested,
and a token file is easy to reuse without re-reading what it permits. The owner
rule is `gmail.readonly` only, so that is checked, not assumed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# gmail.readonly plus the identity scopes Google attaches to every OAuth grant.
# Anything else is an over-grant and fails this check.
ALLOWED = {
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
}

# Named explicitly so the failure message is useful rather than just "unexpected".
DANGEROUS = {
    "https://mail.google.com/": "full Gmail access (read, send, delete, settings)",
    "https://www.googleapis.com/auth/gmail.send": "send email as you",
    "https://www.googleapis.com/auth/gmail.modify": "read, label, delete, and mark email",
    "https://www.googleapis.com/auth/gmail.compose": "create drafts and send",
    "https://www.googleapis.com/auth/gmail.labels": "change Gmail labels",
    "https://www.googleapis.com/auth/gmail.settings.basic": "change Gmail settings",
    "https://www.googleapis.com/auth/drive": "full Drive access",
    "https://www.googleapis.com/auth/calendar": "full Calendar access",
}


def main() -> int:
    home = Path(os.environ.get("HERMES_HOME", "")).expanduser() if os.environ.get(
        "HERMES_HOME", ""
    ).strip() else Path.home() / ".hermes"
    token_path = home / "google_token.json"

    if not token_path.is_file():
        print(f"NOT_AUTHENTICATED: no token at {token_path}")
        return 1

    try:
        payload = json.loads(token_path.read_text())
    except Exception as exc:
        print(f"TOKEN_UNREADABLE: {exc}")
        return 1

    raw = payload.get("scopes") or payload.get("scope") or []
    granted = [s.strip() for s in (raw.split() if isinstance(raw, str) else raw) if s.strip()]

    print(f"token:  {token_path}")
    print(f"scopes: {len(granted)}")
    for s in sorted(granted):
        mark = "ok " if s in ALLOWED else ("OVER-GRANT" if s in DANGEROUS else "UNKNOWN")
        note = f"  <- {DANGEROUS[s]}" if s in DANGEROUS else ""
        print(f"  [{mark}] {s}{note}")

    readonly = "https://www.googleapis.com/auth/gmail.readonly"
    problems = [s for s in granted if s not in ALLOWED]
    if readonly not in granted:
        print("FAIL: gmail.readonly was not granted — the ingest cannot read mail.")
        return 1
    if problems:
        print(f"FAIL: {len(problems)} scope(s) exceed the read-only rule:")
        for s in problems:
            print(f"  - {s}{'  <- ' + DANGEROUS[s] if s in DANGEROUS else ''}")
        print("Revoke and redo: tools/google/gws.sh --revoke, then --auth-url.")
        return 1

    print("PASS: read-only Gmail only — no send, no modify, no delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
