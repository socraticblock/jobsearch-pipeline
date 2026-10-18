"""I-20 -- ACKNOWLEDGEMENTS.md content test.

The file must exist, must name every project this project borrowed
from, and must not be a verbatim copy of any source project's
MANIFESTO, LEGAL_DISCLAIMER, or SECURITY document. A short header
that lists the projects and one paragraph per project is the shape;
the test enforces the shape, not the words.

Run:  python3 -m unittest tests.test_acknowledgements -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACK = ROOT / "ACKNOWLEDGEMENTS.md"

# Projects the borrow log must mention. The list is the source of
# truth: when a new project is borrowed from, add it here AND in
# the ACKNOWLEDGEMENTS.md file. The test fails if the file is
# silent on any project the assistant has recorded.
PROJECTS = [
    "career-ops",
    "JobCtrl",
    "JobNavigator",
    "Jobstead",
    "inbox-job-tracker",
    "sift-roles",
    "jobsync",
    "jobseek",
]


class TestAcknowledgements(unittest.TestCase):

    def test_acknowledgements_file_exists(self) -> None:
        self.assertTrue(
            ACK.exists(),
            f"ACKNOWLEDGEMENTS.md missing at {ACK.relative_to(ROOT)}. "
            f"It is the I-20 deliverable."
        )

    def test_file_is_substantial(self) -> None:
        text = ACK.read_text(encoding="utf-8")
        # A real acknowledgements file names the projects, lists
        # what was borrowed, and states what was not. Anything
        # under 1KB is a stub.
        self.assertGreater(
            len(text),
            1024,
            f"ACKNOWLEDGEMENTS.md is too short ({len(text)} chars). "
            f"A real file names every project, lists the borrowed "
            f"items, and states what was not borrowed."
        )

    def test_file_names_every_borrowed_project(self) -> None:
        text = ACK.read_text(encoding="utf-8").lower()
        missing: list[str] = []
        for project in PROJECTS:
            if project.lower() not in text:
                missing.append(project)
        if missing:
            self.fail(
                f"ACKNOWLEDGEMENTS.md does not mention the following "
                f"projects that the borrow log has named:\n  "
                + "\n  ".join(missing)
                + "\nEither add a paragraph to the file, or remove "
                f"the project from tests/test_acknowledgements.py "
                f"PROJECTS if the borrow was retracted."
            )

    def test_file_distinguishes_borrowed_from_copied(self) -> None:
        """The file must state that no code or verbatim text is
        copied. A reader who skims must not be left to wonder."""
        text = ACK.read_text(encoding="utf-8").lower()
        # Look for the key idea: "does not copy" / "no verbatim" /
        # "rewritten in this project's voice" -- the language is
        # not asserted, the idea is.
        markers = [
            "no code",
            "not a fork",
            "verbatim",
            "rewritten",
            "own voice",
            "does not copy",
        ]
        hits = [m for m in markers if m in text]
        self.assertGreaterEqual(
            len(hits),
            2,
            f"ACKNOWLEDGEMENTS.md does not clearly distinguish "
            f"borrowed ideas from copied text. Found only: {hits}. "
            f"A reviewer who skims must not be left to wonder whether "
            f"this is a derivative work or a fork."
        )

    def test_file_names_what_was_not_borrowed(self) -> None:
        """The 'What was not borrowed' section is what protects the
        project from a later reader who assumes an absence is a
        gap. The test asserts the section exists."""
        text = ACK.read_text(encoding="utf-8").lower()
        self.assertIn(
            "not borrowed",
            text,
            "ACKNOWLEDGEMENTS.md must contain a 'What was not "
            "borrowed' section so a reader does not have to wonder "
            "whether the absence of a feature is a deliberate "
            "choice or a gap."
        )


if __name__ == "__main__":
    unittest.main()
