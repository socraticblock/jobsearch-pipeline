"""M3 -- shortlist digest and owner decisions.

Two responsibilities, deliberately nothing else:

  1. RENDER what the M2 gate surfaced, honestly: what is known, what is
     uncertain, what is incomplete, and what was dropped.
  2. RECORD one decision per (job, action). A decision is a row keyed by
     (job_id, action) -- never inferred from free text, never generalised.

This module CANNOT send. It has no transport layer, no mail library, no HTTP
client, no Gmail code and no process spawn -- and its imports are allowlisted by
a test, so adding one fails the build rather than shipping a way to contact
someone from the module that decides what to contact them about.

Delivery is a separate agent step reading the rendered file -- the same
discipline as `twitter-jobs`, where cron writes a digest and an agent delivers.

Policy this module encodes (owner rules, see HANDOFF.md section 6):

  * A job with any decision is NEVER re-notified.
  * Approval means "approve to prepare", never authorisation to submit.
  * A hard-failed job (surface=False) is never rendered at all -- only counted,
    so the owner can see that something was dropped without it re-entering the
    shortlist by accident.
  * Uncertainty is shown as uncertainty. Nothing is filled in to look complete.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db as db_mod
from .requirements import JobPosting
from .rules import (
    NEEDS_RESEARCH,
    NOT_SUITABLE,
    POTENTIAL_MATCH,
    STRONG_MATCH,
    Verdict,
    describe,
    evaluate,
    load_rules,
)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "digests"

# Closed action vocabulary. Anything else is a programming error, not a decision.
ACTION_APPROVE = "approve"
ACTION_REJECT = "reject"
ACTION_RESEARCH = "research"
ACTION_SAVE = "save"
ACTIONS = (ACTION_APPROVE, ACTION_REJECT, ACTION_RESEARCH, ACTION_SAVE)

# What each action does, printed next to the digest so the meaning is never
# guessed from the word.
ACTION_MEANING = {
    ACTION_APPROVE: "prepare this one (NOT authorisation to submit)",
    ACTION_REJECT: "drop it",
    ACTION_RESEARCH: "look deeper (company, people, salary, scope)",
    ACTION_SAVE: "park it for later",
}

# Fit ranking: what the owner should read first.
_RANK = {STRONG_MATCH: 0, POTENTIAL_MATCH: 1, NEEDS_RESEARCH: 2, NOT_SUITABLE: 3}


class DecisionError(ValueError):
    """A decision that must not be silently accepted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def posting_from_row(row: sqlite3.Row) -> JobPosting:
    """Build a JobPosting from a ledger row.

    Empty/NULL columns stay empty -- never substituted with a guess. A NULL
    title becomes the empty string, which the gate then treats as no evidence.
    """
    return JobPosting(
        title=row["title"] or "",
        company=row["company"] or "",
        description=row["description"] or "",
        url=row["url"] or "",
        location=row["location"] or "",
        remote=row["remote"],
        salary_text=row["salary_text"],
    )


def fit_for_row(row: sqlite3.Row, rules) -> Verdict:
    return evaluate(posting_from_row(row), rules)


def current_decision(con: sqlite3.Connection, job_id: int) -> str | None:
    """The most recent decision for a job, or None."""
    row = con.execute(
        "SELECT action FROM decisions WHERE job_id=? "
        "ORDER BY decided_at DESC, id DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    return row["action"] if row else None


def decided_job_ids(con: sqlite3.Connection) -> set[int]:
    rows = con.execute("SELECT DISTINCT job_id FROM decisions").fetchall()
    return {int(r["job_id"]) for r in rows}


def record_decision(
    con: sqlite3.Connection,
    job_id: int,
    action: str,
    *,
    note: str | None = None,
    actor: str = "owner",
    now: str | None = None,
) -> dict:
    """Record one decision, bound to exactly one job.

    Idempotent per (job_id, action): recording the same action twice leaves one
    row and reports `recorded: False`. A DIFFERENT action for the same job is a
    new row (a change of mind is history worth keeping), and the digest reads
    the latest as the job's status.
    """
    if action not in ACTIONS:
        raise DecisionError(
            f"unknown action {action!r}; expected one of {', '.join(ACTIONS)}"
        )
    exists = con.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not exists:
        raise DecisionError(
            f"no job with id {job_id}: a decision cannot be recorded against an "
            "id that is not in the ledger"
        )

    prior = con.execute(
        "SELECT id FROM decisions WHERE job_id=? AND action=?", (job_id, action)
    ).fetchone()
    if prior:
        return {"recorded": False, "already": True, "job_id": job_id, "action": action}

    con.execute(
        "INSERT INTO decisions(job_id, action, decided_at, actor, note) "
        "VALUES (?,?,?,?,?)",
        (job_id, action, now or _now(), actor, note),
    )
    con.commit()
    return {"recorded": True, "already": False, "job_id": job_id, "action": action}


_COMMAND = re.compile(
    r"^\s*/?(?:job\s*)?#?(?P<job_id>\d+)\s+(?P<action>[a-z_]+)\s*$", re.I
)


def parse_decision_command(text: str) -> tuple[int, str]:
    """Parse the plain-text fallback protocol: `job 42 approve`.

    Accepted: `job 42 approve`, `/job 42 approve`, `42 approve`, `#42 reject`.
    Anything else raises -- an ambiguous command must never resolve to a
    decision against the wrong job.
    """
    m = _COMMAND.match(text or "")
    if not m:
        raise DecisionError(
            f"could not read a decision from {text!r}; expected '<job id> "
            f"<action>' with action one of {', '.join(ACTIONS)}"
        )
    action = m.group("action").casefold()
    if action not in ACTIONS:
        raise DecisionError(
            f"unknown action {action!r}; expected one of {', '.join(ACTIONS)}"
        )
    return int(m.group("job_id")), action


def apply_decision_command(
    con: sqlite3.Connection, text: str, *, note: str | None = None
) -> dict:
    """Parse and record in one step. Refuses an id that is not in the ledger."""
    job_id, action = parse_decision_command(text)
    return record_decision(con, job_id, action, note=note)


def _source_line(con: sqlite3.Connection, job_id: int) -> str:
    row = con.execute(
        "SELECT s.name AS name, g.seen_at AS seen_at FROM sightings g "
        "JOIN sources s ON s.id = g.source_id WHERE g.job_id=? "
        "ORDER BY g.seen_at DESC, g.id DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    if not row:
        return "source unknown"
    return f"{row['name']} @ {row['seen_at']}"


def _fit_label(verdict: Verdict) -> str:
    bucket = "shortlist" if verdict.outcome in (STRONG_MATCH, POTENTIAL_MATCH) else "review"
    return f"{bucket} ({describe(verdict)})"


def _why_bullets(verdict: Verdict) -> list[str]:
    """Cited reasons to look. Empty when the gate found no positive evidence."""
    return list(verdict.satisfied[:4])


def _gap_bullets(verdict: Verdict) -> list[str]:
    """Uncertainty first (the thing to verify), then soft failures."""
    gaps = list(verdict.uncertain)
    gaps += [f"did not meet (soft, still surfaced): {f}" for f in verdict.failed_essential]
    return gaps


def _red_flags(row: sqlite3.Row, verdict: Verdict) -> list[str]:
    flags = list(verdict.hard_avoid)
    if row["description_state"] != "complete":
        flags.append("description incomplete")
    salary = verdict.salary
    # The currency the floor is denominated in comes from the profile, so this
    # line reads in the owner's own currency instead of the one it was written in.
    cur = salary.get("floor_currency") or ""
    if not row["salary_text"]:
        flags.append("no salary published")
    elif salary.get("vs_floor") == "below_floor":
        flags.append(
            f"salary quoted at {salary.get('amount')}{' ' + cur if cur else ''}, "
            "below the net floor"
        )
    elif salary.get("vs_floor") == "needs_conversion":
        flags.append(
            f"salary in {salary.get('currency')} -- convert to "
            f"{cur or 'the floor currency'} net before "
            "comparing (no rate is invented here)"
        )
    elif salary.get("vs_floor") == "unknown":
        flags.append("salary text present but no amount could be read")
    return flags


def render_job(con: sqlite3.Connection, row: sqlite3.Row, verdict: Verdict) -> str:
    """One job block, in the shape agreed in design/M3-approval.md."""
    job_id = int(row["id"])
    title = row["title"] or "(title not read from source)"
    company = row["company"] or "(company unknown)"
    loc = row["location"] or "(location not stated)"
    remote = row["remote"] or "remote policy unknown"
    salary = row["salary_text"] or "not published"

    lines = [f"#{job_id}  {title} — {company}"]
    lines.append(f"Location: {loc} · {remote}       Salary: {salary}")
    lines.append(f"Fit: {_fit_label(verdict)}")
    lines.append(f"Source: {_source_line(con, job_id)}")

    why = _why_bullets(verdict)
    if why:
        lines.append("Why:")
        lines += [f"  - {b}" for b in why]
    else:
        lines.append("Why: no positive evidence found yet (see gaps)")

    gaps = _gap_bullets(verdict)
    lines.append("Gaps:" + ("" if gaps else " none outstanding"))
    lines += [f"  - {g}" for g in gaps]

    flags = _red_flags(row, verdict)
    lines.append("Red flags:" + ("" if flags else " none"))
    lines += [f"  - {f}" for f in flags]

    if row["description_state"] == "complete":
        lines.append("Description: complete")
    else:
        reason = verdict.notes[0] if verdict.notes else "not retrieved"
        lines.append(f"Description: incomplete — {reason}")

    lines.append(f"Link: {row['url'] or 'not captured'}")
    lines.append(f"Status: {current_decision(con, job_id) or 'new'}")
    return "\n".join(lines)


def render_digest(
    con: sqlite3.Connection,
    *,
    limit: int = 10,
    rules=None,
    now: str | None = None,
    notes: list[str] | None = None,
) -> str:
    """Render the owner-facing shortlist.

    Only `new` jobs the gate chose to surface. Decided jobs are excluded (never
    re-notified); hard-dropped jobs are excluded and reported as a count only.
    """
    rules = rules or load_rules()
    if getattr(rules, "profile_path", None) is None:
        # A missing profile would otherwise be invisible: the gate would simply
        # treat every technology as unknown and the owner would read the results
        # as real verdicts. Say it plainly instead.
        notes = [
            "no candidate profile found — no technology or language can be "
            "treated as held. Copy profile/profile.example.yaml to "
            "profile/profile.yaml and fill it in, or point the JOBSEARCH_PROFILE "
            "environment variable at your own file."
        ] + list(notes or [])
    decided = decided_job_ids(con)
    rows = con.execute("SELECT * FROM jobs ORDER BY id").fetchall()

    surfaced, dropped = [], 0
    for row in rows:
        if int(row["id"]) in decided:
            continue
        verdict = fit_for_row(row, rules)
        if not verdict.surface or verdict.outcome == NOT_SUITABLE:
            dropped += 1
            continue
        surfaced.append((row, verdict))

    # Rank by fit, then newest sighting first (stable two-pass sort).
    surfaced.sort(key=lambda p: p[0]["last_seen_at"], reverse=True)
    surfaced.sort(key=lambda p: _RANK.get(p[1].outcome, 9))
    shown = surfaced[:limit]

    stamp = now or _now()
    out = [
        f"Job shortlist — {stamp}",
        f"{len(shown)} of {len(surfaced)} surfaced job(s) shown "
        f"(limit {limit}); {len(decided)} already decided and not repeated; "
        f"{dropped} dropped as not suitable.",
        "",
        "Nothing has been sent, applied to, or submitted. Decisions are recorded "
        "with: job <id> <action>",
        "",
    ]
    if not shown:
        out.append("Nothing new to review.")
    for row, verdict in shown:
        out.append(render_job(con, row, verdict))
        out.append("")
    if notes:
        out.append("Notes:")
        out += [f"  - {n}" for n in notes]
        out.append("")
    out.append("Actions: " + " · ".join(
        f"{a} = {ACTION_MEANING[a]}" for a in ACTIONS
    ))
    return "\n".join(out).rstrip() + "\n"


def write_digest(
    con: sqlite3.Connection,
    out_dir: str | Path = DEFAULT_OUT,
    *,
    limit: int = 10,
    rules=None,
    now: str | None = None,
    notes: list[str] | None = None,
) -> Path:
    """Write the digest to a file. This is the ONLY output path: an agent step
    delivers it. Never overwrites an existing digest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or _now()).replace(":", "").replace("-", "")
    path = out_dir / f"digest-{stamp}.txt"
    if path.exists():
        raise DecisionError(f"refusing to overwrite an existing digest: {path}")
    path.write_text(
        render_digest(con, limit=limit, rules=rules, now=now, notes=notes),
        encoding="utf-8",
    )
    return path


def _run(args) -> int:
    if args.cmd == "decide":
        con = db_mod.connect(args.db)
        try:
            res = apply_decision_command(con, " ".join(args.decision), note=args.note)
        finally:
            con.close()
        if res["already"]:
            print(f"already recorded: job {res['job_id']} {res['action']}")
        else:
            print(f"recorded: job {res['job_id']} {res['action']}")
        return 0

    con = db_mod.connect(args.db)
    try:
        if args.out:
            path = write_digest(con, args.out, limit=args.limit)
            print(f"wrote {path}")
        else:
            print(render_digest(con, limit=args.limit), end="")
    finally:
        con.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="M3: render the job shortlist, or record one decision"
    )
    sub = ap.add_subparsers(dest="cmd")

    p_render = sub.add_parser("render", help="render the shortlist digest")
    p_render.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_render.add_argument("--out", type=Path, default=None,
                          help="write to this directory (default: print to stdout)")
    p_render.add_argument("--limit", type=int, default=10)

    p_decide = sub.add_parser("decide", help="record one decision: '<id> <action>'")
    p_decide.add_argument("decision", nargs="+")
    p_decide.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_decide.add_argument("--note", default=None)

    args = ap.parse_args(argv)
    try:
        return _run(args)
    except DecisionError as exc:
        # A refused decision must read as a refusal, not a crash -- this
        # protocol may be typed by hand from a phone.
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
