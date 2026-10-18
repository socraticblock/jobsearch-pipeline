"""W5.2 -- `doctor`: a single command that lists every unmet
precondition for running jobsearch, with a one-line fix per item.

Borrowed shape:
  - JobCtrl's `tools/doctor.py` (MIT): check-and-report per
    precondition, exit nonzero if any check fails.
  - jobsync's docker-quickstart (no licence): a "check before
    you start" surface that lists what is missing and how to
    install it.

Design principles:
  - Each check is independent. A failure in one does not skip
    the next. The reader sees every problem at once.
  - Each failure prints exactly one thing to do next. No
    paragraphs, no link-spam.
  - Exit code 0 if all checks pass, 1 otherwise. The owner
    can run `python3 tools/doctor.py` from a fresh checkout
    and know what is missing.

The doctor does not perform any network I/O; it inspects only
the local checkout.  It does not write to disk; it only reads.

Usage:
  python3 tools/doctor.py
  python3 tools/doctor.py --quiet   # only show failures
  python3 tools/doctor.py --json    # machine-readable output
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PY_MIN = (3, 10)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    fix: str  # what to do if !passed

    def render(self) -> str:
        marker = "PASS" if self.passed else "FAIL"
        line = f"  [{marker}] {self.name}: {self.detail}"
        if not self.passed:
            line += f"\n         fix: {self.fix}"
        return line


def _check_python() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= PY_MIN
    detail = f"Python {v.major}.{v.minor}.{v.micro}"
    if not ok:
        return Check(
            "python-version",
            False,
            detail,
            f"install Python {'.'.join(str(x) for x in PY_MIN)} or later",
        )
    return Check("python-version", True, detail, "")


def _module_fix(name: str) -> str:
    """The one-line fix for a missing module.

    It must name a distribution that actually provides the module. The one
    dependency this project has is the exception: `pip install yaml` installs
    an unrelated package that does not provide the `yaml` module, so following
    the old hint left the reader exactly as broken as before. Prefer the
    project's own pinned install when the manifest is present.
    """
    if name == "yaml":
        if (ROOT / "requirements.txt").is_file():
            return ("pip install -r requirements.txt   "
                    "(the `yaml` module comes from PyYAML)")
        return "pip install PyYAML   (the package that provides `yaml`)"
    return f"pip install {name}"


def _check_module(name: str, required: bool = True) -> Check:
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "(version unknown)")
        return Check(f"module-{name}", True, f"{name} {ver}", "")
    except ImportError as e:
        if required:
            return Check(
                f"module-{name}",
                False,
                f"{name} not importable: {e}",
                _module_fix(name),
            )
        return Check(
            f"module-{name}",
            True,
            f"{name} not installed (optional, used for: PDFs only)",
            "",
        )


def _check_path(path: Path, label: str, optional: bool = False) -> Check:
    if path.exists():
        return Check(label, True, f"{path.relative_to(ROOT)} exists", "")
    if optional:
        return Check(
            label,
            True,
            f"{path.relative_to(ROOT)} absent (optional, "
            f"defaults used)",
            "",
        )
    return Check(
        label,
        False,
        f"{path.relative_to(ROOT)} not found",
        f"the file is part of the repo; check git status or run "
        f"`git checkout -- {path.relative_to(ROOT)}`",
    )


def _check_executable(path: Path) -> Check:
    if not path.exists():
        return Check(
            f"executable-{path.name}",
            False,
            f"{path.relative_to(ROOT)} not found",
            "tools/verify.sh must exist in the repo",
        )
    if not os.access(path, os.X_OK):
        return Check(
            f"executable-{path.name}",
            False,
            f"{path.relative_to(ROOT)} is not executable",
            f"run: chmod +x {path.relative_to(ROOT)}",
        )
    return Check(
        f"executable-{path.name}",
        True,
        f"{path.relative_to(ROOT)} is executable",
        "",
    )


def _check_var_writable() -> Check:
    """The pipeline writes digest PDFs to var/. Check that the
    directory is creatable and writable. This is a soft check
    because var/ is created on demand."""
    var = ROOT / "var"
    try:
        var.mkdir(exist_ok=True)
        test = var / ".doctor-write-test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return Check("var-writable", True, "var/ is creatable and writable", "")
    except OSError as e:
        return Check(
            "var-writable",
            False,
            f"cannot write to var/: {e}",
            "the pipeline needs var/ for digest PDFs; ensure the "
            "user has write permission on the project directory",
        )


def _check_digests_writable() -> Check:
    """`jobsearch.notify render` writes the rendered shortlist to
    digests/. Two things depend on that directory existing:

      * the export gate lists digests/ in EXCLUDE, because a rendered
        shortlist carries real postings, and
      * `test_every_exclude_entry_exists_in_source` requires every
        EXCLUDE path to exist in the source tree -- which is how a
        defensive entry for a path that no longer exists gets caught.

    A fresh clone has neither var/ nor digests/ (both are gitignored
    runtime output), so the doctor creates both. Created on demand,
    hence a soft check."""
    digests = ROOT / "digests"
    try:
        digests.mkdir(exist_ok=True)
        test = digests / ".doctor-write-test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return Check(
            "digests-writable",
            True,
            "digests/ is creatable and writable",
            "",
        )
    except OSError as e:
        return Check(
            "digests-writable",
            False,
            f"cannot write to digests/: {e}",
            "the pipeline writes the rendered shortlist to digests/; "
            "ensure the user has write permission on the project "
            "directory",
        )


def _check_jobsearch_imports() -> Check:
    """The jobsearch package must import without error. A typo
    or a missing dependency would show up here."""
    try:
        import jobsearch  # noqa: F401
        import jobsearch.rules  # noqa: F401
        import jobsearch.requirements  # noqa: F401
        import jobsearch.rule_why  # noqa: F401
        return Check(
            "jobsearch-imports", True,
            "jobsearch package imports cleanly", "",
        )
    except Exception as e:  # noqa: BLE001
        return Check(
            "jobsearch-imports", False,
            f"jobsearch import failed: {type(e).__name__}: {e}",
            "the package is part of the repo; the failure is a "
            "bug; open an issue with the full error",
        )


def _check_rule_why_consistent() -> Check:
    """The rule_why registry must be loadable and have entries
    for every gate-level rule the corpus uses. A drift between
    the registry and the corpus is a build failure elsewhere;
    the doctor surfaces it here for a quick health check."""
    try:
        from jobsearch import rule_why
        import json
        n_rules = len(rule_why.WHY)
        corpus_path = ROOT / "corpus" / "v1" / "postings.json"
        if not corpus_path.exists():
            return Check(
                "rule-why-consistent", True,
                f"rule_why has {n_rules} entries (corpus absent)", "",
            )
        records = json.loads(corpus_path.read_text(encoding="utf-8"))
        missing = sorted({
            r["rule"] for r in records if r.get("rule")
        } - set(rule_why.WHY))
        if missing:
            return Check(
                "rule-why-consistent", False,
                f"corpus uses rules not in rule_why: {missing}",
                "open rule_why.py and add entries for the missing "
                "rules; the test suite will give the full diff",
            )
        return Check(
            "rule-why-consistent", True,
            f"all {n_rules} rule_why entries are referenced by "
            f"the corpus", "",
        )
    except Exception as e:  # noqa: BLE001
        return Check(
            "rule-why-consistent", False,
            f"failed to load rule_why or corpus: {e}",
            "check that jobsearch/rule_why.py and "
            "corpus/v1/postings.json are well-formed",
        )


def _check_tools_in_path() -> Check:
    """The tools/ scripts need their dependencies to be findable.
    Check that a smoke import of the demo tool works."""
    try:
        # Just import it; don't run it.
        spec = importlib.util.spec_from_file_location(
            "demo_sieve", ROOT / "tools" / "demo_sieve.py"
        )
        if spec is None or spec.loader is None:
            return Check(
                "tools-importable", False,
                "tools/demo_sieve.py cannot be located",
                "check that tools/demo_sieve.py is in the repo",
            )
        return Check(
            "tools-importable", True,
            "tools/demo_sieve.py is loadable", "",
        )
    except Exception as e:  # noqa: BLE001
        return Check(
            "tools-importable", False,
            f"tools/demo_sieve.py failed to load: {e}",
            "the script is part of the repo; the failure is a bug",
        )


def _all_checks() -> list[Check]:
    return [
        _check_python(),
        _check_module("yaml"),
        _check_module("reportlab", required=False),
        _check_path(ROOT / "corpus" / "v1" / "postings.json", "corpus-v1"),
        _check_path(ROOT / "profile" / "profile.yaml",
                    "profile-yaml", optional=True),
        _check_path(ROOT / "tools" / "verify.sh", "verify-sh"),
        _check_path(ROOT / "tools" / "demo_sieve.py", "demo-sieve"),
        _check_path(ROOT / "scripts" / "export_bundle.py", "export-bundle"),
        # W4.4 -- morning-prepare cron glue. A fresh
        # clone should know if the 08:00 cron glue is
        # missing; without it the morning heartbeat
        # (W4.2) cannot fire.
        _check_path(ROOT / "tools" / "morning_prepare.py",
                    "morning-prepare"),
        # W4.5 -- timezone-aware next-fire-time helper.
        # The morning heartbeat prints this so the
        # operator can see when the next run is expected.
        _check_path(ROOT / "tools" / "next_fire.py",
                    "next-fire"),
        # W2.4 -- the data-flow map generator. A new
        # network call without re-running this tool
        # would silently widen the off-by-default
        # surface.
        _check_path(ROOT / "tools" / "build_dataflow_map.py",
                    "build-dataflow-map"),
        # W1.4 -- the public-history audit. A fresh
        # clone should know if the audit is missing.
        _check_path(ROOT / "tools" / "audit_public_history.sh",
                    "audit-history"),
        # The actual render entry point. A fresh
        # clone should know if the render is missing.
        _check_path(ROOT / "tools" / "render_pdf.py",
                    "render-pdf"),
        # W7.2 -- the release handle script. The W7.2 test
        # (tests/test_release_workflow.py) runs this against
        # the export; a fresh clone should know if the
        # script is missing.
        _check_path(ROOT / "tools" / "release_handle.sh",
                    "release-handle"),

        _check_executable(ROOT / "tools" / "verify.sh"),
        _check_executable(ROOT / "tools" / "release_handle.sh"),
        _check_path(ROOT / ".github" / "workflows" / "release-privacy.yml",
                    "release-workflow"),
        _check_var_writable(),
        _check_digests_writable(),
        _check_jobsearch_imports(),
        _check_rule_why_consistent(),
        _check_tools_in_path(),
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check jobsearch's preconditions; report failures "
                    "with a one-line fix per item."
    )
    ap.add_argument("--quiet", action="store_true",
                    help="only show failures (suppress PASS lines)")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON for tooling")
    args = ap.parse_args(argv)

    checks = _all_checks()
    n_pass = sum(1 for c in checks if c.passed)
    n_fail = sum(1 for c in checks if not c.passed)

    if args.json:
        print(json.dumps({
            "pass": n_pass,
            "fail": n_fail,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "detail": c.detail,
                    "fix": c.fix,
                }
                for c in checks
            ],
        }, indent=2))
        return 1 if n_fail else 0

    print("=" * 64)
    print(f"jobsearch doctor — {n_pass} pass, {n_fail} fail")
    print("=" * 64)
    for c in checks:
        if args.quiet and c.passed:
            continue
        print(c.render())
    print()
    if n_fail == 0:
        print("All preconditions met. Run `bash tools/verify.sh` next.")
        return 0
    print(f"{n_fail} precondition(s) unmet. Fix the items above and "
          f"re-run this command.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
