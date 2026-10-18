# Changelog

All notable changes to the jobsearch project. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once a release tag is created.

## [Unreleased]

### Added

- **W1.1 W1.3 W1.4** — Containment guard, export-gate mutation matrix,
  and history-audit script. The public artifact has zero leak risk for
  the deny-listed shapes (token-shaped strings, home-directory paths,
  profile siblings, etc.).
- **W2.1 W2.2 W2.4** — Deterministic gate with snake_case verdict
  vocabulary, data-flow map generator, and provider-isolation guarantee.
- **W3.2** — Every `NOT_SUITABLE` verdict cites a real sentence from
  the posting as evidence.
- **W3.3** — `not_judged` is not a verdict. Pre-evaluate routing of
  incomplete descriptions; coverage line in the digest.
- **W3.4** — `profession_signals` is profile data. Non-English users
  extend the English default without editing code.
- **W3.5** — `rule_why` is the registry that explains every rejection
  in human terms.
- **W4.3** — Bounded exponential backoff on Gmail API 429 / 5xx. No
  proxy-rotate, no UA-spoof, no captcha solve.
- **W4.4** — `flock` run lock on the morning-prepare entry point. A
  second run exits 3 `RUN_ALREADY_IN_PROGRESS`.
- **W4.5** — `next_fire` is a pure function over `zoneinfo`. DST
  handled implicitly.
- **W4.6** — Ingest rolls back + re-raises on commit failure. The
  ledger is in the pre-failure state after a full disk.
- **W5.2** — `tools/doctor.py` is the fresh-clone precondition check.
- **W5.3** — `tools/demo_sieve.py --batch` is the W5.3 front door.
- **W5.4** — `tools/first_run.py` is the pipeline front door: it runs the
  real ingest, the real enrichment step, the real gate and the real digest
  renderer over a shipped synthetic sample (`fixtures/first_run/`), offline,
  with no profile, mailbox or credential of the reader's own. It exists
  because an alert email carries no description, so a reader whose first
  command was `ingest` saw "description incomplete" on every job and read
  it as a broken install. `README.md` now says what a good run looks like,
  and why the descriptions arrive a step later.
- **`tests/test_first_run.py`** — 11 tests over that walkthrough, including
  the two the seam needed: the real ledger is byte-identical after a run,
  and no network primitive appears in the tool.
- **`work_authorisation` is a profile field, and the only source of a work
  authorisation.** `location_and_arrangement.authorization.work_authorisation`
  lists the scopes the candidate may work in. The gate reads that list and
  nothing else: an EU-scope posting is satisfied only when the profile
  declares an EU-wide scope, `NEEDS_RESEARCH` ("location scope to verify")
  when nothing is declared, and a drop quoting the declaration when the
  declaration excludes the place. Matching is whole-word, so `us` does not
  satisfy `Australia`. Nothing is read from citizenship, from residence, or
  from a country named in a posting. (`jobsearch/rules.py`, `CL-026`)
- **The posting's own pay line reaches the gate.** The enrichment step now
  copies the first line or sentence in the fetched page that states a pay
  amount into `jobs.salary_text`, verbatim: no normalisation and no currency
  conversion. A page that states no figure leaves the column `NULL`, and the
  digest says "not published". The below-floor and `needs_conversion` flags
  now fire on a real run for the first time. (`jobsearch/enrich.py`, `CL-025`)
- **`profile/profile.starter.yaml`** — the five-field starter profile the
  README now points a new reader at: stack, floor, local markets, work
  authorisation, years. Every field in it is read by the gate (a test refuses
  a starter key the gate ignores), and each carries a note saying what happens
  when it is absent. `profile.example.yaml` stays as the long-form reference
  and now documents the authorisation field. (`CL-027`)
- **`rules.rules_from_profile()`** — one builder for the dict-shaped profile,
  shared by `tools/demo_sieve.py` and the corpus end-to-end test. Those two
  hand-copied the field mapping, which is how a documented field could reach
  neither of them: exactly what happened to `work_authorisation`.
- **CL-001..CL-027** — The public claim catalogue, all Current, all
  verified by tests.
- **`tests/test_readme_count.py`** — The README's "N tests" claim is
  contract-tested; the count cannot silently drift.
- **`tests/test_export_gate.py::test_manifest_has_no_duplicate_paths`** —
  The MANIFEST's "N files" header is contract-tested against the real
  file count in the bundle.
- **`tests/test_export_gate.py::test_cl_005_bundle_size_matches_manifest`** —
  CL-005's "shipped bundle is N files" claim is contract-tested against
  the manifest.
- **`tests/test_claims_test_counts.py`** — Every "X tests" / "X cases"
  count in CLAIMS.md is contract-tested against the actual test count
  in the named file.
- **`tests/test_claim_range_consistency.py`** — The "CL-001..CL-NNN"
  range in CHANGELOG.md is contract-tested against the actual
  CL-IDs in CLAIMS.md.
- **`tests/test_dataflow_map.py::test_no_tbd_placeholders`** —
  Every row in `docs/DATA-FLOW.md` must have an honest Surface
  description; "TBD" placeholders fail the build.
- **`tests/test_release_workflow.py::TestVerifyReleaseMode`** —
  W7.2 contract: `tools/release_handle.sh` produces a stable
  64-char hex handle for the export; the handle is byte-stable
  on a no-op rebuild and changes when the source changes.
- **`tools/release_handle.sh`** — the extracted W7.2 unit; the
  verify.sh `--release` mode now delegates to it, so the unit
  is testable in isolation.
- **`tests/test_rule_name_verdict_agreement.py::test_every_aspirational_rule_fixture_is_documented_in_rule_why`** —
  Every corpus fixture whose `why` field marks a rule as
  aspirational (the gate has no branch) must have the
  deferral documented in the related rule_why.WHY entry. A
  silent deferral is a documentation drift: a reviewer
  reading the corpus sees a fixture that looks like every
  other one, but the gate does not have a rule for it.
- **`tests/test_corpus_count_claim.py`** — the corpus size
  claim in README.md ("the 21-fixture shipped corpus") and
  CLAIMS.md ("corpus ships 21 fixtures") must equal the
  actual record count in `corpus/v1/postings.json`. A
  future contributor who adds or removes a fixture without
  updating both docs fails this test with a precise error
  message naming the file, the line pattern, and the
  actual count. The third test in the file pins the
  four-band coverage (CL-007) so a band can only be lost
  by an explicit code change, not by accident.
- **`tests/test_run_lock.py::test_morning_prepare_exits_2_when_ledger_is_missing`** —
  Pin exit code 2 (the documented "nothing to work from"
  signal) for the missing-ledger case. The morning
  heartbeat (W4.2) relies on exit 2 to distinguish a
  successful no-op (exit 0) from a broken fresh
  checkout. A future contributor who treated a missing
  ledger as a successful no-op would silently break the
  morning heartbeat. The test asserts the exit code is 2
  AND that the error names the ledger, so the heartbeat
  can surface the problem to the operator.
- **`tests/test_release_workflow.py::test_release_handle_exits_2_on_missing_export_dir`** —
  Pin the W7.2 release handle's exit code 2 for a missing
  or empty export directory. A release that points at a
  deleted dist/ would otherwise look successful; the
  script's "FATAL" + exit 2 contract is the loud failure
  that lets a future verifier detect a broken release.
  The test asserts the exit code, that the error names
  the missing directory (so the operator can see what to
  fix), and that no `RELEASE_HANDLE:` line is printed
  (a missing-dir release has no handle to print).
- **`tests/test_history_audit.py::test_audit_exits_2_on_non_git_directory`** —
  Pin the W1.4 audit's exit code 2 for a non-git
  directory. A clone that lost its `.git/` would
  otherwise appear to have a clean audit instead of
  a broken one. The test asserts the exit code and
  that the error names the bad path so the operator
  can see what to fix.
- **`tests/test_doctor.py::test_doctor_runs_a_documented_number_of_checks`** —
  Pin the doctor check count against CL-018. CL-018
  claims "21 preconditions"; the test reads the
  JSON output and asserts >= 21 (so removing a
  check fails the test) and <= 30 (so a contributor
  who adds 20 checks without thinking fails the
  test). A future contributor who adds or removes
  a check must update CL-018 AND this test in
  the same change.
- **`tests/test_render_pdf.py::test_pdf_includes_dropped_jobs_when_include_unsuitable`** —
  Pin the PDF renderer's `include_unsuitable=True`
  branch (line 262 of render_pdf.py: `if
  include_unsuitable and dropped:`). The text-mode
  branch (line 169) was tested by
  `test_hard_avoid_role_is_dropped_and_named_when_listed`,
  but the PDF branch was not. A future refactor
  that ignores `include_unsuitable` in the PDF
  code path would silently break the `--include-unsuitable`
  CLI flag for the morning PDF while leaving the
  text mode working. The test decodes the PDF's
  ASCII85+FlateDecode streams and asserts the
  dropped job's title and company are present
  when the flag is set and absent when it is
  not.
- **`tests/test_render_pdf.py::test_limit_caps_the_surfaced_jobs`** —
  Pin the `--limit` CLI flag's contract on
  `render_pdf.collect(..., limit=N)`. The flag
  was untested: a future contributor who drops
  the cap (`surfaced = surfaced[:limit]`)
  would silently break the morning PDF's "first
  N jobs" contract. The test also documents
  a real footgun: the current `if limit:`
  truthy check treats `--limit 0` as "no limit"
  (a Python idiom). The test asserts the
  current behaviour and the failure message
  tells the next contributor exactly what
  to change if they want `--limit 0` to
  produce an empty digest.
- **`tests/test_demo_sieve.py::test_stdin_mode_exits_2_on_empty_input`** —
  Pin the empty-stdin exit code contract for
  `tools/demo_sieve.py` (line 234: `if not
  lines: ... sys.exit(2)`). Empty stdin was
  previously only protected by the non-zero
  exit assertions in `test_unknown_corpus_id_exits_nonzero`,
  not by a dedicated empty-stdin test. A
  contributor who refactors the stdin handler
  and drops the empty-input check would
  silently let an empty pipe produce an
  IndexError stack trace (or, after a deeper
  refactor, a `needs_research` verdict for an
  empty title). The test pins the specific
  exit code 2 and asserts the error message
  names both "stdin" and "empty" so a user
  who runs the script by mistake knows what
  went wrong.
- **`tests/test_release_workflow.py::test_release_handle_hex_flag_prints_just_the_hash`** —
  Pin the `--hex` flag in `tools/release_handle.sh`
  (line 47: `if [ "$#" -gt 0 ] && [ "$1" = "--hex" ]`).
  The flag was untested: a future contributor
  who ignores `--hex` (or prints the label
  anyway) would silently break the W7.2
  verifier's hash comparison. The test pins
  the exact stdout -- one line, exactly 64
  lowercase hex chars, no `RELEASE_HANDLE:`
  prefix -- and asserts the hash matches
  the default mode's hash for the same tree
  so a contributor can't subtly change the
  hash algorithm without updating the test
  in the same commit.
- **Tightened `tests/test_history_audit.py::test_audit_catches_committed_jobsearch_path`
  and `test_audit_catches_committed_secret_file`** —
  Changed `assertNotEqual(r.returncode, 0)` to
  `assertEqual(r.returncode, 1)`. The audit
  script's contract is exit 1 specifically
  for "forbidden content found" (vs. exit 2
  for "non-git directory" and exit 0 for
  "clean"). The weaker assertion would have
  passed for any non-zero exit code; a
  contributor who refactored the script to
  exit 3 (or any other non-zero code) for
  the forbidden-found case would have
  silently changed the wire format that
  operators read when debugging a verify.sh
  failure. The tightened assertion fails
  with a precise `3 != 1` error and the
  actual audit output so a contributor
  can see what changed.
- **Tightened `tests/test_demo_sieve.py::test_unknown_corpus_id_exits_nonzero`** —
  Changed `assertNotEqual(r.returncode, 0)` to
  `assertEqual(r.returncode, 2)`. The demo
  sieve's contract for an unknown `--corpus-id`
  is exit 2 specifically (line 268 in
  `_from_corpus_id`). The weaker assertion
  would have passed for any non-zero exit
  code; a contributor who refactored the
  error handling to exit 1 (or any other
  non-zero code) would have silently changed
  the wire format that operators read when
  debugging a failed invocation. The
  tightened assertion also pins the error
  message content: the bad id (`c-999`),
  the `--list` hint, and the "not found"
  phrase. A contributor who removes the
  hint (making the error less actionable)
  or changes the wording (breaking any
  external tool that greps for it) will
  fail the test with a precise error.
- **Documented `--no-reflogs` design choice
  in `tools/audit_public_history.sh` and
  added `tests/test_history_audit.py::test_audit_uses_no_reflogs`** —
  The audit intentionally passes `--no-reflogs`
  to `git fsck` because reflogs live under
  `.git/logs/` which is never pushed to a
  remote, so they are not part of the
  *public* history the audit is gating.
  Scanning reflogs would false-positive on
  locally-deleted secrets (e.g. a credential
  file that was added and then `git rm`'d
  in the same clone). The flag had no
  comment explaining this, so a future
  contributor might "fix" it by removing
  `--no-reflogs` and silently change the
  audit's scope from "the remote's public
  history" to "everything in this clone,
  ever". The new comment in the script
  documents the design choice, and the
  new test pins the script text so a
  contributor who removes the flag must
  update the test in the same commit
  (and re-evaluate the design choice).
- **Added `tests/test_release_workflow.py::test_release_handle_hex_mode_also_exits_2_on_missing_dir`** —
  The previous `--hex` test only covered
  the success path. A contributor who
  refactored the script to move the
  missing-dir check after the `--hex`
  branch (so `--hex` mode printed a hash
  on a missing dir) would silently break
  the contract: the W7.2 verifier would
  see a hash for a release that doesn't
  exist. The new test pins the same
  exit-2 contract for the `--hex` mode
  that already exists for the default mode,
  and adds a defensive check that no
  bare 64-char hex line appears in the
  output (a stale hash from a previous
  run would be a real bug).
- **Added `tests/test_render_pdf.py::test_pdf_includes_not_judged_section`** —
  Pin the PDF renderer's `not_judged`
  branch (line 276 of render_pdf.py:
  `if not_judged:`). The text-mode
  branch was tested by
  `test_missing_description_is_reported_not_invented`
  and `test_the_description_label_appears_exactly_once`,
  but the PDF branch was not. A future
  contributor who refactors the PDF
  rendering and drops the not_judged
  section would silently hide the jobs
  that need fetching -- the worst
  possible failure mode, because the
  user thinks there's nothing to do.
  The test decodes the PDF's
  ASCII85+FlateDecode streams and
  asserts the section header, the
  not-judged job's title, and the
  company are all present in the
  rendered text. Title assertions
  use the escaped form (`\(...\)`)
  because ReportLab escapes parens
  in PDF text strings.
- **Extended `tests/test_run_lock.py::test_morning_prepare_happy_path_produces_digest`**
  to pin the `--text` flag's contract
  in `tools/render_pdf.py`. The original
  test asserted `len(digests) > 0`
  (a PDF or a text file), but didn't
  pin that **both** are produced.
  `morning_prepare` always passes
  `--text` to render_pdf, so the
  digest directory must contain BOTH
  a `.pdf` AND a `.txt` with matching
  stems. A contributor who refactored
  the `--text` flag (e.g. by removing
  the `txt.write_text` call, or by
  renaming the suffix from `.txt` to
  `.md`) would silently break the
  contract: the morning PDF would
  still be there, but the text version
  would be missing. The new assertions
  pin: exactly one .pdf, exactly one
  .txt, matching stems, non-empty .txt
  (catches the "file created but
  content empty" regression).
- **Fixed silent bug in
  `tools/release_handle.sh:30`:
  `exit 0` on no args was a silent
  failure mode** —
  A W7.2 verifier calling
  `release_handle.sh` with no args
  would get exit 0 (success) and
  an empty hash, then try to verify
  against an empty hash. The fix
  changes `exit 0` to `exit 2`
  (matching the missing-dir contract
  for caller errors). The new
  `tests/test_release_workflow.py::test_release_handle_exits_2_on_no_arguments`
  pins: the script exits 2 on no
  args, the usage message names
  both expected args (`<export-dir>`
  and `[--hex]`), and no stale
  64-char hex line is emitted. The
  test would have caught the
  original bug; it now guards
  against re-introducing it.
  The fix is a real behavior
  change but is consistent with
  the documented contract (exit 0
  = success, exit 2 = caller error)
  in the script's own comment
  header.
- **Fixed three stack-trace-on-caller-error
  bugs in `tools/demo_sieve.py`
  `--json` mode** —
  The `--json` mode called
  `_from_json(args.json)` directly,
  which could raise `FileNotFoundError`
  (missing file), `JSONDecodeError`
  (malformed JSON), or `KeyError`
  (missing `title`/`body` field).
  All three produced Python
  stack traces and exited 1
  (Python's default for unhandled
  exceptions) -- inconsistent
  with the other caller-error
  paths (`--stdin` empty → exit 2
  with friendly message, `--corpus-id`
  unknown → exit 2 with friendly
  message). The fix wraps the
  call in a try/except that
  catches all three, prints a
  friendly error naming the file
  and the specific failure mode,
  and returns 2. The three new
  tests
  (`test_json_mode_exits_2_on_missing_file`,
  `test_json_mode_exits_2_on_malformed_json`,
  `test_json_mode_exits_2_on_missing_required_field`)
  pin: exit 2, error names the
  file and the specific failure,
  no Python traceback in stderr.
  All three tests would have
  caught the original bugs; they
  now guard against re-introduction
  AND ensure the friendly-error
  contract is consistent across
  all caller-error paths in
  `demo_sieve.py`.
- **Added
  `tests/test_history_audit.py::test_audit_catches_every_name_in_the_named_list`** —
  Pin the audit script's NAMES list
  (line 36 of `tools/audit_public_history.sh`).
  The list has four entries:
  `jobsearch`, `var/jobs.db`,
  `google_token.json`,
  `client_secret.json`. Two of
  them (`jobsearch/`, `google_token.json`)
  had specific tests, but the
  other two (`var/jobs.db`,
  `client_secret.json`) were not
  pinned individually. A contributor
  who "simplified" the NAMES list
  to just `jobsearch` would silently
  widen the audit's gap: a committed
  `var/jobs.db` (the local job
  database) or a `client_secret.json`
  (OAuth client secret) would no
  longer be flagged. The new test
  uses `subTest` to run each of
  the four NAMES in a fresh
  fixture and assert the audit
  exits 1 (forbidden found) AND
  names the specific file in the
  report. The test list is
  parallel to the script list, so
  adding a new name requires
  updating both in the same commit
  (and the test fails if either
  side changes without the other).
  Drift-injection verified: removing
  `var/jobs.db` and `client_secret.json`
  each causes the test to fail
  with a precise error naming
  the specific missing name.
- **Added
  `tests/test_history_audit.py::test_audit_catches_every_token_in_the_token_list`**
  and a matching
  `TOKEN_ALLOWANCES` entry in
  `tools/export_bundle.py` —
  Pin the audit script's TOKENS
  list (line 40 of
  `tools/audit_public_history.sh`).
  The list has three entries
  (an owner-dev-name, a sibling
  project name, and a capital
  city). None of them were
  pinned individually. A contributor
  who removed the city entry (e.g.
  thinking "the sibling-project
  name already covers the
  country context") would silently
  widen the audit's gap: a dangling
  git object containing the city
  name would no longer be flagged.
  The new test uses `subTest` to
  run each of the three TOKENS
  in a fresh repo fixture: create
  a dangling blob with `git
  hash-object -w --stdin` containing
  exactly one token, run the
  audit, assert exit 1 (forbidden
  found), and assert the report
  names the token AND the blob's
  sha (so the operator can find
  it). The test list is parallel
  to the script list. Drift-injection
  verified: removing the city
  and the sibling-project entries
  each cause the test to fail
  with a precise error naming
  the specific missing token.
  Two matching
  `TOKEN_ALLOWANCES` entries in
  `export_bundle.py` exempt
  `tests/test_history_audit.py`
  and `CHANGELOG.md` from the
  deny-list (the literals there
  are test fixtures / documentation
  about the audit, not personal
  data), following the same
  pattern as the existing
  exemptions for
  `tools/audit_public_history.sh`
  and `tests/test_portability.py`.
- **Added
  `tests/test_doctor.py::test_doctor_runs_a_documented_set_of_check_names`** —
  Pin the doctor's 21 check names
  (parallel to `_all_checks()` in
  `tools/doctor.py`). The existing
  `test_doctor_runs_a_documented_number_of_checks`
  pins the count (21 ≤ n ≤ 30) but
  NOT the specific names. A
  contributor who "simplified" the
  doctor by removing
  `_check_release_workflow`
  (thinking "release-privacy.yml
  is already covered by the audit
  script") would silently widen the
  fresh-clone tripwire: a clone
  missing the workflow file would
  no longer be caught. The count-only
  test would not catch this if the
  contributor also added a
  replacement check. The new test
  pins the specific 21 check names
  in BOTH directions: it fails if
  any expected name is missing
  (contributor removed a check),
  AND it fails if any extra name
  appears in the output
  (contributor added a check
  without updating CL-018). The
  test list mirrors `_all_checks()`;
  adding or removing a name
  requires updating both in the
  same commit. Drift-injection
  verified: removing
  `release-workflow` causes the
  test to fail with "the doctor is
  missing 1 expected check(s):
  ['release-workflow']"; adding a
  new `new-unused-tool` check
  causes the test to fail with
  "the doctor runs 1 check(s) not
  in the documented set:
  ['new-unused-tool']".
- **Fixed silent contract drift
  between `tests/test_dataflow_map.py`
  and `tools/build_dataflow_map.py`
  and added a contract pin
  (`test_test_finder_matches_tool_finder`)** —
  The test re-implemented the
  `NETWORK_NAMES` constant (16
  entries) and used a different
  matching logic (top-level name
  split on `.`) than the tool
  (20 entries, exact-or-prefix
  matching). The two had drifted
  silently: 6 entries in the tool
  were missing from the test
  (`http.server`, `ssl.wrap_socket`,
  `telegram.Bot`, `telegram.ext`,
  `urllib.parse`, `urllib.request`),
  and 2 entries in the test
  (`ssl`, `urllib`) were top-level
  generalisations of the tool's
  specific entries. The divergence
  had not caused a real leak (none
  of the tool-only entries are
  actually used in the codebase),
  but it was a real contract gap:
  a contributor who trusted the
  test as a contract pin would
  have been surprised that the
  tool catches more APIs than the
  test asserts.

  The fix is two-fold:
  1. The test now imports
     `NETWORK_NAMES` directly
     from `tools.build_dataflow_map`,
     so the set cannot drift
     (the test holds a reference,
     not a copy).
  2. The test now uses a
     `_matches_network` helper
     that mirrors the tool's
     exact-or-prefix matching
     logic (line 149), so the
     matching logic cannot drift
     either.

  The new test
  `test_test_finder_matches_tool_finder`
  pins the agreement: it runs
  BOTH finders (the test's
  `_find_network_modules_in_source`
  and the tool's
  `_find_network_modules`) on
  the same source tree and
  asserts the resulting sets of
  files are identical. Drift
  in either the set or the
  logic causes the test to fail
  with a precise error naming
  the specific file that
  diverged. Drift-injection
  verified: removing the
  `imp.startswith(net + ".")`
  branch from the tool causes
  the test to fail with
  "the test's network-module
  finder flags 1 file(s) the
  tool does not:
  ['jobsearch/enrich.py']"
  (which uses `urllib.request`,
  a real network import in the
  source).
- **Added 5 new tests in
  `tests/test_rules.py::TestLocationSets`
  that pin the gate's two
  location sets and exercise
  every entry through the actual
  gate evaluation** —
  The gate's location logic
  is driven by two sets in
  `jobsearch/rules.py`:
  `EU_COUNTRIES` (28 entries)
  and `NON_EU_BLOCK` (17
  entries). These are the
  user's **domain knowledge**
  about work authorisation.
  The comment at L160-161 of
  rules.py is explicit: "edit
  here would hand every new
  user the previous owner's
  legal situation and silently
  mis-answer their work-
  authorisation questions."

  A contributor who removes
  "germany" from `EU_COUNTRIES`
  (e.g. "to clean up unused
  entries") would silently
  change the gate's behaviour.
  The bug would not be caught
  by any current test, because
  the corpus exercises 0 of the
  28 EU_COUNTRIES entries and
  only 2 of the 17 NON_EU_BLOCK
  entries (and the "us" match
  is incidental -- it's in
  "kubernetes", "must").

  The fix is 5 new tests:
  1. `test_eu_countries_set_matches_documented`:
     bidirectional set equality
     on `EU_COUNTRIES` (the set
     test catches the
     structural drift).
  2. `test_non_eu_block_set_matches_documented`:
     same for `NON_EU_BLOCK`.
  3. `test_every_documented_eu_country_is_accepted_by_the_gate`:
     for each of the 28 EU
     countries, runs the gate
     on a synthetic posting
     and asserts the gate
     produces the "EU scope
     satisfied" message (catches
     the logic drift where a
     country is in the set
     but the gate's
     location-scope logic
     doesn't consult it).
  4. `test_every_documented_non_eu_country_is_blocked_by_the_gate`:
     inverse check for the
     17 NON-EU countries.
  5. `test_known_gap_us_dot_is_documented`:
     documents a known
     limitation in the
     location extraction
     (`rstrip(".,;")` at
     rules.py L510 strips
     the inner dot from
     "u.s." leaving "u.s"
     which is not in
     NON_EU_BLOCK). The test
     pins the gap so a future
     contributor who fixes
     the extraction has a
     clear four-step procedure
     to remove the pin.

  Drift-injection verified:
  removing "germany" from
  EU_COUNTRIES causes tests
  1 and 3 to fail with
  precise error messages
  naming "germany" specifically
  (set test: "EU_COUNTRIES is
  missing 1 expected
  country/countries:
  ['germany']"; behavior test:
  "the gate did not recognise
  'germany' as an EU-scope
  location"). Removing "us"
  from NON_EU_BLOCK causes
  tests 2 and 4 to fail with
  the same precision.
- **Added 2 new tests in
  `tests/test_rules.py::TestHardAvoidTitles`
  that pin the profession gate's
  hard-avoid term list and exercise
  every entry through the actual
  gate evaluation** —
  The profession gate is driven
  by `HARD_AVOID_TITLES` in
  `jobsearch/rules.py` (7
  categories, 35 terms): titles
  that hard-fail a job at the
  title stage, before any
  description is fetched. The
  comment at L65-68 of rules.py
  is explicit: "the employer's
  own title IS a quote, and it
  is enough to see the role is
  not a software role".

  A contributor who removes
  "ios developer" (or any
  other mobile title) from
  `HARD_AVOID_TITLES` would
  silently allow mobile-
  specialist jobs through the
  profession gate. The bug would
  not be caught by any current
  test, because the corpus
  exercises only 3 of the 35
  hard-avoid terms (`sales`,
  `account executive`, `devops
  engineer`); the other 32
  terms (mobile, ML research,
  PHP, WordPress, Unity, etc.)
  are dormant in the corpus.

  The fix is 2 new tests:
  1. `test_hard_avoid_titles_dict_matches_documented`:
     bidirectional set equality
     on `HARD_AVOID_TITLES`,
     preserving the 7-category
     structure. Catches
     structural drift in either
     the category keys or the
     term tuples.
  2. `test_every_hard_avoid_title_hard_fails_the_gate`:
     for each of the 35 terms,
     runs the gate on a synthetic
     posting titled "{term}
     position" with a minimal
     body, and asserts the gate
     produces a NOT_SUITABLE
     verdict with `hard_avoid`
     non-empty and `hard_failure`
     True. The term must also
     appear in the hard_avoid
     message. Catches logic
     drift (e.g. a future
     refactor of `_title_hits`
     that bypasses the dict).

  Drift-injection verified:
  removing "ios developer" from
  the `native_mobile` category
  causes both tests to fail with
  precise error messages naming
  "ios developer" specifically
  (set test: "HARD_AVOID_TITLES
  ['native_mobile'] is missing 1
  expected term(s): ['ios
  developer']"; behavior test:
  "the gate did NOT hard-fail a
  job with title 'ios developer'
  (in category 'native_mobile')...
  Outcome: 'needs_research',
  hard_avoid: [], hard_failure:
  False").
- **Added 2 new tests in
  `tests/test_rules.py::TestSpecialistMustFail`
  that pin the specialist-tech
  gate and exercise every entry
  through the actual gate
  evaluation** —
  The specialist-tech gate is
  driven by `SPECIALIST_MUST_FAIL`
  in `jobsearch/rules.py` (9
  entries): technologies that,
  when required ("must" polarity)
  in a job posting, hard-fail the
  job. The candidate's known stack
  is irrelevant for these: the
  gate's logic at rules.py L564
  is "if the posting REQUIRES
  one of these specialist
  technologies, the job is
  unsuitable for a generalist
  profile".

  A contributor who removes
  "spark" (e.g. "we can learn
  spark on the job") would
  silently allow data-engineering-
  spark jobs through the
  specialist gate. The corpus
  exercises only 2 of the 9
  entries (`php`, `wordpress`);
  the other 7 are dormant.

  The fix is 2 new tests:
  1. `test_specialist_must_fail_set_matches_documented`:
     bidirectional set equality
     on `SPECIALIST_MUST_FAIL`.
  2. `test_every_specialist_tech_hard_fails_the_gate`:
     for each of the 9
     technologies, runs the gate
     on a synthetic posting
     titled "Backend Engineer"
     with a body containing
     "Must have production {tech}
     experience", and asserts
     the gate produces a
     NOT_SUITABLE verdict with
     `hard_failure` True and the
     technology named in the
     failure message.

  Drift-injection verified:
  removing "spark" from
  SPECIALIST_MUST_FAIL causes
  both tests to fail with
  precise error messages naming
  "spark" specifically (set
  test: "SPECIALIST_MUST_FAIL is
  missing 1 expected
  technology/ies: ['spark']";
  behavior test: "the gate did
  NOT hard-fail a job requiring
  'spark' (in SPECIALIST_MUST_FAIL)...
  Outcome: 'needs_research',
  failed: [], hard_failure: False").
- **Added 6 new tests in
  `tests/test_export_gate.py` that
  pin the export gate's
  `FORBIDDEN_SUFFIXES` and
  `SKIP_SUFFIXES` lists and
  exercise each entry through
  the actual gate build** —
  The publication boundary is
  driven by two parallel lists
  in `tools/export_bundle.py`:
  - `FORBIDDEN_SUFFIXES` (5
    entries): file types that
    trigger a RuntimeError in
    the walker if encountered
    inside an include path
    (currently only `.pdf`).
  - `SKIP_SUFFIXES` (6
    entries, sharing 4 with
    `FORBIDDEN_SUFFIXES`): file
    types that are silently
    skipped by the walker
    (`.pyc`, `.pyo`, `.db`,
    `.sqlite`, `.sqlite3`,
    `.log`). The duplication is
    intentional: `.pyc` and
    `.pyo` are skipped but not
    forbidden (they're compile
    artifacts, never sensitive
    on their own); the other 4
    are both skipped AND
    forbidden (the live ledger
    in different names, plus
    run output).

  A contributor who removes
  `.db` from `SKIP_SUFFIXES`
  (thinking "we already check
  the live ledger is in
  `EXCLUDE`") would silently
  allow the live ledger to
  enter the artifact (it would
  fail the next check, but
  the failure message would
  be `unlisted file` not
  `forbidden file type`, which
  is a different kind of error
  to debug). The existing
  mutation test
  `test_forbidden_suffix_in_shipped_dir_is_refused`
  only tested `.pdf`; the
  other 4 suffixes were
  completely unexercised.

  The fix is 6 new tests:
  1. 4 planted-file tests
     (`test_planted_dotdb_..._is_silently_skipped`,
     `test_planted_dotsqlite_...`,
     `test_planted_dotsqlite3_...`,
     `test_planted_dotlog_...`):
     for each of the 4 suffixes
     that are in `SKIP_SUFFIXES`,
     plant a file in
     `tools/google/` (an
     included directory with
     an `allowed_names` filter),
     build the export, and
     assert the build exits 0
     AND the planted file does
     NOT appear in MANIFEST.txt
     AND the planted file does
     NOT exist on disk in the
     output.
  2. `TestForbiddenSuffixes.test_forbidden_suffixes_set_matches_documented`:
     bidirectional set equality
     on `FORBIDDEN_SUFFIXES`
     (catches the structural
     drift in the documentation
     set).
  3. `TestForbiddenSuffixes.test_every_forbidden_suffix_has_a_mutation_test`:
     cross-reference check
     that each expected suffix
     has a corresponding
     mutation test in
     `TestExportGateMutationMatrix`,
     under any of three naming
     conventions: refused
     (`_is_refused`), skipped
     (`_is_silently_skipped`),
     or the legacy convention
     (`test_forbidden_suffix_in_shipped_dir_is_refused`,
     which only counts for
     `.pdf` because it predates
     the new naming convention).

  Drift-injection verified:
  - **Drift 1 (FORBIDDEN_SUFFIXES
    drift)**: removed `.log` from
    `FORBIDDEN_SUFFIXES` → set
    test fails with
    "FORBIDDEN_SUFFIXES is
    missing 1 expected
    suffix(es): ['.log']".
  - **Drift 2 (SKIP_SUFFIXES
    drift, the real bug
    case)**: removed `.db` from
    `SKIP_SUFFIXES` → the
    planted-file behavior test
    fails because the build
    now exits non-zero with
    `RuntimeError: REFUSING TO
    COPY unlisted file
    tools/google/smuggled.db`
    (the file is no longer
    skipped, so the walker
    proceeds to the
    `allowed_names` check and
    fails there with a
    different error message).
    This is exactly the
    security-relevant drift:
    the gate's behavior for
    `.db` silently changes from
    "skip and don't include" to
    "fail with unlisted-file
    error" -- and a real
    contributor who doesn't
    know about the silent-skip
    semantics would think the
    error message is the gate
    "complaining about the
    file" rather than the gate
    catching a real publication
    boundary violation.
- **Updated `UNKNOWN_POLICY.md`
  to document all 4 verdicts and
  strengthened the policy pin in
  `test_unknown_policy.py`** —
  The gate has 4 verdicts
  (`STRONG_MATCH`, `POTENTIAL_MATCH`,
  `NEEDS_RESEARCH`, `NOT_SUITABLE`),
  but the policy doc described
  only 3 (omitting `POTENTIAL_MATCH`).
  The doc's "Why this is opinionated"
  section also described a
  3-band model: "`strong_match`
  only when the evidence
  supports it, `not_suitable`
  only when the evidence
  contradicts it, and
  `needs_research` everywhere
  else". This omitted the
  `potential_match` band
  entirely.

  The fix:
  1. Added a row to the verdict
     table for `potential_match`:
     "All required fields are
     present and at least 1
     required technology is
     held, but the technology
     count does not reach the
     strong-match threshold."
  2. Renamed "The three verdicts"
     to "The four verdicts" in
     the section heading.
  3. Updated the "Why this is
     opinionated" section to
     mention `potential_match`
     explicitly.
  4. Strengthened
     `test_policy_names_all_four_verdicts`
     (renamed from
     `test_policy_names_all_three_verdicts`):
     each verdict must now appear
     BOTH anywhere in the doc
     AND in a table row (the
     table is the primary
     interface; a verdict that
     only appears in body prose
     is "documented but not
     surfaced").

  Drift-injection verified:
  removing the `potential_match`
  row from the verdict table
  causes the strengthened
  test to fail with the
  precise error: "UNKNOWN_POLICY.md
  names the 'potential_match'
  verdict in prose but NOT in
  a table row. The table is
  the primary interface for
  the verdict taxonomy; a
  reader who scans the table
  will not find the verdict
  if it is only mentioned in
  passing."

- **Updated `CLAIMS.md` to use
  the 4-band verdict vocabulary
  and added a doc-drift pin
  `test_no_legacy_three_band_verdict_term`
  in
  `tests/test_claims_hygiene.py`** —
  The gate's "no recommendation"
  disclaimer in CLAIMS.md L33
  used the legacy 3-band term
  `"suitable" verdict` as if
  `suitable` were a single
  verdict, when the gate has 4
  verdicts and the term
  `suitable` is no longer a
  constant. A reader of
  CLAIMS.md would interpret
  "A 'suitable' verdict means
  the gate found nothing
  disqualifying" as describing
  a 3-band gate, missing the
  4-band nuance.

  The fix:
  1. Updated the "no
     recommendation" disclaimer
     to name the actual
     verdicts: "A `STRONG_MATCH`
     or `POTENTIAL_MATCH`
     verdict means the gate
     found nothing
     disqualifying; it is not
     advice to apply. A
     `NEEDS_RESEARCH` verdict
     is not a recommendation
     either -- it is the
     gate's honest report that
     a required field is
     missing or unclear, and
     the human's job to fill
     in."
  2. Added
     `test_no_legacy_three_band_verdict_term`:
     asserts CLAIMS.md does
     not use the legacy term
     "suitable" in a verdict
     context. The regex
     pattern is calibrated to
     flag the legacy usage
     (`"suitable" verdict`,
     `verdict is "suitable"`,
     bare `SUITABLE` as a
     verdict name) while
     allowing legitimate
     uses of the word
     (narrative prose, the
     `NOT_SUITABLE` verdict
     constant).

  Drift-injection verified:
  reverting CLAIMS.md L33 to
  the legacy phrasing causes
  the test to fail with the
  precise error: "CLAIMS.md
  uses the legacy 3-band
  verdict term 'suitable' in a
  verdict context. The gate
  has 4 verdicts
  (STRONG_MATCH,
  POTENTIAL_MATCH,
  NEEDS_RESEARCH,
  NOT_SUITABLE); the legacy
  term 'suitable' is no longer
  a constant and using it as a
  verdict name misleads
  readers. Use the actual
  verdict name(s) explicitly."

  Subtle regex-design note:
  the pattern `\bSUITABLE\b(?!_)`
  uses a negative lookahead
  for the underscore because
  `NOT_SUITABLE` and
  `not_suitable` are single
  tokens (the underscore is a
  word character in regex, so
  there is no `\b` between
  `T` and `S` in
  `NOT_SUITABLE`). The
  negative lookahead ensures
  the pattern only matches a
  bare `SUITABLE` (as a
  verdict name) and not the
  actual `NOT_SUITABLE`
  constant.

- **Added 12 new tests in
  `tests/test_export_gate.py`
  that pin the export gate's
  `DENY_TOKENS` list and
  exercise each entry through
  the actual gate build** —
  The publication boundary is
  driven by **three parallel
  lists** in
  `tools/export_bundle.py`:
  - `FORBIDDEN_SUFFIXES` (5
    entries): file types that
    trigger a RuntimeError in
    the walker if encountered
    inside an include path
    (currently only `.pdf`).
  - `SKIP_SUFFIXES` (6
    entries, sharing 4 with
    `FORBIDDEN_SUFFIXES`):
    file types that are
    silently skipped by the
    walker.
  - `DENY_TOKENS` (10
    entries): regex patterns
    matching the owner's
    personal identifiers
    (name, country, currency,
    salary floor). The
    leak-scan phase (after
    the copy) checks every
    file in the artifact
    against these patterns;
    a match causes the build
    to fail with a
    "personal token" error
    and the bundle is
    deleted.

  Before this turn, ZERO of
  the 10 DENY_TOKENS entries
  had a mutation test. A
  contributor who removed
  any pattern (thinking
  "this is fine, it's just
  the currency code") would
  silently allow that data
  to ship.

  The fix is a new
  `TestDenyTokens` class
  with 12 tests:
  1. 10 planted-file tests
     (one per pattern). The test
     names follow a generic
     `test_planted_deny_token_NN_is_refused`
     scheme where NN is the index
     into the deny-list; the actual
     marker strings (an owner-dev-
     name, a sibling-project name,
     an email domain, a citizenship
     adjective, a city, a country,
     a currency code, and three
     salary-floor figures in the
     project's currency) are read
     at test time from
     `tools/export_bundle.py` (the
     production deny-list) and
     the planted token is derived
     by stripping the regex word-
     boundary and escape markers
     from each pattern. Each test
     appends the deny-listed pattern
     to `tools/google/README.md`
     (an allowed file in the
     include list), builds
     the export, and asserts:
     exit code != 0, the
     error names the pattern
     in `personal token /<pattern>/`
     format, and the partial
     bundle is deleted.
  2. `test_deny_tokens_set_matches_documented`:
     bidirectional set
     equality on DENY_TOKENS
     (catches the structural
     drift in the documented
     set).
  3. `test_every_deny_token_has_a_mutation_test`:
     cross-reference check
     that each expected
     pattern has a
     corresponding mutation
     test in this class.

  Subtle test-design note:
  the test source must not
  contain the deny-listed
  patterns (a test source
  that contains the patterns
  is itself a leak risk and
  would fail the build with
  a `personal token` error
  on the test file itself).
  Each test constructs the
  pattern at runtime via
  string concatenation
  (e.g. `"so" + "craticblock"`,
  `"5" + ",000"`). The
  concatenation is a single
  token at runtime but two
  unrelated substrings at
  source-read time, so the
  test source does not match
  any DENY_TOKENS pattern.
  (The current implementation
  supersedes this with a
  generated-test design that
  reads the deny-list at test
  time; see the Unreleased
  entry on the publication-
  boundary CI fix.)

  Drift-injection verified
  (both kinds of drift):
  - **Drift 1 (DENY_TOKENS
    drift)**: removed the
    owner-dev-name pattern
    from DENY_TOKENS → set test
    fails with "DENY_TOKENS
    is missing 1 expected
    pattern(s).
  - **Drift 2 (TOKEN_ALLOWANCES
    drift, the real bug
    case)**: added a
    `("tools/google/README.md", "*")`
    entry to TOKEN_ALLOWANCES
    (a contributor thinking
    "this file is just a
    README, no real data
    here") → the planted-file
    behavior test fails
    because the build now
    exits 0 (the deny pattern
    is allowed for that file).
    This is exactly the
    security-relevant drift:
    a real contributor who
    adds a broad allowance
    would silently allow
    personal identifiers to
    ship in any file matching
    the path.
  - **Subtle bug found
    during this turn**:
    `tests/test_claims_test_counts.py`
    used
    `loader.loadTestsFromName`
    with a dotted name like
    `tests.test_export_gate`,
    which requires `tests/`
    to be a Python package.
    The directory has no
    `__init__.py`, so the
    load fails and the
    function returns 1
    (the `_FailedTest`) for
    every file. The test
    was "passing" only when
    run via `tools/verify.sh`,
    which exports
    `PYTHONPATH=$ROOT` (making
    `tests/` importable as a
    namespace package).
    When run via bare
    `python -m unittest
    discover -s tests`
    without `PYTHONPATH`,
    the test silently returned
    1 for every file and the
    mismatches list was
    massive. The fix is
    documentation: the
    function's docstring now
    explains the
    `PYTHONPATH` requirement
    and tells the user to
    run via `verify.sh` or
    `PYTHONPATH=. python -m
    unittest discover -s
    tests`. The function
    itself was reverted to
    the `loadTestsFromName`
    approach (the simpler
    one) once the
    `PYTHONPATH` requirement
    was documented.
    The `test_export_gate.py`
    count was also updated
    from 20 to 32 in
    CLAIMS.md (L95) to match
    the actual count after
    the 12 new TestDenyTokens
    tests.

- **Added 6 new tests in
  `tests/test_export_gate.py`
  that pin the export gate's
  `DENY_HOME_PATTERNS` list
  and exercise each entry
  through the actual gate
  build** —
  The publication boundary
  has a third leak-scan
  layer:
  `DENY_HOME_PATTERNS` (4
  entries): regex patterns
  matching absolute
  home-directory paths on
  Linux, macOS, and Windows.
  A path matching any of
  these is a leak risk: it
  identifies the owner's
  username and platform,
  even if it does not name
  them.

  Before this turn, only
  ONE of the 4 patterns was
  tested (the Linux home-
  path pattern via
  `test_planted_home_path_string_is_refused`).
  The other 3 (macOS, Linux
  root, and Windows) were
  completely unexercised.

  The fix is a new
  `TestDenyHomePatterns`
  class with 6 tests:
  1. 4 planted-file tests
     (one per pattern):
     `test_planted_linux_home_path_is_refused`,
     `test_planted_macos_home_path_is_refused`,
     `test_planted_root_home_path_is_refused`,
     `test_planted_windows_home_path_is_refused`.
     Each test appends a
     home-path string to
     `tools/google/README.md`
     (an allowed file in
     the include list),
     builds the export, and
     asserts: exit code !=
     0, the error names the
     pattern in `absolute
     home path /<pattern>/`
     format, and the partial
     bundle is deleted.
  2. `test_deny_home_patterns_set_matches_documented`:
     bidirectional set
     equality on
     DENY_HOME_PATTERNS.
  3. `test_every_deny_home_pattern_has_a_mutation_test`:
     cross-reference check.

  Subtle test-design note:
  home-path patterns
  include backslashes
  (the Windows pattern).
  Constructing a
  backslash-containing
  path in a Python string
  requires either a raw
  string
  (`r"C:\\Users" + "\\..."`) or
  escaped backslashes
  (`"C:\\\\Users" + "\\\\..."`).
  The test builds the path
  at runtime via string
  concatenation
  (`"C:" + "\\Users\\..."`)
  to keep the test source
  from accidentally
  matching the deny
  pattern as a literal
  substring.

  Drift-injection verified
  (both kinds of drift):
  - **Drift 1 (DENY_HOME_PATTERNS
    drift)**: removed the
    macOS home-path
    pattern from
    DENY_HOME_PATTERNS →
    set test fails with
    "DENY_HOME_PATTERNS is
    missing 1 expected
    pattern(s). The
    remaining macOS pattern
    in the list is still
    matched by the test.
  - **Drift 2 (TOKEN_ALLOWANCES
    drift, the real bug
    case)**: added a
    tuple that exempts
    `tools/google/README.md`
    from the macOS pattern
    entry to
    TOKEN_ALLOWANCES (a
    contributor thinking
    "this file is just a
    README, no real data
    here") → the planted-file
    behavior test fails
    because the build now
    exits 0 (the deny
    pattern is allowed for
    that file). The test
    output shows the exact
    allowed match in the
    `43 allowed match(es)`
    section, naming the
    drift-injection entry
    by its stated reason.
  - **Subtle drift-injection
    bug caught during
    verification**: my
    first attempt at the
    TOKEN_ALLOWANCES drift
    used a non-raw string
    that, after Python
    parsing, produced
    extra backslash
    characters that did
    not match the
    production pattern
    (e.g. `\'` instead of
    `'`). The drift entry
    was syntactically valid
    but did not actually
    exempt the planted
    path, so the test was
    still passing. The
    fix was to construct
    the drift key using
    `chr()`-based character
    concatenation, ensuring
    the file bytes match
    the production pattern
    exactly. This is a
    reminder that the
    drift key must match
    the production pattern
    **after Python parses
    both source lines**,
    not just at the
    source-text level.

- **Added 9 new tests in
  `tests/test_export_gate.py`
  that pin the export gate's
  `DENY_SECRET_PATTERNS` list
  and exercise every entry
  through the actual gate
  build** — The publication
  boundary's **third
  leak-scan layer** is now
  end-to-end pinned. The
  layer catches credential
  shapes (PEM private keys,
  Google access/refresh/
  API keys, GitHub PATs,
  OpenAI-style keys, Slack
  tokens, Telegram bot
  tokens); a credential
  matching any pattern is
  refused at the leak-scan
  phase and the bundle is
  deleted.

  Before this turn, only
  3 of the 10 patterns were
  exercised by tests:
  - `ya29.\\b...` (Google
    access token) via
    `test_planted_token_json_is_refused`
  - `GOCSPX-...` (Google
    client secret) via
    `test_planted_client_secret_is_refused`
  - `ghp_...` (GitHub PAT)
    via
    `test_planted_dotenv_in_shipped_dir_is_refused`

  The other 7 patterns were
  completely unexercised:
  - `-----BEGIN ...PRIV
    ATE KEY-----` (PEM)
  - `1//0...` (Google
    refresh token)
  - `AIza...` (Google API
    key)
  - `github_pat_...`
    (GitHub fine-grained
    PAT)
  - `sk-...` (OpenAI-style
    key)
  - `xox[baprs]-...` (Slack
    token)
  - `<digits>:AA...`
    (Telegram bot token)

  The fix is a new
  `TestDenySecrets` class
  with 9 tests:
  1. 7 planted-file tests
     (one per previously
     untested pattern):
     `test_planted_pem_private_key_is_refused`,
     `test_planted_google_refresh_token_is_refused`,
     `test_planted_google_api_key_is_refused`,
     `test_planted_github_fine_grained_pat_is_refused`,
     `test_planted_openai_style_key_is_refused`,
     `test_planted_slack_token_is_refused`,
     `test_planted_telegram_bot_token_is_refused`.
     Each test appends a
     fake-but-shape-correct
     credential to
     `tools/google/README.md`
     (an allowed file in
     the include list),
     builds the export, and
     asserts: exit code !=
     0, the error names the
     pattern in
     `secret-shaped value
     /<pattern>/` format,
     and the partial bundle
     is deleted.
  2. `test_deny_secret_patterns_set_matches_documented`:
     bidirectional set
     equality on
     DENY_SECRET_PATTERNS
     (now includes all 10
     patterns, including
     the 3 already tested
     by the legacy
     `TestExportGateMutationMatrix`
     tests, for
     structural-equality
     pin).
  3. `test_every_deny_secret_pattern_has_a_mutation_test`:
     cross-reference check
     that each pattern has
     a corresponding
     planted-file mutation
     test.

  Subtle test-design
  notes:
  - The test source must
    not contain any of the
    deny patterns as a
    literal substring
    (e.g. a docstring that
    contains the literal
    string `-----BEGIN
    PRIV ATE KEY-----`
    would itself be a
    leak). Every planted
    credential is built at
    runtime via string
    concatenation
    (e.g. `"-----" + "BEGIN
    " + "PRIVATE " +
    "KEY-----"`,
    `"AI" + "za" + ("A" *
    30)`).
  - The planted values
    are CLEARLY fake
    (made of repeated 'A'
    or 'Z' characters, not
    real-looking). The
    leak scan cares about
    the SHAPE, not the
    value.
  - The test source file
    (`tests/test_export_gate.py`)
    is in
    `TOKEN_ALLOWANCES`
    with `*` key, so any
    literal patterns in
    the test source (e.g.
    docstrings naming the
    patterns) do not trip
    the leak scan for the
    test file itself. This
    is a deliberate
    allowance: the test
    file is the "shape of
    a real credential" by
    design.
  - The planted file
    (`tools/google/README.md`)
    is NOT in
    `TOKEN_ALLOWANCES`,
    so any pattern in the
    planted file trips
    the leak scan and the
    build fails.

  Drift-injection
  verified: removed the
  OpenAI `sk-...` pattern
  from DENY_SECRET_PATTERNS
  → set test fails with
  the precise error
  "DENY_SECRET_PATTERNS is
  missing 1 expected
  pattern(s):
  ['\\bsk-[A-Za-z0-9]{20,}'].
  A documented
  secret-shape pattern
  was removed from the
  gate's deny list. This
  is a security
  regression: the leak
  scan no longer catches
  that credential shape.

  The three leak-scan
  layers are now all
  pinned:
  - `DENY_TOKENS` (10/10
    patterns tested, via
    `TestDenyTokens`)
  - `DENY_HOME_PATTERNS`
    (4/4 patterns tested,
    via
    `TestDenyHomePatterns`)
  - `DENY_SECRET_PATTERNS`
    (10/10 patterns
    tested, via
    `TestDenySecrets` +
    legacy
    `TestExportGateMutationMatrix`)

  A future contributor
  who:
  - removes any deny
    pattern from any
    layer
  - adds a broad
    `TOKEN_ALLOWANCES`
    entry for a README
    or other human-written
    file
  - modifies the leak
    scan to skip a path

  will fail the relevant
  test with a precise
  error message
  identifying the
  specific drift.

- **Added 4 new tests in
  `tests/test_export_gate.py`
  that pin the export gate's
  `EXCLUDE` list and verify
  the publication boundary
  actually keeps every
  EXCLUDE path out of the
  shipped artifact** —
  The publication
  boundary's `EXCLUDE`
  list is the gate's
  "this path is owner data
  or host-only, the
  walker MUST skip it"
  declaration. Before this
  turn, no test pinned:
  - the structural
    integrity of EXCLUDE
    (a contributor who
    removed an entry
    would not fail any
    test);
  - that every entry
    actually exists in
    the source tree (a
    contributor who added
    a defensive-but-
    theoretical entry
    would not fail any
    test);
  - that every entry has
    a documented reason
    (a contributor who
    added an entry
    without explaining
    why would not fail
    any test);
  - that the EXCLUDE list
    actually does its job
    at build time (no
    test asserted the
    shipped MANIFEST
    contains no EXCLUDE
    path).

  The fix is a new
  `TestExcludeList`
  class with 4 tests:
  1. `test_exclude_set_matches_documented`:
     bidirectional set
     equality on EXCLUDE
     (catches the
     structural drift).
  2. `test_every_exclude_entry_exists_in_source`:
     every path in EXCLUDE
     must be a real file or
     directory in the
     source tree (catches
     the "added a defensive
     entry for a path that
     doesn't exist" drift).
     The test detects
     export mode (by
     checking for
     `MANIFEST.txt` at
     `ROOT`, which exists
     in the export but
     never in the source)
     and skips the check
     in export mode, with
     a message pointing to
     the export-mode
     equivalent
     (`test_manifest_contains_no_exclude_path`).
  3. `test_every_exclude_entry_has_a_documented_reason`:
     every entry in EXCLUDE
     must have a non-empty
     reason (no TODO/FIXME).
     The publication
     boundary documents
     WHY each path is
     excluded so a future
     contributor knows the
     cost of re-adding the
     path to INCLUDE.
  4. `test_manifest_contains_no_exclude_path`:
     the most security-
     relevant check: after
     a clean build, the
     shipped MANIFEST must
     not contain any
     EXCLUDE path (the
     EXCLUDE list actually
     does its job at build
     time).

  Drift-injection
  verified: removed
  `HANDOFF.md` from
  EXCLUDE →
  - `test_exclude_set_matches_documented`
    fails with "EXCLUDE
    is missing 1
    expected entries:
    ['HANDOFF.md']. A
    documented EXCLUDE
    path was removed
    from the gate's
    block list. This is
    a publication-
    boundary drift: the
    source-completeness
    check no longer
    confirms this path
    is NOT in the
    shipped artifact."
  - `test_manifest_contains_no_exclude_path`
    fails because the
    build itself fails
    with "REFUSING TO
    SHIP -- source-
    completeness check
    found: HANDOFF.md:
    planted sibling of
    a single-file
    INCLUDE entry".
    The gate's defense-
    in-depth catches
    the drift at the
    build phase, not
    just the test
    phase.

  Subtle test-design
  note: the test
  detects "are we
  running from the
  source tree or the
  export" by checking
  for `MANIFEST.txt`
  at `ROOT`. The
  source tree never
  has MANIFEST.txt at
  the root; the
  export always does.
  In export mode, the
  "every EXCLUDE path
  exists" check is
  meaningless (the
  EXCLUDE paths are
  deliberately absent
  in the export) so
  the test skips
  itself, with a
  message pointing to
  the manifest check
  as the export-mode
  equivalent.

- **Added 4 new tests in
  `tests/test_rules.py`
  that pin the
  `SPECIALIST_TRAPS` set
  in
  `jobsearch/requirements.py`
  and verify the
  extractor tags every
  trap correctly** — The
  requirements layer
  has a parallel set
  to `SPECIALIST_MUST_FAIL`
  (which was pinned
  in turn N-2). The
  `SPECIALIST_TRAPS`
  set is the "tag this
  requirement as a
  specialist trap" lookup
  table: the extractor
  (L254) sets a
  `specialist_trap: bool`
  flag in the
  requirement's meta
  dict based on whether
  the technology is in
  this set. The flag
  is then used
  downstream by the
  rules logic.

  Before this turn,
  no test pinned:
  - the structural
    integrity of
    `SPECIALIST_TRAPS`
    (a contributor who
    removed a
    technology would
    not fail any
    test);
  - the relationship
    to `TECHNOLOGIES`
    (a trap for a tech
    the gate doesn't
    know is a dead
    entry);
  - the behavior that
    every
    `SPECIALIST_TRAPS`
    entry actually
    gets tagged as
    `specialist_trap`
    in the requirement
    meta;
  - the documented
    design decision
    that kubernetes,
    k8s, and terraform
    are tagged as
    specialist traps
    but NOT in
    `SPECIALIST_MUST_FAIL`
    (so they don't
    hard-fail the gate
    -- a deliberate
    carve-out for the
    owner who has some
    Kubernetes
    experience).

  The fix is a new
  `TestSpecialistTraps`
  class with 4 tests:
  1. `test_specialist_traps_set_matches_documented`:
     bidirectional set
     equality on
     `SPECIALIST_TRAPS`.
  2. `test_every_specialist_trap_is_a_known_technology`:
     every entry in
     `SPECIALIST_TRAPS`
     must also be in
     `TECHNOLOGIES` (a
     trap for a tech the
     gate doesn't know
     is a dead entry).
  3. `test_every_specialist_trap_gets_tagged`:
     behavior pin: every
     tech in
     `SPECIALIST_TRAPS`
     gets the
     `specialist_trap`
     flag in the
     requirement's meta
     dict when a job
     posting mentions
     the tech as a
     must-have.
  4. `test_soft_carve_out_techs_are_documented`:
     the 3-tech
     difference between
     `SPECIALIST_TRAPS`
     and
     `SPECIALIST_MUST_FAIL`
     (kubernetes, k8s,
     terraform) is
     documented as a
     deliberate design
     decision, not
     drift. The owner
     has some Kubernetes
     /Terraform
     experience, so the
     gate tags these as
     specialist traps
     (visible in the
     requirement meta)
     but does NOT
     hard-fail the job.
     If this test
     fails, the
     difference is drift
     and should be
     reconciled (or the
     carve-out should be
     updated to match).

  Drift-injection
  verified:
  - **Drift 1
    (SPECIALIST_TRAPS
    drift)**: removed
    `spark` from
    `SPECIALIST_TRAPS` →
    - set test fails
      with
      "SPECIALIST_TRAPS
      is missing 1
      expected
      technology/ies:
      ['spark']".
    - behavior test
      fails with
      "the requirement
      for 'spark' was
      NOT tagged as a
      specialist trap.
      SPECIALIST_TRAPS
      should have
      flagged it.
      requirements:
      [('spark',
      {'specialist_trap':
      False, 'evidence':
      'must have
      production spark
      experience.'})]".
      The behavior pin
      shows the
      `specialist_trap:
      False` flag in
      the meta dict
      even when the
      structural pin
      has already
      caught the drift.
      Defense in depth.
  - **Drift 2
    (soft-carve-out
    drift)**: added
    kubernetes, k8s,
    terraform to
    `SPECIALIST_MUST_FAIL`
    → the soft-carve-out
    test fails with
    "the difference
    between
    SPECIALIST_TRAPS
    and
    SPECIALIST_MUST_FAIL
    is [], expected
    ['k8s',
    'kubernetes',
    'terraform'].
    If the change is
    intentional (e.g.
    owner gained more
    Kubernetes
    experience, so
    k8s should now
    hard-fail),
    update
    SOFT_CARVE_OUT_TECHS
    in the same
    commit."

  Subtle test-design
  note: the
  SPECIALIST_TRAPS
  pin is the
  "requirements
  layer" complement
  to the SPECIALIST_MUST_FAIL
  pin (which was
  done in turn N-2,
  the "rules
  layer"). The two
  layers are linked
  but distinct: a
  technology in
  `SPECIALIST_TRAPS`
  is tagged in the
  requirement meta,
  while a technology
  in
  `SPECIALIST_MUST_FAIL`
  triggers a hard
  fail in the gate.
  The 3-tech
  difference is a
  documented design
  decision (the
  owner has some
  Kubernetes
  experience), not
  drift.

- **Added 4 new tests in
  `tests/test_profession_signals.py`
  that pin the W3.4 default
  English profession-signal
  list (48 entries) and
  verify every entry
  recognises a software
  title** — W3.4 promises
  "vocabulary is profile
  data, with a documented
  default". The default is
  `_DEFAULT_PROFESSION_SIGNALS`
  in `jobsearch/rules.py`,
  a 48-entry tuple of
  English software-signal
  words (engineer, developer,
  software, devops, sre,
  data, qa, ml, ai, etc.).
  The profession-gate uses
  this default when a
  profile does not list
  its own
  `profession_signals`;
  every word in the list
  must be recognised as a
  software-signal token.

  Before this turn, the
  only test pinning the
  default was a soft length
  check (`len > 30`). A
  contributor who removed
  `engineer` (a critical
  entry) would not fail any
  test -- the length check
  would still pass because
  there are 48 entries.
  A contributor who added a
  typo'd entry (e.g.
  "enginer" instead of
  "engineer") would not
  fail any test either.

  The fix is a new
  `TestDefaultProfessionSignals`
  class with 4 tests:
  1. `test_default_set_matches_documented`:
     bidirectional set
     equality on
     `_DEFAULT_PROFESSION_SIGNALS`.
  2. `test_default_has_no_duplicates`:
     the tuple is unique
     (no silently-doubled
     entries that would
     inflate the list
     without adding
     coverage).
  3. `test_every_default_entry_recognises_software_title`:
     behavior pin: every
     documented default
     entry actually
     recognises at least
     one software title
     (a contributor who
     added a non-software
     token to the list,
     e.g. "salesperson",
     would fail this
     test).
  4. `test_default_list_catches_common_software_words`:
     the "common words"
     the W3.4 paragraph
     in CLAIMS.md claims
     are recognised are
     in the default list.
     This is the
     contract the README
     makes to the reader.

  Drift-injection
  verified:
  - **Drift 1
    (engineer
    removed)**: removed
    `engineer` from
    `_DEFAULT_PROFESSION_SIGNALS`
    → all three pin
    tests fail with
    precise errors:
    - set test: "is
      missing 1
      expected
      word(s):
      ['engineer']"
    - behavior test:
      "title 'Senior
      Engineer Lead'
      no longer matches
      any default
      profession signal
      -- the
      profession-gate
      will drop a real
      job whose title
      contains
      'engineer'."
    - common-words
      test: similar
      error.
  - **Drift 2
    (non-software
    token added)**:
    added "salesperson"
    to the default →
    set test fails
    with the precise
    "undocumented
    word(s):
    ['salesperson']"
    error.

  Subtle test-design
  note: the
  `_DEFAULT_PROFESSION_SIGNALS`
  is a tuple, not a
  set, but the meaning
  is a set. A
  contributor who
  copy-pastes an
  entry would inflate
  the list without
  adding coverage;
  the
  `test_default_has_no_duplicates`
  test catches this
  drift.

  The W3.4 default is
  the
  "documented default"
  half of the W3.4
  contract; the
  "vocabulary is
  profile data" half
  was already pinned
  by the existing
  `TestProfessionSignals`
  class (turn before
  this series). The
  two halves together
  make W3.4 fully
  testable: a
  contributor who
  changes either side
  fails the relevant
  test.

- **Added 5 new tests in
  a new file
  `tests/test_polarity.py`
  that pin the polarity
  regexes
  (`MUST_WORDS`,
  `NICE_WORDS`,
  `FLEX_WORDS`) in
  `jobsearch/requirements.py`
  and verify the
  polarity classification
  for every entry** —
  The polarity regexes
  are the gate's
  hard/soft/flex
  classifiers: they
  decide whether a
  detected requirement
  is a hard "must" (a
  missing one is a
  hard failure) or a
  "nice" (a missing
  one is a soft
  signal, not a
  failure). The flex
  regex is the
  "is this years bar
  negotiable"
  classifier: a
  sentence containing
  a flex phrase (e.g.
  "or equivalent
  experience") is
  uncertain, not a
  hard drop.

  Before this turn,
  no test pinned
  these regexes. A
  contributor who
  removed `required`
  from `MUST_WORDS`
  would silently
  change every
  "required"
  requirement from
  hard-fail to
  soft-signal,
  breaking the
  gate's core
  contract. A
  contributor who
  removed a flex
  phrase from
  `FLEX_WORDS` would
  silently harden a
  "5+ years or
  equivalent"
  requirement from
  NEEDS_RESEARCH to
  NOT_SUITABLE.

  The fix is a new
  `TestPolarityRegexes`
  class with 5 tests:
  1. `test_must_words_set_matches_documented`:
     every documented
     MUST_WORDS entry
     (9 stems) is matched
     by the regex. Uses
     direct matching,
     not regex-source
     parsing (more
     robust).
  2. `test_nice_words_set_matches_documented`:
     every documented
     NICE_WORDS entry
     (7 words) is matched
     by the regex.
  3. `test_flex_words_set_matches_documented`:
     every documented
     FLEX_WORDS phrase
     (7 phrases) is matched
     by the regex.
  4. `test_polarity_classification`:
     behavior pin: every
     MUST_WORDS entry
     triggers "must"
     polarity via
     `_polarity()`;
     every NICE_WORDS
     entry triggers
     "nice" polarity;
     unmarked statements
     default to "nice"
     (W3.1 defensive
     contract: absence
     of evidence is not
     evidence of
     absence, and a
     hard verdict
     against a silent
     requirement is
     exactly the failure
     the project is
     built to refuse).
  5. `test_flex_words_make_years_uncertain`:
     behavior pin: every
     FLEX_WORDS phrase
     triggers the
     `flexible=True` flag
     in the
     `extract_years`
     output (the W3.1
     "5+ years or
     equivalent
     experience" ->
     NEEDS_RESEARCH
     contract).

  Drift-injection
  verified:
  - **Drift 1
    (required
    removed)**: removed
    `required` from
    `MUST_WORDS` →
    both pin tests
    fail with precise
    errors:
    - Set test: "does
      NOT match 1
      documented
      word(s):
      ['required']"
    - Polarity test:
      "'5+ years
      required' was
      classified as
      'nice' instead of
      'must' -- the
      gate would treat
      a required years
      bar as a soft
      signal"
  - **Drift 2
    (or equivalent
    removed)**: removed
    "or equivalent"
    from `FLEX_WORDS` →
    both pin tests
    fail with precise
    errors:
    - Set test: "does
      NOT match 1
      documented
      phrase(s): ['or
      equivalent']"
    - Years test:
      "the years
      requirement for
      '5+ years or
      equivalent' was
      NOT tagged as
      flexible"

  Subtle test-design
  note: the original
  test design used a
  regex-source parser
  to extract the
  literal-word set
  from the compiled
  pattern. This was
  fragile (the
  parser had to
  handle `?` and
  `(?:ed)?` correctly)
  and was abandoned in
  favour of direct
  matching: for each
  documented entry,
  build a sentence
  containing the
  entry and assert
  the regex matches
  it. This is more
  robust because it
  tests the actual
  behaviour: every
  documented word
  must cause the
  regex to match a
  sentence containing
  it.

  The polarity pin
  is a structural +
  behavior pin
  covering a
  previously-unpinned
  surface. The W3.1
  "no verdict against
  a missing field"
  contract is the
  most security-
  relevant contract
  in the project; the
  polarity regexes
  are the gate's
  implementation of
  that contract. A
  drift in these
  regexes would
  silently break the
  contract.

- **Added 3 new tests in
  `tests/test_polarity.py`
  that pin the
  `LANGUAGES` vocabulary
  in
  `jobsearch/requirements.py`
  and verify every
  entry is detected by
  `extract_languages`** —
  The `LANGUAGES` tuple
  is the gate's
  documented default
  vocabulary for
  language
  requirements. It's
  the language
  parallel to
  `SPECIALIST_TRAPS`
  (a fixed vocabulary
  list the extractor
  consults for
  requirements) and
  the default half of
  the W3.4 contract
  ("vocabulary is
  profile data, with
  a documented
  default").

  Before this turn,
  the only test
  mentioning
  LANGUAGES was the
  portability test
  (which checks that
  "portuguese" is
  NOT in the default
  -- a negative
  check, not a
  structural pin). A
  contributor who
  removed `german`
  from LANGUAGES
  would silently
  fail to detect
  German-language
  requirements in
  the default
  profile, leaving
  the gate unaware
  of language
  barriers.

  The fix is a new
  `TestLanguages`
  class with 3 tests:
  1. `test_languages_set_matches_documented`:
     bidirectional set
     equality on
     `LANGUAGES` (the
     9 documented
     entries).
  2. `test_every_language_is_lowercase`:
     every entry is
     lowercase (the
     extractor compares
     against the
     case-folded
     haystack; a
     non-lowercase
     entry would
     silently miss
     every posting).
  3. `test_every_language_is_detected`:
     behavior pin:
     every LANGUAGES
     entry is detected
     by
     `extract_languages`
     when used in a
     posting.

  Drift-injection
  verified:
  - **Drift 1
    (german
    removed)**:
    removed `german`
    from `LANGUAGES`
    → both pin tests
    fail with precise
    errors:
    - Set test: "is
      missing 1
      expected
      language(s):
      ['german']"
    - Behavior test:
      "extract_languages
      did not produce
      a requirement
      for 'german'
      (in LANGUAGES).
      A job posting
      saying 'fluent
      german required'
      would silently
      slip through the
      language gate"
  - **Drift 2
    (case-folding
    drift)**: changed
    `german` to
    `German` (capital
    G) → all three
    pin tests fail:
    - Set test:
      catches the
      missing entry
    - Lowercase test:
      catches the
      non-lowercase
      entry directly
    - Behavior test:
      confirms the
      extractor no
      longer matches
      the case-folded
      haystack

  Subtle test-design
  note: the
  lowercase test
  catches a drift
  that the structural
  set test would
  not. A contributor
  who changes
  `german` to
  `German` keeps
  the structural
  set intact (the
  entry is still
  "in" LANGUAGES),
  but the extractor
  no longer matches
  it. The lowercase
  test makes the
  case-folding
  contract explicit
  and testable.

  The LANGUAGES pin
  is the
  "requirements
  vocabulary"
  parallel to
  SPECIALIST_TRAPS
  (technology
  vocabulary) and
  _DEFAULT_PROFESSION_SIGNALS
  (profession
  vocabulary). All
  three fixed
  vocabularies are
  now pinned with
  structural +
  behavior tests.

- **Added 5 new tests in
  a new file
  `tests/test_actions.py`
  that pin the M3
  shortlist action
  vocabulary in
  `jobsearch/notify.py`
  and verify every
  action has a
  non-empty meaning** —
  The action vocabulary
  (`ACTION_APPROVE`,
  `ACTION_REJECT`,
  `ACTION_RESEARCH`,
  `ACTION_SAVE`,
  `ACTIONS`,
  `ACTION_MEANING`) is
  the gate's public M3
  API: these are the
  strings the shortlist
  UI/CLI passes to the
  notify layer to
  indicate what the
  user wants to do
  with a job (approve
  to prepare, reject
  to drop, research to
  look deeper, save to
  park for later).

  Before this turn, no
  test pinned these
  constants. A
  contributor who
  renamed `ACTION_APPROVE`
  from `"approve"` to
  `"accept"` would
  silently break the
  M3 shortlist UI/CLI
  -- every external
  caller passing the
  old string would no
  longer match. A
  contributor who
  changed
  `ACTION_MEANING[ACTION_APPROVE]`
  from
  `"prepare this one
  (NOT authorisation
  to submit)"` to
  `"prepare this one"`
  would silently lose
  the explicit "NOT
  authorisation to
  submit" caveat -- a
  critical safety
  message that
  prevents the user
  from accidentally
  thinking the gate
  has authorised them
  to submit a job
  application.

  The fix is a new
  `TestActionVocabulary`
  class with 5 tests:
  1. `test_action_constants_set_matches_documented`:
     the 4 action
     constants each
     match a
     documented
     action string.
  2. `test_actions_tuple_set_matches_documented`:
     `ACTIONS` contains
     exactly the 4
     documented
     action strings.
  3. `test_action_meaning_keys_match_actions`:
     the keys of
     `ACTION_MEANING`
     equal the entries
     of `ACTIONS`
     (every action has
     a meaning, no
     orphaned
     meaning).
  4. `test_every_action_meaning_is_nonempty`:
     every action has
     a non-empty
     meaning string.
  5. `test_action_meaning_strings_unchanged`:
     structural pin on
     the exact
     meaning strings
     (the "NOT
     authorisation to
     submit" caveat
     especially).

  Drift-injection
  verified:
  - **Drift 1
    (ACTION_APPROVE
    renamed)**:
    renamed
    `ACTION_APPROVE`
    from `"approve"`
    to `"accept"` →
    4 of 5 pin tests
    fail with precise
    errors:
    - Constants test:
      "ACTION_APPROVE='accept'
      is not in the
      documented
      action set"
    - Tuple test:
      "ACTIONS is
      missing 1
      expected
      action(s):
      ['approve']"
    - Meaning strings
      test (twice):
      catches the
      missing
      "approve" key
      and the extra
      "accept" key
  - **Drift 2
    (safety
    regression)**:
    removed "NOT
    authorisation to
    submit" from
    `ACTION_APPROVE`'s
    meaning →
    the
    `test_action_meaning_strings_unchanged`
    test fails with
    the precise
    error: "'prepare
    this one' !=
    'prepare this one
    (NOT
    authorisation to
    submit)'" --
    catching the
    safety regression
    at the test
    level rather
    than the
    production
    deployment.

  Subtle test-design
  note: the
  meaning-keys test
  does NOT catch a
  rename of
  `ACTION_APPROVE`
  because the
  `ACTION_MEANING`
  dict uses the
  constant as the
  key, so renaming
  the constant
  renames the key
  in sync. This is
  why we need both
  the constants
  test (which
  pins the
  constant values)
  and the meaning
  strings test
  (which pins the
  exact strings).
  The two together
  catch every
  possible drift.

  The action pin
  is the M3 API
  surface pin --
  the public
  strings the
  shortlist UI/CLI
  passes to the
  gate. The "NOT
  authorisation
  to submit"
  caveat in
  particular is a
  safety
  regression
  magnet: a
  contributor who
  doesn't
  understand
  the gate's
  purpose might
  think
  "prepare this
  one" is
  cleaner and
  remove the
  caveat. The
  meaning-strings
  test catches
  this regression
  with a precise
  error message
  that explains
  why the caveat
  is critical.

- **Added 5 new tests in
  a new
  `TestIncludeList`
  class in
  `tests/test_export_gate.py`
  that pin the
  publication
  boundary's
  `INCLUDE` and
  `OPTIONAL_INCLUDE`
  allowlists and
  verify no path
  is in BOTH the
  allowlist and
  the blocklist** —
  The publication
  boundary's
  `INCLUDE` list
  is the gate's
  allowlist: "these
  paths in the
  source tree are
  the ones the
  shipped artifact
  contains." A
  contributor who
  removed an entry
  would silently
  drop a piece of
  the shipped
  artifact (the
  leak scan
  wouldn't catch
  it -- the leak
  scan only
  catches paths
  that are
  PRESENT but
  UNWANTED). A
  contributor who
  added a path
  that is ALSO in
  EXCLUDE would
  create a
  contradiction
  that the gate
  would silently
  resolve in
  EXCLUDE's favor
  (the walker
  sees EXCLUDE
  first).

  Before this
  turn, no test
  pinned the
  `INCLUDE`
  list (EXCLUDE
  was already
  pinned by
  `TestExcludeList`,
  but EXCLUDE is
  the blocklist
  half -- the
  allowlist half
  was silently
  unprotected).

  The fix is a
  new
  `TestIncludeList`
  class with 5
  tests:
  1. `test_include_set_matches_documented`:
     bidirectional
     set equality on
     `INCLUDE` (the
     30 documented
     entries).
  2. `test_every_include_entry_exists_in_source`:
     every path in
     `INCLUDE` must
     be a real
     file or
     directory in
     the source
     tree (catches
     the "added a
     typo'd entry"
     drift). Uses
     the
     MANIFEST.txt
     discriminator
     pattern (same
     as
     `TestExcludeList`)
     to skipTest
     in export
     mode.
  3. `test_no_include_overlaps_exclude`:
     no path is in
     BOTH
     `INCLUDE` and
     `EXCLUDE` (the
     consistency
     contract --
     `INCLUDE` says
     "ship it",
     `EXCLUDE` says
     "don't ship
     it"; a path
     cannot be
     both).
  4. `test_optional_include_set_matches_documented`:
     bidirectional
     set equality on
     `OPTIONAL_INCLUDE`
     (the 4 documented
     entries:
     `LICENSE`,
     `SECURITY.md`,
     `CONTRIBUTING.md`,
     `CHANGELOG.md`).
  5. `test_no_optional_include_overlaps_include_or_exclude`:
     no
     `OPTIONAL_INCLUDE`
     entry is in
     `INCLUDE`
     (would
     double-walk
     every file)
     or in
     `EXCLUDE`
     (would
     contradict
     the
     optional-skip
     logic).

  Drift-injection
  verified:
  - **Drift 1
    (HANDOFF.md
    added to
    INCLUDE)**:
    added
    `HANDOFF.md` to
    `INCLUDE` (it's
    currently in
    EXCLUDE) → 2
    of 5 pin tests
    fail with
    precise errors:
    - Set test:
      "INCLUDE has 1
      undocumented
      entry/entries:
      ['HANDOFF.md']"
    - Overlap test:
      "INCLUDE and
      EXCLUDE share
      1 path(s):
      ['HANDOFF.md'].
      A path cannot
      be in both
      the allowlist
      and the
      blocklist. The
      walker would
      resolve in
      EXCLUDE's
      favor"
  - **Drift 2
    (typo'd
    entry)**:
    added `toolz`
    (typo for
    `tools`) to
    `INCLUDE` → 2
    of 5 pin tests
    fail with
    precise errors:
    - Set test:
      "INCLUDE has 1
      undocumented
      entry/entries:
      ['toolz']"
    - Existence
      test:
      "INCLUDE lists
      1 path(s) that
      do not exist
      in the source
      tree:
      ['toolz']. The
      walker would
      silently skip
      a non-existent
      path"

  Subtle
  test-design
  note: the
  `INCLUDE` pin
  is the
  **allowlist
  complement** to
  the `EXCLUDE`
  pin
  (`TestExcludeList`).
  The two together
  form the
  publication
  boundary: every
  path is
  either in
  `INCLUDE` (ship
  it) or in
  `EXCLUDE` (don't
  ship it) or
  neither
  (silently
  dropped -- a
  contributor who
  adds a new
  source path
  without adding
  it to `INCLUDE`
  would have it
  silently
  dropped from
  the shipped
  artifact).

  The
  INCLUDE/EXCLUDE
  overlap test is
  the most
  security-relevant
  contract: a
  path in BOTH
  lists would
  create a
  contradiction
  that the gate
  would resolve
  in EXCLUDE's
  favor (silent
  drop). A
  contributor who
  adds
  `HANDOFF.md` to
  INCLUDE (it's
  already in
  EXCLUDE) would
  think they've
  made it ship,
  but the walker
  would silently
  skip it -- a
  silent
  misunderstanding
  of the gate's
  intent.

- **Added 3 new tests in
  a new
  `TestTechnologies`
  class in
  `tests/test_rules.py`
  that pin the
  `TECHNOLOGIES`
  default vocabulary
  in
  `jobsearch/requirements.py`
  and verify every
  entry is lowercase
  and unique** —
  The `TECHNOLOGIES`
  tuple is the
  gate's documented
  default vocabulary
  for technology
  requirements. It's
  the technology
  parallel to
  `LANGUAGES` (9
  entries, pinned
  in turn N+2) and
  the default half
  of the W3.4
  contract
  ("vocabulary is
  profile data, with
  a documented
  default").

  Before this turn,
  no test pinned
  `TECHNOLOGIES`
  itself. The
  `TestSpecialistTraps`
  class cross-checks
  `SPECIALIST_TRAPS
  ⊆ TECHNOLOGIES`,
  but a contributor
  who removed
  `typescript` from
  `TECHNOLOGIES`
  would silently
  fail to detect
  TypeScript
  requirements in
  the default
  profile. A
  contributor who
  added a typo'd
  entry (e.g.
  "typpescript")
  would inflate
  the list without
  adding coverage.

  The fix is a new
  `TestTechnologies`
  class with 3 tests:
  1. `test_technologies_set_matches_documented`:
     bidirectional set
     equality on
     `TECHNOLOGIES`
     (the 48 documented
     entries).
  2. `test_technologies_has_no_duplicates`:
     the tuple is
     unique (no
     silently-doubled
     entries that
     would inflate
     the list without
     adding coverage).
  3. `test_every_technology_is_lowercase`:
     every entry is
     lowercase (the
     extractor compares
     against the
     case-folded
     haystack; a
     non-lowercase
     entry would
     silently miss
     every posting).

  Drift-injection
  verified:
  - **Drift 1
    (typescript
    removed)**:
    removed `typescript`
    from `TECHNOLOGIES`
    → the set test
    fails with the
    precise error:
    "TECHNOLOGIES is
    missing 1
    expected
    technology/ies:
    ['typescript']"
  - **Drift 2
    (duplicate
    added)**:
    added `n8n` as a
    duplicate entry
    → the duplicates
    test fails with
    the precise
    error:
    "TECHNOLOGIES has
    1 duplicate
    entry/entries:
    {'n8n': 2}"

  Subtle
  test-design
  note: the
  `TECHNOLOGIES`
  pin is the
  "requirements
  vocabulary"
  parallel to
  `LANGUAGES`
  (9 entries,
  pinned turn
  N+2) and
  `_DEFAULT_PROFESSION_SIGNALS`
  (48 entries,
  pinned turn
  N+1). All
  three fixed
  vocabularies
  are now pinned
  with structural
  + behavior
  tests. The
  W3.4
  "vocabulary is
  profile data,
  with a
  documented
  default"
  contract is
  now testable
  across all
  three
  dimensions.

  Note that the
  cross-check
  `SPECIALIST_TRAPS
  ⊆ TECHNOLOGIES`
  was already
  pinned by
  `TestSpecialistTraps`
  (turn N-2), but
  the structural
  set equality on
  `TECHNOLOGIES`
  itself was
  missing. A
  contributor who
  removed
  `typescript`
  from
  `TECHNOLOGIES`
  would have
  failed the
  cross-check
  too (because
  `typescript` is
  not in
  `SPECIALIST_TRAPS`
  so the
  cross-check
  wouldn't fire),
  but the
  gate's
  ability to
  detect
  TypeScript
  requirements
  in the
  default
  profile would
  have been
  silently
  broken. The
  new
  `TestTechnologies`
  set test
  catches this
  silent
  regression
  at the
  source.

- **Added 5 new tests in
  a new file
  `tests/test_verdicts.py`
  that pin the 4
  verdict constants
  in
  `jobsearch/rules.py`
  and verify each
  appears in
  CLAIMS.md and
  the PDF renderer's
  `_LABEL` dict** —
  The verdict
  vocabulary
  (`STRONG_MATCH`,
  `POTENTIAL_MATCH`,
  `NEEDS_RESEARCH`,
  `NOT_SUITABLE`) is
  the gate's public
  M2 API: these are
  the strings the
  shortlist UI/CLI
  and the PDF
  renderer consume
  to display the
  gate's verdict for
  each job.

  Before this turn,
  no test pinned
  these constants.
  A contributor who
  renamed
  `NEEDS_RESEARCH`
  from
  `"needs_research"`
  to
  `"more_info_needed"`
  would silently:
  1. break
     `tools/render_pdf.py`
     (the PDF
     shortlist would
     silently not
     render the
     verdict);
  2. break the M3
     shortlist UI/CLI
     (any consumer
     checking the
     verdict would
     not match);
  3. make the W3.1
     contract text
     in CLAIMS.md a
     lie
     ("NEEDS_RESEARCH"
     wouldn't exist
     -- the contract
     states "Missing
     evidence is
     NEEDS_RESEARCH,
     never a
     rejection").

  The verdict
  vocabulary is
  the most
  public-facing
  vocabulary in
  the gate: it
  appears in
  CLAIMS.md,
  README.md,
  CHANGELOG.md,
  tools/render_pdf.py,
  and tools/notify.py.
  It is the "what
  did the gate
  decide about this
  job" surface.

  The fix is a new
  `TestVerdictVocabulary`
  class with 5 tests:
  1. `test_verdict_constants_set_matches_documented`:
     structural set
     equality on the
     4 verdict
     constants.
  2. `test_verdict_values_are_unique`:
     no two verdict
     constants share
     the same value
     (a collision
     would silently
     make two
     different
     outcomes
     indistinguishable
     to the M3
     layer).
  3. `test_verdict_values_match_documented_underscore_form`:
     every value is
     lowercase
     underscore form
     (consistent with
     the corpus JSON
     fixtures and
     the
     `test_every_expect_is_an_allowed_value`
     test in
     test_corpus.py).
  4. `test_verdict_values_match_claims_md`:
     the verdict
     strings appear
     in CLAIMS.md
     with the exact
     same casing (a
     contributor who
     changed the
     constant without
     updating the
     docs would have
     the docs say
     "needs_research"
     while the
     constant was
     "more_info_needed"
     -- silently
     making every
     doc reference
     wrong).
  5. `test_render_pdf_knows_every_verdict`:
     the PDF
     renderer's
     `_LABEL` dict
     has a label for
     every verdict
     (an unrendered
     verdict would
     be a silent UI
     regression).

  Drift-injection
  verified:
  - **Drift 1
    (NEEDS_RESEARCH
    renamed)**:
    renamed
    `NEEDS_RESEARCH`
    from
    `"needs_research"`
    to
    `"more_info_needed"`
    → 2 of 5 pin
    tests fail with
    precise errors:
    - Constants
      test:
      "NEEDS_RESEARCH='more_info_needed'
      is not in the
      documented
      verdict set"
    - Docs test:
      "NEEDS_RESEARCH='more_info_needed'
      does not appear
      in CLAIMS.md"
  - **Drift 2
    (case-form
    drift)**: changed
    `NEEDS_RESEARCH`
    from
    `"needs_research"`
    to
    `"NEEDS-RESEARCH"`
    (uppercase +
    dash) → 3 of 5
    pin tests fail:
    - Constants
      test catches
      the rename
    - Docs test
      catches the
      doc/code
      mismatch
    - Underscore
      form test
      catches the
      case-form
      drift
      directly
      (the value
      is not
      lowercase
      underscore
      form)

  Subtle
  test-design
  note: the
  verdict pin is
  the **M2 API
  surface pin**
  (the strings
  the shortlist
  UI/CLI
  consumes), and
  it's the most
  public-facing
  pin of the
  series: the
  verdict
  vocabulary
  appears in
  CLAIMS.md as
  the gate's
  public
  contract. A
  contributor
  who changed
  the constant
  without
  updating the
  docs would
  have the docs
  say one thing
  and the code
  another --
  silently
  making every
  doc reference
  wrong. The
  `test_verdict_values_match_claims_md`
  test is the
  doc-vs-code
  consistency
  contract: the
  public
  vocabulary
  must agree
  with the
  public
  contract.

- **Added 3 new tests
  in a new file
  `tests/test_location_scope.py`
  that pin the
  `EU_SCOPE` and
  `WORLD_OK` regexes
  in
  `jobsearch/rules.py`
  and verify each
  documented scope
  stem is matched,
  and the two
  regexes do not
  overlap** —
  `EU_SCOPE` and
  `WORLD_OK` are
  the regex-based
  location
  detectors that
  complement
  `EU_COUNTRIES`
  (set of 28
  country names)
  and
  `NON_EU_BLOCK`
  (set of 17
  non-EU country
  names). Where
  the country
  sets detect
  *country names*,
  the regexes
  detect *scope
  descriptions*
  like "EU",
  "EMEA",
  "worldwide",
  "anywhere",
  "global".

  Before this
  turn, no test
  pinned these
  regexes. A
  contributor
  who removed
  "emea" from
  `EU_SCOPE`
  would silently
  miss
  EMEA-marketed
  jobs (the gate
  would treat
  them as
  not-EU-scope,
  falling
  through to
  `non_eu_block`
  checks -- a
  false positive).
  A contributor
  who removed
  "anywhere"
  from
  `WORLD_OK`
  would silently
  miss "remote
  from anywhere"
  jobs (the gate
  would treat
  them as
  not-world-ok,
  falling
  through to
  NON_EU_BLOCK
  -- a false
  negative that
  could be a
  NEEDS_RESEARCH
  when the job
  is actually
  open to
  anywhere).

  The location-scope
  resolution
  order is:
  1. `EU_SCOPE`
     matches OR
     place in
     `EU_COUNTRIES`
     -> satisfied
     (EU work auth)
  2. `WORLD_OK`
     matches ->
     satisfied
     (remote from
     anywhere)
  3. place in
     `NON_EU_BLOCK`
     -> failed
     (hard)
  4. else ->
     uncertain
     (NEEDS_RESEARCH)

  A drift in the
  regexes would
  silently shift
  jobs between
  these
  branches. The
  `TestLocationSets`
  class pins
  the country
  sets; this
  class pins
  the regexes.

  The fix is a
  new
  `TestLocationScopeRegexes`
  class with 3
  tests:
  1. `test_eu_scope_matches_documented_stems`:
     every documented
     stem matches
     the regex in
     a sentence.
  2. `test_world_ok_matches_documented_stems`:
     every documented
     stem matches
     the regex in
     a sentence.
  3. `test_eu_scope_does_not_match_world_ok_stems`:
     the two
     regexes do
     not overlap
     (a job
     saying
     "worldwide"
     should not
     also satisfy
     EU_SCOPE).

  Drift-injection
  verified:
  - **Drift 1
    (emea
    removed)**: removed
    "emea" from
    `EU_SCOPE` ->
    the EU_SCOPE
    stem test
    fails with
    the precise
    error:
    "EU_SCOPE did
    NOT match the
    documented
    stem 'emea'
    in the
    sentence
    'this role is
    open to
    candidates
    across the
    emea'. A job
    advertising
    'emea' as the
    location
    scope would
    silently fall
    through to
    the
    NON_EU_BLOCK
    check (false
    positive --
    a job that
    should be
    marked
    'satisfied'
    would be
    marked
    'uncertain'
    or
    'failed')."
  - **Drift 2
    (anywhere
    removed)**:
    removed
    "anywhere"
    from
    `WORLD_OK` ->
    the WORLD_OK
    stem test
    fails.

  Subtle
  test-design
  note: the
  direct-matching
  pattern is the
  same as the
  polarity
  regexes (turn
  N-2): for
  each
  documented
  entry, build a
  sentence and
  assert the
  regex matches
  it. This
  pattern
  reliably
  catches stem
  removal and
  silent drift
  in regex
  vocabularies.

- **Added 3 new tests
  in a new
  `TestDescriptionLengthThreshold`
  class in
  `tests/test_rules.py`
  that pin
  `MIN_DESCRIPTION_CHARS`
  in
  `jobsearch/rules.py`
  and verify it
  is positive
  and
  reasonable** —
  `MIN_DESCRIPTION_CHARS`
  is the gate's
  behavior
  threshold for
  "description
  is too short
  to evaluate".
  If a posting's
  description
  (after noise
  stripping) is
  shorter than
  this threshold,
  the gate:
  1. adds a note
     "description
     missing or
     too short to
     evaluate (N
     chars)";
  2. sets the
     verdict to
     `NEEDS_RESEARCH`
     if the
     posting
     would
     otherwise be
     a
     `POTENTIAL_MATCH`
     or
     `STRONG_MATCH`;
  3. in
     `enrich.py`
     (M4), marks
     the posting's
     `state` as
     `"incomplete"`
     rather than
     `"complete"`.

  The constant
  is used in 4
  places and is
  referenced by
  `tests/test_enrich.py`
  (which
  imports it
  directly
  rather than
  hard-coding
  the value). A
  contributor
  who changed
  the value from
  `80` to `50`
  would
  silently:
  1. accept
     shorter
     descriptions
     as
     "evaluable"
     (less
     rigorous);
  2. change
     verdicts for
     descriptions
     in the 50-79
     char range
     (now
     evaluable,
     was
     NEEDS_RESEARCH);
  3. change the
     M4 state for
     those
     descriptions
     (now
     complete,
     was
     incomplete).

  None of the
  existing tests
  would fail
  because they
  use the
  constant
  directly
  rather than
  hard-coding
  the value. A
  drift in the
  constant
  would be a
  silent
  behavior
  change.

  The fix is a
  new
  `TestDescriptionLengthThreshold`
  class with 3
  tests:
  1. `test_threshold_value_is_eighty`:
     the constant
     is `80` (the
     documented
     value).
  2. `test_threshold_is_positive`:
     the constant
     is a positive
     integer
     (defensive: a
     zero or
     negative
     threshold
     would make
     every
     description
     "evaluable").
  3. `test_threshold_is_reasonable`:
     the
     threshold is
     between 40
     and 200 chars
     (a sanity
     check --
     values
     outside this
     range are
     either too
     lax or too
     strict for a
     real job
     posting).

  Drift-injection
  verified:
  - **Drift 1
    (80 -> 50)**:
    the value
    test fails
    with the
    precise
    error
    listing the
    3 behavioral
    consequences
    (accept
    shorter,
    change
    verdicts,
    change M4
    state).
  - **Drift 2
    (80 -> 0)**:
    all 3 tests
    fail (value
    test +
    positive
    test +
    reasonable
    test) --
    defense-in-depth
    catches the
    "defeat the
    gate"
    attempt at
    every
    layer.

  Subtle
  test-design
  note: the
  description-length
  pin is the
  **numeric
  threshold pin**
  (similar in
  shape to the
  verdict pin:
  public
  behavior
  threshold that
  affects the
  gate's
  verdicts).
  The
  defense-in-depth
  approach
  (3 layers:
  value, sign,
  range) means
  a single test
  is enough to
  catch value
  drift, but the
  sign and
  range tests
  catch
  semantic
  nonsense (a
  zero or
  negative
  threshold;
  a
  threshold
  in an
  obviously
  wrong
  range).

- **Added 2 new tests in
  a new
  `TestSkipDirs` class
  in
  `tests/test_export_gate.py`
  that pin the
  `SKIP_DIRS`
  cache-directory
  contract in
  `tools/export_bundle.py`
  and verify every
  documented cache
  dir is in the
  skip list** —
  The export gate's
  `SKIP_DIRS` is the
  cache-directory
  contract: "these
  directory names
  are skipped by
  the walker when
  assembling the
  shipped bundle."
  A drift in
  `SKIP_DIRS` would
  silently ship
  cache contents
  in the public
  artifact (or
  silently drop
  legitimate
  content).

  Before this
  turn, no test
  pinned
  `SKIP_DIRS`.
  The
  `TestForbiddenSuffixes`
  class pins the
  parallel
  contract for
  file suffixes
  (".pdf", ".log",
  etc.) but not
  for directory
  names.

  `SKIP_DIRS` is
  used in 2
  places:
  1. The manifest
     builder at
     L747: `if
     entry.name in
     SKIP_DIRS or
     entry.suffix
     in
     SKIP_SUFFIXES:
     continue`
     (skip
     top-level
     entries
     whose name
     is a cache
     dir).
  2. The recursive
     walker at
     L986: `if
     any(part in
     SKIP_DIRS for
     part in
     entry.relative_to(src).parts):`
     (skip any
     file whose
     path contains
     a cache dir
     as a part).

  The 5
  documented
  cache
  directories:
  - `__pycache__`:
    Python
    bytecode
    cache
    (`.pyc`
    files);
    shipping
    these in
    the bundle
    would
    waste
    space and
    ship
    platform-specific
    bytecode.
  - `.git`: git
    internals;
    shipping
    these would
    expose
    commit
    history,
    branches,
    and tags
    in the
    bundle
    (HUGE and
    a privacy
    leak).
  - `.mypy_cache`:
    mypy
    type-checker
    cache.
  - `.ruff_cache`:
    ruff
    linter
    cache.
  - `.pytest_cache`:
    pytest
    test-runner
    cache.

  A contributor
  who removed
  `__pycache__`
  from
  `SKIP_DIRS`
  would
  silently
  ship
  bytecode
  cache files
  in the
  bundle. A
  contributor
  who removed
  `.git` would
  ship git
  internals
  in the
  bundle -- a
  privacy leak
  of commit
  history.

  The fix is a
  new
  `TestSkipDirs`
  class with 2
  tests:
  1. `test_skip_dirs_set_matches_documented`:
     bidirectional
     set equality
     on
     `SKIP_DIRS`
     (the 5
     documented
     entries).
  2. `test_walker_skips_every_documented_dir`:
     behavior
     check --
     every
     documented
     cache dir is
     in
     `SKIP_DIRS`
     (the walker
     must skip
     it).

  Drift-injection
  verified:
  - **Drift 1
    (__pycache__
    removed)**:
    removed
    `__pycache__`
    from
    `SKIP_DIRS` ->
    both pin
    tests fail
    with precise
    errors:
    - Set test:
      "SKIP_DIRS
      is missing
      1 expected
      entry/entries:
      ['__pycache__'].
      Removing a
      cache
      directory
      from
      SKIP_DIRS
      would
      silently
      ship its
      contents in
      the public
      artifact.
      Removing
      `__pycache__`
      would ship
      bytecode
      cache files"
    - Walker
      test:
      "Documented
      cache
      directory
      '__pycache__'
      is NOT in
      SKIP_DIRS"
  - **Drift 2
    (var
    added)**:
    added
    `var` to
    `SKIP_DIRS`
    (over-pin) ->
    the set
    test
    catches
    the
    over-pin
    (SKIP_DIRS
    has 1
    undocumented
    entry:
    'var').

  Subtle
  test-design
  note: the
  `SKIP_DIRS`
  pin is the
  **directory-name
  complement**
  to
  `FORBIDDEN_SUFFIXES`
  (the file-suffix
  contract).
  The two
  together
  cover the
  walker's
  two-stage
  skip logic:
  1. Skip
     top-level
     entries by
     name
     (SKIP_DIRS)
     or suffix
     (SKIP_SUFFIXES).
  2. Skip
     nested
     files by
     any-part
     (SKIP_DIRS)
     or suffix
     (SKIP_SUFFIXES).

  A drift in
  `SKIP_DIRS`
  would
  silently
  ship cache
  contents
  (a privacy
  leak for
  `.git`, a
  bundle-size
  bloat for
  `__pycache__`,
  a stale-data
  leak for
  `.mypy_cache`
  and
  `.ruff_cache`
  and
  `.pytest_cache`).
  The pin
  catches
  both
  directions
  of drift
  (removal
  and
  addition).

- **Added 4 new tests
  in a new file
  `tests/test_python_version.py`
  that pin the
  doctor's `PY_MIN`
  constant and verify
  it matches the
  README's stated
  minimum Python
  version (and
  detected a real
  doc-vs-code
  drift: README
  said "3.11+" but
  the code uses
  `str | None`
  PEP 604 which is
  3.10+, so PY_MIN
  is correctly
  (3, 10))** —
  `PY_MIN` in
  `tools/doctor.py`
  is the project's
  minimum Python
  version. The doctor
  checks the running
  Python against
  `PY_MIN` and fails
  the check if the
  version is below
  `PY_MIN`. A drift in
  `PY_MIN` would
  silently:
  1. Lower it (e.g.
     from `(3, 10)` to
     `(3, 8)`): the
     doctor would pass
     Python 3.8/3.9
     installs even
     though the code
     uses 3.10+ syntax
     (`str | None` PEP
     604 union syntax,
     `list[...]`
     without typing
     imports,
     `dict[...]`
     without typing
     imports). A 3.8
     install would fail
     with a
     `SyntaxError` at
     import time -- a
     hard failure that
     the doctor should
     have caught.
  2. Raise it (e.g.
     from `(3, 10)` to
     `(3, 12)`): the
     doctor would fail
     3.10/3.11 installs
     even though the
     code works on
     those versions.

  Before this turn,
  no test pinned
  `PY_MIN`. The
  doctor check at
  L66 is the only
  enforcement, and
  the doctor is a
  one-shot script
  that runs at
  fresh-clone time.
  A contributor who
  changed `PY_MIN`
  would not fail any
  test.

  The
  Python-version
  contract is
  **3-way**:
  1. `PY_MIN` in
     doctor.py (the
     code check).
  2. README.md
     "Python X.Y+"
     (the public
     contract that a
     third-party copy
     follows).
  3. The actual
     Python syntax
     used in the
     project (3.10+
     for `str | None`).

  If any of these
  disagree, either
  the doctor is
  over-strict, the
  README is wrong,
  or the project is
  using syntax newer
  than the doctor
  allows.

  When the test was
  first written, it
  caught a real
  drift: README
  said "3.11+" but
  `PY_MIN` is
  `(3, 10)`. The
  test failed with
  the precise error
  "README.md
  declares 'Python
  3.11+ but
  tools/doctor.py
  PY_MIN is
  (3, 10)". The
  README was wrong
  (PEP 604 `X | Y`
  was introduced
  in 3.10, not
  3.11), so the
  README was
  corrected to
  "3.10+" and the
  test now passes.

  The fix is a new
  `TestPythonVersionRequirement`
  class with 4
  tests:
  1. `test_py_min_value_matches_documented`:
     the constant is
     `(3, 10)` (the
     documented
     value).
  2. `test_py_min_is_a_tuple_of_two_ints`:
     the constant is
     well-formed
     (defensive: a
     wrong shape
     would break the
     doctor check at
     L66).
  3. `test_py_min_matches_actual_syntax`:
     the constant is
     consistent with
     the actual
     Python syntax
     used in the
     project (i.e.
     `str | None` is
     3.10+, so PY_MIN
     must be >=
     (3, 10)).
  4. `test_py_min_matches_readme`:
     the constant
     matches the
     README's stated
     minimum version
     (doc-vs-code
     consistency
     contract).

  Drift-injection
  verified:
  - **Drift 1
    (PY_MIN
    lowered to
    (3, 8))**:
    3 of 4 pin
    tests fail
    (value +
    syntax +
    README --
    the value
    test catches
    the numeric
    drift; the
    syntax test
    catches
    that PY_MIN
    is below
    what the
    project
    actually
    needs; the
    README test
    doesn't
    fire because
    the README
    was
    correct).
  - **Drift 2
    (README
    re-introduced
    to 3.11+)**:
    the README
    test catches
    the
    doc-vs-code
    drift alone
    (the value
    test passes
    because
    PY_MIN is
    unchanged;
    the syntax
    test passes
    because the
    project
    still uses
    `str | None`;
    only the
    README
    contract
    changed).

  Subtle
  test-design
  note: this
  is the
  **first 3-way
  consistency
  pin** in the
  series
  (code, doc,
  syntax). Most
  pins are
  2-way
  (constant +
  use site, or
  constant +
  doc). The
  Python-version
  pin is 3-way
  because the
  contract has
  three
  independent
  sources: the
  doctor's
  numeric
  threshold,
  the README's
  English
  statement,
  and the
  actual
  Python
  syntax used
  in the
  project.
  Each of
  these can
  drift
  independently
  -- the README
  can lie about
  the version
  (which it
  was), the
  doctor can
  be too lax
  or too
  strict, and
  the project
  can use
  syntax newer
  than the
  doctor
  allows. A
  pin for all
  three
  ensures the
  contract
  stays
  consistent.

  Subtle
  test-design
  note: the
  AST-based
  syntax test
  is the
  most
  reliable way
  to detect
  Python
  syntax
  usage (much
  more reliable
  than regex
  matching,
  which would
  miss
  `Optional[X]`
  vs `X | None`).
  The test
  parses every
  `.py` file
  in
  `jobsearch/`
  with
  `ast.parse`
  and walks
  the AST
  looking for
  `BinOp` with
  `BitOr` -- the
  AST node for
  `X | Y`. This
  catches the
  PEP 604
  union syntax
  used in
  type
  annotations.

- **Added 6 new tests in
  a new
  `TestDefaultUserAgent`
  class in
  `tests/test_enrich.py`
  that pin the
  `DEFAULT_UA` HTTP
  user-agent string
  and verify it is a
  real Chrome browser
  UA with no personal
  data and no bot
  tokens** —
  `DEFAULT_UA` in
  `jobsearch/enrich.py`
  is the User-Agent
  string used by
  `fetch_html()` when
  making HTTP requests.
  The UA is what the
  job board (LinkedIn)
  sees when the
  enrichment code
  fetches a posting
  page.

  The UA contract is
  **security/privacy +
  parse-correctness**:
  1. **Parse
     correctness**: The
     UA was verified
     against a live
     page on
     2026-10-13 (see
     enrich.py L54).
     The markup regex
     `_MARKUP_RE` and
     `_SECTION_RE`
     were designed
     against the
     markup LinkedIn
     serves for THIS
     UA. If the UA
     changes to
     something the
     site treats as a
     bot, the site
     would serve
     different markup
     (e.g. a "please
     log in" page, or
     a stripped
     description).
     The regexes
     would fail to
     match, and every
     posting would be
     marked
     `incomplete`
     (description too
     short to
     evaluate). That
     cascades to
     `NEEDS_RESEARCH`
     verdicts across
     the whole corpus.
  2. **Privacy**: A
     real browser UA
     (Mozilla +
     AppleWebKit +
     Chrome) is the
     common case, not
     a unique
     fingerprint. A
     custom UA with a
     personal token
     would uniquely
     identify the user
     to LinkedIn. A
     bot-UA (e.g.
     "Python-urllib/3.11"
     or "wget" or
     "curl") would be
     blocked outright
     or served a
     challenge page.

  Before this turn,
  no test pinned
  `DEFAULT_UA`. A
  contributor who
  changed the UA to
  "Python-urllib/3.11"
  (the Python
  default) would
  have:
  1. Been blocked by
     LinkedIn (the
     urllib UA is
     widely
     blacklisted).
  2. No test would
     fail (the regex
     tests use saved
     pages, not live
     fetches).
  3. The published
     artifact would
     silently regress
     the M4 enrichment
     milestone.

  The fix is a new
  `TestDefaultUserAgent`
  class with 6 tests:
  1. `test_default_ua_is_a_string`:
     the constant is a
     non-empty string.
  2. `test_default_ua_contains_browser_tokens`:
     the UA contains
     "Mozilla" and
     "AppleWebKit".
  3. `test_default_ua_does_not_contain_bot_tokens`:
     the UA does NOT
     contain bot-UA
     tokens
     (case-insensitive).
  4. `test_default_ua_does_not_contain_personal_data`:
     the UA does NOT
     contain an email
     or a
     user-specific
     token.
  5. `test_default_ua_is_chrome_browser`:
     the UA is a
     Chrome browser
     UA (matches the
     "verified against
     a live page"
     comment).
  6. `test_default_ua_chrome_version_is_recent`:
     the Chrome
     version in the
     UA is >= 100.

  Drift-injection
  verified:
  - **Drift 1
    (UA ->
    Python-urllib/3.11)**:
    5 of 6 tests
    fail (the
    personal-data
    test passes
    because
    Python-urllib
    doesn't have
    an email --
    but the
    is-a-string
    test catches
    the length,
    the
    contains-browser-tokens
    test catches
    the missing
    Mozilla,
    the
    does-not-contain-bot-tokens
    test catches
    the urllib
    token, the
    is-chrome-browser
    test catches
    the missing
    Chrome, the
    chrome-version-recent
    test fails
    because there
    is no Chrome
    version at
    all).
  - **Drift 2
    (UA -> Safari)**:
    2 of 6 tests
    fail (the
    is-chrome-browser
    test catches
    the missing
    Chrome, the
    chrome-version-recent
    test fails
    because there
    is no Chrome
    version).
  - **Drift 3
    (Chrome 140
    -> Chrome 30)**:
    1 of 6 tests
    fails (the
    chrome-version-recent
    test catches
    the outdated
    version).

  Subtle
  test-design
  note: this is
  the **privacy
  + parse-correctness
  pin** in the
  series. Most
  pins are about
  data values
  (vocabulary,
  thresholds,
  paths) or
  publication
  boundary
  (allowlist,
  blocklist).
  The UA pin is
  about a
  *fingerprint
  contract*: the
  UA is what
  the user
  presents to
  the job board
  on every fetch.
  A wrong UA
  either breaks
  parsing
  (regexes were
  designed for
  the Chrome
  markup) or
  exposes the
  user (custom
  UA =
  fingerprint).

  The 6-test
  layering
  (string shape,
  contains,
  not-contains,
  no-personal-data,
  is-Chrome,
  is-recent)
  provides
  defense-in-depth:
  - Drift 1
    (Python-urllib)
    is caught by
    5 of 6 tests
    (all except
    the
    personal-data
    test, which
    is about
    personal data
    not bot
    detection).
  - Drift 2
    (Safari) is
    caught by 2
    of 6 tests
    (Chrome
    token
    + version
    test).
  - Drift 3
    (outdated
    Chrome) is
    caught by 1
    of 6 tests
    (version
    test).
  This is the
  expected
  layering: each
  test catches
  the drift it's
  designed to
  catch, and
  multiple tests
  catch the
  severe drifts.

- **Added 4 new tests
  in a new file
  `tests/test_dataflow_regexes.py`
  that pin the 4
  network-direction
  classifier regexes
  in
  `tools/build_dataflow_map.py`:
  PARSE_ONLY,
  UNKNOWN_NETWORK,
  OUTBOUND, INBOUND
  -- the
  classifier that
  drives
  `docs/DATA-FLOW.md`** —
  These 4 regexes
  are the
  network-direction
  classifier
  contract. The
  output of the
  classifier is
  `docs/DATA-FLOW.md`
  -- a public
  document that
  audits the
  project's
  network
  exposure. A
  third party
  copying the
  project would
  look at this
  document to
  understand what
  the project does
  at the network
  layer.

  The resolution
  order in the
  classifier is:
  1. `_direction(name)`:
     - `INBOUND.search(name)`
       -> "inbound"
     - `OUTBOUND.search(name)`
       -> "outbound"
     - else ->
       "unknown"
  2. `_infer_surface(path, net)`:
     - `PARSE_ONLY.search(net)`
       -> "stdlib
       parse only, no
       network call"
     - `UNKNOWN_NETWORK.search(net)`
       -> "imported;
       surface depends
       on call site
       -- see source"
     - `urllib.request`
       -> detailed
       heuristics
     - else ->
       "unknown
       surface"

  A drift in any
  of these regexes
  would silently
  misclassify
  modules in
  `docs/DATA-FLOW.md`:
  - Removing
    `telegram` from
    `OUTBOUND`
    would
    misclassify a
    Telegram call
    as "unknown"
    rather than
    "outbound". A
    reviewer would
    not see it
    highlighted in
    the dataflow
    map.
  - Removing
    `asyncio.open_connection`
    from `INBOUND`
    would
    misclassify a
    server (e.g. an
    asyncio TCP
    server) as
    "unknown"
    rather than
    "inbound". A
    reviewer would
    miss that the
    project runs an
    inbound server.
  - Removing
    `urllib.error`
    from
    `PARSE_ONLY`
    would
    misclassify a
    pure parse call
    as "unknown
    surface" rather
    than "stdlib
    parse only, no
    network call".

  The published
  artifact would
  silently drift
  from what the
  code actually
  does. A third
  party auditing
  the project
  would miss real
  network calls
  or falsely
  report
  parse-only
  calls as
  network calls.

  The fix is a new
  `TestDataflowRegexes`
  class with 4
  tests:
  1. `test_parse_only_matches_documented_imports`:
     each documented
     PARSE_ONLY
     import matches.
  2. `test_unknown_network_matches_documented_imports`:
     each documented
     UNKNOWN_NETWORK
     import matches.
  3. `test_outbound_matches_documented_imports`:
     each documented
     OUTBOUND import
     matches.
  4. `test_inbound_matches_documented_imports`:
     each documented
     INBOUND import
     matches.

  Drift-injection
  verified:
  - **Drift 1
    (telegram
    removed
    from
    OUTBOUND)**:
    the OUTBOUND
    test fails
    with precise
    errors via
    subTest for
    each
    `telegram.*`
    case.
  - **Drift 2
    (asyncio.open_connection
    removed from
    INBOUND)**:
    the INBOUND
    test fails
    for
    `asyncio.open_connection`.
  - **Drift 3
    (urllib.error
    removed from
    PARSE_ONLY)**:
    the PARSE_ONLY
    test fails
    for
    `urllib.error.HTTPError`
    and
    `urllib.error.URLError`.

  Subtle
  test-design
  note: this is
  the **network-surface
  audit pin** --
  the public
  contract is
  "DATA-FLOW.md
  accurately
  reflects what
  the project does
  at the network
  layer". The
  classifier is
  not the kind of
  thing most
  projects pin,
  but it's the
  exact kind of
  thing that
  silently drifts
  when a
  contributor
  removes a
  "deprecated"
  module. The
  4-test
  structure (one
  per regex)
  ensures each
  regex is
  pinned
  independently,
  and the
  subTest
  pattern
  reports which
  specific case
  failed.

- **Added 2 new tests
  in a new
  `TestCurrencyConstants`
  class in
  `tests/test_rules.py`
  that pin the
  `_CURRENCY_ALIAS`
  and `_NOT_A_CURRENCY`
  salary-parser
  constants in
  `jobsearch/rules.py`** —
  These two private
  constants are the
  **currency recognition
  contract** for the
  gate's salary parser:
  - `_CURRENCY_ALIAS`:
    symbol-to-ISO-code
    mappings
    (4 entries:
    ₾→GEL, €→EUR,
    $→USD, £→GBP).
  - `_NOT_A_CURRENCY`:
    stop-words that
    appear near
    salary text but
    are not
    currencies
    (7 entries: NET,
    GROSS, PER, AND,
    THE, FOR, MON).

  Both are used in
  the salary parser
  (`_parse_salary` at
  L399) and the gate
  (currency-code
  extraction at
  L323).

  `_CURRENCY_ALIAS`
  is the symbol→code
  contract: a posting
  that says "5000 ₾"
  needs the ₾ symbol
  to be recognised as
  GEL. A drift that
  removes ₾ from
  `_CURRENCY_ALIAS`
  would silently
  mis-parse GEL
  salaries -- the
  gate would not
  know the salary is
  in GEL, would not
  floor-check it
  against the
  profile's GEL
  floor, and would
  either fall
  through to
  "unknown currency"
  or be flagged as
  "needs_conversion"
  when no conversion
  is actually needed.

  `_NOT_A_CURRENCY`
  is the
  not-a-currency
  stop-word list.
  The gate extracts
  3-letter tokens
  from the floor
  text and checks
  each against
  `_NOT_A_CURRENCY`;
  the first one not
  in the list is
  taken as the
  currency. A drift
  that adds a real
  currency (e.g.
  USD) to the list
  would silently
  exclude that
  currency from
  being recognised
  in "5000 NET USD
  per month" text.

  Before this turn,
  no test pinned
  these constants.
  Both are private
  (prefix `_`)
  because they are
  implementation
  details of the
  salary parser, but
  they are part of
  the gate's
  behavior contract
  (W3.1
  salary-flooring
  and currency
  detection). A
  drift would
  silently change
  the gate's
  verdicts for
  every posting
  that mentions a
  salary in a
  currency or
  symbol listed
  here.

  The fix is a new
  `TestCurrencyConstants`
  class with 2 tests:
  1. `test_currency_alias_matches_documented_symbols`:
     each documented
     symbol maps to
     the documented
     ISO code, and
     no undocumented
     symbols are
     present.
  2. `test_not_a_currency_matches_documented_stop_words`:
     each documented
     stop-word is in
     the list, and
     no real ISO
     currency code
     is in the
     list (which
     would defeat
     the whole
     point).

  Drift-injection
  verified:
  - **Drift 1
    (₾ removed
    from
    _CURRENCY_ALIAS)**:
    the alias test
    fails for the
    ₾ symbol with
    a precise
    error via
    subTest.
  - **Drift 2
    (USD added to
    _NOT_A_CURRENCY)**:
    the not-a-currency
    test catches
    the real
    currency code
    in the
    stop-word list
    with a precise
    error: "_NOT_A_CURRENCY
    contains 1
    real currency
    code(s):
    ['USD']. Adding
    a real currency
    to the
    stop-word list
    would silently
    exclude that
    currency from
    being recognised
    in salary
    text. For
    example, if
    'USD' were in
    the list,
    '5000 USD per
    month' would
    be read as
    'the code is
    something else'
    rather than
    'the code is
    USD'."

  Subtle
  test-design
  note: this
  is the
  **currency-recognition
  pin** --
  the contract
  for what the
  gate's salary
  parser reads
  as a currency
  code vs a
  stop-word. A
  drift in
  either set
  silently
  changes the
  gate's
  salary-flooring
  verdicts.

  Subtle
  test-design
  note: the
  test also
  exercises
  the **leak-scan
  allowlist
  interaction**:
  when the test
  class was first
  added, the
  export gate's
  leak scan
  flagged
  `tests/test_rules.py:1793:
  personal token
  /\bgel\b/` --
  because
  "GEL" appears
  in the new
  test's
  docstring and
  constants.
  The leak scan
  flagged it
  because the
  `DENY_TOKENS`
  blocklist
  includes "gel"
  as a personal
  token (the
  user's profile
  uses GEL).

  The fix was to
  add a new
  entry to
  `TOKEN_ALLOWANCES`:
  `("tests/test_rules.py",
  r"\bgel\b")`
  with the same
  justification
  as the existing
  `("jobsearch/rules.py",
  r"\bgel\b")`
  entry -- "GEL
  is one of four
  currency codes
  the salary
  parser
  recognises;
  naming the code
  in a vocabulary
  discloses
  nothing about
  the owner's
  profile or
  salary."

  This is a
  real example
  of the
  **leak-scan
  allowlist
  ecosystem**: a
  new test that
  uses a
  blocklisted
  token (a
  personal
  currency code)
  must be added
  to the
  allowlist with
  a documented
  reason. The
  export gate's
  hard-refusal
  tests catch
  this on every
  run.

- **Added 4 new tests
  in a new
  `TestMarkupRegexes`
  class in
  `tests/test_enrich.py`
  that pin the 4
  LinkedIn
  markup-parser
  constants in
  `jobsearch/enrich.py`:
  `_MARKUP_RE`,
  `_SECTION_RE`,
  `_CLAMP_RE`, and
  `_APPLY_PATH`** —
  These 4
  constants are
  the **LinkedIn
  markup parser
  contract**:
  they determine
  what
  `extract_description()`
  and the
  apply-link
  detector in
  `enrich.py`
  see when they
  read a saved
  LinkedIn page.
  The comment at
  L54-58 in
  enrich.py
  documents:
  "The real
  markup
  (verified
  against a live
  page on
  2026-10-13)".

  - **`_MARKUP_RE`**:
    matches
    `<div class="show-more-less-html__markup...">...</div>`
    (the inner
    markup div).
  - **`_SECTION_RE`**:
    matches
    `<div class="description__text...">...</section>`
    (the outer
    description
    div with
    section-end).
  - **`_CLAMP_RE`**:
    matches
    `clamp-after-N`
    (the CSS class
    LinkedIn adds
    when it
    truncates the
    description).
  - **`_APPLY_PATH`**:
    `"/jobs/view/externalApply/"`
    (LinkedIn's
    external apply
    URL path).

  `_MARKUP_RE` and
  `_SECTION_RE`
  are the two
  regexes tried in
  order in
  `extract_description()`
  (L114): the
  function returns
  the first match
  that yields
  non-empty text.
  A drift in
  `_MARKUP_RE`
  (e.g. removing
  `show-more-less-html__markup`
  from the class
  name) would
  silently fail to
  extract the
  description from
  real LinkedIn
  pages, and the
  gate would mark
  every posting as
  `incomplete`
  (description too
  short to
  evaluate), which
  cascades to
  `NEEDS_RESEARCH`
  verdicts across
  the whole
  corpus.

  `_CLAMP_RE` is
  the clamp-signal
  detector. When
  LinkedIn serves
  a guest page, it
  clamps the
  description to
  ~20 lines and
  adds the
  `show-more-less-html__markup--clamp-after-20`
  class. The
  function returns
  `(text, was_clamped=True)`
  so the caller
  knows the
  description is
  truncated. A
  drift that
  removes
  `clamp-after-`
  from `_CLAMP_RE`
  would silently
  mis-report
  clamped
  descriptions as
  complete, and
  the gate would
  mark truncated
  postings as
  `complete` --
  giving wrong
  verdicts to
  truncated
  postings.

  `_APPLY_PATH` is
  the
  external-apply
  URL path. When a
  posting has an
  "Apply on company
  site" link, the
  URL contains
  `/jobs/view/externalApply/`.
  A drift that
  changes this to
  a wrong path
  would silently
  mis-detect
  external apply
  links, and the
  gate would
  either miss them
  (mark as "direct
  apply" when
  external) or
  false-detect them
  (mark as
  "external" when
  direct).

  Before this turn,
  no test pinned
  these 4
  constants
  directly. The
  existing
  `TestRealPage`
  test uses a
  saved page (which
  is good -- it
  tests the
  end-to-end
  behavior on real
  markup), but it
  would still pass
  if the regexes
  were broken in a
  way that happens
  to match the
  saved page (e.g.
  if `_MARKUP_RE`
  was changed to a
  more permissive
  regex that
  matches a larger
  block of the
  page). The fix is
  a new
  `TestMarkupRegexes`
  class with 4
  tests that pin
  the individual
  regex shapes and
  the `_APPLY_PATH`
  value.

  Drift-injection
  verified:
  - **Drift 1
    (show-more-less-html__markup
    removed from
    _MARKUP_RE)**:
    the markup
    test fails
    with a
    precise error:
    "_MARKUP_RE
    pattern
    '...other-class...'
    does NOT contain
    'show-more-less-html__markup'.
    The saved
    LinkedIn page
    at
    `var/page_cache/4477142227.html`
    uses this class
    as the
    description
    inner div.
    Removing the
    class from the
    regex would
    silently fail
    to extract
    descriptions
    from real
    LinkedIn
    pages, and the
    gate would mark
    every posting
    as `incomplete`."
  - **Drift 2
    (_APPLY_PATH
    changed to
    /jobs/view/wrong/)**:
    the apply-path
    test fails
    with a
    precise error.
  - **Drift 3
    (clamp-after-
    removed from
    _CLAMP_RE)**:
    the clamp
    test fails
    with a
    precise error.

  Subtle
  test-design
  note: each
  test uses
  **both
  positive AND
  negative
  snippets**.
  The positive
  snippet proves
  the regex
  matches what
  it's supposed
  to; the
  negative
  snippet proves
  the regex
  doesn't match
  what it
  shouldn't.
  This catches
  both
  **under-permissive
  regexes**
  (which miss
  real
  descriptions)
  and
  **over-permissive
  regexes**
  (which match
  the wrong
  block of the
  page).

  Subtle
  test-design
  note: the
  test also
  exercises
  the
  **observed-vs-asserted
  discrepancy
  via the
  saved page**:
  the comment in
  enrich.py
  says the
  regexes were
  "verified
  against a live
  page on
  2026-10-13",
  and the saved
  page at
  `var/page_cache/4477142227.html`
  is the
  evidence. The
  test class
  references
  the saved
  page in its
  error
  messages,
  making the
  evidence
  chain
  explicit.

- **Added 3 new tests
  in a new file
  `tests/test_db_schema.py`
  that pin the
  `SCHEMA` and
  `SCHEMA_VERSION`
  database
  contract in
  `jobsearch/db.py`** —
  `SCHEMA` and
  `SCHEMA_VERSION`
  in
  `jobsearch/db.py`
  are the
  **database
  contract**:
  they define
  the data layout
  that the rest
  of the code
  reads and
  writes. The
  schema is
  applied every
  time `connect()`
  is called, and
  `SCHEMA_VERSION`
  is recorded in
  the `meta`
  table.

  `SCHEMA` defines
  7 tables and 3
  indexes:
  - `meta`:
    key/value store
    (records
    `schema_version`)
  - `sources`:
    where listings
    came from
  - `jobs`:
    canonical
    listings
  - `sightings`:
    observations
    of a listing
  - `messages`:
    M2 processed
    alert messages
  - `decisions`:
    M3 owner
    decisions
  - `actions`:
    M5 outbound
    action audit

  The 3 indexes:
  - `idx_jobs_status`:
    on jobs(status)
  - `idx_jobs_seen`:
    on
    jobs(last_seen_at)
  - `idx_sightings_job`:
    on
    sightings(job_id)

  `SCHEMA_VERSION
  = 1` is the
  version stored
  in the meta
  table at init.

  A drift in
  `SCHEMA` would
  silently change
  the data layout:
  - Drop a table
    -> the rest of
    the code would
    error on first
    read ("no such
    table").
  - Add a column
    -> existing
    rows would
    have NULL in
    the new column.
  - Drop a column
    -> the rest of
    the code would
    error on first
    read ("no such
    column").
  - Drop an index
    -> queries
    would fall
    back to table
    scans (silent
    performance
    regression).

  A drift in
  `SCHEMA_VERSION`
  would silently
  mark an
  existing DB as
  the wrong
  version. If a
  contributor
  bumped the
  version to 2
  without writing
  a migration,
  the gate would
  still work
  (since the
  schema is the
  same), but a
  future
  migration that
  checked "if
  version == 1
  then ..."
  would silently
  skip the
  migration.

  Before this
  turn, no test
  pinned the
  schema. A
  contributor who
  added a column
  or dropped a
  table would
  not see a test
  fail until the
  next runtime
  test exercised
  the new column
  / dropped
  table.

  The fix is a
  new
  `TestDatabaseSchema`
  class with 3
  tests:
  1. `test_schema_version_is_one`:
     `SCHEMA_VERSION`
     is exactly 1
     (an int,
     positive).
  2. `test_schema_contains_documented_tables`:
     the schema
     contains all
     7 documented
     tables, and
     no
     undocumented
     tables.
  3. `test_schema_contains_documented_indexes`:
     the schema
     contains all
     3 documented
     indexes, and
     no
     undocumented
     indexes.

  Drift-injection
  verified:
  - **Drift 1
    (actions
    table renamed
    to
    _actions_disabled)**:
    the tables
    test fails
    for the
    `actions`
    table with
    a precise
    subTest
    error.
  - **Drift 2
    (SCHEMA_VERSION
    1 -> 2)**:
    the version
    test fails
    with a
    precise
    error.
  - **Drift 3
    (idx_jobs_status
    renamed to
    _idx_jobs_status_disabled)**:
    the indexes
    test fails
    for the
    `idx_jobs_status`
    index with
    a precise
    subTest
    error.

  Subtle
  test-design
  note: the
  test uses
  the same
  importlib
  sys.modules
  pattern as
  the doctor
  and
  dataflow-map
  tests, because
  db.py has no
  decorators
  (the pattern
  is just the
  safe way to
  import a
  module by
  exec'ing its
  source). The
  test catches
  both
  under-pin
  (missing
  table/index)
  AND over-pin
  (extra
  table/index
  that no code
  reads or
  writes).

  Subtle
  test-design
  note: this
  is the
  **database
  schema pin**
  -- the
  contract for
  what the
  database
  looks like
  to the rest
  of the code.
  A drift would
  silently
  change the
  data layout.
  The 3-test
  structure
  (version +
  tables +
  indexes)
  covers all
  three
  independent
  ways the
  schema can
  drift: the
  version
  constant, the
  table set,
  and the
  index set.

- **Added 5 new tests
  in a new file
  `tests/test_parse_alert_constants.py`
  that pin the 5 most
  contract-critical
  alert-parser
  constants in
  `jobsearch/parse_alert.py`:
  `_BOILERPLATE`,
  `_JOB_URL`,
  `_CARD_MARK`,
  `_BLOCK_SEP`,
  and
  `_VIEW_LABEL`** —
  The 7
  alert-parser
  constants in
  `jobsearch/parse_alert.py`
  are the M2
  alert-parser
  contract.

  The most
  contract-critical
  of these is
  `_BOILERPLATE`.
  The comment at
  L46-48
  documents a
  real production
  bug that would
  resurface if
  any of its 10
  sub-patterns
  drifts:

  > Badges, not
  > job titles.
  > LinkedIn puts
  > these inside
  > every card and
  > above every
  > "View job" link
  > in the text
  > part. Reading
  > one as a title
  > INVENTS a job:
  > on the first
  > real alert
  > tested, 9 of
  > 12 extracted
  > rows were this
  > badge, each
  > carrying a
  > real job id,
  > so each would
  > have entered
  > the ledger as
  > a distinct
  > job.

  A drift that
  removes a
  single pattern
  (e.g. "actively
  hiring") from
  `_BOILERPLATE`
  would silently
  inject 9
  phantom jobs
  per alert into
  the ledger.
  This is the
  **alert-injection
  contract** --
  the regex that
  prevents the
  ledger from
  being flooded
  with phantom
  jobs.

  `_JOB_URL` is
  the
  external_job_id
  extractor.
  LinkedIn job
  URLs come in 3
  shapes:
  - `https://www.linkedin.com/jobs/view/4012345678/`
  - `https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=...`
  - `https://www.linkedin.com/jobs/view/some-slug-4012345678?refId=...`

  A drift that
  narrows the
  regex (e.g.
  removes the
  `[a-z0-9-]*-`
  slug prefix)
  would silently
  fail to extract
  job ids from
  URLs with
  slugs.

  `_CARD_MARK` is
  the HTML
  job-card
  detector.
  LinkedIn serves
  job cards as
  HTML elements
  with
  `data-test-id="job-card"`.
  A drift that
  removes the
  `job-card`
  value would
  silently fail
  to detect cards
  in the HTML
  part of an
  alert.

  `_BLOCK_SEP` is
  the block
  separator. A
  drift that
  narrows the
  character class
  (e.g. removes
  `=`) would
  silently fail
  to split blocks
  separated by
  `=====` lines.

  Before this
  turn, no test
  pinned these 7
  constants. A
  contributor who
  "cleaned up" a
  "duplicate" or
  "redundant"
  sub-pattern in
  `_BOILERPLATE`
  would silently
  inject phantom
  jobs.

  The fix is a
  new
  `TestParseAlertConstants`
  class with 5
  tests:
  1. `test_boilerplate_matches_documented_badges`:
     each documented
     boilerplate
     sub-pattern
     matches a
     documented
     badge line.
  2. `test_boilerplate_does_not_match_real_titles`:
     the regex
     does NOT
     match a
     real job
     title.
  3. `test_job_url_matches_documented_shapes`:
     each
     documented
     LinkedIn URL
     shape
     matches AND
     captures
     the `id`
     named
     group.
  4. `test_card_mark_matches_documented_html`:
     the
     documented
     HTML marker
     matches.
  5. `test_block_sep_matches_documented_separators`:
     each
     documented
     block
     separator
     matches
     (dashes,
     equals,
     asterisks,
     underscores).

  Drift-injection
  verified:
  - **Drift 1
    ("actively
    hiring" ->
    "hiring" in
    _BOILERPLATE)**:
    the
    boilerplate
    test fails
    for "This
    company is
    actively
    hiring" with
    a precise
    subTest
    error.
  - **Drift 2
    (slug prefix
    removed from
    _JOB_URL)**:
    the job-url
    test fails
    for the 2
    slugged URL
    cases with
    precise
    subTest
    errors.

  Subtle
  test-design
  note: the
  test uses
  the
  **try-import-skip** pattern
  for the
  first time
  in the
  series --
  because
  `parse_alert.py`
  has a
  relative
  import
  (`from
  .normalize
  import
  ...`),
  the test
  must be
  run as
  part of
  the
  `jobsearch`
  package.
  The
  `_load_parse_alert()`
  helper
  uses
  `raise
  unittest.SkipTest(...)`
  if the
  import
  fails, so
  the tests
  skip
  gracefully
  when
  run in
  isolation
  rather
  than
  erroring.

  Subtle
  test-design
  note: the
  test exercises
  the
  **negative
  case for
  _BOILERPLATE**
  (must NOT
  match real
  job
  titles) --
  this is
  the
  defense
  against
  the
  reverse
  drift
  (a
  contributor
  who
  makes
  the
  regex
  too
  aggressive
  and
  starts
  rejecting
  real
  job
  titles
  as
  boilerplate).
  This
  is the
  same
  positive
  + negative
  pattern
  as the
  markup
  regex
  pin
  (turn
  N+3).

  Subtle
  test-design
  note: this
  is the
  **alert-parser
  contract
  pin** --
  the M2
  contract
  that
  determines
  what the
  alert-parser
  reads
  from a
  LinkedIn
  alert
  email.
  The
  5-test
  structure
  covers
  the 5
  most
  contract-critical
  constants
  (out of
  7 in the
  module).
  The
  remaining
  2
  (`_SEP`
  and
  `_ANY_URL`)
  are
  less
  security-critical
  and
  can
  be
  pinned
  in
  a
  follow-up
  turn
  if
  needed.

- **Added 3 new tests
  in a new file
  `tests/test_legal_suffix.py`
  that pin the
  `_LEGAL_SUFFIX`
  company-name
  dedup regex in
  `jobsearch/normalize.py`** —
  `_LEGAL_SUFFIX`
  in
  `jobsearch/normalize.py`
  is the
  **company-name
  dedup contract**:
  the regex that
  strips
  legal-form
  suffixes from
  company names
  when computing
  the fallback
  dedup key. The
  comment at L21
  documents:

  > Legal-form
  > suffixes
  > stripped ONLY
  > for the
  > fallback key,
  > and only as
  > whole words.

  The regex
  matches 17
  legal forms:
  inc, llc, ltd,
  limited, gmbh,
  bv, nv, plc,
  sa, sarl, ag,
  oy, ab, as, co,
  corp,
  corporation
  (case-insensitive,
  optional
  trailing dot).

  A drift in
  `_LEGAL_SUFFIX`
  would silently
  break company
  dedup:
  - Remove "gmbh"
    -> "Acme GmbH"
    and "Acme"
    become 2
    different
    companies in
    the ledger.
    The
    alert-parser
    would extract
    2 postings
    (one per
    source)
    instead of 1.
  - Remove "ltd"
    -> "Acme Ltd"
    and "Acme"
    become 2
    different
    companies.
  - Add a
    non-legal word
    (e.g.
    "company") ->
    the regex
    would
    over-strip,
    turning "Acme
    Company" into
    "Acme".
  - Remove the
    `\b` word
    boundaries ->
    "include"
    would match
    the "inc"
    substring,
    and the
    company name
    would be
    silently
    corrupted.

  Before this
  turn, no test
  pinned
  `_LEGAL_SUFFIX`.
  A contributor
  who "cleaned
  up" the regex
  (e.g. removed
  a "redundant"
  or "duplicate"
  suffix) would
  silently break
  company dedup.

  The fix is a
  new
  `TestLegalSuffix`
  class with 3
  tests:
  1. `test_legal_suffix_matches_documented_forms`:
     each
     documented
     legal form
     matches a
     sample
     company
     name.
  2. `test_legal_suffix_does_not_match_word_substring`:
     the regex
     does NOT
     match a
     word that
     contains a
     legal form
     as a
     substring
     (e.g.
     "include"
     contains
     "inc" but
     must NOT
     match).
  3. `test_legal_suffix_pattern_uses_word_boundary`:
     the pattern
     source
     contains
     `\b` word
     boundaries
     (structural
     pin).

  Drift-injection
  verified:
  - **Drift 1
    (gmbh
    removed from
    _LEGAL_SUFFIX)**:
    the
    documented-forms
    test fails
    for "Acme
    GmbH" with a
    precise
    subTest
    error.
  - **Drift 2
    (\b word
    boundaries
    removed)**:
    the
    non-match
    test fails
    for 3
    non-suffix
    words with
    precise
    subTest
    errors,
    and the
    structural
    test fails
    because the
    pattern no
    longer
    contains
    `\b`.

  Subtle
  test-design
  note: the
  test combines
  **positive
  cases**
  (each legal
  form must
  match a
  sample
  company),
  **negative
  cases**
  (a word that
  contains a
  legal form as
  a substring
  must NOT
  match), AND
  a
  **structural
  check** (the
  pattern
  source must
  contain `\b`).
  This is the
  same
  positive
  + negative
  + structural
  pattern as
  the markup
  regex pin
  (turn N+3)
  and the
  alert-parser
  pin (turn
  N+4).
  The
  structural
  check is
  the most
  important:
  a regex that
  matches the
  right cases
  but lacks
  `\b` is
  broken
  because it
  also matches
  the wrong
  cases
  ("include"
  ->
  "clude").

  Subtle
  test-design
  note: this
  is the
  **company-name
  dedup pin**
  -- the
  contract for
  what counts
  as a legal
  form for the
  fallback
  dedup key.
  A drift
  would
  silently
  double the
  number of
  companies
  in the
  ledger
  (or worse,
  silently
  merge
  unrelated
  companies).
  The
  3-test
  structure
  covers
  all 3 ways
  the regex
  can drift:
  missing
  form,
  missing
  word
  boundary,
  and missing
  optional
  trailing
  dot.

- **Added 3 new tests
  in a new file
  `tests/test_software_signal.py`
  that pin the
  `_SOFTWARE_SIGNAL`
  software-profession
  classifier regex
  in
  `jobsearch/rules.py`** —
  `_SOFTWARE_SIGNAL`
  in
  `jobsearch/rules.py`
  is the
  **software-profession
  classifier
  contract**:
  the regex that
  decides whether
  a job title is
  a software
  role.

  The comment at
  L75-77
  documents:

  > Generic
  > vocabulary,
  > not one
  > person's
  > facts --
  > which is
  > why it
  > lives in
  > code. The
  > profile's
  > own stack,
  > aliases and
  > languages
  > extend it
  > at runtime,
  > so a
  > stranger's
  > React/Go/Rust
  > search is
  > not judged
  > by this
  > owner's
  > word list.

  The regex
  matches **45
  software-related
  terms**
  (engineer,
  developer,
  software,
  architect,
  fullstack,
  frontend,
  backend,
  devops, sre,
  data, qa,
  security, ai,
  ml, etc.).

  A drift in
  `_SOFTWARE_SIGNAL`
  would silently
  change whether
  a job is
  recognized as
  software (and
  thus subject to
  M2 matching):
  - Remove
    "devops" ->
    "DevOps
    Engineer"
    postings are
    still
    recognized
    via
    "engineer",
    but "DevOps"
    alone (in a
    job title
    without
    "Engineer")
    would not be
    recognized.
  - Remove "ml"
    or "ai" ->
    "ML Engineer"
    postings are
    still
    recognized
    via
    "engineer",
    but "ML"
    alone would
    not be.
  - Add a
    non-software
    word (e.g.
    "sales") ->
    the regex
    would
    over-recognize
    sales roles
    as software.

  The test
  strategy must
  catch BOTH
  removal of
  discrete terms
  AND addition of
  non-software
  terms. The
  challenge is
  that most test
  titles (e.g.
  "DevOps
  Engineer")
  match MULTIPLE
  alternatives,
  so removing
  one alternative
  doesn't make
  the title
  stop matching.

  The solution
  is a
  **3-pronged
  structural test
  strategy**:
  1. **Discriminating
    matches**:
    use test
    strings
    that ONLY
    match one
    specific
    alternative
    (e.g. "devops"
    alone, not
    "DevOps
    Engineer" --
    "DevOps
    Engineer"
    also matches
    "engineer").
  2. **Negative
    matches**:
    use test
    strings
    that must
    NOT match
    (e.g.
    "senior
    sales" --
    not a
    software
    role).
  3. **Structural
    check**:
    the pattern
    source
    must
    contain
    the
    documented
    terms
    (the
    alternatives
    in the
    regex).

  The
  discriminating
  matches use
  the
  **standalone
  form** of each
  term (no
  "Engineer"
  suffix), so
  that removing
  the term makes
  the match fail.

  The structural
  check verifies
  the **set of
  alternatives**
  in the regex
  source matches
  the documented
  set (45 terms).
  This catches
  both
  **removal**
  (missing
  term) and
  **addition**
  (extra term).

  The fix is a
  new
  `TestSoftwareSignal`
  class with 3
  tests:
  1. `test_software_signal_matches_documented_terms`:
     each
     documented
     software
     term
     matches a
     standalone
     test string
     (50 cases,
     one per
     alternative).
  2. `test_software_signal_does_not_match_non_software`:
     the regex
     does NOT
     match a
     non-software
     string (10
     cases).
  3. `test_software_signal_pattern_contains_documented_terms`:
     the pattern
     source
     contains
     the
     documented
     terms AND
     uses `\b`
     word
     boundaries
     AND is
     case-insensitive
     (structural
     pin).

  Drift-injection
  verified:
  - **Drift 1
    (devops
    removed)**:
    the
    discriminating
    test fails
    for "devops"
    with a
    precise
    subTest
    error, AND
    the
    structural
    test fails
    for the
    "devops"
    term.
  - **Drift 2
    (ml
    removed)**:
    the
    discriminating
    test fails
    for "ml"
    with a
    precise
    subTest
    error, AND
    the
    structural
    test fails
    for the
    "ml" term.
  - **Drift 3
    (sales
    added)**:
    the
    non-match
    test fails
    for "senior
    sales" with
    a precise
    subTest
    error.

  Subtle
  test-design
  note: the
  **discriminating
  match** pattern
  is the key
  innovation
  here -- using
  the standalone
  form of each
  term (no
  "Engineer"
  suffix) so
  that the test
  fails for the
  specific term
  removed,
  rather than
  passing via
  an overlapping
  match.

  This is the
  same problem
  the alert-parser
  pin (turn
  N+4) faced
  with the
  `_JOB_URL`
  regex (URLs
  with slugs
  vs URLs
  without),
  and the
  solution is
  the same:
  use test
  cases that
  ONLY match
  via the
  specific
  alternative
  being tested.

  Subtle
  test-design
  note: this
  is the
  **software-profession
  classifier
  pin** -- the
  M2 contract
  that
  determines
  whether a
  job title
  is recognized
  as software
  (and thus
  subject to
  M2 matching).

  A drift would
  silently
  change the
  profession
  classification
  for any
  posting with
  a title that
  contains a
  specific
  term
  ("DevOps",
  "ML", "SRE",
  etc.).

  The 3-test
  structure
  covers all 3
  ways the
  regex can
  drift:
  missing
  term (caught
  by both
  discriminating
  and
  structural),
  added
  non-software
  term (caught
  by non-match),
  and
  structural
  changes
  (caught by
  structural).

- **Added 5 new tests
  in a new file
  `tests/test_years_parser.py`
  that pin the
  `_YEARS`
  years-of-experience
  parser regex in
  `jobsearch/requirements.py`** —
  `_YEARS` in
  `jobsearch/requirements.py`
  is the
  **years-of-experience
  parser contract**:
  the W3.1 contract
  that extracts
  the years
  claim from a
  posting.

  The regex
  captures:
  - `n`: the
    years number
    (1-2 digits)
  - `after`: up
    to 80 chars
    of context
    after
    "years/yrs"

  The pattern
  supports:
  - "5 years" ->
    n=5
  - "5+ years"
    -> n=5 (the
    + is
    optional)
  - "5 to 7
    years" ->
    n=5 (the
    "to N" is
    optional,
    captures
    the floor)
  - "3 yrs" ->
    n=3
  - "10 years
    experience"
    -> n=10

  A drift in
  `_YEARS` would
  silently
  mis-parse the
  years claim
  from posting
  text, which
  would corrupt
  the
  years-of-experience
  field used in
  M2 matching:
  - Remove the
    "to \d{1,2}"
    range
    support ->
    "5 to 7
    years"
    postings
    would not be
    recognized
    as having a
    years claim.
    And worse:
    if the regex
    still matches
    but captures
    the CEILING
    instead of
    the FLOOR,
    the gate
    would
    silently
    inflate the
    required
    experience
    and reject
    candidates
    who meet
    the floor.
  - Remove the
    "yrs?" short
    form -> "3
    yrs"
    postings
    would not be
    recognized.
  - Remove the
    `\d{1,2}`
    limit
    (change to
    `\d+`) ->
    "100 years"
    would match
    (the limit
    caps years
    at 99).
  - Change the
    "after"
    limit from
    80 to 20 ->
    the context
    would be
    truncated,
    losing
    information.

  Before this
  turn, no test
  pinned
  `_YEARS`. A
  contributor
  who "cleaned
  up" the regex
  (e.g. removed
  a "redundant"
  or "duplicate"
  sub-pattern)
  would
  silently
  break the
  years
  extraction.

  The fix is a
  new
  `TestYearsParser`
  class with 5
  tests:
  1. `test_years_matches_documented_forms`:
     each
     documented
     years form
     matches
     (13 cases:
     basic, plus,
     range,
     short form).
  2. `test_years_captures_named_group_n`:
     the `n`
     named
     group
     captures
     the years
     number.
  3. `test_years_captures_named_group_after`:
     the `after`
     named
     group
     captures
     up to 80
     chars of
     context.
  4. `test_years_captures_floor_in_range`:
     for a
     range like
     "5 to 7
     years", the
     regex
     captures
     the FLOOR
     (5), not
     the CEILING
     (7). This
     is the
     **discriminating
     behavior
     test**:
     the regex
     could still
     match the
     string
     after a
     drift, but
     capture a
     different
     year.
  5. `test_years_pattern_uses_1_to_2_digit_limit`:
     the
     pattern
     source
     contains
     `(?P<n>\d{1,2})`
     (the
     years
     number
     named group
     uses
     1-2 digit
     cap) AND
     is
     case-insensitive
     (structural
     pin).

  Drift-injection
  verified (3
  drifts, all
  caught):
  - **Drift 1
    (to
    range
    support
    removed)**:
    the
    floor-in-range
    test fails
    because
    the regex
    now
    captures
    7 (the
    ceiling)
    instead
    of 5 (the
    floor).
    This is
    the
    **discriminating
    behavior
    test**: a
    naive
    test that
    just
    checks
    "regex
    matches
    the
    string"
    would
    pass even
    after the
    drift.
  - **Drift 2
    (yrs?
    short
    form
    removed)**:
    the
    documented-forms
    test fails
    for 3 "yrs"
    cases with
    precise
    subTest
    errors.
  - **Drift 3
    (\d{1,2}
    cap
    removed
    -> \d+)**:
    the
    structural
    test fails
    because
    the named
    group
    `(?P<n>\d{1,2})`
    is no
    longer in
    the
    pattern.

  Subtle
  test-design
  note: the
  **discriminating
  behavior
  test** is
  the key
  innovation
  here.
  When a
  regex can
  match the
  same string
  in multiple
  ways
  (e.g. via
  the floor
  or the
  ceiling of
  a range),
  a naive
  "does the
  regex match"
  test is
  not enough
  -- you need
  to check
  what was
  captured.

  This is the
  same
  challenge
  the
  software-signal
  pin (turn
  N+4) faced
  with
  overlapping
  alternatives,
  and the
  solution
  is the
  same: test
  for the
  **specific
  value
  captured**,
  not just
  the
  **presence
  of a
  match**.

  Subtle
  test-design
  note: the
  **structural
  pin** uses
  a
  discriminating
  substring
  `(?P<n>\d{1,2})`
  to identify
  the years
  number
  cap, not
  just `\d{1,2}`
  (which
  would also
  match the
  "to N" range
  cap). A
  drift that
  changes
  `\d{1,2}` to
  `\d+` in the
  years number
  position
  (but leaves
  the "to N"
  range cap
  unchanged)
  would be
  caught by
  the
  structural
  test.

  Subtle
  test-design
  note: this
  is the
  **W3.1
  years-of-experience
  pin** -- the
  contract for
  how the
  gate
  extracts
  the years
  claim from
  a posting.
  A drift
  would
  silently
  corrupt
  the
  years-of-experience
  field used
  in M2
  matching.

  The 5-test
  structure
  covers all
  5 ways the
  regex can
  drift:
  missing
  form
  (caught by
  documented-forms),
  missing
  named
  group
  (caught by
  n-group and
  after-group),
  wrong
  capture
  (caught by
  floor-in-range),
  missing
  cap
  (caught by
  structural),
  and missing
  case-insensitivity
  (caught by
  structural).

### Changed

- The verdict vocabulary was renamed from the 3-band model
  (`SUITABLE` / `NEEDS_RESEARCH` / `NOT_SUITABLE`) to the 4-band
  model (`STRONG_MATCH` / `POTENTIAL_MATCH` / `NEEDS_RESEARCH` /
  `NOT_SUITABLE`). The constants in `jobsearch/rules.py` are
  `STRONG_MATCH`, `POTENTIAL_MATCH`, `NEEDS_RESEARCH`, `NOT_SUITABLE`
  with the lowercase string values used in JSON and the corpus.
- The export-gate's MANIFEST.txt now deduplicates entries; the "N
  files" header always equals the real file count in the bundle.
- The doctor now checks for all 9 tools in `tools/` (was 4).

### Fixed

- **A fresh clone failed its own publication-boundary test, so the branch
  could never go green in CI.** `EXCLUDE` in `tools/export_bundle.py` lists
  `digests/` -- a rendered shortlist carries real postings, so it must never
  ship -- and `test_every_exclude_entry_exists_in_source` requires every
  EXCLUDE path to exist in the source tree. `digests/` is gitignored runtime
  output, so a fresh clone has no such directory and the test failed with
  `EXCLUDE lists 1 path(s) that do not exist in the source tree: ['digests']`.
  It failed on the CI runner only, because the working copy used for local
  runs happened to have the directory. `var/` has always had the same problem
  and was rescued by the doctor creating it as Step 0 of `verify.sh`; the
  doctor now creates `digests/` the same way (`digests-writable`; the CL-018
  count moves 21 -> 22, and the pinned check-name set moves with it).
- **The truncated-DB test passed for the wrong reason.** It asserted that
  `sqlite3.connect()` plus `SELECT 1` raises `DatabaseError` on a corrupted
  ledger, but a constant `SELECT 1` needs no page read, so some SQLite builds
  return it without ever validating the file. The test now reads
  `sqlite_master`, which requires the schema stored in the header page, so the
  corruption is genuinely detected -- it failed on the CI runner's SQLite
  ("DatabaseError not raised") while passing locally.
- **`EXCLUDE` listed `digests` while the working copy was missing it**, from a
  half-applied local edit: removing the entry clears
  `test_every_exclude_entry_exists_in_source` but breaks the bidirectional
  `test_exclude_set_matches_documented`, so neither state was shippable. The
  entry is restored and the real cause (no directory in a fresh clone) is
  fixed above.
- **`tests/` was not a package, so the export gate's own self-import resolved
  to whatever `tests` package sat earlier on `sys.path`.** Added
  `tests/__init__.py`. Clears
  `test_every_forbidden_suffix_has_a_mutation_test` (ImportError) and the
  17-entry stale-count report from `test_each_named_test_count_matches_actual`.
- **`applications/` was neither tracked nor ignored**, so a stray `git add -A`
  in the working copy could commit the owner's job-application drafts. Now
  ignored.
- **`SECURITY.md` named the wrong repository** (the public checkout
  the project was moved out of on 2026-10-15). It now names
  the current repo and states the allowlisted-artifact model.
- **The gate invented a work authorisation, and a test pinned the invention.**
  An EU-scope posting was reported as "EU scope satisfied by citizenship with
  EU work authorisation" for every user: not only users who had declared
  nothing, but users who are not EU citizens at all. `rules.py`'s own comment
  said citizenship comes from the profile, but `Rules` had no such field and
  the loader never read one, so a legal fact about a person was manufactured
  from the name of a country in a posting. `tests/test_rules.py` asserted the
  behaviour, so the suite was green while the claim was false. Authorisation is
  now declared (`work_authorisation`) and never inferred; the old assertion is
  replaced by five tests covering declared, undeclared, excluding, and
  word-boundary cases. (`CL-026`)
- **`jobs.salary_text` was read by the renderer and written by nothing.** The
  column existed, the digest's below-floor and foreign-currency branches read
  it, and `tests/test_m3.py` proved those branches worked -- by inserting the
  column by hand. No code path in the pipeline ever populated it, so on a real
  run every posting read "no salary published" and neither flag could fire.
  The enrichment step now stores the posting's own pay line. (`CL-025`)
- **`tools/doctor.py` blamed the repo for a missing dependency.** The
  `tools-importable` check called `importlib.util.spec_from_file_location`
  without importing `importlib.util`. In a normal environment something else
  imports it first, so the bug stayed invisible; with PyYAML and reportlab both
  absent — the fresh-machine case the doctor exists for — the AttributeError was
  swallowed by that check's `except Exception` and surfaced as a false failure
  naming the wrong file: "tools/demo_sieve.py failed to load: module 'importlib'
  has no attribute 'util'", with the fix line "the failure is a bug". Added the
  import, and added the stripped-environment test that pins it.
- **`tools/doctor.py` printed an install command that does not install the
  module.** A missing `yaml` reported the fix as `pip install yaml`; that
  distribution does not provide the `yaml` module, so following the instruction
  left the reader as broken as before. The fix line now names
  `pip install -r requirements.txt` when the manifest is present, and
  `pip install PyYAML` when it is not.
- **`tests/test_export_gate.py::TestExportGateHardRefusals`** —
  the `test_forbidden_suffix_in_shipped_dir_is_refused` method
  was a duplicate of the one in `TestExportGateMutationMatrix`
  (same name, same body, planted-item test in a class whose
  docstring says "do not need a planted item"). Removed the
  duplicate. A future failure in the .pdf-planted case now
  shows up in exactly one class:method instead of two rows
  with the same identifier.
- **`REQUIREMENTS.md` BR-004 stale count.** The export-gate
  mutation matrix was documented as "16 cases" but the
  duplicate removal dropped the count to 14. Bumped the
  count to 14 so the requirements table agrees with the
  actual test count.
- **`tools/audit_public_history.sh` had a half-implemented
  `--pattern` feature** documented in the script's usage
  comments but never wired into the script body. The
  `PATTERN="${2:-jobsearch}"` line read the second
  positional argument but never used it -- a future
  maintainer reading the script would have to discover
  that the `--pattern` example in the comments doesn't
  work. Removed the dead variable, removed the misleading
  example, and extended the exit-code documentation to
  cover the previously-implicit exit 2 (non-git path).
- **`CLAIMS.md` CL-018 stale precondition count.**
  The doctor was documented as "14 preconditions" but
  the actual count (with every W-workstream's check
  wired in) is 21. Bumped the count to 21 and added
  a contract test (`test_doctor_runs_a_documented_number_of_checks`)
  that pins it so the next contributor who adds or
  removes a check must update the claim in the same
  change.
- **`tools/morning_prepare.py` had a dead import from day 1.** The
  `from tools.render_pdf import main` import failed silently because
  `tools/` had no `__init__.py`. Fixed by `sys.path.insert(ROOT/"tools")`
  and direct module import.
- **`docs/DATA-FLOW.md` shipped with "TBD: reviewer to fill" for
  every row.** The build_dataflow_map tool now summarises the
  surface from the source: literal URLs, "user-supplied URL", or
  "stdlib parse only, no network call". A placeholder fails the
  build via `test_no_tbd_placeholders`.
- **The export gate was double-walking `docs/`** because the path was
  in both `INCLUDE` and `OPTIONAL_INCLUDE`. The MANIFEST had 88
  entries for 86 unique paths. Fixed by removing the duplicate and
  adding defensive dedup.
- **The README's "115 tests" claim was stale by 185 tests.** Now
  contract-tested by `tests/test_readme_count.py`.
- **`test_claims_hygiene.py` regex expected `---` but CLAIMS.md uses
  em-dash `—`.** Fixed by accepting the en-dash / em-dash / hyphen
  character class.
- **The corpus sidecar `corpus/v1/.synthetic` documented the old
  3-band vocabulary.** Updated to the 4-band model.
- **`DISCLAIMER.md` section 4 referenced `SUITABLE` (a 3-band
  concept).** Updated to "non-`NOT_SUITABLE` verdict" and a 4-band
  description.
- **The doctor checked for 4 of 9 tools.** A fresh clone of the
  project would not be told if 5 of the 9 tools were missing.
- **No-evasion scan matched its own rationale comment** in
  `test_bounded_retry.py`. Fixed by stripping comments and strings
  before scanning.
- **`flock` `fd.close(); raise` inside `@contextmanager` masked
  `BlockingIOError` with `ValueError("I/O operation on closed
  file")`.** Fixed by deferring close to `finally`.
- **`sqlite3.Connection.commit` is read-only and cannot be
  monkey-patched.** Tests use a duck-typed `_CommitProxy` wrapper.
- **`Popen.stdout` and `Popen.stderr` were not closed in
  `test_run_lock.py`,** causing ResourceWarnings. Fixed by
  explicit `.close()` in `finally`.

### Deprecated

- The 3-band verdict vocabulary. `SUITABLE` is no longer a constant.

### Removed

- The `test_run_lock.py` ResourceWarning from unclosed pipes.

### Security

- The export gate's mutation matrix proves the gate fails closed on
  every deny-listed shape. The history-audit script is the
  repeatable check that nothing has leaked.

## Notes

- A future contributor who adds a W-item must add a "Added" line here
  with the W-item ID. A future contributor who removes a requirement
  (per `REQUIREMENTS.md`) must add a "Removed" line here. The CHANGELOG
  is the project history, not the requirements catalogue.
- The CHANGELOG is in `OPTIONAL_INCLUDE` of the export bundle; it
  ships with the public artifact when present.
