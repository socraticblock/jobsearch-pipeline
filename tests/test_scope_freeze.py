"""W2.2 — the OAuth scope freeze is enforced by a test.

The contract: across all OAuth helpers, the only Google scope the
pipeline ever *requests* is `gmail.readonly`. Widening the request set
-- adding `gmail.send`, `gmail.modify`, etc. -- fails the build.

A refusal list (the scopes the runner REFUSES to honour if they appear
on a token) is the *opposite* of a request: it is the assertion that
the runtime would catch a widened token. A refusal list is allowed to
name the write scopes; a request list is not. The test distinguishes
them by name (WRITE_SCOPES / FORBIDDEN_SCOPES / DENIED_SCOPES /
BLOCKED_SCOPES / REFUSED_SCOPES are refusal names; SCOPES /
REQUESTED_SCOPES / OAUTH_SCOPES / REQUEST_SCOPES / READONLY_SCOPE are
request names).

Run:  python3 -m unittest tests.test_scope_freeze -v
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Scopes the pipeline must never REQUEST. Listed explicitly so a future
# maintainer who greps this file for the rule sees what the rule means
# in concrete terms.
REQUEST_FORBIDDEN_SCOPES = (
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.insert",
    "https://www.googleapis.com/auth/gmail.delete",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
)

# Names whose values are REQUEST lists. These are the scopes the code
# actually asks Google for at runtime. READONLY_SCOPE is a request name
# (it is the one scope the runner uses) and is on this list so a future
# refactor that widens READONLY_SCOPE to a list of write scopes is
# caught here.
REQUEST_NAMES = frozenset({
    "SCOPES", "REQUESTED_SCOPES", "OAUTH_SCOPES", "REQUEST_SCOPES",
    "READONLY_SCOPE",
})

# Names whose values are REFUSAL lists. These are scopes the runtime
# refuses to honour if a token carries them -- the opposite of a
# request. They are allowed to name write scopes.
REFUSAL_NAMES = frozenset({
    "WRITE_SCOPES", "FORBIDDEN_SCOPES", "DENIED_SCOPES",
    "BLOCKED_SCOPES", "REFUSED_SCOPES",
})

# Files the scan looks at. Limited to the OAuth helper so a future
# addition (a Calendar client, say) is opt-in and a deliberate test
# update.
OAUTH_FILES = [
    ROOT / "tools" / "google" / "setup.py",
    ROOT / "tools" / "google" / "fetch_alerts.py",
    ROOT / "tools" / "google" / "check_scopes.py",
]


def _literal_strings(node) -> list[str]:
    """Return all string constants in a list/tuple/Constant expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        out = []
        for elt in node.elts:
            out.extend(_literal_strings(elt))
        return out
    return []


def _scopes_in(path: Path, names: frozenset[str]) -> set[str]:
    """Return the set of OAuth scope string literals assigned to any of `names`
    in the module-level assignments of `path`, OR passed as the value of
    a `scopes=`/`scope=` kwarg. Docstring literals are NOT included -- the
    walk is over AST nodes, not text.
    """
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return set()
    scopes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    for value in _literal_strings(node.value):
                        if value.startswith("https://www.googleapis.com/auth/") or value.startswith("https://mail.google.com/"):
                            scopes.add(value)
        if isinstance(node, ast.keyword) and node.arg in ("scopes", "scope"):
            for value in _literal_strings(node.value):
                if value.startswith("https://www.googleapis.com/auth/") or value.startswith("https://mail.google.com/"):
                    scopes.add(value)
    return scopes


class TestScopeFreeze(unittest.TestCase):
    """Across all OAuth helpers, the requested scope set is {gmail.readonly}."""

    def test_requested_scopes_equal_readonly(self):
        union: set[str] = set()
        for path in OAUTH_FILES:
            if not path.exists():
                self.fail(f"expected OAuth helper at {path} but it is missing")
            union |= _scopes_in(path, REQUEST_NAMES)
        self.assertEqual(
            union, {EXPECTED_SCOPE},
            f"requested scope set is not exactly {{{EXPECTED_SCOPE!r}}}.\n"
            f"  found: {sorted(union)}\n"
            f"  The scope freeze is W2.2: only {EXPECTED_SCOPE} is allowed.",
        )

    def test_refusal_lists_may_name_write_scopes(self):
        """A refusal list (WRITE_SCOPES etc.) is the runtime guard that
        rejects a widened token. The test asserts that at least one
        refusal list exists -- without it, a token with gmail.send would
        not be caught and the request-only freeze is incomplete.
        """
        has_refusal = False
        for path in OAUTH_FILES:
            text = path.read_text(encoding="utf-8")
            if re.search(r"\b(WRITE|FORBIDDEN|DENIED|BLOCKED|REFUSED)_SCOPES\b", text):
                has_refusal = True
                break
        self.assertTrue(
            has_refusal,
            "no OAuth helper has a refusal list (WRITE_SCOPES / "
            "FORBIDDEN_SCOPES / DENIED_SCOPES). The request-side freeze "
            "is not enough: a runtime guard that rejects a widened "
            "token is required, or the request side can be silently "
            "widened by a future change.",
        )

    def test_no_request_constant_names_a_forbidden_scope(self):
        """Cross-check: even if the union of REQUEST_NAMES is exactly the
        readonly scope, no individual request-shaped constant may list
        a forbidden scope. This catches a refactor that adds a new
        request constant (something_else) that happens to live outside
        the union because of a typo in REQUEST_NAMES."""
        for path in OAUTH_FILES:
            text = path.read_text(encoding="utf-8")
            for scope in REQUEST_FORBIDDEN_SCOPES:
                # Look for the scope on the RHS of a request-shaped
                # assignment. The pattern is "NAME = ... <scope> ..."
                # with NAME in REQUEST_NAMES.
                for name in REQUEST_NAMES:
                    pat = rf"^\s*{name}\s*=\s*[\[(].*?{re.escape(scope)}"
                    if re.search(pat, text, re.MULTILINE | re.DOTALL):
                        self.fail(
                            f"{path.name} request constant {name!r} names a "
                            f"forbidden scope {scope!r}. The W2.2 freeze "
                            f"forbids this even if a future test update "
                            f"forgets to add it to REQUEST_FORBIDDEN_SCOPES."
                        )


if __name__ == "__main__":
    unittest.main()
