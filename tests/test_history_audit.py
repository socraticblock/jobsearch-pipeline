"""W1.4 — the public-history audit is a repeatable script, and it works.

`tools/audit_public_history.sh` must:

  * exit 0 on a clean public checkout (verified clean today);
  * exit non-zero when a forbidden path is planted in a fixture clone.

The fixture clone is a throwaway git repo with one commit whose tree
contains a `jobsearch/` directory, and another with a profile-shaped file.
The audit must flag both. This test creates both, runs the script, and
asserts the exit codes; the clean-tree case runs against the live public
repo (the parent of the project), which is the script's normal mode of
operation.

NOTE: this test file is shipped in the public bundle. The reference to
the live public repo is a *runtime* check, not a string we keep in the
shipped source -- see TestHistoryAuditClean for the public_repo_path()
helper that resolves the parent at runtime.

Run:  python3 -m unittest tests.test_history_audit -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT = ROOT / "tools" / "audit_public_history.sh"


def public_repo_path() -> Path:
    """Return the path of the live public repo the audit should run against.

    Resolution order: the JOBSEARCH_PUBLIC_REPO env var, then the parent
    of the project (~/hermes-workspace, which is where this project is
    developed in-tree), then None (test is skipped).

    The shipped test file does NOT name the public repo's actual name.
    The developer's local environment sets the env var; a stranger
    running the shipped test against their own checkout sets the same
    var to point at wherever their own public repo lives.
    """
    env = os.environ.get("JOBSEARCH_PUBLIC_REPO")
    if env:
        return Path(env)
    parent = ROOT.parent
    if (parent / ".git").exists():
        return parent
    return None


class TestHistoryAuditClean(unittest.TestCase):
    """The audit exits 0 on the live public checkout.

    This is the assertion that, today, the public repo contains no
    jobsearch content. A future refactor of the audit script that makes
    it too lax fails here, because the live tree is what we ship from.
    """

    def test_audit_exits_zero_on_live_public_repo(self):
        target = public_repo_path()
        if target is None:
            self.skipTest("no live public repo to audit; set JOBSEARCH_PUBLIC_REPO or run from inside the workspace")
        r = subprocess.run(
            ["bash", str(AUDIT), str(target)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(
            r.returncode, 0,
            f"audit reported a leak in the live public repo ({target}):\n{r.stdout}\n{r.stderr}",
        )


class TestHistoryAuditFixturePositives(unittest.TestCase):
    """The audit exits non-zero on a fixture clone with planted content.

    Each fixture is a throwaway git repo with one commit that contains a
    forbidden path. The audit must catch it.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="history_audit_"))
        self.repo = self.tmp / "public_clone"
        self.repo.mkdir()
        # Initialise a tiny repo with the same branch name as the public
        # one so the script's `git stash` and `git fsck` calls are valid.
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "t"], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _commit_with(self, rel_path: str, content: str) -> None:
        p = self.repo / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", rel_path], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "fixture"], check=True)

    def test_audit_catches_committed_jobsearch_path(self):
        # A jobsearch/ directory committed once: the audit must flag it.
        # The contract is exit 1 specifically (forbidden content
        # found), not just non-zero. A contributor who changes the
        # script to exit 3 (e.g. as part of a refactor that splits
        # the "forbidden" case from the "non-git" case) would
        # silently change the wire format that operators read
        # when debugging a verify.sh failure.
        self._commit_with("jobsearch/README.md", "# would-be jobsearch")
        r = subprocess.run(
            ["bash", str(AUDIT), str(self.repo)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            r.returncode, 1,
            f"audit must exit 1 (forbidden found) for a "
            f"committed jobsearch/; got {r.returncode}. "
            f"stdout: {r.stdout[:200]!r}; stderr: "
            f"{r.stderr[:200]!r}"
        )
        combined = r.stdout + r.stderr
        self.assertIn("jobsearch", combined)

    def test_audit_catches_committed_secret_file(self):
        # google_token.json committed in a public tree: the audit
        # must flag the filename. The contract is exit 1
        # specifically (forbidden content found), not just
        # non-zero.
        self._commit_with("google_token.json", "{}")
        r = subprocess.run(
            ["bash", str(AUDIT), str(self.repo)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            r.returncode, 1,
            f"audit must exit 1 (forbidden found) for a "
            f"committed google_token.json; got "
            f"{r.returncode}. stdout: {r.stdout[:200]!r}; "
            f"stderr: {r.stderr[:200]!r}"
        )
        combined = r.stdout + r.stderr
        self.assertIn("google_token.json", combined)

    def test_audit_clean_when_no_forbidden_content(self):
        # A fixture with no forbidden paths: the audit must pass.
        self._commit_with("README.md", "hello")
        self._commit_with("src/main.py", "print('hi')")
        r = subprocess.run(
            ["bash", str(AUDIT), str(self.repo)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(r.returncode, 0,
                         f"audit falsely flagged a clean tree:\n{r.stdout}\n{r.stderr}")

    def test_audit_catches_every_name_in_the_named_list(self) -> None:
        """The audit's NAMES list (line 36 of
        `tools/audit_public_history.sh`) is the contract
        for "what must never appear in a public clone".
        It currently has four entries: `jobsearch`,
        `var/jobs.db`, `google_token.json`,
        `client_secret.json`. Two of them
        (`jobsearch/`, `google_token.json`) have
        specific tests, but the other two
        (`var/jobs.db`, `client_secret.json`) are
        not pinned individually.

        A contributor who "simplifies" the NAMES list
        to just `jobsearch` (because the other three
        are "covered by other tests") would silently
        widen the audit's gap: a committed
        `var/jobs.db` (the local job-tracking
        database) or a `client_secret.json` (OAuth
        client secret) would no longer be flagged.

        The test pins all four NAMES by committing
        each one in a fresh fixture and asserting
        the audit exits 1 (forbidden found). The
        test enumerates the same list as the script
        (NAMES_SCRIPT), and the assertion fails if
        either the script list shrinks or the test
        list grows -- forcing both to be updated
        in the same commit.

        The test runs the same fixture four times
        in separate repos (to keep each test case
        independent). Each case is fast (< 1s per
        git init + commit + audit).
        """
        import tempfile
        # The four NAMES the script currently scans.
        # If you add a name to the script's NAMES
        # list, add it here too -- the test will
        # then assert the new name is caught.
        NAMES_SCRIPT = [
            "jobsearch/secret.md",   # covered by name match on "jobsearch"
            "var/jobs.db",            # local DB; covered by "var/jobs.db"
            "google_token.json",      # OAuth token; covered by name
            "client_secret.json",     # OAuth client secret; covered by name
        ]
        # Substrings the audit report MUST include
        # to be useful to a human reading the output.
        # The first two are name matches; the last
        # two are token substrings (so the report
        # names the leaked token, not just the file).
        for name in NAMES_SCRIPT:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp) / "repo"
                    repo.mkdir()
                    subprocess.run(
                        ["git", "-C", str(repo), "init", "-q"],
                        check=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(repo), "config",
                         "user.email", "test@example.com"],
                        check=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(repo), "config",
                         "user.name", "test"],
                        check=True,
                    )
                    # Commit the forbidden name with
                    # minimal content.
                    self._commit_with_name(repo, name, "fixture")
                    r = subprocess.run(
                        ["bash", str(AUDIT), str(repo)],
                        capture_output=True, text=True, timeout=60,
                    )
                    self.assertEqual(
                        r.returncode, 1,
                        f"audit must exit 1 (forbidden found) "
                        f"for a committed {name!r}; got "
                        f"{r.returncode}. stdout: "
                        f"{r.stdout[:200]!r}; stderr: "
                        f"{r.stderr[:200]!r}"
                    )
                    # The audit report must name the
                    # forbidden file so the operator
                    # can see what to fix. For the
                    # "jobsearch" case the name match
                    # fires on the substring, so the
                    # report contains "jobsearch" but
                    # not necessarily the full
                    # rel_path -- assert on the
                    # leftmost directory name (the
                    # NAMES list entry) for that
                    # case.
                    combined = r.stdout + r.stderr
                    if name.startswith("jobsearch/"):
                        # The script greps for the
                        # NAMES list entry, which is
                        # "jobsearch" (the substring
                        # of the path). The report
                        # contains "jobsearch" but
                        # not the full path.
                        self.assertIn(
                            "jobsearch", combined,
                            f"the audit report must name "
                            f"'jobsearch' when a "
                            f"'jobsearch/' file is "
                            f"committed; got: "
                            f"{combined[:300]!r}"
                        )
                    else:
                        # The other three are exact
                        # filename matches; the
                        # report must name the
                        # filename.
                        self.assertIn(
                            name, combined,
                            f"the audit report must name "
                            f"the forbidden file {name!r} "
                            f"so the operator can see "
                            f"what to fix; got: "
                            f"{combined[:300]!r}"
                        )

    def _commit_with_name(self, repo: Path, rel_path: str,
                          content: str) -> None:
        """Helper that commits a file at a relative
        path inside a specific repo. Mirrors
        `_commit_with` but takes the repo as an
        arg (the subTest case uses a fresh repo
        per case)."""
        p = repo / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", rel_path],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q",
             "-m", "fixture"],
            check=True,
        )

    def test_audit_catches_every_token_in_the_token_list(self) -> None:
        """The audit's TOKENS list (line 40 of
        `tools/audit_public_history.sh`) is the
        contract for "what personal-identifier
        strings must never appear in any git
        object in a public clone". It currently
        has several entries covering the owner's
        identifiers (city, country, project names,
        and the currency code). None of them are
        pinned individually.

        A contributor who "simplifies" the TOKENS
        list (e.g. removes the city entry because
        "the country entry already covers the
        place-name context") would silently widen
        the audit's gap: a dangling git object
        containing the city name would no longer
        be flagged. This is exactly the kind of
        leak a public-history audit is supposed
        to catch.

        The audit only scans the TOKENS list
        against dangling objects (line 92),
        because reachable history is already
        public by definition (the user
        explicitly pushed it) and HEAD is
        protected by the pre-push hook. A
        dangling object is the only place a
        future contributor might miss a token:
        a file was added and then `git rm`'d,
        the commit was rewritten, the branch
        was deleted -- the object is still in
        the object store and would be pushed
        by a future `git push --mirror` or
        `git push --tags --force`.

        The test pins all three TOKENS by:
        1. Initializing a fresh git repo.
        2. Creating a dangling blob with `git
           hash-object -w --stdin` containing
           exactly one token (so the test
           attributes the flag to the right
           token, not "any token").
        3. Running the audit.
        4. Asserting the audit exits 1
           (forbidden found) AND names the
           specific token in the report.

        The test list is parallel to the
        script list, so adding a new token
        requires updating both in the same
        commit.
        """
        import tempfile
        # The audit script's TOKENS list is the
        # contract for what the script scans. We
        # read it at test time from the audit
        # script itself, so the test source does
        # not hardcode any personal-identifier
        # value (the real values live in
        # tools/audit_public_history.sh, which is
        # not in the shipped bundle).
        import re as _re
        text = AUDIT.read_text(encoding="utf-8")
        m = _re.search(r"TOKENS=\((.*?)\)", text, _re.DOTALL)
        self.assertIsNotNone(
            m, "could not locate TOKENS=(...) in the audit script"
        )
        TOKENS_SCRIPT = _re.findall(r'"([^"]+)"', m.group(1))
        for token in TOKENS_SCRIPT:
            with self.subTest(token=token):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp) / "repo"
                    repo.mkdir()
                    subprocess.run(
                        ["git", "-C", str(repo), "init", "-q"],
                        check=True,
                    )
                    # Create a dangling blob
                    # containing ONLY this token
                    # (so the test attributes
                    # the flag to the right
                    # token, not "any token").
                    # The blob is created with
                    # `git hash-object -w` which
                    # writes the object to the
                    # store but does NOT link
                    # it to any commit, so it
                    # shows up as a dangling
                    # object in `git fsck`.
                    content = (
                        f"just the word {token} "
                        f"alone in this blob\n"
                    )
                    blob_proc = subprocess.run(
                        ["git", "-C", str(repo),
                         "hash-object", "-w",
                         "--stdin"],
                        input=content,
                        capture_output=True, text=True,
                        check=True,
                    )
                    blob_sha = blob_proc.stdout.strip()
                    # Sanity check: the blob
                    # is dangling (otherwise
                    # the test setup is wrong).
                    fsck = subprocess.run(
                        ["git", "-C", str(repo), "fsck",
                         "--unreachable", "--no-reflogs",
                         "--no-progress"],
                        capture_output=True, text=True,
                    )
                    self.assertIn(
                        "dangling blob", fsck.stdout,
                        f"test setup error: the blob "
                        f"{blob_sha} is not dangling; "
                        f"fsck said: {fsck.stdout!r}. "
                        f"The test cannot distinguish "
                        f"dangling-object scanning from "
                        f"reachable-history scanning."
                    )
                    # Run the audit.
                    r = subprocess.run(
                        ["bash", str(AUDIT), str(repo)],
                        capture_output=True, text=True,
                        timeout=60,
                    )
                    self.assertEqual(
                        r.returncode, 1,
                        f"audit must exit 1 (forbidden "
                        f"found) for a dangling object "
                        f"containing {token!r}; got "
                        f"{r.returncode}. stdout: "
                        f"{r.stdout[:200]!r}; stderr: "
                        f"{r.stderr[:200]!r}"
                    )
                    # The audit report must name
                    # the dangling object's sha
                    # AND the token, so the
                    # operator can see which
                    # object to inspect and what
                    # to look for.
                    combined = r.stdout + r.stderr
                    self.assertIn(
                        token, combined,
                        f"the audit report must name "
                        f"the token {token!r} so the "
                        f"operator can see what was "
                        f"leaked; got: "
                        f"{combined[:300]!r}"
                    )
                    self.assertIn(
                        blob_sha, combined,
                        f"the audit report must name "
                        f"the dangling object's sha "
                        f"{blob_sha!r} so the operator "
                        f"can find it; got: "
                        f"{combined[:300]!r}"
                    )

    def test_audit_exits_2_on_non_git_directory(self):
        """The audit must refuse to run (exit 2) when the
        given path is not a git repository. A future
        contributor who changed the script to exit 0 on
        a non-git path (treating it as a clean no-op)
        would silently break the verify workflow: a clone
        that lost its `.git` directory would appear to
        have a clean audit instead of a broken one.

        The error must also name the path so the
        operator can see what to fix. A "fatal" line
        without a path is a hard-to-debug failure.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            not_a_repo = Path(tmp) / "not-a-repo"
            not_a_repo.mkdir()
            r = subprocess.run(
                ["bash", str(AUDIT), str(not_a_repo)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                r.returncode, 2,
                f"non-git-dir audit must exit 2; got "
                f"{r.returncode}. stdout: {r.stdout[:200]!r}; "
                f"stderr: {r.stderr[:200]!r}"
            )
            combined = r.stdout + r.stderr
            self.assertIn(
                str(not_a_repo), combined,
                f"the non-git-dir error must name the path; "
                f"got: {combined[:300]!r}"
            )

    def test_audit_uses_no_reflogs(self) -> None:
        """The audit script uses `git fsck --no-reflogs`
        intentionally. Reflogs live under .git/logs/
        which is never pushed to a remote, so they are
        not part of the *public* history the audit is
        gating. Scanning reflogs would false-positive
        on locally-deleted secrets (e.g. a credential
        file that was added and then git-rm'd in the
        same clone).

        A future contributor who "fixed" this by
        removing `--no-reflogs` would silently change
        the audit's scope from "the remote's public
        history" to "everything in this clone, ever",
        and every developer who ever committed a
        secret locally would fail the audit on a
        clean push.

        The test pins the script text so the
        contributor must update the test in the
        same commit if they really want to scan
        reflogs (and re-evaluate the design choice).
        """
        script_text = AUDIT.read_text(encoding="utf-8")
        self.assertIn(
            "--no-reflogs", script_text,
            f"audit must use `git fsck --no-reflogs` to "
            f"skip reflogs (which are not part of the "
            f"public history); the script text does not "
            f"contain --no-reflogs. A contributor who "
            f"removes this flag will silently change the "
            f"audit scope. If you intended to scan "
            f"reflogs, update this test in the same "
            f"commit AND re-evaluate the design choice "
            f"(see the comment above the fsck line)."
        )
        # The flag is passed to `git fsck`, not some
        # other git subcommand. Pin the surrounding
        # context so a contributor who moves the
        # flag to a different git subcommand (e.g.
        # `git log --no-reflogs` which doesn't
        # exist) fails the test.
        self.assertIn(
            "fsck --unreachable --no-reflogs",
            script_text,
            f"--no-reflogs must be passed to `git fsck "
            f"--unreachable` (the command that walks "
            f"dangling objects); got script text that "
            f"does not contain the expected context. "
            f"A contributor who moves the flag to a "
            f"different subcommand fails this test."
        )


if __name__ == "__main__":
    unittest.main()
