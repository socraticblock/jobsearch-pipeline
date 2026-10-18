"""I-06 -- COMPARISON.md shape and content test.

Borrowed shape from JobCtrl's docs/comparison.md. The test asserts:

  1. The document exists at docs/COMPARISON.md.
  2. The document is substantial (>2KB of opinion).
  3. The document has the three sections: "What this project does",
     "What this project does NOT do", "Where it sits in the
     ecosystem" -- the borrowed shape, in this project's voice.
  4. The document names the four-outcome vocabulary
     (strong_match, potential_match, needs_research, not_suitable)
     so a reader can find it without reading the code.
  5. The "what it is NOT" table is at least as long as the "what
     it IS" table, because a sieve's value is partly in the
     things it refuses to do.

A doc that drifts from the shape is a build failure; the
comparison is part of the project's public contract.

Run:  python3 -m unittest tests.test_comparison -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMPARISON = ROOT / "docs" / "COMPARISON.md"


class TestComparison(unittest.TestCase):

    def test_comparison_file_exists(self) -> None:
        self.assertTrue(
            COMPARISON.exists(),
            f"COMPARISON.md missing at {COMPARISON.relative_to(ROOT)}. "
            f"It is the I-06 deliverable: a capability matrix in "
            f"the JobCtrl shape, in this project's voice."
        )

    def test_comparison_is_substantial(self) -> None:
        text = COMPARISON.read_text(encoding="utf-8")
        # 2KB of opinion. A short doc would be a stub.
        self.assertGreater(
            len(text),
            2048,
            f"COMPARISON.md is too short ({len(text)} chars). A "
            f"real comparison has all three sections, the "
            f"vocabulary, and the ecosystem mapping."
        )

    def test_comparison_has_three_sections(self) -> None:
        """The borrowed shape has three sections: what it does,
        what it does NOT do, where it sits in the ecosystem."""
        text = COMPARISON.read_text(encoding="utf-8").lower()
        self.assertIn(
            "what this project does",
            text,
            "must have a 'What this project does' section."
        )
        self.assertIn(
            "what this project does not",
            text,
            "must have a 'What this project does NOT do' section."
        )
        self.assertIn(
            "where it sits in the ecosystem",
            text,
            "must have a 'Where it sits in the ecosystem' section."
        )

    def test_comparison_lists_four_outcome_vocabulary(self) -> None:
        """The reader who skims the doc must find the four
        outcomes without reading the code. The four are the
        public contract."""
        text = COMPARISON.read_text(encoding="utf-8")
        for outcome in (
            "strong_match",
            "potential_match",
            "needs_research",
            "not_suitable",
        ):
            self.assertIn(
                outcome,
                text,
                f"COMPARISON.md must name the {outcome} outcome "
                f"explicitly; it is part of the public contract."
            )

    def test_not_doing_table_is_at_least_as_long_as_doing_table(self) -> None:
        """A sieve's value is partly in the things it refuses to
        do. The 'does NOT do' table should be at least as long
        as the 'does' table. A reader who finds the project is
        checking for the refusal, not just the capabilities."""
        text = COMPARISON.read_text(encoding="utf-8")
        # Count table rows in each section. A row is a line that
        # starts with '| ... |' (with content in at least one
        # cell). The split point is the heading "## What this
        # project does NOT do".
        does_match = re.search(
            r"## What this project does\b(.*?)## What this project does NOT do",
            text, re.DOTALL,
        )
        doesnot_match = re.search(
            r"## What this project does NOT do(.*?)## Where it sits",
            text, re.DOTALL,
        )
        self.assertIsNotNone(does_match, "missing 'does' section")
        self.assertIsNotNone(doesnot_match, "missing 'does NOT do' section")
        def row_count(s: str) -> int:
            # A table row has at least 2 columns.
            return sum(1 for line in s.splitlines()
                       if line.startswith("|") and line.count("|") >= 3
                       and "---" not in line)
        does = row_count(does_match.group(1))
        doesnot = row_count(doesnot_match.group(1))
        self.assertGreaterEqual(
            doesnot, does,
            f"'does NOT do' table ({doesnot} rows) is shorter than "
            f"'does' table ({does} rows). A sieve's value is partly "
            f"in the things it refuses to do; the refusal should be "
            f"at least as long as the capability list."
        )

    def test_comparison_mentions_borrowed_projects(self) -> None:
        """The ecosystem section must reference the same projects
        the borrow log names. A reader cross-referencing the two
        documents should not find a project mentioned in one but
        not the other."""
        text = COMPARISON.read_text(encoding="utf-8")
        ack_text = (ROOT / "ACKNOWLEDGEMENTS.md").read_text(encoding="utf-8")
        # Project names to check (loose; case-insensitive).
        for name in ("career-ops", "JobCtrl", "JobNavigator",
                     "inbox-job-tracker", "jobsync"):
            self.assertIn(
                name, text,
                f"COMPARISON.md ecosystem section must mention {name}."
            )

    def test_comparison_acknowledges_borrowing(self) -> None:
        """The doc must say, in plain language, that the SHAPE was
        borrowed. A reader who skims must not be left to wonder
        whether the matrix shape is original."""
        text = COMPARISON.read_text(encoding="utf-8").lower()
        markers = ["borrowed", "jobctrl", "shape from"]
        hits = [m for m in markers if m in text]
        self.assertGreaterEqual(
            len(hits), 2,
            f"COMPARISON.md does not clearly acknowledge the "
            f"borrowed shape. Found only: {hits}. A reader must "
            f"not be left to wonder whether the matrix is original."
        )


if __name__ == "__main__":
    unittest.main()
