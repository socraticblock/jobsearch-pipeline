"""Unified command-line entry point for the jobsearch pipeline.

    jobsearch fetch [--source NAME] [--db PATH]
    jobsearch onboard --cv CV [--preferences PREFS] [--out PATH]
    jobsearch doctor
    jobsearch first-run [--run-dir DIR]
    jobsearch ingest DIR [--db PATH]
    jobsearch enrich [--limit N] [--spacing S] [--db PATH]
    jobsearch render [--db PATH] [--out PATH]

Every subcommand delegates to the existing module so behaviour stays identical
to `python3 -m jobsearch.<module>` / `python3 tools/<tool>.py`.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_module(module: str, argv: list[str]) -> int:
    sys.argv = [module] + argv
    runpy.run_module(module, run_name="__main__")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobsearch", description="Local-first job search assistant.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch account-free job sources")
    p_fetch.add_argument("--db", type=Path, default=None)
    p_fetch.add_argument("--source", action="append", choices=["remoteok", "remotive", "arbeitnow", "hn_hiring"])
    p_fetch.add_argument("--timeout", type=int, default=30)

    p_onboard = sub.add_parser("onboard", help="CV + preferences -> profile/profile.yaml")
    p_onboard.add_argument("--cv", type=Path, required=True)
    p_onboard.add_argument("--preferences", type=Path, default=None)
    p_onboard.add_argument("--out", type=Path, default=None)

    sub.add_parser("doctor", help="check preconditions (requires repository checkout)")
    p_fr = sub.add_parser("first-run", help="offline walkthrough (requires repository checkout)")
    p_fr.add_argument("--run-dir", type=Path, default=None)

    p_ing = sub.add_parser("ingest", help="ingest a maildir")
    p_ing.add_argument("email_dir", type=Path)
    p_ing.add_argument("--db", type=Path, default=None)

    p_mc = sub.add_parser("merge-candidates", help="suggest duplicate job groups")
    p_mc.add_argument("--db", type=Path, default=None)
    p_mc.add_argument("--threshold", type=float, default=0.6)

    p_cs = sub.add_parser("check-status", help="re-check open job URLs, mark expired")
    p_cs.add_argument("--db", type=Path, default=None)
    p_cs.add_argument("--limit", type=int, default=20)
    p_cs.add_argument("--spacing", type=float, default=1.0)
    p_cs.add_argument("--job-id", type=int, default=None)
    p_cs.add_argument("--dry-run", action="store_true")

    p_en = sub.add_parser("enrich", help="fetch job descriptions")
    p_en.add_argument("--db", type=Path, default=None)
    p_en.add_argument("--limit", type=int, default=3)
    p_en.add_argument("--spacing", type=float, default=45.0)
    p_en.add_argument("--job-id", type=int, default=None)
    p_en.add_argument("--dry-run", action="store_true")
    p_en.add_argument("--resume", action="store_true")
    p_en.add_argument("--queue-path", type=Path, default=None)

    p_rh = sub.add_parser("render-html", help="render the shortlist as HTML")
    p_rh.add_argument("--db", type=Path, default=None)
    p_rh.add_argument("--out", type=Path, default=None)
    p_rh.add_argument("--limit", type=int, default=50)

    p_re = sub.add_parser("render", help="render the shortlist")
    p_re.add_argument("--db", type=Path, default=None)
    p_re.add_argument("--out", type=Path, default=None)
    p_re.add_argument("--include-unsuitable", action="store_true")
    p_re.add_argument("--text", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        from . import fetch as f

        db = args.db or f.DEFAULT_DB
        sources = args.source if args.source else None
        argv2 = ["--db", str(db), "--timeout", str(args.timeout)]
        if sources:
            for s in sources:
                argv2 += ["--source", s]
        return f.main(argv2)
    if args.cmd == "onboard":
        from . import onboard as m

        argv2 = ["--cv", str(args.cv)]
        if args.preferences:
            argv2 += ["--preferences", str(args.preferences)]
        if args.out:
            argv2 += ["--out", str(args.out)]
        return m.main(argv2)
    if args.cmd == "doctor":
        tool_path = ROOT / "tools" / "doctor.py"
        if not tool_path.is_file():
            print("jobsearch doctor requires a repository checkout.",
                  "Clone the repository to run this command:",
                  "  git clone https://github.com/socraticblock/jobsearch-pipeline.git",
                  file=sys.stderr)
            return 2
        sys.argv = ["doctor"]
        runpy.run_path(str(tool_path), run_name="__main__")
        return 0
    if args.cmd == "first-run":
        if not (ROOT / "fixtures" / "first_run").is_dir():
            print("first-run needs the shipped sample data (fixtures/first_run/), which is",
                  "not included in the pip install. Clone the repository instead:",
                  "  git clone <repository-url> && cd jobsearch",
                  "  python3 tools/first_run.py", sep="\n", file=sys.stderr)
            return 2
        argv2 = []
        if args.run_dir:
            argv2 += ["--run-dir", str(args.run_dir)]
        sys.argv = ["first_run"] + argv2
        runpy.run_path(str(ROOT / "tools" / "first_run.py"), run_name="__main__")
        return 0
    if args.cmd == "ingest":
        from . import ingest as m

        db = args.db or m.DEFAULT_DB
        return m.main([str(args.email_dir), "--db", str(db)])
    if args.cmd == "merge-candidates":
        from . import merge_candidates as m

        db = args.db or m.DEFAULT_DB
        return m.main(["--db", str(db), "--threshold", str(args.threshold)])
    if args.cmd == "check-status":
        from . import check_status as m

        db = args.db or m.DEFAULT_DB
        argv2 = ["--db", str(db), "--limit", str(args.limit), "--spacing", str(args.spacing)]
        if args.job_id is not None:
            argv2 += ["--job-id", str(args.job_id)]
        if args.dry_run:
            argv2 += ["--dry-run"]
        return m.main(argv2)
    if args.cmd == "enrich":
        from . import enrich as m

        db = args.db or m.DEFAULT_DB
        argv2 = ["--db", str(db), "--limit", str(args.limit), "--spacing", str(args.spacing)]
        if args.job_id is not None:
            argv2 += ["--job-id", str(args.job_id)]
        if args.dry_run:
            argv2 += ["--dry-run"]
        if args.resume:
            argv2 += ["--resume"]
        if args.queue_path is not None:
            argv2 += ["--queue-path", str(args.queue_path)]
        return m.main(argv2)
    if args.cmd == "render-html":
        from . import render_html as m

        db = args.db or m.DEFAULT_DB
        argv2 = ["--db", str(db), "--limit", str(args.limit)]
        if args.out:
            argv2 += ["--out", str(args.out)]
        return m.main(argv2)
    if args.cmd == "render":
        from . import render_pdf as m

        db = args.db or m.DEFAULT_DB
        argv2 = ["--db", str(db)]
        if args.out:
            argv2 += ["--out", str(args.out)]
        if args.include_unsuitable:
            argv2 += ["--include-unsuitable"]
        if args.text:
            argv2 += ["--text"]
        return m.main(argv2)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
