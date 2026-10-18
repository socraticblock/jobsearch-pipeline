"""W4.3 -- Bounded retries, no evasion.

The Gmail API call gets bounded exponential backoff on
429/5xx. After N attempts the run is killed with a recorded
reason, not silently retried forever. No proxy rotation,
no UA spoof, no captcha solve -- only the retry loop.

Borrowed shape: Google API client library's built-in
retry/backoff (the default 100s total budget is too generous
for our cron; we cap at 5 attempts and 31s total). The
"no evasion" half is a tree-level scan: the fetch path
must not import a proxy, a UA-spoof helper, a captcha
solver, or any of the obvious bypass primitives.

Run:  python3 -m unittest tests.test_bounded_retry -v
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A tiny stub HttpError that mimics googleapiclient's shape:
# it carries a `status_code` and a `reason`.
class _StubHttpError(Exception):
    def __init__(self, status_code: int, reason: str = "rate limit"):
        super().__init__(f"{status_code} {reason}")
        self.status_code = status_code
        self.reason = reason


class TestBoundedRetry(unittest.TestCase):
    """W4.3 -- the retry loop is bounded and observable."""

    def test_429_retries_then_succeeds(self) -> None:
        """A 429 on the first call, success on the second:
        the run completes and stats record exactly one
        retry."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}

        def call():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _StubHttpError(429)
            return {"messages": []}

        # Sleep 0s so the test runs in finite time. We
        # patch time.sleep via monkey-patching below.
        orig_sleep = fetch_alerts.time.sleep
        fetch_alerts.time.sleep = lambda s: None
        try:
            result = fetch_alerts._api_call_with_retry(
                call, label="messages.list", stats=stats
            )
        finally:
            fetch_alerts.time.sleep = orig_sleep

        self.assertEqual(calls["n"], 2,
                         "expected 1 retry + 1 success = 2 calls")
        self.assertEqual(stats.get("retried"), 1)
        self.assertEqual(stats.get("retry_exhausted"), 0)
        self.assertEqual(result, {"messages": []})

    def test_429_exhausts_after_max_attempts(self) -> None:
        """A 429 that never goes away: the loop runs N
        attempts, then raises SystemExit(4) with a recorded
        reason."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}

        def call():
            calls["n"] += 1
            raise _StubHttpError(429)

        orig_sleep = fetch_alerts.time.sleep
        fetch_alerts.time.sleep = lambda s: None
        try:
            with self.assertRaises(SystemExit) as cm:
                fetch_alerts._api_call_with_retry(
                    call, label="messages.list", stats=stats
                )
        finally:
            fetch_alerts.time.sleep = orig_sleep

        self.assertEqual(cm.exception.code, 4,
                         "exhausted retry must exit 4, not 0")
        self.assertEqual(
            calls["n"], fetch_alerts.RETRY_MAX_ATTEMPTS,
            f"expected exactly {fetch_alerts.RETRY_MAX_ATTEMPTS} "
            f"attempts, got {calls['n']}"
        )
        self.assertEqual(stats.get("retried"),
                         fetch_alerts.RETRY_MAX_ATTEMPTS)
        self.assertEqual(stats.get("retry_exhausted"), 1)

    def test_4xx_other_than_429_does_not_retry(self) -> None:
        """A 401, 403, 404 is a hard fail: the token is
        broken or revoked, and retrying just wastes the
        user's quota. The loop does NOT retry these."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}

        def call():
            calls["n"] += 1
            raise _StubHttpError(401, "invalid token")

        with self.assertRaises(_StubHttpError):
            fetch_alerts._api_call_with_retry(
                call, label="messages.list", stats=stats
            )

        self.assertEqual(calls["n"], 1,
                         "a 401 must not retry; got 1 attempt")
        self.assertEqual(stats.get("retried", 0), 0,
                         "a 401 must not be recorded as a retry")

    def test_5xx_is_retried(self) -> None:
        """A 503 (server error) is a transient signal and
        gets the same backoff as 429."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}

        def call():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _StubHttpError(503, "service unavailable")
            return {"ok": True}

        orig_sleep = fetch_alerts.time.sleep
        fetch_alerts.time.sleep = lambda s: None
        try:
            result = fetch_alerts._api_call_with_retry(
                call, label="messages.list", stats=stats
            )
        finally:
            fetch_alerts.time.sleep = orig_sleep

        self.assertEqual(calls["n"], 2)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(stats.get("retried"), 1)

    def test_connection_error_is_retried(self) -> None:
        """A bare ConnectionError (no status_code) is a
        transient signal and gets the backoff."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}

        def call():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("DNS blip")
            return {"ok": True}

        orig_sleep = fetch_alerts.time.sleep
        fetch_alerts.time.sleep = lambda s: None
        try:
            fetch_alerts._api_call_with_retry(
                call, label="messages.list", stats=stats
            )
        finally:
            fetch_alerts.time.sleep = orig_sleep

        self.assertEqual(calls["n"], 2)
        self.assertEqual(stats.get("retried"), 1)

    def test_backoff_doubles_each_attempt(self) -> None:
        """The backoff delay starts at RETRY_BASE_DELAY and
        doubles each attempt. A contributor who changes
        the multiplier silently breaks the rate limit
        etiquette."""
        from tools.google import fetch_alerts

        calls = {"n": 0}
        stats: dict = {}
        sleeps: list[float] = []

        def call():
            calls["n"] += 1
            if calls["n"] < 4:
                raise _StubHttpError(429)
            return {"ok": True}

        orig_sleep = fetch_alerts.time.sleep
        fetch_alerts.time.sleep = lambda s: sleeps.append(s)
        try:
            fetch_alerts._api_call_with_retry(
                call, label="messages.list", stats=stats
            )
        finally:
            fetch_alerts.time.sleep = orig_sleep

        # 3 retries, so 3 sleeps, each double the previous.
        self.assertEqual(len(sleeps), 3)
        # The first sleep is the base delay; each next is
        # double.
        self.assertEqual(sleeps[0], fetch_alerts.RETRY_BASE_DELAY)
        self.assertEqual(sleeps[1], fetch_alerts.RETRY_BASE_DELAY * 2)
        self.assertEqual(sleeps[2], fetch_alerts.RETRY_BASE_DELAY * 4)

    def test_no_evasion_in_the_fetch_path(self) -> None:
        """W4.3 + CL-014: the fetch path does not import a
        proxy, a UA-spoof helper, a captcha solver, or any
        of the obvious bypass primitives. This is a tree
        scan, not an AST scan, because the threat is a
        contributor copy-pasting from a blog post.

        The scan ignores lines that are inside a triple-
        quoted string OR a `#` comment, so the W4.3
        rationale comment ("we never proxy-rotate, ...")
        does not trip the test on itself.
        """
        # Banned patterns: anything that smells like
        # auto-rotation, headless-browser automation, or
        # captcha solve.
        FORBIDDEN = (
            r"proxy-rotate",
            r"proxy\.Pool",
            r"User-Agent.*spoof",
            r"rotate_user_agent",
            r"fake_ua",
            r"captcha",
            r"two_captcha",
            r"anticaptcha",
            r"puppeteer",
            r"playwright",
            r"selenium",
            r"requests_html",
        )
        # The fetch path lives here. We scan the whole
        # tools/google/ tree; the bypass primitives would
        # not be legitimate anywhere in the project.
        target = (ROOT / "tools" / "google").resolve()
        for src in sorted(target.rglob("*.py")):
            text = src.read_text(encoding="utf-8", errors="ignore")
            # Strip comments and docstrings so the W4.3
            # rationale itself does not trip the test.
            # (Stripping strings risks false negatives in
            # data files; this tree is .py only.)
            cleaned = re.sub(r"#.*$", "", text, flags=re.M)
            cleaned = re.sub(r'"""[\s\S]*?"""', "", cleaned)
            cleaned = re.sub(r"'''[\s\S]*?'''", "", cleaned)
            for pat in FORBIDDEN:
                if re.search(pat, cleaned, re.IGNORECASE):
                    # Find the actual line for the error
                    # message.
                    for lineno, line in enumerate(
                        text.splitlines(), 1
                    ):
                        if re.search(pat, line, re.IGNORECASE):
                            self.fail(
                                f"{src.relative_to(ROOT)}:{lineno} "
                                f"matches forbidden pattern {pat!r}: "
                                f"{line.strip()[:60]!r}. The fetch "
                                f"path is bounded retry only; any "
                                f"evasion primitive is a CL-014 "
                                f"violation."
                            )


if __name__ == "__main__":
    unittest.main()
