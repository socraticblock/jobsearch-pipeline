"""M3 acceptance tests: shortlist rendering and job-bound decisions.

Run:  python3 -m unittest discover -s tests -v
      python3 -O -m unittest discover -s tests      # must behave IDENTICALLY

unittest assertion methods only, never bare `assert` -- see tests/test_m1.py.

The acceptance tests from design/M3-approval.md section 6 are named here
verbatim as test names:
  * a_decision_mutates_exactly_the_row_for_its_job
  * a_decided_job_is_never_re_notified
  * an_approval_for_one_job_is_not_replayable_against_another
  * with_no_decisions_the_digest_lists_only_new_jobs
"""

from __future__ import annotations

import ast
import contextlib
import io
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import db as db_mod                                    # noqa: E402
from jobsearch import notify                                          # noqa: E402
from jobsearch.ingest import ingest_directory                         # noqa: E402
from jobsearch.rules import load_rules, evaluate                      # noqa: E402

FIXTURES = ROOT / "fixtures"
# The suite reads its OWN synthetic profile, never the developer's -- otherwise
# a stranger's test run fails on someone else's salary floor.
FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "test_profile.yaml"
NOTIFY_SRC = (ROOT / "jobsearch" / "notify.py").read_text(encoding="utf-8")

STRONG_DESC = (
    "We are looking for an AI Automation Engineer to join our team. Remote "
    "within the EU. You will build automations with TypeScript, React and "
    "Node.js. Salary 8000 EUR per month."
)
BELOW_FLOOR_DESC = (
    "Full-Stack Engineer. Remote within the EU. TypeScript, React and Node.js "
    "required. Salary 3000 EUR per month."
)
FOREIGN_DESC = (
    "Full-Stack Engineer. Remote within the EU. TypeScript and React required. "
    "Compensation in USD."
)
IOS_DESC = "iOS Developer. Build Swift applications. Remote worldwide. Swift and Kotlin required."


def digest_ids(text: str) -> set[int]:
    """Job ids actually rendered as blocks (`#12  Title ...`)."""
    return {int(m) for m in re.findall(r"^#(\d+)\s", text, re.MULTILINE)}


class M3Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "jobs.db"
        self.con = db_mod.connect(self.db_path)
        self.rules = load_rules(FIXTURE_PROFILE)

    def tearDown(self):
        self.con.close()
        self._tmp.cleanup()

    def add_job(
        self,
        *,
        title: str,
        company: str = "Acme",
        description: str | None = None,
        state: str = "incomplete",
        location: str = "Remote (EU)",
        remote: str | None = "remote",
        salary_text: str | None = None,
    ) -> int:
        now = "2026-10-13T00:00:00+00:00"
        cur = self.con.execute(
            "INSERT INTO jobs(dedupe_key,title,company,location,remote,url,description,"
            "description_state,salary_text,status,first_seen_at,last_seen_at,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'open',?,?,?,?)",
            (
                f"test:{title}:{abs(hash(description or ''))}", title, company, location,
                remote, "https://example.invalid/j", description, state, salary_text,
                now, now, now, now,
            ),
        )
        self.con.commit()
        return int(cur.lastrowid)

    def ingest_fixtures(self) -> None:
        ingest_directory(self.con, FIXTURES)

    def digest(self, **kw) -> str:
        return notify.render_digest(self.con, rules=self.rules, **kw)


class TestDecisionCommand(unittest.TestCase):
    def test_fallback_command_forms_all_parse(self):
        for text, expected in (
            ("job 42 approve", (42, "approve")),
            ("/job 42 approve", (42, "approve")),
            ("42 reject", (42, "reject")),
            ("#42 save", (42, "save")),
            ("  job   7   research  ", (7, "research")),
            ("JOB 7 APPROVE", (7, "approve")),
        ):
            with self.subTest(text=text):
                self.assertEqual(notify.parse_decision_command(text), expected)

    def test_unknown_action_is_refused(self):
        with self.assertRaises(notify.DecisionError):
            notify.parse_decision_command("42 apply")

    def test_ambiguous_text_is_refused(self):
        for text in ("", "approve", "42", "job 42", "42 approve and submit",
                     "maybe job 42 approve"):
            with self.subTest(text=text):
                with self.assertRaises(notify.DecisionError):
                    notify.parse_decision_command(text)

    def test_action_vocabulary_is_closed(self):
        self.assertEqual(
            set(notify.ACTIONS), {"approve", "reject", "research", "save"}
        )


class TestDecisions(M3Base):
    def test_a_decision_mutates_exactly_the_row_for_its_job(self):
        a = self.add_job(title="AI Automation Engineer")
        b = self.add_job(title="Full-Stack Engineer")
        before = self.con.execute(
            "SELECT updated_at, status FROM jobs WHERE id=?", (b,)
        ).fetchone()

        res = notify.record_decision(self.con, a, "approve")
        self.assertTrue(res["recorded"])

        rows = self.con.execute("SELECT job_id FROM decisions").fetchall()
        self.assertEqual([int(r["job_id"]) for r in rows], [a])
        self.assertIsNone(notify.current_decision(self.con, b))
        after = self.con.execute(
            "SELECT updated_at, status FROM jobs WHERE id=?", (b,)
        ).fetchone()
        self.assertEqual((before["updated_at"], before["status"]),
                         (after["updated_at"], after["status"]))

    def test_repeating_the_same_action_records_once(self):
        a = self.add_job(title="AI Automation Engineer")
        first = notify.record_decision(self.con, a, "save")
        second = notify.record_decision(self.con, a, "save")
        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertTrue(second["already"])
        count = self.con.execute(
            "SELECT COUNT(*) c FROM decisions WHERE job_id=?", (a,)
        ).fetchone()["c"]
        self.assertEqual(count, 1)

    def test_changing_a_decision_keeps_history_and_latest_wins(self):
        a = self.add_job(title="AI Automation Engineer")
        notify.record_decision(self.con, a, "approve", now="2026-10-13T09:00:00+00:00")
        notify.record_decision(self.con, a, "reject", now="2026-10-13T10:00:00+00:00")
        self.assertEqual(notify.current_decision(self.con, a), "reject")
        count = self.con.execute(
            "SELECT COUNT(*) c FROM decisions WHERE job_id=?", (a,)
        ).fetchone()["c"]
        self.assertEqual(count, 2)

    def test_unknown_action_is_refused_at_write_time(self):
        a = self.add_job(title="AI Automation Engineer")
        with self.assertRaises(notify.DecisionError):
            notify.record_decision(self.con, a, "submit")
        self.assertEqual(
            self.con.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"], 0
        )

    def test_an_approval_for_one_job_is_not_replayable_against_another(self):
        a = self.add_job(title="AI Automation Engineer")
        self.add_job(title="Full-Stack Engineer")
        notify.apply_decision_command(self.con, f"job {a} approve")
        # A job id that is not in the ledger must be refused, not created.
        with self.assertRaises(notify.DecisionError):
            notify.apply_decision_command(self.con, "job 9999 approve")
        rows = self.con.execute("SELECT job_id FROM decisions").fetchall()
        self.assertEqual([int(r["job_id"]) for r in rows], [a])

    def test_foreign_key_still_holds_in_the_schema(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute(
                "INSERT INTO decisions(job_id, action, decided_at) "
                "VALUES (4242, 'approve', '2026-10-13T00:00:00+00:00')"
            )


class TestDigest(M3Base):
    def test_with_no_decisions_the_digest_lists_only_new_jobs(self):
        self.ingest_fixtures()
        text = self.digest()
        ids = digest_ids(text)
        self.assertEqual(len(ids), 10)
        self.assertIn("0 already decided", text)
        for line in re.findall(r"^Status: (.+)$", text, re.MULTILINE):
            self.assertEqual(line, "new")

    def test_a_decided_job_is_never_re_notified(self):
        self.ingest_fixtures()
        before = digest_ids(self.digest())
        target = sorted(before)[0]
        notify.record_decision(self.con, target, "approve")

        after = digest_ids(self.digest())
        self.assertNotIn(target, after)
        self.assertEqual(after, before - {target})
        self.assertIn("1 already decided and not repeated", self.digest())

        # The decision is still readable on the job itself, even though the
        # digest no longer repeats it.
        row = self.con.execute("SELECT * FROM jobs WHERE id=?", (target,)).fetchone()
        block = notify.render_job(self.con, row, notify.fit_for_row(row, self.rules))
        self.assertIn("Status: approve", block)

    def test_hard_failed_job_is_never_rendered_only_counted(self):
        self.ingest_fixtures()
        ios = self.add_job(title="iOS Developer", description=IOS_DESC,
                           state="complete", salary_text=None)
        text = self.digest()
        self.assertNotIn(ios, digest_ids(text))
        self.assertIn("1 dropped as not suitable", text)

    def test_digest_never_overstates_an_incomplete_description(self):
        self.ingest_fixtures()
        text = self.digest()
        self.assertIn("Description: incomplete", text)
        self.assertNotIn("Description: complete", text)

    def test_digest_renders_a_retrieved_description_as_a_shortlist_fit(self):
        job = self.add_job(title="AI Automation Engineer", description=STRONG_DESC,
                           state="complete", salary_text="8000 EUR per month")
        text = self.digest()
        self.assertIn(job, digest_ids(text))
        self.assertIn("shortlist (STRONG MATCH)", text)
        self.assertIn("Why:", text)
        self.assertIn("Description: complete", text)
        self.assertNotIn("description incomplete", text)

    def test_salary_below_floor_is_flagged_but_never_rejects(self):
        job = self.add_job(title="Full-Stack Engineer", description=BELOW_FLOOR_DESC,
                           state="complete", salary_text="3000 EUR per month")
        text = self.digest()
        self.assertIn(job, digest_ids(text))
        self.assertIn("below the net floor", text)

    def test_foreign_currency_is_flagged_without_inventing_a_rate(self):
        job = self.add_job(title="Full-Stack Engineer", description=FOREIGN_DESC,
                           state="complete", salary_text="USD 90000 per year")
        text = self.digest()
        self.assertIn(job, digest_ids(text))
        self.assertIn("salary in USD", text)
        self.assertIn("no rate is invented here", text)

    def test_fit_ranking_puts_the_strongest_first(self):
        self.add_job(title="Needs Research Backend Engineer", description=None)
        self.add_job(title="AI Automation Engineer", description=STRONG_DESC,
                     state="complete", salary_text="8000 EUR per month")
        text = self.digest()
        order = [int(i) for i in re.findall(r"^#(\d+)\s", text, re.MULTILINE)]
        self.assertEqual(len(order), 2)
        strong = self.con.execute(
            "SELECT id FROM jobs WHERE title='AI Automation Engineer'"
        ).fetchone()["id"]
        self.assertEqual(order[0], int(strong))

    def test_limit_is_reported_honestly(self):
        self.ingest_fixtures()
        text = self.digest(limit=3)
        self.assertEqual(len(digest_ids(text)), 3)
        self.assertIn("3 of 10 surfaced job(s) shown", text)

    def test_digest_states_that_nothing_was_sent_or_submitted(self):
        self.ingest_fixtures()
        text = self.digest()
        self.assertIn("Nothing has been sent, applied to, or submitted.", text)

    def test_approve_is_described_as_prepare_not_submit(self):
        self.ingest_fixtures()
        text = self.digest()
        self.assertIn("approve = prepare this one (NOT authorisation to submit)", text)

    def test_write_digest_writes_a_file_and_refuses_to_overwrite(self):
        self.ingest_fixtures()
        out = Path(self._tmp.name) / "digests"
        path = notify.write_digest(self.con, out, rules=self.rules,
                                   now="2026-10-13T12:00:00+00:00")
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent, out)
        self.assertIn("Job shortlist", path.read_text(encoding="utf-8"))
        with self.assertRaises(notify.DecisionError):
            notify.write_digest(self.con, out, rules=self.rules,
                                now="2026-10-13T12:00:00+00:00")


class TestCli(M3Base):
    """The CLI is the fallback path a human types, so it must fail legibly."""

    def test_cli_refuses_an_unknown_job_without_a_traceback(self):
        self.add_job(title="AI Automation Engineer")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = notify.main(
                ["decide", "9999", "approve", "--db", str(self.db_path)]
            )
        self.assertEqual(rc, 2)
        self.assertIn("refused:", err.getvalue())
        self.assertIn("no job with id 9999", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_cli_refuses_an_unknown_action_without_a_traceback(self):
        self.add_job(title="AI Automation Engineer")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = notify.main(["decide", "1", "apply", "--db", str(self.db_path)])
        self.assertEqual(rc, 2)
        self.assertIn("refused:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_cli_decide_reports_recorded_then_already(self):
        job = self.add_job(title="AI Automation Engineer")
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            rc1 = notify.main(["decide", str(job), "approve", "--db", str(self.db_path)])
            rc2 = notify.main(["decide", str(job), "approve", "--db", str(self.db_path)])
        self.assertEqual([rc1, rc2], [0, 0])
        text = capture.getvalue()
        self.assertIn(f"recorded: job {job} approve", text)
        self.assertIn(f"already recorded: job {job} approve", text)

    def test_cli_render_writes_one_digest_file(self):
        self.ingest_fixtures()
        outdir = Path(self._tmp.name) / "digests"
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            rc = notify.main(
                ["render", "--db", str(self.db_path), "--out", str(outdir),
                 "--limit", "5"]
            )
        self.assertEqual(rc, 0)
        files = sorted(outdir.glob("digest-*.txt"))
        self.assertEqual(len(files), 1)
        self.assertIn("5 of 10 surfaced job(s) shown", files[0].read_text(encoding="utf-8"))


class TestNoSendCapability(unittest.TestCase):
    """M3 renders and records. It must have no way to contact anyone.

    Enforced structurally, not by wording: the module's imports are allowlisted,
    so a future transport import fails the build rather than shipping quietly.
    """

    INERT_STDLIB = {"__future__", "argparse", "re", "sqlite3", "datetime", "pathlib", "sys"}
    LOCAL_MODULES = {"db", "normalize", "parse_alert", "requirements", "rules", "ingest"}
    OUTBOUND_VERBS = r"^(send|submit|transmit|deliver|dispatch)"

    @staticmethod
    def _imports(src: str) -> tuple[set[str], set[str]]:
        absolute: set[str] = set()
        relative: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    absolute.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.module:
                        relative.add(node.module.split(".")[0])
                    else:
                        # `from . import x as y` has module=None
                        for alias in node.names:
                            relative.add(alias.name.split(".")[0])
                elif node.module:
                    absolute.add(node.module.split(".")[0])
        return absolute, relative

    @staticmethod
    def _dotted_names(src: str) -> set[str]:
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                names.add(f"{node.value.id}.{node.attr}")
        return names

    def test_notify_imports_only_inert_stdlib_and_local_modules(self):
        absolute, relative = self._imports(NOTIFY_SRC)
        self.assertEqual(absolute - self.INERT_STDLIB, set())
        self.assertEqual(relative - self.LOCAL_MODULES, set())

    def test_no_process_spawn_or_filesystem_escape(self):
        banned = {
            n for n in self._dotted_names(NOTIFY_SRC)
            if n.startswith(("os.", "subprocess.", "socket.", "shutil."))
        }
        self.assertEqual(banned, set())

    def test_notify_defines_no_outbound_function(self):
        names = re.findall(r"^def (\w+)", NOTIFY_SRC, re.MULTILINE)
        senders = [n for n in names if re.match(self.OUTBOUND_VERBS, n)]
        self.assertEqual(senders, [], f"notify.py defines an outbound function: {senders}")

    def test_module_has_no_bare_assert(self):
        self.assertIsNone(re.search(r"^\s*assert\s", NOTIFY_SRC, re.MULTILINE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
