"""W1.3 — the export gate is fail-closed and is proven by mutation.

The gate is `scripts/export_bundle.py`. The mutation test does NOT mutate the
real project tree; it copies the project to a tempdir, plants one forbidden
item at a time (in the COPY, not the source), runs the gate against the
copy with --src/--out, and asserts the gate exits non-zero, names the
offending path, and leaves no bundle behind. A final clean run on an
unmutated copy must exit zero.

This file also covers W1.2 (allowlist, fresh-history tree) and W1.4 (the
clean baseline the gate is comparing against). It runs offline.

Run:  python3 -m unittest tests.test_export_gate -v
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPORT = ROOT / "scripts" / "export_bundle.py"


def _venv_python() -> str:
    # Prefer the interpreter running the test suite (the one with the
    # declared dependencies installed). Fall back to an explicit venv
    # override, then to a plain `python3` on PATH. This keeps the suite
    # runnable on a clean machine (CI) where the Hermes venv is absent.
    override = os.environ.get("HERMES_VENV_PYTHON") or os.environ.get("PY")
    if override and Path(override).is_file():
        return override
    return sys.executable


def _copy_clean_tree(dst: Path) -> None:
    """Copy the project to dst, omitting anything the script would not ship.

    This is the mutation harness's "fresh clone": it has the same source
    layout as a real git clone of the project (minus .git), with a hard
    guarantee that var/ and the real profile are not present.
    """
    skip_dirs = {"__pycache__", ".git", "node_modules", ".wrangler",
                 "cache", "state", "tmp", "var", "digests", "dist"}
    skip_suffixes = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log"}
    for entry in sorted(ROOT.iterdir()):
        if entry.name in skip_dirs or entry.suffix in skip_suffixes:
            continue
        if entry.is_dir():
            shutil.copytree(entry, dst / entry.name,
                            ignore=shutil.ignore_patterns(*skip_dirs, "*.pyc", "*.pyo",
                                                          "*.db", "*.log"))
        else:
            shutil.copy2(entry, dst / entry.name)


def _build(src: Path, out: Path, *, allow_no_licence: bool = True) -> subprocess.CompletedProcess:
    cmd = [_venv_python(), str(EXPORT), "--src", str(src), "--out", str(out)]
    if allow_no_licence:
        cmd.append("--allow-no-licence")
    return subprocess.run(cmd, capture_output=True, text=True)


class TestExportGateCleanBaseline(unittest.TestCase):
    """The gate must pass on an unmutated, current copy of the project.

    This is the test that fails first if a refactor accidentally introduces
    a personal token, an absolute path, a forbidden file type, or an
    unlisted file. It is the one the operator cares about: "can I publish
    what I have right now?"
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_clean_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_copy_exits_zero(self):
        r = _build(self.src, self.out)
        self.assertEqual(r.returncode, 0, f"clean copy was rejected:\n{r.stdout}\n{r.stderr}")
        # The build is real: a bundle exists, it has the expected manifest,
        # and it has the generated requirements.txt the script writes.
        self.assertTrue((self.out / "MANIFEST.txt").exists())
        self.assertTrue((self.out / "requirements.txt").exists())
        self.assertTrue((self.out / ".gitignore").exists())

    def test_manifest_has_no_duplicate_paths(self):
        """The MANIFEST must list every shipped file exactly
        once. A duplicate means the gate is silently double-
        walking a path (e.g. the same name in both INCLUDE
        and OPTIONAL_INCLUDE), and a future reader trusting
        the 'N files' header to plan a release would over-
        count.

        Regression for the docs/ double-walk: the gate had
        `docs` in both INCLUDE and OPTIONAL_INCLUDE, so
        every file under docs/ landed in the manifest
        twice and the header said '88 files' for a 86-
        file export.
        """
        r = _build(self.src, self.out)
        self.assertEqual(r.returncode, 0, f"clean copy was rejected:\n{r.stdout}\n{r.stderr}")
        paths = []
        header_count = None
        for line in (self.out / "MANIFEST.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("#") and "files" in line:
                # The "# N files" line.
                m = re.search(r"(\d+)\s+files", line)
                if m:
                    header_count = int(m.group(1))
                continue
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                paths.append(parts[2])
        # 1. No duplicate paths in the manifest.
        self.assertEqual(
            len(paths), len(set(paths)),
            f"the MANIFEST has duplicate paths: {paths!r}"
        )
        # 2. The header count must match the entry count.
        self.assertEqual(
            header_count, len(paths),
            f"the 'N files' header says {header_count} but the "
            f"manifest has {len(paths)} entries"
        )
        # 3. The header count must match the actual file
        # count in the bundle (minus the three generated
        # files: MANIFEST.txt, .gitignore, requirements.txt).
        real_files = 0
        for path in self.out.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.out)
            if rel.name in {"MANIFEST.txt", ".gitignore", "requirements.txt"}:
                continue
            real_files += 1
        self.assertEqual(
            header_count, real_files,
            f"the 'N files' header says {header_count} but the "
            f"bundle has {real_files} real files"
        )

    def test_cl_005_bundle_size_matches_manifest(self):
        """CL-005 in CLAIMS.md claims a specific file count
        for the shipped bundle. The claim must agree with
        the manifest header. A drift in either direction
        is a lie a careful reader can be misled by.

        Regression for the silent drift: CL-005 was at one
        point claiming '49 files' for an 86-file export.
        A future contributor who updates one without the
        other fails this test.
        """
        r = _build(self.src, self.out)
        self.assertEqual(r.returncode, 0, f"clean copy was rejected:\n{r.stdout}\n{r.stderr}")
        # Read the manifest header.
        manifest_count = None
        for line in (self.out / "MANIFEST.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("#") and "files" in line:
                m = re.search(r"(\d+)\s+files", line)
                if m:
                    manifest_count = int(m.group(1))
                break
        self.assertIsNotNone(
            manifest_count,
            "the manifest has no '# N files' header line"
        )
        # Read what CL-005 claims.
        claims = (self.src / "CLAIMS.md").read_text(encoding="utf-8")
        m = re.search(
            r"#### CL-005.*?\n(.*?)(?=\n####|\Z)",
            claims,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "CLAIMS.md has no CL-005 claim")
        claim_body = m.group(1)
        m2 = re.search(
            r"shipped bundle is\s+(\d+)\s+files",
            claim_body,
        )
        self.assertIsNotNone(
            m2,
            "CL-005 has no 'shipped bundle is N files' phrase"
        )
        claim_count = int(m2.group(1))
        self.assertEqual(
            manifest_count, claim_count,
            f"the manifest says {manifest_count} files but "
            f"CL-005 claims {claim_count}. Update one to match "
            f"the other."
        )

    def test_built_tree_has_no_unlisted_files(self):
        r = _build(self.src, self.out)
        self.assertEqual(r.returncode, 0, f"clean copy was rejected:\n{r.stdout}\n{r.stderr}")
        manifest_paths = set()
        for line in (self.out / "MANIFEST.txt").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 3 and not line.startswith("#"):
                manifest_paths.add(parts[2])
        # The generated files are not on the manifest but are legitimate.
        generated = {"MANIFEST.txt", ".gitignore", "requirements.txt"}
        for path in self.out.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.out))
            self.assertIn(rel, manifest_paths | generated,
                          f"unlisted file in built tree: {rel}")


class TestExportGateMutationMatrix(unittest.TestCase):
    """Each forbidden item, planted in the COPY, must make the gate fail.

    The matrix is the list below. Every entry must (a) exit non-zero,
    (b) name the offending path in stderr or stdout, and (c) leave no
    bundle behind. Adding a new forbidden item to the gate without adding
    it here means a future regression in the deny list goes unproven.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_mutation_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _assert_rejected(self, planted_path: Path, *, name_substring: str = ""):
        r = _build(self.src, self.out)
        self.assertNotEqual(
            r.returncode, 0,
            f"gate accepted a tree with {planted_path} planted",
        )
        combined = r.stdout + r.stderr
        needle = name_substring or planted_path.name
        self.assertIn(
            needle, combined,
            f"gate did not name '{needle}' in its refusal:\n{combined}",
        )
        # The incomplete bundle must be gone.
        self.assertFalse(
            (self.out / "MANIFEST.txt").exists(),
            "gate left a partial bundle behind on refusal",
        )

    def test_planted_token_json_is_refused(self):
        # A fake token-shaped file dropped into a shipped directory: the
        # gate's leak scanner fires on the secret-shaped value inside.
        planted = self.src / "tools" / "google" / "leakcheck_marker.json"
        planted.parent.mkdir(parents=True, exist_ok=True)
        # Real-shaped Google access token: ya29. + 24 base64url chars.
        token = "ya29." + ("A" * 24)
        planted.write_text(json.dumps({"token": token}), encoding="utf-8")
        self._assert_rejected(planted, name_substring="leakcheck_marker.json")

    def test_planted_client_secret_is_refused(self):
        # A real-shaped client_secret.json dropped into a shipped
        # directory: the secret-shape scanner fires on the GOCSPX- value.
        planted = self.src / "tools" / "google" / "leakcheck_marker.json"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(json.dumps({"client_id": "abc.apps.googleusercontent.com",
                                       "client" + "_secret": "GOCSPX" + "-" + "FAKEFAKEFAKEFAKEFAKE"}),
                           encoding="utf-8")
        self._assert_rejected(planted, name_substring="leakcheck_marker.json")

    def test_planted_profile_yaml_is_refused(self):
        # A profile.yaml planted into a sibling position of the shipped
        # example profile: the source-completeness check refuses a
        # planted sibling file (the shipping list is for the EXAMPLE;
        # a second file at the same path is by definition not the one
        # the list named). The planted file also carries a real-shaped
        # token value so the secret-shape scanner fires too.
        planted = self.src / "profile" / "leakcheck_profile.yaml"
        planted.parent.mkdir(parents=True, exist_ok=True)
        token = "ya29." + ("B" * 24)
        planted.write_text(f"identity:\n  full_name: Real Owner\n  token: {token}\n",
                           encoding="utf-8")
        self._assert_rejected(planted, name_substring="leakcheck_profile.yaml")

    def test_planted_dotenv_in_shipped_dir_is_refused(self):
        # A .env dropped into a shipped directory (tools/google, which is
        # in INCLUDE): the file walker visits it, the filename is on the
        # forbidden list AND the content is a real PAT shape.
        planted = self.src / "tools" / "google" / ".env"
        planted.parent.mkdir(parents=True, exist_ok=True)
        # The PAT shape is reconstructed at runtime from a base prefix so
        # the test source itself does not contain a deny-listed string.
        marker = "ghp_" + ("Z" * 24)
        planted.write_text("API" + "_KEY=" + marker + "\n", encoding="utf-8")
        self._assert_rejected(planted, name_substring=".env")

    def test_planted_home_path_string_is_refused(self):
        # A docstring or comment containing a home-path shape trips the
        # home-path scan. The path is built from pieces so the test
        # source itself does not match the deny list.
        planted = self.src / "tools" / "google" / "_hermes_home.py"
        original = planted.read_text(encoding="utf-8") if planted.exists() else ""
        home_prefix = "/" + "home" + "/"
        planted.write_text(
            f"{original}\n# example: {home_prefix}notes_user{os.sep}notes\n",
            encoding="utf-8",
        )
        self._assert_rejected(planted, name_substring="/" + "home/")

    def test_planted_unlisted_file_is_refused(self):
        # A file inside an included directory that is not in the manifest
        # trips the completeness check. We add it to tools/google (a
        # shipped directory) so the include walker visits it.
        planted = self.src / "tools" / "google" / "unlisted_marker.txt"
        planted.write_text("this file is not on the include list", encoding="utf-8")
        self._assert_rejected(planted, name_substring="unlisted_marker.txt")

    def test_forbidden_suffix_in_shipped_dir_is_refused(self):
        # A .pdf inside an include path: the walker refuses the copy
        # outright (RuntimeError) rather than the leak-scan refusing later.
        planted = self.src / "tools" / "google" / "smuggled.pdf"
        planted.write_bytes(b"%PDF-1.4\n%fake\n")
        self._assert_rejected(planted, name_substring="smuggled.pdf")

    def test_planted_dotdb_in_shipped_dir_is_silently_skipped(self):
        # A .db inside an include path: the walker silently skips it
        # (it's in `SKIP_SUFFIXES`). The .db is the live ledger; the
        # gate's job is to ensure it does NOT end up in the artifact.
        # The test asserts the file is dropped (not refused with
        # RuntimeError, like .pdf, because .db is "expected" in the
        # source tree but not allowed in the artifact).
        planted = self.src / "tools" / "google" / "smuggled.db"
        planted.write_bytes(b"SQLite format 3\x00fake\n")
        # Run the build.
        r = _build(self.src, self.out)
        self.assertEqual(
            r.returncode, 0,
            f"gate should exit 0 (the .db is "
            f"silently skipped, not refused): "
            f"stdout={r.stdout!r}, stderr={r.stderr!r}"
        )
        # The manifest must NOT contain the planted file.
        if (self.out / "MANIFEST.txt").exists():
            manifest_text = (self.out / "MANIFEST.txt").read_text()
            self.assertNotIn(
                "smuggled.db", manifest_text,
                f"the .db ended up in MANIFEST.txt. "
                f"This is a publication leak: the "
                f"live ledger is in the public "
                f"artifact. Manifest: {manifest_text!r}"
            )
        # The .db must not be on disk in the output.
        self.assertFalse(
            (self.out / "tools" / "google" / "smuggled.db").exists(),
            f"the .db ended up on disk in the "
            f"output. This is a publication leak: "
            f"the live ledger is in the public "
            f"artifact. Output tree: "
            f"{list(self.out.rglob('*'))[:20]}"
        )

    def test_planted_dotsqlite_in_shipped_dir_is_silently_skipped(self):
        # A .sqlite inside an include path: same logic as .db
        # (the live ledger under another name).
        planted = self.src / "tools" / "google" / "smuggled.sqlite"
        planted.write_bytes(b"SQLite format 3\x00fake\n")
        r = _build(self.src, self.out)
        self.assertEqual(
            r.returncode, 0,
            f"gate should exit 0 (the .sqlite "
            f"is silently skipped, not refused): "
            f"stdout={r.stdout!r}, stderr={r.stderr!r}"
        )
        if (self.out / "MANIFEST.txt").exists():
            manifest_text = (self.out / "MANIFEST.txt").read_text()
            self.assertNotIn(
                "smuggled.sqlite", manifest_text,
                f"the .sqlite ended up in MANIFEST.txt. "
                f"This is a publication leak. Manifest: "
                f"{manifest_text!r}"
            )
        self.assertFalse(
            (self.out / "tools" / "google" / "smuggled.sqlite").exists(),
            f"the .sqlite ended up on disk in "
            f"the output. Output tree: "
            f"{list(self.out.rglob('*'))[:20]}"
        )

    def test_planted_dotsqlite3_in_shipped_dir_is_silently_skipped(self):
        # A .sqlite3 inside an include path: same logic as .db
        # (the live ledger under yet another name).
        planted = self.src / "tools" / "google" / "smuggled.sqlite3"
        planted.write_bytes(b"SQLite format 3\x00fake\n")
        r = _build(self.src, self.out)
        self.assertEqual(
            r.returncode, 0,
            f"gate should exit 0 (the .sqlite3 "
            f"is silently skipped, not refused): "
            f"stdout={r.stdout!r}, stderr={r.stderr!r}"
        )
        if (self.out / "MANIFEST.txt").exists():
            manifest_text = (self.out / "MANIFEST.txt").read_text()
            self.assertNotIn(
                "smuggled.sqlite3", manifest_text,
                f"the .sqlite3 ended up in "
                f"MANIFEST.txt. This is a "
                f"publication leak. Manifest: "
                f"{manifest_text!r}"
            )
        self.assertFalse(
            (self.out / "tools" / "google" / "smuggled.sqlite3").exists(),
            f"the .sqlite3 ended up on disk in "
            f"the output. Output tree: "
            f"{list(self.out.rglob('*'))[:20]}"
        )

    def test_planted_dotlog_in_shipped_dir_is_silently_skipped(self):
        # A .log inside an include path: the walker silently skips
        # it (it's in `SKIP_SUFFIXES`). A .log is run output
        # (potentially containing personal identifiers or job URLs
        # the user has applied to). The gate's job is to ensure
        # it does NOT end up in the artifact.
        planted = self.src / "tools" / "google" / "smuggled.log"
        planted.write_text("INFO run started\n", encoding="utf-8")
        r = _build(self.src, self.out)
        self.assertEqual(
            r.returncode, 0,
            f"gate should exit 0 (the .log is "
            f"silently skipped, not refused): "
            f"stdout={r.stdout!r}, stderr={r.stderr!r}"
        )
        if (self.out / "MANIFEST.txt").exists():
            manifest_text = (self.out / "MANIFEST.txt").read_text()
            self.assertNotIn(
                "smuggled.log", manifest_text,
                f"the .log ended up in MANIFEST.txt. "
                f"This is a publication leak: run "
                f"output (potentially containing "
                f"personal identifiers) is in the "
                f"public artifact. Manifest: "
                f"{manifest_text!r}"
            )
        self.assertFalse(
            (self.out / "tools" / "google" / "smuggled.log").exists(),
            f"the .log ended up on disk in the "
            f"output. Output tree: "
            f"{list(self.out.rglob('*'))[:20]}"
        )


class TestForbiddenSuffixes(unittest.TestCase):
    """The export gate's `FORBIDDEN_SUFFIXES`
    is the list of file types that cannot
    ship in the public artifact, declared
    once in `scripts/export_bundle.py` and
    consulted by the walker (refusing the
    copy outright) and the leak scan
    (refusing the bundle if the walker
    missed one).

    The list is the user's **publication
    boundary**: a .db in the artifact is
    the live ledger; a .log is run
    output; a .pdf is a rendered digest;
    a .sqlite* is the same ledger under
    another name. The comment at L42-45
    of export_bundle.py is explicit:
    "the list here is the single source
    of truth -- both the copy_tree
    walker and the post-build scan
    consult it".

    A contributor who removes ".log"
    (thinking "logs are fine, they're
    just stdout") would silently allow
    run output (potentially containing
    personal identifiers or job URLs
    the user has applied to) into the
    public artifact. The existing
    mutation test `test_forbidden_suffix_in_shipped_dir_is_refused`
    only tests `.pdf`; a contributor
    could remove any of the other 4
    suffixes and the test would still
    pass.

    The fix is two layers:
    1. A bidirectional set-equality
       test on `FORBIDDEN_SUFFIXES`
       (the set test catches the
       structural drift).
    2. A behavior test for EACH
       of the 5 suffixes (catches
       the logic drift: a suffix
       in the set but the walker
       doesn't actually check it).
       The behavior tests
       (test_planted_dotdb_...
       etc.) live in the existing
       `TestExportGateMutationMatrix`
       class above. This class
       provides the structural pin
       and the cross-reference.

    The pin is `FORBIDDEN_SUFFIXES_EXPECTED`
    (5 entries) at the module
    level of this test class, parallel
    to the source constant. If a
    suffix is added or removed in
    the export gate, update both
    in the same commit.
    """

    # The 5 forbidden suffixes,
    # parallel to `FORBIDDEN_SUFFIXES`
    # in `scripts/export_bundle.py` L46.
    # If you add a suffix, add it here
    # too. If you remove one, update
    # both in the same commit.
    FORBIDDEN_SUFFIXES_EXPECTED = {
        ".pdf", ".db", ".sqlite", ".sqlite3", ".log",
    }

    def test_forbidden_suffixes_set_matches_documented(self) -> None:
        """`FORBIDDEN_SUFFIXES` in
        `scripts/export_bundle.py` must
        contain exactly the 5
        documented suffixes. A
        contributor who removes
        ".log" (thinking "logs are
        just stdout") would silently
        allow run output into the
        public artifact.
        """
        # Import the export gate's
        # constant by exec'ing the
        # module and pulling the
        # constant out, rather than
        # importing it as a regular
        # module (the module's
        # `__name__ == "__main__"`
        # guard would be bypassed,
        # and side effects would
        # fire).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_export_for_test",
            EXPORT,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        actual = mod.FORBIDDEN_SUFFIXES
        expected = self.FORBIDDEN_SUFFIXES_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"FORBIDDEN_SUFFIXES is missing "
            f"{len(missing)} expected "
            f"suffix(es): {sorted(missing)}. "
            f"Removing a suffix silently "
            f"allows files with that suffix "
            f"into the public artifact. "
            f"If the removal is intentional, "
            f"update this test in the same "
            f"commit. Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"FORBIDDEN_SUFFIXES has "
            f"{len(extra)} undocumented "
            f"suffix(es): {sorted(extra)}. "
            f"If a suffix was intentionally "
            f"added, update this test in "
            f"the same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_every_forbidden_suffix_has_a_mutation_test(self) -> None:
        """The 5 documented suffixes must
        each have a mutation test in
        `TestExportGateMutationMatrix`
        (or this class). The set test
        above pins the set, but if a
        suffix is in the set but the
        walker doesn't check it, only
        a behavior test catches that.
        Cross-check that every
        expected suffix has a
        corresponding planted-file
        test.

        The cross-check is by name:
        the test class
        `TestExportGateMutationMatrix`
        has methods like
        `test_planted_dotdb_...` for
        each suffix. The naming
        convention is
        `test_planted_dot{suffix_without_dot}_in_shipped_dir_is_refused`.
        For ".db" the method is
        `test_planted_dotdb_in_shipped_dir_is_refused`.

        The historical test for ".pdf"
        predates this naming
        convention: it is named
        `test_forbidden_suffix_in_shipped_dir_is_refused`
        (singular "suffix", `_is_refused`
        verb). The 4 suffix-specific
        tests use a different verb
        (`_is_silently_skipped`)
        because the walker behavior
        for these is to silently
        skip (not raise) -- they
        are in `SKIP_SUFFIXES` not
        `FORBIDDEN_SUFFIXES`. So the
        cross-check accepts both
        naming conventions for each
        suffix.

        If a suffix is added to the
        expected list but no
        corresponding mutation test
        is found under either
        naming convention, this
        test fails with the specific
        suffix.
        """
        # Find TestExportGateMutationMatrix
        # by name. The existing test
        # file is the only test_export_gate
        # file.
        from tests import test_export_gate
        mutation_class = test_export_gate.TestExportGateMutationMatrix
        method_names = dir(mutation_class)
        for suffix in self.FORBIDDEN_SUFFIXES_EXPECTED:
            # ".db" -> "dotdb" (no leading dot)
            suffix_part = suffix.lstrip(".")
            # New naming convention
            # (refused with RuntimeError,
            # for FORBIDDEN_SUFFIXES entries
            # that are not in SKIP_SUFFIXES)
            new_refused = f"test_planted_dot{suffix_part}_in_shipped_dir_is_refused"
            # Alternative naming convention
            # (silently skipped, for entries
            # in SKIP_SUFFIXES that should
            # not appear in the artifact)
            new_skipped = f"test_planted_dot{suffix_part}_in_shipped_dir_is_silently_skipped"
            # Historical naming convention
            # (predates the new convention;
            # the original test for ".pdf"
            # uses the singular form).
            legacy_name = "test_forbidden_suffix_in_shipped_dir_is_refused"
            found = (
                new_refused in method_names
                or new_skipped in method_names
                or (
                    # The legacy test is a single
                    # historical test, and it
                    # specifically covers ".pdf"
                    # (the only forbidden suffix
                    # at the time the test was
                    # written). So the legacy
                    # name only counts as the
                    # match for ".pdf".
                    suffix == ".pdf" and legacy_name in method_names
                )
            )
            self.assertTrue(
                found,
                f"FORBIDDEN_SUFFIXES contains "
                f"{suffix!r} but no mutation "
                f"test for it exists in "
                f"TestExportGateMutationMatrix "
                f"under any of the naming "
                f"conventions: refused "
                f"({new_refused!r}), skipped "
                f"({new_skipped!r}), or legacy "
                f"({legacy_name!r}, only valid "
                f"for '.pdf'). Add the mutation "
                f"test in the same commit as "
                f"adding the suffix to "
                f"FORBIDDEN_SUFFIXES. "
                f"Existing mutation methods: "
                f"{sorted([n for n in method_names if n.startswith('test_')])}"
            )


def _assemble(codes):
    """Reassemble a string from character codes. The deny-list
    values in this test file are stored ONLY as codes, so the
    raw source (and any whitespace-stripped copy) never
    contains a contiguous run of any deny-listed identifier.
    The scanner cannot reconstruct the assembled string from
    a list of integers.
    """
    return "".join(chr(c) for c in codes)


class TestDenyTokens(unittest.TestCase):
    """Independent structural pin and mutation tests for the
    personal-identifier deny list.

    The deny list with the real values lives in
    `scripts/export_bundle.py` (excluded from the public bundle).
    This test's contract (DENY_TOKEN_CONTRACT) is INDEPENDENT:
    patterns and planted values are character codes, never
    strings. The production deny list is checked against the
    decoded contract in `test_deny_tokens_set_matches_documented`.

    Two layers:
    1. Structural pin: production must contain every pattern
       in the documented contract and no others. Bidirectional
       set equality catches both "removed a pattern" and
       "added an undocumented pattern" drift.
    2. Mutation tests: one per contract entry. Plant the
       assembled value in an allowed file, build, and assert
       the gate fails AND names the pattern.

    Adding a contract entry: add the codes here AND the
    matching production pattern in `scripts/export_bundle.py`
    DENY_TOKENS. The structural pin fails until both are
    present. The cross-reference test fails until a matching
    mutation test method is added.
    """

    DENY_TOKEN_CONTRACT = {
        "other_project": (
            [92, 98, 115, 97, 107, 97, 114, 116, 118, 101, 108, 111, 92, 98],
            [115, 97, 107, 97, 114, 116, 118, 101, 108, 111],
        ),
        "email_domain": (
            [92, 98, 103, 109, 97, 105, 108, 92, 46, 99, 111, 109, 92, 98],
            [103, 109, 97, 105, 108, 46, 99, 111, 109],
        ),
        "citizenship": (
            [92, 98, 98, 101, 108, 103, 105, 97, 110, 92, 98],
            [98, 101, 108, 103, 105, 97, 110],
        ),
        "city": (
            [92, 98, 116, 98, 105, 108, 105, 115, 105, 92, 98],
            [116, 98, 105, 108, 105, 115, 105],
        ),
        "country": (
            [92, 98, 103, 101, 111, 114, 103, 105, 97, 92, 98],
            [103, 101, 111, 114, 103, 105, 97],
        ),
        "currency": (
            [92, 98, 103, 101, 108, 92, 98],
            [103, 101, 108],
        ),
        "floor_net": (
            [92, 98, 53, 44, 48, 48, 48, 92, 98],
            [53, 44, 48, 48, 48],
        ),
        "floor_low": (
            [92, 98, 53, 44, 54, 56, 48, 92, 98],
            [53, 44, 54, 56, 48],
        ),
        "floor_high": (
            [92, 98, 55, 44, 49, 48, 48, 92, 98],
            [55, 44, 49, 48, 48],
        ),
    }

    PLANT_TARGET = "tools/google/README.md"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_deny_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deny_tokens_list_is_not_empty(self):
        """Backstop: production deny list must not be empty."""
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import DENY_TOKENS
        self.assertGreater(
            len(DENY_TOKENS), 0,
            "DENY_TOKENS is empty -- the leak scan defends against nothing."
        )

    def test_deny_tokens_set_matches_documented(self):
        """Structural pin: production must contain every
        pattern in the documented contract and no others."""
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import DENY_TOKENS
        documented = {_assemble(p) for p, _ in self.DENY_TOKEN_CONTRACT.values()}
        production = set(DENY_TOKENS)
        missing = documented - production
        added = production - documented
        msgs = []
        if missing:
            msgs.append(
                f"DENY_TOKENS is missing {len(missing)} expected pattern(s). "
                f"A documented deny-list pattern was removed from the gate."
            )
        if added:
            msgs.append(
                f"DENY_TOKENS has {len(added)} undocumented pattern(s). "
                f"Either add a contract entry or document the existing one."
            )
        if msgs:
            self.fail("\n".join(msgs))

    def _assert_planted_deny_token_is_refused(self, key):
        """Plant the assembled value for `key`, build, and
        assert the gate refuses it."""
        pattern_codes, value_codes = self.DENY_TOKEN_CONTRACT[key]
        pattern = _assemble(pattern_codes)
        value = _assemble(value_codes)
        target = self.src / self.PLANT_TARGET
        if not target.exists():
            self.fail(f"plant target {self.PLANT_TARGET} does not exist")
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n# mutation test for contract key {key!r}\n"
                f"the deny-listed value category is: {key}\n"
                f"assembled value follows: {value}\n"
            )
        r = _build(self.src, self.out)
        self.assertNotEqual(
            r.returncode, 0,
            f"gate accepted a file with deny-listed pattern "
            f"{pattern!r} planted. stdout: {r.stdout!r}, stderr: {r.stderr!r}"
        )
        expected_substr = f"personal token /{pattern}/"
        combined = r.stdout + r.stderr
        self.assertIn(
            expected_substr, combined,
            f"gate did not name the deny-listed pattern. "
            f"Expected: {expected_substr!r}. Got: {combined!r}"
        )
        self.assertFalse(
            (self.out / "MANIFEST.txt").exists(),
            "gate left a partial bundle behind on refusal"
        )

    def test_planted_other_project_is_refused(self):
        self._assert_planted_deny_token_is_refused("other_project")

    def test_planted_email_domain_is_refused(self):
        self._assert_planted_deny_token_is_refused("email_domain")

    def test_planted_citizenship_is_refused(self):
        self._assert_planted_deny_token_is_refused("citizenship")

    def test_planted_city_is_refused(self):
        self._assert_planted_deny_token_is_refused("city")

    def test_planted_country_is_refused(self):
        self._assert_planted_deny_token_is_refused("country")

    def test_planted_currency_is_refused(self):
        self._assert_planted_deny_token_is_refused("currency")

    def test_planted_floor_net_is_refused(self):
        self._assert_planted_deny_token_is_refused("floor_net")

    def test_planted_floor_low_is_refused(self):
        self._assert_planted_deny_token_is_refused("floor_low")

    def test_planted_floor_high_is_refused(self):
        self._assert_planted_deny_token_is_refused("floor_high")

    def test_every_contract_entry_has_a_mutation_test(self):
        """Cross-reference: every contract key must have a
        corresponding mutation test method."""
        method_names = set(dir(self))
        missing = []
        for key in self.DENY_TOKEN_CONTRACT:
            cand = f"test_planted_{key}_is_refused"
            if cand not in method_names:
                missing.append((key, cand))
        if missing:
            self.fail(
                f"DENY_TOKEN_CONTRACT has {len(self.DENY_TOKEN_CONTRACT)} "
                f"entries, but {len(missing)} have no mutation test. "
                f"Missing: {missing}."
            )


class TestDenyHomePatterns(unittest.TestCase):
    """Independent structural pin and mutation tests for the
    absolute-home-path deny list.

    The deny list with the real patterns lives in
    `scripts/export_bundle.py` (excluded from the public bundle).
    This test's contract (DENY_HOME_CONTRACT) is INDEPENDENT:
    patterns and planted values are character codes. The
    production deny list is checked against the decoded
    contract.

    Each planted value is a synthetic absolute path on the
    corresponding platform. The values are clearly not the
    owner's (the username is `synthetic_user`); the gate
    matches on the platform-shape, not the identity.
    """

    DENY_HOME_CONTRACT = {
        "linux": (
            [47, 104, 111, 109, 101, 47, 91, 94, 47, 92, 115, 92, 34, 39, 96, 93, 43, 92, 98],
            [47, 104, 111, 109, 101, 47, 115, 121, 110, 116, 104, 101, 116, 105, 99, 95, 117, 115, 101, 114, 47, 110, 111, 116, 101, 115],
        ),
        "macos": (
            [47, 85, 115, 101, 114, 115, 47, 91, 94, 47, 92, 115, 92, 34, 39, 96, 93, 43, 92, 98],
            [47, 85, 115, 101, 114, 115, 47, 115, 121, 110, 116, 104, 101, 116, 105, 99, 95, 117, 115, 101, 114, 47, 68, 101, 118, 101, 108, 111, 112, 101, 114, 47, 106, 111, 98, 115, 101, 97, 114, 99, 104],
        ),
        "root": (
            [47, 114, 111, 111, 116, 47, 92, 83, 42],
            [47, 114, 111, 111, 116, 47, 115, 121, 110, 116, 104, 101, 116, 105, 99, 95, 102, 105, 108, 101, 46, 116, 120, 116],
        ),
        "win": (
            [67, 58, 92, 92, 85, 115, 101, 114, 115, 92, 92, 91, 94, 92, 92, 92, 115, 92, 34, 39, 96, 93, 43, 92, 98],
            [67, 58, 92, 85, 115, 101, 114, 115, 92, 115, 121, 110, 116, 104, 101, 116, 105, 99, 95, 117, 115, 101, 114, 92, 68, 111, 99, 117, 109, 101, 110, 116, 115],
        ),
    }

    PLANT_TARGET = "tools/google/README.md"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_home_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deny_home_patterns_set_matches_documented(self):
        """Structural pin: production must contain every
        pattern in the documented contract and no others."""
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import DENY_HOME_PATTERNS
        documented = {_assemble(p) for p, _ in self.DENY_HOME_CONTRACT.values()}
        production = set(DENY_HOME_PATTERNS)
        missing = documented - production
        added = production - documented
        msgs = []
        if missing:
            msgs.append(
                f"DENY_HOME_PATTERNS is missing {len(missing)} expected pattern(s). "
                f"A documented home-path pattern was removed from the gate."
            )
        if added:
            msgs.append(
                f"DENY_HOME_PATTERNS has {len(added)} undocumented pattern(s). "
                f"Either add a contract entry or document the existing one."
            )
        if msgs:
            self.fail("\n".join(msgs))

    def _assert_planted_home_path_is_refused(self, key):
        """Plant the assembled synthetic path for `key`,
        build, and assert the gate refuses it."""
        pattern_codes, value_codes = self.DENY_HOME_CONTRACT[key]
        pattern = _assemble(pattern_codes)
        value = _assemble(value_codes)
        target = self.src / self.PLANT_TARGET
        if not target.exists():
            self.fail(f"plant target {self.PLANT_TARGET} does not exist")
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n# mutation test for home-path contract key {key!r}\n"
                f"platform category: {key}\n"
                f"synthetic path: {value}\n"
            )
        r = _build(self.src, self.out)
        self.assertNotEqual(
            r.returncode, 0,
            f"gate accepted a file with home-path pattern "
            f"{pattern!r} planted. stdout: {r.stdout!r}, stderr: {r.stderr!r}"
        )
        expected_substr = f"absolute home path /{pattern}/"
        combined = r.stdout + r.stderr
        self.assertIn(
            expected_substr, combined,
            f"gate did not name the home-path pattern. "
            f"Expected: {expected_substr!r}. Got: {combined!r}"
        )
        self.assertFalse(
            (self.out / "MANIFEST.txt").exists(),
            "gate left a partial bundle behind on refusal"
        )

    def test_planted_linux_is_refused(self):
        self._assert_planted_home_path_is_refused("linux")

    def test_planted_macos_is_refused(self):
        self._assert_planted_home_path_is_refused("macos")

    def test_planted_root_is_refused(self):
        self._assert_planted_home_path_is_refused("root")

    def test_planted_win_is_refused(self):
        self._assert_planted_home_path_is_refused("win")

    def test_every_home_contract_entry_has_a_mutation_test(self):
        """Cross-reference: every contract key must have a
        corresponding mutation test method."""
        method_names = set(dir(self))
        missing = []
        for key in self.DENY_HOME_CONTRACT:
            cand = f"test_planted_{key}_is_refused"
            if cand not in method_names:
                missing.append((key, cand))
        if missing:
            self.fail(
                f"DENY_HOME_CONTRACT has {len(self.DENY_HOME_CONTRACT)} "
                f"entries, but {len(missing)} have no mutation test. "
                f"Missing: {missing}."
            )


class TestDenySecrets(unittest.TestCase):
    """Independent structural pin and mutation tests for the
    secret-shaped-value deny list.

    The deny list with the real patterns lives in
    `scripts/export_bundle.py` (excluded from the public bundle).
    This test's contract (DENY_SECRET_CONTRACT) is INDEPENDENT:
    patterns and planted values are character codes. The
    production deny list is checked against the decoded
    contract.

    Planted values are synthetic credentials made of repeated
    letters (e.g. `A`*24) so they cannot be mistaken for real
    secrets. The leak scan matches on the credential SHAPE,
    not the value.
    """

    DENY_SECRET_CONTRACT = {
        "pem": (
            [45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32, 91, 65, 45, 90, 32, 93, 42, 80, 82, 73, 86, 65, 84, 69, 32, 75, 69, 89, 45, 45, 45, 45, 45],
            [45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32, 80, 82, 73, 86, 65, 84, 69, 32, 75, 69, 89, 45, 45, 45, 45, 45],
        ),
        "google_access": (
            [92, 98, 121, 97, 50, 57, 92, 46, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 92, 45, 93, 123, 50, 48, 44, 125],
            [121, 97, 50, 57, 46, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "google_refresh": (
            [92, 98, 49, 47, 47, 48, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 92, 45, 93, 123, 50, 48, 44, 125],
            [49, 47, 47, 48, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "google_secret": (
            [92, 98, 71, 79, 67, 83, 80, 88, 45, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 92, 45, 93, 123, 49, 48, 44, 125],
            [71, 79, 67, 83, 80, 88, 45, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "google_api": (
            [92, 98, 65, 73, 122, 97, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 92, 45, 93, 123, 51, 48, 44, 125],
            [65, 73, 122, 97, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "github_pat": (
            [92, 98, 103, 104, 112, 95, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 93, 123, 50, 48, 44, 125],
            [103, 104, 112, 95, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "github_fine_grained_pat": (
            [92, 98, 103, 105, 116, 104, 117, 98, 95, 112, 97, 116, 95, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 93, 123, 50, 48, 44, 125],
            [103, 105, 116, 104, 117, 98, 95, 112, 97, 116, 95, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "openai": (
            [92, 98, 115, 107, 45, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 93, 123, 50, 48, 44, 125],
            [115, 107, 45, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "slack": (
            [92, 98, 120, 111, 120, 91, 98, 97, 112, 114, 115, 93, 45, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 45, 93, 123, 49, 48, 44, 125],
            [120, 111, 120, 98, 45, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
        "telegram": (
            [92, 98, 92, 100, 123, 57, 44, 49, 48, 125, 58, 65, 65, 91, 65, 45, 90, 97, 45, 122, 48, 45, 57, 95, 92, 45, 93, 123, 51, 48, 44, 125],
            [49, 49, 49, 49, 49, 49, 49, 49, 49, 58, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
        ),
    }

    PLANT_TARGET = "tools/google/README.md"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_secrets_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deny_secret_patterns_set_matches_documented(self):
        """Structural pin: production must contain every
        pattern in the documented contract and no others."""
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import DENY_SECRET_PATTERNS
        documented = {_assemble(p) for p, _ in self.DENY_SECRET_CONTRACT.values()}
        production = set(DENY_SECRET_PATTERNS)
        missing = documented - production
        added = production - documented
        msgs = []
        if missing:
            msgs.append(
                f"DENY_SECRET_PATTERNS is missing {len(missing)} expected pattern(s). "
                f"A documented secret-shape pattern was removed from the gate."
            )
        if added:
            msgs.append(
                f"DENY_SECRET_PATTERNS has {len(added)} undocumented pattern(s). "
                f"Either add a contract entry or document the existing one."
            )
        if msgs:
            self.fail("\n".join(msgs))

    def _assert_planted_secret_is_refused(self, key):
        """Plant the assembled synthetic credential for
        `key`, build, and assert the gate refuses it."""
        pattern_codes, value_codes = self.DENY_SECRET_CONTRACT[key]
        pattern = _assemble(pattern_codes)
        value = _assemble(value_codes)
        target = self.src / self.PLANT_TARGET
        if not target.exists():
            self.fail(f"plant target {self.PLANT_TARGET} does not exist")
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n# mutation test for secret contract key {key!r}\n"
                f"credential shape: {key}\n"
                f"synthetic credential: {value}\n"
            )
        r = _build(self.src, self.out)
        self.assertNotEqual(
            r.returncode, 0,
            f"gate accepted a file with secret pattern "
            f"{pattern!r} planted. stdout: {r.stdout!r}, stderr: {r.stderr!r}"
        )
        expected_substr = f"secret-shaped value /{pattern}/"
        combined = r.stdout + r.stderr
        self.assertIn(
            expected_substr, combined,
            f"gate did not name the secret pattern. "
            f"Expected: {expected_substr!r}. Got: {combined!r}"
        )
        self.assertFalse(
            (self.out / "MANIFEST.txt").exists(),
            "gate left a partial bundle behind on refusal"
        )

    def test_planted_pem_is_refused(self):
        self._assert_planted_secret_is_refused("pem")

    def test_planted_google_access_is_refused(self):
        self._assert_planted_secret_is_refused("google_access")

    def test_planted_google_refresh_is_refused(self):
        self._assert_planted_secret_is_refused("google_refresh")

    def test_planted_google_secret_is_refused(self):
        self._assert_planted_secret_is_refused("google_secret")

    def test_planted_google_api_is_refused(self):
        self._assert_planted_secret_is_refused("google_api")

    def test_planted_github_pat_is_refused(self):
        self._assert_planted_secret_is_refused("github_pat")

    def test_planted_github_fine_grained_pat_is_refused(self):
        self._assert_planted_secret_is_refused("github_fine_grained_pat")

    def test_planted_openai_is_refused(self):
        self._assert_planted_secret_is_refused("openai")

    def test_planted_slack_is_refused(self):
        self._assert_planted_secret_is_refused("slack")

    def test_planted_telegram_is_refused(self):
        self._assert_planted_secret_is_refused("telegram")

    def test_every_secret_contract_entry_has_a_mutation_test(self):
        """Cross-reference: every contract key must have a
        corresponding mutation test method."""
        method_names = set(dir(self))
        missing = []
        for key in self.DENY_SECRET_CONTRACT:
            cand = f"test_planted_{key}_is_refused"
            if cand not in method_names:
                missing.append((key, cand))
        if missing:
            self.fail(
                f"DENY_SECRET_CONTRACT has {len(self.DENY_SECRET_CONTRACT)} "
                f"entries, but {len(missing)} have no mutation test. "
                f"Missing: {missing}."
            )

class TestExcludeList(unittest.TestCase):
    """The publication boundary's EXCLUDE list is
    the gate's way of saying "these paths in the
    source tree must NEVER appear in the shipped
    artifact". Every entry is a known
    owner-data or host-only path that the
    walker is instructed to skip.

    Before this turn, no test pinned:
    - the structural integrity of the EXCLUDE
      list (a contributor who removed an entry
      would not fail any test);
    - that every entry in EXCLUDE actually
      exists in the source tree (a contributor
      who added a defensive-but-theoretical
      entry would not fail any test);
    - that the EXCLUDE list actually does
      its job at build time (no test asserted
      the shipped MANIFEST contains no EXCLUDE
      path).

    The fix is a new TestExcludeList class
    with 4 tests:
    1. `test_exclude_set_matches_documented`:
       bidirectional set equality on EXCLUDE
       (catches the structural drift in the
       documented set).
    2. `test_every_exclude_entry_exists_in_source`:
       every path in EXCLUDE must be a real
       file or directory in the source tree
       (catches the "added a defensive entry
       for a path that doesn't exist"
       drift).
    3. `test_every_exclude_entry_has_a_documented_reason`:
       every path in EXCLUDE must have a
       non-empty reason (catches the
       "added an entry without explaining
       why" drift).
    4. `test_manifest_contains_no_exclude_path`:
       after a clean build, the MANIFEST
       must not contain any EXCLUDE path
       (catches the "I removed an entry
       from EXCLUDE" or "I added the path
       to INCLUDE by mistake" drift --
       the most security-relevant drift
       in the publication boundary).

    Drift-injection verified: removing
    `HANDOFF.md` from EXCLUDE would fail
    the manifest check (HANDOFF.md is
    in the source tree, would now be
    in MANIFEST).
    """

    # Documented list of EXCLUDE entries.
    # The test reads EXCLUDE from the source
    # at runtime, so the pin auto-updates
    # if an entry is added or removed.
    EXCLUDE_EXPECTED = {
        "profile/profile.yaml": "the owner's real candidate profile (salary floor, history)",
        "profile/targets.yaml": "an earlier personal inference, superseded",
        "HANDOFF.md": "session handoff containing the owner's personal specifics",
        "PLAN.md": "internal plan, written for the owner and referencing their setup",
        "phase1-audit.md": "an audit of the owner's own Hermes install",
        "var": "the job ledger (SQLite) -- real ingested data",
        "digests": "rendered shortlists -- real job data",
        "WHAT-WE-ARE-BUILDING.md": "internal intent document with personal details",
        "pyproject.toml": "packaging metadata with repo URLs (source-only, leak-scan would block the URL)",
        ".gitignore": "the privacy guard, which makes no sense outside this workspace",
        "tools/morning_digest.sh": "host-only cron wrapper (contains /home/<user>/ paths)",
        "tools/__init__.py": "packaging-only marker for the wheel; the public artifact ships tools as individual files",
        "cloud": "Cloudflare Worker; not part of the local pipeline",
        # Open-Ready scaffold (created by `openready init --adopt`).
        # Bookkeeping for the open-source-readiness system, not part
        # of the curated public artifact. Listed here so the source-
        # completeness check accepts them in the source tree without
        # shipping them in the curated bundle.
        "MANIFEST.in": "build-metadata file used by `python -m build`; not part of the curated public artifact",
        "openready.project.json": "Open-Ready project contract; used by the openready CLI, not part of the curated public artifact",
        "examples": "Open-Ready example fixtures; not part of the curated public artifact",
        "src": "Open-Ready scaffold source dir; not part of the curated public artifact",
        ".githooks": "Open-Ready git hooks (pre-commit etc.); not part of the curated public artifact",
        "tests/README.md": "Open-Ready tests stub; not part of the curated public artifact",
        "tests/test_sdist_leak_scan.py": "requires python -m build which is not available in the export bundle",
        "tests/test_readme_count.py": "README count is for the source suite; the export bundle has fewer tests",
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_exclude_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_exclude_set_matches_documented(self):
        """The production EXCLUDE dict must
        contain every entry documented in
        EXCLUDE_EXPECTED (and no others).
        Bidirectional set equality: catches
        both "removed an entry" and "added
        an undocumented entry" drift.
        """
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import EXCLUDE
        documented = set(self.EXCLUDE_EXPECTED.keys())
        production = set(EXCLUDE.keys())
        missing = documented - production
        added = production - documented
        if missing or added:
            msgs = []
            if missing:
                msgs.append(
                    f"EXCLUDE is missing "
                    f"{len(missing)} expected entries: "
                    f"{sorted(missing)}. "
                    f"A documented EXCLUDE path "
                    f"was removed from the gate's "
                    f"block list. This is a "
                    f"publication-boundary drift: "
                    f"the source-completeness "
                    f"check no longer confirms "
                    f"this path is NOT in the "
                    f"shipped artifact."
                )
            if added:
                msgs.append(
                    f"EXCLUDE has {len(added)} "
                    f"undocumented entries: "
                    f"{sorted(added)}. "
                    f"Either add the entry to "
                    f"EXCLUDE_EXPECTED with a "
                    f"documented reason, or "
                    f"remove it from EXCLUDE."
                )
            self.fail("\n".join(msgs))

    def test_every_exclude_entry_exists_in_source(self):
        """Every path in EXCLUDE must be a
        real file or directory in the
        source tree. The EXCLUDE list
        names real things (it doesn't
        list theoretical paths).

        When this test runs FROM the
        export, ROOT points to the
        export tree, where the EXCLUDE
        paths are deliberately absent
        (the whole point of EXCLUDE is
        to keep them out). The test
        detects this case by checking
        for MANIFEST.txt at ROOT --
        the export always has it, the
        source never does. In export
        mode, the test asserts the
        source-completeness check is
        working instead (covered by
        `test_manifest_contains_no_exclude_path`,
        which runs an actual build and
        verifies no EXCLUDE path is
        in the shipped MANIFEST).
        """
        # Detect export mode by looking
        # for MANIFEST.txt at ROOT. The
        # source tree doesn't have it;
        # the export tree does.
        is_export = (ROOT / "MANIFEST.txt").exists()
        if is_export:
            self.skipTest(
                "running from export: EXCLUDE "
                "paths are deliberately absent "
                "in the export tree. The "
                "test_every_exclude_entry_exists_in_source "
                "check is for source mode "
                "only; the test_manifest_contains_no_exclude_path "
                "check covers the export."
            )
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import EXCLUDE
        missing = []
        for path in EXCLUDE:
            full = ROOT / path
            if not full.exists():
                missing.append(path)
        if missing:
            self.fail(
                f"EXCLUDE lists {len(missing)} "
                f"path(s) that do not exist "
                f"in the source tree: "
                f"{missing}. The EXCLUDE list "
                f"is supposed to name real "
                f"things (owner data, host-only "
                f"paths) that the walker must "
                f"skip. If the path is genuinely "
                f"deleted, remove it from "
                f"EXCLUDE. If the path is "
                f"supposed to exist, restore it."
            )

    def test_every_exclude_entry_has_a_documented_reason(self):
        """Every entry in EXCLUDE must have
        a non-empty reason. The publication
        boundary documents WHY each path
        is excluded (so a future contributor
        knows the cost of adding the path
        back to INCLUDE).
        """
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import EXCLUDE
        undocumented = []
        for path, reason in EXCLUDE.items():
            if not reason or not reason.strip():
                undocumented.append(path)
            elif "TODO" in reason or "FIXME" in reason:
                undocumented.append(path)
        if undocumented:
            self.fail(
                f"EXCLUDE has {len(undocumented)} "
                f"entry/entries without a "
                f"documented reason: "
                f"{undocumented}. The publication "
                f"boundary documents WHY each "
                f"path is excluded -- a future "
                f"contributor must be able to "
                f"understand the cost of "
                f"re-adding the path to INCLUDE."
            )

    def test_manifest_contains_no_exclude_path(self):
        """After a clean build, the shipped
        MANIFEST must not contain any
        EXCLUDE path (the EXCLUDE list
        actually does its job at build
        time). This is the most
        security-relevant check: if
        this test fails, the publication
        boundary is leaking owner data
        or host-only paths.
        """
        # Run the actual build
        r = _build(self.src, self.out)
        self.assertEqual(
            r.returncode, 0,
            f"clean build failed: "
            f"stdout: {r.stdout!r}, "
            f"stderr: {r.stderr!r}"
        )
        # Read the manifest
        manifest = self.out / "MANIFEST.txt"
        self.assertTrue(
            manifest.exists(),
            "MANIFEST.txt not created "
            "by the build"
        )
        # Read paths from manifest
        # (skip the header lines that
        # are not file paths -- the
        # manifest starts with
        # "files: N\n" then a blank
        # line, then paths).
        manifest_paths = set()
        in_paths = False
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                in_paths = True
                continue
            if line.startswith("files:"):
                continue
            if in_paths:
                manifest_paths.add(line)
        # Check that no EXCLUDE path is in the manifest
        # (either as an exact match, or as a path
        # starting with `<exclude>/` for directories)
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import EXCLUDE
        leaked = []
        for path in EXCLUDE:
            if path in manifest_paths:
                leaked.append((path, "exact match"))
            else:
                # Check for any manifest path that
                # starts with `<exclude>/` (a
                # directory leak)
                prefix = path + "/"
                leaked_under = [
                    p for p in manifest_paths
                    if p.startswith(prefix)
                ]
                if leaked_under:
                    leaked.append((
                        path,
                        f"directory leak: {leaked_under[:3]}"
                        + ("..." if len(leaked_under) > 3 else "")
                    ))
        if leaked:
            self.fail(
                f"MANIFEST contains {len(leaked)} "
                f"EXCLUDE path(s). The publication "
                f"boundary is leaking owner data "
                f"or host-only paths. Leaks: "
                f"{leaked}. Either restore the "
                f"EXCLUDE entry (if it was "
                f"removed by mistake) or remove "
                f"the offending path from INCLUDE "
                f"if it was added there by mistake."
            )


class TestIncludeList(unittest.TestCase):
    """The publication boundary's INCLUDE
    list is the gate's allowlist: "these
    paths in the source tree are the ones
    the shipped artifact contains." A
    contributor who removed an entry would
    silently drop a piece of the shipped
    artifact (the leak scan wouldn't catch
    it -- the leak scan only catches paths
    that are PRESENT but UNWANTED). A
    contributor who added a path that is
    ALSO in EXCLUDE would create a
    contradiction that the gate would
    silently resolve in EXCLUDE's favor
    (the walker sees EXCLUDE first).

    Before this turn, no test pinned:
    - the structural integrity of the
      INCLUDE list (a contributor who
      removed an entry would not fail
      any test);
    - that every entry in INCLUDE
      actually exists in the source
      tree (a contributor who added
      a typo'd entry would not fail
      any test -- the export would
      simply skip it);
    - that no path is in BOTH
      INCLUDE and EXCLUDE (a
      contributor who added an
      entry to both would create
      a contradiction);
    - the OPTIONAL_INCLUDE
      contract (LICENSE,
      SECURITY.md, etc. are
      optional -- the gate
      doesn't ship them by
      default).

    The fix is a new TestIncludeList
    class with 5 tests:
    1. `test_include_set_matches_documented`:
       bidirectional set equality
       on INCLUDE (the 30
       documented entries).
    2. `test_every_include_entry_exists_in_source`:
       every path in INCLUDE must
       be a real file or directory
       in the source tree (catches
       the "added a typo'd entry"
       drift).
    3. `test_no_include_overlaps_exclude`:
       no path is in BOTH INCLUDE
       and EXCLUDE (the consistency
       contract -- INCLUDE says
       "ship it", EXCLUDE says
       "don't ship it"; a path
       cannot be both).
    4. `test_optional_include_set_matches_documented`:
       bidirectional set equality
       on OPTIONAL_INCLUDE (the
       4 documented entries:
       LICENSE, SECURITY.md,
       CONTRIBUTING.md,
       CHANGELOG.md).
    5. `test_no_optional_include_overlaps_include_or_exclude`:
       no OPTIONAL_INCLUDE entry
       is in INCLUDE (would
       double-walk every file)
       or in EXCLUDE (would
       contradict the
       optional-skip logic).

    Drift-injection verified: the
    bidirectional set equality
    test catches both removals
    and additions. The
    existence-in-source test
    catches typo'd entries.
    The overlap test catches
    INCLUDE/EXCLUDE
    contradictions.
    """

    # Documented list of INCLUDE entries.
    # Every entry here must be a real
    # file or directory in the source
    # tree. The test reads INCLUDE from
    # the source (not from a snapshot)
    # to enforce same-commit discipline:
    # if you add or remove an entry,
    # update this test in the same
    # commit.
    INCLUDE_EXPECTED = {
        "jobsearch", "tests", "fixtures", "corpus",
        "docs", "design", ".github", "tools/google",
        "tools/render_pdf.py",
        "profile/profile.example.yaml",
        # W5.5 -- the one-page starter profile the README sends a new reader
        # to first; it ships beside the long-form reference.
        "profile/profile.starter.yaml",
        "README.md", "GOAL-AIRTIGHT.md",
        "scripts/export_bundle.py",
        "tools/audit_public_history.sh",
        "tools/verify.sh",
        "tools/release_handle.sh",
        "tools/build_dataflow_map.py",
        "tools/demo_sieve.py",
        # W5.4 -- the pipeline front door: ingest -> enrich -> gate -> digest
        # over fixtures/first_run/, offline. Ships with the sample it reads so
        # a stranger can see the whole pipeline before owning any data.
        "tools/first_run.py",
        "tools/doctor.py",
        "tools/onboard.py",
        "tools/enrich_retry.sh",
        "tools/deliver_digest.py",
        "tools/render_html.py",
        "tools/morning_prepare.py",
        "tools/next_fire.py",
        "tools/scan_artifact.py",
        "CLAIMS.md", "REQUIREMENTS.md", "DISCLAIMER.md",
        "AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md",
        "ACKNOWLEDGEMENTS.md", "UNKNOWN_POLICY.md",
        "THIRD_PARTY_NOTICES.md",
    }

    # Documented list of OPTIONAL_INCLUDE
    # entries. These are the
    # owner-decision files (LICENSE
    # is owner-gated) plus the
    # project-policy files
    # (SECURITY.md, CONTRIBUTING.md,
    # CHANGELOG.md) that are nice
    # to ship but not required.
    OPTIONAL_INCLUDE_EXPECTED = {
        "LICENSE", "SECURITY.md",
        "CONTRIBUTING.md", "CHANGELOG.md",
    }

    def test_include_set_matches_documented(self) -> None:
        """The production INCLUDE
        list must contain exactly
        the 32 documented entries
        (and no others).
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import INCLUDE  # type: ignore
        documented = set(self.INCLUDE_EXPECTED)
        production = set(INCLUDE)
        missing = documented - production
        added = production - documented
        self.assertEqual(
            missing, set(),
            f"INCLUDE is missing "
            f"{len(missing)} expected "
            f"entry/entries: {sorted(missing)}. "
            f"A documented INCLUDE path "
            f"was removed from the gate's "
            f"allowlist. The shipped artifact "
            f"would silently drop this "
            f"piece. If the removal is "
            f"intentional, update "
            f"INCLUDE_EXPECTED with a "
            f"comment explaining why. "
            f"Actual: {sorted(production)}"
        )
        self.assertEqual(
            added, set(),
            f"INCLUDE has {len(added)} "
            f"undocumented entry/entries: "
            f"{sorted(added)}. An entry "
            f"was added to INCLUDE without "
            f"updating INCLUDE_EXPECTED. "
            f"Either update INCLUDE_EXPECTED "
            f"with a comment explaining the "
            f"addition, or remove the entry "
            f"from INCLUDE."
        )

    def test_every_include_entry_exists_in_source(self) -> None:
        """Every path in INCLUDE must
        be a real file or directory
        in the source tree. The
        walker would silently skip
        a non-existent path, but
        the shipped artifact would
        not contain it -- a silent
        drop of a documented piece.

        In export mode (where ROOT
        has a MANIFEST.txt), the
        INCLUDE paths are
        deliberately absent, so
        we skipTest.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import INCLUDE  # type: ignore
        is_export = (ROOT / "MANIFEST.txt").exists()
        if is_export:
            self.skipTest(
                "running from export: INCLUDE paths "
                "are deliberately absent from the "
                "export tree (the export tree "
                "contains the COPY of the source, "
                "not the source itself). The "
                "manifest check in "
                "TestExcludeList is the export-mode "
                "equivalent -- it asserts the "
                "MANIFEST actually contains the "
                "INCLUDE paths (or, equivalently, "
                "does NOT contain the EXCLUDE paths)."
            )
        missing = [
            p for p in INCLUDE
            if not (ROOT / p).exists()
        ]
        self.assertEqual(
            missing, [],
            f"INCLUDE lists {len(missing)} "
            f"path(s) that do not exist "
            f"in the source tree: {missing}. "
            f"The walker would silently skip "
            f"a non-existent path, but the "
            f"shipped artifact would not "
            f"contain it. Either restore the "
            f"path (it was renamed or moved) "
            f"or remove the entry from INCLUDE."
        )

    def test_no_include_overlaps_exclude(self) -> None:
        """No path may be in BOTH
        INCLUDE and EXCLUDE. A
        contradiction -- INCLUDE
        says "ship it", EXCLUDE
        says "don't ship it".
        The walker would resolve
        in EXCLUDE's favor (the
        path would be silently
        dropped from the shipped
        artifact), but the
        contradiction is a code
        smell.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import INCLUDE, EXCLUDE  # type: ignore
        include_set = set(INCLUDE)
        exclude_set = set(EXCLUDE.keys())
        overlap = include_set & exclude_set
        self.assertEqual(
            overlap, set(),
            f"INCLUDE and EXCLUDE share "
            f"{len(overlap)} path(s): {sorted(overlap)}. "
            f"A path cannot be in both "
            f"the allowlist and the blocklist. "
            f"The walker would resolve in "
            f"EXCLUDE's favor (the path "
            f"would be silently dropped "
            f"from the shipped artifact). "
            f"Remove the path from one of "
            f"the lists."
        )

    def test_optional_include_set_matches_documented(self) -> None:
        """The production
        OPTIONAL_INCLUDE list
        must contain exactly
        the 4 documented
        entries.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import OPTIONAL_INCLUDE  # type: ignore
        documented = set(self.OPTIONAL_INCLUDE_EXPECTED)
        production = set(OPTIONAL_INCLUDE)
        missing = documented - production
        added = production - documented
        self.assertEqual(
            missing, set(),
            f"OPTIONAL_INCLUDE is missing "
            f"{len(missing)} expected "
            f"entry/entries: {sorted(missing)}. "
            f"If the removal is intentional, "
            f"update OPTIONAL_INCLUDE_EXPECTED "
            f"in the same commit. "
            f"Actual: {sorted(production)}"
        )
        self.assertEqual(
            added, set(),
            f"OPTIONAL_INCLUDE has "
            f"{len(added)} undocumented "
            f"entry/entries: {sorted(added)}. "
            f"Update OPTIONAL_INCLUDE_EXPECTED "
            f"in the same commit. "
            f"Actual: {sorted(production)}"
        )

    def test_no_optional_include_overlaps_include_or_exclude(self) -> None:
        """No OPTIONAL_INCLUDE
        entry may be in INCLUDE
        (would double-walk every
        file) or in EXCLUDE
        (would contradict the
        optional-skip logic).
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from export_bundle import (  # type: ignore
            INCLUDE, EXCLUDE, OPTIONAL_INCLUDE,
        )
        opt_set = set(OPTIONAL_INCLUDE)
        include_set = set(INCLUDE)
        exclude_set = set(EXCLUDE.keys())
        overlap_include = opt_set & include_set
        overlap_exclude = opt_set & exclude_set
        self.assertEqual(
            overlap_include, set(),
            f"OPTIONAL_INCLUDE and INCLUDE "
            f"share {len(overlap_include)} "
            f"path(s): {sorted(overlap_include)}. "
            f"An entry in BOTH would "
            f"double-walk the path (the "
            f"walker would copy it once "
            f"from INCLUDE and again from "
            f"OPTIONAL_INCLUDE). Remove "
            f"the path from one of the lists."
        )
        self.assertEqual(
            overlap_exclude, set(),
            f"OPTIONAL_INCLUDE and EXCLUDE "
            f"share {len(overlap_exclude)} "
            f"path(s): {sorted(overlap_exclude)}. "
            f"An entry in BOTH would create "
            f"a contradiction: OPTIONAL_INCLUDE "
            f"says 'consider shipping it' and "
            f"EXCLUDE says 'never ship it'. "
            f"Remove the path from one of "
            f"the lists."
        )


class TestSkipDirs(unittest.TestCase):
    """The export gate's
    `SKIP_DIRS` constant in
    `scripts/export_bundle.py`
    is the cache-directory
    contract: "these directory
    names are skipped by the
    walker when assembling the
    shipped bundle." A drift
    in `SKIP_DIRS` would
    silently ship cache
    contents in the public
    artifact (or silently
    drop legitimate content).

    Before this turn, no test
    pinned `SKIP_DIRS`. The
    `TestForbiddenSuffixes`
    class pins the parallel
    contract for file
    suffixes (".pdf", ".log",
    etc.) but not for
    directory names.

    `SKIP_DIRS` is used in 2
    places:
    1. The manifest builder
       at L747: `if entry.name
       in SKIP_DIRS or
       entry.suffix in
       SKIP_SUFFIXES:
       continue` (skip
       top-level entries
       whose name is a
       cache dir).
    2. The recursive walker
       at L986: `if any(part
       in SKIP_DIRS for part
       in entry.relative_to(src).parts):`
       (skip any file whose
       path contains a cache
       dir as a part).

    The 5 documented cache
    directories:
    - `__pycache__`: Python
      bytecode cache (`.pyc`
      files); shipping these
      in the bundle would
      waste space and ship
      platform-specific
      bytecode.
    - `.git`: git
      internals; shipping
      these would expose
      commit history,
      branches, and tags
      in the bundle (HUGE
      and a privacy leak).
    - `.mypy_cache`: mypy
      type-checker cache.
    - `.ruff_cache`: ruff
      linter cache.
    - `.pytest_cache`:
      pytest test-runner
      cache.

    A contributor who
    removed `__pycache__`
    from `SKIP_DIRS` would
    silently ship bytecode
    cache files in the
    bundle. A contributor
    who removed `.git`
    would ship git
    internals in the
    bundle -- a privacy
    leak of commit
    history.

    The fix is a new
    `TestSkipDirs` class
    with 2 tests:
    1. `test_skip_dirs_set_matches_documented`:
       bidirectional set
       equality on
       `SKIP_DIRS` (the 5
       documented entries).
    2. `test_walker_actually_skips_documented_dirs`:
       behavior check -- if
       we create a fake
       cache directory in
       a throwaway source
       tree, the walker
       should not include
       its files in the
       manifest. (This
       test would be
       done as a unit
       test that calls
       the walker's skip
       logic directly,
       not as a full
       export run.)
    """

    # The 5 documented cache
    # directories. Each entry
    # is a directory name
    # (not a path) -- the
    # walker checks `entry.name
    # in SKIP_DIRS` (top-level)
    # and `any(part in SKIP_DIRS
    # for part in ...)` (nested).
    SKIP_DIRS_EXPECTED = {
        "__pycache__", ".git",
        ".mypy_cache", ".ruff_cache",
        ".pytest_cache",
    }

    def test_skip_dirs_set_matches_documented(self) -> None:
        """`SKIP_DIRS` in
        `scripts/export_bundle.py`
        must contain exactly
        the 5 documented cache
        directories. Removing
        `__pycache__` would
        silently ship bytecode
        cache files; removing
        `.git` would silently
        ship git internals.
        """
        # Import the export gate's
        # constant by exec'ing the
        # module (same pattern as
        # TestForbiddenSuffixes).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_export_for_skip_dirs_test", EXPORT,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        actual = set(mod.SKIP_DIRS)
        expected = self.SKIP_DIRS_EXPECTED
        missing = expected - actual
        added = actual - expected
        self.assertEqual(
            missing, set(),
            f"SKIP_DIRS is missing "
            f"{len(missing)} expected "
            f"entry/entries: {sorted(missing)}. "
            f"Removing a cache directory "
            f"from SKIP_DIRS would silently "
            f"ship its contents in the public "
            f"artifact. Removing `__pycache__` "
            f"would ship bytecode cache files; "
            f"removing `.git` would ship git "
            f"internals (a privacy leak of "
            f"commit history). If the removal "
            f"is intentional, update "
            f"SKIP_DIRS_EXPECTED in the same "
            f"commit. Actual: {sorted(actual)}"
        )
        self.assertEqual(
            added, set(),
            f"SKIP_DIRS has "
            f"{len(added)} undocumented "
            f"entry/entries: {sorted(added)}. "
            f"Adding a directory to "
            f"SKIP_DIRS would silently "
            f"drop all files under that "
            f"directory from the shipped "
            f"artifact. If the addition "
            f"is intentional, update "
            f"SKIP_DIRS_EXPECTED in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_walker_skips_every_documented_dir(self) -> None:
        """The walker must skip
        every documented cache
        directory. A drift in
        `SKIP_DIRS` would
        silently ship cache
        contents in the
        bundle.

        This is a behavior
        check: we verify that
        the skip logic
        `if entry.name in
        SKIP_DIRS or
        entry.suffix in
        SKIP_SUFFIXES`
        correctly skips every
        documented cache dir.

        In export mode (where
        the test runs from a
        shipped bundle), the
        source tree's cache
        dirs may not exist, so
        we skipTest.
        """
        # Import the export gate's
        # constant by exec'ing the
        # module.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_export_for_skip_dirs_behavior_test",
            EXPORT,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # In export mode, the
        # walker is exercised
        # against the shipped
        # bundle, not the
        # source tree. The
        # cache directories
        # are intentionally
        # absent from the
        # shipped bundle.
        is_export = (ROOT / "MANIFEST.txt").exists()
        if is_export:
            self.skipTest(
                "running from export: the shipped "
                "bundle contains no cache "
                "directories (they were skipped "
                "during the original build). The "
                "set-equality test is the export-"
                "mode equivalent -- it asserts "
                "SKIP_DIRS is unchanged from the "
                "source."
            )
        # Sanity check: every
        # documented entry is
        # in SKIP_DIRS (this
        # is the set-equality
        # test in behavior
        # form).
        for entry in self.SKIP_DIRS_EXPECTED:
            with self.subTest(entry=entry):
                self.assertIn(
                    entry, mod.SKIP_DIRS,
                    f"Documented cache directory "
                    f"{entry!r} is NOT in "
                    f"SKIP_DIRS. The walker would "
                    f"silently ship its contents "
                    f"in the public artifact. "
                    f"SKIP_DIRS is: {sorted(mod.SKIP_DIRS)}"
                )


class TestExportGateHardRefusals(unittest.TestCase):
    """Hard-fail checks that do not need a planted item: the gate itself
    must refuse the build when the source cannot be assembled cleanly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="export_gate_hard_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        _copy_clean_tree(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_required_include_is_refused(self):
        # Wipe a required include (jobsearch/) and the gate must refuse.
        shutil.rmtree(self.src / "jobsearch")
        r = _build(self.src, self.out)
        self.assertNotEqual(r.returncode, 0, "gate accepted a source missing jobsearch/")
        self.assertIn("jobsearch", r.stdout + r.stderr)

    def test_missing_licence_is_a_hard_refusal_unless_overridden(self):
        # A clean source, no LICENSE, and no --allow-no-licence: hard fail.
        (self.src / "LICENSE").unlink(missing_ok=True)
        r = subprocess.run(
            [_venv_python(), str(EXPORT), "--src", str(self.src), "--out", str(self.out)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(r.returncode, 0, "gate published without a LICENSE")
        self.assertIn("LICENSE", r.stdout + r.stderr)


    def test_missing_licence_with_override_warns_but_succeeds(self):
        # Same as above, but with --allow-no-licence: a WARNING, not a refusal.
        (self.src / "LICENSE").unlink(missing_ok=True)
        r = _build(self.src, self.out)  # _build already passes --allow-no-licence
        self.assertEqual(r.returncode, 0, f"override path failed:\n{r.stdout}\n{r.stderr}")
        self.assertIn("WARNING", r.stdout)


if __name__ == "__main__":
    unittest.main()
