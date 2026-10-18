"""Assertions against genuine LinkedIn alert emails, when they are present.

var/real_alerts/ holds real alerts kept on this machine only -- var/ is excluded
from the shipped bundle, so a copy of this project never carries someone's mail.
When the directory is empty (any fresh copy) these tests SKIP rather than fail.

The assertions encode exactly what the real mail exposed: a badge stored as a
title, and a location that was never read.

Run:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch.parse_alert import _is_boilerplate, parse_message  # noqa: E402

REAL_ALERTS = sorted((ROOT / "var" / "real_alerts").glob("*.eml"))


@unittest.skipUnless(REAL_ALERTS, "no real alert emails present (var/real_alerts is empty)")
class TestRealAlerts(unittest.TestCase):
    def test_every_real_alert_yields_complete_listings(self):
        for path in REAL_ALERTS:
            pm = parse_message(path.read_bytes())
            with self.subTest(alert=path.name):
                self.assertEqual(pm.source_name, "linkedin_job_alert")
                self.assertGreaterEqual(len(pm.listings), 1, "no listings found at all")
                for listing in pm.listings:
                    self.assertIsNotNone(listing.external_job_id)
                    self.assertIsNotNone(listing.title, "title missing")
                    self.assertIsNotNone(listing.company, "company missing")
                    self.assertIsNotNone(listing.location, "location missing")
                    self.assertFalse(
                        _is_boilerplate(listing.title),
                        f"badge {listing.title!r} stored as a title",
                    )


if __name__ == "__main__":
    unittest.main()
