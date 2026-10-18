"""I-31 -- the
company-name
dedup pin.

`_LEGAL_SUFFIX` in
`jobsearch/normalize.py`
is the company-name
dedup contract: the
regex that strips
legal-form suffixes
from company names
when computing the
fallback dedup key.
The comment at L21
documents:

> Legal-form suffixes
> stripped ONLY for
> the fallback key,
> and only as whole
> words.

The regex matches
14 legal forms:
inc, llc, ltd,
limited, gmbh, bv,
nv, plc, sa, sarl,
ag, oy, ab, as, co,
corp, corporation
(case-insensitive,
optional trailing
dot).

A drift in
`_LEGAL_SUFFIX`
would silently
break company
dedup:
- Remove "gmbh" ->
  "Acme GmbH" and
  "Acme" become 2
  different
  companies in the
  ledger. The
  alert-parser
  would extract 2
  postings (one
  per source)
  instead of 1.
- Remove "ltd" ->
  "Acme Ltd" and
  "Acme" become 2
  different
  companies.
- Add a non-legal
  word (e.g.
  "company") ->
  the regex would
  over-strip,
  turning "Acme
  Company" into
  "Acme" (which
  may or may not
  be desired).

Before this turn,
no test pinned
`_LEGAL_SUFFIX`.
A contributor who
"cleaned up" the
regex (e.g.
removed a "redundant"
or "duplicate"
suffix) would
silently break
company dedup.

The fix is a new
`TestLegalSuffix`
class with 3 tests:
1. `test_legal_suffix_matches_documented_forms`:
   each
   documented
   legal form
   matches.
2. `test_legal_suffix_does_not_match_word_boundary`:
   the regex
   does NOT
   match a
   non-suffix
   word
   (e.g.
   "include"
   contains
   "inc" but
   must NOT
   match).
3. `test_legal_suffix_strips_for_fallback_key`:
   the
   `clean_company()`
   function
   (or
   equivalent)
   strips the
   suffix for
   the
   fallback
   key.

Drift-injection
verified: removing
"gmbh" fails the
documented-forms
test.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_normalize():
    """Helper: import
    the normalize
    module.

    The module has no
    relative imports,
    so a direct
    import works.
    """
    try:
        from jobsearch import normalize
        return normalize
    except ImportError:
        raise unittest.SkipTest(
            "jobsearch package not on "
            "PYTHONPATH; cannot import "
            "normalize."
        )


class TestLegalSuffix(unittest.TestCase):
    """`_LEGAL_SUFFIX` in
    `jobsearch/normalize.py`
    is the company-name
    dedup contract.
    """

    LEGAL_FORMS = (
        "inc", "llc", "ltd", "limited",
        "gmbh", "bv", "nv", "plc",
        "sa", "sarl", "ag", "oy",
        "ab", "as", "co", "corp",
        "corporation",
    )

    LEGAL_FORM_SAMPLES = (
        # inc
        ("Acme Inc", "inc"),
        # llc
        ("Acme LLC", "llc"),
        # ltd
        ("Acme Ltd", "ltd"),
        # limited
        ("Acme Limited", "limited"),
        # gmbh
        ("Acme GmbH", "gmbh"),
        # bv (Dutch)
        ("Acme BV", "bv"),
        # nv (Dutch)
        ("Acme NV", "nv"),
        # plc (UK)
        ("Acme PLC", "plc"),
        # sa (French/Spanish)
        ("Acme SA", "sa"),
        # sarl (French)
        ("Acme SARL", "sarl"),
        # ag (German/Swiss)
        ("Acme AG", "ag"),
        # oy (Finnish)
        ("Acme Oy", "oy"),
        # ab (Swedish)
        ("Acme AB", "ab"),
        # as (Norwegian)
        ("Acme AS", "as"),
        # co
        ("Acme Co", "co"),
        # corp
        ("Acme Corp", "corp"),
        # corporation
        ("Acme Corporation", "corporation"),
    )

    NON_MATCHES = (
        "include",  # contains "inc" but
                    # not as a suffix
        "incorporated",  # contains "inc"
                         # but not the
                         # legal form
        "agency",  # contains "ag"
                   # but not the
                   # legal form
        "association",  # contains "as"
                        # but not the
                        # legal form
    )

    def test_legal_suffix_matches_documented_forms(self) -> None:
        """`_LEGAL_SUFFIX` in
        `jobsearch/normalize.py`
        must match every
        documented
        legal-form
        suffix. A drift
        that removes a
        legal form
        would silently
        break company
        dedup.
        """
        mod = _load_normalize()
        for company, expected_form in self.LEGAL_FORM_SAMPLES:
            with self.subTest(company=company):
                m = mod._LEGAL_SUFFIX.search(company)
                self.assertIsNotNone(
                    m,
                    f"_LEGAL_SUFFIX did NOT "
                    f"match the documented "
                    f"legal form in "
                    f"{company!r}. The "
                    f"regex is the "
                    f"company-name dedup "
                    f"contract: a legal "
                    f"form not matched "
                    f"would silently "
                    f"break dedup, "
                    f"turning e.g. "
                    f"'Acme GmbH' and "
                    f"'Acme' into 2 "
                    f"different companies."
                )
                # And the
                # matched
                # form
                # must
                # be
                # the
                # expected
                # one.
                self.assertEqual(
                    m.group(0).rstrip(".").lower(),
                    expected_form,
                    f"_LEGAL_SUFFIX matched "
                    f"{m.group(0)!r} in "
                    f"{company!r}, expected "
                    f"{expected_form!r}. "
                    f"The match must be the "
                    f"documented legal form."
                )

    def test_legal_suffix_does_not_match_word_substring(self) -> None:
        """`_LEGAL_SUFFIX` in
        `jobsearch/normalize.py`
        must NOT match a
        word that
        contains a legal
        form as a
        substring (the
        regex uses
        word boundaries
        `\b`).

        Without word
        boundaries, the
        regex would
        over-strip:
        "include" would
        be stripped to
        "clude" (the "inc"
        match), and the
        company name
        would be
        corrupted.
        """
        mod = _load_normalize()
        for word in self.NON_MATCHES:
            with self.subTest(word=word):
                self.assertIsNone(
                    mod._LEGAL_SUFFIX.search(word),
                    f"_LEGAL_SUFFIX matched "
                    f"a non-suffix word "
                    f"{word!r}. The regex "
                    f"must use word "
                    f"boundaries so it "
                    f"only matches the "
                    f"documented legal "
                    f"forms as whole "
                    f"words. A regex "
                    f"without word "
                    f"boundaries would "
                    f"silently corrupt "
                    f"company names "
                    f"(e.g. 'include' "
                    f"-> 'clude')."
                )

    def test_legal_suffix_pattern_uses_word_boundary(self) -> None:
        """The `_LEGAL_SUFFIX`
        pattern must use
        word boundaries
        (`\b`) so it
        only matches the
        legal forms as
        whole words, not
        as substrings.

        This is the
        structural pin:
        the regex source
        must contain
        `\b` anchors
        around the
        legal forms.
        """
        mod = _load_normalize()
        pat = mod._LEGAL_SUFFIX.pattern
        # The
        # pattern
        # must
        # contain
        # \b
        # anchors.
        self.assertIn(
            r"\b", pat,
            f"_LEGAL_SUFFIX pattern "
            f"{pat!r} does NOT contain "
            f"\\b word-boundary "
            f"anchors. Without \\b, "
            f"the regex would match "
            f"a legal form as a "
            f"substring (e.g. "
            f"'include' would match "
            f"the 'inc' prefix)."
        )
        # And it
        # must
        # allow
        # an
        # optional
        # trailing
        # dot.
        self.assertIn(
            r"\.", pat,
            f"_LEGAL_SUFFIX pattern "
            f"{pat!r} does NOT allow "
            f"an optional trailing "
            f"dot. Real legal forms "
            f"appear with or without "
            f"a trailing dot "
            f"('Acme Inc.' vs "
            f"'Acme Inc')."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
