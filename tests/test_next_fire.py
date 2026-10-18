"""W4.5 -- Timezone and DST contract test.

The morning-prepare next-fire-time must stay on 08:00
local across a DST boundary. Across a spring-forward
boundary, the next 08:00 is still 08:00. Across a
fall-back boundary, the local day is 25 hours long,
and the next 08:00 is also 08:00 (no double-fire, no
missed fire).

Run:  python3 -m unittest tests.test_next_fire -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The tools/ tree has no __init__.py, so we cannot
# `from tools.next_fire import ...` like a normal
# package. We add tools/ to sys.path and import the
# module directly.
sys.path.insert(0, str(ROOT / "tools"))
from next_fire import next_fire, DEFAULT_TZ  # noqa: E402


class TestNextFire(unittest.TestCase):
    """W4.5 -- 08:00 stays 08:00 across a DST boundary."""

    def test_today_before_eight_is_today_at_eight(self) -> None:
        """If now is 07:30 in Europe/Berlin, the next fire
        is today at 08:00."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 6, 1, 7, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour, nxt.minute),
            (2026, 6, 1, 8, 0),
        )
        self.assertEqual(nxt.tzinfo, tz)

    def test_today_after_eight_is_tomorrow_at_eight(self) -> None:
        """If now is 08:30, the next fire is tomorrow at
        08:00 (we already passed today's fire)."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 6, 1, 8, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 6, 2, 8),
        )

    def test_today_at_eight_is_tomorrow_at_eight(self) -> None:
        """If now is exactly 08:00, the next fire is
        tomorrow (not now): a fire at exactly `now` is
        already in progress, and the helper must not
        return a past-or-equal candidate."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 6, 1, 8, 0, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 6, 2, 8),
        )

    def test_spring_forward_dst_does_not_miss_eight(self) -> None:
        """In Europe/Berlin, the spring-forward 2026
        boundary is 2026-03-29: at 02:00 the clock jumps
        to 03:00. The day is 23 hours, but the morning
        08:00 is unambiguous. If `now` is 01:30 on
        2026-03-29, the next fire is still 08:00 the
        same day."""
        tz = ZoneInfo("Europe/Berlin")
        # 01:30 on the spring-forward day, 6.5 hours
        # before 08:00. DST does not affect 08:00; the
        # day simply has 23 hours.
        now = datetime(2026, 3, 29, 1, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 3, 29, 8),
        )

    def test_spring_forward_dst_does_not_double_fire(self) -> None:
        """If `now` is 07:30 on the spring-forward day,
        the next fire is still 08:00 the same day. The
        day is shorter, but 08:00 only happens once."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 3, 29, 7, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 3, 29, 8),
        )

    def test_fall_back_dst_does_not_double_fire(self) -> None:
        """In Europe/Berlin, the fall-back 2026 boundary
        is 2026-10-25: at 03:00 the clock goes back to
        02:00, so the 02:00-03:00 hour happens twice. The
        morning 08:00 is unambiguous. If `now` is 07:30,
        the next fire is 08:00 the same day, not the
        second-occurrence of an earlier hour."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 10, 25, 7, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 10, 25, 8),
        )

    def test_fall_back_at_one_am_loop_picks_first_eight(self) -> None:
        """A pathological case: now is 02:30 (the FIRST
        02:30 of the fall-back day). The next fire is
        still 08:00 the same day; the helper does not
        confuse itself with the second 02:00-03:00
        hour."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 10, 25, 2, 30, tzinfo=tz,
                       fold=0)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 10, 25, 8),
        )

    def test_naive_now_is_utc(self) -> None:
        """A naive `now` is interpreted as UTC. The
        next fire is converted to the target timezone."""
        tz = ZoneInfo("Europe/Berlin")
        # 06:00 UTC on a summer day in Berlin is 08:00
        # local. The next fire from 05:00 UTC is 08:00
        # local the same day.
        now = datetime(2026, 6, 1, 5, 0)
        nxt = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 6, 1, 8),
        )
        self.assertEqual(nxt.tzinfo, tz)

    def test_unknown_timezone_raises_value_error(self) -> None:
        """An unknown timezone name produces a clear
        ValueError, not a generic exception."""
        now = datetime(2026, 6, 1, 5, 0, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(ValueError) as cm:
            next_fire(now, target_hour=8, tz_name="Atlantis")
        self.assertIn("Atlantis", str(cm.exception))

    def test_invalid_target_hour_raises_value_error(self) -> None:
        """A target_hour outside 0..23 is a programming
        error and must be loud."""
        now = datetime(2026, 6, 1, 5, 0, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(ValueError):
            next_fire(now, target_hour=24, tz_name="UTC")
        with self.assertRaises(ValueError):
            next_fire(now, target_hour=-1, tz_name="UTC")

    def test_different_timezone_is_respected(self) -> None:
        """A 06:00 UTC `now` produces 08:00 in Berlin AND
        a different local hour in New York. The
        timezone parameter is honoured, not hardcoded."""
        now = datetime(2026, 6, 1, 6, 0, tzinfo=ZoneInfo("UTC"))
        berlin = next_fire(now, target_hour=8, tz_name="Europe/Berlin")
        newyork = next_fire(now, target_hour=8, tz_name="America/New_York")
        self.assertEqual(berlin.hour, 8)
        self.assertEqual(berlin.utcoffset().total_seconds() / 3600, 2)
        # 08:00 New York in June is 12:00 UTC, which is
        # 4 hours after `now` (06:00 UTC). So the next
        # fire is today at 08:00 in New York.
        self.assertEqual(newyork.hour, 8)
        self.assertEqual(
            newyork.utcoffset().total_seconds() / 3600, -4
        )

    def test_midnight_is_a_valid_target_hour(self) -> None:
        """target_hour=0 (midnight) is supported; the
        helper is not hardcoded to 8."""
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 6, 1, 23, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=0, tz_name="Europe/Berlin")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 6, 2, 0),
        )

    def test_default_timezone_is_europe_berlin(self) -> None:
        """The default tz is Europe/Berlin; an operator
        who does not pass --tz gets the local Berlin
        time. The README documents this; a contributor
        who changes the default must update this test."""
        self.assertEqual(DEFAULT_TZ, "Europe/Berlin")

    def test_utc_timezone_works(self) -> None:
        """UTC is a valid tz_name; a UTC-based
        deployment is supported."""
        tz = ZoneInfo("UTC")
        now = datetime(2026, 6, 1, 7, 30, tzinfo=tz)
        nxt = next_fire(now, target_hour=8, tz_name="UTC")
        self.assertEqual(
            (nxt.year, nxt.month, nxt.day, nxt.hour),
            (2026, 6, 1, 8),
        )
        self.assertEqual(nxt.utcoffset().total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
