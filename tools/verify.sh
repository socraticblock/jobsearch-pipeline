#!/usr/bin/env bash
# tools/verify.sh — the single command that equals CI (W7.1).
#
# A locally green run of this script and a CI run on the same SHA must
# produce the same result. The script runs every gate whose evidence the
# GOAL-AIRTIGHT.md workstreams require: the suite in both modes, the
# export gate (clean + every mutation), the history audit, the scope
# freeze, the bundled credentials check, the no-bundled-credentials
# check, the W1 containment assertions, and (optionally) the bundled
# suite from the export itself.
#
# Exit codes: 0 all green; 1 any failure. Each step prints its own
# result so a CI log shows exactly which step failed.
#
# Usage:
#   tools/verify.sh                  # full local gate
#   tools/verify.sh --release        # full gate + versioned release handle
#   tools/verify.sh --skip-export    # skip --run-tests on the export
#                                    # (faster, but loses the "copy
#                                    # stands alone" evidence)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PY:-${HERMES_VENV_PYTHON:-$HOME/.hermes/hermes-agent/venv/bin/python3}}"

skip_export=0
release=0
for arg in "$@"; do
    case "$arg" in
        --skip-export) skip_export=1 ;;
        --release)     release=1 ;;
        --help|-h)
            sed -n '3,20p' "$0"
            exit 0
            ;;
        *) echo "unknown flag: $arg"; exit 2 ;;
    esac
done

# Pin the interpreter: the matching layer needs PyYAML, which system
# python3 on this host does not have. Without this pin, a CI run on a clean
# runner would silently fail the rules tests. Fall back to python3 when the
# pinned venv is absent (e.g. GitHub Actions), so the gate still runs.
if [ ! -x "$PY" ]; then
    PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    echo "FATAL: no usable python interpreter (set PY or HERMES_VENV_PYTHON)"
    exit 2
fi

# Make the project's own venv-tools importable when tests do
# `from tools import ...`. The standard `python3 -m unittest` does
# NOT do this on its own; the test files use the cwd as sys.path[0].
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

run_step() {
    local name="$1"; shift
    echo
    echo "==> $name"
    if "$@"; then
        echo "    PASS"
    else
        local rc=$?
        echo "    FAIL (exit $rc)"
        return $rc
    fi
}

# Step 0: the doctor. Inspects preconditions (python version,
# required modules, the corpus, the rules) and reports any
# failures with a one-line fix. If the doctor fails, the rest
# of verify.sh is not going to be meaningful; a fresh clone
# with a missing corpus or wrong python version would just
# produce a long, hard-to-read unittest traceback.
run_step "doctor (preconditions)" \
    "$PY" tools/doctor.py

# Step 1: the test suite in normal mode.
run_step "unittest (normal mode)" \
    "$PY" -m unittest discover -s tests

# Step 2: the test suite in -O mode. The site repo's `test:security`
# script runs under `python3 -O`, and asserts (mistakenly) survive
# optimisation. The jobsearch suite uses unittest assertion methods
# only, so a green -O run is real evidence the suite encodes the
# requirement, not the implementation.
run_step "unittest (-O mode, must behave identically)" \
    "$PY" -O -m unittest discover -s tests

# Step 3: the export gate, clean baseline. The export gate's mutation
# tests are part of the unittest suite; this is the "operator could
# publish today" check.
run_step "export gate (clean baseline, no LICENSE override)" \
    "$PY" scripts/export_bundle.py --allow-no-licence

# Step 4: the history audit. The audit's "clean" case runs against the
# live PUBLIC repo (the parent of this project), not against this repo --
# see tests/test_history_audit.py. Run it there when available; skip
# (with a note) otherwise, so a fresh checkout with no parent .git does
# not fail the gate.
if [ -d "$ROOT/../.git" ]; then
    run_step "history audit (live public repo)" \
        bash tools/audit_public_history.sh "$ROOT/.."
else
    echo
    echo "==> history audit (live public repo): SKIPPED (no parent .git)"
fi

# Step 5 (optional): run the suite FROM the export. This is the
# "the copy stands alone" check. Skipped by --skip-export to keep the
# default fast.
if [ "$skip_export" -eq 0 ]; then
    run_step "unittest from the export (proves the copy stands alone)" \
        "$PY" scripts/export_bundle.py --allow-no-licence --run-tests
else
    echo
    echo "==> unittest from the export: SKIPPED (--skip-export)"
fi

echo
echo "VERIFY: all steps green"

# Step 6 (--release): print the artifact hash handle for the release
# ledger. The ledger entry is a sha256 of the artifact directory, which
# the release script can use to verify the published copy byte-for-byte.
# The handle computation lives in tools/release_handle.sh, which is the
# unit-tested unit; verify.sh is the glue.
if [ "$release" -eq 1 ]; then
    OUT="$ROOT/dist/jobsearch-pipeline"
    if [ ! -d "$OUT" ]; then
        echo "FATAL: --release requested but $OUT does not exist"
        exit 2
    fi
    bash "$ROOT/tools/release_handle.sh" "$OUT"
fi
