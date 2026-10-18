"""The first run — `tools/first_run.py` test.

`tools/first_run.py` is the deliverable that shows the *pipeline* work, where
`tools/demo_sieve.py` shows the gate work: an alert email becomes ledger rows,
enrichment supplies the descriptions, and the real digest renderer prints the
shortlist. This test asserts the parts that make it evidence rather than a
screenshot:

  1. It runs on a clean checkout and exits 0.
  2. The digest it prints contains a STRONG MATCH **with the quoted evidence
     behind it** -- the product's central promise.
  3. A posting with no description is NEEDS_RESEARCH, not a drop.
  4. A posting that fails a quoted essential is dropped and counted, not
     hidden.
  5. It never reads or writes the owner's real ledger (`var/jobs.db`).
  6. Its run directory is regenerable: a second run over the same path works.
  7. It performs no network I/O (the sample pages are read from disk).
  8. Every shipped sample file declares itself synthetic.
  9. The narration names the enrichment step, so the "your inbox has no
     descriptions until you enrich" explanation cannot be dropped silently.

Run:  python3 -m unittest tests.test_first_run -v
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "first_run.py"
SAMPLES = ROOT / "fixtures" / "first_run"
REAL_LEDGER = ROOT / "var" / "jobs.db"
PY = sys.executable

SYNTHETIC_MARKER = "SYNTHETIC ONLY"


def _run(run_dir: Path) -> subprocess.CompletedProcess:
    """Run the tool with a throwaway run directory, from the repo root."""
    return subprocess.run(
        [PY, str(TOOL), "--run-dir", str(run_dir)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestFirstRun(unittest.TestCase):

    def test_tool_exists(self) -> None:
        self.assertTrue(
            TOOL.exists(),
            f"first_run.py missing at {TOOL.relative_to(ROOT)}. It is the "
            f"entry point that shows the pipeline run end to end.",
        )

    def test_exits_zero_and_prints_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
            self.assertEqual(
                result.returncode, 0,
                f"first_run.py failed:\n{result.stdout}\n{result.stderr}",
            )
            self.assertIn("Job shortlist", result.stdout)
            self.assertIn("Nothing has been sent, applied to, or submitted",
                          result.stdout)

    def test_digest_shows_a_strong_match_with_its_quoted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn(
                "STRONG MATCH", result.stdout,
                f"the sample must produce at least one strong match; the "
                f"first-run walkthrough has nothing to show without it:\n"
                f"{result.stdout}",
            )
            self.assertIn("Why:", result.stdout)
            self.assertIn("technology held: python", result.stdout)
            # The local-market line carries the posting's own words.
            self.assertIn("local market:", result.stdout)
            self.assertIn("based in Riverton", result.stdout)

    def test_no_description_is_needs_research_not_a_drop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("NEEDS RESEARCH", result.stdout)
            self.assertIn("description incomplete", result.stdout)
            self.assertIn("Description: incomplete", result.stdout)

    def test_failed_essential_is_dropped_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
            self.assertEqual(result.returncode, 0, result.stdout)
            # Same digest header the real renderer prints: the drop is
            # reported as a count, and the job itself is not rendered.
            self.assertIn("1 dropped as not suitable", result.stdout)
            digest = result.stdout.split("Step 3/4")[1].split("Step 4/4")[0]
            self.assertNotIn(
                "PHP", digest,
                "a hard-failed posting must not be rendered into the "
                "shortlist; only its count belongs in the header",
            )

    def test_it_never_touches_the_real_ledger(self) -> None:
        if not REAL_LEDGER.exists():
            self.skipTest("no real ledger at var/jobs.db on this checkout")
        before = _sha256(REAL_LEDGER)
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            _sha256(REAL_LEDGER), before,
            "first_run.py modified the owner's real ledger. It must build "
            "its own throwaway ledger and leave var/jobs.db alone.",
        )

    def test_writes_only_below_the_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            result = _run(run_dir)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(
                (run_dir / "jobs.db").exists(),
                "the throwaway ledger was not built below --run-dir",
            )
            self.assertIn("was not read or written", result.stdout)

    def test_the_run_dir_is_regenerable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            first = _run(run_dir)
            second = _run(run_dir)
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertEqual(
                second.returncode, 0,
                f"a second run over an existing run directory failed -- it "
                f"must regenerate rather than accumulate:\n{second.stdout}",
            )
            self.assertIn("ledger now : 4 job(s)", second.stdout)

    def test_no_network_io(self) -> None:
        """The walkthrough must work with no network. The sample pages are
        read from disk; a network primitive in this tool is a bug."""
        text = TOOL.read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import requests", "import httpx",
                          "import socket", "from urllib", "from requests",
                          "from httpx", "from socket"):
            self.assertNotIn(
                forbidden, text,
                f"first_run.py imports {forbidden!r}; the first run must "
                f"perform no network I/O.",
            )

    def test_the_shipped_sample_declares_itself_synthetic(self) -> None:
        profile = SAMPLES / "profile.sample.yaml"
        self.assertTrue(profile.is_file(), f"missing {profile}")
        lines = [l.strip() for l in profile.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        first = lines[0].lstrip("#").strip() if lines else ""
        self.assertTrue(
            first.startswith(SYNTHETIC_MARKER),
            f"{profile.relative_to(ROOT)} must open with the synthetic "
            f"marker; got {lines[0][:60]!r}",
        )
        data_files = [p for p in SAMPLES.rglob("*") if p.is_file()]
        self.assertGreaterEqual(len(data_files), 5, "the sample shrank")
        for path in data_files:
            self.assertIn(
                SYNTHETIC_MARKER, path.read_text(encoding="utf-8"),
                f"{path.relative_to(ROOT)} carries no synthetic marker. A "
                f"shipped sample that might be real data is a legal exposure.",
            )

    def test_the_narration_names_the_enrichment_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "run")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("python3 -m jobsearch.enrich", result.stdout)
            self.assertIn("no network call", result.stdout)


if __name__ == "__main__":
    unittest.main()
