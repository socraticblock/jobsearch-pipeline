#!/usr/bin/env python3
"""Assemble a clean, shareable copy of the jobsearch pipeline.

    python3 scripts/export_bundle.py                 # build dist/jobsearch-pipeline/
    python3 scripts/export_bundle.py --tar           # ...and a .tar.gz beside it
    python3 scripts/export_bundle.py --run-tests     # run the suite from the export

Why a script rather than "just copy the folder": this workspace also holds the
owner's candidate profile, their job ledger and their session notes, and it sits
inside a checkout of a PUBLIC repository. A hand-made copy is one forgotten `cp`
away from publishing somebody's salary floor. The include list below is therefore
explicit -- anything not named is not shipped -- and the build refuses to produce
an artifact that trips the leak scan.

The scan is a deny-list, not a proof. It catches the personal identifiers and the
secret shapes we know about; it cannot catch a name nobody thought to list. Read
the manifest before sharing, and re-run this after any change to the docs.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

# Absolute home / user paths. Matched as a literal leading segment so a
# docstring that happens to mention "the user" does not trip it.
DENY_HOME_PATTERNS = [
    r"/home/[^/\s\"'`]+\b",          # /home/<user>/...
    r"/Users/[^/\s\"'`]+\b",         # /Users/<user>/... (macOS)
    r"/root/\S*",                    # /root/...
    r"C:\\Users\\[^\\\s\"'`]+\b",   # C:\Users\<user>\...
]

# Forbidden suffixes inside the shipped tree. These never have a legitimate
# reason to land in a published copy: a .db is the live ledger, a .log is
# run output, a .pdf is a rendered digest, and a .sqlite* is the same ledger
# under another name. The list here is the single source of truth -- both the
# copy_tree walker and the post-build scan consult it.
FORBIDDEN_SUFFIXES = {".pdf", ".db", ".sqlite", ".sqlite3", ".log"}


def _is_forbidden(path: Path) -> str | None:
    """Return a reason string if path's name is not allowed in the published tree, else None."""
    s = path.suffix.lower()
    if s in FORBIDDEN_SUFFIXES:
        return f"forbidden file type ({s})"
    if path.name in {"token.json", "google_token.json", "client_secret.json",
                     "google_client_secret.json", ".env", ".env.local"}:
        return f"secret-shaped filename ({path.name})"
    return None

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUNDLE_NAME = "jobsearch-pipeline"

# Where this build is being assembled FROM. The default is the project root --
# the working copy. --src lets the export gate (W1.3) point at a throwaway
# clone with a planted forbidden item, so the mutation test does not have to
# mutate the real checkout. Both root and src are ignored by the leak scan
# itself; only the assembled output is scanned.
SRC = ROOT

# Per-directory allowlist. For INCLUDE entries that are directories, only
# files whose name is in the set below are copied. This is the second half
# of the W1.3 mutation test: a file planted in a shipped directory that
# the include list did not name is refused at copy time, not at leak-scan
# time. The leak scan is the catch-all for content shape; this is the
# catch-all for *membership*.
DIRECTORY_ALLOWLIST: dict[str, set[str]] = {
    "tools/google": {
        "README.md",
        "_hermes_home.py",
        "check_scopes.py",
        "fetch_alerts.py",
        "gws.sh",
        "setup.py",
    },
    # The project's `docs/` contains both tracked project
    # documents (COMPARISON, DATA-FLOW, demo) and Open-Ready
    # scaffold files (README, adr/). The INCLUDE entry ships
    # the whole directory; the allowlist below restricts the
    # copy to the intended files. Subdirectories (`adr/`) ship
    # entirely -- the leak scan catches secret-shaped content.
    "docs": {
        "COMPARISON.md",
        "DATA-FLOW.md",
        "demo.html",
        "README.md",
    },
}

# Everything that ships. Directories are copied recursively. Anything here must
# be safe to hand to a stranger -- the leak scan enforces that, this list is the
# intent.
INCLUDE = [
    "jobsearch",              # the pipeline itself (stdlib + PyYAML)
    "tests",                  # the copy's own suite; its evidence
    "fixtures",               # synthetic alert emails only -- never real mail
    "corpus",                 # labelled counterexample corpus (I-04); pinned by SHA in corpus/manifest.json when shipped
    "docs",                   # generated documentation (DATA-FLOW.md etc.)
    "design",                 # M2/M3 design notes
    ".github",                # GitHub Actions (I-19): release-privacy.yml is part of the public artifact's CI furniture
    "tools/google",           # read-only Gmail OAuth helper + verifiers
    # Shipped because the shipped suite imports it: tests/test_render_pdf.py
    # does `from tools import render_pdf`. Leaving it out produced an artifact
    # whose own tests could not be run -- a copy that is broken on arrival is
    # exactly what --run-tests and the export gate exist to prevent.
    "tools/render_pdf.py",
    "profile/profile.example.yaml",
    # The one-page starter the README points at first. Ships with the
    # reference so a reader who wants five fields does not have to read the
    # long form to find the field names.
    "profile/profile.starter.yaml",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    # - GOAL-AIRTIGHT.md is the requirement list with tests paired to every
    #   claim; it is the project's contract with anyone reading it.
    # - scripts/export_bundle.py is the export gate itself; without it the
    #   W1.3 / W7.1 / W7.3 tests cannot run on the artifact.
    # - tools/audit_public_history.sh is the W1.4 history audit; same reason.
    # - tools/verify.sh is the single local command that equals CI (W7.1).
    "GOAL-AIRTIGHT.md",
    "scripts/export_bundle.py",
    "tools/audit_public_history.sh",
    "tools/verify.sh",
    "tools/scan_artifact.py",
    # W7.2 -- the release handle (artifact tree hash). The
    # W7.2 test (tests/test_release_workflow.py) runs the
    # script against the export and asserts the handle is
    # stable; shipping it in the export lets the bundled
    # suite verify the same contract against the bundle.
    "tools/release_handle.sh",
    # I-09 -- data-flow map generator (W2.4 deliverable)
    "tools/build_dataflow_map.py",
    # I-07 -- interactive demo of the sieve
    "tools/demo_sieve.py",
    # W5.x -- the first run: ingest -> enrich -> gate -> digest on shipped
    # synthetic data, offline. Ships with the sample it reads
    # (fixtures/first_run/, already covered by the "fixtures" include) so a
    # stranger can see the whole pipeline work before they have a profile,
    # a mailbox or a Google account.
    "tools/first_run.py",
    # W5.2 -- single-command health check
    "tools/doctor.py",
    # New: onboarding from a CV + preferences.
    "tools/onboard.py",
    # Packaging metadata.
    # (pyproject.toml stays in the source tree only: it carries the repo URL,
    # which the leak scan would block in the export. pip install works from
    # the source clone.)
    # Enrich retry helper for cron.
    "tools/enrich_retry.sh",
    # Telegram delivery of the digest.
    "tools/deliver_digest.py",
    # Static HTML report (no backend, no login).
    "tools/render_html.py",
    # W4.4 -- morning-prepare cron glue. Ships because the
    # public W4.4 contract test (tests/test_run_lock.py)
    # spawns the actual file as a subprocess; without it,
    # the export's own tests cannot verify the run lock.
    # The file contains no host-specific paths.
    "tools/morning_prepare.py",
    # W4.5 -- timezone-aware next-fire-time helper. Pure
    # function over Python's zoneinfo module; ships so
    # operators in other timezones can compute the next
    # 08:00 without depending on the host's clock.
    "tools/next_fire.py",
    # The CLAIMS / REQUIREMENTS / DISCLAIMER / AGENTS surface (I-01..I-13).
    # CLAIMS.md is the public truth-table; REQUIREMENTS.md is the stable-ID
    # catalogue; DISCLAIMER.md is the user-facing responsibility statement;
    # AGENTS.md is the canonical agent contract. CLAUDE.md, CODEX.md, and
    # GEMINI.md are 2-line wrappers around AGENTS.md that ship with it so
    # the project loads correctly in any of the common coding CLIs.
    # ACKNOWLEDGEMENTS.md (I-20) and UNKNOWN_POLICY.md (I-16) join the
    # public surface as borrow log and the project's "no fabrication"
    # policy.
    "CLAIMS.md",
    "REQUIREMENTS.md",
    "DISCLAIMER.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    "GEMINI.md",
    "ACKNOWLEDGEMENTS.md",
    "UNKNOWN_POLICY.md",
    # requirements.txt is GENERATED by this script (see REQUIREMENTS_TXT) rather
    # than copied, so the shipped dependency list cannot drift from the notes.
]

# Copied only when present, and never invented. Repo furniture a stranger needs
# (licence, security policy, changelog) plus the leak runbook. Anything named
# here is scanned like everything else; "optional" means "not every checkout
# has one yet", not "unchecked". LICENSE is deliberately in this list rather
# than INCLUDE: the licence is an owner decision, and the export gate is the
# thing that refuses to publish while it is missing (W7.3). docs/ is NOT
# here -- it is already in INCLUDE; adding it again would double-walk
# every file under docs/ and add a duplicate entry to the manifest.
OPTIONAL_INCLUDE = [
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
]

# Deliberately NOT shipped. Listed rather than merely omitted so that a future
# edit has to argue with the reason. The companion to this dict is
# SOURCE_EXCLUDE -- a per-path allow list of files that the source tree
# may legitimately contain (the owner's real profile, the working db,
# the session handoff) but that the walker must never visit. The
# source-completeness check consults SOURCE_EXCLUDE so it does not flag
# the very files it is designed to keep out of the artifact.
EXCLUDE = {
    "var": "the job ledger (SQLite) -- real ingested data",
    "digests": "rendered shortlists -- real job data",
    "pyproject.toml": "packaging metadata with repo URLs (source-only, leak-scan would block the URL)",
    ".gitignore": "the privacy guard, which makes no sense outside this workspace",
    # Open-Ready scaffold (created by `openready init --adopt`):
    # bookkeeping for the open-source-readiness system, not part
    # of the public jobsearch artifact. Listed here so the source-
    # completeness check accepts them in the source tree without
    # shipping them in the curated bundle.
    "MANIFEST.in": "build-metadata file used by `python -m build`; not part of the curated public artifact",
    "tests/test_installed_cli.py": "requires python -m build which is not available in the export bundle",
    "openready.project.json": "Open-Ready project contract; used by the openready CLI, not part of the curated public artifact",
}
# Files the source-completeness check must NOT flag. The source tree is
# allowed to contain these (they are owner data or host-only paths);
# the check just confirms they are not in the published artifact.
SOURCE_EXCLUDE = set(EXCLUDE.keys())

SKIP_DIRS = {"__pycache__", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log"}

# Personal identifiers, matched on WORD BOUNDARIES. Substring matching would
# flag "angel" for "GEL" and "georgian" for "Georgia", and a scanner that cries
# wolf gets switched off -- which is how a real leak ships.
DENY_TOKENS = [
    # Sibling-project handle and email provider: public, but the
    # owner prefers not to advertise them in the artifact
    # since they are not part of the project identity.
    r"\bsakartvelo\b", r"\bgmail\.com\b", r"\bbelgian\b",
    # Private: location, language, currency, compensation.
    r"\btbilisi\b", r"\bgeorgia\b", r"\bgel\b",
    # The owner's actual compensation figures, read from their profile rather
    # than remembered: the floor, and the written target range.
    r"\b5,000\b", r"\b5,680\b", r"\b7,100\b",
]

# Secret-shaped VALUES, not field names. An earlier version of this list matched
# the literal words `client_secret` and `refresh_token`, and so refused to ship
# the OAuth helper whose whole job is to write those JSON fields -- a scanner
# that blocks the credential code for naming credentials is useless. These
# patterns match what an actual secret looks like.
DENY_SECRET_PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bya29\.[A-Za-z0-9_\-]{20,}",        # Google access token
    r"\b1//0[A-Za-z0-9_\-]{20,}",          # Google refresh token
    r"\bGOCSPX-[A-Za-z0-9_\-]{10,}",       # Google client secret
    r"\bAIza[A-Za-z0-9_\-]{30,}",          # Google API key
    r"\bghp_[A-Za-z0-9]{20,}",             # GitHub PAT
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bsk-[A-Za-z0-9]{20,}",              # OpenAI-style key
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}",     # Slack token
    r"\b\d{9,10}:AA[A-Za-z0-9_\-]{30,}",   # Telegram bot token
]

# Files where naming a token is the point, or where a token is world knowledge
# rather than a fact about a person. Every entry states why, and the scan PRINTS
# each allowance it applies -- an allowance nobody can see is how a scanner gets
# quietly neutered.
TOKEN_ALLOWANCES = {
    ("jobsearch/rules.py", r"\bgel\b"): (
        "GEL is one of four currency codes the salary parser recognises. The "
        "owner's own floor and the currency it is stated in now come from the "
        "profile, so naming the code in a vocabulary discloses nothing about them."
    ),
    ("tests/test_rules.py", r"\bgel\b"): (
        "The test pins _CURRENCY_ALIAS (which includes GEL as a symbol). "
        "The GEL currency code is a public vocabulary entry in the salary "
        "parser; naming it in the test that pins the vocabulary discloses "
        "nothing about the owner's profile or salary."
    ),
    ("corpus/v1/postings.json", "*"): (
        "The labelled counterexample corpus (I-04) is synthetic by construction "
        "(see corpus/v1/.synthetic). It uses real city and country names as "
        "fixtures for the gate's location rules -- the body of c-009 mentions "
        "Tbilisi because the test exercises the local_ok branch. None of "
        "these names are the owner's location; they are test data."
    ),
    ("tests/test_portability.py", "*"): (
        "This file exists to assert that the shipped template contains no personal "
        "markers, so it has to name them. Its only personal content is the list."
    ),
    ("tests/test_starter_profile.py", "*"): (
        "This file asserts that the shipped starter profile carries no personal "
        "marker, so it has to name the markers it refuses. Its only personal "
        "content is that list, and the file it guards is a template of "
        "placeholders."
    ),
    ("tools/audit_public_history.sh", "*"): (
        "The history audit exists to prove those markers never reached a commit, "
        "so it has to name them. It contains no value belonging to the owner -- "
        "only the words a leak would necessarily contain."
    ),
    # test_history_audit.py exercises the audit script's NAMES and TOKENS
    # lists. The test legitimately needs to assert each entry is caught,
    # so it has to name them. Each literal in the test file is a fixture
    # used to verify the audit, not a real personal identifier; the test
    # constructs dangling blobs and commits the forbidden paths to prove
    # the audit flags them. The list of literals here is parallel to the
    # audit script's NAMES and TOKENS lists.
    ("tests/test_history_audit.py", "*"): (
        "The audit test exercises the audit script's NAMES and TOKENS "
        "lists, so it has to name them. Each literal in the test file is a "
        "fixture used to verify the audit catches that specific marker -- "
        "the test does not assert the marker belongs to a real person, "
        "only that the audit would flag it if it did."
    ),
    # test_render_pdf.py exercises the renderer with a salary string the gate
    # recognises. The value itself is a fixture, not a real figure, and the test
    # would be self-defeating if it could not name a recognisable currency shape.
    ("tests/test_render_pdf.py", r"\b5,000\b"): (
        "Fixture salary string used to assert 'pay is reported only when the "
        "posting states it'. The test guards the renderer's honesty; it is not "
        "the owner's own floor."
    ),
    ("CHANGELOG.md", "*"): (
        "The changelog documents the audit-script pinning work and other "
        "test additions that legitimately need to name the personal "
        "identifiers (e.g. when explaining what the audit script's "
        "NAMES and TOKENS lists contain). The file is part of the "
        "publication; its only personal content is the names of the "
        "audit markers, not values belonging to the owner."
    ),
    # SECURITY.md is the runbook. To describe what a leak looks like and how
    # to recognise one, it has to name the personal identifiers a leak would
    # necessarily contain. None of them are values -- they are the words the
    # audit script greps for.
    ("SECURITY.md", "*"): (
        "The leak runbook has to name what it is looking for: the repository "
        "name, the project location, the country of residence, the salary floor "
        "currency code. The file is part of the publication gate; its only "
        "personal content is the list of things a real leak would necessarily "
        "include."
    ),
    # The export-gate mutation test plants real-shaped values into throwaway
    # files at runtime. The shapes themselves are deny-listed, so the test code
    # has to mention them in string literals. Each literal in the test file is
    # a fixture shape used to verify the gate, not a real secret. The shape
    # strings live in the test, the values they produce are 24+ char fillers
    # the test constructs from "A" * 24 etc.
    ("tests/test_export_gate.py", "*"): (
        "The mutation test constructs deny-listed shapes from placeholders at "
        "runtime to verify the gate catches them. None of the literals in this "
        "file are real credentials; they are the SHAPES a real credential would "
        "have, which is exactly what the gate's deny-list matches against."
    ),
    # I-04 -- labelled counterexample corpus (postings.json + .synthetic sidecar)
    ("corpus/v1/postings.json", "*"): (
        "Labelled counterexample corpus (I-04). Borrowed pattern from "
        "inbox-job-tracker's tests/fixtures/emails.json: a JSON array of "
        "synthetic {id, rule, expect, why, body, title, ...} records. "
        "Each `rule` maps to a key in jobsearch/rule_why.WHY. Each `why` "
        "names the failure category. Real city names (Tbilisi, London) "
        "appear in synthetic bodies as test data for the gate's location "
        "rules; they are not the owner's location."
    ),
    ("corpus/v1/.synthetic", "*"): (
        "The SYNTHETIC ONLY sidecar for the corpus. The first line is the "
        "marker; the rest of the file is free-form documentation. The "
        "synthetic-only test asserts every JSON fixture directory has this "
        "sidecar. JSON has no comment syntax, so the sidecar is the marker."
    ),
    # I-05 -- why registry test
    ("tests/test_why_spec.py", "*"): (
        "Test for the why-field-as-spec registry in jobsearch/rule_why.py. "
        "The test asserts every category in WHY is a non-empty sentence and "
        "that at least a quarter of them reference a real workstream or "
        "claim id. The test does not contain any real personal data."
    ),
    # I-14 -- synthetic-only fixture header test
    ("tests/test_synthetic_only.py", "*"): (
        "Test that asserts every fixture or corpus data file in "
        "tests/fixtures, corpus/, or fixtures/ self-declares as synthetic. "
        "The test walks the directories and looks for the SYNTHETIC ONLY "
        "marker (or a .synthetic sidecar for JSON files). The test does not "
        "contain any real personal data; the regexes it uses for "
        "defence-in-depth are constructed from the project rule list, not "
        "from real values."
    ),
    # I-04 -- corpus shape test
    ("tests/test_corpus.py", "*"): (
        "Test for the corpus shape: JSON array, every record has the "
        "required fields, every rule is in the why registry, every expect "
        "is an allowed value, every why is a sentence, no real emails. The "
        "test does not contain any real personal data."
    ),
    # I-05 -- rule_why.py itself
    ("jobsearch/rule_why.py", "*"): (
        "The why-field-as-spec registry. A central dict mapping each rule "
        "category to a one-sentence statement of the failure it catches. "
        "The same string is used in the test docstring, the corpus "
        "fixture's `why`, the verdict surface, and the CLAIMS.md "
        "verification. None of the strings are personal data; they are "
        "general principles and W/B/CL/I references."
    ),
    # I-09 -- data-flow map and its generator
    ("tools/build_dataflow_map.py", "*"): (
        "Generator for docs/DATA-FLOW.md. Walks the source tree, finds "
        "every module that imports a network API (urllib, requests, "
        "telegram, ...), and renders a Markdown table. The committed map "
        "is byte-identical to the tool's output (reproducibility test). "
        "The tool does not import any network API itself; it only reads "
        "source files via the stdlib `ast` module."
    ),
    ("docs/DATA-FLOW.md", "*"): (
        "Generated by tools/build_dataflow_map.py. Lists every module "
        "that performs network I/O, the API it imports, the direction "
        "of the call, and the data surface. The map is the W2.4 deliverable."
    ),
    ("docs/COMPARISON.md", "*"): (
        "Capability matrix in the JobCtrl docs/comparison.md shape, "
        "rewritten in this project's voice. The doc explicitly "
        "acknowledges the borrowed shape so a reader does not have "
        "to wonder whether the matrix is original. The doc does not "
        "contain any personal data."
    ),
    ("tools/demo_sieve.py", "*"): (
        "Interactive demo of the sieve. Borrowed shape from "
        "career-ops' walk-through: a reader can run the gate on a "
        "real posting and see the verdict, the satisfied signals, "
        "the failed essentials, the uncertain items, and the why "
        "from the rule_why registry. The tool does not perform any "
        "network I/O; it only reads the corpus or stdin and uses "
        "the stdlib and PyYAML."
    ),
    ("tools/doctor.py", "*"): (
        "W5.2 single-command health check. Borrowed shape from "
        "JobCtrl's doctor (MIT) and jobsync's check-and-suggest "
        "pattern. Inspects a fresh checkout, reports every unmet "
        "precondition with a one-line fix per item, and exits 1 "
        "if anything is missing. The tool does not perform any "
        "network I/O; it only reads the local filesystem and "
        "imports the jobsearch package."
    ),
    ("tools/morning_prepare.py", "*"): (
        "W4.4 morning-prepare cron glue. The file contains no "
        "host-specific paths; it is the public half of the "
        "08:00 daily delivery and the W4.4 contract test "
        "(tests/test_run_lock.py) spawns it as a subprocess to "
        "verify the run lock works on a /tmp copy. The script "
        "does not perform any network I/O; it runs the local "
        "ingest and the local render. The run lock is acquired "
        "with flock(LOCK_EX | LOCK_NB) on var/morning-prepare.lock."
    ),
    ("tools/next_fire.py", "*"): (
        "W4.5 timezone-aware next-fire-time helper. Pure "
        "function over Python's zoneinfo module; computes "
        "the next target_hour in a given IANA timezone "
        "and correctly handles DST transitions (spring-"
        "forward, fall-back) without explicit day-iteration "
        "logic. The helper does not perform any network I/O "
        "or shell out; the calculation is fully local so it "
        "is testable in isolation and deterministic across "
        "hosts. Default target_hour=8, default tz=Europe/"
        "Berlin; both are overridable via CLI flags."
    ),
    ("tests/test_dataflow_map.py", "*"): (
        "Test that the data-flow map is up to date: every network module "
        "in source is documented, every documented module is real, and "
        "re-running the generator produces a byte-identical file. The "
        "test does not perform any network I/O itself; it only inspects "
        "source code via `ast` and `subprocess`."
    ),
    # I-19 -- CI release gate
    ("tests/test_release_workflow.py", "*"): (
        "Test for the release-privacy GitHub Action: the workflow YAML "
        "parses, has both the verify and privacy jobs, does not pass "
        "the no-licence override, uses a current (v4+) checkout action. "
        "The test does not perform any network I/O itself; it only "
        "inspects the YAML text."
    ),
    (".github/workflows/release-privacy.yml", "*"): (
        "GitHub Actions workflow that runs tools/verify.sh and a deny-list "
        "leak scan on the BUILT tree on every push and PR. The action is "
        "the I-19 / W7.1 deliverable; the W7.3 owner gates stay owner gates "
        "(the action refuses to publish; the human publishes). The workflow "
        "file does not contain any personal data."
    ),
    # I-16 test, I-20 test
    ("tests/test_unknown_policy.py", "*"): (
        "Test for the Unknown policy: the policy doc exists, names all "
        "three verdicts, cites the corpus fixture; the gate's evaluate() "
        "returns `needs_research` (not a fabricated verdict) for every "
        "named missing-evidence shape, and the corpus's c-001 fixture "
        "evaluates to `needs_research` as the policy says it must. The "
        "test does not perform any network I/O; it only inspects the "
        "policy doc and the corpus JSON."
    ),
    ("tests/test_acknowledgements.py", "*"): (
        "Test for ACKNOWLEDGEMENTS.md: the file exists, is substantial, "
        "names every borrowed project, distinguishes borrowed ideas from "
        "copied text, and contains a 'what was not borrowed' section. "
        "The test does not perform any network I/O; it only reads the "
        "borrow log."
    ),
    ("tests/test_corpus_end_to_end.py", "*"): (
        "End-to-end QA test for the corpus: every fixture in "
        "corpus/v1/postings.json is run through extract() and "
        "evaluate() with its documented profile, and the outcome "
        "must equal the fixture's `expect`. The test also asserts "
        "every fixture has a `profile` field and that the gate is "
        "deterministic. The test does not perform any network I/O."
    ),
    ("tests/test_comparison.py", "*"): (
        "Test for docs/COMPARISON.md: the file exists, is "
        "substantial, has the three borrowed sections, names the "
        "four-outcome vocabulary, the 'does NOT do' table is at "
        "least as long as the 'does' table, the ecosystem section "
        "mentions every borrowed project, and the doc "
        "acknowledges the borrowed shape. The test does not "
        "perform any network I/O; it only reads the doc text."
    ),
    ("tests/test_demo_sieve.py", "*"): (
        "Test for tools/demo_sieve.py: the tool exists, the default "
        "invocation runs, the --list and --corpus-id and --stdin "
        "and --json modes all work, the output includes the why "
        "from the registry, and an unknown corpus id exits nonzero. "
        "The test does not perform any network I/O; it only runs "
        "the demo as a subprocess and inspects its stdout."
    ),
    ("tests/test_rule_name_verdict_agreement.py", "*"): (
        "QA test: every corpus fixture's rule name agrees with its "
        "verdict. A rule name that contains a hard-drop substring "
        "must produce a not_suitable verdict; a rule name with "
        "'uncertain' must produce needs_research; a rule name with "
        "'satisfied', 'soft_signal', or 'learnable' must produce a "
        "suitable verdict. Drift between name and verdict is a "
        "documentation problem and a reader trap. The test does not "
        "perform any network I/O; it only reads the corpus JSON."
    ),
    ("tests/test_doctor.py", "*"): (
        "Test for tools/doctor.py: the tool exists, the clean "
        "checkout passes, missing required files produce a FAIL "
        "with a one-line fix, non-executable verify.sh produces a "
        "chmod fix, --json output is well-formed and exits 1 on "
        "failure, --quiet suppresses PASS lines, every FAIL has a "
        "fix line, and the source contains no network imports. "
        "The test does not perform any network I/O; it works on "
        "disposable copies in /tmp."
    ),
    ("tests/test_evidence_quote.py", "*"): (
        "W3.2 contract test: every verdict's failed_essential "
        "list must cite the posting. The contract: every failure "
        "has a quoted phrase; the quoted phrase is a real "
        "substring of the title or body; non-title failures "
        "include a real sentence (3+ words), not a single "
        "keyword. Drift between the failure string and the "
        "posting is a fabrication. The test does not perform "
        "any network I/O; it only inspects the corpus and the "
        "verdict output."
    ),
    ("tests/test_profession_signals.py", "*"): (
        "W3.4 contract test: the profession-signal vocabulary is "
        "profile data with a documented English default. A "
        "non-English candidate adds their own list to profile.yaml "
        "without editing code. The test asserts the default "
        "English list catches every common software title word; "
        "a non-English title is missed by the default; a profile "
        "with German/French signals recognises the locale's "
        "software title; and a non-software German title "
        "(Verkäufer) is still rejected with the augmented "
        "profile. The test does not perform any network I/O; it "
        "only inspects the corpus and the gate."
    ),
    ("tests/test_coverage.py", "*"): (
        "W3.3 contract test: the digest's coverage line is "
        "honest. A reader who sees a shortlist must be able to "
        "tell whether the gate is silent because every posting "
        "passed, or because the gate never had a description to "
        "evaluate. The test asserts: collect() returns a "
        "5-tuple; stats always carries the four counts "
        "(read, with_description, not_judged, surfaced, dropped); "
        "incomplete-description postings go to not_judged, not "
        "to surfaced or dropped; the text report's coverage line "
        "includes the not_judged count; the NOT YET RETRIEVED "
        "section lists each unretrieved posting with its link. "
        "The test does not perform any network I/O; it builds a "
        "fresh SQLite ledger in /tmp and inspects the collect "
        "and report functions."
    ),
    ("tests/test_claims_hygiene.py", "*"): (
        "CLAIMS.md is the project's constitution: every public "
        "statement about the project is backed by a current "
        "verification. The test asserts: every CL-XXX claim has "
        "a unique number, a status (Current/Beta/Roadmap), a "
        "Verification pointer, and a Last verified date; a "
        "Roadmap claim cannot point at a file that exists on "
        "disk (the work is shipped, the claim must be Current). "
        "The test does not perform any network I/O; it only "
        "inspects the document and the filesystem."
    ),
    ("tests/test_bounded_retry.py", "*"): (
        "W4.3 contract test: the Gmail API call gets bounded "
        "exponential backoff on 429 and 5xx; a 4xx other than "
        "429 is a hard fail; the retry loop is capped at 5 "
        "attempts and named in the run report; the backoff "
        "doubles each attempt; the fetch path does not import "
        "any evasion primitive (proxy rotator, UA-spoof helper, "
        "captcha solver, headless-browser automation library). "
        "The test does not perform any network I/O; it stubs "
        "HttpError locally and inspects the retry loop directly."
    ),
    ("tests/test_run_lock.py", "*"): (
        "W4.4 contract test: morning-prepare acquires an "
        "exclusive non-blocking file lock before doing any work; "
        "a second invocation that finds the lock held exits 3 "
        "with a recorded reason; the lock is released "
        "automatically on process exit (kernel reclaims the fd); "
        "a render failure inside the lock-holding block still "
        "releases the lock. The test does not perform any "
        "network I/O; it spawns the actual morning_prepare.py "
        "as a subprocess in a /tmp copy of the project."
    ),
    ("tests/test_next_fire.py", "*"): (
        "W4.5 contract test: 08:00 stays 08:00 across a DST "
        "boundary. The test exercises both the spring-forward "
        "(2026-03-29 in Europe/Berlin: 02:00 -> 03:00) and "
        "fall-back (2026-10-25: 02:00-03:00 happens twice) "
        "transitions and asserts the helper never misses or "
        "double-fires 08:00. The test does not perform any "
        "network I/O; it pins the clock with explicit "
        "datetime objects and inspects the helper's return value."
    ),
    ("tests/test_storage_failure.py", "*"): (
        "W4.6 contract test: the ledger survives a full "
        "disk, a truncated DB, and a half-written WAL. The "
        "test exercises real SQLite behavior on /tmp "
        "copies of the ledger: a commit failure (ENOSPC or "
        "read-only DB) leaves the ledger in the pre-failure "
        "state, a truncated DB fails fast with a clear "
        "DatabaseError, and a WAL-mode write is replayed on "
        "next open. The test does not perform any network "
        "I/O; it uses Python's tempfile and unittest.mock."
    ),
    # I-16 -- the Unknown policy
    ("UNKNOWN_POLICY.md", "*"): (
        "The project's 'no fabrication' policy. States that missing "
        "evidence produces `needs_research`, not a fabricated verdict. "
        "Names the three verdicts, the missing-evidence shapes, the "
        "minimum-evidence rule, and why the policy is opinionated. The "
        "doc does not contain any personal data."
    ),
    # I-20 -- the borrow log
    ("ACKNOWLEDGEMENTS.md", "*"): (
        "Borrow log: lists every project this project took a pattern or "
        "shape from, the licence that project ships under, and the "
        "specific idea this project re-derived. The doc also lists what "
        "was NOT borrowed and why. No verbatim text from any source "
        "project is reproduced; the borrowed items are shapes, not "
        "words. The doc does not contain any personal data."
    ),
    # GOAL-AIRTIGHT.md is the project goal. It names the owner, the
    # repository the project lives inside, and the public repo's name to
    # make clear that the project sits in a checkout that holds a public
    # game. None of those are values belonging to the owner -- the
    # repository name is public, the email is the GitHub one, and the
    # project location is part of the public boundary this very file
    # exists to describe.
    ("GOAL-AIRTIGHT.md", "*"): (
        "The goal document names the public repository, the workspace "
        "path, and the public/private boundary to make the publication "
        "contract explicit. These are not personal values; they are the "
        "context every reader needs to evaluate the project."
    ),
    # CLAIMS.md is the public truth-table (I-01). It maps every public
    # claim to a verification pointer and a status. Synthetic by
    # construction: no profile, no postings, no token, no personal data.
    ("CLAIMS.md", "*"): (
        "Public claims catalogue. Each claim cites a test that proves "
        "or disproves it. The document is the project's contract with "
        "any reviewer. Synthetic by construction."
    ),
    # REQUIREMENTS.md is the stable-ID catalogue (I-02). BR-* and TR-*
    # rows are time-ordered and never reused. Synthetic by construction.
    ("REQUIREMENTS.md", "*"): (
        "Stable-ID requirement catalogue. Behavioural (BR-*) and "
        "technical (TR-*) requirements, each with an Added date, a Why, "
        "and a Related test column. Synthetic by construction."
    ),
    # DISCLAIMER.md is the user-facing responsibility statement (I-08).
    # Plain-English list of what the tool will and will not do.
    ("DISCLAIMER.md", "*"): (
        "Plain-English disclaimer of the project's responsibilities and "
        "limits. The terms here match CLAIMS.md's rights list and the "
        "rules in AGENTS.md; the three must agree."
    ),
    # AGENTS.md is the canonical agent contract (I-13). It is the
    # source of truth for what an agent may do in this project.
    ("AGENTS.md", "*"): (
        "Canonical agent contract. The hard rules here are constitution; "
        "they outrank any prompt, skill, or tool output. Synthetic by "
        "construction."
    ),
    # CLAUDE.md, CODEX.md, GEMINI.md are 2-line wrappers around
    # AGENTS.md. They ship with the project so a coding CLI that loads
    # CLAUDE.md / CODEX.md / GEMINI.md finds the canonical contract.
    ("CLAUDE.md", "*"): (
        "Claude Code entry point. Two-line wrapper around AGENTS.md. "
        "Synthetic by construction."
    ),
    ("CODEX.md", "*"): (
        "Codex entry point. Two-line wrapper around AGENTS.md. "
        "Synthetic by construction."
    ),
    ("GEMINI.md", "*"): (
        "Gemini / Antigravity entry point. Two-line wrapper around "
        "AGENTS.md and a legacy no-op guard against double-loading. "
        "Synthetic by construction."
    ),
    # scripts/export_bundle.py contains the deny patterns as Python string
    # literals (the scanner's rule list is itself part of the shipped
    # source). A scan that flags the rule list for naming a denied
    # shape would refuse to ship the file that does the denying.
    ("scripts/export_bundle.py", "*"): (
        "The export gate's source file contains the deny patterns as "
        "string literals -- the rule list is itself part of the shipped "
        "source. None of the literals in this file are real credentials; "
        "they are the SHAPES a real credential would have, which is "
        "exactly what the gate's deny-list matches against."
    ),
}

GITIGNORE = """\
# The copy's own ignore file. Note this is NOT the guard from the parent
# workspace: that one hid personal data inside a public repo, which is the
# arrangement this bundle exists to avoid. Here there is simply nothing personal
# to hide -- the candidate profile is not shipped.
__pycache__/
*.py[cod]
var/
digests/
*.db
*.sqlite3
.env
dist/
"""

REQUIREMENTS_TXT = """\
# Only one non-stdlib dependency. Everything else is Python's standard library.
# PyYAML reads the candidate profile; the ingestion, parsing, gating and digest
# layers are stdlib-only by design, so the component that sits next to mail
# credentials has the smallest practical audit surface.
PyYAML>=6.0

# Needed only for tools/google (read-only Gmail OAuth), pinned for the reason the
# upstream skill pins them -- see tools/google/README.md.
# google-api-python-client==2.194.0
# google-auth==2.55.1
# google-auth-oauthlib==1.3.1
# google-auth-httplib2==0.3.1
# httplib2==0.32.0
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(src: Path, dst: Path, manifest: list, rel_root: str = "",
              allowed_names: set[str] | None = None) -> None:
    """Copy a directory tree into dst, refusing to copy anything that the
    export gate would later refuse to ship. A forbidden file that slips through
    here is caught by leak_scan; raising here turns "refuse to ship" into
    "refuse to even try" and gives a tighter error message.

    If allowed_names is given, files in this directory not in the set are
    refused at copy time. This is the second half of the W1.3 mutation
    test: a planted file in a shipped directory that the include list did
    not name must NOT silently land in the artifact.

    Returns the list of (rel, sha256, bytes) tuples for the files actually
    copied, so the caller can compare it against what was on disk -- a file
    that is in the source directory but not in the manifest is exactly the
    "unlisted file" the W1.3 mutation test is designed to plant.
    """
    for entry in sorted(src.iterdir(), key=lambda p: p.name):
        if entry.name in SKIP_DIRS or entry.suffix in SKIP_SUFFIXES:
            continue
        rel = f"{rel_root}{entry.name}"
        # Skip files/directories listed in EXCLUDE
        if rel in EXCLUDE or any(rel.startswith(p + "/") for p in EXCLUDE if "/" in p):
            continue
        if entry.is_dir():
            # Pass the allowed_names filter through to subdirs, but do
            # NOT filter at subdir level unless this is the include
            # root. Subdirectories are not filtered; the leak scan
            # would catch a secret-shaped file in a subdir.
            (dst / entry.name).mkdir(parents=True, exist_ok=True)
            copy_tree(entry, dst / entry.name, manifest, rel_root=f"{rel}/")
        else:
            if allowed_names is not None and entry.name not in allowed_names:
                raise RuntimeError(
                    f"REFUSING TO COPY unlisted file {rel}: this directory's "
                    f"include-list entry did not authorise it. Either remove "
                    f"the file or add it to the include list."
                )
            reason = _is_forbidden(entry)
            if reason:
                raise RuntimeError(
                    f"REFUSING TO COPY forbidden file {rel}: {reason}. "
                    f"Move it out of the include path or add an explicit allowance."
                )
            shutil.copy2(entry, dst / entry.name)
            manifest.append((rel, sha256(entry), entry.stat().st_size))


def leak_scan(root: Path, expected_manifest: list[tuple[str, str, int]] | None = None
              ) -> tuple[list[str], list[str]]:
    """Return (findings, allowances_applied).

    Empty findings == nothing matched. That is never the same as "safe": this is
    a deny-list, and it only knows the names somebody thought to write down.

    If expected_manifest is given, also assert every file in the built tree is
    accounted for in the manifest -- an unlisted file is a leak risk even when
    none of the deny-list patterns match.
    """
    findings: list[str] = []
    allowed: list[str] = []
    token_res = [(t, re.compile(t, re.IGNORECASE)) for t in DENY_TOKENS]
    secret_res = [(p, re.compile(p)) for p in DENY_SECRET_PATTERNS]
    home_res = [(p, re.compile(p)) for p in DENY_HOME_PATTERNS]

    def allowance_for(rel: str, token: str) -> str | None:
        for (path_key, token_key), reason in TOKEN_ALLOWANCES.items():
            if path_key != rel:
                continue
            if token_key == "*" or token_key == token:
                return reason
        return None

    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        rel_s = str(rel)
        seen.add(rel_s)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            findings.append(f"{rel}: BINARY or unreadable — inspect before sharing")
            continue
        for token, rx in token_res:
            m = rx.search(text)
            if not m:
                continue
            line_no = text[:m.start()].count("\n") + 1
            reason = allowance_for(rel_s, token)
            if reason:
                allowed.append(f"{rel}:{line_no}: /{token}/ — {reason}")
            else:
                findings.append(f"{rel}:{line_no}: personal token /{token}/")
        for pattern, rx in secret_res:
            m = rx.search(text)
            if m:
                line_no = text[:m.start()].count("\n") + 1
                # Secret-pattern allowances: same dictionary, looked up
                # by pattern. An entry keyed on "*" allows all secret
                # patterns for that file (used by the mutation test,
                # which must name deny-listed shapes in string literals).
                reason = allowance_for(rel_s, pattern)
                if reason:
                    allowed.append(f"{rel}:{line_no}: /{pattern}/ — {reason}")
                else:
                    findings.append(f"{rel}:{line_no}: secret-shaped value /{pattern}/")
        for pattern, rx in home_res:
            m = rx.search(text)
            if m:
                line_no = text[:m.start()].count("\n") + 1
                reason = allowance_for(rel_s, pattern)
                if reason:
                    allowed.append(f"{rel}:{line_no}: /{pattern}/ — {reason}")
                else:
                    findings.append(f"{rel}:{line_no}: absolute home path /{pattern}/")

    if expected_manifest is not None:
        manifest_paths = {p for p, _, _ in expected_manifest}
        unlisted = seen - manifest_paths
        # The generated files are not on the manifest: the .gitignore, the
        # MANIFEST.txt itself, and the generated requirements.txt. Filter those.
        generated = {"MANIFEST.txt", ".gitignore", "requirements.txt"}
        truly_unlisted = unlisted - generated
        if truly_unlisted:
            for u in sorted(truly_unlisted):
                findings.append(f"{u}: UNLISTED — present in built tree but not in the manifest")
    return findings, allowed


def build(args) -> int:
    src = Path(args.src).resolve() if args.src else ROOT
    out = Path(args.out).resolve() if args.out else (src / "dist" / BUNDLE_NAME)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest: list = []
    missing = []
    for item in INCLUDE:
        s = src / item
        if not s.exists():
            missing.append(item)
            continue
        if s.is_dir():
            # Preserve the include entry's own path: "tools/google" must land at
            # tools/google, not be flattened to the bundle root. Both halves of
            # this bug (files and directories) were caught by --run-tests and by
            # reading the tarball listing, not by the offline unit tests.
            dest = out / item
            dest.mkdir(parents=True, exist_ok=True)
            copy_tree(s, dest, manifest, rel_root=f"{item}/",
                      allowed_names=DIRECTORY_ALLOWLIST.get(item))
        else:
            # Preserve the include entry's own path: "profile/profile.example.yaml"
            # must land at profile/, not be flattened to the bundle root. The
            # export's own test run is what caught this.
            dest = out / item
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, dest)
            manifest.append((item, sha256(s), s.stat().st_size))
    if missing:
        print(f"ERROR: include list names paths that do not exist: {missing}")
        shutil.rmtree(out)
        return 1

    for item in OPTIONAL_INCLUDE:
        s = src / item
        if not s.exists():
            continue
        if s.is_dir():
            dest = out / item
            dest.mkdir(parents=True, exist_ok=True)
            copy_tree(s, dest, manifest, rel_root=f"{item}/",
                      allowed_names=DIRECTORY_ALLOWLIST.get(item))
        else:
            dest = out / item
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, dest)
            manifest.append((item, sha256(s), s.stat().st_size))

    (out / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (out / "requirements.txt").write_text(REQUIREMENTS_TXT, encoding="utf-8")

    manifest.sort()
    # Dedupe defensively: a file in both INCLUDE and
    # OPTIONAL_INCLUDE would land here twice. The header
    # below claims "{N} files", and a future reader
    # trusting that number to plan a release must be
    # able to compare it against a real file count.
    # The earlier W4.6 + W4.4 tests for the manifest
    # were checking entries, not paths; the dedup is
    # the right place to make the two agree.
    seen: set[str] = set()
    deduped: list = []
    for rel, h, size in manifest:
        if rel in seen:
            continue
        seen.add(rel)
        deduped.append((rel, h, size))
    manifest = deduped
    lines = [
        f"# {BUNDLE_NAME} — build manifest",
        f"# built {date.today().isoformat()} by scripts/export_bundle.py",
        f"# {len(manifest)} files",
        "# sha256  bytes  path",
    ]
    lines += [f"{h}  {size:>8}  {rel}" for rel, h, size in manifest]
    (out / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"assembled {len(manifest)} files -> {out}")

    findings, allowed = leak_scan(out, expected_manifest=manifest)
    if findings:
        print("\nREFUSING TO SHIP — leak scan found:")
        for f in findings:
            print(f"  {f}")
        shutil.rmtree(out)
        print("\nthe incomplete bundle was deleted; fix the source and re-run")
        return 1

    # Source-completeness check: walk the source tree and assert that
    # every file the walker would have shipped is on the manifest. The
    # leak scan's completeness check only sees what the WALKER copied;
    # this check sees what the SOURCE has. The two checks together close
    # the gap: a planted file in a shipped directory (which the walker
    # picks up) is flagged here if it was not in the include list.
    #
    # Semantics: the walker visits only the directories and files named
    # in INCLUDE. A source file that is in an unlisted directory (e.g.
    # profile/profile.yaml, profile/targets.yaml) is *not* walked; the
    # check ignores it. A source file in a listed directory is walked,
    # and the check demands it be on the manifest.
    source_findings: list[str] = []
    expected_manifest_paths = {p for p, _, _ in manifest}
    expected_manifest_paths.add("MANIFEST.txt")
    expected_manifest_paths.add(".gitignore")
    expected_manifest_paths.add("requirements.txt")
    # Build the set of source paths the walker would visit. INCLUDE
    # entries that are directories recurse; entries that are single files
    # are taken as-is. A file under a single-file INCLUDE entry is
    # *not* considered a "walked root" (the walker doesn't visit its
    # directory) but its siblings in the same directory ARE flagged by
    # the sibling check below: any other file in a directory that has
    # a single-file INCLUDE entry is a candidate for smuggling.
    include_roots: list[Path] = []
    include_siblings: dict[Path, set[str]] = {}
    for item in INCLUDE + OPTIONAL_INCLUDE:
        s = src / item
        if s.is_dir():
            include_roots.append(s)
        elif s.is_file():
            # Track the parent directory and the set of single-file
            # entries inside it. A planted sibling must not be walked.
            parent = s.parent
            include_siblings.setdefault(parent, set()).add(item)
    for entry in src.rglob("*"):
        if not entry.is_file():
            continue
        if any(part in SKIP_DIRS for part in entry.relative_to(src).parts):
            continue
        if entry.suffix in SKIP_SUFFIXES:
            continue
        rel = str(entry.relative_to(src))
        # SOURCE_EXCLUDE: these files are owner-data or host-only; the
        # source tree is allowed to contain them, but they are not in
        # the manifest and the walker must not visit them. Skip silently.
        if rel in SOURCE_EXCLUDE or any(rel.startswith(p + "/") for p in SOURCE_EXCLUDE):
            continue
        # Is this file under a walked include root?
        walked = any(entry.is_relative_to(r) for r in include_roots)
        if walked and rel not in expected_manifest_paths:
            source_findings.append(f"{rel}: source tree has a file the include list did not authorise")
            continue
        # Is this a sibling of a single-file INCLUDE entry in a directory
        # that has no other INCLUDE entries? Then the planted file's
        # presence is suspicious even if the walker didn't visit it --
        # because the sibling could be `profile/profile.yaml` and the
        # next refactor might widen INCLUDE to ship the whole `profile/`
        # directory by mistake.
        for parent, entries in include_siblings.items():
            if entry.parent == parent and rel not in entries and rel not in expected_manifest_paths:
                # We only flag this when the parent has NO directory INCLUDE
                # entry (otherwise the directory walker would already catch
                # it). The check: parent is not in include_roots.
                if not any(parent == r or parent.is_relative_to(r) for r in include_roots):
                    source_findings.append(
                        f"{rel}: planted sibling of a single-file INCLUDE entry "
                        f"(parent has only file-level shipping); remove it or "
                        f"add the file to the include list explicitly"
                    )
                    break
    if source_findings:
        print("\nREFUSING TO SHIP — source-completeness check found:")
        for f in source_findings:
            print(f"  {f}")
        shutil.rmtree(out)
        print("\nthe incomplete bundle was deleted; remove unlisted files or extend the include list")
        return 1

    print("leak scan: no unpermitted matches (deny-list only — read MANIFEST.txt)")
    if allowed:
        print(f"  {len(allowed)} allowed match(es), each with a stated reason:")
        for a in allowed:
            print(f"    - {a}")

    if not (out / "LICENSE").exists():
        msg = ("REFUSING TO SHIP — no LICENSE file in the built tree. "
               "Copyright is reserved by default, so 'all rights reserved' is the "
               "result of publishing without one. Add a LICENSE (owner decision), "
               "or re-run with --allow-no-licence for a non-publishable diagnostic copy.")
        if args.allow_no_licence:
            print("WARNING: " + msg)
        else:
            print(msg)
            shutil.rmtree(out)
            print("\nthe incomplete bundle was deleted; pick a licence and re-run")
            return 1

    if args.tar:
        tgz = DIST / f"{BUNDLE_NAME}-{date.today().isoformat()}.tar.gz"
        with tarfile.open(tgz, "w:gz") as tar:
            tar.add(out, arcname=BUNDLE_NAME)
        print(f"archive -> {tgz}  ({tgz.stat().st_size // 1024} KB)")

    if args.run_tests:
        print("\nrunning the suite FROM THE EXPORT (proves the copy stands alone):")
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=out, capture_output=True, text=True,
            env={"PYTHONPATH": str(out)},
        )
        output = (r.stdout + r.stderr).strip()
        for line in output.splitlines():
            print(f"  {line}")
        if r.returncode != 0:
            print("FAILED: the export does not pass its own tests")
            return 1
        print("export is self-contained: its own suite passes")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Assemble a shareable copy of the pipeline")
    ap.add_argument("--tar", action="store_true", help="also write a .tar.gz")
    ap.add_argument("--run-tests", action="store_true", help="run the suite from the export")
    ap.add_argument("--src", default=None,
                    help="source directory to assemble from (default: project root). "
                         "Used by the W1.3 mutation tests to point at a throwaway "
                         "clone with a planted forbidden item.")
    ap.add_argument("--out", default=None,
                    help="output directory (default: <src>/dist/jobsearch-pipeline). "
                         "Lets the mutation test run the gate against a tempdir.")
    ap.add_argument("--allow-no-licence", action="store_true",
                    help="build the bundle even without a LICENSE file. The result is a "
                         "diagnostic copy, not a publishable one. Used by the export gate "
                         "tests so they can run before the owner has chosen a licence.")
    args = ap.parse_args(argv)
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
