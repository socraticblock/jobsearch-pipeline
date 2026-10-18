# Acknowledgements

This project borrows ideas, schemas, and patterns from a small set of
publicly-available projects in the job-search tooling space. It does
**not** copy their code, fixtures, or text verbatim, and it is not a
fork of any of them. The borrowed items are: **methodology patterns**,
**document shapes**, and **a small set of named design conventions**
that turned out to work better than what was here before.

Every paragraph below names the project, the licence it ships under,
and the specific idea this project took from it. Where a project is
under a copyleft licence, this project does **not** distribute any
of its source code, so the copyleft terms do not apply to the
artifacts in this repository.

The borrowing was deliberate and not exhaustive. The point was to
build the second instance of a pattern that already worked once, not
to assemble a kitchen-sink of every feature in the ecosystem.

---

## career-ops (career-ops-hq/career-ops)

Licence: AGPL-3.0 (the AGPL landmine is real; this project does not
copy or fork career-ops' code; the document shapes below were
re-derived, not copied).

- **The "user-first" 9-point rights list** that careers advice often
  hides in legal copy. This project paraphrases the structure
  (visibility, inference, error, ...), not the text, in `CLAIMS.md`.
- **The `MANIFESTO.md` tone** -- declarative sentences about what the
  project will and will not do, owned by the project, not the user.
  This project's `CLAIMS.md` and `DISCLAIMER.md` follow the same shape.
- **The pluggable-mode pattern** where one repository holds many
  country- or board-specific adapters. This project's pipeline is
  country-agnostic on purpose; the idea is reserved as a future
  pattern, not implemented.
- **The `modes/_shared.md` "rules of engagement" list** -- a single
  file that documents what a downstream agent or human may not do.
  This project's `AGENTS.md` is the small-scale version; the
  full-scale version is the future `design/MODES.md` placeholder.
- **The `DATA_CONTRACT.md` shape** -- a single document that lists
  every field that crosses a boundary. This project's
  `docs/DATA-FLOW.md` is the same idea, generated from the import
  graph, not hand-maintained.
- **The `tests/test-all.mjs` discipline** -- a single test runner
  that covers everything, not a per-domain split. This project's
  `tests/test_export_gate.py` is the local mirror; CI is the
  remote mirror.

## JobCtrl (ebarti/JobCtrl)

Licence: AGPL-3.0 (same landmine; no source is copied).

- **The `BR-NNN` / `TR-NNN` stable-ID requirement catalogue** in
  `docs/requirements.md`. This project re-derives the shape in
  `REQUIREMENTS.md` and the test `tests/test_synthetic_only.py` is
  a thin cousin of JobCtrl's gate that asserts the catalogue cannot
  silently lose rows.
- **The `docs/comparison.md` capability matrix** -- a table that
  says "what this project is, and what it is not". This project
  has the same shape in `CLAIMS.md`'s `Current / Beta / Roadmap`
  taxonomy; the standalone `docs/comparison.md` is the future
  expansion.
- **The `docs/architecture/scoring.md` shape** -- a single file
  that names every scoring rule and what it catches. This project's
  `jobsearch/rule_why.py` is the same idea, code-first, with the
  prose version living in the test docstrings and the corpus
  fixture `why` fields.
- **The `docs/claims-ledger.md` CL-NNN shape** -- a single table
  mapping public claims to verification evidence. This project
  re-derives the shape in `CLAIMS.md`; the test
  `tests/test_why_spec.py` is the contract that the ledger cannot
  lose rows.

## JobNavigator (vesaias/JobNavigator)

Licence: MIT (no copyleft landmine, but the project still does not
copy any text or code).

- **The `LEGAL_DISCLAIMER.md` shape** -- a single document that
  names what the project will not do, in plain language, at the
  top of the repository. This project's `DISCLAIMER.md` is the
  same shape, rewritten in this project's voice.
- **The `backend/scraper/{_shared,ats,sources,orchestrator}.py`
  pluggable-provider tree** -- a directory that holds the
  implementation, the per-provider adapter, and the per-provider
  source list as three separate files. This project's pipeline
  is single-file per concern on purpose; the pluggable tree is
  reserved for the future, not built.

## Jobstead (adibas03/jobstead)

Licence: see upstream (the project is small and early; the
licence was checked at first study and the lessons in `Jobstead.md`
do not appear to be the kind of expression that would attract
copyright protection regardless).

- **The append-only lessons log with `[PROMOTED]` / `[REFUTED]` /
  `[DEPRECATED]` status suffixes.** This project keeps the same
  idea in `design/STATUS.md` (not yet shipped; the project has
  not had time to accumulate lessons worth suffixing).
- **The `scripts/check-drift.sh` pattern** -- a single shell script
  that asserts a stated invariant. This project's
  `tools/audit_public_history.sh` is the same shape, scoped to
  the W1.4 history audit.

## inbox-job-tracker (michaelxu-dev/inbox-job-tracker)

Licence: see upstream (checked at first study; the fixtures
schema is the borrowed item, not the content).

- **The `tests/fixtures/emails.json` labelled-counterexample
  schema** -- a JSON array of `{id, expect, why, body}` records
  where `why` names the failure mode the fixture is for. This
  project's `corpus/v1/postings.json` is the same shape, applied
  to posting classification, with a different `rule` field
  pointing into `jobsearch/rule_why.WHY` for the prose form.
- **The "every fixture has a `why`" discipline.** This project's
  `tests/test_corpus.py` makes the discipline a build failure:
  a fixture without a `why` field does not ship.

## sift-roles (jakemercure28/sift-roles)

Licence: see upstream (small project, single star, not a
production reference).

- **The `curl | sh` install story.** This project does not adopt
  the install pattern; the documentation of why not is the
  borrowed item. The `make install` item (I-15) is the future
  expansion and is intentionally deferred.
- **The "sift" name** was *not* taken -- it was avoided on
  principle. The reasoning is in `README.md`'s name section;
  the project name is `jobsearch-pipeline` and will stay
  that way until a viral name is owner-approved.

## jobsync (Gsync/jobsync)

Licence: see upstream.

- **The Docker Compose quick-start.** This project's onboarding
  has the same shape in `README.md`'s quickstart section, but
  in plain Python instead of a Compose file -- the project ships
  stdlib + PyYAML, so a Compose file would be a layer this
  project does not need.

## jobseek (colophon-group/jobseek)

Licence: dual MIT + CC BY-NC 4.0 (the data licence is the
interesting part; the MIT code licence is uncontentious).

- **The split-licence pattern** -- code under a permissive
  licence, derived data under a more restrictive one. This
  project is single-licence at the moment; the split pattern is
  the future expansion if a corpus is published.
- **The "data is not the project"** distinction. This project's
  `DISCLAIMER.md` and `CLAIMS.md` both say the same thing in
  different words: the sieve is the project, the corpus is the
  evidence.

---

## Borrowed ideas that did not survive

A small number of ideas were considered and dropped. They are
listed here so a reader does not have to wonder whether the
absence is a gap or a deliberate choice.

- **career-ops' "Implementations welcome" stance** -- this project
  does not adopt the stance because the corpus and the rule
  registry are tight; opening the implementation to community
  forks would invite credential-shaped commits the gate is
  designed to refuse.
- **JobCtrl's `app.py` / `cli.py` / `web.py` three-mode split.**
  This project ships one mode (a single Python entry point) and
  does not adopt the three-mode split. The reason is the
  publication boundary: three modes means three surfaces a
  contributor has to remember to test, and the historical leak
  rate is higher when the surface is wider.
- **The career-ops `agent-inbox` mode.** This project is local-
  first on purpose; an agent-inbox would require a public
  surface the project refuses to build.

---

## What was not borrowed

This project does not borrow:

- Verbatim text from any project's `MANIFESTO.md`,
  `LEGAL_DISCLAIMER.md`, `SECURITY.md`, `AGENTS.md`, or
  `DATA_CONTRACT.md`. Where the **shape** of a document is
  borrowed, the **words** are this project's own.
- Any fixture, posting, recruiter name, or company name. Every
  record in `corpus/v1/postings.json` is synthetic by
  construction; the `corpus/v1/.synthetic` sidecar is the
  marker.
- Any project's brand, name, or logo. The `sift` name was
  avoided on principle; `jobsearch-pipeline` is the working
  name and will not change without an owner decision.
- Any code, **with one explicit exception**: `tools/google/setup.py` is a
  vendored copy of the Nous Research `google-workspace` Hermes skill (MIT,
  Copyright (c) 2025 Nous Research), with the scope list narrowed and adapted
  for standalone use. See `THIRD_PARTY_NOTICES.md` for full attribution.
