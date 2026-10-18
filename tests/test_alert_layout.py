"""Regression tests for the LinkedIn alert layout the parser used to get wrong.

Every case here comes from a real alert email:

  * the parser read LinkedIn's "This company is actively hiring" badge as a job
    title -- 9 of the 12 rows in the first real alert were that badge, each
    carrying a real job id, so each would have entered the ledger as a job;
  * `location` was empty on all 12 rows, which silently disabled the owner's
    location/remote rule while looking like it had passed;
  * the plain-text part was merged before the HTML part, so a text-path guess
    outranked the per-card data (a header line became job 1's title).

fixtures/alert_005_card_layout.eml reproduces that structure with invented data.
var/real_alerts/ holds the genuine emails, on this machine only.

Run:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch.parse_alert import (  # noqa: E402
    _is_boilerplate,
    _listings_from_text,
    parse_message,
)

FIXTURES = ROOT / "fixtures"
CARD_FIXTURE = FIXTURES / "alert_005_card_layout.eml"


class TestFurnitureIsNotATitle(unittest.TestCase):
    def test_known_linkedin_furniture_is_rejected(self):
        for line in (
            "This company is actively hiring",
            "Actively recruiting",
            "Be an early applicant",
            "Easy Apply",
            "Promoted",
            "12 applicants",
            "Your job alert has been created: Software Engineer in Dublin, Ireland.",
            "You’ll receive notifications when new jobs are posted that match your search preferences.",
        ):
            self.assertTrue(_is_boilerplate(line), f"{line!r} must not be usable as a title")

    def test_real_job_titles_survive_the_filter(self):
        for title in (
            "Senior Platform Engineer",
            "ML Engineer",
            "Data Platform Engineer",
            "Staff Software Engineer, Golang",
            "AI/Machine Learning Engineer with Databricks",
            "Senior Application Architect (Modernization & Delivery Enablement)",
        ):
            self.assertFalse(_is_boilerplate(title), f"{title!r} must not be filtered out")


class TestCardLayout(unittest.TestCase):
    """One `data-test-id="job-card"` block per job: title, then
    "Company · Location", then a badge."""

    EXPECTED = {
        "4012346100": ("Senior Platform Engineer", "Northwind", "Remote"),
        "4012346101": ("Machine Learning Engineer", "Globex", "Dublin, Ireland"),
        "4012346102": ("Backend Engineer, Go", "Initech", "Hybrid Dublin, Ireland"),
    }

    def setUp(self):
        self.pm = parse_message(CARD_FIXTURE.read_bytes())
        self.by_id = {listing.external_job_id: listing for listing in self.pm.listings}

    def test_every_card_yields_a_complete_listing(self):
        self.assertEqual(len(self.pm.listings), 3)
        self.assertEqual(set(self.by_id), set(self.EXPECTED))
        for job_id, (title, company, location) in self.EXPECTED.items():
            listing = self.by_id[job_id]
            self.assertEqual(listing.title, title, f"title for {job_id}")
            self.assertEqual(listing.company, company, f"company for {job_id}")
            self.assertEqual(listing.location, location, f"location for {job_id}")

    def test_badge_is_never_used_as_a_title(self):
        for listing in self.pm.listings:
            self.assertFalse(
                _is_boilerplate(listing.title),
                f"badge text {listing.title!r} was stored as a job title",
            )

    def test_location_is_present_on_every_listing(self):
        # The original defect: an empty location makes the location/remote rule a
        # no-op that still reports success.
        for listing in self.pm.listings:
            self.assertTrue(listing.location, f"{listing.external_job_id} has no location")

    def test_plain_text_part_cannot_outrank_the_card_data(self):
        # The fixture's plain-text part is FIRST in the MIME message and its first
        # block carries the alert header. A text-first merge therefore stored the
        # header as job 1's title; HTML must win.
        first = self.by_id["4012346100"]
        self.assertNotIn("job alert", (first.title or "").lower())
        self.assertNotIn("notification", (first.company or "").lower())
        self.assertEqual(first.company, "Northwind")


class TestDashSeparatedPlainText(unittest.TestCase):
    """Real alerts divide jobs with a run of dashes, not blank lines, and put
    company and location on their own lines."""

    TEXT = (
        "Your job alert has been created: Software Engineer in Dublin, Ireland.\n"
        "\nYou’ll receive notifications when new jobs are posted that match your search preferences.\n"
        "\nSenior Platform Engineer\nNorthwind\nRemote\nActively recruiting\n"
        "View job: https://www.linkedin.com/comm/jobs/view/4012346100?trackingId=z\n"
        "\n" + "-" * 57 + "\n"
        "\nML Engineer\nGlobex\nDublin, Ireland\n"
        "View job: https://www.linkedin.com/comm/jobs/view/4012346101?trackingId=z\n"
    )

    def setUp(self):
        self.listings = {l.external_job_id: l for l in _listings_from_text(self.TEXT)}

    def test_both_jobs_are_found(self):
        self.assertEqual(set(self.listings), {"4012346100", "4012346101"})

    def test_header_is_not_borrowed_as_a_title(self):
        for listing in self.listings.values():
            self.assertIsNotNone(listing.title)
            self.assertFalse(_is_boilerplate(listing.title), f"{listing.title!r}")

    def test_company_and_location_come_from_their_own_lines(self):
        self.assertEqual(self.listings["4012346100"].title, "Senior Platform Engineer")
        self.assertEqual(self.listings["4012346100"].company, "Northwind")
        self.assertEqual(self.listings["4012346100"].location, "Remote")
        self.assertEqual(self.listings["4012346101"].company, "Globex")
        self.assertEqual(self.listings["4012346101"].location, "Dublin, Ireland")


if __name__ == "__main__":
    unittest.main()
