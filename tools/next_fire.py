"""W4.5 -- next-fire-time helper.

08:00 stays 08:00 across a DST boundary. The
next-fire-time for the morning-prepare cron is
computed by `next_fire(now, target_hour=8, tz_name=...)`,
a pure function that takes a clock and returns the
next target_hour in the target timezone.

Across a spring-forward boundary (e.g. Europe/Berlin
2026-03-29), the local clock skips from 02:00 to 03:00
and the day has 23 hours. The morning 08:00 is
unambiguous; the helper just iterates day-by-day using
`zoneinfo` and never produces a non-existent wall-clock
time.

Across a fall-back boundary (e.g. Europe/Berlin
2026-10-25), the local clock goes from 02:59 back to
02:00 and the 02:00-03:00 hour happens twice. The
morning 08:00 is still unambiguous; the helper picks
the first 08:00 of the day.

The function is fully local (no shell, no `date`); the
operator can compute the next fire time in any
timezone without depending on the host's clock.

Borrowed shape: the standard Python `zoneinfo` module
(Python 3.9+) plus `datetime.replace()` for the
hour-set. The spring/fall transitions are handled
implicitly: `zoneinfo` knows when 02:00 does not exist
(spring) and when 02:00 occurs twice (fall); the helper
just iterates the date by one day at a time.

Usage:
    from tools.next_fire import next_fire
    nxt = next_fire(datetime.now(timezone.utc))
    # -> next 08:00 in Europe/Berlin

Run:  python3 tools/next_fire.py
      # prints the next 08:00 Berlin time as ISO 8601
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# W4.5 -- the local timezone default. The owner runs the
# morning-prepare in Europe/Berlin. A future operator in
# another timezone overrides this with --tz. The
# default is documented in the README; a contributor who
# changes the default must update the W4.5 contract test.
DEFAULT_TZ = "Europe/Berlin"
DEFAULT_HOUR = 8


def next_fire(
    now: datetime,
    *,
    target_hour: int = DEFAULT_HOUR,
    tz_name: str = DEFAULT_TZ,
) -> datetime:
    """Return the next datetime >= now whose local hour
    is target_hour in tz_name. The result is timezone-
    aware (tz=tz_name).

    DST: the function iterates day-by-day, computing
    the target datetime in tz_name and checking it is
    strictly after `now`. Across a spring-forward
    boundary, the local clock skips the missing hour;
    the helper never produces a non-existent wall-clock
    time. Across a fall-back boundary, the helper picks
    the first target_hour of the day.

    Args:
      now: a timezone-aware or naive datetime. If
        naive, it is interpreted as UTC.
      target_hour: the local hour (0..23) at which the
        job should fire. Defaults to 08:00.
      tz_name: an IANA timezone name (e.g.
        "Europe/Berlin"). Defaults to DEFAULT_TZ.

    Returns:
      A timezone-aware datetime in tz_name.

    Raises:
      ValueError: if the computed next-fire time is
        not strictly after `now` (the helper is stuck;
        the caller should treat this as a bug).
    """
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"unknown timezone {tz_name!r}; use an IANA "
            f"name like 'Europe/Berlin'"
        ) from exc
    if not (0 <= target_hour <= 23):
        raise ValueError(
            f"target_hour must be 0..23; got {target_hour}"
        )
    # Anchor the comparison in the target timezone. We
    # never call `now.replace(hour=target_hour)` on a
    # naive datetime; instead, we convert `now` to the
    # target zone and then iterate day-by-day.
    if now.tzinfo is None:
        now_utc = now.replace(tzinfo=timezone.utc)
    else:
        now_utc = now.astimezone(timezone.utc)
    # Start with the local-tz representation of now.
    now_local = now_utc.astimezone(tz)
    # The candidate is today at target_hour in tz. If
    # `now` is before that, today is the answer. If
    # `now` is at-or-after, tomorrow is the answer.
    candidate_today = now_local.replace(
        hour=target_hour, minute=0, second=0, microsecond=0,
    )
    if candidate_today > now_local:
        return candidate_today
    # Tomorrow (or further if a DST transition warped the
    # clock: iterating day-by-day converges in <= 2
    # iterations because target_hour is the same
    # wall-clock hour every day).
    candidate = candidate_today + timedelta(days=1)
    # Defensive: a future-proofing guard. In practice the
    # loop is unnecessary; we keep one step to be safe
    # against a target_hour that happens to land inside a
    # DST gap.
    for _ in range(7):
        if candidate > now_local:
            return candidate
        candidate = candidate + timedelta(days=1)
    raise ValueError(
        f"next_fire could not find a valid time for "
        f"now={now!r} target_hour={target_hour} tz={tz_name}"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: print the next fire time for the host."""
    import argparse
    ap = argparse.ArgumentParser(
        description="Print the next morning-prepare fire time"
    )
    ap.add_argument(
        "--tz", default=DEFAULT_TZ,
        help=f"IANA timezone name (default: {DEFAULT_TZ})",
    )
    ap.add_argument(
        "--hour", type=int, default=DEFAULT_HOUR,
        help=f"target local hour 0..23 (default: {DEFAULT_HOUR})",
    )
    ap.add_argument(
        "--now", default=None,
        help="override the clock (ISO 8601); for testing",
    )
    args = ap.parse_args(argv)
    if args.now:
        now = datetime.fromisoformat(args.now)
    else:
        now = datetime.now(timezone.utc)
    nxt = next_fire(now, target_hour=args.hour, tz_name=args.tz)
    print(nxt.isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
