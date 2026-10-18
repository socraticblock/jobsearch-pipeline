# The Unknown Policy

This project refuses to invent a confident answer when the evidence
does not support one. The policy is short on purpose: a long policy
becomes a paragraph a future reader skips.

## The rule

> **When the gate cannot find a satisfying answer from the data it
> has, the verdict is `needs_research`, not a fabricated `strong_match`
> or `not_suitable`.**

A `needs_research` verdict is not a soft answer. It is a verdict.
The next step is the human's, not the sieve's. The sieve's job is
to surface the missing signal, not to fill it in.

## The four verdicts

| Verdict          | When                                              | Action for the human     |
|------------------|---------------------------------------------------|--------------------------|
| `strong_match`       | All required fields are present and at least 2 required technologies are held.   | Apply.                   |
| `potential_match`    | All required fields are present and at least 1 required technology is held, but the technology count does not reach the strong-match threshold. | Read the posting, decide. |
| `needs_research` | At least one required field is missing or unclear.| Read the posting, decide.|
| `not_suitable`   | A required field is present and fails.            | Skip.                    |

The verdicts are not a probability, not a recommendation, and not
a prediction of interview success. They are the gate's honest
report of what it could determine.

## What "missing evidence" looks like

The sieve has a small set of inputs: the posting's `title` and
`body`, the candidate's profile (`known_stack`, `learnable_stack`,
`years_can_honestly_claim`, `floor_net`, `floor_currency`,
`local_ok`, `language_ok`), and a small set of constants
(`NON_EU_BLOCK`, `HARD_AVOID_BY_TITLE`, `MIN_DESCRIPTION_CHARS`).

If any of the inputs is `None` and a rule depends on it, the rule
must produce `needs_research`, not a guess. The two most common
shapes are:

1. **`years_can_honestly_claim is None` and the posting demands a
   number of years.** The candidate has not yet decided what they
   can honestly claim. The sieve refuses to invent a number for
   them. The verdict is `needs_research`, the rule code is the
   `years_bar_missing_evidence` branch, and the corpus fixture
   `corpus/v1/postings.json#c-001` exercises the rule.

2. **`known_stack` does not list a required technology, and the
   posting has no "or equivalent" clause.** The candidate has not
   said they know the technology. The sieve refuses to invent a
   stack from the description. The verdict is
   `not_suitable` with the missing technology quoted, and the
   rule is `stack_missing_required` in
   `corpus/v1/postings.json#c-011`.

The two cases are deliberately different. A missing `years` is an
honest unknown; a missing `known_stack` is a present negative.
The sieve does not collapse the two into a single "uncertain" bucket
because the human's next step is different in each.

## What the sieve will not do

- It will not say "5+ years" means "you should apply if you have
  3 years." The candidate decides the equivalency, not the sieve.
- It will not say "EUR 30k" means "you should accept." The candidate
  has a floor; the sieve reports whether the posting is below it.
- It will not rank postings. A `strong_match` verdict means
  "nothing disqualifying," not "best fit."
- It will not learn from the candidate's history. The sieve is
  deterministic; the next verdict is the same as the last
  verdict for the same inputs.

## The minimum-evidence rule

A `strong_match` verdict requires:

1. The posting's `title` is non-empty and parses against the
   `HARD_AVOID_BY_TITLE` list.
2. The posting's `body` has at least `MIN_DESCRIPTION_CHARS` (32)
   characters.
3. The candidate's `years_can_honestly_claim` is set (not `None`).
4. The candidate's `known_stack` covers every required technology
   in the body that is named as a hard requirement.
5. The candidate's `local_ok` includes the posting's location, or
   the posting is `remote`.
6. The posting's stated salary, if present, is at or above
   `floor_net` in `floor_currency`.

A posting that fails any of these is `needs_research` (if the
input is missing) or `not_suitable` (if the input is present and
fails). The minimum-evidence rule is a restatement of the rest of
this document; the corpus fixtures in `corpus/v1/postings.json`
are the named examples.

## Why this is opinionated

A sieve that always says `strong_match` is a sieve the candidate
ignores. A sieve that always says `not_suitable` is a sieve the
candidate mutes. The middle path -- `strong_match` only when the
evidence strongly supports it, `potential_match` when it
partially supports it, `not_suitable` only when the evidence
contradicts it, and `needs_research` everywhere else -- is the
path the candidate learns to trust.

The corpus is the contract. A new rule that produces a
`strong_match` verdict in a fixture the corpus calls `needs_research`
is a build failure. A new rule that produces a `not_suitable` in
a fixture the corpus calls `strong_match` is also a build failure.
The corpus is not a wish list; it is the gate's published
behaviour.
