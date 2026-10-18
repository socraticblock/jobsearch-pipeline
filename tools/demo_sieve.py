"""Interactive demo of the sieve.

A small command-line tool that takes a posting (from a corpus
fixture id, from a JSON file, or from stdin) and prints the
gate's verdict, the satisfied signals, the failed essentials, the
uncertain items, the notes, the salary comparison, and the
why-strings of every rule that fired.

The point is the same as career-ops' walk-through shape: a
reader who has not seen the gate run can run it once and
understand what the verdict means. The doc shapes (CLAIMS.md,
COMPARISON.md, UNKNOWN_POLICY.md) describe the contract; this
tool is the executable proof.

Usage:
    python3 tools/demo_sieve.py --corpus-id c-001
    python3 tools/demo_sieve.py --json path/to/posting.json
    python3 tools/demo_sieve.py --stdin
    # then type the title (line 1), body (rest), and Ctrl-D
    python3 tools/demo_sieve.py --list

The tool is the I-07 deliverable. It does not perform any
network I/O. It is shipped with the bundle as a
reference-able artifact for a reader who wants to see the
sieve work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import rules as rules_module  # noqa: E402
from jobsearch import rule_why  # noqa: E402
from jobsearch.requirements import JobPosting, extract  # noqa: E402


CORPUS_V1 = ROOT / "corpus" / "v1" / "postings.json"

# A default profile for the demo. The point is to show the
# sieve's behaviour; the profile is illustrative, not a real
# candidate's data.
DEFAULT_PROFILE = {
    "known_stack": ["python", "go", "django", "postgres", "aws"],
    "learnable_stack": ["rust", "elixir", "kotlin"],
    "floor_net": 4000,
    "floor_currency": "EUR",
    "local_ok": ["samplecity", "anothercity"],
    "languages_usable": ["english"],
    "years_can_honestly_claim": 5,
    # The demo's illustrative candidate may work in the EU. Declared, not
    # inferred: without this list an EU-scope posting is NEEDS_RESEARCH
    # (missing evidence), which is the point of the work_authorisation field.
    "work_authorisation": ["eu"],
}


def _load_corpus() -> list[dict]:
    if not CORPUS_V1.exists():
        return []
    return json.loads(CORPUS_V1.read_text(encoding="utf-8"))


def _postings_for_id(record: dict) -> JobPosting:
    profile = record.get("profile", DEFAULT_PROFILE)
    posting = JobPosting(
        title=record["title"],
        description=record["body"],
        location=record.get("location", "remote"),
    )
    return posting, profile


def _evaluate(posting: JobPosting, profile: dict) -> rules_module.Verdict:
    # One builder for the dict-shaped profile, shared with the corpus runner,
    # so a new profile field cannot reach one caller and miss the other.
    rules = rules_module.rules_from_profile(profile)
    extract(
        posting,
        extra_terms=rules.known_stack | rules.learnable_stack,
        extra_languages=rules.languages_usable,
    )
    return rules_module.evaluate(posting, rules), rules


def _render(verdict: rules_module.Verdict, rules: rules_module.Rules,
            record: dict | None) -> str:
    out: list[str] = []
    out.append("=" * 64)
    out.append(f"VERDICT: {verdict.outcome}")
    out.append(f"  (surface: {verdict.surface}, hard_failure: {verdict.hard_failure})")
    out.append("=" * 64)
    if record:
        out.append(f"corpus id     : {record.get('id', '?')}")
        out.append(f"rule          : {record.get('rule', '?')}")
        out.append(f"expected      : {record.get('expect', '?')}")
    if record:
        out.append(f"posting title : {record.get('title', '?')}")
        out.append(f"posting body  : {record.get('body', '?')[:200]}"
                   + ("..." if len(record.get("body", "")) > 200 else ""))
    out.append("")
    if verdict.satisfied:
        out.append("SATISFIED:")
        for s in verdict.satisfied:
            out.append(f"  + {s}")
        out.append("")
    if verdict.failed_essential:
        out.append("FAILED ESSENTIALS:")
        for f in verdict.failed_essential:
            out.append(f"  ! {f}")
        out.append("")
    if verdict.uncertain:
        out.append("UNCERTAIN (W3.1: needs_research, not a fabricated verdict):")
        for u in verdict.uncertain:
            out.append(f"  ? {u}")
        out.append("")
    if verdict.notes:
        out.append("NOTES:")
        for n in verdict.notes:
            out.append(f"  - {n}")
        out.append("")
    if verdict.salary.get("parsed"):
        s = verdict.salary
        out.append("SALARY:")
        out.append(f"  stated  : {s.get('amount')} {s.get('currency')}")
        out.append(f"  floor   : {rules.floor_net} {rules.floor_currency}")
        out.append(f"  vs_floor: {s.get('vs_floor', 'unknown')}")
        if s.get("note"):
            out.append(f"  note    : {s['note']}")
        out.append("")
    if verdict.hard_avoid:
        out.append("HARD AVOID (W6.x: title-level reject):")
        for a in verdict.hard_avoid:
            out.append(f"  X {a}")
        out.append("")
    out.append("WHY (per the rule_why registry):")
    # Find the why string for this fixture's rule, if any.
    rule_key = (record or {}).get("rule", "")
    if rule_key and rule_key in rule_why.WHY:
        out.append(f"  {rule_why.WHY[rule_key]}")
    else:
        out.append("  (no rule_why entry for this verdict)")
    out.append("")
    return "\n".join(out)


def _list_corpus() -> None:
    records = _load_corpus()
    print(f"corpus/v1/postings.json has {len(records)} fixtures:")
    for r in records:
        print(f"  {r.get('id', '?'):>5}  expect={r.get('expect', '?'):<16}  "
              f"rule={r.get('rule', '?'):<32}  {r.get('title', '?')[:40]}")


def _batch_digest() -> str:
    """Run the gate on every corpus fixture and produce a
    digest-style summary. This is the W5.3 deliverable: a
    one-command proof the gate works, with no Google setup,
    no .eml files, no profile editing required. Borrowed
    shape: career-ops' walk-through."""
    records = _load_corpus()
    if not records:
        return (
            f"corpus at {CORPUS_V1.relative_to(ROOT)} is empty or missing."
        )
    out: list[str] = []
    from collections import Counter
    counts: Counter[str] = Counter()
    lines: list[str] = []
    for r in records:
        posting, profile, record = _from_corpus_id(r["id"])
        verdict, _ = _evaluate(posting, profile)
        counts[verdict.outcome] += 1
        ok = "ok" if verdict.outcome == r.get("expect") else "DRIFT"
        line = (
            f"  {r.get('id', '?'):>5}  "
            f"verdict={verdict.outcome:<16} "
            f"expect={r.get('expect', '?'):<16} "
            f"[{ok}]  "
            f"{r.get('title', '?')[:42]}"
        )
        lines.append(line)
    total = len(records)
    surfaced = counts.get("strong_match", 0) + counts.get("potential_match", 0)
    needs_research = counts.get("needs_research", 0)
    not_suitable = counts.get("not_suitable", 0)
    out.append("=" * 70)
    out.append(f"jobsearch batch demo  —  {total} fixtures evaluated")
    out.append("=" * 70)
    out.append("")
    out.append(f"  shortlist  (strong_match + potential_match): {surfaced}")
    out.append(f"  needs_research (gate flagged, not a drop)   : {needs_research}")
    out.append(f"  not_suitable (rejected, reason cited)       : {not_suitable}")
    out.append("")
    out.append("Per-fixture verdict (ok = verdict matches expect; DRIFT = drift):")
    for line in lines:
        out.append(line)
    out.append("")
    n_drift = sum(1 for r in records
                  if _evaluate(*_from_corpus_id(r["id"])[:2])[0].outcome
                  != r.get("expect"))
    out.append(f"Drift: {n_drift}/{total} fixtures have verdict != expect.")
    if n_drift > 0:
        out.append("A non-zero drift is a build failure. See tests/test_"
                   "corpus_end_to_end.py.")
    out.append("")
    out.append("Why this is the W5.3 demo:")
    out.append("  * No .eml files needed.")
    out.append("  * No Google credentials needed.")
    out.append("  * No profile editing needed (each fixture carries its own profile).")
    out.append("  * Reads only corpus/v1/postings.json, which ships with the repo.")
    out.append("  * Same gate the production pipeline uses.")
    out.append("")
    return "\n".join(out)


def _from_stdin() -> tuple[JobPosting, dict]:
    print("Enter the posting. First line: title. Remaining lines: body.")
    print("End the body with a line containing only '.'.")
    print()
    lines = sys.stdin.readlines()
    if not lines:
        print("stdin was empty", file=sys.stderr)
        sys.exit(2)
    title = lines[0].rstrip("\n")
    body_lines: list[str] = []
    for line in lines[1:]:
        if line.rstrip("\n") == ".":
            break
        body_lines.append(line.rstrip("\n"))
    body = "\n".join(body_lines).strip()
    return (
        JobPosting(title=title, description=body, location="remote"),
        DEFAULT_PROFILE,
    )


def _from_json(path: Path) -> tuple[JobPosting, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = data.get("profile", DEFAULT_PROFILE)
    return (
        JobPosting(
            title=data["title"],
            description=data["body"],
            location=data.get("location", "remote"),
        ),
        profile,
    )


def _from_corpus_id(cid: str) -> tuple[JobPosting, dict, dict]:
    records = _load_corpus()
    match = next((r for r in records if r.get("id") == cid), None)
    if not match:
        print(f"corpus id {cid!r} not found in {CORPUS_V1.relative_to(ROOT)}",
              file=sys.stderr)
        print("run with --list to see available ids", file=sys.stderr)
        sys.exit(2)
    posting, profile = _postings_for_id(match)
    return posting, profile, match


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run the jobsearch sieve on a posting and print the verdict."
    )
    ap.add_argument("--corpus-id", help="evaluate the corpus fixture with this id")
    ap.add_argument("--json", type=Path, help="evaluate a posting from a JSON file")
    ap.add_argument("--stdin", action="store_true",
                    help="read the posting from stdin (title on line 1, body after)")
    ap.add_argument("--list", action="store_true",
                    help="list the available corpus fixtures and exit")
    ap.add_argument("--batch", action="store_true",
                    help="run the gate on every corpus fixture and print a "
                         "digest-style summary. This is the W5.3 "
                         "credential-free demo: no .eml files, no Google "
                         "setup, no profile editing. Reads only "
                         "corpus/v1/postings.json.")
    args = ap.parse_args(argv)

    if args.list:
        _list_corpus()
        return 0

    if args.batch:
        print(_batch_digest())
        return 0

    record: dict | None = None
    if args.corpus_id:
        posting, profile, record = _from_corpus_id(args.corpus_id)
    elif args.json:
        try:
            posting, profile = _from_json(args.json)
        except FileNotFoundError:
            # Caller error: the user passed a path
            # that does not exist. Same exit code
            # as the other caller-error paths
            # (stdin empty, unknown corpus id).
            print(
                f"json input file {args.json!r} does not exist",
                file=sys.stderr,
            )
            return 2
        except json.JSONDecodeError as e:
            # Caller error: the file exists but
            # is not valid JSON. Print a friendly
            # error naming the file and the parse
            # position, not a stack trace.
            print(
                f"json input file {args.json!r} is not valid "
                f"JSON: {e.msg} (line {e.lineno} column {e.colno})",
                file=sys.stderr,
            )
            return 2
        except KeyError as e:
            # Caller error: the JSON is valid but
            # missing a required field (title or
            # body). Print which field is missing
            # and how to see the expected schema.
            print(
                f"json input file {args.json!r} is missing "
                f"required field {e!s} (the demo sieve "
                f"needs at least 'title' and 'body')",
                file=sys.stderr,
            )
            return 2
    elif args.stdin:
        posting, profile = _from_stdin()
    else:
        # Default: run c-001 (the canonical missing-evidence case).
        posting, profile, record = _from_corpus_id("c-001")
        print("(no input given; defaulting to corpus c-001 -- "
              "the canonical missing-evidence case)")
        print()

    verdict, rules = _evaluate(posting, profile)
    print(_render(verdict, rules, record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
