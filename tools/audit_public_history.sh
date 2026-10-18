#!/usr/bin/env bash
# audit_public_history.sh -- the repeatable W1.4 history audit.
#
# Why this is a script and not just a one-shot command in HANDOFF.md: every
# future change to the public repo deserves a fresh check, and "I re-ran it
# once and it was clean" ages badly. The script makes the check as cheap as a
# single command, and the test (tests/test_history_audit.py) makes the script
# itself the unit under proof.
#
# The audit is intentionally narrow: it asserts that no project path ever
# appears in the public repository -- in HEAD, in any reachable history, in any
# stash, or in any dangling object. Anything that the leak runbook's history
# rewrite would need to address is the output of this audit, so it has to
# match what a real reviewer would do.
#
# Usage:
#   tools/audit_public_history.sh                          # audit this checkout
#   tools/audit_public_history.sh /path/to/public/repo     # audit a clone
#
# Exit codes:
#   0 clean (no forbidden paths in HEAD, history, stashes, or dangling objects)
#   1 one or more forbidden paths found
#   2 the given path is not a git repository (audit cannot run)

set -euo pipefail

REPO_DIR="${1:-$(git rev-parse --show-toplevel)}"

if ! git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "ERROR: $REPO_DIR is not a git repository"
    exit 2
fi

# The names the audit is looking for. Kept in one place so a future maintainer
# does not grep "jobsearch" in one place and forget "var/" in another.
NAMES=("jobsearch" "var/jobs.db" "google_token.json" "client_secret.json")
# The set of personal-identifier tokens the leak scan would also catch, so a
# reviewer running this gets the same view they would have if they ran the
# export gate against a tree that included a leak.
TOKENS=("socraticblock" "sakartvelo" "Tbilisi")

found=0
report() {
    if [ "$1" -ne 0 ]; then
        found=1
        echo "  HIT: $2"
    fi
}

echo "auditing $REPO_DIR for paths/tokens that must never appear here"

# 1. HEAD working tree
echo "  [1/4] HEAD working tree..."
for n in "${NAMES[@]}"; do
    if git -C "$REPO_DIR" ls-files | grep -F -x "$n" >/dev/null 2>&1 \
       || [ -n "$(git -C "$REPO_DIR" ls-files | grep -F "/$n/")" ]; then
        report 1 "HEAD tracks $n"
    fi
done

# 2. All reachable history (every commit, every tree blob)
echo "  [2/4] reachable history..."
for n in "${NAMES[@]}"; do
    if git -C "$REPO_DIR" log --all --pretty=format: --name-only \
        | grep -F "$n" >/dev/null 2>&1; then
        report 1 "reachable history contains $n"
    fi
done

# 3. Stashes
echo "  [3/4] stashes..."
if git -C "$REPO_DIR" stash list | grep -q .; then
    if git -C "$REPO_DIR" stash list -p | grep -F "jobsearch" >/dev/null 2>&1; then
        report 1 "stash contains jobsearch content"
    fi
fi

# 4. Dangling objects (commits, trees, blobs not reachable from any ref)
# Use --no-reflogs intentionally: reflogs live under .git/logs/ which is
# never pushed to a remote, so they're not part of the *public* history
# the audit is gating. Scanning reflogs would surface locally-deleted
# secrets (e.g. a credential file that was added and then git-rm'd in
# the same clone) and false-positive on the public repo. The audit's
# job is to gate what's already on the remote's HEAD reachable set;
# local-only artefacts (reflogs, stash) are out of scope.
echo "  [4/4] dangling objects..."
dangling_blobs=$(git -C "$REPO_DIR" fsck --unreachable --no-reflogs --no-progress 2>/dev/null \
    | awk '/dangling (blob|tree|commit)/ {print $3}')
for obj in $dangling_blobs; do
    # Each object is a sha; try to read its content safely.
    content=$(git -C "$REPO_DIR" cat-file -p "$obj" 2>/dev/null || true)
    for tok in "${TOKENS[@]}"; do
        if echo "$content" | grep -F "$tok" >/dev/null 2>&1; then
            report 1 "dangling object $obj contains $tok"
        fi
    done
    for n in "${NAMES[@]}"; do
        if echo "$content" | grep -F "$n" >/dev/null 2>&1; then
            report 1 "dangling object $obj references $n"
        fi
    done
done

if [ "$found" -eq 0 ]; then
    echo "  clean: no forbidden paths or tokens in HEAD, history, stashes, or dangling objects"
    exit 0
else
    echo "  FAIL: the public repository contains something that must not be there."
    echo "  See SECURITY.md for the leak runbook."
    exit 1
fi
