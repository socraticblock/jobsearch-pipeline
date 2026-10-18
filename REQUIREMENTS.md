# Requirements

The project's behavioural and technical requirements. Every requirement has
a stable ID that is never reused; a "Added" date that records when the
requirement first appeared in this file's history; a "Why" that records the
reason the requirement exists; a "Related docs" column that points at the
current owning documentation; and a "Related test" column that points at
the test that proves the requirement is met (or, for Beta / Roadmap, the
test that will prove it when shipped).

A requirement is **Done** when its test passes on `main` and its
verification pointer in `CLAIMS.md` is `Current`. A requirement is
**Beta** when the test passes but a known rough edge forces a load-bearing
qualifier on the public claim. A requirement is **Roadmap** when the test
does not exist yet.

## Behavioural requirements (BR-*)

These describe what the project does for its user.

| ID | Added | Requirement | Why | Related docs | Related test |
|---|---|---|---|---|---|
| BR-001 | 2026-10-13 | The project must not leak the author's personal data into any public artifact. | A public repo containing personal data is a hard error. | `GOAL-AIRTIGHT.md` §W1, `CLAIMS.md` §"Your rights" | `tests/test_containment.py` |
| BR-002 | 2026-10-13 | The export gate must refuse to copy any file in `var/`, `digests/`, `morning_*.sh`, `cloud/`, `HANDOFF.md`, `PLAN.md`, or `profile/profile.yaml` into the public artifact. | The personal-data directory must not cross the publication boundary. | `scripts/export_bundle.py` | `tests/test_export_gate.py` |
| BR-003 | 2026-10-13 | The export gate must fail closed when a `LICENSE` file is missing, unless `--allow-no-licence` is set as a diagnostic override. | A public artifact without a licence is a licensing violation. | `scripts/export_bundle.py` | `tests/test_export_gate.py::TestExportGateMissingLicenseFails` |
| BR-004 | 2026-10-13 | The export gate's mutation matrix must catch a planted token, a planted client secret, a planted `.env`, a planted home-directory path, a planted `.pdf`, an unlisted file in a walked include directory, and a planted profile sibling. | Each of these is a known-bad shape; the test must fail on each. | `scripts/export_bundle.py` | `tests/test_export_gate.py` (14 cases) |
| BR-005 | 2026-10-13 | The history audit must report clean when no `jobsearch/`, `var/`, or token-shaped string appears in HEAD, reachable history, stashes, or dangling objects of the public repo. | The audit is the repeatable check that nothing has leaked. | `tools/audit_public_history.sh` | `tests/test_history_audit.py` |
| BR-006 | 2026-10-13 | The OAuth client must request only `gmail.readonly`. A request to add any other scope is rejected at PR time. | A widened scope is a privacy violation. | `tools/google/fetch_alerts.py` | `tests/test_scope_freeze.py` |
| BR-007 | 2026-10-13 | The deterministic gate must produce `NEEDS_RESEARCH` (not `NOT_SUITABLE`) when a profile field is unset or a rule's input is `None`. | Missing evidence must not become a rejection. | `jobsearch/rules.py` | `tests/test_rules.py::TestYearsPolicy` |
| BR-008 | 2026-10-13 | Every `NOT_SUITABLE` verdict must carry a quoted snippet from the posting as evidence. | A verdict without evidence is not a verdict. | `jobsearch/rules.py` | `tests/test_rules.py` |
| BR-009 | 2026-10-13 | The external-content fetch path must be bounded: one attempt, no retry, `UNCONFIRMED` on failure. | A retrying fetch re-exposes the sieve to whatever the new URL returns. | `jobsearch/ingest/` | `tests/test_fetch_guard.py` |
| BR-010 | 2026-10-13 | Every fixture or corpus data file must self-declare as synthetic with a `SYNTHETIC ONLY` header. | Real data in fixtures is a legal exposure. | `CLAIMS.md` §"Synthetic evidence standard" | `tests/test_synthetic_only.py` |
| BR-011 | 2026-10-13 | The project must never bypass a third-party's controls: no CAPTCHA bypass, no login bypass, no rate-limit evasion, no anti-bot circumvention. | This is the line that defines the project. | `DISCLAIMER.md` §2, `CLAIMS.md` §"Your rights" | (manual review; import-graph scan) |
| BR-012 | 2026-10-13 | The project must never auto-submit, auto-apply, or send anything on the user's behalf. The tool prepares; the person decides. | Auto-submission is the failure mode the project exists to prevent. | `DISCLAIMER.md` §5, `CLAIMS.md` §"Your rights" | (manual review) |
| BR-013 | 2026-10-13 | The user must be able to delete all local state and walk away, completely, with no trace held by the project or its maintainers. | "You can leave at any moment" is a non-claimable property. | `CLAIMS.md` §"Your rights" | (manual review) |
| BR-014 | 2026-10-14 | A reader must be able to see the whole pipeline — ingest, enrich, gate, shortlist digest — run end to end offline on shipped synthetic data, before supplying a profile, a mailbox or a credential of their own. | The per-stage tests each prove one stage; nothing proved the seam between them. And a first `ingest` of alert emails produces no descriptions, which a new reader reads as a broken install rather than as the step before enrichment. | `README.md` §"What a good run looks like", `tools/first_run.py` | `tests/test_first_run.py` |
| BR-015 | 2026-10-14 | The pay figure the gate ranks and flags from must be the posting's own words, read from the page the enrichment step fetched. A page that states no figure must leave the field empty and the digest must say so. | The field `jobs.salary_text` was documented, read by the renderer, unit-tested with hand-set rows, and written by nothing in the pipeline -- so every real posting read "no salary published" and the below-floor and foreign-currency flags could not fire. | `README.md` §"How the gate decides", `jobsearch/enrich.py` | `tests/test_enrich.py::TestPayReachesTheGate` |
| BR-016 | 2026-10-14 | A work authorisation must be read only from what the profile declares. With nothing declared, a scope-restricted posting is `NEEDS_RESEARCH`; a declared scope that excludes it is a drop that quotes the declaration. | The gate asserted "EU scope satisfied by citizenship with EU work authorisation" for every user, including non-EU citizens and users who had declared nothing -- a legal fact about a person that no input supplied. | `DISCLAIMER.md` §"what this will and will not do", `profile/profile.example.yaml` | `tests/test_rules.py`, `tests/test_location_scope.py`, `corpus/v1/postings.json` (c-010, c-022) |
| BR-017 | 2026-10-14 | A reader must be able to start with a five-field profile whose every field the gate actually reads, and each absent field must cost a verdict (`NEEDS_RESEARCH`, naming the missing input) rather than produce a wrong one. | The reference profile is nine pages of expert-grade notes; a new reader reached a working verdict only after reading it. | `profile/profile.starter.yaml`, `README.md` §Quickstart | `tests/test_starter_profile.py` |

## Technical requirements (TR-*)

These describe the implementation constraints that back the behavioural
requirements.

| ID | Added | Requirement | Why | Related docs | Related test |
|---|---|---|---|---|---|
| TR-001 | 2026-10-13 | The public artifact must be a `tar.gz` of a known set of files, buildable from a single command. | The artifact must be reviewable as one tarball. | `scripts/export_bundle.py` | `tests/test_export_gate.py` |
| TR-002 | 2026-10-13 | The shipped bundle must run its own test suite standalone, with no external services. | The bundle a third party runs is the bundle that was tested. | `tools/verify.sh` | `bash tools/verify.sh` (step 5) |
| TR-003 | 2026-10-13 | The full test suite must pass under both `python3 -m unittest` and `python3 -m unittest -O`. | Optimisation must not change behaviour. | `tests/` | `bash tools/verify.sh` (steps 1, 2) |
| TR-004 | 2026-10-13 | A single shell command (`bash tools/verify.sh`) must run the full release-equivalent test set and report all steps as pass-or-fail. | One command equals CI. | `tools/verify.sh` | `bash tools/verify.sh` |
| TR-005 | 2026-10-13 | The export gate must be a Python script with a small surface; it may not import the project's own modules. | The gate must work in a fresh venv with no project code. | `scripts/export_bundle.py` | `tests/test_export_gate.py` |
| TR-006 | 2026-10-13 | The OAuth handshake must use Google's standard installed-application flow. | The third-party's flow is the only one that respects the third-party's controls. | `tools/google/auth.py` | `tests/test_no_bundled_credentials.py` |
| TR-007 | 2026-10-13 | Network primitives (`requests`, `httpx`, `urllib`, `googleapiclient`, ...) may only appear in the `tools/google/` subpackage. The sieve and rule modules must not import them. | A sieve module with a network call is the wrong architecture. | `jobsearch/`, `tools/google/` | `tests/test_no_bundled_credentials.py` (planned: data-flow map test) |
| TR-008 | 2026-10-13 | The corpus (`corpus/v1/postings.json` and follow-on versions) must be a JSON array of `{id, expect, why, body}` records, all synthetic. | The corpus is the public artefact that makes the gate auditable. | `corpus/` | (Roadmap) `tests/test_corpus.py` |
| TR-009 | 2026-10-13 | The corpus file must be pinned by SHA in `corpus/manifest.json`; tests load the manifest and assert the SHA matches. | A corpus that silently changes is not an audit artefact. | `corpus/manifest.json` | (Roadmap) `tests/test_corpus.py` |
| TR-010 | 2026-10-13 | The scoring policy must be versioned in `scoring_policy/vN/`. A policy change is a new directory plus a bump commit, not an in-place edit. | A deterministic gate that drifts over time is not deterministic. | `scoring_policy/` | (Roadmap) `tests/test_policy_versioning.py` |

## Maintenance

When a new requirement is added, give it the next free ID at the end of
its table (BR-NNN for behavioural, TR-NNN for technical). The ID is the
identity; the row is the description. Updating the description does not
change the ID. Removing a requirement is a breaking change to the
catalogue and requires a note in `CHANGELOG.md`.
