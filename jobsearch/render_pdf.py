"""Render the shortlist as a PDF the owner can read on a phone.

This is a DELIVERY tool, not a decision tool. It imports the gate from
`jobsearch.rules` and the row adapters from `jobsearch.notify`, so the PDF can
never disagree with the shortlist that M3 renders. It makes no judgements of its
own.

Rules this file obeys:

  * It renders only what is known. A description that was never retrieved says
    "not yet retrieved" -- the PDF never fills a gap to look complete.
  * Pay is reported, never invented, and never used to rank. When the posting
    does not state a number, the PDF says so instead of staying silent.
  * Every verdict carries its evidence: what was satisfied, what is uncertain,
    and the exact quoted requirement that failed.
  * A dropped job is not silently absent; the last page counts them and names
    them, so the filter can be judged.

reportlab is optional on purpose. The package's own dependency list stays at one
(PyYAML); if reportlab is missing this writes a plain-text version instead and
says so, rather than crashing a morning delivery.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

# package module: no sys.path manipulation needed

from jobsearch import notify  # noqa: E402
from jobsearch.rules import (  # noqa: E402
    NEEDS_RESEARCH,
    NOT_SUITABLE,
    POTENTIAL_MATCH,
    STRONG_MATCH,
    load_rules,
)

DEFAULT_DB = Path.home() / ".local" / "share" / "jobsearch" / "jobs.db"
DEFAULT_OUT = Path.home() / ".local" / "share" / "jobsearch" / "digests"

_LABEL = {
    STRONG_MATCH: "STRONG MATCH",
    POTENTIAL_MATCH: "POTENTIAL MATCH",
    NEEDS_RESEARCH: "NEEDS RESEARCH",
    NOT_SUITABLE: "GENERALLY UNSUITABLE",
}


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _remote(row: sqlite3.Row) -> str:
    return (row["remote"] or "arrangement not stated").strip()


def _pay(row: sqlite3.Row, verdict) -> str:
    """Pay, only as the posting states it. Silence is reported as silence."""
    if row["salary_text"]:
        return row["salary_text"].strip()
    sal = verdict.salary or {}
    if sal.get("parsed"):
        return f"{sal.get('amount')} {sal.get('currency')} (as stated in the posting)"
    if sal.get("raw"):
        return f"{sal['raw']}"
    return "not stated in the posting"


def _description_block(row: sqlite3.Row, chars: int) -> str:
    desc = (row["description"] or "").strip()
    if not desc:
        # Body only: callers add the "Description:" label, so it appears once.
        return "not yet retrieved (the posting page has not been read yet)."
    body = desc[:chars]
    if len(desc) > chars:
        body += f"\n[... {len(desc) - chars} more characters at the link above]"
    return body


def collect(db: Path, include_unsuitable: bool, limit: int | None):
    """Return (surfaced, dropped, stats) using the same gate as the digest."""
    rules = load_rules()
    con = _connect(db)
    already = notify.decided_job_ids(con)
    rows = con.execute(
        "SELECT * FROM jobs ORDER BY COALESCE(title, ''), id"
    ).fetchall()

    surfaced, dropped, not_judged = [], [], []
    for row in rows:
        if row["id"] in already:
            continue  # a decided job is never re-offered
        # W3.3 -- Coverage is printed, not implied. A posting
        # whose description has not been retrieved cannot be
        # judged. We route it to its own bucket and explain
        # why in the coverage line, instead of letting it
        # surface as a misleading `needs_research`.
        if (row["description_state"] or "") != "complete":
            not_judged.append((row, "description not yet retrieved"))
            continue
        verdict = notify.fit_for_row(row, rules)
        (surfaced if verdict.surface else dropped).append((row, verdict))

    # Rank by fit, never by pay: strong first, then potential, then research.
    order = {STRONG_MATCH: 0, POTENTIAL_MATCH: 1, NEEDS_RESEARCH: 2}
    surfaced.sort(key=lambda rv: (order.get(rv[1].outcome, 9), rv[0]["id"]))
    if limit:
        surfaced = surfaced[:limit]

    stats = {
        "read": len(rows),
        "surfaced": len(surfaced),
        "dropped": len(dropped),
        # W3.3: the four counts the reader needs. `read` is
        # every posting the digest saw. `with_description` is
        # every posting that came with a description, not
        # just the ones the gate surfaced. A reader who sees
        # "12 with a description, 5 not yet retrieved" knows
        # exactly which postings are awaiting a fetch. `not_judged`
        # is every posting the gate COULD NOT evaluate, with
        # the reason.
        "with_description": sum(
            1 for r, _ in (surfaced + dropped)
            if (r["description"] or "").strip()
        ),
        "not_judged": len(not_judged),
        "profile": rules.profile_path or "(none found — rules are empty defaults)",
        "generated": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
    }
    return surfaced, dropped, not_judged, stats, include_unsuitable


def _text_report(surfaced, dropped, not_judged, stats, include_unsuitable: bool,
                 desc_chars: int = 700) -> str:
    out = [
        f"JOB SHORTLIST — {stats['generated']}",
        # W3.3: the four counts the reader needs to see at a
        # glance. "not_judged" is the postings the gate could
        # not evaluate, separated from "surfaced" and "dropped"
        # so a reader does not see a misleading needs_research
        # for a posting whose description has not been read.
        f"{stats['read']} postings read · "
        f"{stats['with_description']} with a description retrieved · "
        f"{stats['not_judged']} not yet retrieved (no description) · "
        f"{stats['surfaced']} surfaced · {stats['dropped']} dropped",
        "",
    ]
    for i, (row, v) in enumerate(surfaced, 1):
        out += [
            f"[{i}] {row['title']}   ({_LABEL.get(v.outcome, v.outcome)})",
            f"    {row['company']} · {row['location']} · {_remote(row)}",
            f"    Pay: {_pay(row, v)}",
            f"    Link: {row['url']}",
            f"    Fits: {', '.join(v.satisfied[:4]) or '-'}",
            f"    Uncertain: {', '.join(v.uncertain[:4]) or '-'}",
            f"    Failed: {', '.join(v.failed_essential[:2]) or '-'}",
            # The PDF prints this; the text version must not silently differ.
            f"    Description: {_description_block(row, desc_chars)}",
            "",
        ]
    if include_unsuitable and dropped:
        out += ["DROPPED (counted, not hidden):"]
        for row, v in dropped:
            reason = (v.failed_essential or ["(see notes)"])[0]
            out.append(f"  - {row['title']} @ {row['company']}: {reason}")
    # W3.3: a not_judged posting is not a verdict -- the gate
    # never had a description to evaluate. Show it last, with
    # the reason, so the reader knows the next step is to
    # fetch the page, not to mark the job down.
    if not_judged:
        out += ["", "NOT YET RETRIEVED (no description to judge):"]
        for row, reason in not_judged:
            out.append(f"  - {row['title']} @ {row['company']}: {reason}")
            out.append(f"    Link: {row['url']}")
    return "\n".join(out)


def render_pdf(surfaced, dropped, not_judged, stats, include_unsuitable: bool,
               out: Path, desc_chars: int) -> Path:
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak,
                                    Paragraph, SimpleDocTemplate, Spacer)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=17, leading=21,
                        spaceAfter=2, alignment=TA_LEFT)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, leading=13,
                         textColor="#444444", spaceAfter=6)
    job = ParagraphStyle("job", parent=styles["Heading2"], fontSize=12.5,
                         leading=15, spaceBefore=10, spaceAfter=1)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=9,
                          leading=12.5, textColor="#333333")
    lab = ParagraphStyle("lab", parent=styles["Normal"], fontSize=9, leading=12,
                         textColor="#0b5cad")
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9,
                          leading=12.5)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8,
                           leading=11, textColor="#555555")

    def esc(value) -> str:
        return escape(str(value))

    def p(text: str, style=body) -> Paragraph:
        """Plain text: escaped here, so a job title can never inject markup."""
        return Paragraph(esc(text).replace("\n", "<br/>"), style)

    def pm(markup: str, style=body) -> Paragraph:
        """Our own markup. Every interpolated value must be esc()'d by the caller."""
        return Paragraph(markup.replace("\n", "<br/>"), style)

    flow = [
        p("Job shortlist", h1),
        # W3.3: the coverage line states the four counts
        # the reader needs to know whether the digest is
        # honest. A reader who sees "10 not yet retrieved"
        # knows the next step is to fetch the page, not to
        # mark the posting down.
        p(f"{stats['generated']} · {stats['read']} postings read · "
          f"{stats['with_description']} with a full description retrieved · "
          f"{stats['not_judged']} not yet retrieved (no description to judge) · "
          f"{stats['surfaced']} surfaced · {stats['dropped']} dropped", sub),
        p("Every job here passed the deterministic gate. Verdicts cite their "
          "evidence; uncertainty is shown as uncertainty. Nothing has been "
          "applied to, and nothing will be without your explicit approval for "
          "that one job.", small),
        HRFlowable(width="100%", thickness=0.6, color="#bbbbbb", spaceAfter=4),
    ]

    for i, (row, v) in enumerate(surfaced, 1):
        block = [
            pm(f"{i}. {esc(row['title'])}", job),
            pm(f"<b>{esc(row['company'] or 'company not stated')}</b> · "
               f"{esc(row['location'] or 'location not stated')} · {esc(_remote(row))}", meta),
            pm(f"<b>Verdict:</b> {esc(_LABEL.get(v.outcome, v.outcome))}", lab),
            pm(f"<b>Pay:</b> {esc(_pay(row, v))}", meta),
        ]
        if row["url"]:
            block.append(pm(f'<b>Link:</b> <link href="{esc(row["url"])}" color="#0b5cad">'
                            f'{esc(row["url"])}</link>', meta))
        if v.satisfied:
            block.append(pm(f"<b>Fits:</b> {esc('; '.join(v.satisfied[:5]))}", body))
        if v.uncertain:
            block.append(pm(f"<b>Needs checking:</b> {esc('; '.join(v.uncertain[:5]))}", body))
        if v.failed_essential:
            block.append(pm(f"<b>Failed:</b> {esc('; '.join(v.failed_essential[:3]))}", body))
        if v.notes:
            block.append(pm(f"<b>Notes:</b> {esc('; '.join(v.notes[:3]))}", small))
        block.append(p(f"Description: {_description_block(row, desc_chars)}", body))
        flow.append(KeepTogether(block))

    if include_unsuitable and dropped:
        flow.append(PageBreak())
        flow.append(p("Dropped by the gate (counted, never hidden)", h1))
        flow.append(p("These did not pass. They are listed so the filter itself "
                      "can be judged — a rule you disagree with shows up here.", sub))
        for row, v in dropped:
            reason = (v.failed_essential or ["(no quoted requirement — see notes)"])[0]
            flow.append(pm(f"<b>{esc(row['title'])}</b> — {esc(row['company'] or '?')}<br/>"
                           f"<font size=8 color='#777777'>{esc(reason)}</font>", small))

    # W3.3: not_judged is its own section, NOT a verdict. A
    # reader who sees this list knows the next step is to
    # fetch the description, not to evaluate a verdict the
    # gate never made.
    if not_judged:
        flow.append(PageBreak())
        flow.append(p("Not yet retrieved (no description to judge)", h1))
        flow.append(p("These postings had only a title when the digest "
                      "ran. The gate never saw a description to evaluate, "
                      "so no verdict was made. Fetch the page to add them "
                      "to tomorrow's digest.", sub))
        for row, reason in not_judged:
            link = (row['url'] or '').strip() or '(no link on file)'
            flow.append(pm(f"<b>{esc(row['title'])}</b> — {esc(row['company'] or '?')}<br/>"
                           f"<font size=8 color='#777777'>{esc(reason)}</font><br/>"
                           f"<font size=8 color='#0b5cad'>{esc(link)}</font>", small))

    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title="Job shortlist", author="jobsearch-pipeline",
    ).build(flow)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the shortlist as a PDF.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=None,
                    help="PDF path (default var/digests/jobsearch-<date>.pdf)")
    ap.add_argument("--limit", type=int, default=None, help="cap jobs listed")
    ap.add_argument("--desc-chars", type=int, default=700,
                    help="description characters per job")
    ap.add_argument("--include-unsuitable", action="store_true",
                    help="append the dropped jobs, with reasons, on a last page")
    ap.add_argument("--text", action="store_true",
                    help="write the plain-text version as well")
    args = ap.parse_args(argv)

    if not args.db.is_file():
        print(f"no ledger at {args.db}", file=sys.stderr)
        return 2

    surfaced, dropped, not_judged, stats, inc = collect(
        args.db, args.include_unsuitable, args.limit
    )
    stamp = datetime.now().strftime("%Y-%m-%d")
    out = args.out or (DEFAULT_OUT / f"jobsearch-{stamp}.pdf")

    try:
        render_pdf(surfaced, dropped, not_judged, stats, inc, out, args.desc_chars)
    except ImportError as exc:
        # Honest degradation: never fail a morning delivery over a renderer.
        out = out.with_suffix(".txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _text_report(surfaced, dropped, not_judged, stats, inc, args.desc_chars),
            encoding="utf-8",
        )
        print(f"PDF unavailable ({exc}); wrote text version instead: {out}")
        return 0

    print(f"{out}  ({stats['surfaced']} jobs surfaced, {stats['dropped']} dropped, "
          f"{stats['not_judged']} not yet retrieved, "
          f"{stats['with_description']} with descriptions)")
    if args.text:
        txt = out.with_suffix(".txt")
        txt.write_text(
            _text_report(surfaced, dropped, not_judged, stats, inc, args.desc_chars),
            encoding="utf-8",
        )
        print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
