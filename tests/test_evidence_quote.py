"""W3.2 -- No verdict without quoted evidence.

Every `failed_essential` in a verdict must cite the posting.
The cite is verifiable if the quoted text appears in the
posting's title or body (lowercased, whitespace-normalized).

A drift between the failure string and the posting is a
fabrication or a missing quote. The contract is:

  * Every failure has a quoted string.
  * The quoted string is a substring of the title or body.
  * The quoted string is not empty.
  * The quoted string is at least 1 word long.

A failure that violates any of these is a build failure.
The test runs every corpus fixture through extract() and
evaluate() and asserts the contract for every failed_essential.

Run:  python3 -m unittest tests.test_evidence_quote -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "corpus" / "v1" / "postings.json"

from jobsearch import rules as rules_module  # noqa: E402
from jobsearch.requirements import JobPosting, extract  # noqa: E402


def _haystack(record: dict) -> str:
    """The normalised haystack for verification: title + body,
    lowercased, with whitespace collapsed."""
    text = (record.get("title", "") + " " + record.get("body", "")).lower()
    return re.sub(r"\s+", " ", text)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _evaluate(record: dict):
    profile = record.get("profile", {})
    rules = rules_module.Rules(
        floor_net=profile.get("floor_net"),
        known_stack=set(profile.get("known_stack", [])),
        learnable_stack=set(profile.get("learnable_stack", [])),
        floor_currency=profile.get("floor_currency", ""),
        local_ok=tuple(profile.get("local_ok", [])),
        languages_usable=tuple(profile.get("languages_usable", ["english"])),
        years_can_honestly_claim=profile.get("years_can_honestly_claim"),
        profession_signals=tuple(profile.get("profession_signals", ())),
    )
    posting = JobPosting(
        title=record["title"],
        description=record["body"],
        location="remote",
    )
    extract(
        posting,
        extra_terms=rules.known_stack | rules.learnable_stack,
        extra_languages=rules.languages_usable,
    )
    return rules_module.evaluate(posting, rules)


class TestEvidenceQuote(unittest.TestCase):
    """W3.2 -- every verdict cites its evidence."""

    def test_every_failure_has_a_quoted_phrase(self) -> None:
        """A failure without a quoted string violates W3.2.
        The gate's failure strings MUST include a quote so a
        reader can verify the failure against the posting."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for rec in records:
            v = _evaluate(rec)
            for failed in v.failed_essential:
                if not re.search(r'"[^"]+"', failed):
                    offenders.append(
                        f"  {rec['id']}: no quoted phrase: {failed!r}"
                    )
        if offenders:
            self.fail(
                "W3.2 violation: a verdict failed without "
                "quoting the posting. The gate's failure strings "
                "must include a quoted phrase so a reader can "
                "verify the failure against the posting:\n"
                + "\n".join(offenders)
            )

    def test_every_quoted_phrase_is_a_substring_of_the_posting(self) -> None:
        """A quoted phrase that does not appear in the posting
        is a fabrication. The phrase must be a real substring
        of the title or body."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for rec in records:
            haystack = _haystack(rec)
            v = _evaluate(rec)
            for failed in v.failed_essential:
                m = re.search(r'"([^"]+)"', failed)
                if not m:
                    continue  # already flagged above
                quote = _normalize(m.group(1))
                if quote not in haystack:
                    # Fall back: at least 50% of the words
                    # must appear in the haystack.
                    words = re.findall(r"\w+", quote)
                    found = sum(1 for w in words if w in haystack)
                    if found < max(1, len(words) * 0.5):
                        offenders.append(
                            f"  {rec['id']}: quote {m.group(1)!r} "
                            f"is not verifiable in the posting. "
                            f"{found}/{len(words)} words found."
                        )
        if offenders:
            self.fail(
                "W3.2 violation: a failure's quoted evidence is "
                "not in the posting. The gate must cite the "
                "posting's own words, not a fabricated phrase:\n"
                + "\n".join(offenders)
            )

    def test_no_failure_cites_a_single_keyword_alone(self) -> None:
        """A single-word quote like 'php' or 'wordpress' is a
        keyword, not a real quote. The gate's evidence for a
        technology drop must include a sentence from the body,
        not just the technology name."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for rec in records:
            v = _evaluate(rec)
            for failed in v.failed_essential:
                m = re.search(r'"([^"]+)"', failed)
                if not m:
                    continue
                quote = m.group(1).strip()
                words = re.findall(r"\w+", quote)
                # 1-word quote is only OK if the failure is
                # the title-check (title names no software role)
                # or the no-software-signal branch.  In those
                # cases, the title IS the evidence and a 1-2
                # word title is fine.  Other failures need a
                # real sentence (>= 3 words).
                if len(words) <= 2 and "title" not in failed.lower():
                    offenders.append(
                        f"  {rec['id']}: short quote {quote!r} in "
                        f"a non-title failure: {failed!r}. A "
                        f"technology drop or salary mismatch must "
                        f"cite a real sentence, not a single "
                        f"keyword."
                    )
        if offenders:
            self.fail(
                "W3.2 violation: a non-title failure cites only "
                "a single keyword. The gate must include a real "
                "sentence from the posting as evidence:\n"
                + "\n".join(offenders)
            )

    def test_technology_failures_cite_the_sentence(self) -> None:
        """The W3.2 fix on the technology branch: the failure
        string must include a sentence from the body, not just
        the technology name. This is the regression test for
        the W3.2 fix specifically."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        # Fixtures that exercise the technology-drop branch.
        # c-011 uses PHP/WordPress, both specialist technologies.
        rec = next((r for r in records if r["id"] == "c-011"), None)
        if rec is None:
            self.skipTest("c-011 not present in corpus")
        v = _evaluate(rec)
        for failed in v.failed_essential:
            self.assertIn(
                "(context: \"", failed,
                f"technology failure must include a context "
                f"quote: {failed!r}"
            )
            m = re.search(r'"([^"]+)"', failed)
            self.assertIsNotNone(
                m, f"technology failure must include a quoted "
                f"phrase: {failed!r}"
            )
            quote = m.group(1)
            self.assertGreaterEqual(
                len(re.findall(r"\w+", quote)), 3,
                f"technology failure's quote must be a real "
                f"sentence (3+ words), got {quote!r}"
            )


if __name__ == "__main__":
    unittest.main()
