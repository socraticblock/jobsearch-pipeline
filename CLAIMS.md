# CLAIMS

Every public statement this project makes about itself. Each claim has a status,
a verification pointer, and a last-verified date. A claim without a passing
verification is a promise, not a fact.

## Status taxonomy

- **Current** — code on `main` proves it. The verification passes on the pinned
  SHA. This is the only status that can appear unqualified in the README.
- **Beta** — code on `main` proves it, but the surface has a known rough edge
  such that the public claim **must carry a load-bearing qualifier** to stay
  truthful. Beta claims may ship, only with that qualifier.
- **Roadmap** — not shipped. Roadmap claims appear only in `ROADMAP.md`; they
  never gate a README claim or a demo asset.

## Your rights as a user of this project

These hold regardless of any other change to this file. They are the project's
constitution; if a future change would break one, the change is wrong.

1. You are invisible by default. No network call is made without your explicit
   step.
2. The tool prepares. You decide. Nothing is sent, submitted or applied on
   your behalf; the decision path is human-only.
3. Your data is yours. Portable, exportable, deletable. The export gate exists
   so you can prove that.
4. The gate is honest. Missing evidence is `NEEDS_RESEARCH`, never a rejection.
   A 3+ year posting against a profile with no years field is unknown, not
   filtered.
5. You can leave at any moment, completely. The repo's import graph is
   auditable; no module talks to the network without a testable reason.
6. No recommendation. A `STRONG_MATCH` or `POTENTIAL_MATCH`
   verdict means the gate found nothing disqualifying; it
   is not advice to apply. A `NEEDS_RESEARCH` verdict is
   not a recommendation either -- it is the gate's
   honest report that a required field is missing or
   unclear, and the human's job to fill in.
7. No false-negative guarantee. The system will misclassify some postings.
   The goal is auditable uncertainty, not perfect recall.
8. The system never bypasses a third-party's controls: no CAPTCHA bypass, no
   login bypass, no rate-limit evasion, no anti-bot circumvention. A
   contribution that adds any of these will be rejected.

## Synthetic evidence standard

Synthetic data may illustrate product behaviour, drive screenshots, and prove
deterministic QA invariants, but it may never measure public performance,
speed, accuracy, or outcome claims. Any public measurement claim needs a
non-synthetic measurement source and a resolving pointer.

## The claims

### Privacy and containment (W1)

#### CL-001 — Current

The working copy contains a `jobsearch/.gitignore` with `*` so the personal-data
tree cannot be committed accidentally. The gitignore is the only thing keeping
personal data out of the public checkout; it is a tripwire, not a wall, and
that is named honestly.

- **Owner:** repo owner
- **Verification:** `tests/test_containment.py::TestW1_1_ContainmentGuard`
- **Last verified:** 2026-10-13

#### CL-002 — Current

The export gate at `scripts/export_bundle.py` builds the public artifact from a
known allowlist, refuses to copy any file whose path matches a deny pattern
(`/home/<user>`, `/Users/`, `/root/`, `C:\Users\`, anything ending in
`.pdf .db .sqlite .sqlite3 .log`), refuses to build without a `LICENSE`
file unless `--allow-no-licence` is set as a diagnostic override, and
deduplicates the manifest defensively so the "N files" header always
equals the real file count in the bundle. A file that lands in both
INCLUDE and OPTIONAL_INCLUDE is silently double-counted if the gate
does not dedup; the dedup is the gate's defense.

- **Owner:** repo owner
- **Verification:** `tests/test_export_gate.py` (full mutation matrix)
- **Last verified:** 2026-10-13

#### CL-003 — Current

The export gate's mutation matrix proves the gate fails closed on: a planted
`token.json` (regex `ya29.{20,}`), a planted `client_secret.json` (regex
`GOCSPX-`), a planted `.env`, a planted home-directory path, a planted PDF,
a planted file in a walked include directory that is not on the allowlist, a
planted profile file, and a missing `LICENSE`. The matrix also proves the
manifest has no duplicate paths and the "N files" header matches the real
file count, so a future reader trusting the header to plan a release
will not be silently over-counted.

- **Owner:** repo owner
- **Verification:** `tests/test_export_gate.py` (61 cases, incl.
  `test_manifest_has_no_duplicate_paths` and
  `test_cl_005_bundle_size_matches_manifest` and the new
  `TestForbiddenSuffixes` class that pins the gate's
  `FORBIDDEN_SUFFIXES` set and verifies each entry is exercised
  by a corresponding mutation test, and the new
  `TestDenyTokens` class that pins the gate's
  `DENY_TOKENS` list and verifies each personal-token
  pattern is exercised by a planted-file mutation test,
  and the new `TestDenyHomePatterns` class that pins
  the gate's `DENY_HOME_PATTERNS` list and verifies
  each home-path pattern is exercised by a
  planted-file mutation test, and the new
  `TestDenySecrets` class that pins the gate's
  `DENY_SECRET_PATTERNS` list and verifies each
  secret-shape pattern is exercised by a
  planted-file mutation test, and the new
  `TestExcludeList` class that pins the gate's
  `EXCLUDE` list and verifies the
  publication boundary actually keeps every
  EXCLUDE path out of the shipped artifact) and
  `tests/test_rules.py` (the
  `TestSpecialistTraps` class pins the
  `SPECIALIST_TRAPS` set and verifies
  each technology is tagged in the
  requirement meta; the
  `TestTechnologies` class
  pins the `TECHNOLOGIES`
  default vocabulary
  and verifies every
  entry is lowercase
  and unique) and
  `tests/test_profession_signals.py`
  (the
  `TestDefaultProfessionSignals`
  class pins the W3.4
  default English list
  and verifies every
  entry recognises a
  software title) and
  `tests/test_polarity.py`
  (the
  `TestPolarityRegexes`
  class pins the
  `MUST_WORDS`,
  `NICE_WORDS`, and
  `FLEX_WORDS` regexes
  and verifies every
  entry triggers the
  correct polarity
  classification; the
  `TestLanguages` class
  pins the `LANGUAGES`
  vocabulary and
  verifies every entry
  is detected by
  `extract_languages`)
  and
  `tests/test_actions.py`
  (the
  `TestActionVocabulary`
  class pins the M3
  shortlist action
  vocabulary and
  verifies every
  action has a
  non-empty meaning)
  and the
  `TestIncludeList`
  class in
  `tests/test_export_gate.py`
  that pins the
  `INCLUDE` and
  `OPTIONAL_INCLUDE`
  allowlists and
  verifies no path
  is in BOTH the
  allowlist and
  the blocklist
  and
  `tests/test_verdicts.py`
  (the
  `TestVerdictVocabulary`
  class pins the 4
  verdict constants
  and verifies each
  appears in CLAIMS.md
  and the PDF
  renderer's `_LABEL`
  dict)
  and
  `tests/test_location_scope.py`
  (the
  `TestLocationScopeRegexes`
  class pins the
  `EU_SCOPE` and
  `WORLD_OK` regexes
  and verifies each
  documented scope
  stem is matched)
  and
  `tests/test_rules.py`
  (the
  `TestDescriptionLengthThreshold`
  class pins the
  `MIN_DESCRIPTION_CHARS`
  constant and
  verifies it is
  positive and
  reasonable)
  and
  `tests/test_export_gate.py`
  (the
  `TestSkipDirs`
  class pins the
  gate's
  `SKIP_DIRS`
  cache-directory
  contract and
  verifies every
  documented
  cache dir
  is in the
  skip list)
  and
  `tests/test_python_version.py`
  (the
  `TestPythonVersionRequirement`
  class pins
  the doctor's
  `PY_MIN`
  constant and
  verifies it
  matches the
  README's
  stated
  minimum
  Python
  version)
  and
  `tests/test_enrich.py`
  (the
  `TestDefaultUserAgent`
  class pins
  the
  `DEFAULT_UA`
  HTTP
  user-agent
  string and
  verifies it
  is a real
  Chrome
  browser UA
  with no
  personal
  data and no
  bot tokens)
  and
  `tests/test_dataflow_regexes.py`
  (the
  `TestDataflowRegexes`
  class pins
  the 4
  network-direction
  classifier
  regexes
  in
  `tools/build_dataflow_map.py`:
  PARSE_ONLY,
  UNKNOWN_NETWORK,
  OUTBOUND,
  INBOUND -- the
  classifier
  that drives
  `docs/DATA-FLOW.md`)
  and
  `tests/test_rules.py`
  (the
  `TestCurrencyConstants`
  class pins
  the
  `_CURRENCY_ALIAS`
  and
  `_NOT_A_CURRENCY`
  salary-parser
  constants)
  and
  `tests/test_enrich.py`
  (the
  `TestMarkupRegexes`
  class pins
  the
  `_MARKUP_RE`,
  `_SECTION_RE`,
  `_CLAMP_RE`,
  and
  `_APPLY_PATH`
  LinkedIn
  markup-parser
  constants --
  the regexes
  the
  description
  extractor
  was
  designed
  against
  per the
  "verified
  against a
  live page
  on
  2026-10-13"
  comment
  in
  enrich.py
  L54)
  and
  `tests/test_db_schema.py`
  (the
  `TestDatabaseSchema`
  class pins
  the 7-table
  + 3-index
  SQLite
  schema and
  the
  `SCHEMA_VERSION`
  constant in
  `jobsearch/db.py`
  -- the data
  layout the
  rest of the
  code reads
  and writes)
  and
  `tests/test_parse_alert_constants.py`
  (the
  `TestParseAlertConstants`
  class pins
  the 5 most
  contract-critical
  alert-parser
  constants in
  `jobsearch/parse_alert.py`:
  `_BOILERPLATE`
  -- the
  alert-injection
  contract
  that
  prevents
  phantom-job
  injection,
  `_JOB_URL`,
  `_CARD_MARK`,
  `_BLOCK_SEP`,
  and
  `_VIEW_LABEL`)
  and
  `tests/test_legal_suffix.py`
  (the
  `TestLegalSuffix`
  class pins
  the
  `_LEGAL_SUFFIX`
  company-name
  dedup regex
  in
  `jobsearch/normalize.py`
  -- the 17
  legal-form
  suffixes
  stripped
  from
  company
  names
  for the
  fallback
  dedup key)
  and
  `tests/test_software_signal.py`
  (the
  `TestSoftwareSignal`
  class pins
  the
  `_SOFTWARE_SIGNAL`
  software-profession
  classifier
  regex in
  `jobsearch/rules.py`
  -- the 45
  software-related
  terms
  matched
  by job
  titles)
  and
  `tests/test_years_parser.py`
  (the
  `TestYearsParser`
  class pins
  the
  `_YEARS`
  years-of-experience
  parser regex
  in
  `jobsearch/requirements.py`
  -- the W3.1
  years-of-experience
  contract)
- **Last verified:** 2026-10-13

#### CL-004 — Current

The history audit at `tools/audit_public_history.sh` runs against the live
public repo and reports clean when no `jobsearch/`, `var/`, or token-shaped
string appears in HEAD, reachable history, stashes, or dangling objects.

- **Owner:** repo owner
- **Verification:** `tests/test_history_audit.py`
- **Last verified:** 2026-10-13

#### CL-005 — Current

The shipped bundle is 149 files (the 141st is `tests/__init__.py`, an empty
marker that lets the export gate's own test self-import work under the
project's own `unittest discover` walker; the 142nd–144th are the
`docs/README.md` and `docs/adr/000-template.md` Open-Ready scaffold files
shipped alongside the tracked project documents via the `docs` directory
allowlist), builds with no LLM dependency,
runs its own 576-test suite standalone from `dist/jobsearch-pipeline`, and is
self-contained enough to be the public artifact a third party runs.

- **Owner:** repo owner
- **Verification:** `bash tools/verify.sh` step 5 (bundled suite)
- **Last verified:** 2026-10-13

### Credentials and data flow (W2)

#### CL-006 — Current

The only network-capable modules in `jobsearch/` are the OAuth handshake
(`tools/google/auth.py`) and the Gmail read API (`tools/google/fetch_alerts.py`).
No module in the sieve or rule path opens a socket, makes an HTTP request, or
imports a network primitive.

- **Owner:** repo owner
- **Verification:** `tests/test_no_bundled_credentials.py`,
  `tests/test_scope_freeze.py` (AST-based allowlist)
- **Last verified:** 2026-10-13

#### CL-007 — Current

The OAuth scope freeze is enforced by an AST test that distinguishes request
constants (`SCOPES`, `READONLY_SCOPE`) from refusal constants (`WRITE_SCOPES`).
The only scope the client requests is `gmail.readonly`. A refusal list may
name write scopes (correct behaviour), but a request list may not.

- **Owner:** repo owner
- **Verification:** `tests/test_scope_freeze.py` (3 cases, AST-aware)
- **Last verified:** 2026-10-13

### Gate honesty (W3)

#### CL-008 — Current

The deterministic gate never produces a `NOT_SUITABLE` verdict from missing
evidence. When a profile field is unset or a rule's input is `None`, the
verdict is `NEEDS_RESEARCH` ("we don't know"), not a rejection. The years
field is the worked example: unset → `NEEDS_RESEARCH`; set to 3 → drop
5+ year postings; set to 5 → accept 5+ year postings.

- **Owner:** repo owner
- **Verification:** `tests/test_rules.py::TestYearsPolicy` (3 cases)
- **Last verified:** 2026-10-13

#### CL-016 — Current (W3.3)

The digest's coverage line states the four counts a reader needs: how
many postings were read, how many had a description retrieved, how many
could not be judged (no description), how many surfaced, and how many
dropped. A posting with `description_state != "complete"` routes to a
`not_judged` bucket (not to `surfaced` or `dropped`) with a reason;
a "NOT YET RETRIEVED" section lists each unretrieved posting with its
link. A reader who sees "12 surfaced, 5 not yet retrieved" knows the
gate never had a description for 5 postings — those are awaiting a
fetch, not a verdict. A contributor who drops the `not_judged` count
or who lets incomplete-description postings surface as
`needs_research` fails the build. The contract is enforced by
`tests/test_coverage.py` (7 tests: 5-tuple return, four-count stats,
incomplete routing, complete routing, coverage line, NOT YET RETRIEVED
section, ledger-partition invariants).

- **Owner:** repo owner
- **Verification:** `tests/test_coverage.py` (7 tests)
- **Last verified:** 2026-10-13

#### CL-017 — Current (W3.4)

The profession-signal vocabulary (the title words that indicate a
software role) lives in the profile, with a documented English default
exposed as `jobsearch.rules._DEFAULT_PROFESSION_SIGNALS`. A non-English
candidate adds their own list to `profile.yaml` (`profession_signals:`
at the top level or under `location_and_arrangement:`) without editing
code. The contract is enforced by `tests/test_profession_signals.py`:
the default English list catches every common software title word; a
non-English title (e.g. "Softwareentwickler", "Développeur") is missed
by the default; a profile with German or French signals recognises
the locale's software title; and a non-software German title
("Verkäufer" = salesperson) is still rejected with the augmented
profile (the override is a positive list, not a language whitelist).
The W3.4 corpus fixtures (c-019, c-020, c-021) and the regression test
together prevent a future contributor from hardcoding a locale word
into the gate.

- **Owner:** repo owner
- **Verification:** `tests/test_profession_signals.py` (11 tests);
  the `TestDefaultProfessionSignals` class pins
  the W3.4 default English list (48
  documented entries, every entry
  recognises a software title) and
  prevents silent removal of
  common words like "engineer"
  corpus fixtures c-019, c-020, c-021 in `corpus/v1/postings.json`
- **Last verified:** 2026-10-13

#### CL-009 — Current (W3.2)

Every `failed_essential` entry in the gate's output carries a quoted snippet
from the posting that explains the rejection. The snippet is the evidence;
without it, the verdict does not exist. The contract is enforced by
`tests/test_evidence_quote.py`: every failure has a quoted phrase; the
quoted phrase is a real substring of the title or body; non-title failures
include a real sentence (3+ words), not a single keyword; and the c-011
PHP/WordPress regression case cites a real sentence from the body. A
contributor who lets the gate "quote" a single keyword (a fabricated
label, not real evidence) fails the build. Title-based failures may quote
the short title itself (the title IS the evidence for a title-based
failure).

- **Owner:** repo owner
- **Verification:** `tests/test_evidence_quote.py` (4 tests)
- **Last verified:** 2026-10-13

#### CL-010 — Current

The synthetic fixture corpus in `corpus/` carries a `SYNTHETIC ONLY` header
on every file. A test refuses any fixture file that lacks the header. This
makes "no real-user data ever ships in a fixture" enforceable by build.

- **Owner:** repo owner
- **Verification:** `tests/test_synthetic_only.py`
- **Last verified:** 2026-10-13 (this revision)

#### CL-011 — Current

A labelled counterexample corpus (`corpus/v1/postings.json`) of synthetic
postings, each with an `id`, `expect` verdict, and a `why` field naming the
failure category, is the public artefact that makes the gate auditable.
This is the second-instance pattern from inbox-job-tracker's response-classification
corpus, applied to posting classification. The corpus ships 22 fixtures
covering all four verdict bands (`strong_match`, `potential_match`,
`needs_research`, `not_suitable`) and all five requirement kinds
(experience_years, seniority, location, language, technology). The W3.4
fixtures (c-019, c-020, c-021) exercise a non-English title vocabulary.

- **Owner:** repo owner
- **Verification:** `tests/test_corpus.py` (full corpus contract;
  shape, end-to-end verdict match, band coverage, requirement-kind
  coverage, gate-rule coverage, name↔verdict agreement)
- **Last verified:** 2026-10-13

### Failure modes (W4)

#### CL-023 — Current (W4.6)

The ledger survives a full disk, a truncated DB, and a
half-written WAL. The contract:
  * **Full disk during ingest:** `jobsearch/ingest.py::ingest_message`
    wraps the `con.commit()` call in a try/except. On
    `OperationalError` (ENOSPC, IO error, read-only DB, lock
    timeout), the open transaction is rolled back so the ledger
    is in the pre-failure state, and the original error is
    re-raised. The morning-prepare maps that to exit 1 with a
    recorded reason. The contract is enforced by
    `tests/test_storage_failure.py::TestFullDisk`.
  * **Truncated DB:** SQLite refuses to open a truncated DB with
    a clear `DatabaseError` (e.g. "file is not a database",
    "database disk image is malformed"). The next reader fails
    fast; the corruption is not silently masked. The contract
    is enforced by `tests/test_storage_failure.py::TestTruncatedDb`.
  * **WAL recovery:** with `journal_mode=WAL`, a row written in
    one connection is visible in a second connection that opens
    the DB file and replays the WAL. The crash-safe guarantee
    SQLite provides for embedded use is the right primitive
    for the morning-prepare pipeline. The contract is enforced
    by `tests/test_storage_failure.py::TestWalRecovery`.
  * **Loud failure mode:** a truncated DB never silently returns
    an empty result. A reader that opens a truncated DB MUST
    raise `DatabaseError`; the next morning-prepare sees a
    clear error, not a "no new jobs" digest. The contract is
    enforced by
    `tests/test_storage_failure.py::TestStorageFailureIsLoud`.

- **Owner:** repo owner
- **Verification:** `tests/test_storage_failure.py` (8 tests)
- **Last verified:** 2026-10-13

#### CL-022 — Current (W4.5)

The next-fire-time for the morning-prepare cron stays on 08:00
local across a DST boundary. `tools/next_fire.py` is a pure
function over Python's `zoneinfo` module: `next_fire(now,
target_hour=8, tz_name="Europe/Berlin")` returns the next
datetime whose local hour is 8 in the target timezone.
Across the spring-forward 2026-03-29 boundary (Europe/Berlin:
02:00 → 03:00, day is 23 hours), the helper still picks
08:00 the same day. Across the fall-back 2026-10-25 boundary
(02:00-03:00 happens twice), the helper picks 08:00 the same
day; the second-occurrence of an earlier hour does not
confuse the calculation. The default timezone is
`Europe/Berlin`; an operator in another timezone overrides
via `--tz`. The morning-prepare run report prints the
next-fire time so the morning heartbeat (W4.2) shows when
the next run is expected. The contract is enforced by
`tests/test_next_fire.py` (14 tests: today-before-eight,
today-after-eight, exactly-at-eight, spring-forward both
sides, fall-back both sides, naive-now-is-UTC, unknown-timezone,
invalid-hour, different-timezone, midnight-target, default-tz,
UTC-tz).

- **Owner:** repo owner
- **Verification:** `tests/test_next_fire.py` (14 tests)
- **Last verified:** 2026-10-13

#### CL-021 — Current (W4.4)

The morning-prepare run acquires an exclusive non-blocking
file lock on `var/morning-prepare.lock` before doing any
work. A second invocation that finds the lock held exits 3
with a recorded reason (`RUN_ALREADY_IN_PROGRESS: another
morning-prepare is holding the run lock; refusing to start
a second run`) so the morning heartbeat (W4.2) catches the
overlap. The lock is released automatically when the
file descriptor is closed (end of the with-block) and on
process termination (the kernel reclaims the fd), so a
crashed run does not strand the lock. The contract is
enforced by `tests/test_run_lock.py` (6 tests: a second
acquire is refused; the lock releases on process exit;
two concurrent morning_prepare invocations do not
double-deliver; a render failure inside the lock-holding
block still releases the lock; the happy-path run
produces a digest and prints the next-fire time; a
missing ledger returns exit 2 so the morning heartbeat
sees a broken fresh checkout).

- **Owner:** repo owner
- **Verification:** `tests/test_run_lock.py` (6 tests)
- **Last verified:** 2026-10-13

#### CL-020 — Current (W4.3)

The Gmail API call gets bounded exponential backoff on 429 and 5xx
(500, 502, 503, 504). The retry loop in `tools/google/fetch_alerts.py`
caps at 5 attempts, with delays of 1s, 2s, 4s, 8s (then 16s would
follow but the cap is reached first). A 4xx other than 429 is a hard
fail: the token is broken or revoked, and retrying just wastes the
user's quota. The run report (`mailbox=READ_OK`, `retried=N`,
`retry_exhausted=N`) names the retry counts so a reader can see how
many 429s were absorbed. After the cap, the run exits 4 with the
reason `API_RETRY_EXHAUSTED`. The fetch path is bounded retry only:
the test `test_no_evasion_in_the_fetch_path` does a tree scan of
`tools/google/` and refuses any import of a proxy rotator, a UA-spoof
helper, a captcha solver, or a headless-browser automation library.
A contributor who copy-pastes a bypass primitive from a blog post
fails the build.

- **Owner:** repo owner
- **Verification:** `tests/test_bounded_retry.py` (7 tests:
  429 retries then succeeds, exhaustion after max attempts,
  4xx-other-than-429 does not retry, 5xx is retried, ConnectionError
  is retried, backoff doubles each attempt, no evasion primitives
  in the fetch path)
- **Last verified:** 2026-10-13

#### CL-012 — Current

The `verify.sh` one-shot at `tools/verify.sh` runs the full test suite, the
suite under `-O`, the export gate, the live history audit, and the bundled
suite, and reports all five steps as pass-or-fail in a single run.

- **Owner:** repo owner
- **Verification:** `bash tools/verify.sh` (5 steps, all green)
- **Last verified:** 2026-10-13

#### CL-013 — Current

The external-content fetch path is bounded: one attempt per source, no retry,
`UNCONFIRMED` on failure. A retrying loop in the fetch path is a build failure.
This applies to *posting fetches* (each alert URL is fetched exactly once
per run; a 404 or empty body marks the posting UNCONFIRMED and the run
moves on). It does NOT apply to the *Gmail API call itself* — a 429 from
the API is a backoff signal (W4.3), not a content-failure signal. The
distinction matters: the URL boundary is the line we never cross twice,
because crossing it turns into bot detection; the API boundary IS ours
to back off from.

- **Owner:** repo owner
- **Verification:** `tests/test_fetch_guard.py`
- **Last verified:** 2026-10-13

### Legal boundary (W6)

#### CL-014 — Current

The third-party bypass rule is in the project's rights list above and in
`DISCLAIMER.md`. No module in `jobsearch/` imports a CAPTCHA solver, a
login-bypass library, a headless-browser detection-evasion package, or any
of the obvious bypass primitives. A contribution that adds one is rejected.

- **Owner:** repo owner
- **Verification:** import-graph scan + manual review of
  `tests/test_no_bundled_credentials.py`
- **Last verified:** 2026-10-13

### Release discipline (W7)

#### CL-015 — Current

The release privacy gate is wired into a GitHub Actions workflow at
`.github/workflows/release-privacy.yml` (not `release-check.yml` — that
was an earlier proposed name; the shipped file is `release-privacy.yml`,
asserted by `tests/test_release_workflow.py::test_workflow_file_exists`).
The workflow has two jobs: `verify` runs `bash tools/verify.sh` (the
local verify chain), and `privacy` scans the built tree for leaks.
Both jobs run on every push to `main` and on every PR; a failed check
blocks the merge. The action does NOT pass the `--allow-no-licence`
override (asserted by `test_workflow_does_not_silently_bypass_licence`),
so a missing `LICENSE` is a build failure, not a quiet green.

The action is also the second-instance pattern: the local export gate
(W1.3) is the first safeguard on the owner's machine, and the CI run
on a clean machine is the second pair of eyes. A contributor who
forks the repo and never clones the owner's machine still has to
pass this gate.

- **Owner:** repo owner
- **Verification:** `tests/test_release_workflow.py` (13 tests:
  file exists, YAML parses, both jobs present, runs on push and PR,
  no licence-bypass override, checkout v4 only, release handle is
  printed, release handle is stable on rebuild, release handle
  changes when source changes, release handle exits 2 on a
  missing export directory, release handle --hex prints just the
  hash, release handle --hex mode also exits 2 on a missing dir,
  release handle exits 2 on no arguments)
- **Last verified:** 2026-10-13

#### CL-018 — Current (W5.2)

`tools/doctor.py` is the first command a fresh checkout runs. It checks
22 preconditions (Python version, PyYAML, reportlab optional, corpus
well-formed, profile optional, export-bundle consistency, verify.sh
executable, package importable, var/ writable, digests/ writable,
rule_why sync, tool loadability) and reports a one-line fix per failure. Exits 0 on pass, 1
on any failure; supports `--quiet` for CI and `--json` for machine
readers. No network I/O. The doctor also runs as Step 0 of
`tools/verify.sh`, so a broken env fails fast before the unittest
discovery even starts. A contributor who adds an environment
dependency without updating the doctor fails the build.

- **Owner:** repo owner
- **Verification:** `tests/test_doctor.py` (12 tests, including
  the mutation tests that prove the doctor detects a missing
  corpus, a non-executable verify.sh, a missing PyYAML, etc.,
  on a fresh /tmp copy; plus a contract test that pins the
  number of preconditions at >= 22 and the specific set of
  22 check names so CL-018 cannot drift; plus a
  stripped-environment test that blocks PyYAML and reportlab
  and asserts every failure is named with a real fix)
- **Last verified:** 2026-10-14

#### CL-019 — Current (W5.3)

`tools/demo_sieve.py --batch` is the credential-free demo. A fresh
reader runs it and sees the gate run on every corpus fixture with
no `.eml` files, no Google setup, no profile editing required. The
output is a digest-style summary: how many fixtures evaluated, the
verdict distribution across all four bands, a per-fixture verdict
line with `ok`/`DRIFT`, and a count of drift. Drift is the build
failure: if the corpus says "c-019 → strong_match" and the gate
produces "not_suitable", `--batch` reports the drift and exits
non-zero. The contract is enforced by
`tests/test_demo_sieve.py::test_batch_mode_runs_every_fixture`.

- **Owner:** repo owner
- **Verification:** `tests/test_demo_sieve.py` (13 tests, including
  the batch-mode drift check, the empty-stdin exit-2 contract,
  the unknown-corpus-id exit-2 contract, and the three --json
  caller-error exit-2 contracts: missing file, malformed JSON,
  missing required field)
- **Last verified:** 2026-10-13

#### CL-024 — Current (W5.4)

`tools/first_run.py` shows the whole pipeline, not just the gate: it ingests a
shipped sample alert email with the real parser, runs the real enrichment step
(`enrich_one`, with the page bytes read from a shipped synthetic file instead of
an HTTP GET), judges the postings with the real gate, and prints the real
shortlist digest. It runs with no profile of the reader's own, no mailbox, no
Google account and no network call, and it never reads or writes the real
ledger (`var/jobs.db`): it builds a throwaway one under `var/first-run/`, or
wherever `--run-dir` points. The sample it reads lives in `fixtures/first_run/`
and every file in it declares itself synthetic.

The claim is narrow on purpose: this is a walkthrough of shipped synthetic
data, and it proves the *plumbing* end to end. It does not measure the gate's
accuracy, and it is not evidence about a reader's own postings. What it does
make checkable is the join between stages -- the alert parser, the
description-state transition, the gate and the renderer -- which is the seam
the shipped per-stage tests each cover only on their own side.

- **Owner:** repo owner
- **Verification:** `tests/test_first_run.py` (11 tests: runs and exits 0,
  digest shows a strong match with its quoted evidence, an incomplete
  description is NEEDS_RESEARCH and not a drop, a failed essential is dropped
  and counted, the real ledger is byte-identical afterwards, only the run
  directory is written, the run directory is regenerable, no network
  primitives in the source, every shipped sample file declares itself
  synthetic, and the narration names the enrichment step)
- **Last verified:** 2026-10-14

#### CL-025 — Current

`jobs.salary_text` is filled from the posting's own text, and from nothing
else. The enrichment step reads the page it actually fetched, takes the first
line or sentence that states a pay amount, and stores that line verbatim:
no normalisation, no currency conversion, no invented figure. A page that
states no amount leaves the column `NULL`, and the digest then says "not
published". The gate ranks and flags from this field and never rejects on it:
a posting below the floor is surfaced with the figure quoted, and a posting in
another currency is flagged `needs_conversion` rather than converted at an
invented rate.

Until this was wired, the column existed, the renderer read it, the unit tests
set it by hand -- and no code path in the pipeline ever wrote it, so every real
posting read "no salary published" and neither flag could fire on a real run.

- **Owner:** repo owner
- **Verification:** `tests/test_enrich.py::TestPayReachesTheGate` (5 tests
  running fetch -> extract -> store -> render: the pay line is stored verbatim,
  no statement leaves the field empty, below-floor is flagged and the job is
  still rendered, above-floor is not flagged, a foreign currency is stored
  verbatim and flagged for conversion), plus `tests/test_m3.py` for the
  renderer's flag wording
- **Last verified:** 2026-10-14

#### CL-026 — Current

Work authorisation is declared, never inferred. The gate reads
`location_and_arrangement.authorization.work_authorisation` from the profile
and nothing else -- not citizenship, not residence, not a country named in a
posting. With the list empty, a posting scoped to the EU (or to any country)
reports `NEEDS_RESEARCH` with a "location scope to verify" reason. With a list
that covers the scope, the requirement is satisfied and the digest quotes the
declared scopes back. With a list that excludes the scope, the posting is a
hard drop whose failure line names the declaration it contradicts. Matching is
whole-word, so a declaration of `us` does not satisfy `Australia`.

Before this, every user was told "EU scope satisfied by citizenship with EU
work authorisation" whether or not they were EU citizens and whether or not
they had filled anything in -- a legal fact about a person that no input
supplied. `tests/test_rules.py` pinned that behaviour, which is why a green
suite was not evidence it was right.

- **Owner:** repo owner
- **Verification:** `tests/test_rules.py` (EU scope satisfied only when
  declared; no declaration is NEEDS_RESEARCH; a declared scope that excludes
  the place is a drop quoting the declaration; short tokens do not match by
  substring; the 28-country EU loop and the 17-country block loop),
  `tests/test_location_scope.py`, `corpus/v1/postings.json` (c-010, c-022)
- **Last verified:** 2026-10-14

#### CL-027 — Current

`profile/profile.starter.yaml` is the five-field profile a new reader can copy
to `profile/profile.yaml` and run. Its fields are all read by the gate -- a
starter key the gate ignores is a trap, and a test refuses one -- and each one
carries a one-line note saying what happens when it is absent (the gate reports
NEEDS_RESEARCH and names the missing input rather than guessing). The starter
names no person, city or figure of the author's: it carries placeholder values
and ships in the public artifact beside the long-form reference.

- **Owner:** repo owner
- **Verification:** `tests/test_starter_profile.py` (7 tests: the file exists,
  parses, carries only keys the gate reads, reaches the loader as written,
  judges a posting from five fields, carries no personal data, and the
  long-form reference documents the authorisation field), plus the export
  gate's deny-token scan over the shipped tree
- **Last verified:** 2026-10-14

## Maintenance

When public behaviour changes, update the affected claim's status, verification
pointer, and last-verified date. A claim that loses its verification is a
**Beta** until the verification is restored, and a **Roadmap** if the work
departs.

The synthetic-evidence standard and the rights list above are not claims; they
are constitution. Changes to either require a new commit and a note in
`CHANGELOG.md`.
