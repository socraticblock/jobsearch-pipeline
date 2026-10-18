#!/usr/bin/env python3
"""Deliver the shortlist digest to Telegram.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment (or a
.env file in the project root). Renders the digest text and sends it in
chunks of <= 4096 chars (Telegram's message limit).

    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 tools/deliver_digest.py

Exit codes: 0 sent | 1 missing config | 2 send failed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import db as db_mod
from jobsearch.notify import render_digest
from jobsearch.rules import load_rules

DEFAULT_DB = ROOT / "var" / "jobs.db"
DEFAULT_PROFILE = ROOT / "profile" / "profile.yaml"
MAX_CHARS = 4000


def _load_env():
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _send(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
            return bool(payload.get("ok"))
    except Exception:
        return False


def main(argv=None):
    _load_env()
    ap = argparse.ArgumentParser(description="Deliver the shortlist digest to Telegram.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    ap.add_argument("--dry-run", action="store_true", help="print the digest, do not send")
    args = ap.parse_args(argv)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        if args.dry_run:
            pass
        else:
            print("missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", file=sys.stderr)
            return 1

    try:
        rules = load_rules(args.profile)
    except Exception as exc:
        print(f"could not load profile: {exc}", file=sys.stderr)
        return 1
    con = db_mod.connect(args.db)
    try:
        text = render_digest(con, limit=20, rules=rules)
    finally:
        con.close()

    if args.dry_run:
        print(text)
        return 0

    # chunk
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > MAX_CHARS:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)

    for chunk in chunks:
        if not _send(token, chat_id, chunk):
            print("send failed", file=sys.stderr)
            return 2
    print(f"sent {len(chunks)} message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
