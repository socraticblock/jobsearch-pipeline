"""QA test -- the corpus's rule names agree with the corpus's verdicts.

A fixture's `rule` field is a human-readable name that should
encode the rule's intended behaviour. When the rule name says
'hard_drop' the verdict must be 'not_suitable'; when the rule
name says 'uncertain' the verdict must be 'needs_research'; when
the rule name says 'satisfied' the verdict must be in the
suitable band (strong_match or potential_match).

A drift between the name and the verdict is a documentation
problem and a reader-trap: a future contributor who reads the
rule name will expect one outcome and see another. Either the
rule name, the verdict, or the gate's logic must move.

Run:  python3 -m unittest tests.test_rule_name_verdict_agreement -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "corpus" / "v1" / "postings.json"

# Substring rules for each verdict band.
# A rule name is checked against each band in order; the first
# match wins. Each entry: (band_name, list_of_substrings).
# The band_name is the verdict the band requires:
#   "not_suitable"      => the verdict must be not_suitable
#   "needs_research"    => the verdict must be needs_research
#   "suitable"          => the verdict must be strong_match or potential_match
#
# Substring design notes:
#   - "below_floor" is in the SUITABLE band (not not_suitable) because
#     the gate surfaces below-floor salary as a soft signal the
#     candidate decides on. The substring does not by itself mean
#     "hard drop".
#   - "does_not_drop" and "no_drop" are in the SUITABLE band because
#     they describe a rule that REFUSES to drop, i.e. surfaces.
#   - "uncertain" stays in the NEEDS_RESEARCH band because that is
#     its meaning in the rule_why registry.
BAND_RULES: list[tuple[str, tuple[str, ...]]] = [
    # HARD-NO bands first
    ("not_suitable", ("hard_drop", "strict_drop", "hard_avoid",
                      "block", "no_signal", "no_software",
                      "missing_required", "no_bundled")),
    ("needs_research", ("uncertain", "missing_evidence", "unknown")),
    # SOFT bands (the gate surfaces these)
    ("suitable", ("satisfied", "soft_signal", "learnable",
                  "potential", "match", "below_floor",
                  "does_not_drop", "no_drop", "agency")),
]

# The full set of acceptable verdict strings.
SUITABLE_VERDICTS = ("strong_match", "potential_match")
ALL_VERDICTS = ("not_suitable", "needs_research", "strong_match", "potential_match")


def _classify_rule_name(rule: str) -> str | None:
    """Return the band a rule name implies, or None if the
    name is ambiguous (no recognized substring)."""
    for band, substrings in BAND_RULES:
        if any(s in rule for s in substrings):
            return band
    return None


class TestRuleNameVerdictAgreement(unittest.TestCase):
    """The rule name and the verdict must agree."""

    def test_every_rule_name_is_classifiable(self) -> None:
        """Every rule name must contain a recognized substring
        so a reader knows what to expect. An unclassifiable name
        is a documentation drift."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for rec in records:
            rule = rec.get("rule", "")
            band = _classify_rule_name(rule)
            if band is None:
                offenders.append(
                    f"  {rec['id']} rule={rule!r}: the name does not "
                    f"contain any of the recognized substrings "
                    f"({' '.join(s for _, subs in BAND_RULES for s in subs)}). "
                    f"Rename the rule to describe the gate behaviour."
                )
        if offenders:
            self.fail(
                "These rule names are ambiguous -- a reader cannot "
                "tell what verdict to expect from the name. Rename "
                "the rule to include a recognized substring:\n"
                + "\n".join(offenders)
            )

    def test_every_rule_name_matches_its_verdict(self) -> None:
        """Every rule's verdict must be in the band its name
        implies."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        mismatches: list[str] = []
        for rec in records:
            rule = rec.get("rule", "")
            expect = rec.get("expect", "")
            band = _classify_rule_name(rule)
            if band is None:
                continue  # already flagged by the previous test
            if band == "not_suitable" and expect != "not_suitable":
                mismatches.append(
                    f"  {rec['id']} rule={rule!r} expect={expect!r}  "
                    f"-- rule name says 'drop' but verdict is {expect!r}; "
                    f"either rename the rule or change the verdict"
                )
            elif band == "needs_research" and expect != "needs_research":
                mismatches.append(
                    f"  {rec['id']} rule={rule!r} expect={expect!r}  "
                    f"-- rule name says 'uncertain' but verdict is "
                    f"{expect!r}; either rename the rule or change "
                    f"the verdict"
                )
            elif band == "suitable" and expect not in SUITABLE_VERDICTS:
                mismatches.append(
                    f"  {rec['id']} rule={rule!r} expect={expect!r}  "
                    f"-- rule name says 'satisfied' but verdict is "
                    f"{expect!r}; either rename the rule or change "
                    f"the verdict"
                )
        if mismatches:
            self.fail(
                "The corpus's rule names and verdicts disagree. A "
                "reader who reads the rule name will expect one "
                "outcome and see another. Fix the rule name, the "
                "verdict, or the gate's logic so the three agree.\n"
                + "\n".join(mismatches)
            )

    def test_every_verdict_is_in_the_vocabulary(self) -> None:
        """A verdict that is not one of the four documented
        outcomes is a typo."""
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        for rec in records:
            expect = rec.get("expect", "")
            self.assertIn(
                expect, ALL_VERDICTS,
                f"{rec['id']}: expect={expect!r} is not in the "
                f"four-outcome vocabulary {ALL_VERDICTS}. Use the "
                f"exact snake_case spelling that the gate returns."
            )

    def test_every_aspirational_rule_fixture_is_documented_in_rule_why(self) -> None:
        """A corpus fixture whose `why` field says the rule is
        aspirational (the gate has no branch for it yet) is a
        documented future-work marker: the fixture is
        informational, not a contract on gate behaviour. The
        WHY registry must acknowledge the gap so a reader who
        finds the fixture can trace it back to a future-work
        note.

        A fixture that calls the rule aspirational but whose
        WHY entry is silent on the gap is a silent
        documentation drift: a reviewer reading the corpus
        sees a fixture that looks like every other one, but
        the gate does not have a rule for it. The fix is
        either (a) implement the rule, or (b) document the
        deferral in the WHY registry. The test enforces
        (b) so the gap is never silent.

        The signal we look for in the `why` field:
          - "aspirational" -- the gate has no branch
          - "the gate has no ... check today" -- explicit gap
          - "TODO marker" -- deferral tag
          - "is informational" -- explicit non-contract
        The signal we look for in the related WHY entry:
          - "aspirational" or "TODO" or "gap" or
            "not implemented" or "not documented"
        """
        import re
        from jobsearch import rule_why
        records = json.loads(CORPUS.read_text(encoding="utf-8"))
        offenders: list[str] = []
        # Words that mean "deferral" in fixture `why` text.
        deferral_signals = re.compile(
            r"(aspirational|TODO\s+marker|is\s+informational|"
            r"the\s+gate\s+has\s+no\s+\w+|no\s+check\s+today|"
            r"documented\s+future.work|no\s+branch\s+today)",
            re.I,
        )
        for rec in records:
            rule = rec.get("rule", "")
            fixture_why = rec.get("why", "")
            if not deferral_signals.search(fixture_why):
                # The fixture does not claim a deferral;
                # the test only enforces the contract for
                # fixtures that DO claim a deferral.
                continue
            # The fixture claims a deferral. Find the
            # related WHY entry and assert the deferral
            # is documented there too.
            related = [
                (key, value) for key, value in rule_why.WHY.items()
                if key == rule or key in fixture_why
            ]
            if not related:
                offenders.append(
                    f"  {rec['id']} rule={rule!r}: the fixture's "
                    f"`why` claims a deferral, but no rule_why "
                    f"entry matches the rule name or appears "
                    f"in the `why` text. A reviewer cannot "
                    f"trace the deferral back to a WHY entry."
                )
                continue
            for key, value in related:
                if re.search(
                    r"aspirational|TODO|gap|"
                    r"not\s+implemented|not\s+documented",
                    value, re.I,
                ):
                    break
            else:
                offenders.append(
                    f"  {rec['id']} rule={rule!r}: the fixture's "
                    f"`why` claims a deferral, but the related "
                    f"rule_why entries ({[k for k, _ in related]!r}) "
                    f"do not mention the deferral. A reviewer "
                    f"reading the WHY registry will not learn "
                    f"the rule is unimplemented."
                )
        if offenders:
            self.fail(
                "Some aspirational-rule fixtures are not "
                "documented as deferrals in the WHY registry. "
                "Either implement the rule (and remove the "
                "aspirational note from the fixture's `why`), "
                "or document the gap in the related rule_why "
                "entry's value.\n"
                + "\n".join(offenders)
            )


if __name__ == "__main__":
    unittest.main()
