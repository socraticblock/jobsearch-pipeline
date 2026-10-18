"""Test that the release-privacy GitHub Action is well-formed.

This test is a static check: it asserts the YAML parses, contains
the expected jobs, and does not silently auto-bypass the licence
check (a common way an over-eager CI hides owner-gated decisions).

Run:  python3 -m unittest tests.test_release_workflow -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORKFLOW = ROOT / ".github" / "workflows" / "release-privacy.yml"


def _parse_yaml(text: str) -> dict:
    """Minimal YAML parser using PyYAML if present, else a regex
    fallback for the small subset we need."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_yaml_fallback(text)
    return yaml.safe_load(text)


def _parse_yaml_fallback(text: str) -> dict:
    """A fragile YAML subset parser. PyYAML is the real path; this
    is here for environments where it is not installed."""
    import re
    out: dict = {}
    stack: list[tuple[int, dict]] = [(-1, out)]
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        # Top-level "name: foo" or list "- item"
        m = re.match(r"^(\s*)(\S+):\s*(.*)$", line)
        if m:
            indent = len(m.group(1))
            key = m.group(2)
            value = m.group(3)
            # Pop the stack to current indent
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if value:
                parent[key] = value.strip('"').strip("'")
            else:
                child: dict = {}
                parent[key] = child
                stack.append((indent, child))
    return out


class TestReleaseWorkflow(unittest.TestCase):

    def test_workflow_file_exists(self) -> None:
        self.assertTrue(
            WORKFLOW.exists(),
            f"release-privacy.yml missing at {WORKFLOW.relative_to(ROOT)}. "
            f"This is the I-19 / W7.1 deliverable."
        )

    def test_workflow_yaml_parses(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        data = _parse_yaml(text)
        self.assertIsInstance(data, dict)
        self.assertEqual(
            data.get("name"),
            "release-privacy",
            "workflow name must be 'release-privacy'"
        )

    def test_workflow_has_both_jobs(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        data = _parse_yaml(text)
        jobs = data.get("jobs", {})
        self.assertIn("verify", jobs, "must have a 'verify' job that runs tools/verify.sh")
        self.assertIn(
            "privacy",
            jobs,
            "must have a 'privacy' job that scans the built tree"
        )

    def test_workflow_runs_on_push_and_pr(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        # Look for 'on: push' and 'pull_request' somewhere in the
        # first 30 lines.
        head = "\n".join(text.splitlines()[:30])
        self.assertIn("push:", head, "must trigger on push")
        self.assertIn("pull_request:", head, "must trigger on pull_request")

    def test_workflow_does_not_silently_bypass_licence(self) -> None:
        """A common failure mode in CI: an action that runs the build
        with the no-licence override and calls the run 'green' even
        when the licence is missing. We assert the action does NOT
        pass the override flag in any `run:` block."""
        import re
        text = WORKFLOW.read_text(encoding="utf-8")
        # Match a `run: ...` block up to the next blank line or
        # another `run:` / `- ` (next step). Comments are stripped.
        for m in re.finditer(
            r"run:\s*\|?\s*\n((?:\s{8,}[^\n]*\n)+)",
            text,
        ):
            block = m.group(1)
            stripped = re.sub(r"#[^\n]*", "", block)
            if "--allow-no-licence" in stripped:
                self.fail(
                    "the action must NOT pass the no-licence override "
                    "in a run block; the absence of a licence is a "
                    "signal that fails the build."
                )

    def test_workflow_uses_checkout_v4(self) -> None:
        """A v3-pinned action is a known supply-chain risk; we use
        v4+. This catches a contributor who copies an old action
        from another project."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@v4", text)
        self.assertNotIn("actions/checkout@v2", text)
        self.assertNotIn("actions/checkout@v3", text)


class TestVerifyReleaseMode(unittest.TestCase):
    """W7.2 contract: `tools/verify.sh --release` produces a
    versioned release handle -- a `sha256=<hex> path=<dir>`
    line on stdout -- for the freshly built artifact.

    The handle is the artifact's tree hash: every file in
    the export is hashed by sorted relative path, then the
    concatenation is hashed again. The handle is what a
    downstream verifier compares byte-for-byte; the W7.2
    contract is "the ledger entry matches the rebuild".

    The test exercises the real script
    (`tools/release_handle.sh` -- the unit the verify
    script delegates to), on a disposable copy of the
    project, and asserts:
      1. The script exits 0 in --release mode.
      2. The output contains a RELEASE_HANDLE line.
      3. The hash is a 64-character hex string.
      4. The path is the export directory the script built.
      5. The hash is **stable** -- a second run on the same
         tree (no changes) produces the same hash. This is
         the contract: the handle does not drift on a
         no-op rebuild.
      6. The hash **changes** if a file in the source tree
         is changed before the build. This catches a hash
         function that ignores content (e.g. one that hashes
         the file list but not the bytes).
    """

    ROOT = Path(__file__).resolve().parents[1]
    HANDLE_SCRIPT = ROOT / "tools" / "release_handle.sh"
    EXPORT_BUILDER = ROOT / "scripts" / "export_bundle.py"
    PY = sys.executable

    def _build_export_in_copy(self, dst: Path) -> None:
        """Run the export gate in a /tmp copy to produce
        the artifact whose handle the test then computes.

        Building the export in a copy (rather than against
        the source tree) is what makes the test honest:
        the handle the test computes is the handle of an
        artifact the script itself produced, not a handle
        of a hand-built dist/ directory.

        The export_bundle.py script computes ROOT at module
        load time as the parent of the script's own path.
        When the test runs the script from a /tmp copy,
        ROOT would be the test's copy (which is what we
        want). But the script ALSO has a module-level SRC
        constant that points at the original ROOT. The
        cleanest way to make the script operate on the
        copy is to pass --src and --out explicitly: the
        --src argument overrides the implicit ROOT, and
        --out makes sure the dist is written inside the
        copy, not somewhere else.
        """
        import subprocess
        result = subprocess.run(
            [self.PY, str(self.EXPORT_BUILDER),
             "--src", str(dst),
             "--out", str(dst / "dist" / "jobsearch-pipeline"),
             "--allow-no-licence"],
            cwd=dst, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            result.returncode, 0,
            f"export gate failed in copy:\n{result.stdout}\n{result.stderr}"
        )
        # The export prints "assembled N files ->" before the
        # leak-scan output. Some warnings (e.g. "no LICENSE")
        # do not fail the run -- the script returns 0 with the
        # bundle still on disk. The next assertion (the
        # existence of dist/jobsearch-pipeline) is the real
        # success check. If this assert passes but the
        # directory is missing, the export script has a bug:
        # a successful return code with no bundle is a lie.

    def _run_handle(self, dst: Path) -> str:
        """Run the release_handle.sh against the export
        that the export gate produced in `dst`, and
        return the stdout."""
        import subprocess
        export_dir = dst / "dist" / "jobsearch-pipeline"
        self.assertTrue(
            export_dir.exists(),
            f"export directory {export_dir} not built; the export gate failed"
        )
        result = subprocess.run(
            ["bash", str(self.HANDLE_SCRIPT), str(export_dir)],
            cwd=dst, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"release_handle.sh failed:\n{result.stdout}\n{result.stderr}"
        )
        return result.stdout

    def _parse_handle(self, stdout: str) -> tuple[str, str]:
        """Find the RELEASE_HANDLE line and return (hash, path)."""
        import re
        m = re.search(
            r"RELEASE_HANDLE:\s*sha256=([0-9a-f]{64})\s+path=(\S+)",
            stdout,
        )
        self.assertIsNotNone(
            m,
            f"the --release output has no RELEASE_HANDLE line:\n{stdout}"
        )
        return m.group(1), m.group(2)

    def _make_copy(self) -> Path:
        """Make a disposable copy of the project, return its
        path. The copy strips __pycache__, .git, var, dist
        so the export can be built cleanly."""
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="release_handle_test_")
        dst = Path(tmp) / "jobsearch"
        shutil.copytree(
            self.ROOT, dst,
            ignore=shutil.ignore_patterns(
                "__pycache__", ".git", "var", "dist", "*.pyc"
            ),
        )
        return dst

    def test_release_handle_is_printed(self) -> None:
        """The handle script prints a RELEASE_HANDLE line
        with a 64-char hex hash and the export path."""
        import shutil
        dst = self._make_copy()
        try:
            self._build_export_in_copy(dst)
            stdout = self._run_handle(dst)
            h, p = self._parse_handle(stdout)
            self.assertEqual(len(h), 64, f"hash is not 64 chars: {h!r}")
            self.assertTrue(
                p.endswith("dist/jobsearch-pipeline"),
                f"path does not end in dist/jobsearch-pipeline: {p}"
            )
        finally:
            shutil.rmtree(dst, ignore_errors=True)

    def test_release_handle_is_stable_on_rebuild(self) -> None:
        """The handle for an unchanged tree is the same on
        two consecutive builds. A handle that drifts on a
        no-op rebuild is not a usable identifier."""
        import shutil
        dst1 = self._make_copy()
        dst2 = self._make_copy()
        try:
            self._build_export_in_copy(dst1)
            self._build_export_in_copy(dst2)
            h1, _ = self._parse_handle(self._run_handle(dst1))
            h2, _ = self._parse_handle(self._run_handle(dst2))
            self.assertEqual(
                h1, h2,
                f"the release handle drifted between two "
                f"consecutive builds: {h1} != {h2}"
            )
        finally:
            shutil.rmtree(dst1, ignore_errors=True)
            shutil.rmtree(dst2, ignore_errors=True)

    def test_release_handle_changes_when_source_changes(self) -> None:
        """If a file in the source tree is changed, the
        handle must change. A handle that ignores content
        (e.g. one that hashes the file list but not the
        bytes) would still match on a no-op rebuild; the
        more important contract is that real changes are
        reflected in the handle."""
        import shutil
        dst = self._make_copy()
        try:
            self._build_export_in_copy(dst)
            h1, _ = self._parse_handle(self._run_handle(dst))
            # Touch a shipped file. We use the corpus because
            # it is small, deterministic, and changing one
            # fixture changes the hash but not the build
            # outcome (the corpus is shipped verbatim).
            corpus = dst / "corpus" / "v1" / "postings.json"
            self.assertTrue(corpus.exists(), "corpus not found in copy")
            original = corpus.read_text(encoding="utf-8")
            # Append a comment to the JSON. Strict JSON
            # parsers would reject this, but the export
            # gate does not re-parse the corpus; it just
            # hashes the bytes. The test only needs a byte
            # change, not a semantically meaningful one.
            corpus.write_text(
                original + "\n// W7.2-test: changed at " + "x" * 64,
                encoding="utf-8",
            )
            # Rebuild the export. The hash script only
            # hashes what the export put on disk, so a
            # change to the source without a rebuild
            # would leave the previous handle on disk --
            # the test would then fail with a "no change"
            # error. The rebuild is the contract.
            self._build_export_in_copy(dst)
            h2, _ = self._parse_handle(self._run_handle(dst))
            self.assertNotEqual(
                h1, h2,
                f"the release handle did not change after a "
                f"byte change to the corpus: still {h1}"
            )
        finally:
            shutil.rmtree(dst, ignore_errors=True)

    def test_release_handle_exits_2_on_missing_export_dir(self) -> None:
        """The release handle script documents exit code 2
        for a missing or empty export directory. This is
        the W7.2 contract: a release that cannot find its
        target cannot print a handle, and the failure must
        be loud (non-zero) so the verify script on a
        future checkout can detect a broken release.

        A future contributor who changed the script to
        exit 0 on a missing dir (treating it as a no-op)
        would silently break the release workflow: a
        release that points at a deleted dist/ would
        appear successful instead of broken. The test
        pins exit 2 and asserts the error names the
        missing directory so the operator can see what
        to fix.
        """
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = Path(tmp) / "does_not_exist"
            self.assertFalse(missing_dir.exists(), "precondition")
            r = subprocess.run(
                ["bash", str(self.HANDLE_SCRIPT), str(missing_dir)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                r.returncode, 2,
                f"missing-export-dir release_handle.sh must "
                f"exit 2; got {r.returncode}. stdout: "
                f"{r.stdout[:200]!r}; stderr: "
                f"{r.stderr[:200]!r}"
            )
            # The error must name the missing directory so
            # the operator can see what to fix.
            combined = r.stdout + r.stderr
            self.assertIn(
                str(missing_dir), combined,
                f"the missing-dir exit must name the missing "
                f"directory; got: {combined[:300]!r}"
            )
            # The error must NOT print a RELEASE_HANDLE line:
            # a missing-dir release has no handle to print.
            self.assertNotIn(
                "RELEASE_HANDLE:", combined,
                f"a missing-dir release must not print a "
                f"RELEASE_HANDLE line; got: {combined[:300]!r}"
            )

    def test_release_handle_hex_flag_prints_just_the_hash(self) -> None:
        """The `--hex` flag in `tools/release_handle.sh`
        (line 47: `if [ "$#" -gt 0 ] && [ "$1" = "--hex" ]`)
        must print the bare 64-char hex hash on stdout,
        with no `RELEASE_HANDLE:` prefix and no path.

        This is the contract that the W7.2 verifier uses
        when comparing two builds: the verifier wants
        just the hash to diff, not the full label line.
        The default mode prints the label so a human
        reading the output knows what the hash refers
        to; the `--hex` mode is for machine consumers.

        A future contributor who changes the script to
        ignore `--hex` (or to print the label anyway)
        would silently break the verifier's hash
        comparison. The test pins the exact stdout:
        one line, exactly 64 hex chars, no
        `RELEASE_HANDLE:` prefix, no path.
        """
        import shutil
        import subprocess
        dst = self._make_copy()
        try:
            self._build_export_in_copy(dst)
            export_dir = dst / "dist" / "jobsearch-pipeline"
            self.assertTrue(export_dir.exists(), "precondition")
            r = subprocess.run(
                ["bash", str(self.HANDLE_SCRIPT),
                 str(export_dir), "--hex"],
                cwd=dst, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                r.returncode, 0,
                f"--hex mode failed:\\n"
                f"stdout: {r.stdout!r}\\nstderr: {r.stderr!r}"
            )
            # The --hex output is a single line.
            lines = r.stdout.strip().splitlines()
            self.assertEqual(
                len(lines), 1,
                f"--hex must print exactly one line; got "
                f"{len(lines)}: {r.stdout!r}"
            )
            # The single line is exactly 64 hex chars.
            hex_hash = lines[0]
            self.assertEqual(
                len(hex_hash), 64,
                f"--hex hash must be 64 chars; got "
                f"{len(hex_hash)}: {hex_hash!r}"
            )
            self.assertTrue(
                all(c in "0123456789abcdef" for c in hex_hash),
                f"--hex hash must be lowercase hex; got: "
                f"{hex_hash!r}"
            )
            # The --hex mode does NOT print the
            # RELEASE_HANDLE label.
            self.assertNotIn(
                "RELEASE_HANDLE:", r.stdout,
                f"--hex mode must not print the label; "
                f"got: {r.stdout!r}"
            )
            # The --hex hash must match the hash
            # from the default mode (same tree, same
            # hash -- only the output format differs).
            r_default = subprocess.run(
                ["bash", str(self.HANDLE_SCRIPT),
                 str(export_dir)],
                cwd=dst, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                r_default.returncode, 0,
                f"default mode failed:\\n{r_default.stdout!r}"
            )
            _, default_path = self._parse_handle(r_default.stdout)
            default_hash = r_default.stdout.split("sha256=")[1].split()[0]
            self.assertEqual(
                hex_hash, default_hash,
                f"--hex hash must match default-mode hash "
                f"for the same tree; got --hex={hex_hash!r} "
                f"vs default={default_hash!r}"
            )
        finally:
            shutil.rmtree(dst, ignore_errors=True)

    def test_release_handle_hex_mode_also_exits_2_on_missing_dir(
        self,
    ) -> None:
        """The `--hex` flag in `tools/release_handle.sh`
        (line 47) must still exit 2 on a missing export
        directory. The default mode is tested by
        `test_release_handle_exits_2_on_missing_export_dir`,
        but a contributor who refactors the `--hex`
        branch to skip the missing-dir check (e.g. by
        moving the `echo "$HASH"` before the
        `[ -d "$EXPORT_DIR" ] || exit 2` guard) would
        silently make the `--hex` mode print an empty
        hash or a stale hash from a previous run
        instead of failing loudly.

        The test pins the specific exit code 2 so
        a contributor who moves the guard fails
        the test with a precise error.
        """
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = Path(tmp) / "does_not_exist_hex"
            self.assertFalse(missing_dir.exists(), "precondition")
            r = subprocess.run(
                ["bash", str(self.HANDLE_SCRIPT),
                 str(missing_dir), "--hex"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                r.returncode, 2,
                f"--hex mode must also exit 2 on a "
                f"missing dir; got {r.returncode}. "
                f"stdout: {r.stdout[:200]!r}; "
                f"stderr: {r.stderr[:200]!r}"
            )
            # The error must name the missing
            # directory so the operator can see
            # what to fix.
            self.assertIn(
                str(missing_dir), r.stdout + r.stderr,
                f"the missing-dir error must name the "
                f"path; got: {(r.stdout + r.stderr)[:300]!r}"
            )
            # The --hex mode must NOT print a
            # bare 64-char hex line (the print
            # would be a stale hash from a
            # previous run, which is exactly the
            # bug we're guarding against).
            combined = r.stdout + r.stderr
            for line in combined.splitlines():
                stripped = line.strip()
                if (len(stripped) == 64 and
                        all(c in "0123456789abcdef"
                            for c in stripped)):
                    self.fail(
                        f"--hex mode printed a bare 64-char "
                        f"hex line on a missing dir; this "
                        f"is a stale hash from a previous "
                        f"run. Guard order is wrong. Got: "
                        f"{stripped!r}"
                    )

    def test_release_handle_exits_2_on_no_arguments(self) -> None:
        """The release handle script's CLI contract
        is: 0=success, 2=caller error (no-args or
        missing dir). Before this test, the
        no-args path was a silent bug -- the
        script printed the usage message to
        stderr but exited 0 (success), so a W7.2
        verifier calling the script with no args
        would get exit 0 and an empty hash, then
        try to verify against an empty hash
        (silently broken). The bug was in
        `tools/release_handle.sh` line 30:
        `exit 0` should have been `exit 2`
        (matching the missing-dir contract).

        The test pins the fixed contract so a
        contributor who "fixes" the no-args path
        back to exit 0 (e.g. by misreading the
        usage message as non-fatal) fails the
        test with a precise error.

        The test also asserts the usage message
        names both expected args
        (`<export-dir>` and `[--hex]`) so a
        contributor who simplifies the usage
        message (e.g. removes the `[--hex]`
        hint) fails the test.
        """
        import subprocess
        r = subprocess.run(
            ["bash", str(self.HANDLE_SCRIPT)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            r.returncode, 2,
            f"release_handle.sh with no args must exit 2 "
            f"(caller error, same as missing-dir); got "
            f"{r.returncode}. A W7.2 verifier calling "
            f"the script with no args would silently "
            f"see exit 0 and an empty hash -- exactly "
            f"the bug this test guards against. "
            f"stdout: {r.stdout[:200]!r}; "
            f"stderr: {r.stderr[:200]!r}"
        )
        # The usage message must name both
        # expected args so a new user (or a
        # CI log scraper) can see the contract
        # without reading the source.
        self.assertIn(
            "<export-dir>", r.stderr,
            f"the no-args usage message must name the "
            f"required arg; got: {r.stderr[:200]!r}"
        )
        self.assertIn(
            "[--hex]", r.stderr,
            f"the no-args usage message must name the "
            f"optional --hex flag (so a user can see "
            f"the machine-readable mode exists); got: "
            f"{r.stderr[:200]!r}"
        )
        # The no-args path must NOT print a
        # 64-char hex line -- a hash on the
        # no-args path would be a real bug
        # (the script has no $HASH to print,
        # but a contributor who refactored
        # the script might emit a stale
        # hash from a previous run).
        for line in (r.stdout + r.stderr).splitlines():
            stripped = line.strip()
            if (len(stripped) == 64 and
                    all(c in "0123456789abcdef"
                        for c in stripped)):
                self.fail(
                    f"release_handle.sh with no args "
                    f"printed a bare 64-char hex line; "
                    f"this is a stale hash. Got: "
                    f"{stripped!r}"
                )


if __name__ == "__main__":
    unittest.main()
