"""The first run — see the whole pipeline work, offline, in one command.

The demo (`tools/demo_sieve.py --batch`) proves the *gate* on the shipped
corpus. This tool proves the *pipeline*: an alert email becomes ledger rows,
those rows become postings with descriptions, and the postings become the
shortlist digest you would actually read.

Why it exists. An alert email carries a title, a company, a location and a
link -- never a description. So a newcomer who ingests the shipped alert
fixtures and renders sees "description incomplete (0 chars)" on every job and
reasonably concludes the tool is broken. It is not broken: it is waiting for
enrichment (M4), and this tool shows that next state on shipped synthetic
data, with no mailbox, no Google account, no profile of your own and no
network call of any kind.

What is real here:
  * `jobsearch.ingest` parses the .eml (the real parser).
  * `jobsearch.enrich.enrich_one` extracts the description and sets
    `description_state` (the real enrichment step; only the byte source is
    swapped -- a file on disk instead of one HTTP GET).
  * `jobsearch.rules` judges each posting (the real gate).
  * `jobsearch.notify.render_digest` renders the shortlist (the real output).

What is synthetic: `fixtures/first_run/` -- one sample alert email, three
sample posting pages, one sample profile. Invented employers, invented
people, no address that resolves.

The tool never reads or writes the real ledger (`var/jobs.db`). It builds its
own throwaway ledger under `var/first-run/`, which holds nothing but
regenerable copies of the shipped fixtures.

Usage:
    python3 tools/first_run.py
    python3 tools/first_run.py --run-dir /tmp/first-run

Exit codes: 0 the walkthrough ran | 1 a precondition failed | 2 bad usage.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import db as db_mod  # noqa: E402
from jobsearch import enrich as enrich_mod  # noqa: E402
from jobsearch import ingest as ingest_mod  # noqa: E402
from jobsearch.notify import render_digest  # noqa: E402
from jobsearch.rules import load_rules  # noqa: E402

SAMPLES = ROOT / "fixtures" / "first_run"
DEFAULT_RUN_DIR = ROOT / "var" / "first-run"

# How many postings the sample enrichment pass will look at. The sample ships
# four jobs; the cap only stops a runaway loop if a future sample is larger.
ENRICH_LIMIT = 50

RULE = "=" * 70


def _heading(text: str) -> None:
    print()
    print(RULE)
    print(text)
    print(RULE)


def _load_doctor():
    """Load `tools/doctor.py` the way `tools/doctor.py` loads other tools:
    by path, because `tools/` is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "first_run_doctor", ROOT / "tools" / "doctor.py"
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # Register before executing: `@dataclass` resolves the defining module
    # through `sys.modules[cls.__module__]`, so a module that is executed but
    # never registered raises AttributeError on its first dataclass.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def preconditions() -> bool:
    """Run the doctor's checks. Print only what is missing, plus its fix.

    The doctor is the same one `python3 tools/doctor.py` runs; the point of
    running it here is that a fresh reader gets the failures and the fixes
    before a wall of pipeline output, not after it.
    """
    _heading("Step 0/4 — preconditions")
    doctor = _load_doctor()
    if doctor is None:
        print("  [FAIL] tools/doctor.py could not be loaded from this checkout.")
        print("         fix: the file is part of the repo; check git status")
        return False
    checks = doctor._all_checks()  # noqa: SLF001 -- same-repo tool, by design
    failed = [c for c in checks if not c.passed]
    if not failed:
        print(f"  all {len(checks)} preconditions met")
        return True
    for check in failed:
        print(check.render())
    print()
    print(f"  {len(failed)} precondition(s) unmet. Fix the items above and "
          f"run this command again.")
    return False


def fresh_run_dir(path: Path) -> Path:
    """Recreate the throwaway ledger directory.

    Only this tool's own namespace is removed, and everything in it is a
    regenerable copy built from `fixtures/first_run/`. The real ledger
    (`var/jobs.db`) and every digest under `var/digests/` are never opened.
    """
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_page_fetcher(pages_dir: Path):
    """The sample's byte source for `enrich_one`.

    In production the fetcher is `jobsearch.enrich.fetch_html`, which performs
    one HTTP GET of the LinkedIn guest page. Here the bytes come from a
    shipped synthetic page on disk, so the walkthrough runs offline. Everything
    downstream -- the markup extraction, the description-state transition, the
    "never guess a description" rule -- is the production code.
    """

    def fetch(url: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", url or "")
        if not match:
            raise enrich_mod.FetchError(
                f"no shipped sample page for {url!r}"
            )
        page = pages_dir / f"{match.group(1)}.html"
        if not page.is_file():
            raise enrich_mod.FetchError(
                f"no shipped sample page for {url!r}"
            )
        try:
            return page.read_text(encoding="utf-8")
        except OSError as exc:
            raise enrich_mod.FetchError(f"cannot read {page}: {exc}") from exc

    return fetch


def _describe_enrichment(con) -> None:
    """Print what each job's description state is now, and why."""
    rows = con.execute(
        "SELECT id, title, description_state, description FROM jobs ORDER BY id"
    ).fetchall()
    print("  job  state        chars  title")
    for row in rows:
        chars = len(row["description"] or "")
        print(
            f"  #{row['id']:<3} {str(row['description_state'] or '?'):<12} "
            f"{chars:>5}  {(row['title'] or '(no title)')[:44]}"
        )


def run(run_dir: Path) -> int:
    pages_dir = SAMPLES / "pages"
    mailbox = SAMPLES / "mailbox"
    sample_profile = SAMPLES / "profile.sample.yaml"
    for required in (mailbox, pages_dir, sample_profile):
        if not required.exists():
            print(f"FAIL: shipped sample missing: {required.relative_to(ROOT)}")
            print("      the sample is part of the repo; check git status")
            return 2

    fresh_run_dir(run_dir)
    db_path = run_dir / "jobs.db"
    con = db_mod.connect(db_path)
    try:
        # 1. Ingest: the real alert-email parser, into the throwaway ledger.
        _heading("Step 1/4 — ingest the sample alert email")
        totals = ingest_mod.ingest_directory(
            con, mailbox, source_kind="email_alert"
        )
        print(f"  files read : {totals['files']}")
        print(f"  skipped    : {totals['skipped']}")
        print(f"  new jobs   : {totals['new_jobs']}")
        print(f"  ledger now : {totals['unique_jobs']} job(s) in {db_path.name}")
        print()
        print("  An alert email carries a title, a company, a location and a")
        print("  link. It does not carry a description -- so at this point")
        print("  every job is incomplete, exactly as your own inbox would be.")

        # 2. Enrich: the real enrichment step, one page at a time.
        _heading("Step 2/4 — enrich (the step that supplies descriptions)")
        fetcher = local_page_fetcher(pages_dir)
        pending = enrich_mod._pending(con, ENRICH_LIMIT, None)  # noqa: SLF001
        done = no_page = 0
        for row in pending:
            try:
                result = enrich_mod.enrich_one(con, row, fetcher=fetcher)
            except enrich_mod.FetchError:
                # Production would make one HTTP attempt here and stop on
                # failure; a failure is never recorded as "no description".
                no_page += 1
                print(
                    f"  #{row['id']:<3} no sample page shipped -> stays "
                    f"incomplete (production: one fetch attempt, then "
                    f"needs_research if it fails)"
                )
                continue
            if result["state"] == "complete":
                done += 1
            print(
                f"  #{result['job_id']:<3} state={result['state']} "
                f"chars={result['chars']}"
                + ("  (clamped guest view -- may be partial)"
                   if result["clamped"] else "")
            )
        print()
        print(f"  descriptions stored: {done} of {len(pending)} pending job(s); "
              f"{no_page} with no sample page")
        print()
        _describe_enrichment(con)

        # 3. Judge + render: the real gate and the real digest.
        _heading("Step 3/4 — the shortlist digest (the real output)")
        rules = load_rules(sample_profile)
        print(render_digest(con, limit=10, rules=rules))

        # 4. What just happened, and what is different on your machine.
        _heading("Step 4/4 — what you just saw, and what comes next")
        print("Real code paths: the alert parser, the enrichment step, the")
        print("deterministic gate, and the digest renderer. The postings,")
        print("employers and profile are synthetic, and no network call was")
        print("made -- the posting pages were read from disk.")
        print()
        print("Two things the digest is telling you on purpose:")
        print("  * A verdict carries the quoted requirement behind it. No")
        print("    quote, no failure.")
        print("  * A posting with no description is NEEDS_RESEARCH, not a")
        print("    rejection. The gate refuses to judge what it cannot read.")
        print()
        print("Two things the digest tells you about pay. #1 and #2 show the")
        print("posting's own pay line, because those pages state one. #2's 2,800")
        print("EUR is below the sample profile's 6,000 EUR floor, so it is")
        print("flagged -- and the job is still rendered: compensation ranks and")
        print("flags, it never rejects. #4 states no figure, so it reads 'not")
        print("published'. The field is filled from the posting, never guessed.")
        print()
        print("A second one, closed this week: the EU job's location line now")
        print("reads \"work authorisation declared for this scope (eu)\". It says")
        print("that because the sample profile declares it, and for no other")
        print("reason -- delete the work_authorisation list and the same job")
        print("becomes \"location scope to verify\" instead. The gate no longer")
        print("infers a work authorisation from citizenship or from a country")
        print("named in a posting.")
        print()
        print("On your own data, the same three commands are:")
        print("  1. cp profile/profile.example.yaml profile/profile.yaml")
        print("     $EDITOR profile/profile.yaml      # your stack, floor, market")
        print("  2. python3 -m jobsearch.ingest <maildir> --db var/jobs.db")
        print("  3. python3 -m jobsearch.enrich --limit 5   # one fetch per job")
        print("     python3 -m jobsearch.notify render --db var/jobs.db")
        print()
        try:
            shown = db_path.relative_to(ROOT)
        except ValueError:
            # --run-dir may point outside the checkout (the suite does).
            shown = db_path
        print(f"This run's throwaway ledger: {shown}")
        print("Your real ledger (var/jobs.db) was not read or written.")
        return 0
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="See the jobsearch pipeline run end to end on shipped "
                    "synthetic data, offline: ingest -> enrich -> gate -> "
                    "shortlist digest."
    )
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR,
                    help="where to build the throwaway ledger "
                         f"(default: {DEFAULT_RUN_DIR})")
    args = ap.parse_args(argv)

    print("jobsearch — first run")
    if not preconditions():
        return 1
    return run(args.run_dir)


if __name__ == "__main__":
    sys.exit(main())
