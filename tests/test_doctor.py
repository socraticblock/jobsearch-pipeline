"""W5.2 -- tools/doctor.py test.

The doctor is a one-command health check for a fresh checkout.
The test asserts:

  1. The doctor exists and runs.
  2. On a clean checkout, every check passes and exit is 0.
  3. On a checkout with a missing required file, the doctor
     reports the failure with a one-line fix and exits 1.
  4. On a checkout with a non-executable verify.sh, the doctor
     reports the chmod fix and exits 1.
  5. The --json output is well-formed and reports pass/fail
     counts.
  6. The --quiet mode suppresses PASS lines.
  7. The doctor does not perform any network I/O (it only
     inspects the local checkout).

The test does not modify the source tree; it works on
disposable copies in /tmp.

Run:  python3 -m unittest tests.test_doctor -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "tools" / "doctor.py"
PY = sys.executable


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy a directory tree, skipping __pycache__ and .git."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns("__pycache__", ".git", "var",
                                       "dist", "*.pyc"),
    )


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run the doctor from the COPY at cwd, not the source.

    A fresh checkout test must exercise the copy's doctor.py,
    not the original.  Otherwise the test always sees a clean
    checkout regardless of what is in the copy.
    """
    doctor_in_copy = cwd / "tools" / "doctor.py"
    return subprocess.run(
        [PY, str(doctor_in_copy), *args],
        cwd=cwd, capture_output=True, text=True, timeout=30,
    )


class TestDoctor(unittest.TestCase):

    def test_doctor_file_exists(self) -> None:
        self.assertTrue(
            DOCTOR.exists(),
            f"doctor.py missing at {DOCTOR.relative_to(ROOT)}. "
            f"It is the W5.2 deliverable."
        )

    def test_clean_checkout_passes(self) -> None:
        result = _run([], ROOT)
        self.assertEqual(
            result.returncode, 0,
            f"doctor failed on a clean checkout:\n{result.stdout}\n"
            f"{result.stderr}"
        )
        self.assertIn("0 fail", result.stdout)
        self.assertIn("All preconditions met", result.stdout)

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "jobsearch"
            _copy_tree(ROOT, dst)
            (dst / "corpus" / "v1" / "postings.json").unlink()
            result = _run(["--quiet"], dst)
            self.assertEqual(
                result.returncode, 1,
                "doctor should exit 1 on a missing required file"
            )
            self.assertIn("corpus-v1", result.stdout)
            self.assertIn("not found", result.stdout)
            self.assertIn("fix:", result.stdout)

    def test_non_executable_verify_sh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "jobsearch"
            _copy_tree(ROOT, dst)
            os.chmod(dst / "tools" / "verify.sh", 0o644)
            result = _run(["--quiet"], dst)
            self.assertEqual(
                result.returncode, 1,
                "doctor should exit 1 when verify.sh is not executable"
            )
            self.assertIn("executable-verify.sh", result.stdout)
            self.assertIn("chmod +x", result.stdout)

    def test_json_output_is_well_formed(self) -> None:
        result = _run(["--json"], ROOT)
        self.assertEqual(result.returncode, 0)
        # The JSON output goes to stdout.
        data = json.loads(result.stdout)
        self.assertIn("pass", data)
        self.assertIn("fail", data)
        self.assertIsInstance(data["pass"], int)
        self.assertIsInstance(data["fail"], int)
        self.assertEqual(data["fail"], 0)
        self.assertIsInstance(data["checks"], list)
        self.assertGreater(len(data["checks"]), 0)
        # Each check has the four required fields.
        for c in data["checks"]:
            self.assertIn("name", c)
            self.assertIn("passed", c)
            self.assertIn("detail", c)
            self.assertIn("fix", c)

    def test_json_output_exits_1_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "jobsearch"
            _copy_tree(ROOT, dst)
            (dst / "scripts" / "export_bundle.py").unlink()
            result = _run(["--json"], dst)
            self.assertEqual(result.returncode, 1)
            data = json.loads(result.stdout)
            self.assertGreater(data["fail"], 0)

    def test_quiet_mode_suppresses_pass_lines(self) -> None:
        result = _run(["--quiet"], ROOT)
        self.assertEqual(result.returncode, 0)
        # PASS marker should NOT appear in quiet output (only
        # FAIL lines and the summary).
        for line in result.stdout.splitlines():
            self.assertNotIn(
                "[PASS]", line,
                f"quiet mode should suppress PASS lines; got: {line!r}"
            )

    def test_each_check_has_a_fix_line_when_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "jobsearch"
            _copy_tree(ROOT, dst)
            (dst / "tools" / "verify.sh").unlink()
            result = _run(["--quiet"], dst)
            self.assertEqual(result.returncode, 1)
            # Every FAIL line must have a fix: line after it.
            fail_count = sum(1 for l in result.stdout.splitlines()
                             if "[FAIL]" in l)
            fix_count = sum(1 for l in result.stdout.splitlines()
                            if "fix:" in l)
            self.assertGreaterEqual(
                fix_count, fail_count,
                f"every FAIL should have a fix line: "
                f"{fail_count} FAILs, {fix_count} fixes"
            )

    def test_no_network_io(self) -> None:
        """The doctor must not make outbound network calls. We
        check by ensuring the source contains no `urllib`,
        `requests`, `httpx`, or `socket` imports."""
        text = DOCTOR.read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import requests",
                          "import httpx", "import socket",
                          "from urllib", "from requests",
                          "from httpx", "from socket"):
            self.assertNotIn(
                forbidden, text,
                f"doctor.py imports {forbidden!r}; the doctor "
                f"must not perform any network I/O."
            )

    def test_doctor_runs_a_documented_number_of_checks(self) -> None:
        """The doctor must run a specific number of checks;
        CL-018 names that number. A future contributor
        who adds a check without updating CL-018 would
        silently drift the claim; a future contributor
        who removes a check without updating CL-018 would
        silently weaken the fresh-clone tripwire. The
        JSON output is the source of truth (it lists every
        check by name with its pass/fail status), so the
        test reads it directly rather than parsing the
        human-readable output.

        The test asserts the count is at least 22 (the
        number documented in CL-018) AND that the count
        is at most 30 (an upper bound that catches a
        contributor who adds 20 checks without thinking).
        A precise lower bound is the right shape: a
        contributor who adds one new check gets a clean
        test after they update CL-018; a contributor who
        removes a check fails the test immediately.
        """
        result = _run(["--json"], ROOT)
        self.assertEqual(
            result.returncode, 0,
            f"doctor --json failed on a clean checkout: "
            f"stdout: {result.stdout[:200]!r}; "
            f"stderr: {result.stderr[:200]!r}"
        )
        import json
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(
                f"doctor --json output is not valid JSON: "
                f"{e}; stdout: {result.stdout[:300]!r}"
            )
        checks = data.get("checks", [])
        self.assertIsInstance(
            checks, list,
            f"doctor JSON output must have a 'checks' list; "
            f"got: {type(checks).__name__}"
        )
        # CL-018 says 22 preconditions. A future
        # contributor who adds a check must update CL-018
        # and this test; the cleanest is to bump the
        # lower bound to match.
        self.assertGreaterEqual(
            len(checks), 22,
            f"CL-018 documents 22 preconditions but the "
            f"doctor only runs {len(checks)}: {[c.get('name') for c in checks]}. "
            f"Either CL-018 is stale, or a check was "
            f"silently removed."
        )
        # An upper bound catches a contributor who adds
        # 20 checks without thinking. 30 is generous --
        # the doctor is a quick precondition check, not
        # a comprehensive audit.
        self.assertLessEqual(
            len(checks), 30,
            f"the doctor runs {len(checks)} checks, which "
            f"is more than the 30-check upper bound. If "
            f"this is intentional, update this test; if "
            f"not, the doctor is doing more work than its "
            f"design intent supports."
        )

    def test_doctor_runs_a_documented_set_of_check_names(self) -> None:
        """The doctor must run a specific set of checks;
        CL-018 names the count (22) but not the
        individual checks. A future contributor
        who "simplifies" the doctor by removing
        one check (e.g. `_check_release_workflow`,
        thinking "release-privacy.yml is already
        covered by the audit script") would
        silently widen the fresh-clone tripwire:
        a clone missing the workflow file would
        no longer be caught.

        The count-only test (above) does NOT
        catch this -- the count would stay at
        22 if the contributor also added a
        different check. This test pins the
        specific set of check names, parallel
        to the doctor's `_all_checks()` list,
        so adding or removing a name requires
        updating both in the same commit.

        The test list mirrors the doctor's
        `_all_checks()` list (line 250 of
        `tools/doctor.py`). The doctor is
        the source of truth -- this test
        is the contract pin. If the test
        list and the doctor list diverge,
        the test fails with the specific
        missing or extra name in the
        error message.
        """
        result = _run(["--json"], ROOT)
        self.assertEqual(
            result.returncode, 0,
            f"doctor --json failed on a clean checkout: "
            f"stdout: {result.stdout[:200]!r}; "
            f"stderr: {result.stderr[:200]!r}"
        )
        import json
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(
                f"doctor --json output is not valid JSON: "
                f"{e}; stdout: {result.stdout[:300]!r}"
            )
        actual_names = [c["name"] for c in data["checks"]]
        actual_set = set(actual_names)
        # The 22 checks the doctor must run.
        # This list must stay parallel to
        # `_all_checks()` in tools/doctor.py.
        # If you add a check to the doctor,
        # add it here too -- the test will
        # then assert the new check is in
        # the output. If you remove a check
        # from the doctor, remove it here
        # too -- the test will then assert
        # it's gone.
        expected_names = [
            "python-version",
            "module-yaml",
            "module-reportlab",
            "corpus-v1",
            "profile-yaml",
            "verify-sh",
            "demo-sieve",
            "export-bundle",
            "morning-prepare",
            "next-fire",
            "build-dataflow-map",
            "audit-history",
            "render-pdf",
            "release-handle",
            "release-workflow",
            "executable-verify.sh",
            "executable-release_handle.sh",
            "var-writable",
            "digests-writable",
            "jobsearch-imports",
            "rule-why-consistent",
            "tools-importable",
        ]
        expected_set = set(expected_names)
        # Check for missing names (in expected
        # but not in actual). This catches a
        # contributor who removed a check
        # from the doctor.
        missing = expected_set - actual_set
        self.assertEqual(
            missing, set(),
            f"the doctor is missing {len(missing)} "
            f"expected check(s): {sorted(missing)}. "
            f"Each name in this list must be in "
            f"the doctor's output -- if a check "
            f"was intentionally removed, update "
            f"this test and CL-018 in the same "
            f"commit. Actual names: {sorted(actual_set)}"
        )
        # Check for extra names (in actual
        # but not in expected). This catches
        # a contributor who added a check
        # without updating this test (and
        # thus without documenting it in
        # CL-018).
        extra = actual_set - expected_set
        self.assertEqual(
            extra, set(),
            f"the doctor runs {len(extra)} check(s) "
            f"not in the documented set: "
            f"{sorted(extra)}. If a check was "
            f"intentionally added, update this "
            f"test and CL-018 in the same "
            f"commit. Actual names: "
            f"{sorted(actual_set)}"
        )


    def test_stripped_environment_names_missing_modules_with_a_real_fix(self) -> None:
        """W5.2's own contract: run in a stripped environment and assert every
        failing check is named with a fix.

        The doctor is the first command a fresh reader runs, so the stripped
        environment IS its subject matter. Two ways this contract has been
        broken here, and this test is what pins both:

          * `importlib.util` was used in `_check_tools_in_path` but never
            imported. With PyYAML and reportlab both absent -- exactly the
            fresh-machine case -- the AttributeError was swallowed by that
            check's `except Exception` and reported as a false failure
            blaming the repo: "tools/demo_sieve.py failed to load: module
            'importlib' has no attribute 'util'", fix "the failure is a bug".
            The reader was told the wrong thing about the wrong file.
          * the missing-module fix line said `pip install yaml`, a package
            that does not provide the `yaml` module, so following it left the
            reader as broken as before.

        The stripped environment is built with a `sitecustomize.py` on
        PYTHONPATH that refuses to resolve those two distributions.
        """
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "blocker"
            blocker.mkdir()
            (blocker / "sitecustomize.py").write_text(
                "import sys\n"
                "class _Block:\n"
                "    def find_spec(self, name, path=None, target=None):\n"
                "        if name.split('.')[0] in ('yaml', 'reportlab'):\n"
                "            raise ImportError('blocked by the test: ' + name)\n"
                "        return None\n"
                "sys.meta_path.insert(0, _Block())\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(blocker)
            result = subprocess.run(
                [PY, str(ROOT / "tools" / "doctor.py")],
                cwd=ROOT, capture_output=True, text=True, timeout=60, env=env,
            )
        self.assertEqual(
            result.returncode, 1,
            f"the doctor must exit non-zero when a required module is "
            f"missing:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("module-yaml", result.stdout)
        self.assertIn("fix:", result.stdout)
        self.assertTrue(
            "pip install -r requirements.txt" in result.stdout
            or "pip install PyYAML" in result.stdout,
            f"the fix for a missing `yaml` module must name a distribution "
            f"that provides it (requirements.txt or PyYAML), not "
            f"`pip install yaml`:\n{result.stdout}",
        )
        self.assertNotIn(
            "[FAIL] tools-importable", result.stdout,
            f"a missing dependency must not be reported as a failure of the "
            f"repo's own tool:\n{result.stdout}",
        )
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
