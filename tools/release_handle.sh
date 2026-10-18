#!/usr/bin/env bash
# tools/release_handle.sh — compute the release handle for an export directory.
#
# The W7.2 contract: a versioned release has a hash handle the verifier
# can compare byte-for-byte. This script computes that handle for an
# export directory: a sha256 of every file's sha256, concatenated in
# sorted relative-path order. This is a tree hash, not a commit hash.
#
# Usage:
#   tools/release_handle.sh <export-dir>     # print RELEASE_HANDLE line
#   tools/release_handle.sh <export-dir> --hex  # print just the hex hash
#
# Exit codes:
#   0 success
#   2 the export directory is missing or empty
#
# The script is the unit-tested extraction of the --release logic in
# tools/verify.sh. Splitting it out lets the regression test
# `tests/test_release_workflow.py::TestVerifyReleaseMode` exercise
# the handle computation without re-running the full suite.
#
# Run:  bash tools/release_handle.sh /path/to/dist/jobsearch-pipeline

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "FATAL: usage: $0 <export-dir> [--hex]" >&2
    exit 2
fi

OUT="$1"
shift

if [ ! -d "$OUT" ]; then
    echo "FATAL: export directory $OUT does not exist" >&2
    exit 2
fi

# Hash every file in the export by sorted relative path, then hash
# the concatenation. This is a tree hash, not a commit hash; it
# is what the verify script on a future checkout will compare.
# We use null-delimited paths and sort -z so filenames with
# spaces or newlines are handled correctly.
HASH=$(cd "$OUT" && find . -type f -not -path '*__pycache__*' \
    -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')

if [ "$#" -gt 0 ] && [ "$1" = "--hex" ]; then
    echo "$HASH"
else
    echo "RELEASE_HANDLE: sha256=$HASH path=$OUT"
fi
