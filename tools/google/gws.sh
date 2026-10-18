#!/usr/bin/env bash
# Jobsearch Google Workspace helper — the ONLY supported way to run setup.py.
#
# Why this wrapper exists: setup.py stores the OAuth token at
# $HERMES_HOME/google_token.json, and inside a Hermes session HERMES_HOME is a
# PROFILE directory (e.g. ~/.hermes/profiles/assistant-1). Run setup.py raw and
# the Gmail token is silently coupled to whichever of the five interchangeable
# lanes happened to run it — the other four could not read Gmail, and a cron job
# under a different profile would fail with NOT_AUTHENTICATED.
#
# Pinning HERMES_HOME here instead puts the token with the project:
#   var/gws-home/google_token.json
# which is (a) lane-independent and (b) inside jobsearch/.gitignore's `*` guard,
# so it can never reach the public repo this workspace sits inside.
#
# Override with JOBSEARCH_GWS_HOME only if you know why you are doing it.
set -euo pipefail

export HERMES_HOME="${JOBSEARCH_GWS_HOME:-$HOME/hermes-workspace/jobsearch/var/gws-home}"
mkdir -p "$HERMES_HOME"

# Resolve SETUP relative to this script so a copy in any checkout finds it.
SETUP="$(cd "$(dirname "$0")/.." && pwd)/google/setup.py"
VENV_PY="$HOME/.hermes/hermes-agent/venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  VENV_PY="$(command -v python3 || true)"
fi
if [ -z "$VENV_PY" ] || [ ! -x "$VENV_PY" ]; then
  echo "ERROR: no usable python interpreter (set PATH or HERMES_VENV_PYTHON)" >&2
  exit 1
fi

exec "$VENV_PY" "$SETUP" "$@"
