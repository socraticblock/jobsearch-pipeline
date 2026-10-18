# Comparison

What this project is, what it is not, and where it sits in the
job-search tooling landscape. Borrowed shape from
`ebarti/JobCtrl/docs/comparison.md` (MIT). The original is a
capability matrix; this is the same shape, applied to the
jobsearch-pipeline, and rewritten in this project's voice.

The matrix is opinionated on purpose. A reader who wants a neutral
list of every job-search tool can find one; this document is for
the reader who wants to know whether this project is the right
choice for them, and if not, where they should look instead.

---

## The pipeline at a glance

A self-hosted Python program that takes a job posting (text) and
returns a verdict in one of four outcomes:

- **`strong_match`** — all required fields are present and pass.
- **`potential_match`** — most required fields pass; one soft
  signal is missing.
- **`needs_research`** — at least one required field is missing or
  cannot be evaluated. The candidate decides.
- **`not_suitable`** — at least one required field is present and
  fails. The candidate skips.

The verdict is deterministic: the same posting and the same
profile produce the same verdict. The pipeline does not learn
from the candidate's history, does not rank, and does not
recommend.

A labelled counterexample corpus (`corpus/v1/postings.json`)
documents the gate's published behaviour. A new rule that produces
a different verdict for a corpus fixture fails the build. The
corpus is the contract.

---

## What this project does

| Capability                                       | Status        | Notes                                                    |
|--------------------------------------------------|---------------|----------------------------------------------------------|
| Classify a posting against a profile             | Shipped       | Deterministic; outcome is one of four vocabulary words.  |
| Reason about missing evidence                    | Shipped       | Missing evidence produces `needs_research`, not a guess.  |
| Document every rule in a central registry        | Shipped       | `jobsearch/rule_why.WHY`: every rule has a one-sentence why. |
| Reject secret-shaped values in the build tree    | Shipped       | `scripts/export_bundle.py` runs a deny-list scan on the BUILT tree. |
| Ship a counterexample corpus with the build      | Shipped       | 15 fixtures, every rule exercised.                       |
| Run the full verification with one command       | Shipped       | `tools/verify.sh` = local CI.                            |
| Run a CI privacy gate on every push and PR       | Shipped       | `.github/workflows/release-privacy.yml`.                 |
| Render the verdict as a daily digest             | Shipped       | Text and PDF.                                            |
| Read postings from Gmail (read-only OAuth)       | Shipped       | Off by default; one command to enable.                   |
| Refuse to publish without a licence              | Shipped       | The export gate refuses; the owner decides.              |
| Document what was borrowed from where            | Shipped       | `ACKNOWLEDGEMENTS.md` is the borrow log.                 |
| State the "no fabrication" policy in plain text  | Shipped       | `UNKNOWN_POLICY.md` is the contract.                     |

---

## What this project does NOT do

| Capability                                       | Status        | Why not                                                  |
|--------------------------------------------------|---------------|----------------------------------------------------------|
| Recommend jobs                                   | Will not      | A recommendation is a guess; the sieve refuses to guess. |
| Rank jobs                                        | Will not      | A ranking is a guess; same reason.                       |
| Apply on the candidate's behalf                  | Will not      | The candidate applies.                                   |
| Browse the public job boards for postings        | Will not      | A scraper is a different project; the user runs one and feeds the result. |
| Pull postings from behind a login wall           | Will not      | Authenticated scraping is a different project.           |
| Decide the candidate's location                  | Will not      | The profile says where the candidate is; the sieve does not move them. |
| Decide the candidate's salary floor              | Will not      | The profile says what the candidate needs.               |
| Replace the candidate's judgement                | Will not      | The verdict is a label, not a recommendation.            |
| Send email                                       | Will not      | The digest is a Telegram message and PDF; email is out of scope. |
| Learn from the candidate's history               | Will not      | The sieve is deterministic.                              |
| Ship a licence without the owner deciding        | Will not      | The owner decides; the export gate refuses to ship without one. |
| Auto-publish on a green CI light                 | Will not      | CI is a verification; the human publishes.               |
| Run in the cloud                                  | Will not      | Local-first by design. The owner runs the pipeline on their machine. |

---

## Where it sits in the ecosystem

This section lists the projects the borrow log names, and what
this project is for vs. what they are for. The list is honest
about overlap and the gap the project fills.

### career-ops (career-ops-hq/career-ops, AGPL-3.0)

- **What it is:** a multi-mode career operations platform with
  pluggable modes (track, plan, search, apply).
- **What this project is:** a single-purpose sieve that takes a
  posting and returns a verdict.
- **When to use career-ops:** when the user wants a full platform
  with a tracker, a planner, and an applier in one repo.
- **When to use this project:** when the user wants a local-first
  sieve they can run on a single posting without adopting a
  platform.

### JobCtrl (ebarti/JobCtrl, MIT)

- **What it is:** a job aggregator with a stable-ID requirement
  catalogue and a capability matrix.
- **What this project is:** a single-purpose sieve.
- **When to use JobCtrl:** when the user wants a job aggregator
  with a discoverable surface area.
- **When to use this project:** when the user wants the sieve
  without the aggregator.

### JobNavigator (vesaias/JobNavigator, MIT)

- **What it is:** a backend scraper with a pluggable-provider
  tree.
- **What this project is:** a single-purpose sieve.
- **When to use JobNavigator:** when the user wants a scraper.
- **When to use this project:** when the user has postings
  already and wants a verdict.

### inbox-job-tracker (michaelxu-dev/inbox-job-tracker)

- **What it is:** a Gmail-ingesting job tracker.
- **What this project is:** a sieve that runs after the
  tracker, not the tracker itself.
- **When to use inbox-job-tracker:** when the user wants
  emails turned into tracked postings.
- **When to use this project:** when the user already has
  tracked postings and wants them classified.

### jobsync (Gsync/jobsync)

- **What it is:** a Docker Compose quick-start for a
  multi-component stack.
- **When to use jobsync:** when the user wants containers
  in their job-search stack.
- **When to use this project:** when the user wants a single
  Python process with stdlib + PyYAML only.

### The gap this project fills

A reader who has tried one or more of the above projects, and
wants a sieve that:

- is local-first (no cloud component, no SaaS),
- does not learn from the candidate's history,
- is deterministic and reproducible,
- ships with a labelled counterexample corpus as the contract,
- refuses to invent a confident answer on missing evidence,

will find this project. A reader who wants anything else should
look at the list above.

---

## What the sieve will not promise

The project will not promise:

- That the verdict is the right call for the candidate. The
  verdict is what the gate could determine; the candidate
  decides.
- That more data improves the verdict. Adding more postings to
  the corpus improves the *documentation*, not the *verdict*;
  the verdict is a function of the rule, not the corpus.
- That the corpus is exhaustive. The corpus covers the rules
  the sieve has. A new rule needs a new fixture, and a missing
  fixture is a build failure on `tests/test_corpus_end_to_end.py`.

The project will promise:

- That the corpus is the published behaviour. A fixture in
  the corpus says "the gate produces this verdict for this
  input"; the test enforces it; a regression is a build
  failure.
- That the build is reproducible. `bash tools/verify.sh`
  runs the full chain in 30 seconds; a green run is the
  local proof of readiness.
- That the public surface contains no personal data. The
  export gate runs a deny-list scan on the BUILT tree, not
  the source tree, and refuses to ship on a hit.

---

## The version this document describes

This document describes the pipeline at the SHA of the most
recent passing `tools/verify.sh` run. A change to the pipeline's
behaviour is documented in the versioned release notes; a
change to the sieve's vocabulary is documented in `CLAIMS.md`.

The sieve's vocabulary is stable. The four outcomes
(`strong_match`, `potential_match`, `needs_research`,
`not_suitable`) are part of the public contract; renaming
one is a breaking change that the corpus and the test suite
will catch.
