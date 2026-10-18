"""Find likely duplicate jobs across sources for owner confirmation.

Prints groups of jobs whose normalized (title, company) are close, so the
owner can decide whether to merge them. Nothing is merged automatically: a
wrong merge loses a real posting, and that decision belongs to the owner.

Usage:
    python3 -m jobsearch.merge_candidates --db var/jobs.db
    python3 -m jobsearch.merge_candidates --threshold 0.8
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import db as db_mod

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "jobs.db"


def _norm(text):
    if not text:
        return ""
    return " ".join(text.lower().split())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    # Simple token-overlap (Jaccard) on words. Good enough as a suggestion.
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_candidates(con, threshold: float = 0.6):
    rows = con.execute(
        "SELECT id, title, company, url, status FROM jobs ORDER BY id"
    ).fetchall()
    groups: list[list] = []
    seen: set[int] = set()
    for i, a in enumerate(rows):
        if a["id"] in seen:
            continue
        cluster = [a]
        for b in rows[i + 1:]:
            if b["id"] in seen:
                continue
            key_a = _norm(a["title"]) + " " + _norm(a["company"])
            key_b = _norm(b["title"]) + " " + _norm(b["company"])
            if _similarity(key_a, key_b) >= threshold and key_a and key_b:
                cluster.append(b)
                seen.add(b["id"])
        if len(cluster) > 1:
            groups.append(cluster)
            for r in cluster:
                seen.add(r["id"])
    return groups


def main(argv=None):
    ap = argparse.ArgumentParser(description="Suggest duplicate job groups for owner review.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--threshold", type=float, default=0.6)
    args = ap.parse_args(argv)
    con = db_mod.connect(args.db)
    try:
        groups = find_candidates(con, args.threshold)
        if not groups:
            print("no likely duplicates found")
            return 0
        for idx, group in enumerate(groups, 1):
            print(f"\nGroup {idx}:")
            for r in group:
                print(f"  #{r['id']} [{r['status']}] {r['title']} @ {r['company']}")
                print(f"      {r['url']}")
        print(f"\n{len(groups)} group(s). Review and merge manually if appropriate.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
