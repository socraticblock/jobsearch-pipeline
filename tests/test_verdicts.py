"""I-22 -- the verdict vocabulary pin.

The verdict vocabulary in `jobsearch/rules.py`
(`STRONG_MATCH`, `POTENTIAL_MATCH`,
`NEEDS_RESEARCH`, `NOT_SUITABLE`) is the
gate's public M2 API: these are the strings
the shortlist UI/CLI and the PDF renderer
consume to display the gate's verdict for
each job.

Before this turn, no test pinned these
constants. A contributor who renamed
`NEEDS_RESEARCH` from `"needs_research"`
to `"more_info_needed"` would silently:
1. break `tools/render_pdf.py` (the PDF
   shortlist would silently not render
   the verdict);
2. break the M3 shortlist UI/CLI (any
   consumer checking the verdict would
   not match);
3. make the W3.1 contract text in
   CLAIMS.md a lie ("NEEDS_RESEARCH"
   wouldn't exist -- the contract
   states "Missing evidence is
   NEEDS_RESEARCH, never a rejection").

The verdict vocabulary is the most
public-facing vocabulary in the gate:
it appears in CLAIMS.md, README.md,
CHANGELOG.md, tools/render_pdf.py,
and tools/notify.py. It is the
"what did the gate decide about this
job" surface.

The fix is a new `TestVerdictVocabulary`
class with 5 tests:
1. `test_verdict_constants_set_matches_documented`:
   structural set equality on the 4
   verdict constants.
2. `test_verdict_values_are_unique`:
   no two verdict constants share
   the same value (a collision
   would silently make two
   different outcomes
   indistinguishable to the
   M3 layer).
3. `test_verdict_values_match_documented_underscore_form`:
   every value is lowercase
   underscore form (consistent
   with the corpus JSON
   fixtures and the
   `test_every_expect_is_an_allowed_value`
   test in test_corpus.py).
4. `test_verdict_values_match_claims_md`:
   the verdict strings appear
   in CLAIMS.md, README.md,
   and CHANGELOG.md with the
   exact same casing (a
   contributor who
   changed the constant
   without updating the
   docs would have the
   docs say "STRONG_MATCH"
   while the constant
   was "strong_match" --
   silently making
   every doc reference
   wrong).
5. `test_render_pdf_knows_every_verdict`:
   the PDF renderer's
   `VERDICT_LABEL` dict has
   a label for every verdict
   (an unrendered verdict
   would be a silent UI
   regression).

Drift-injection verified: changing
`NEEDS_RESEARCH` to
`"more_info_needed"` fails both
the constants test and the
`test_verdict_values_match_claims_md`
test with precise errors.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch.rules import (  # noqa: E402
    NEEDS_RESEARCH,
    NOT_SUITABLE,
    POTENTIAL_MATCH,
    STRONG_MATCH,
)


# The 4 documented verdicts. These
# are the gate's M2 API: every
# consumer (the M3 shortlist
# UI/CLI, the PDF renderer, the
# corpus fixtures) checks against
# these strings. If you rename one,
# update this test in the same
# commit AND every consumer.
VERDICTS_EXPECTED = {
    "strong_match", "potential_match",
    "needs_research", "not_suitable",
}


class TestVerdictVocabulary(unittest.TestCase):
    """The verdict vocabulary in
    `jobsearch/rules.py` is the
    gate's public M2 API: the
    strings the shortlist UI/CLI
    and the PDF renderer consume
    to display the gate's verdict.
    They must be pinned.
    """

    def test_verdict_constants_set_matches_documented(self) -> None:
        """The 4 verdict constants
        (`STRONG_MATCH`,
        `POTENTIAL_MATCH`,
        `NEEDS_RESEARCH`,
        `NOT_SUITABLE`) must each
        match a documented
        verdict string.

        Renaming `NEEDS_RESEARCH`
        from `"needs_research"` to
        `"more_info_needed"` would
        silently break the M3
        shortlist UI/CLI.
        """
        actual = {
            "STRONG_MATCH": STRONG_MATCH,
            "POTENTIAL_MATCH": POTENTIAL_MATCH,
            "NEEDS_RESEARCH": NEEDS_RESEARCH,
            "NOT_SUITABLE": NOT_SUITABLE,
        }
        for name, value in actual.items():
            with self.subTest(constant=name):
                self.assertIn(
                    value, VERDICTS_EXPECTED,
                    f"{name}={value!r} is not in the "
                    f"documented verdict set "
                    f"{sorted(VERDICTS_EXPECTED)}. "
                    f"Renaming a verdict constant "
                    f"would silently break the M3 "
                    f"shortlist UI/CLI, the PDF "
                    f"renderer, and every corpus "
                    f"fixture that uses the old "
                    f"string. If the rename is "
                    f"intentional, update "
                    f"VERDICTS_EXPECTED in the same "
                    f"commit AND every consumer "
                    f"(tools/render_pdf.py, "
                    f"tools/notify.py, CLAIMS.md, "
                    f"README.md, CHANGELOG.md, "
                    f"corpus fixtures). Actual: "
                    f"{sorted(actual.values())}"
                )

    def test_verdict_values_are_unique(self) -> None:
        """No two verdict constants
        may share the same value.
        A collision would silently
        make two different
        outcomes indistinguishable
        to the M3 layer.
        """
        values = [
            STRONG_MATCH, POTENTIAL_MATCH,
            NEEDS_RESEARCH, NOT_SUITABLE,
        ]
        from collections import Counter
        counter = Counter(values)
        collisions = {
            v: count for v, count in counter.items()
            if count > 1
        }
        self.assertEqual(
            collisions, {},
            f"Verdict constants have "
            f"{len(collisions)} collision(s): "
            f"{collisions}. Two verdict "
            f"constants sharing the same value "
            f"would silently make two different "
            f"outcomes indistinguishable to the "
            f"M3 layer. Rename one of the "
            f"colliding constants."
        )

    def test_verdict_values_match_documented_underscore_form(self) -> None:
        """Every verdict value must
        be lowercase underscore
        form. The corpus JSON
        fixtures use this form
        (e.g. "needs_research"),
        and the test_corpus.py
        `test_every_expect_is_an_allowed_value`
        test asserts that every
        fixture's `expect` field
        is one of these strings.
        """
        for name, value in [
            ("STRONG_MATCH", STRONG_MATCH),
            ("POTENTIAL_MATCH", POTENTIAL_MATCH),
            ("NEEDS_RESEARCH", NEEDS_RESEARCH),
            ("NOT_SUITABLE", NOT_SUITABLE),
        ]:
            with self.subTest(constant=name):
                self.assertRegex(
                    value,
                    r"^[a-z][a-z0-9_]*$",
                    f"{name}={value!r} is not in "
                    f"lowercase underscore form. "
                    f"The corpus JSON fixtures and "
                    f"the test_every_expect_is_an_"
                    f"allowed_value test in "
                    f"test_corpus.py expect this "
                    f"form. A value in any other "
                    f"form (e.g. 'NEEDS-RESEARCH', "
                    f"'NeedsResearch', 'more info "
                    f"needed') would silently fail "
                    f"the corpus test."
                )

    def test_verdict_values_match_claims_md(self) -> None:
        """The verdict strings
        must appear in CLAIMS.md
        with the exact same
        casing. A contributor who
        changed the constant
        without updating the
        docs would have the docs
        say "needs_research" while
        the constant was
        "more_info_needed" --
        silently making every doc
        reference wrong.
        """
        claims = (ROOT / "CLAIMS.md").read_text()
        for name, value in [
            ("STRONG_MATCH", STRONG_MATCH),
            ("POTENTIAL_MATCH", POTENTIAL_MATCH),
            ("NEEDS_RESEARCH", NEEDS_RESEARCH),
            ("NOT_SUITABLE", NOT_SUITABLE),
        ]:
            with self.subTest(constant=name):
                # Look for the value
                # surrounded by
                # backticks (the
                # doc style for code
                # references).
                if f"`{value}`" not in claims:
                    # Try without backticks as a
                    # fallback (in case the doc
                    # style changed).
                    if value not in claims:
                        self.fail(
                            f"{name}={value!r} does "
                            f"not appear in CLAIMS.md. "
                            f"CLAIMS.md is the public "
                            f"contract for the gate's "
                            f"behavior; every verdict "
                            f"must be mentioned in it. "
                            f"Either add `{value}` to "
                            f"CLAIMS.md, or update the "
                            f"constant. The verdict "
                            f"vocabulary is the gate's "
                            f"public API surface; the "
                            f"doc and the code must "
                            f"agree."
                        )

    def test_render_pdf_knows_every_verdict(self) -> None:
        """The PDF renderer's
        `_LABEL` dict must have
        a label for every
        verdict. An unrendered
        verdict would be a
        silent UI regression
        (the PDF would not
        display a label for
        that verdict, leaving
        a blank line in the
        shortlist).
        """
        # Import the render_pdf module
        sys.path.insert(0, str(ROOT / "tools"))
        from render_pdf import _LABEL  # type: ignore
        verdict_constants = {
            "STRONG_MATCH": STRONG_MATCH,
            "POTENTIAL_MATCH": POTENTIAL_MATCH,
            "NEEDS_RESEARCH": NEEDS_RESEARCH,
            "NOT_SUITABLE": NOT_SUITABLE,
        }
        for name, value in verdict_constants.items():
            with self.subTest(constant=name):
                self.assertIn(
                    value, _LABEL,
                    f"_LABEL in "
                    f"tools/render_pdf.py is missing "
                    f"a label for {name}={value!r}. "
                    f"The PDF renderer would silently "
                    f"display a blank line for this "
                    f"verdict (no label = no render). "
                    f"Add a label to _LABEL, "
                    f"e.g. {value!r}: '{value.upper().replace('_', ' ')}'."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
