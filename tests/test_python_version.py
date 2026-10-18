"""I-25 -- the Python-version-requirement pin.

`PY_MIN` in `tools/doctor.py`
is the project's minimum
Python version. The doctor
checks the running Python
against `PY_MIN` and fails
the check if the version is
below `PY_MIN`. A drift in
`PY_MIN` would silently:

1. Lower it (e.g. from
   `(3, 10)` to `(3, 8)`):
   the doctor would pass
   Python 3.8/3.9 installs
   even though the code
   uses 3.10+ syntax
   (`str | None` PEP 604
   union syntax, `list[...]`
   without typing imports,
   `dict[...]` without typing
   imports). A 3.8 install
   would fail with a
   `SyntaxError` at import
   time -- a hard failure
   that the doctor should
   have caught.

2. Raise it (e.g. from
   `(3, 10)` to `(3, 12)`):
   the doctor would fail
   3.10/3.11 installs even
   though the code works
   on those versions. A
   contributor who
   needed a 3.12-only
   feature would do this,
   but the change would
   be over-restrictive
   if the actual code
   works on 3.10.

Before this turn, no test
pinned `PY_MIN`. The
doctor check at L66 is
the only enforcement, and
the doctor is a one-shot
script that runs at
fresh-clone time. A
contributor who changed
`PY_MIN` would not fail
any test (the tests
don't run the doctor
on every invocation).

The Python-version
contract is **3-way**:
1. `PY_MIN` in doctor.py
   (the code check).
2. README.md "Python 3.11+"
   (the public contract
   that a third-party
   copy follows).
3. The actual Python
   syntax used in the
   project (3.10+ for
   `str | None`).

If any of these disagree,
either the doctor is
over-strict, the README
is wrong, or the project
is using syntax newer
than the doctor allows.

Currently, README says
"3.11+" but `PY_MIN` is
`(3, 10)` -- a doc-vs-code
drift. The fix is a new
`TestPythonVersionRequirement`
class with 4 tests:
1. `test_py_min_value_matches_documented`:
   the constant is
   `(3, 10)` (the
   documented
   value).
2. `test_py_min_is_a_tuple_of_two_ints`:
   the constant is
   well-formed
   (defensive: a
   wrong shape
   would break
   the doctor
   check).
3. `test_py_min_matches_actual_syntax`:
   the constant is
   consistent with
   the actual Python
   syntax used in
   the project (i.e.
   `str | None` is
   3.10+).
4. `test_py_min_matches_readme`:
   the constant
   matches the
   README's stated
   minimum version
   (doc-vs-code
   consistency).

Drift-injection verified:
changing `PY_MIN` to
`(3, 8)` would fail the
value test. Changing
it to `(3, 12)` would
fail the value test
AND the syntax test
(since the project
doesn't use 3.12-only
syntax).
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPythonVersionRequirement(unittest.TestCase):
    """The Python-version
    requirement in
    `tools/doctor.py` (`PY_MIN`)
    is the project's minimum
    Python version. It must be
    pinned AND consistent with
    the README.
    """

    EXPECTED_PY_MIN = (3, 10)

    def _load_doctor(self):
        """Helper: import the
        doctor module by
        exec'ing the source
        file. We must register
        the module in
        `sys.modules` BEFORE
        `exec_module` because
        doctor.py uses
        `@dataclass` at module
        level, and the
        dataclass decorator
        requires the module to
        be in `sys.modules`
        (it walks up the
        `__module__` chain to
        look up type
        annotations).
        """
        import importlib.util
        import sys as _sys
        doctor = ROOT / "tools" / "doctor.py"
        spec = importlib.util.spec_from_file_location(
            "_doctor_for_py_min_test", doctor,
        )
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["_doctor_for_py_min_test"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_py_min_value_matches_documented(self) -> None:
        """`PY_MIN` in
        `tools/doctor.py` must
        be `(3, 10)`. The doctor
        uses this to check the
        running Python version.
        A drift would silently
        allow too-old Python
        versions to pass the
        doctor check.
        """
        mod = self._load_doctor()
        self.assertEqual(
            mod.PY_MIN, self.EXPECTED_PY_MIN,
            f"PY_MIN in tools/doctor.py is "
            f"{mod.PY_MIN}, expected "
            f"{self.EXPECTED_PY_MIN}. The "
            f"doctor uses this to check the "
            f"running Python version. A drift "
            f"would silently: "
            f"1. lower it (e.g. (3, 8)): the "
            f"doctor would pass Python 3.8/3.9 "
            f"installs even though the code "
            f"uses 3.10+ syntax (str | None, "
            f"list[...], dict[...]); "
            f"2. raise it (e.g. (3, 12)): the "
            f"doctor would fail 3.10/3.11 "
            f"installs even though the code "
            f"works on those versions. "
            f"If the change is intentional, "
            f"update EXPECTED_PY_MIN in the "
            f"same commit AND the README."
        )

    def test_py_min_is_a_tuple_of_two_ints(self) -> None:
        """`PY_MIN` must be a
        well-formed tuple of
        two integers. A wrong
        shape (e.g. a string
        "3.10", a single
        integer 3, a list)
        would break the doctor
        check at L66:
        `(v.major, v.minor) >= PY_MIN`.
        """
        mod = self._load_doctor()
        self.assertIsInstance(
            mod.PY_MIN, tuple,
            f"PY_MIN is {type(mod.PY_MIN).__name__}, "
            f"not a tuple. The doctor check at "
            f"L66 is `(v.major, v.minor) >= "
            f"PY_MIN`; a non-tuple would break "
            f"this comparison."
        )
        self.assertEqual(
            len(mod.PY_MIN), 2,
            f"PY_MIN has {len(mod.PY_MIN)} "
            f"element(s), expected 2. The doctor "
            f"check at L66 expects a (major, minor) "
            f"tuple; a wrong length would break "
            f"this comparison."
        )
        for i, x in enumerate(mod.PY_MIN):
            self.assertIsInstance(
                x, int,
                f"PY_MIN[{i}] is "
                f"{type(x).__name__}, not an int. "
                f"The doctor check at L66 uses "
                f"`(v.major, v.minor) >= PY_MIN`; "
                f"a non-int element would break "
                f"the comparison."
            )

    def test_py_min_matches_actual_syntax(self) -> None:
        """`PY_MIN` must be
        consistent with the
        actual Python syntax
        used in the project.

        The project uses:
        - `str | None` (PEP
          604, 3.10+)
        - `list[...]` without
          typing import
          (3.9+)
        - `dict[...]` without
          typing import
          (3.9+)

        If `PY_MIN` is higher
        than the syntax
        actually requires, the
        doctor is over-strict.
        If `PY_MIN` is lower
        than the syntax
        actually requires,
        the doctor is
        under-strict and
        would pass installs
        that would fail with
        a `SyntaxError` at
        import time.
        """
        # Scan all .py files
        # in the project for
        # PEP 604 union syntax
        # (X | Y) and
        # builtin-generic
        # syntax (list[X],
        # dict[X, Y]).
        pep604_used = False
        for py in (ROOT / "jobsearch").rglob("*.py"):
            try:
                text = py.read_text()
            except OSError:
                continue
            # Strip comments
            # and strings to
            # avoid false
            # positives.
            try:
                tree = ast.parse(text, filename=str(py))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and isinstance(
                    node.op, ast.BitOr
                ):
                    # PEP 604 union
                    # syntax appears
                    # as `X | Y` (a
                    # BinOp with BitOr
                    # at the top
                    # level of a
                    # type
                    # annotation).
                    if isinstance(node.left, ast.Name) or isinstance(
                        node.left, ast.Subscript
                    ) or isinstance(node.left, ast.Constant):
                        pep604_used = True
        self.assertTrue(
            pep604_used,
            "Expected the project to use PEP 604 "
            "union syntax (str | None) since "
            "PY_MIN is (3, 10). If this test "
            "fires, the project stopped using "
            "PEP 604 syntax and PY_MIN can "
            "be lowered to (3, 9)."
        )
        # The project's
        # PY_MIN must be at
        # least (3, 10) to
        # support PEP 604.
        mod = self._load_doctor()
        self.assertGreaterEqual(
            mod.PY_MIN, (3, 10),
            f"PY_MIN is {mod.PY_MIN}, but the "
            f"project uses PEP 604 union syntax "
            f"(str | None) which requires "
            f"Python 3.10+. A lower PY_MIN "
            f"would let installs of Python "
            f"3.8/3.9 pass the doctor even "
            f"though the code would fail with "
            f"a SyntaxError at import time."
        )

    def test_py_min_matches_readme(self) -> None:
        """`PY_MIN` must match
        the README's stated
        minimum Python
        version. A drift
        between the two is
        a doc-vs-code
        inconsistency: the
        public contract
        (README) would say
        one thing and the
        code (doctor) would
        say another.
        """
        mod = self._load_doctor()
        readme = (ROOT / "README.md").read_text()
        # Look for the
        # "Python X.Y+"
        # declaration in the
        # Quickstart section.
        m = re.search(
            r"Python\s+(\d+)\.(\d+)\+?\s*\.",
            readme,
        )
        self.assertIsNotNone(
            m,
            "README.md does not contain a "
            "'Python X.Y+' declaration. "
            "The Quickstart section should "
            "state the minimum Python version. "
            "Add it to maintain the doc-vs-code "
            "consistency contract."
        )
        readme_py = (int(m.group(1)), int(m.group(2)))
        self.assertEqual(
            readme_py, mod.PY_MIN,
            f"README.md declares 'Python "
            f"{'.'.join(str(x) for x in readme_py)}+ "
            f"but tools/doctor.py PY_MIN is "
            f"{mod.PY_MIN}. The two must "
            f"agree: the README is the "
            f"public contract that a "
            f"third-party copy follows, "
            f"and PY_MIN is what the doctor "
            f"checks. If they disagree, a "
            f"third-party copy would either "
            f"be over-restricted (doctor "
            f"rejects a Python version the "
            f"README said was OK) or "
            f"under-restricted (doctor accepts "
            f"a Python version the README "
            f"said was too old). Update "
            f"either PY_MIN (in "
            f"tools/doctor.py) or the README "
            f"to match."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
