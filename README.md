# jobsearch-pipeline

> **A job sieve, not a job robot.** Read job postings, check each against
> your CV and preferences, and get a shortlist that tells you *why* — with
> the exact quoted requirement behind every verdict. Nothing is sent, applied
> to, or submitted. Ever.

## Try it in 60 seconds (no account, no network)

```bash
git clone https://github.com/socraticblock/jobsearch-pipeline.git && cd jobsearch-pipeline
python3 tools/first_run.py
```

You will see the whole pipeline run on shipped synthetic data — no profile,
no mailbox, no Google account, no network call.

## What it will and will not do

**Does:**

- Parse LinkedIn alert emails (multipart HTML *and* plain text) into a ledger
- Deduplicate across emails, so re-running is safe and a job seen twice is one row
- Evaluate each posting against your profile with a documented rule set
- Say *why* — every rejection cites the exact quoted requirement it failed
- Never reject for uncertainty: an incomplete description goes to review
- Rank by fit, never by pay, and flag pay only
- Record your decision per job: approve / reject / research / save

**Does not, by construction:**

- Send anything. There is no mail transport, HTTP client or browser in the
  decision path, and a test allowlists the module's imports so one cannot be
  added quietly.
- Apply to anything. `approve` means *prepare*, never *submit*. Submission is a
  separate gate with recipient validation, idempotency and read-back that does
  not exist here yet.
- Decide for you. Uncertainty routes to manual review; it never self-resolves
  into a rejection.

## Quickstart

Python 3.10+ . One required dependency (PyYAML); `reportlab` is optional
and only needed for PDF digests (`pip install 'jobsearch-pipeline[pdf]'`).

```bash
pip install -r requirements.txt

# The primary install path is a git clone (sample data + tools ship with the
# repo). `pip install jobsearch-pipeline` installs the library/CLI core only;
# first-run/doctor require a clone.
# 0. see the whole pipeline work, offline, on shipped synthetic data:
#    ingest -> enrich -> gate -> digest. No profile of your own, no
#    mailbox, no Google account, no network call.
python3 tools/first_run.py

# 1. check the environment (W5.2: the doctor)
python3 tools/doctor.py

# 2. your profile — five fields is enough (`profile.example.yaml` is the
#    long-form reference: vocabulary, profession signals, outcome wording)
#    Option A: hand-edit the starter:
cp profile/profile.starter.yaml profile/profile.yaml
$EDITOR profile/profile.yaml          # stack, floor, market, work auth, years
#    Option B: generate from a CV (skills are extracted; review the result):
python3 tools/onboard.py --cv resume.txt --out profile/profile.yaml

# 3. widen the sieve beyond LinkedIn alert emails (account-free sources):
python3 -m jobsearch.fetch            # RemoteOK + Remotive + Arbeitnow
#    or: python3 -m jobsearch.cli fetch --source remotive

# 4. see the gate alone, scored against the 22-fixture shipped corpus
#    (W5.3: labelled counterexamples, no credentials needed)
python3 tools/demo_sieve.py --batch

# 5. bring in your own alert emails (.eml files, from a local mailbox)
python3 -m jobsearch.ingest <your-maildir> --db var/jobs.db

# 6. supply the descriptions the alert emails do not carry
python3 -m jobsearch.enrich --limit 5 --spacing 45

# 7. see the shortlist, then decide
python3 -m jobsearch.notify render --db var/jobs.db
python3 -m jobsearch.notify decide 3 research --db var/jobs.db

# 8. run the tests
python3 -m unittest discover -s tests
```

Steps 0 and 1 are the front door: a fresh reader sees the pipeline run and
finds out what is missing before committing to a real profile or a real
inbox. Step 0 builds its own throwaway ledger under `var/first-run/` and
never reads or writes your real one.

## What a good run looks like

`python3 tools/first_run.py` prints this, from the shipped sample (trimmed;
the timestamp is the real one from the run that produced the block):

```
Step 1/4 — ingest the sample alert email
  new jobs   : 4
Step 2/4 — enrich (the step that supplies descriptions)
  #1   state=complete chars=629
  descriptions stored: 3 of 4 pending job(s); 1 with no sample page

Step 3/4 — the shortlist digest (the real output)
Job shortlist — 2026-10-14T13:31:52+00:00
3 of 3 surfaced job(s) shown (limit 10); 0 already decided and not repeated; 1 dropped as not suitable.

#1  Backend Engineer — Northwind Logistics
Location: Riverton, Sampleland · remote policy unknown       Salary: Compensation is 7,500 EUR net per month.
Fit: shortlist (STRONG MATCH)
Why:
  - local market: "based in Riverton"
  - technology held: postgresql
  - technology held: python
  - technology held: django
Red flags: none
Description: complete

#2  Analytics Engineer — Contoso Retail Group
Location: Remote (Germany) · remote       Salary: We offer 2,800 EUR net per month for this position.
Fit: shortlist (STRONG MATCH)
Why:
  - work authorisation declared for this scope (eu): "Remote (Germany)"
Red flags:
  - salary quoted at 2800.0 EUR, below the net floor
```

Four things in that output are the product:

- **The verdict is ranked, and the evidence is quoted.** `local market:
  "based in Riverton"` is the posting's own words, not a restatement.
- **A work authorisation is repeated, never inferred.** The second job is
  satisfiable because the sample profile declares `work_authorisation: ["eu"]`.
  Delete that line and the same job reads "location scope to verify" -- the
  gate does not decide where you may work.
- **Pay is quoted, and a low one is flagged rather than hidden or obeyed.**
  `2,800 EUR, below the net floor` is a flag on a job that is still rendered:
  compensation ranks and flags, it never rejects.
- **The drop is a count, not a disappearance.** `1 dropped as not suitable`
  is a posting that failed a quoted essential (in the sample, a role that
  required PHP at production scale). It is not rendered, and it is not
  hidden.
- **Incompleteness is reported, never guessed.** The fourth posting's page
  could not be read, so it is `NEEDS RESEARCH` with "description incomplete"
  as the reason -- not a rejection, and not a pass on absent evidence.

## Why your first ingest shows no descriptions

An alert email carries a title, a company, a location and a link. It does
not carry the posting text. So `ingest` alone produces exactly what the
shipped alert fixtures produce: real rows, and no description to judge
against -- every job is `NEEDS RESEARCH` with "description incomplete".

That is the designed behaviour, not a broken install. Step 5 above is the
step that fills the gap: `jobsearch.enrich` fetches the posting page once
(one attempt, no retry, `429` stops the run) and stores the description it
actually read. Never a guess: a page that cannot be read stays
`incomplete`, and the gate keeps saying `NEEDS RESEARCH` rather than
passing a job on invented text.

The shipped alert fixtures in `fixtures/` exist to test the *parser*, so
ingesting them is a parser smoke test, not a demo of the shortlist.
`tools/first_run.py` is the demo of the shortlist.

If no profile is found the digest says so explicitly rather than quietly
evaluating everything against an empty rule set. Point it elsewhere with
`JOBSEARCH_PROFILE=/path/to/profile.yaml`.

## How the gate decides

Four outcomes: `strong_match`, `potential_match`, `needs_research`,
`not_suitable`. The rules that produce them are the interesting part of this
project, and each one is covered by a test:

| Rule | Behaviour |
|---|---|
| No failure without evidence | Every rejection cites a quoted requirement. No quote, no failure. |
| "5+ years required", no flexibility | Fails — but a **soft** failure, still surfaced to you |
| "5+ years **or equivalent experience**" | Not a failure |
| "3+ years **preferred**" | Not a failure |
| Incomplete description | Never fails. Becomes `needs_research`. |
| Compensation | **Never fails.** Ranks and flags only. The figure is the posting's own words, read from the page during enrichment; where no page states one the digest says "not published" rather than guessing. Foreign currency is flagged for conversion, never converted at an invented rate. |
| Unfamiliar tool mentioned in passing | Not a failure |
| Essential specialist technology you lack | Hard failure — dropped, not surfaced |
| Seniority word in the title | A note, never a failure |
| Location | Only what your profile declares counts. A work authorisation you did not state is `NEEDS_RESEARCH` ("verify") — never a pass on an assumed citizenship; a scope you *did* declare that excludes the country is a drop, on your own terms. "must RESIDE in X" becomes review, because an employer-of-record or relocation route may exist |

The direction of failure is chosen on purpose: a *missed* requirement makes a job
`needs_research` (safe), whereas an *invented* one would wrongly reject it.

**Three knobs come from your profile:** `compensation.floor` (ranking only, never a
rejection), `stack[].status`, which decides which technologies count as held, and
`location_and_arrangement.authorization.work_authorisation`, which is the only
source for where you may legally work.
Your own stack also *extends* the built-in vocabulary, so a technology the
authors never anticipated still matches.

## Layout

```
jobsearch/            the pipeline
  db.py               SQLite ledger: sources, jobs, sightings, messages, decisions, actions
  normalize.py        dedupe keys, content hashing, remote classification
  parse_alert.py      alert email -> listings (fails safe on unreadable input)
  ingest.py           M1 CLI: .eml files -> ledger, idempotent
  requirements.py     posting -> structured requirements, each with its quote
  rules.py            the deterministic gate
  notify.py           M3: shortlist rendering + job-bound decisions
  enrich.py           M4: posting page -> description (stdlib only, offline-testable)
tests/                592 tests, incl. portability tests for people copying this
fixtures/             6 synthetic alert emails (never real mail)
fixtures/first_run/   1 sample alert + 3 sample posting pages + 1 sample profile,
                      the offline data `tools/first_run.py` reads
profile/              profile.starter.yaml (five fields, the fast path),
                      profile.example.yaml (the long-form reference)
design/               M2 matching and M3 approval design notes
tools/                one-shot entry points (first-run, verify, doctor, demo, render, render-html, morning-prepare, next-fire, build-dataflow-map, export-bundle, audit-history, release-handle, onboard, deliver-digest, enrich-retry)
tools/google/         optional: read-only Gmail reader, OAuth helper, scope verifier
```

The bundle was produced from a private working copy by an export step that is
deliberately **not** included here: it carries the author's own identifiers in
its leak-scan deny-list, so shipping it would publish the very list it exists to
enforce. Everything you need to use and extend the pipeline is above.

## Wiring it to real email (optional, read-only)

`tools/google/` vendors a proven OAuth setup. Two things about it are load-bearing
and documented in `tools/google/README.md`:

- It asks for **one** scope, `gmail.readonly`. The upstream skill it came from
  asks for eight, including the ability to send mail as you and to delete it.
- It pins `HERMES_HOME` so the token lands with the project rather than inside a
  profile directory.

`tools/google/check_scopes.py` verifies what you were actually granted and fails
on any over-grant. *Asking* for read-only and *receiving* read-only are different
claims, and only one of them is a security property.

**A caveat worth knowing before you build on this:** while a Google Cloud project
is in *Testing* status, Google expires refresh tokens after 7 days. A scheduled
job on such an app breaks roughly weekly. Whatever you build on top must treat a
failed refresh as an alarm — never as "no new jobs". `tools/google/fetch_alerts.py`
does exactly that: it exits 3 on a failed refresh, and 0 only after it has
actually read the mailbox.

**"Just publish it to Production" is not the one-click escape it sounds like.**
The *Publish app* button on the Audience page stays **disabled** (the console
says only "you must complete your configuration on the Branding page", naming no
field) until the **App domain** section is filled in: an application home page, a
public privacy policy link, and terms of service, all on a domain you can point
at. Uploading an app logo additionally obliges you to submit for verification.
That is why the pipeline ships a loud weekly-refresh failure instead of assuming
a fix: the honest options are re-consenting when the token dies, or doing the
homepage/privacy-policy work and publishing properly.

## Design commitments

- **Idempotency is structural.** Unique keys mean a re-run, a crash-and-retry or a
  duplicate email add zero rows.
- **Never invent a fact.** A field that could not be read stays `NULL` and the row
  is marked incomplete. Nothing is guessed to fill a gap.
- **Never pair an ambiguous link with borrowed text** — a listing with no
  readable title keeps `NULL` rather than silently mislabelling a job.
- **Standard library only** for ingestion and parsing. The component that will
  sit next to mail credentials has the smallest practical audit surface.
- **No bare `assert` anywhere.** The suite runs identically under `python -O`; a
  test enforces it, because bare asserts are stripped under `-O` and a neutered
  test suite is worse than none.

## Licence

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for the full text.

`pip install jobsearch-pipeline` installs the core CLI. Repository-based tooling
(tools/, scripts/, fixtures/) requires a checkout of the repository.

## Provenance

Extracted from a private working copy. `tools/google/setup.py` is a vendored copy
of the `google-workspace` Hermes skill (MIT, Nous Research) with the scope list
narrowed; the other files here were written for this project. `MANIFEST.txt`
records a sha256 for every shipped file.
