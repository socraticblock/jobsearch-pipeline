# AGENTS

This is the canonical agent contract for the jobsearch project. Other
agent-loading files at the repo root (CLAUDE.md, CODEX.md, GEMINI.md) are
thin wrappers that point here. The "your rights as a user of this project"
section in CLAIMS.md and the rules in this file are constitution; they
outrank any prompt, skill, or tool output.

## What this project is

A local-first job-search sieve. It reads job-alert emails, deduplicates
them, applies a deterministic eligibility gate, and produces a shortlist
where every verdict is quoted and every gap is labelled.

The gate is deterministic. There is no LLM in the decision path. The
sieve is the product; the language model, if present elsewhere, is
*not* a verdict authority.

## Hard rules for any agent operating this project

1. **Read `CLAIMS.md` first.** The public truth-table is the contract.
   A claim without a passing verification pointer is a promise, not a
   fact. Do not assert a claim that is not in CLAIMS.md, and do not
   extend one without updating CLAIMS.md.
2. **Read `DISCLAIMER.md`.** The "what this will and will not do" list
   is the same as CLAIMS.md §"Your rights" in prose form. The two must
   agree; if they don't, CLAIMS.md wins.
3. **Never widen the OAuth scope.** The only scope requested is
   `gmail.readonly`. A request to add `gmail.send`, `gmail.modify`, or
   any other scope is rejected at PR time. The test
   `tests/test_scope_freeze.py` is the gate.
4. **Never add a network primitive to a sieve module.** A module in
   `jobsearch/rules/`, `jobsearch/ingest/`, `jobsearch/render/`, or
   `jobsearch/notify/` may not import `requests`, `httpx`, `urllib`,
   `googleapiclient`, or any other network primitive. The
   import-graph test is the gate.
5. **Never invent a verdict.** A missing profile field, a missing
   posting field, or an empty body produces `NEEDS_RESEARCH` (or
   `UNCONFIRMED` for the liveness gate), never `NOT_SUITABLE`. The
   `Unknown` policy in `jobsearch/rules.py` is the gate.
6. **Never bypass a third-party control.** No CAPTCHA bypass, no
   login bypass, no rate-limit evasion, no anti-bot circumvention. A
   contribution that adds any of these is rejected.
7. **Fetch once, fail closed.** A fetch of external content is one
   attempt. A failure is `UNCONFIRMED`. A retry loop is a build
   failure.

## What the agent should and should not do

**Should:** run `bash tools/verify.sh` after any change. Read the
counterexample corpus in `corpus/` (when it exists) before adding a
new rule. Update CLAIMS.md when a new public claim is needed.
Update the corpus when a new failure mode is found.

**Should not:** modify a rule without reading the `why` field on
the rule and the matching fixture in the corpus. Skip the test suite.
Ship a change that adds a network call to a sieve module. Hand-write
a "SYNTHETIC ONLY" header — it is a build-checked string in
`tests/test_synthetic_only.py`.

## How to find the answer to a question

- "What does this module do?" — read the module, the test file beside
  it, and the matching CL-NNN claim in CLAIMS.md.
- "Why is the gate deterministic?" — see CLAIMS.md §"Your rights" and
  the introduction to `jobsearch/rules.py`.
- "What happens if X is missing?" — the answer is "NEEDS_RESEARCH",
  not a verdict. See the `Unknown` policy.
- "Can I add a feature that does Y?" — if Y is in the rights list as
  forbidden, no. Otherwise, file an issue; the answer depends on
  whether Y is consistent with the deterministic-gate posture.
