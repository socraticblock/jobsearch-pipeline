#!/usr/bin/env python3
"""Render the job shortlist as a self-contained HTML file (no backend, no login)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch.render_html import main

if __name__ == "__main__":
    raise SystemExit(main())
