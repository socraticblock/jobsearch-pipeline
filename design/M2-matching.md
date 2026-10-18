# M2 — Intelligent Matching (design)

Goal: decide *whether a real vacancy is worth the owner's attention* — and prove
it, with a citation for every verdict. Never silently reject.

## 1. Layered pipeline (deterministic first, probabilistic last)

```
description text
   │
   ├─[1] requirements.py  Extract structured requirements (LLM, cited)
   │        each requirement: {kind, polarity, text, quote, confidence}
   │        kind: experience_years | technology | location | remote | language
   │              | degree | authorization | seniority | other
   │        polarity: must | nice
   │
   ├─[2] rules.py        DETERMINISTIC hard gate
   │        output per requirement: MET | NOT_MET(cited) | UNKNOWN
   │        - NOT_MET only from an explicit `must` + a verified profile fact
   │        - everything else -> UNKNOWN -> MANUAL REVIEW
   │
   ├─[3] match.py        Semantic recall (local nomic-embed-text). Ranks; never rejects.
   │
   └─[4] evaluate.py     LLM writes fit / why / gaps / red flags, each citing a quote
            + a final disposition: shortlist | review | pass, with the reason
```

**Rule that makes the whole thing safe:** a listing is auto-rejected only when a
deterministic rule fails on an explicit employer *must*. Every other negative
outcome is `review`, not `pass`. Uncertainty escalates to a human; it never
resolves itself into a rejection.

## 2. The candidate profile (the actual product)

`profile/candidate.yaml`, every entry carrying a **provenance tier** and a
**source handle**:

- `verified` — provable from the CV or a repo (e.g. a shipped project, a commit,
  a live URL). Handle: file/line or `repo@sha`.
- `transferable` — a real skill applied in a different domain.
- `developing` — currently learning; must never be presented as experience.
- `not_production` — knows the tool, no demonstrated production use.
- `hard_requirements` — what the owner must have (location, remote, salary floor,
  languages, work authorisation).
- `preferences` — soft ranking signals.
- `needs_confirmation` — an explicit list of open questions for the owner.

**Non-negotiable:** no entry without a handle. If it cannot be sourced, it goes in
`needs_confirmation`, never in `verified`. The profile is reviewed and signed off
by the owner *before* any automated judgement runs.

### How the "3 years experience" case is handled explicitly
1. Parse the stated minimum into a number of months.
2. Compare against the profile's **verified** months for that skill/role.
3. If the employer states it as a hard requirement and verified < stated →
   `NOT_MET`, citing the requirement quote.
4. If the employer is vague ("some experience"), or the profile entry is
   `transferable`, → `UNKNOWN` → manual review *with the gap named*.
This directly implements "a stated minimum could be a disqualifier, depending on
how strictly the employer states it".

## 3. Anti-false-negative focus (owner's amendment)

Acceptance measures **both** error directions on a labelled set of ≥30 real
listings judged by the owner:

- **missed suitable opportunities (false rejects)** — the expensive error; target ~0
- **wrong recommendations (false accepts)** — tolerated if clearly explained
- every rejection cites the exact requirement + quote it failed
- incomplete/unretrievable descriptions → `review`, never `pass`

## 4. Output contract

For each listing: `job_id`, `disposition`, `fit`, `why[]`, `gaps[]`,
`red_flags[]`, `missing_info[]`, and for each claim a `quote` from the
description. No claim without a quote. This is what M3 renders.

## 5. Dependencies / cost

Embeddings: local `nomic-embed-text` (already installed, free). Bulk scoring:
local `qwen3-coder:30b`. Final cited evaluation: cheap cloud flash model
(pennies/day). No new paid service.

## 6. Open questions for the owner

Locations/markets, remote policy, salary floor, languages, seniority band, work
authorisation, and which project details may be named publicly.
