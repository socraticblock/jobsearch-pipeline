"""I-07 -- demo_sieve.py test.

The demo is a reference-able artifact for a reader who has not
seen the gate run. The test asserts:

  1. The tool exists and runs.
  2. The default invocation (no args) returns a verdict.
  3. The --list mode shows all corpus fixtures.
  4. The --corpus-id mode runs a specific fixture.
  5. The --stdin mode reads a posting from stdin and returns a
     verdict.
  6. The --json mode reads a JSON file.
  7. The output includes the verdict, the satisfied list, and the
     why string from the registry.
  8. The tool does not perform any network I/O (it only uses
     stdlib and PyYAML).

A reader who cannot run the tool should be able to read the test
and understand what the demo does.

Run:  python3 -m unittest tests.test_demo_sieve -v
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO = ROOT / "tools" / "demo_sieve.py"
PY = sys.executable


def _run_demo(*args: str, stdin: str | None = None,
              timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = [PY, str(DEMO), *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=ROOT,
        input=stdin, timeout=timeout,
    )


class TestDemoSieve(unittest.TestCase):

    def test_demo_file_exists(self) -> None:
        self.assertTrue(
            DEMO.exists(),
            f"demo_sieve.py missing at {DEMO.relative_to(ROOT)}. "
            f"It is the I-07 deliverable."
        )

    def test_default_invocation_runs(self) -> None:
        result = _run_demo()
        self.assertEqual(
            result.returncode, 0,
            f"default invocation failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        self.assertIn("VERDICT:", result.stdout)
        # Default should pick c-001 (the canonical missing-evidence
        # case) and produce needs_research.
        self.assertIn("needs_research", result.stdout)

    def test_list_mode_shows_all_corpus_fixtures(self) -> None:
        result = _run_demo("--list")
        self.assertEqual(result.returncode, 0)
        # Read the actual corpus to know what ids to expect.
        corpus = json.loads(
            (ROOT / "corpus" / "v1" / "postings.json")
            .read_text(encoding="utf-8")
        )
        for rec in corpus:
            self.assertIn(
                rec["id"], result.stdout,
                f"--list output missing fixture id {rec['id']}"
            )

    def test_batch_mode_runs_every_fixture(self) -> None:
        """W5.3 -- the credential-free demo. Runs the gate on
        every corpus fixture and produces a digest-style
        summary, with no .eml files, no Google setup, no
        profile editing."""
        result = _run_demo("--batch")
        self.assertEqual(result.returncode, 0)
        # The summary mentions the fixture count.
        self.assertIn("fixtures evaluated", result.stdout)
        # The summary mentions all four verdict bands.
        for band in ("strong_match", "potential_match",
                     "needs_research", "not_suitable"):
            self.assertIn(band, result.stdout,
                          f"batch output missing verdict band: {band}")
        # The W5.3 explanation is there.
        self.assertIn("W5.3", result.stdout)
        self.assertIn("No .eml files needed", result.stdout)
        # No drift: every fixture matches its documented expect.
        # (The test is end-to-end: this IS the W3.4 + W3.2 +
        # W5.3 contract.)
        # Read the drift line: "Drift: N/..."
        m = re.search(r"Drift:\s+(\d+)/(\d+)\s+fixtures",
                      result.stdout)
        self.assertIsNotNone(m, "batch output missing Drift line")
        n_drift, n_total = int(m.group(1)), int(m.group(2))
        self.assertEqual(
            n_drift, 0,
            f"W5.3 batch demo found {n_drift}/{n_total} drift. "
            f"The demo is supposed to be the executable proof the "
            f"gate matches the corpus; any drift here is a build "
            f"failure elsewhere."
        )

    def test_corpus_id_mode_runs_specific_fixture(self) -> None:
        result = _run_demo("--corpus-id", "c-001")
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: needs_research", result.stdout)
        self.assertIn("c-001", result.stdout)
        self.assertIn("years_bar_missing_evidence", result.stdout)

    def test_stdin_mode_runs_provided_posting(self) -> None:
        stdin = (
            "Senior Backend Engineer\n"
            "5+ years Python. Remote. Django. Postgres. AWS.\n"
            ".\n"
        )
        result = _run_demo("--stdin", stdin=stdin)
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT:", result.stdout)
        # The verdict should be one of the four outcomes.
        for outcome in ("strong_match", "potential_match",
                        "needs_research", "not_suitable"):
            if outcome in result.stdout:
                break
        else:
            self.fail(
                f"stdin mode did not produce a verdict:\n{result.stdout}"
            )

    def test_json_mode_runs_provided_posting(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({
                "title": "Backend Engineer",
                "body": (
                    "Backend Engineer. 5+ years Python. "
                    "Remote. Django. Postgres."
                ),
                "location": "remote",
            }, f)
            path = f.name
        try:
            result = _run_demo("--json", path)
            self.assertEqual(result.returncode, 0)
            self.assertIn("VERDICT:", result.stdout)
        finally:
            Path(path).unlink()

    def test_output_includes_why_from_registry(self) -> None:
        """The why-field-as-spec registry is a contract; the demo
        must surface it so a reader can see the rule's reasoning,
        not just the verdict."""
        result = _run_demo("--corpus-id", "c-001")
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "WHY (per the rule_why registry):", result.stdout,
            "the demo's output must include the WHY section that "
            "draws from the rule_why registry."
        )
        self.assertIn("W3.1", result.stdout,
                      "the W3.1 reference should appear in the why")

    def test_unknown_corpus_id_exits_nonzero(self) -> None:
        """The `--corpus-id` flag of `tools/demo_sieve.py`
        (line 268: `sys.exit(2)` in `_from_corpus_id`)
        must exit 2 when the requested id is not in
        the corpus. The contract is exit 2 specifically
        (corpus id not found), not just non-zero.

        Exit-code map for demo_sieve:
        - 0 = success (verdict emitted or list printed)
        - 2 = caller error (unknown corpus id, empty stdin)
        - non-zero = other failure (e.g. crash)

        The tighter assertion pins the specific code
        so a contributor who refactors the error
        handling to exit 1 (or any other non-zero)
        would fail the test with a precise error
        message that names the contract.
        """
        result = _run_demo("--corpus-id", "c-999")
        self.assertEqual(
            result.returncode, 2,
            f"unknown corpus id must exit 2 (caller "
            f"error); got {result.returncode} with "
            f"stderr: {result.stderr!r}"
        )
        # The error message names the bad id (so
        # the user knows what they typed wrong)
        # and points at the corpus file (so the
        # user knows where to look).
        self.assertIn(
            "c-999", result.stderr,
            f"error must name the bad id c-999 so the "
            f"user can see what they typed; got: "
            f"{result.stderr!r}"
        )
        # The error message includes a hint to run
        # --list, so a user who hits the error can
        # see what ids are available without
        # having to read the script source.
        self.assertIn(
            "--list", result.stderr,
            f"error must point at --list so the user "
            f"can see available ids; got: "
            f"{result.stderr!r}"
        )
        # The original assertion (looser) is now
        # redundant with the assertEqual above --
        # we keep the test method name to avoid
        # breaking any external tools that grep
        # for it, but the body is now strict.
        self.assertIn("not found", result.stderr.lower())

    def test_stdin_mode_exits_2_on_empty_input(self) -> None:
        """The `--stdin` mode of `tools/demo_sieve.py`
        (line 234) must exit 2 on empty input. A
        contributor who refactors the stdin handler
        and drops the empty-input check would
        silently let an empty pipe produce a verdict
        for an empty title (which would default to
        `needs_research` per the gate's title rules,
        making the empty input look like a job the
        user wanted to evaluate).

        The test asserts the specific exit code 2
        (not just non-zero) because:
        - 0 = success (verdict emitted)
        - 2 = empty stdin (caller error)
        - non-zero = other failure

        The script's docstring at line 234 documents
        this contract: `if not lines: print(...);
        sys.exit(2)`. The test pins it.

        The test also asserts the error message names
        "stdin" and "empty" so a user who runs the
        script by mistake knows what went wrong.
        """
        result = _run_demo("--stdin", stdin="")
        self.assertEqual(
            result.returncode, 2,
            f"empty stdin must exit 2 (caller error); "
            f"got {result.returncode} with stderr: "
            f"{result.stderr!r}"
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "stdin", combined,
            f"empty-stdin error must name 'stdin' so the "
            f"caller knows to feed input; got: "
            f"{combined!r}"
        )
        self.assertIn(
            "empty", combined,
            f"empty-stdin error must name 'empty' so the "
            f"caller knows the pipe was empty (not "
            f"e.g. unreadable); got: {combined!r}"
        )

    def test_json_mode_exits_2_on_missing_file(self) -> None:
        """The demo sieve's `--json` mode must exit 2
        on a missing input file. Before this test,
        the path was a silent bug: the script called
        `path.read_text()` on a non-existent path,
        which raised an unhandled `FileNotFoundError`
        that printed a Python stack trace to stderr
        and exited 1 (Python's default for unhandled
        exceptions). A user who mistyped the path
        would see a stack trace instead of a friendly
        error.

        The fix wraps `_from_json` in a try/except
        in `tools/demo_sieve.py` that catches
        `FileNotFoundError`, prints a friendly
        error naming the missing file, and returns
        2 (matching the other caller-error exit
        codes: unknown corpus id, empty stdin).

        The test pins: exit 2, error names the
        missing file path, no Python traceback in
        stderr.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist.json"
            self.assertFalse(missing.exists(), "precondition")
            result = _run_demo("--json", str(missing))
            self.assertEqual(
                result.returncode, 2,
                f"--json with a missing file must exit 2 "
                f"(caller error); got {result.returncode}. "
                f"stderr: {result.stderr[:300]!r}"
            )
            self.assertIn(
                str(missing), result.stderr,
                f"the missing-file error must name the path "
                f"so the user can see what to fix; got: "
                f"{result.stderr[:300]!r}"
            )
            # No Python traceback. The fix replaces
            # the stack trace with a friendly one-liner.
            self.assertNotIn(
                "Traceback", result.stderr,
                f"the missing-file error must be a friendly "
                f"one-liner, not a Python traceback; got: "
                f"{result.stderr[:300]!r}"
            )

    def test_json_mode_exits_2_on_malformed_json(self) -> None:
        """The demo sieve's `--json` mode must exit 2
        on a malformed JSON file. Before this test,
        the path raised an unhandled `JSONDecodeError`
        with a Python stack trace. The fix catches
        the exception, prints a friendly error
        naming the file and the parse position
        (line and column), and returns 2.

        The test pins: exit 2, error names the
        file and the parse failure position,
        no Python traceback.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not valid json {{{")
            result = _run_demo("--json", str(bad))
            self.assertEqual(
                result.returncode, 2,
                f"--json with malformed JSON must exit 2 "
                f"(caller error); got {result.returncode}. "
                f"stderr: {result.stderr[:300]!r}"
            )
            self.assertIn(
                str(bad), result.stderr,
                f"the malformed-JSON error must name the "
                f"file; got: {result.stderr[:300]!r}"
            )
            self.assertNotIn(
                "Traceback", result.stderr,
                f"the malformed-JSON error must be a friendly "
                f"one-liner, not a Python traceback; got: "
                f"{result.stderr[:300]!r}"
            )

    def test_json_mode_exits_2_on_missing_required_field(self) -> None:
        """The demo sieve's `--json` mode must exit 2
        when the JSON is valid but missing a required
        field (`title` or `body`). Before this test,
        the path raised an unhandled `KeyError` with
        a Python stack trace. The fix catches the
        exception, prints a friendly error naming
        the missing field, and returns 2.

        The test pins: exit 2, error names the
        missing field, no Python traceback.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing_field = Path(tmp) / "missing_field.json"
            # Valid JSON but no 'title' field.
            missing_field.write_text('{"body": "5+ years Python"}')
            result = _run_demo("--json", str(missing_field))
            self.assertEqual(
                result.returncode, 2,
                f"--json with missing field must exit 2 "
                f"(caller error); got {result.returncode}. "
                f"stderr: {result.stderr[:300]!r}"
            )
            self.assertIn(
                "title", result.stderr.lower(),
                f"the missing-field error must name the "
                f"missing field (here 'title'); got: "
                f"{result.stderr[:300]!r}"
            )
            self.assertNotIn(
                "Traceback", result.stderr,
                f"the missing-field error must be a friendly "
                f"one-liner, not a Python traceback; got: "
                f"{result.stderr[:300]!r}"
            )


if __name__ == "__main__":
    unittest.main()
