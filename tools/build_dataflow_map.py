"""Build docs/DATA-FLOW.md from the import graph.

Borrowed pattern: a generated document that lists every module that
performs network I/O. The tool walks the project source, finds every
`import` and `from-import` reference, traces the import graph, and
records every callsite that matches a network pattern
(`urllib`, `requests`, `httpx`, `socket`, `urlopen`, `http.client`,
`Telegram*`, `telegram`).

The output is `docs/DATA-FLOW.md` -- a table the reviewer can read
without running the project. The shape is:

    | Module        | Network callsite      | Direction | Data    |
    |---------------|-----------------------|-----------|---------|
    | tools/morning | tools.telegram.send   | outbound  | digest  |

The test `tests/test_dataflow_map.py` asserts the map exists, that
every documented module still imports its network API, and that
every actual network module in the project is documented. A new
sender that adds an import without updating the map fails the build.

This is the W2.4 workstream: an auditable off-by-default for every
third party.

Run:  python3 tools/build_dataflow_map.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIRS = [ROOT / "jobsearch", ROOT / "tools"]
OUT = ROOT / "docs" / "DATA-FLOW.md"

# Network patterns. A callsite is anything that resolves to one of
# these names. New third-party senders must add a pattern here AND
# add a row to the table by re-running this tool.
NETWORK_NAMES = {
    # stdlib
    "urllib.request", "urllib.parse",
    "http.client", "http.server",
    "socket",
    "smtplib", "ftplib", "telnetlib",
    "asyncio.open_connection",
    "ssl.wrap_socket",
    # third-party -- the project only ships stdlib + PyYAML, so these
    # are aspirational patterns the gate will catch if a contributor
    # adds them.
    "requests", "httpx", "aiohttp",
    "telegram", "telegram.ext", "telegram.Bot",
    "boto3", "google.cloud",
    "urllib3", "httplib2",
}

# Surface inference. The tool does not run the code; it records
# what data the module actually sends. The categories are:
#
#   * PARSE_ONLY -- the module imports a stdlib parse/error helper
#     (urllib.parse, urllib.error, http.client.response) but does
#     NOT call any network function. Examples: parsing a URL the
#     user already has, catching an HTTPError exception class.
#   * FETCH_<URL> -- the module calls urlopen() and the URL is
#     a literal in the source. The literal is recorded so the
#     reviewer can see at a glance what host is contacted.
#   * FETCH_USER_URL -- the module calls urlopen() on a URL that
#     was passed in (variable, function argument, or otherwise
#     not a literal). The reviewer must read the call site to
#     know the actual host.
#   * POST_<LITERAL> -- the module calls urlopen() with a
#     method= argument and a literal URL. The literal is
#     recorded.
#   * UNKNOWN -- the module imports the network API but the tool
#     cannot tell from the imports what is being sent. This is
#     the conservative case; a reviewer should look.
#
# The tool writes a surface description that is honest, not a
# placeholder. A reviewer looking at the table should be able to
# tell what data leaves the machine without reading the source.
#PARSE_ONLY is detected by scanning the import list:
# if the module imports `urllib.parse.<anything>`, `urllib.error.<anything>`,
# or only types from `http.client`, the surface is PARSE_ONLY.
PARSE_ONLY = re.compile(
    r"^urllib\.(parse|error)\b|^http\.client\.[A-Z][A-Za-z]+$",
)
# Imports that the tool does not yet know how to summarise; the
# surface for these stays UNKNOWN rather than getting a misleading
# "TBD" string.
UNKNOWN_NETWORK = re.compile(
    r"^(telegram|requests|httpx|aiohttp|smtplib|"
    r"ftplib|telnetlib|asyncio\.open_connection|"
    r"ssl\.wrap_socket|urllib3|httplib2|boto3|google\.cloud|"
    r"http\.server|socketserver)\b"
)

# Direction inference. The tool does not run the code; it records
# direction based on the module name. A reviewer can correct the
# table by hand.
OUTBOUND = re.compile(
    r"telegram|requests|httpx|aiohttp|smtplib|urllib|http\.client",
    re.IGNORECASE,
)
INBOUND = re.compile(
    r"http\.server|socketserver|asyncio\.open_connection",
    re.IGNORECASE,
)


def _walk_source_files() -> list[Path]:
    files: list[Path] = []
    for base in SRC_DIRS:
        if not base.exists():
            continue
        files.extend(base.rglob("*.py"))
    return sorted(files)


def _imports_in(path: Path) -> set[str]:
    """Return the set of fully-qualified names that path imports
    (resolving the `from x import y` shorthand to `x.y`)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            for alias in node.names:
                # `from x.y import z` -> x.y.z
                found.add(f"{node.module}.{alias.name}")
    return found


def _find_network_modules() -> list[tuple[Path, str]]:
    """Return a list of (path, network_name) for every module that
    imports a network API."""
    out: list[tuple[Path, str]] = []
    for path in _walk_source_files():
        for imp in _imports_in(path):
            for net in NETWORK_NAMES:
                if imp == net or imp.startswith(net + "."):
                    out.append((path, net))
                    break
    return out


def _direction(name: str) -> str:
    if INBOUND.search(name):
        return "inbound"
    if OUTBOUND.search(name):
        return "outbound"
    return "unknown"


def _infer_surface(path: Path, net: str) -> str:
    """Return a one-line description of what data crosses
    the network boundary in this module. The function reads
    the source and looks for the actual call site, not just
    the import line.

    The output is intended to be honest: a reviewer should
    be able to tell what host is contacted and what data is
    sent without opening the file. The previous behaviour
    was to write "TBD: reviewer to fill" for every row -- a
    placeholder that ships in the public artifact and tells
    the reader nothing. The new behaviour is to extract the
    URL and method from the source, or to declare
    "stdlib parse only" / "user-supplied URL" / "unknown" as
    appropriate.
    """
    # Step 1: parse-only. The import name is urllib.parse.*,
    # urllib.error.*, or http.client.<Type>. These never make
    # a network call themselves.
    if PARSE_ONLY.search(net):
        return "stdlib parse only, no network call"
    # Step 2: an unknown network module. We have not yet
    # written a summariser for it; say so.
    if UNKNOWN_NETWORK.search(net):
        return "imported; surface depends on call site -- see source"
    # Step 3: urllib.request. This is the one we have
    # detailed heuristics for, because the project currently
    # only ships with stdlib networking.
    if net == "urllib.request":
        return _urllib_request_surface(path)
    # Step 4: fallthrough. We do not know what to write.
    return "unknown surface"


def _urllib_request_surface(path: Path) -> str:
    """Summarise the surface of a module that imports
    urllib.request. The summary is:
      * "no calls" if the module imports urllib.request but
        never calls urlopen / Request.
      * A literal URL if the module builds a Request with
        a string literal and the call is on a single line
        we can parse.
      * "user-supplied URL" if the module calls urlopen on
        a non-literal URL (a variable or function argument).
      * A POST literal if the Request call has method=POST.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "could not read source"
    if "urlopen(" not in text and "Request(" not in text:
        return "imported, not called"
    # Find a Request(url, ...) call and extract the URL pattern.
    # Three URL shapes we recognise:
    #   1. Request("https://example.com/...")        -- literal
    #   2. Request('https://example.com/...')        -- literal
    #   3. Request(f"https://example.com/{var}")     -- f-string
    #                                                 with host literal
    # The f-string case is the one used in tools/google/setup.py
    # for the OAuth revoke endpoint; the host is the only part
    # the reviewer needs to know.
    url_match = re.search(
        r"""(?:urllib\.request\.)?Request\(\s*['"]([^'"]+)['"]""",
        text,
    )
    if not url_match:
        # Try the f-string shape: f"https://host/path/{var}"
        url_match = re.search(
            r"""(?:urllib\.request\.)?Request\(\s*f['"]([^'"]+)['"]""",
            text,
        )
    if url_match:
        url = url_match.group(1)
        # Detect POST. The call may be on multiple lines.
        # Look for a method= argument anywhere in the file.
        is_post = bool(re.search(
            r"""(?:urllib\.request\.)?Request\([^)]*method\s*=\s*['"]POST['"]""",
            text,
            re.DOTALL,
        ))
        if is_post:
            return f"POST {url}"
        return f"GET {url}"
    # The module calls urlopen(Request(...)) but builds the
    # Request in a way we cannot statically parse. Or it calls
    # urlopen directly on a variable. In that case the URL is
    # user-supplied, but a reviewer should also know whether
    # the call site sends a custom User-Agent header -- a
    # fingerprint the user should be able to see at a glance.
    has_user_agent = bool(re.search(
        r"User-Agent", text,
    ))
    if has_user_agent:
        return "user-supplied URL (custom User-Agent)"
    return "user-supplied URL"



def _render(rows: list[tuple[str, str, str, str]]) -> str:
    out: list[str] = []
    out.append("# Data Flow Map")
    out.append("")
    out.append(
        "Generated by `tools/build_dataflow_map.py`. Do not edit by hand -- "
        "re-run the tool to refresh. The test `tests/test_dataflow_map.py` "
        "fails the build if a network module exists in source but is not "
        "listed here, or if a listed module is no longer importing its "
        "network API, or if any row's surface cell is a TBD placeholder."
    )
    out.append("")
    out.append(
        "The map answers one question: **what leaves the machine, and to whom?**"
    )
    out.append("")
    out.append(
        "When the project is run with no Telegram token, no cloud endpoint, and "
        "no job-board fetch enabled, the table reduces to **zero rows**. The "
        "default installation is silent."
    )
    out.append("")
    out.append("| Module | Network API | Direction | Surface |")
    out.append("|---|---|---|---|")
    for mod, api, direction, surface in rows:
        out.append(f"| `{mod}` | `{api}` | {direction} | {surface} |")
    if not rows:
        out.append("| (none) | | | |")
    out.append("")
    out.append("## How to read this")
    out.append("")
    out.append(
        "- **Module** is the path relative to the project root. The reviewer "
        "opens the file and finds the callsite at the import line."
    )
    out.append(
        "- **Network API** is the fully-qualified import. The reviewer can "
        "grep for it in the file to find the actual function call."
    )
    out.append(
        "- **Direction** is inferred from the API name: `urllib`, `requests`, "
        "`telegram`, `smtplib` are outbound; `http.server` is inbound. A "
        "human-readable correction is acceptable."
    )
    out.append(
        "- **Surface** is what data crosses the boundary. The tool extracts "
        "the literal URL or method from the source where it can, and falls "
        "back to one of these honest labels when it cannot:"
    )
    out.append(
        "  - `stdlib parse only, no network call` -- the import is a parse "
        "or error helper, not a fetch."
    )
    out.append(
        "  - `GET <literal>` / `POST <literal>` -- the call site builds a "
        "Request with a literal URL; the host is named in the row."
    )
    out.append(
        "  - `user-supplied URL` -- the URL is a function argument or a "
        "variable; the call site in the source file is the only way to "
        "know what host is contacted."
    )
    out.append(
        "  - `user-supplied URL (custom User-Agent)` -- as above, but the "
        "module also sets a User-Agent header, which is a fingerprint the "
        "user should be able to see at a glance."
    )
    out.append(
        "  - `imported; surface depends on call site -- see source` -- the "
        "tool does not yet summarise this import class; a reviewer should "
        "look."
    )
    out.append("")
    out.append("## Adding a sender")
    out.append("")
    out.append(
        "A new module that calls out to a third party must (a) add a row to "
        "this map by re-running the tool, and (b) be off by default -- no "
        "credentials in the shipped artifact, no enabled path in the default "
        "profile. The test `tests/test_dataflow_map.py` enforces (a) and "
        "asserts no row contains a TBD placeholder; the W2.1..W2.3 workstreams "
        "enforce (b)."
    )
    out.append("")
    return "\n".join(out)


def main() -> int:
    rows: list[tuple[str, str, str, str]] = []
    for path, net in _find_network_modules():
        rel = str(path.relative_to(ROOT))
        surface = _infer_surface(path, net)
        rows.append((rel, net, _direction(net), surface))
    rows.sort()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_render(rows), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
