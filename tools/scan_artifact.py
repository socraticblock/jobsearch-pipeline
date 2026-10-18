# tools/scan_artifact.py
# Independent, reusable privacy scanner for built PyPI artifacts.
# Used by the CI gate (release-privacy.yml) and by the publish
# path (release.yml), and exercised by tests/test_sdist_leak_scan.py
# against synthetic leak fixtures.
#
# The scanner reads the production deny-list from
# `scripts/export_bundle.py` so this module and the export gate
# cannot drift on what they defend. Matching semantics mirror the
# production scanner in scripts/export_bundle.py:
#   - DENY_TOKENS are matched case-insensitively
#   - DENY_SECRET_PATTERNS and DENY_HOME_PATTERNS are matched
#     case-sensitively
# The test file is the only place that ships a synthetic leak
# fixture, and it ships the SHAPE of a leak, not a real value,
# so the test source itself is not a leak.

import re
import sys
import tarfile
import zipfile
from pathlib import Path

from scripts.export_bundle import (
    DENY_TOKENS,
    DENY_SECRET_PATTERNS,
    DENY_HOME_PATTERNS,
    TOKEN_ALLOWANCES,
)

def _relative_member_path(member_name: str) -> str:
    """Strip the top-level directory from an sdist member path
    so it matches the allowance keys (which use source-tree
    relative paths like 'jobsearch/rules.py')."""
    parts = member_name.split("/")
    if len(parts) > 1 and parts[0].startswith("jobsearch_pipeline"):
        return "/".join(parts[1:])
    return member_name


def _is_allowed(rel_path: str, pattern: str) -> bool:
    """Check if a matched pattern is allowed for this file,
    mirroring the production export scanner's allowance system."""
    for (path_key, token_key), reason in TOKEN_ALLOWANCES.items():
        if path_key != rel_path:
            continue
        if token_key == "*" or token_key == pattern:
            return True
    return False


_PATTERNS: list[tuple[re.Pattern, str]] = []
for _p in DENY_TOKENS:
    _PATTERNS.append((re.compile(_p, re.IGNORECASE), _p))
for _p in DENY_SECRET_PATTERNS:
    _PATTERNS.append((re.compile(_p), _p))
for _p in DENY_HOME_PATTERNS:
    _PATTERNS.append((re.compile(_p), _p))


def scan_bytes(data: bytes) -> list[str]:
    """Return the deny-list patterns that match in `data`.

    The return is the list of matched pattern strings (not
    offsets). Callers log the file:line context themselves.

    Non-UTF-8 bytes are not silently dropped: the data is
    decoded both as UTF-8 (with replacement for invalid bytes)
    and as latin-1 (which preserves every byte). A pattern
    found by either decoding is reported, so non-UTF-8
    content cannot bypass the scan.
    """
    matches: set[str] = set()
    # Scan as UTF-8 (replacement chars for invalid bytes)
    text = data.decode("utf-8", errors="replace")
    for rx, pat in _PATTERNS:
        if rx.search(text):
            matches.add(pat)
    # Scan as latin-1 (preserves every byte, catches non-UTF-8
    # content that might contain deny-listed identifiers)
    raw_text = data.decode("latin-1")
    for rx, pat in _PATTERNS:
        if rx.search(raw_text):
            matches.add(pat)
    return sorted(matches)


def scan_tar_gz(archive: Path) -> list[tuple[str, list[str]]]:
    """Return [(member_name, [matched_pattern, ...]), ...]
    for every file in the sdist that matches a deny-list
    pattern. Empty list == clean.

    Extraction or reading failures are reported as findings
    (fail-closed), not silently skipped.
    """
    findings: list[tuple[str, list[str]]] = []
    with tarfile.open(archive) as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            ef = tf.extractfile(m)
            if ef is None:
                findings.append((m.name, ["UNREADABLE_MEMBER"]))
                continue
            try:
                data = ef.read()
            except Exception:
                findings.append((m.name, ["UNREADABLE_MEMBER"]))
                continue
            matches = scan_bytes(data)
            # Filter out allowed patterns
            rel_path = _relative_member_path(m.name)
            real_matches = [p for p in matches if not _is_allowed(rel_path, p)]
            if real_matches:
                findings.append((m.name, real_matches))
    return findings


def scan_wheel(archive: Path) -> list[tuple[str, list[str]]]:
    """Return [(name, [matched_pattern, ...]), ...] for every
    file in the wheel that matches a deny-list pattern. Empty
    list == clean.

    Extraction or reading failures are reported as findings
    (fail-closed), not silently skipped.
    """
    findings: list[tuple[str, list[str]]] = []
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            # Skip directories
            if name.endswith("/"):
                continue
            try:
                data = zf.read(name)
            except Exception:
                findings.append((name, ["UNREADABLE_MEMBER"]))
                continue
            matches = scan_bytes(data)
            rel_path = _relative_member_path(name)
            real_matches = [p for p in matches if not _is_allowed(rel_path, p)]
            if real_matches:
                findings.append((name, real_matches))
    return findings


def scan_artifact(archive: Path) -> list[tuple[str, list[str]]]:
    """Dispatch to the correct reader based on the archive
    suffix (.tar.gz -> sdist, .whl -> wheel). Unknown
    suffixes raise ValueError.

    Archive-level corruption propagates as an exception
    (fail-closed).
    """
    if archive.name.endswith(".tar.gz"):
        return scan_tar_gz(archive)
    if archive.name.endswith(".whl"):
        return scan_wheel(archive)
    raise ValueError(f"unsupported archive type: {archive}")


def _cli() -> int:
    """Command-line entry point for the CI gate and the
    publish path. Exits 0 on clean, 1 on any finding.
    Prints findings as `path: pattern` lines so CI can
    surface them in PR annotations.
    """
    if len(sys.argv) < 2:
        print("usage: scan_artifact.py <archive> [<archive>...]", file=sys.stderr)
        return 2
    ok = True
    for arg in sys.argv[1:]:
        archive = Path(arg)
        if not archive.is_file():
            print(f"::error::archive not found: {archive}", file=sys.stderr)
            ok = False
            continue
        try:
            results = scan_artifact(archive)
        except Exception as e:
            print(f"::error file={archive.name}::scan failed: {e}", file=sys.stderr)
            ok = False
            continue
        for name, matches in results:
            for m in matches:
                print(f"::error file={archive.name}!{name}::deny-list pattern {m!r} found in published artifact")
            if matches:
                ok = False
    if ok:
        print("published artifacts are clean of deny-listed tokens")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli())
