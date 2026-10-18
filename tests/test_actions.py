"""I-19 -- the action vocabulary pin.

The action vocabulary in `jobsearch/notify.py`
(`ACTION_APPROVE`, `ACTION_REJECT`,
`ACTION_RESEARCH`, `ACTION_SAVE`,
`ACTIONS`, `ACTION_MEANING`) is the gate's
public M3 API: these are the strings the
shortlist UI/CLI passes to the notify layer
to indicate what the user wants to do with
a job (approve to prepare, reject to drop,
research to look deeper, save to park for
later).

Before this turn, no test pinned these
constants. A contributor who renamed
`ACTION_APPROVE` from `"approve"` to
`"accept"` would silently break the M3
shortlist UI/CLI -- every external caller
passing the old string would no longer
match. A contributor who changed
`ACTION_MEANING[ACTION_APPROVE]` from
`"prepare this one (NOT authorisation
to submit)"` to `"prepare this one"`
would silently lose the explicit
"NOT authorisation to submit" caveat
-- a critical safety message that
prevents the user from accidentally
thinking the gate has authorised
them to submit a job application.

The fix is a new `TestActionVocabulary`
class with 5 tests:
1. `test_action_constants_set_matches_documented`:
   structural set equality on the 4
   action constants
   (`ACTION_APPROVE`, `ACTION_REJECT`,
   `ACTION_RESEARCH`, `ACTION_SAVE`).
2. `test_actions_tuple_set_matches_documented`:
   structural set equality on
   `ACTIONS` (the canonical tuple
   of the 4 actions).
3. `test_action_meaning_keys_match_actions`:
   the keys of `ACTION_MEANING`
   must equal the entries of
   `ACTIONS` (every action has
   a meaning, no orphaned
   meaning).
4. `test_every_action_meaning_is_nonempty`:
   every action has a
   non-empty meaning string
   (an empty meaning would
   silently break the M3
   shortlist UI which
   displays the meaning).
5. `test_action_meaning_strings_unchanged`:
   structural pin on the
   exact meaning strings
   (the "NOT authorisation
   to submit" caveat
   especially).

Drift-injection verified: changing
`ACTION_APPROVE` to `"accept"`
fails both structural tests with
precise errors.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import notify  # noqa: E402
from jobsearch.notify import (  # noqa: E402
    ACTION_APPROVE,
    ACTION_MEANING,
    ACTION_REJECT,
    ACTION_RESEARCH,
    ACTION_SAVE,
    ACTIONS,
)


# The 4 documented actions. These
# are the public M3 API strings the
# shortlist UI/CLI passes to the
# notify layer. If you rename one,
# update this test in the same
# commit.
ACTIONS_EXPECTED = {
    "approve", "reject", "research", "save",
}

# The 4 documented meaning strings
# keyed by action. The exact
# strings are part of the public
# contract: the M3 shortlist UI
# displays them to the user.
# The "NOT authorisation to submit"
# caveat in `ACTION_APPROVE` is
# especially critical -- it
# prevents the user from
# accidentally thinking the gate
# has authorised them to submit
# a job application.
ACTION_MEANING_EXPECTED = {
    "approve": "prepare this one (NOT authorisation to submit)",
    "reject": "drop it",
    "research": "look deeper (company, people, salary, scope)",
    "save": "park it for later",
}


class TestActionVocabulary(unittest.TestCase):
    """The action vocabulary in
    `jobsearch/notify.py` is the
    gate's public M3 API: these
    are the strings the shortlist
    UI/CLI passes to the notify
    layer. They must be pinned.
    """

    def test_action_constants_set_matches_documented(self) -> None:
        """The 4 action constants
        (`ACTION_APPROVE`,
        `ACTION_REJECT`,
        `ACTION_RESEARCH`,
        `ACTION_SAVE`) must each
        match the documented
        action string.

        Renaming `ACTION_APPROVE`
        from `"approve"` to
        `"accept"` would silently
        break the M3 shortlist
        UI/CLI.
        """
        actual = {
            "ACTION_APPROVE": ACTION_APPROVE,
            "ACTION_REJECT": ACTION_REJECT,
            "ACTION_RESEARCH": ACTION_RESEARCH,
            "ACTION_SAVE": ACTION_SAVE,
        }
        for name, value in actual.items():
            with self.subTest(constant=name):
                self.assertIn(
                    value, ACTIONS_EXPECTED,
                    f"{name}={value!r} is not in the "
                    f"documented action set "
                    f"{sorted(ACTIONS_EXPECTED)}. "
                    f"Renaming an action constant "
                    f"would silently break the M3 "
                    f"shortlist UI/CLI which passes "
                    f"this string. If the rename is "
                    f"intentional, update "
                    f"ACTIONS_EXPECTED in the same "
                    f"commit. Actual: {sorted(actual.values())}"
                )

    def test_actions_tuple_set_matches_documented(self) -> None:
        """`ACTIONS` (the canonical
        tuple of the 4 actions)
        must contain exactly the
        4 documented action
        strings.
        """
        actual = set(ACTIONS)
        expected = ACTIONS_EXPECTED
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing, set(),
            f"ACTIONS is missing "
            f"{len(missing)} expected "
            f"action(s): {sorted(missing)}. "
            f"Removing an action from "
            f"ACTIONS would silently "
            f"break the M3 shortlist "
            f"UI/CLI which passes the "
            f"missing string. If the "
            f"removal is intentional, "
            f"update ACTIONS_EXPECTED "
            f"in the same commit. "
            f"Actual: {sorted(actual)}"
        )
        self.assertEqual(
            extra, set(),
            f"ACTIONS has {len(extra)} "
            f"undocumented action(s): "
            f"{sorted(extra)}. If an "
            f"action was intentionally "
            f"added, update "
            f"ACTIONS_EXPECTED in the "
            f"same commit. Actual: "
            f"{sorted(actual)}"
        )

    def test_action_meaning_keys_match_actions(self) -> None:
        """The keys of
        `ACTION_MEANING` must
        equal the entries of
        `ACTIONS` (every
        action has a meaning,
        no orphaned meaning).
        """
        meaning_keys = set(ACTION_MEANING.keys())
        actions_set = set(ACTIONS)
        missing_meaning = actions_set - meaning_keys
        extra_meaning = meaning_keys - actions_set
        self.assertEqual(
            missing_meaning, set(),
            f"ACTION_MEANING is missing "
            f"the meaning for "
            f"{len(missing_meaning)} "
            f"action(s): "
            f"{sorted(missing_meaning)}. "
            f"An action without a "
            f"meaning would silently "
            f"break the M3 shortlist "
            f"UI which displays the "
            f"meaning. Add the missing "
            f"meaning, or remove the "
            f"action from ACTIONS."
        )
        self.assertEqual(
            extra_meaning, set(),
            f"ACTION_MEANING has "
            f"{len(extra_meaning)} "
            f"orphaned meaning(s) for "
            f"actions not in ACTIONS: "
            f"{sorted(extra_meaning)}. "
            f"An orphaned meaning is "
            f"dead code -- it can never "
            f"be displayed. Remove the "
            f"orphaned meaning, or add "
            f"the action to ACTIONS."
        )

    def test_every_action_meaning_is_nonempty(self) -> None:
        """Every action must
        have a non-empty
        meaning string. An
        empty meaning would
        silently break the
        M3 shortlist UI
        which displays the
        meaning.
        """
        for action, meaning in ACTION_MEANING.items():
            with self.subTest(action=action):
                self.assertTrue(
                    meaning and meaning.strip(),
                    f"ACTION_MEANING[{action!r}] "
                    f"is empty. The M3 shortlist "
                    f"UI displays the meaning; "
                    f"an empty meaning would "
                    f"render as a blank line, "
                    f"silently confusing the user "
                    f"about what the action does."
                )

    def test_action_meaning_strings_unchanged(self) -> None:
        """The exact meaning
        strings are part of
        the public contract:
        the M3 shortlist UI
        displays them to the
        user.

        The "NOT authorisation
        to submit" caveat in
        `ACTION_APPROVE` is
        especially critical --
        it prevents the user
        from accidentally
        thinking the gate has
        authorised them to
        submit a job
        application.
        """
        actual = dict(ACTION_MEANING)
        expected = ACTION_MEANING_EXPECTED
        for action, expected_meaning in expected.items():
            with self.subTest(action=action):
                actual_meaning = actual.get(action)
                self.assertEqual(
                    actual_meaning, expected_meaning,
                    f"ACTION_MEANING[{action!r}] "
                    f"is {actual_meaning!r}, "
                    f"expected {expected_meaning!r}. "
                    f"The exact meaning string "
                    f"is part of the public "
                    f"contract: the M3 shortlist "
                    f"UI displays it to the user. "
                    f"A change to the 'NOT "
                    f"authorisation to submit' "
                    f"caveat especially is a "
                    f"safety regression -- it "
                    f"could cause the user to "
                    f"accidentally think the gate "
                    f"has authorised them to "
                    f"submit a job application. "
                    f"If the change is intentional, "
                    f"update ACTION_MEANING_EXPECTED "
                    f"in the same commit."
                )
        # And check no extra meanings
        for action in actual:
            self.assertIn(
                action, expected,
                f"ACTION_MEANING has an extra "
                f"key {action!r} not in the "
                f"documented meaning set. "
                f"Remove the orphaned meaning, "
                f"or add it to "
                f"ACTION_MEANING_EXPECTED in the "
                f"same commit."
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
