"""Static HTML report for the job shortlist.

No backend, no login, no CDN: a single self-contained .html file that can be
opened in any browser offline. It reuses the same gate verdicts as the text
digest, so the two never disagree.

Usage:
    python3 -m jobsearch.render_html --db var/jobs.db --out var/digests/report.html
    python3 -m jobsearch.render_html --db var/jobs.db   # prints to stdout
"""
from __future__ import annotations

import argparse
import html as html_mod
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import db as db_mod
from .notify import (
    STRONG_MATCH,
    POTENTIAL_MATCH,
    NEEDS_RESEARCH,
    NOT_SUITABLE,
    _RANK,
    decided_job_ids,
    fit_for_row,
    load_rules,
)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"


def _esc(value) -> str:
    if value is None:
        return ""
    return html_mod.escape(str(value), quote=True)


def render_html(con: sqlite3.Connection, *, limit: int = 50, rules=None) -> str:
    rules = rules or load_rules()
    decided = decided_job_ids(con)
    rows = con.execute("SELECT * FROM jobs ORDER BY id").fetchall()

    surfaced = []
    dropped = 0
    for row in rows:
        if int(row["id"]) in decided:
            continue
        verdict = fit_for_row(row, rules)
        if not verdict.surface or verdict.outcome == NOT_SUITABLE:
            dropped += 1
            continue
        surfaced.append((row, verdict))

    surfaced.sort(key=lambda p: p[0]["last_seen_at"], reverse=True)
    surfaced.sort(key=lambda p: _RANK.get(p[1].outcome, 9))
    shown = surfaced[:limit]

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>Job shortlist — {_esc(stamp)}</title>")
    parts.append("<style>")
    parts.append(
        "body{font-family:system-ui,-apple-system,sans-serif;margin:24px;color:#1a1a1a;}"
        "h1{margin-bottom:4px;} .meta{color:#555;margin-bottom:16px;}"
        "table{border-collapse:collapse;width:100%;font-size:14px;}"
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top;}"
        "th{background:#f4f4f4;cursor:pointer;}"
        "tr:hover{background:#fafafa;}"
        ".strong{color:#1b7f3a;font-weight:600;}"
        ".potential{color:#1a5fb4;}"
        ".review{color:#8a6d00;}"
        ".link{word-break:break-all;}"
        "details{margin-top:4px;} summary{cursor:pointer;color:#555;}"
    )
    parts.append("</style></head><body>")
    parts.append(f"<h1>Job shortlist</h1>")
    parts.append(f'<p class="meta">{_esc(stamp)} · {len(shown)} of {len(surfaced)} shown · '
                 f'{len(decided)} already decided · {dropped} dropped as not suitable</p>')
    parts.append("<p>Nothing has been sent, applied to, or submitted. "
                 "Decisions are recorded with: <code>job &lt;id&gt; &lt;action&gt;</code></p>")

    if not shown:
        parts.append("<p>Nothing new to review.</p>")
    else:
        parts.append("<table id='jobs'><thead><tr>")
        parts.append("<th onclick=\"sortTable(0)\">ID</th>")
        parts.append("<th onclick=\"sortTable(1)\">Title</th>")
        parts.append("<th onclick=\"sortTable(2)\">Company</th>")
        parts.append("<th onclick=\"sortTable(3)\">Location</th>")
        parts.append("<th onclick=\"sortTable(4)\">Fit</th>")
        parts.append("<th>Link</th>")
        parts.append("</tr></thead><tbody>")
        for row, verdict in shown:
            job_id = int(row["id"])
            title = row["title"] or "(title not read from source)"
            company = row["company"] or "(company unknown)"
            loc = row["location"] or "(location not stated)"
            outcome = verdict.outcome
            cls = "strong" if outcome == STRONG_MATCH else ("potential" if outcome == POTENTIAL_MATCH else "review")
            why = "; ".join(verdict.satisfied[:3])
            gaps = "; ".join(verdict.uncertain[:3])
            parts.append("<tr>")
            parts.append(f"<td>{job_id}</td>")
            parts.append(f"<td>{_esc(title)}</td>")
            parts.append(f"<td>{_esc(company)}</td>")
            parts.append(f"<td>{_esc(loc)}</td>")
            parts.append(f"<td class='{cls}'>{_esc(outcome)}</td>")
            parts.append(f"<td class='link'><a href='{_esc(row['url'] or '')}' target='_blank' rel='noopener'>open</a></td>")
            parts.append("</tr>")
            parts.append("<tr><td colspan='6'>")
            parts.append(f"<details><summary>details</summary>")
            parts.append(f"<p><strong>Why:</strong> {_esc(why or 'no positive evidence')}</p>")
            parts.append(f"<p><strong>Gaps:</strong> {_esc(gaps or 'none outstanding')}</p>")
            parts.append(f"<p><strong>Salary:</strong> {_esc(row['salary_text'] or 'not published')}</p>")
            parts.append(f"<p><strong>Status:</strong> {_esc(row['status'])} · "
                         f"{'complete' if row['description_state']=='complete' else 'incomplete'} description</p>")
            parts.append("</details></td></tr>")
        parts.append("</tbody></table>")

    parts.append("<script>")
    parts.append(
        "function sortTable(n){var t=document.getElementById('jobs');"
        "var r=Array.from(t.tBodies[0].rows);"
        "r.sort(function(a,b){var x=a.cells[n].innerText,y=b.cells[n].innerText;"
        "return x<y?-1:x>y?1:0;});"
        "r.forEach(function(row){t.tBodies[0].appendChild(row);});}"
    )
    parts.append("</script>")
    parts.append("</body></html>")
    return "\n".join(parts)


def write_html(con, out_path, *, limit=50, rules=None):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(con, limit=limit, rules=rules), encoding="utf-8")
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the job shortlist as a self-contained HTML file.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args(argv)
    con = db_mod.connect(args.db)
    try:
        if args.out:
            path = write_html(con, args.out, limit=args.limit)
            print(f"wrote {path}")
        else:
            print(render_html(con, limit=args.limit))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
