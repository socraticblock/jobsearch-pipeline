#!/usr/bin/env bash
# tools/enrich_retry.sh — safe to run from cron. Re-attempts incomplete jobs
# with backoff. Never re-fetches complete jobs. Exits 0 on success or "nothing
# to do", 6 on rate-limit (cron will retry later), 7 on fetch failures.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PY:-${HERMES_VENV_PYTHON:-$HOME/.hermes/hermes-agent/venv/bin/python3}}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  echo "FATAL: no usable python interpreter (set PY or HERMES_VENV_PYTHON)" >&2
  exit 2
fi
exec "$PY" -m jobsearch.enrich --resume --limit 3 --spacing 90 "$@"
