"""Minutes-since-local-midnight arithmetic for slots that may cross midnight.

Comparing bare `datetime.time` objects breaks for any slot ending at or after
midnight, because the local hour wraps to 0 and compares as *earlier* than the
start. Every time-of-day comparison in the scheduling domain goes through these
helpers so the wrap is handled in exactly one place.

Slot bounds are returned in a half-open [start, end) range on a 0..2880 scale:
a slot that crosses midnight simply has an end past 1440.
"""

from datetime import datetime

MINUTES_PER_DAY = 24 * 60


def minutes_of_day(value: datetime) -> int:
    return value.hour * 60 + value.minute


def slot_minutes(local_start: datetime, local_end: datetime) -> tuple[int, int]:
    """Local slot bounds as minutes since midnight, unwrapped across midnight."""
    start_minutes = minutes_of_day(local_start)
    end_minutes = minutes_of_day(local_end)
    if end_minutes <= start_minutes:
        end_minutes += MINUTES_PER_DAY
    return start_minutes, end_minutes


def range_minutes(range_start: int, range_end: int) -> tuple[int, int]:
    """Window bounds as minutes since midnight, unwrapped (e.g. 22:00 -> 00:00)."""
    if range_end <= range_start:
        range_end += MINUTES_PER_DAY
    return range_start, range_end


def overlap_minutes(start: int, end: int, range_start: int, range_end: int) -> int:
    """Minutes of [start, end) that fall inside [range_start, range_end).

    Both the slot and the window are checked against the next day as well, so a
    slot running past midnight still matches a morning window and vice versa.
    """
    range_start, range_end = range_minutes(range_start, range_end)
    total = 0
    for shift in (0, MINUTES_PER_DAY):
        total += max(0, min(end, range_end + shift) - max(start, range_start + shift))
    return total


def contained_in_range(start: int, end: int, range_start: int, range_end: int) -> bool:
    """True when [start, end) fits entirely inside [range_start, range_end)."""
    range_start, range_end = range_minutes(range_start, range_end)
    return any(
        start >= range_start + shift and end <= range_end + shift
        for shift in (0, MINUTES_PER_DAY)
    )


def overlaps_range(start: int, end: int, range_start: int, range_end: int) -> bool:
    """True when [start, end) shares any time with [range_start, range_end)."""
    return overlap_minutes(start, end, range_start, range_end) > 0
