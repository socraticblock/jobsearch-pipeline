"""Acceptance tests for the source layer's first adapter (RemoteOK).

Everything here runs offline: the adapter takes an injected fetcher, exactly as
``enrich`` does with its page fetcher, so no test depends on a live endpoint or
on the network being up.

The tests are written around the promises the source layer makes, not around
its implementation:

* a missing field stays missing (None), it is never guessed;
* a description is stored only when the source supplied one;
* a dead endpoint is a recorded failure, never "no jobs today";
* re-ingesting the same postings adds no rows;
* a provider's terms travel with the adapter that depends on them.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jobsearch import db as db_mod
from jobsearch import ingest as ingest_mod
from jobsearch.sources import base, remoteok

NOTICE = {
    "last_updated": 1792022419,
    "legal": (
        "API Terms of Service: Please link back (with follow, and without nofollow!) "
        "to the URL on Remote OK and mention Remote OK as a source."
    ),
}
FULL = {
    "id": "1137512",
    "position": "AI Automation Engineer",
    "company": "Example Labs",
    "location": "",
    "salary_min": 80000,
    "salary_max": 110000,
    "date": "2026-10-14T01:31:49+00:00",
    "url": "https://remoteok.com/remote-jobs/example-1137512",
    "tags": ["engineer"],
    "description": "<p>We are hiring an engineer to build agent workflows. TypeScript required.</p>",
}
REMOTE_NAMED = {
    "id": "1137513",
    "position": "Remote Full-Stack Developer",
    "company": "Second Co",
    "location": "Worldwide",
    "date": "2026-10-13T09:00:00+00:00",
    "url": "https://remoteok.com/remote-jobs/second-1137513",
    "description": "<div><li>Node.js</li><li>React</li></div>",
}
NO_DESCRIPTION = {
    "id": "1137514",
    "position": "Platform Engineer",
    "company": "Third Co",
    "location": "",
    "url": "https://remoteok.com/remote-jobs/third-1137514",
    "description": "",
}
NO_IDENTITY = {"position": "Mystery Role", "company": "", "url": None, "description": ""}


def board(*elements) -> str:
    return json.dumps([NOTICE, *elements])


def fetcher_returning(body: str):
    return lambda url: (200, body)


class RemoteOkAdapterTests(unittest.TestCase):
    def fetch(self, body: str):
        return remoteok.fetch(fetcher=fetcher_returning(body))

    # --- mapping: what the source said, and nothing more -------------------
    def test_terms_notice_is_not_mistaken_for_a_posting(self) -> None:
        listings, run = self.fetch(board(FULL, REMOTE_NAMED))
        self.assertEqual(run.status, "ok")
        self.assertEqual(run.items, 2)
        self.assertNotIn("legal", [getattr(x, "title", None) for x in listings])

    def test_full_description_is_captured(self) -> None:
        listings, run = self.fetch(board(FULL))
        self.assertTrue(listings[0].has_description)
        self.assertIn("agent workflows", listings[0].description)
        self.assertEqual(run.items_with_description, 1)

    def test_html_is_converted_to_text_not_stored_as_markup(self) -> None:
        listings, _ = self.fetch(board(REMOTE_NAMED))
        self.assertNotIn("<li>", listings[0].description)
        self.assertIn("Node.js", listings[0].description)

    def test_empty_description_stays_none(self) -> None:
        listings, run = self.fetch(board(NO_DESCRIPTION))
        self.assertIsNone(listings[0].description)
        self.assertFalse(listings[0].has_description)
        self.assertEqual(run.items_with_description, 0)

    def test_empty_location_is_none_and_remote_is_not_invented(self) -> None:
        listings, _ = self.fetch(board(FULL))
        self.assertIsNone(listings[0].location)
        self.assertIsNone(listings[0].remote, "no location and no text: remote must stay unstated")

    def test_remote_is_read_from_the_source_text_when_it_says_so(self) -> None:
        listings, _ = self.fetch(board(REMOTE_NAMED))
        self.assertEqual(listings[0].remote, "remote")

    def test_salary_is_labelled_as_published_because_no_currency_is_given(self) -> None:
        listings, _ = self.fetch(board(FULL))
        salary = listings[0].salary_text
        self.assertIn("80,000", salary)
        self.assertIn("110,000", salary)
        self.assertNotIn("$", salary, "the payload states no currency; inventing one is a fabricated fact")
        self.assertIn("not stated", salary)

    def test_posting_without_any_salary_has_none(self) -> None:
        listings, _ = self.fetch(board(REMOTE_NAMED))
        self.assertIsNone(listings[0].salary_text)

    def test_unidentifiable_element_is_counted_not_dressed_up(self) -> None:
        listings, run = self.fetch(board(NO_IDENTITY))
        self.assertEqual(run.items, 1)
        self.assertEqual(run.items_missing_identity, 1)
        self.assertIsNone(listings[0].external_job_id)
        self.assertIsNone(listings[0].company)

    # --- failure is evidence, not silence ---------------------------------
    def test_http_failure_is_a_failed_run_not_an_empty_board(self) -> None:
        def boom(url):
            raise base.FetchError("HTTP 503 for remoteok", status=503)

        listings, run = remoteok.fetch(fetcher=boom)
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.http_status, 503)
        self.assertIn("503", run.error)

    def test_non_json_body_is_a_failure_not_an_empty_board(self) -> None:
        listings, run = self.fetch("<html>maintenance</html>")
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("not JSON", run.error)

    def test_json_that_is_not_a_list_is_a_failure(self) -> None:
        listings, run = self.fetch('{"jobs": []}')
        self.assertEqual(listings, [])
        self.assertEqual(run.status, "failed")
        self.assertIn("expected a JSON array", run.error)

    def test_non_http_url_is_refused_before_any_request(self) -> None:
        with self.assertRaises(base.FetchError):
            base.fetch_json("file:///etc/passwd")

    def test_run_evidence_serialises_the_outcome(self) -> None:
        _listings, run = self.fetch(board(FULL, NO_DESCRIPTION))
        payload = run.as_dict()
        self.assertEqual(payload["items"], 2)
        self.assertEqual(payload["items_with_description"], 1)
        self.assertEqual(payload["status"], "ok")

    def test_record_run_appends_rather_than_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-runs.jsonl"
            _listings, run = self.fetch(board(FULL))
            base.record_run(run, path)
            base.record_run(run, path)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["source"], "remoteok")

    # --- terms travel with the adapter ------------------------------------
    def test_remoteok_attribution_is_required_and_recorded_verbatim(self) -> None:
        policy = remoteok.SPEC.policy
        self.assertTrue(policy.attribution_required)
        self.assertIn("nofollow", policy.terms_quote)
        self.assertEqual(policy.verified_on, "2026-10-15")
        lines = base.required_attribution([remoteok.SPEC])
        self.assertEqual(len(lines), 1)
        self.assertIn("Remote OK", lines[0])

    def test_required_attribution_is_empty_when_no_source_requires_it(self) -> None:
        spec = base.SourceSpec(
            kind="feed_api", name="quiet", external_ref="", homepage="",
            policy=base.SourcePolicy(
                terms_url="", verified_on="2026-10-15", attribution_required=False
            ),
        )
        self.assertEqual(base.required_attribution([spec]), [])


class SourceIngestTests(unittest.TestCase):
    """The adapter path must obey the same ledger rules as the email path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "jobs.db"
        self.con = db_mod.connect(self.db)

    def tearDown(self) -> None:
        self.con.close()
        self._tmp.cleanup()

    def ingest_board(self, body: str):
        listings, run = remoteok.fetch(fetcher=fetcher_returning(body))
        stats = ingest_mod.ingest_listings(
            self.con, listings,
            source_kind=remoteok.SPEC.kind,
            source_name=remoteok.SPEC.name,
            external_ref=remoteok.SPEC.external_ref,
            raw_ref="remoteok:test",
        )
        return stats, run

    def test_description_reaches_the_ledger_as_complete(self) -> None:
        stats, _ = self.ingest_board(board(FULL))
        self.assertEqual(stats["new_jobs"], 1)
        row = self.con.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual(row["description_state"], "complete")
        self.assertIn("agent workflows", row["description"])
        self.assertEqual(row["company"], "Example Labs")

    def test_no_description_means_incomplete_and_null_never_a_guess(self) -> None:
        self.ingest_board(board(NO_DESCRIPTION))
        row = self.con.execute("SELECT * FROM jobs").fetchone()
        self.assertIsNone(row["description"])
        self.assertEqual(row["description_state"], "incomplete")

    def test_reingest_adds_no_rows(self) -> None:
        first, _ = self.ingest_board(board(FULL, REMOTE_NAMED))
        second, _ = self.ingest_board(board(FULL, REMOTE_NAMED))
        self.assertEqual(first["new_jobs"], 2)
        self.assertEqual(second["new_jobs"], 0)
        self.assertEqual(second["seen_jobs"], 2)
        self.assertEqual(second["unique_jobs"], 2)

    def test_identity_is_the_strong_form_from_the_source_id(self) -> None:
        self.ingest_board(board(FULL))
        key = self.con.execute("SELECT dedupe_key FROM jobs").fetchone()["dedupe_key"]
        self.assertEqual(key, "remoteok:id:1137512")

    def test_unidentifiable_listing_is_skipped_and_counted(self) -> None:
        listings = [base.SourceListing()]  # nothing at all: not a row anyone can act on
        stats = ingest_mod.ingest_listings(
            self.con, listings, source_kind="feed_api", source_name="remoteok"
        )
        self.assertEqual(stats["skipped_unidentifiable"], 1)
        self.assertEqual(stats["new_jobs"], 0)
        self.assertEqual(stats["unique_jobs"], 0)

    def test_known_values_are_never_overwritten_with_later_blanks(self) -> None:
        self.ingest_board(board(FULL))
        thinner = remoteok.SourceListing(
            external_job_id="1137512", title=None, company=None, location=None
        )
        ingest_mod.ingest_listings(
            self.con, [thinner], source_kind="feed_api", source_name="remoteok"
        )
        row = self.con.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual(row["title"], "AI Automation Engineer")
        self.assertEqual(row["company"], "Example Labs")

    def test_a_later_full_description_fills_a_blank_without_overwriting(self) -> None:
        self.ingest_board(board(NO_DESCRIPTION))
        self.assertIsNone(self.con.execute("SELECT description FROM jobs").fetchone()["description"])
        filled = remoteok.SourceListing(
            external_job_id="1137514", title="Platform Engineer", company="Third Co",
            description="Full text arrived on a later pass.",
        )
        ingest_mod.ingest_listings(self.con, [filled], source_kind="feed_api", source_name="remoteok")
        row = self.con.execute("SELECT description, description_state FROM jobs").fetchone()
        self.assertEqual(row["description_state"], "complete")
        self.assertIn("later pass", row["description"])

    def test_the_adapter_path_records_a_sighting(self) -> None:
        self.ingest_board(board(FULL))
        sightings = self.con.execute("SELECT COUNT(*) c FROM sightings").fetchone()["c"]
        self.assertEqual(sightings, 1)

    def test_email_path_and_adapter_path_agree_on_identity(self) -> None:
        """Same source, same id, two different entry points -> one row."""
        self.ingest_board(board(FULL))
        listings = [remoteok.SourceListing(
            external_job_id="1137512", title="AI Automation Engineer", company="Example Labs"
        )]
        stats = ingest_mod.ingest_listings(
            self.con, listings, source_kind="feed_api", source_name="remoteok"
        )
        self.assertEqual(stats["new_jobs"], 0)
        self.assertEqual(stats["unique_jobs"], 1)


if __name__ == "__main__":
    unittest.main()
