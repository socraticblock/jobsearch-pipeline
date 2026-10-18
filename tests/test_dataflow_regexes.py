"""I-26 -- the network-direction regex pin.

`PARSE_ONLY`, `UNKNOWN_NETWORK`,
`OUTBOUND`, and `INBOUND` in
`tools/build_dataflow_map.py`
are the network-direction
classifier regexes. They
determine which network
boundary a code block crosses
when scanning the project for
network-touching modules. The
output of the classifier is
`docs/DATA-FLOW.md` -- a
public document that audits
the project's network
exposure. A third party
copying the project would
look at this document to
understand what the project
does at the network layer.

The resolution order in the
classifier is:
1. `_direction(name)`:
   - `INBOUND.search(name)`
     -> "inbound"
   - `OUTBOUND.search(name)`
     -> "outbound"
   - else -> "unknown"
2. `_infer_surface(path, net)`:
   - `PARSE_ONLY.search(net)`
     -> "stdlib parse only,
     no network call"
   - `UNKNOWN_NETWORK.search(net)`
     -> "imported; surface
     depends on call site
     -- see source"
   - `urllib.request` ->
     detailed heuristics
   - else -> "unknown
     surface"

The inputs to the regexes
are **fully-qualified import
names** (e.g.
`urllib.request.urlopen`,
`http.client.HTTPResponse`).

The contract is:
- `PARSE_ONLY` (re.IGNORECASE off):
  - matches
    `urllib.parse.*` and
    `urllib.error.*` (the
    parse-only parts of
    urllib)
  - matches
    `http.client.<TypeName>`
    (e.g.
    `http.client.HTTPResponse`,
    NOT
    `http.client.HTTPConnection`
    which is a real
    network call)
- `UNKNOWN_NETWORK`:
  - matches known
    network modules
    that the tool has
    not yet written a
    summariser for
    (`telegram`,
    `requests`,
    `httpx`,
    `aiohttp`,
    `smtplib`,
    `ftplib`,
    `telnetlib`,
    `asyncio.open_connection`,
    `ssl.wrap_socket`,
    `urllib3`,
    `httplib2`,
    `boto3`,
    `google.cloud`,
    `http.server`,
    `socketserver`)
- `OUTBOUND` (re.IGNORECASE):
  - matches any of
    `telegram`,
    `requests`,
    `httpx`,
    `aiohttp`,
    `smtplib`,
    `urllib`,
    `http.client`
- `INBOUND`
  (re.IGNORECASE):
  - matches
    `http.server`,
    `socketserver`,
    `asyncio.open_connection`

A drift in any of these
regexes would silently
misclassify modules in
`docs/DATA-FLOW.md`:
- Removing `telegram` from
  `OUTBOUND` would
  misclassify a
  Telegram call
  as "unknown"
  rather than
  "outbound". A
  reviewer would
  not see it
  highlighted in
  the dataflow
  map.
- Removing `asyncio.open_connection`
  from `INBOUND`
  would
  misclassify a
  server (e.g.
  an asyncio
  TCP server) as
  "unknown"
  rather than
  "inbound". A
  reviewer would
  miss that the
  project runs
  an inbound
  server.
- Removing
  `urllib.error`
  from
  `PARSE_ONLY`
  would
  misclassify a
  pure parse
  call as
  "unknown
  surface"
  rather than
  "stdlib parse
  only, no
  network call".

The published artifact
would silently drift
from what the code
actually does. A
third party
auditing the
project would
miss real
network calls
or falsely
report
parse-only
calls as
network calls.

The fix is a new
`TestDataflowRegexes`
class with 4 tests:
1. `test_parse_only_matches_documented_imports`:
   each documented
   PARSE_ONLY
   import matches.
2. `test_unknown_network_matches_documented_imports`:
   each documented
   UNKNOWN_NETWORK
   import matches.
3. `test_outbound_matches_documented_imports`:
   each documented
   OUTBOUND import
   matches.
4. `test_inbound_matches_documented_imports`:
   each documented
   INBOUND import
   matches.

Drift-injection verified:
removing `telegram` from
OUTBOUND would fail the
OUTBOUND test.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dataflow_map():
    """Helper: import the
    dataflow map tool by
    exec'ing the source
    file. We must register
    the module in
    `sys.modules` BEFORE
    `exec_module` because
    the module uses type
    annotations that the
    dataclass decorator
    needs to walk the
    `__module__` chain
    (same lesson as the
    doctor module).
    """
    import importlib.util
    import sys as _sys
    p = ROOT / "tools" / "build_dataflow_map.py"
    spec = importlib.util.spec_from_file_location(
        "_dataflow_map_for_test", p,
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["_dataflow_map_for_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDataflowRegexes(unittest.TestCase):
    """The
    `build_dataflow_map.py`
    tool's 4 network-direction
    regexes (PARSE_ONLY,
    UNKNOWN_NETWORK,
    OUTBOUND, INBOUND) are
    the public-dataflow
    classifier. They
    determine what
    `docs/DATA-FLOW.md`
    reports. A drift would
    silently misclassify
    modules.
    """

    def test_parse_only_matches_documented_imports(self) -> None:
        """`PARSE_ONLY` in
        `tools/build_dataflow_map.py`
        must match every
        documented
        parse-only import:
        `urllib.parse.*`,
        `urllib.error.*`,
        `http.client.<TypeName>`.

        Removing `urllib.error`
        would silently
        misclassify a
        pure-parse call
        (e.g.
        `urllib.error.HTTPError`
        used for
        exception
        handling) as
        "unknown
        surface"
        rather than
        "stdlib parse
        only".
        """
        mod = _load_dataflow_map()
        PARSE_ONLY_CASES = (
            # urllib.parse
            "urllib.parse.urlparse",
            "urllib.parse.urlencode",
            "urllib.parse.quote",
            # urllib.error
            "urllib.error.HTTPError",
            "urllib.error.URLError",
            # http.client (type
            # imports)
            "http.client.HTTPResponse",
            "http.client.BadStatusLine",
        )
        for case in PARSE_ONLY_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod.PARSE_ONLY.search(case),
                    f"PARSE_ONLY did NOT match "
                    f"the documented parse-only "
                    f"import {case!r}. A "
                    f"parse-only import would "
                    f"be silently misclassified "
                    f"as 'unknown surface' "
                    f"instead of 'stdlib parse "
                    f"only, no network call'."
                )

    def test_unknown_network_matches_documented_imports(self) -> None:
        """`UNKNOWN_NETWORK` in
        `tools/build_dataflow_map.py`
        must match every
        documented
        unknown-network
        module:
        `telegram`,
        `requests`, `httpx`,
        `aiohttp`,
        `smtplib`,
        `ftplib`,
        `telnetlib`,
        `asyncio.open_connection`,
        `ssl.wrap_socket`,
        `urllib3`,
        `httplib2`,
        `boto3`,
        `google.cloud`,
        `http.server`,
        `socketserver`.

        Removing `telegram`
        would silently
        misclassify a
        Telegram call
        as "unknown"
        rather than
        "imported;
        surface depends
        on call site".
        A reviewer would
        not see the
        Telegram call
        flagged in
        DATA-FLOW.md.
        """
        mod = _load_dataflow_map()
        UNKNOWN_NETWORK_CASES = (
            "telegram.send",
            "telegram.ext.ConversationHandler",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.AsyncClient",
            "aiohttp.ClientSession",
            "aiohttp.web",
            "smtplib.SMTP",
            "ftplib.FTP",
            "telnetlib.Telnet",
            "asyncio.open_connection",
            "ssl.wrap_socket",
            "urllib3.PoolManager",
            "httplib2.Http",
            "boto3.client",
            "google.cloud.storage",
            "http.server.HTTPServer",
            "socketserver.TCPServer",
        )
        for case in UNKNOWN_NETWORK_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod.UNKNOWN_NETWORK.search(case),
                    f"UNKNOWN_NETWORK did NOT "
                    f"match the documented "
                    f"unknown-network import "
                    f"{case!r}. The import would "
                    f"be silently misclassified "
                    f"as 'unknown surface' "
                    f"instead of 'imported; "
                    f"surface depends on call "
                    f"site -- see source'."
                )

    def test_outbound_matches_documented_imports(self) -> None:
        """`OUTBOUND` in
        `tools/build_dataflow_map.py`
        must match every
        documented outbound
        module:
        `telegram`,
        `requests`,
        `httpx`,
        `aiohttp`,
        `smtplib`,
        `urllib`,
        `http.client`
        (case-insensitive).

        Removing `telegram`
        from OUTBOUND would
        silently
        misclassify a
        Telegram call as
        "unknown" rather
        than "outbound".
        A reviewer would
        not see the
        Telegram call
        highlighted in
        DATA-FLOW.md.
        """
        mod = _load_dataflow_map()
        OUTBOUND_CASES = (
            "telegram.Bot",
            "telegram.ext",
            "requests.get",
            "requests.Session",
            "httpx.get",
            "httpx.AsyncClient",
            "aiohttp.ClientSession",
            "smtplib.SMTP",
            "urllib.request.urlopen",
            "urllib.error.HTTPError",
            "http.client.HTTPConnection",
        )
        for case in OUTBOUND_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod.OUTBOUND.search(case),
                    f"OUTBOUND did NOT match "
                    f"the documented outbound "
                    f"import {case!r}. The "
                    f"import would be silently "
                    f"misclassified as "
                    f"'unknown' instead of "
                    f"'outbound'. A reviewer "
                    f"auditing the project's "
                    f"network exposure would "
                    f"miss this outbound call."
                )

    def test_inbound_matches_documented_imports(self) -> None:
        """`INBOUND` in
        `tools/build_dataflow_map.py`
        must match every
        documented inbound
        module:
        `http.server`,
        `socketserver`,
        `asyncio.open_connection`
        (case-insensitive).

        Removing
        `asyncio.open_connection`
        would silently
        misclassify an
        asyncio TCP
        server as
        "unknown"
        rather than
        "inbound". A
        reviewer would
        miss that the
        project runs an
        inbound server.
        """
        mod = _load_dataflow_map()
        INBOUND_CASES = (
            "http.server.HTTPServer",
            "http.server.BaseHTTPRequestHandler",
            "socketserver.TCPServer",
            "socketserver.UDPServer",
            "asyncio.open_connection",
        )
        for case in INBOUND_CASES:
            with self.subTest(case=case):
                self.assertIsNotNone(
                    mod.INBOUND.search(case),
                    f"INBOUND did NOT match "
                    f"the documented inbound "
                    f"import {case!r}. The "
                    f"import would be silently "
                    f"misclassified as "
                    f"'unknown' instead of "
                    f"'inbound'. A reviewer "
                    f"auditing the project's "
                    f"network exposure would "
                    f"miss this inbound "
                    f"server."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
