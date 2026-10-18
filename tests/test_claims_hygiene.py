"""CL-XX document hygiene.

CLAIMS.md is the project's constitution: every public statement
about the project must be backed by a current verification.
A claim that says "Roadmap" while the code is shipped is a
lie a future reader can be misled by. This test enforces
basic hygiene:

  1. Every CL-XXX claim has a unique number.
  2. Every claim has a status (Current / Beta / Roadmap).
  3. Every claim has a Verification pointer (a test file
     or a shipped file path).
  4. Every claim has a "Last verified" date.
  5. Roadmap claims do not have shipped work as their
     verification pointer (a sanity check that the
     document is up to date with the codebase).

This is a small but high-signal test: a contributor who
adds a new claim and forgets the verification pointer
fails the build. A contributor who demotes a current
claim to roadmap and forgets to delete the test fails
the build.

Run:  python3 -m unittest tests.test_claims_hygiene -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLAIMS = ROOT / "CLAIMS.md"
DOC = CLAIMS.read_text(encoding="utf-8")


class TestClaimsDocument(unittest.TestCase):

    def setUp(self) -> None:
        # Re-read each time the test runs in isolation; the
        # module-level read is fine because the file does
        # not change mid-run.
        self.doc = CLAIMS.read_text(encoding="utf-8")

    def test_each_claim_has_a_status(self) -> None:
        """Every claim has a status: Current, Beta, or Roadmap.
        A blank status is a definition that drifted."""
        # Find every "#### CL-XXX" line and inspect the status
        # token on the same line. The status line uses an
        # em-dash separator ("#### CL-001 — Current") and the
        # status can carry a suffix like "Current (W3.4)".
        claim_re = re.compile(
            r"^#### CL-(\d+)\s*[—–-]\s*([A-Z][a-z]+(?:\s*\([^)]+\))?)\s*$",
            re.M,
        )
        claims = claim_re.findall(self.doc)
        self.assertGreater(
            len(claims), 10,
            "expected at least 10 claims in CLAIMS.md"
        )
        valid_statuses = {"Current", "Beta", "Roadmap"}
        for n, status in claims:
            root_status = status.split(" ")[0]
            self.assertIn(
                root_status, valid_statuses,
                f"CL-{n} has status {status!r}; "
                f"must be one of {valid_statuses}"
            )

    def test_claim_numbers_are_unique(self) -> None:
        """Every CL-XXX number is unique. A duplicate is a typo
        that the reader cannot recover from."""
        nums = re.findall(r"^#### CL-(\d+)", self.doc, re.M)
        dups = {n for n in nums if nums.count(n) > 1}
        self.assertEqual(
            dups, set(),
            f"CLAIMS.md has duplicate CL numbers: {sorted(dups)}"
        )

    def test_every_claim_has_a_verification_line(self) -> None:
        """Every claim has a `- **Verification:**` line. A claim
        without a verification is a promise, not a fact."""
        # Slice into claim blocks
        blocks = re.split(r"^#### CL-", self.doc, flags=re.M)[1:]
        for i, block in enumerate(blocks, 1):
            first_line = block.splitlines()[0]
            num = first_line.split(" ")[0].strip()
            self.assertIn(
                "**Verification:**", block,
                f"CL-{num} has no `**Verification:**` line. "
                f"A claim without a verification is a promise, "
                f"not a fact."
            )

    def test_every_claim_has_a_last_verified_date(self) -> None:
        """Every claim has a `- **Last verified:**` line. A claim
        that has not been re-verified recently is stale and
        the README is not allowed to point at it."""
        blocks = re.split(r"^#### CL-", self.doc, flags=re.M)[1:]
        for block in blocks:
            first_line = block.splitlines()[0]
            num = first_line.split(" ")[0].strip()
            self.assertIn(
                "**Last verified:**", block,
                f"CL-{num} has no `**Last verified:**` line. "
                f"Reader cannot tell whether the verification "
                f"is current."
            )

    def test_roadmap_claims_do_not_point_at_shipped_work(self) -> None:
        """A Roadmap claim is a promise of future work. If the
        verification pointer names a shipped file or test, the
        claim is dishonest: the work is shipped, the claim
        should be Current. This test surfaces that drift."""
        # Find every claim block.
        blocks = re.split(r"^#### CL-", self.doc, flags=re.M)[1:]
        for block in blocks:
            first_line = block.splitlines()[0]
            num = first_line.split(" ")[0].strip()
            if "Roadmap" not in first_line:
                continue
            # A roadmap claim's verification is allowed to be
            # "when shipped" or to name a future path. If it
            # points at a file that exists, that's drift.
            m = re.search(
                r"\*\*Verification:\*\*\s*`?([^`\n]+)", block
            )
            if not m:
                continue
            pointer = m.group(1).strip()
            # Strip "(when shipped)" and other qualifiers
            pointer = re.sub(r"\s*\(when\s+shipped\)\s*", "", pointer)
            pointer = re.sub(r"\s*\(future\)\s*", "", pointer)
            # If the pointer looks like a file path, check it.
            # (We treat test_foo.py and tools/foo.py as paths,
            # and prose like "tests/test_xxx (when shipped)" as
            # not a path -- the regex strips "(when shipped)".)
            looks_like_path = (
                "/" in pointer or
                pointer.endswith(".py") or
                pointer.endswith(".yml") or
                pointer.endswith(".yaml") or
                pointer.endswith(".md")
            )
            if not looks_like_path:
                continue
            path = ROOT / pointer
            self.assertFalse(
                path.exists(),
                f"CL-{num} is labelled Roadmap but its "
                f"verification pointer {pointer!r} exists on "
                f"disk at {path}. The work is shipped; the "
                f"claim must be Current."
            )

    def test_no_legacy_three_band_verdict_term(self) -> None:
        """CLAIMS.md describes the gate's contract for
        a public reader. If the doc uses the legacy
        3-band term "suitable verdict" (as if
        `suitable` were a single verdict), the
        reader is misled: the gate has four verdicts
        (`STRONG_MATCH`, `POTENTIAL_MATCH`,
        `NEEDS_RESEARCH`, `NOT_SUITABLE`), and the
        term `suitable` is no longer a constant --
        it is the obsolete umbrella for the two
        non-NEEDS-RESEARCH, non-NOT-SUITABLE
        verdicts.

        This test asserts the doc does not
        use the legacy term in a verdict
        context. The pattern
        `"suitable" verdict` (or any
        near-variant) is the legacy usage.
        A reader who has not seen the
        code would interpret "suitable
        verdict" as a single band and
        miss the 4-band nuance.

        A legitimate use of the word
        "suitable" -- e.g. in narrative
        prose talking about the goal
        ("nothing suitable slips by") --
        is allowed: only the verdict
        context is pinned.
        """
        # The legacy usage is the phrase
        # '"suitable" verdict' or the bare
        # word "suitable" appearing as a
        # verdict name (e.g. "A suitable
        # verdict means..."). The pattern
        # matches quoted or capitalised
        # usage in a verdict context.
        legacy_patterns = [
            # "A 'suitable' verdict means..." or
            # "A 'suitable' verdict is..." -- the
            # exact drift caught in CLAIMS.md L33.
            r'\bsuitable\b.{0,5}\bverdict\b',
            r'\bverdict\b.{0,5}\bsuitable\b',
            # "SUITABLE" as a bare verdict name
            # (all caps) -- would imply it is
            # one of the four constants.
            r'\bSUITABLE\b(?!_)',
        ]
        offenders: list[str] = []
        for i, line in enumerate(self.doc.split("\n"), 1):
            for pattern in legacy_patterns:
                if re.search(pattern, line, re.I):
                    # Skip the historical record
                    # in CHANGELOG entries that
                    # legitimately mention the
                    # 3-band vocabulary to
                    # describe the rename.
                    if "CHANGELOG" in line or "changelog" in line:
                        continue
                    # Skip lines that mention the
                    # rename from 3-band to
                    # 4-band in a historical
                    # context (e.g. "renamed
                    # from SUITABLE to
                    # STRONG_MATCH").
                    if "rename" in line.lower() or "renamed" in line.lower():
                        continue
                    offenders.append(f"L{i}: {line.strip()[:100]}")
        if offenders:
            self.fail(
                "CLAIMS.md uses the legacy 3-band "
                "verdict term 'suitable' in a "
                "verdict context. The gate has 4 "
                "verdicts (STRONG_MATCH, "
                "POTENTIAL_MATCH, NEEDS_RESEARCH, "
                "NOT_SUITABLE); the legacy term "
                "'suitable' is no longer a constant "
                "and using it as a verdict name "
                "misleads readers. Use the actual "
                "verdict name(s) explicitly. "
                "Offending lines:\n  "
                + "\n  ".join(offenders)
            )


if __name__ == "__main__":
    unittest.main()
