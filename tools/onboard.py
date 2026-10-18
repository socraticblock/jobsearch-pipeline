#!/usr/bin/env python3
"""Compatibility wrapper: re-exports jobsearch.onboard."""
import sys
from jobsearch.onboard import *  # noqa: F401, F403
from jobsearch.onboard import main
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
