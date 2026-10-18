# Third-Party Notices

This project includes vendored third-party code. The following files are
copied (with modifications) from upstream projects and are subject to
their original licenses.

## Nous Research — Google Workspace skill

- **Files:**
  - `tools/google/setup.py` (vendored copy)
  - `tools/google/_hermes_home.py` (vendored copy)
- **Upstream origin:** Nous Research Hermes Agent — `google-workspace` skill
- **Upstream repository:** https://github.com/NousResearch/hermes-agent
- **License:** MIT
- **Original copyright:** Copyright (c) 2025 Nous Research
- **Modifications:**
  - `setup.py`: Scope list narrowed to project requirements; adapted for standalone use without Hermes Agent runtime.
  - `_hermes_home.py`: Standalone fallback for HERMES_HOME resolution; no modifications to core logic.
- **Full license text:**

```
MIT License

Copyright (c) 2025 Nous Research

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Other dependencies

- **PyYAML** (>=6.0) — MIT License, Copyright (c) 2017-2021 Ingy döt Net, 2006-2016 Kirill Simonov
- **reportlab** (>=4.0, optional) — BSD License, Copyright (c) ReportLab Inc.

No other third-party code is vendored in this repository. All other files
under `jobsearch/`, `tests/`, `scripts/`, and `tools/` (except the
vendored Google Workspace files listed above) are original work.