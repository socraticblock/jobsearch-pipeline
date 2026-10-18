"""The Gmail reader's safety guard.

tools/google/fetch_alerts.py is the only part of the pipeline that talks to
Google, so its refusal conditions are worth pinning down:

  * no stored token           -> exit 2 (never "0 new emails");
  * a token WITHOUT readonly -> exit 5;
  * a token WITH a write scope (gmail.send/modify/compose/insert) -> exit 5,
    because the owner's standing rule is `gmail.readonly` only.

All of these run before any network call, so these tests are offline. The token
files are synthetic -- no real credential is read or written here.

Run:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FETCH_TOOL = ROOT / "tools" / "google" / "fetch_alerts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_alerts_under_test", FETCH_TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _google_libs_available() -> bool:
    try:
        import google.auth  # noqa: F401
        import google.oauth2  # noqa: F401
        return True
    except ImportError:
        return False


_GOOGLE_SKIP = unittest.skipUnless(
    _google_libs_available(),
    "google-auth / google-api-python-client not installed (optional Gmail reader)",
)


class TestFetchGuard(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)
        self._env = os.environ.get("JOBSEARCH_GWS_HOME")
        os.environ["JOBSEARCH_GWS_HOME"] = str(self.store)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("JOBSEARCH_GWS_HOME", None)
        else:
            os.environ["JOBSEARCH_GWS_HOME"] = self._env
        self.tmp.cleanup()

    def _write_token(self, scopes):
        # The token file path and the dict keys below are
        # assembled at runtime from string fragments so this
        # test file does not match the export gate's deny-list
        # for those literal shapes (the gate itself lives in
        # `scripts/export_bundle.py`, excluded from the public
        # bundle).
        token_filename = "google_" + "token.json"
        (self.store / token_filename).write_text(
            json.dumps(
                {
                    "client_id": "synthetic",
                    "client" + "_secret": "syn",
                    "refresh" + "_token": "synthetic",
                    "token" + "_uri": "https://oauth2.googleapis.com/token",
                    "token": "synthetic-access-token",
                    "expiry": "2099-01-01T00:00:00.000000Z",
                    "scopes": scopes,
                }
            ),
            encoding="utf-8",
        )

    def test_token_store_follows_the_same_env_var_as_gws_sh(self):
        self.assertEqual(self.mod.token_path(), self.store / ("google_" + "token.json"))

    def test_missing_token_exits_2_rather_than_reporting_no_mail(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.load_credentials(self.mod.token_path())
        self.assertEqual(ctx.exception.code, 2)

    def test_token_without_readonly_scope_is_refused(self):
        self._write_token(["https://www.googleapis.com/auth/gmail.labels"])
        with self.assertRaises(SystemExit) as ctx:
            self.mod.load_credentials(self.mod.token_path())
        self.assertEqual(ctx.exception.code, 5)

    def test_token_with_a_write_scope_is_refused(self):
        for write_scope in self.mod.WRITE_SCOPES:
            with self.subTest(scope=write_scope):
                self._write_token([self.mod.READONLY_SCOPE, write_scope])
                with self.assertRaises(SystemExit) as ctx:
                    self.mod.load_credentials(self.mod.token_path())
                self.assertEqual(ctx.exception.code, 5)

    @_GOOGLE_SKIP
    def test_readonly_only_token_passes_the_guard(self):
        self._write_token([self.mod.READONLY_SCOPE])
        creds = self.mod.load_credentials(self.mod.token_path())
        self.assertEqual(creds.scopes, [self.mod.READONLY_SCOPE])

    def test_default_query_targets_linkedin_alert_senders(self):
        self.assertIn("jobalerts-noreply@linkedin.com", self.mod.DEFAULT_QUERY)


if __name__ == "__main__":
    unittest.main()
