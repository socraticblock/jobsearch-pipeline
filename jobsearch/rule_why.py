"""Why-field-as-spec for every rule category.

Borrowed pattern (career-ops' `_shared.md` rules table + Jobstead's
append-only status suffixes + inbox-job-tracker's `why` field on each
counterexample): every verdict category carries a one-sentence
statement of the failure it catches. The same string is used in four
places:

  1. As a docstring on the rule in the test suite
  2. As the `why` field on a corpus fixture that exercises the rule
  3. As the explanation surfaced with the verdict in the digest
  4. As the human-readable reason in the CLAIMS.md verification

A rule change that loses its `why` is wrong; a test that exercises a
rule without asserting the `why` is incomplete; a corpus fixture
without a `why` field is refused by the corpus-shape test.

This module is the central registry. It must be kept in sync with
`jobsearch/rules.py`. The test `tests/test_why_spec.py` asserts that
every rule branch in `evaluate()` reaches this module.
"""

from __future__ import annotations

# Each entry: short category id -> (one-line why, where it is exercised).
#
# The `why` string is the sentence that a stranger reads to understand
# the rule. It is the same string in the test docstring, in the corpus
# fixture's `why` field, in the verdict surface, and in CLAIMS.md.

WHY: dict[str, str] = {
    # W3.1 — years bar with missing evidence
    "years_bar_missing_evidence": (
        "rejecting a posting for a 3+ year experience demand when the  (W3.1)"
        "profile has no years_can_honestly_claim would manufacture a "
        "confident fit narrative for an honest unknown; the project is "
        "built to refuse this failure mode (W3.1)"
    ),
    # W3.1 — years bar with set evidence
    "years_bar_strict_drop": (
        "when the candidate has committed to an honest number and the  (W3.1)"
        "posting demands strictly more with no flexibility, the gate "
        "has both sides of the comparison and a hard drop is the "
        "correct verdict"
    ),
    # W3.1 — years bar with flexible wording
    "years_bar_flexible_uncertain": (
        "a 3+ year demand with explicit flexibility wording is  (W3.1)"
        "uncertain, not a hard drop -- the candidate's equivalent "
        "experience might count, and a 2-year candidate may legitimately "
        "apply"
    ),
    # W3.1 — title-based hard avoid
    "hard_avoid_by_title": (
        "a title that names a hard-avoid role (e.g. devops-only) is a  (W3.1)"
        "hard drop, irrespective of description content; the title IS "
        "the specialist thing and re-reading the description will not "
        "change the role"
    ),
    # W3.1 — title with no software signal
    "no_software_signal_in_title": (
        "a title with no software signal (e.g. pure sales) is a hard  (W3.1)"
        "drop -- the gate is for software roles and a non-software title "
        "means the posting is not for this sieve"
    ),
    # W3.1 — empty title
    "empty_title_unknown": (
        "a posting with no title is missing evidence; the gate must  (W3.1)"
        "not invent a verdict by inferring a role from the description"
    ),
    # W3.1 — language unstated
    "language_unknown_not_dropped": (
        "a posting in a language the candidate does not list is  (W3.1)"
        "uncertain, not a hard drop -- the candidate may still read the "
        "description in translation, and the gate's job is to surface "
        "the signal not the conclusion"
    ),
    # W3.1 — description too short
    "description_too_short_uncertain": (
        "a posting with a very short description does not have enough  (W3.1)"
        "signal to evaluate; the gate must not pretend to know and "
        "must route to NEEDS_RESEARCH, not a verdict"
    ),
    # W3.1 — local market satisfied
    "local_market_satisfied": (
        "a posting in a city the candidate's profile lists as local_ok  (W3.1)"
        "is a satisfied location signal, not an issue to surface"
    ),
    # W3.1 — language known satisfied
    "language_known_satisfied": (
        "a required language the candidate's profile lists as  (W3.1)"
        "languages_usable is a satisfied signal, not an issue to "
        "surface; the language requirement is one the candidate "
        "already meets"
    ),
    # W3.1 — strong match (all required fields pass and at least
    # 2 must-have technologies are in the candidate's known_stack).
    # The strong_match verdict is the only verdict that is purely
    # positive: every required dimension is met, and the gate is
    # confident the candidate is a strong fit. The rule documents
    # what the gate's `strong_match` branch is asserting.
    "strong_match_perfect_fit": (
        "a posting whose every required dimension is met and whose  (W3.1)"
        "at-least-two must-have technologies are in the candidate's "
        "known_stack is a strong match; the gate is confident the "
        "candidate is a good fit and the verdict is the highest "
        "available"
    ),
    # W3.1 — non-EU block hard drop
    "non_eu_block_hard_drop": (
        "a posting restricted to a country in NON_EU_BLOCK is a hard  (W3.1)"
        "drop when the profile declares a work authorisation that "
        "excludes it -- the candidate cannot work from there on their "
        "own stated terms and no EOR/relocation route would change it"
    ),
    # W3.1 / CL-026 — EU scope with no declared work authorisation
    "location_authorisation_missing_evidence": (
        "an EU-scope posting is not evidence of an EU work  (W3.1)"
        "authorisation: with nothing declared in the profile the gate "
        "reports NEEDS_RESEARCH instead of crediting a permission the "
        "candidate never stated, and never rejects them over it"
    ),
    # W3.1 — required stack missing
    "stack_missing_required": (
        "a required technology the candidate does not list as known or  (W3.1)"
        "learnable is a hard drop with the missing tech quoted as "
        "evidence"
    ),
    # W3.1 — required stack partial (learnable, gate surfaces as
    # potential_match because the technology IS in the candidate's
    # learnable list and the gate's surface logic is the union of
    # satisfied + uncertain, weighted by strict requirement)
    "stack_partial_learnable": (
        "a required technology the candidate lists as learnable is a  (W3.1)"
        "soft positive signal, not a hard drop -- the candidate has "
        "a real chance of picking it up; surface it as a reason to "
        "apply, not as a reason to skip"
    ),
    # W3.1 — salary below floor (gate surfaces as potential_match
    # because the candidate might accept below-floor for a perfect
    # fit; the gate is not a recommendation)
    "salary_below_floor_soft_signal": (
        "a posting whose stated salary is below the candidate's floor  (W3.1)"
        "is a soft signal the candidate must evaluate themselves; "
        "the gate is not a recommendation, so a below-floor posting "
        "is surfaced with the salary quoted, not silently dropped"
    ),
    # W3.1 — salary unspecified
    "salary_unspecified_does_not_drop": (
        "a posting with no salary stated is not a drop; the gate must  (W3.1)"
        "not invent a comparison, and a missing figure is not the same "
        "as a low one"
    ),
    # W3.1 — agency intermediary (gate does not have a separate
    # agency branch today; the rule_why entry documents the
    # intended behaviour. The corpus fixture c-015 documents
    # the deferral in its `why` field, see
    # test_rule_name_verdict_agreement.py::test_every_aspirational_rule_fixture_is_documented_in_rule_why.
    # Until a gate branch exists, the verdict on an
    # agency-routed posting comes from other rules -- years,
    # stack, location -- not from this one.)
    "agency_intermediary_soft_signal": (
        "a posting routed through a recruitment agency is a soft  (W3.1)"
        "positive signal: the actual employer is unnamed but the "
        "role is real, and the gate surfaces it with the agency "
        "noted so the candidate knows to ask who the employer is. "
        "NOTE: gate has no agency check today; the rule is "
        "aspirational, see test_why_spec.py. (BR-equivalent of "
        "career-ops' agency confirmation gate.)"
    ),
    # W2.1 — bundled credentials
    "no_bundled_credentials": (
        "shipping a client_id or client_secret in the public artifact  (W2.1)"
        "would let a third party use the project's OAuth client as a "
        "phishing tool; the build refuses to ship it"
    ),
    # W2.2 — scope freeze
    "scope_freeze": (
        "widening the OAuth scope to gmail.send or gmail.modify turns  (W2.2)"
        "a read-only tool into a write-capable one and breaks the "
        "consent model the user signed into"
    ),
    # W1.3 — export gate fail-closed
    "export_gate_fail_closed": (
        "a public artifact with personal data, a missing LICENSE, or  (W1.3)"
        "an unlisted file in the source tree is the kind of leak that "
        "cannot be undone; the gate must refuse to ship it"
    ),
    # W1.4 — history audit
    "history_audit_repeatable": (
        "the only way to prove a leak did not happen is to run the  (W1.4)"
        "same check again and get the same answer; the audit must be "
        "a script, not a one-time check"
    ),
    # W4.1 — bounded fetch
    "bounded_fetch": (
        "a retrying loop re-exposes the sieve to whatever the new URL  (W4.1)"
        "returns; a bounded one-attempt fetch with UNCONFIRMED on "
        "failure is the only safe default"
    ),
    # W4.7 — fetched text treated as untrusted input
    "fetched_text_untrusted": (
        "the body of a Gmail message, a posting page, or a Telegram  (W4.7)"
        "response is data, not instructions; no rule may treat its "
        "phrasing as an instruction to the gate"
    ),
    # W3.5 — counterexample corpus
    "counterexample_corpus": (
        "a deterministic gate that cannot name the failure modes it  (W3.5)"
        "catches is not auditable; every category of failure needs a "
        "labelled fixture so a contributor can see what the rule is "
        "for"
    ),
    # W7.1 — one-shot verify
    "one_shot_verify": (
        "a contributor who has to remember to run five commands in  (W7.1)"
        "order will not run them; one command that runs the full "
        "release-equivalent test set is the only path that scales"
    ),
    # W6.1 — no third-party bypass
    "no_third_party_bypass": (
        "bypassing CAPTCHA, login, rate limits, or bot controls on a  (W6.1)"
        "third-party service is the line the project refuses to cross; "
        "a contribution that adds any of these is rejected at PR time"
    ),
    # W6.2 — verdict is not a recommendation
    "verdict_not_recommendation": (
        "a SUITABLE verdict means the gate found nothing disqualifying;  (W6.2)"
        "it is not advice to apply, not a probability of interview, and "
        "not a prediction of hire; the system recommends nothing"
    ),
    # W6.3 — no false-negative guarantee
    "no_false_negative_guarantee": (
        "the system will misclassify some postings; the goal is  (W6.3)"
        "auditable uncertainty, not perfect recall; this is stated "
        "in DISCLAIMER.md and CLAIMS.md"
    ),
}


def get_why(category: str) -> str:
    """Return the `why` for a category. Raises if the category is unknown.

    A test asserts that every category used in the rule module exists
    here. A category that is missing is a build failure: the rule is
    not auditable until its `why` is registered.
    """
    if category not in WHY:
        raise KeyError(
            f"No 'why' registered for category {category!r}. "
            f"Add it to jobsearch.rule_why.WHY so the rule is auditable."
        )
    return WHY[category]
