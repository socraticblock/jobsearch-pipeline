# GOAL — an airtight, open-sourceable job-search system

Written 2026-10-13. Every requirement below carries a **test** — the command that proves it,
and the result that counts as proof. A requirement without a passing test is not done, no
matter how good the code looks.

## What "airtight" means here (three properties, no more)

1. **It cannot leak the author's personal data** — candidate profile, pay floor, employment
   history, location, citizenship, tokens, mailbox-derived data — into any public artifact.
2. **A stranger can run it safely** — on a clean machine, with their own credentials, without
   their data going anywhere they did not choose.
3. **It fails safe and tells the truth** — no silent failure, no invented suitability, no
   verdict without quoted evidence, no claim the system cannot back.

Airtight does **not** mean "guaranteed free of false positives". That is not achievable and
will never be claimed. It means the boundaries are enforced by construction and the
uncertainty is reported instead of hidden.

## Baseline measured 2026-10-13 (the starting line)

- 127 unittest cases green in normal mode **and** under `-O`.
- Containment audit run today and **clean**: no `jobsearch/` path in the public HEAD tree, none
  ever added in reachable history, zero commits touching it, stash clean, all 5 dangling objects
  clean. Nothing has leaked; the exposure is strictly forward-looking.
- Single guard today: `jobsearch/.gitignore` containing `*` inside a checkout of the
  public repository. A tripwire, not a wall.
- Missing: LICENSE, CONTRIBUTING.md, SECURITY.md, CI, requirements/pyproject.
- `gmail.readonly` is a restricted scope: public third-party use requires annual CASA assessment.
  Current Google project is in Testing mode, so refresh tokens die every 7 days.

---

## W1 — Containment: the publication boundary

**W1.1 Move the project out of the public checkout.**
The working copy moves to a private repo path (`~/jobsearch`). The public workspace keeps no
directory that can hold personal data.
*Test:* `git -C ~/hermes-workspace ls-files | grep -c jobsearch` → `0`; and
`ls ~/hermes-workspace/jobsearch` → "No such file or directory".

**W1.2 Publish by allowlist into a fresh-history repo.**
The public repo is built by copying named files into an empty directory and committing once.
History is never inherited.
*Test:* in the public repo, `git log --oneline | wc -l` → `1`, and
`git log --all --name-only | grep -c -E "profile/profile\.yaml|var/|token|secret"` → `0`.

**W1.3 Export gate, fail-closed, tested by mutation.**
`tools/export_gate.sh` builds the artifact into a temp dir, then refuses to proceed unless every
manifest entry exists, no unlisted file is present, and a scanner finds zero hits for: token /
client-secret shapes, the personal profile, `var/` content, absolute home paths, and any
`.db`/`.pdf`/`.log` file.
*Test (mutation matrix on throwaway copies, run through the gate):* plant each forbidden item in
turn — a fake `token.json`, a real-shaped `client_secret.json`, a `profile.yaml`, a `.db`, an
absolute path string, an unlisted file — and assert the gate **exits non-zero and names the
offending path** in every case. Also assert the clean tree exits `0`. (`tests/test_export_gate.py`)

**W1.4 History audit as a repeatable script.**
`tools/audit_public_history.sh` asserts no project path exists in HEAD, in `--all` history, in
stashes, or in dangling objects.
*Test:* the script exits `0` today (verified clean), and exits non-zero when run against a
fixture clone where the path was committed once. (`tests/test_history_audit.py`)

**W1.5 Leak runbook (removed).** The internal leak runbook has been
replaced by the public Security Policy in SECURITY.md, which uses
GitHub private security advisories for reporting.

---

## W2 — Credentials and data flow

**W2.1 No bundled OAuth client, ever.**
The package contains no client ID or secret; the user supplies their own path.
*Test:* `tests/test_no_bundled_credentials.py` greps the shipped tree for `client_id`,
`client_secret`, and Google secret JSON shapes → 0 hits; and config loading **fails loudly** when
no user client path is configured.

**W2.2 Scope freeze enforced by test.**
*Test:* assert the requested scope set equals exactly `["https://www.googleapis.com/auth/gmail.readonly"]`.
Any widening — ever — fails the build. This is the "do not widen this list" rule as executable code.

**W2.3 Documented credential model.**
Per-user Google Cloud project; desktop-app OAuth with loopback; token file mode `600`; the
Testing-mode 7-day refresh expiry stated up front in the quickstart, not buried.
*Test:* after a token write, assert `stat -c %a google_token.json` → `600`; assert the quickstart
contains the expiry caveat (a doc test that greps for it, so it cannot be quietly dropped).

**W2.4 Data-flow map, and off-by-default for every third party.**
A single table in `docs/DATA-FLOW.md` listing exactly what leaves the machine: Telegram (digest
text + PDF), Cloudflare (raw postings, only if enabled), job boards (fetch requests), never the
profile or the rules.
*Test:* with a profile that configures no Telegram token and no cloud endpoint, assert the
delivery path is inert and no outbound request is made (an HTTP stub asserts zero calls);
and assert the map lists every module that performs network I/O (built from the import graph,
so a new sender fails the test until it is documented).

**W2.5 Deletion and revocation actually work.**
One command deletes local derived data; one revokes the token.
*Test:* run against a throwaway DB copy — assert the target tables are empty and personal fields
absent; run revoke — assert the token file is gone and a subsequent fetch fails with a clear
"not authorised" message rather than a silent skip.

---

## W3 — The gate must be honest, on labelled data

**W3.1 "Years I can honestly claim" becomes a required profile field.**
The years rule compares against it. While it is unset, the outcome for such a posting is
**UNKNOWN**, never a rejection — deciding against missing evidence is exactly what this project
refuses to do.
*Test:* profile without the field → a posting requiring "5+ years, no flexibility" evaluates to
UNKNOWN and lands in the digest's "not judged" section. (This **changes** the test written today,
which currently asserts a drop — the drop is only valid once the field exists.)

**W3.2 No verdict without quoted evidence.**
*Test:* for every posting in the fixture corpus, assert each failure carries a quote from the
posting text, and any unjudged posting is labelled `not_judged` with the missing input named.

**W3.3 Coverage is printed, not implied.**
The digest states how many postings had a description, how many could not be judged, and why.
*Test:* render a mixed fixture; assert the coverage line and its counts match the DB.

**W3.4 Vocabulary becomes profile data, with a documented default.**
The profession-signal list moves to the profile (English list kept as the default), so a
non-English user can extend it without editing code.
*Test:* titles in a second language (German and Portuguese fixtures) are neither blanket-dropped
nor blanket-kept; assert each verdict matches the labelled expectation.

**W3.5 A labelled counterexample corpus — the real quality bar.**
A fixed set of postings with expected outcomes: obvious matches, hard avoids, ambiguous titles
("Consultant", "Analyst", "Product Owner"), non-English titles, missing descriptions, hostile
experience wording.
*Test:* `tests/test_gate_corpus.py` scores the gate against the labels and **fails on any
mismatch**, printing a per-case diff. Unknown cases must be labelled unknown, not guessed — the
score is the evidence, and a green suite with a wrong label is a broken test, not a pass.

---

## W4 — Failure modes and observability

**W4.1 A run report per run.** Fetched, failed, skipped, coverage, and the reason for each.
*Test:* inject 429, 404, expired token, and a no-description posting; assert each is named in the
report with its reason, and that a run with failures is never reported as clean.

**W4.2 Heartbeat: a broken 08:00 job must shout.** Non-zero exit plus a failure notice; no
partial digest presented as complete.
*Test:* break the renderer deliberately → assert non-zero exit and a failure notice; assert the
job still holds its state (no deletes on failure — see the data-safety rule).

**W4.3 Bounded retries, no evasion.** Backoff on 429, hard stop after N attempts, never
proxy-rotate, never spoof a user agent, never solve a challenge.
*Test:* against a stub server returning 429 → assert exactly N attempts with increasing delay,
a recorded reason, and zero evasion code paths (the tree is grepped for proxy/captcha/UA-spoof
markers).

**W4.4 Idempotency and overlap.** Re-runs never duplicate rows or messages; two concurrent runs
cannot corrupt the ledger.
*Test:* run twice concurrently against a copy → assert identical row counts, one delivery, and a
recorded lock/skip for the second run.

**W4.5 Timezone and DST.** 08:00 stays 08:00 across a DST boundary.
*Test:* with a frozen clock at both sides of the boundary, assert the computed next-fire time.

**W4.6 Storage failure.** Full disk, corrupt DB, WAL recovery.
*Test:* simulate a full disk and a truncated DB on copies → assert a clear error, no corruption,
and that the last good ledger is still readable.

**W4.7 Fetched text is untrusted input.** Posting text can contain injection attempts, hostile
markup or dangerous links.
*Test:* a fixture posting carrying an instruction-shaped string and a `javascript:` link → assert
the renderer escapes it, the link is dropped, only `http(s)` survives, and no fetched text can
change a gate verdict.

---

## W5 — A stranger can run it

**W5.1 Reproducible install.** `requirements.txt` or `pyproject.toml` with pinned versions and a
stated Python floor.
*Test:* fresh venv install succeeds; the import graph closes (no undeclared import).

**W5.2 `doctor`.** One command naming every unmet precondition and its fix: Python version, deps,
profile validity, token file presence and mode, output dir writability, timezone, cron reachable.
*Test:* run in a stripped environment → assert every failing check is named with a fix, and exit
non-zero; run in a good environment → exit `0`.

**W5.3 Credential-free demo.** Fixtures produce a real digest — text and PDF — with no Google
account, no token, no network.
*Test:* `HOME=$(mktemp -d)` demo run → exit `0`, digest file exists, N jobs listed, zero outbound
requests.

**W5.4 Quickstart from clone to first digest**, including the Google Cloud steps and the
Testing-mode caveat, plus the "no Gmail yet" path.
*Test:* every command in the quickstart is executed verbatim by a smoke script; a command that
no longer works fails the build.

**W5.5 Lawful and honest repo furniture.** LICENSE (owner's choice), CONTRIBUTING.md carrying
the project's evidence standard, SECURITY.md with a private reporting route, CHANGELOG.md.
*Test:* files exist; the licence identifier is machine-readable and matches the manifest.

---

## W6 — Legal and terms boundary

**W6.1 Page fetching is off by default**, documented as the user's own responsibility, with 429
respected and never evaded.
*Test:* assert fetching is disabled unless enabled in the profile, and that a 429 stops the run
rather than being retried around.

**W6.2 No republication of real posting content.** Fixtures are synthetic.
*Test:* a guard asserts no URL or company string from the live ledger appears in any publishable
file, and that fixture descriptions carry a synthetic marker.

**W6.3 A claims list stating what it will not do**: no auto-apply, no captcha bypass, no terms
evasion, no suitability guarantee, no invented salary or experience.
*Test:* each claim appears in README and is matched by a test that enforces the behaviour
(the never-send test already exists for the first one).

---

## W7 — Release discipline

**W7.1 One local command that equals CI.** `tools/verify.sh` runs: suite in both modes, import
graph, privacy guard, history audit, export gate, deny-list scan, scope freeze, gate corpus.
*Test:* CI (free on public repos) runs exactly this script; a locally green run and a CI run
produce the same result on the same SHA.

**W7.2 Versioned release with a hash handle.** Tag, changelog entry, and the artifact
`sha256` recorded in the consolidation ledger alongside the tag.
*Test:* `tools/verify.sh --release` prints the artifact hash; the ledger entry matches it
byte-for-byte on rebuild.

**W7.3 Owner gates stay owner gates.** Licence choice, first public push, and any cloud deploy
remain explicit owner decisions, recorded with date and reason.
*Test:* the release script refuses to publish without an explicit flag, and refuses without a
licence file present.

---

## Definition of done

**Gate A — "safe to push publicly"** (containment first, because it is the only live risk):
W1.1–W1.5, W2.1, W2.2, W5.5, W6.2, W7.1, W7.3.

**Gate B — "safe for a stranger to run"**:
W2.3–W2.5, W3.1–W3.5, W4.1–W4.7, W5.1–W5.4, W6.1, W6.3, W7.2.

**Never claimed, at any gate:** that the filter has no false negatives; that fetched page text is
accurate; that a user's own fetching complies with a third party's terms; that any digest is a
recommendation.

## Owner decisions still open

- The number of years you can honestly claim, which unlocks W3.1.
- Whether the cloud Worker ships at all, or stays undeployed.
- Whether Telegram stays the delivery path — it is a third-party data path for Gmail-derived
  content, which is a compliance question only you can settle.
