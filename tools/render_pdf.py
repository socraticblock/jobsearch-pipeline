#!/usr/bin/env python3
"""Compatibility wrapper: re-exports jobsearch.render_pdf."""
import sys
from jobsearch.render_pdf import *  # noqa: F401, F403
import jobsearch.render_pdf as _rp
# Re-export private helpers that tests reference
for _attr in dir(_rp):
    if _attr.startswith("_") and not _attr.startswith("__"):
        globals()[_attr] = getattr(_rp, _attr)
from jobsearch.render_pdf import main
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
