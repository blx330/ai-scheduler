from datetime import datetime, timezone

from app.domain.availability.interval_ops import interval_covered, merge_intervals, subtract_intervals
from app.domain.availability.models import Interval


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, 23, hour, minute, tzinfo=timezone.utc)


def test_merge_intervals_merges_adjacent_and_overlapping() -> None:
    intervals = [
        Interval(dt(9), dt(10)),
        Interval(dt(10), dt(11)),
        Interval(dt(12), dt(13)),
        Interval(dt(12, 30), dt(14)),
    ]

    merged = merge_intervals(intervals)

    assert merged == [Interval(dt(9), dt(11)), Interval(dt(12), dt(14))]


def test_subtract_intervals_respects_busy_gaps() -> None:
    available = [Interval(dt(9), dt(12))]
    busy = [Interval(dt(10), dt(11))]

    effective = subtract_intervals(available, busy)

    assert effective == [Interval(dt(9), dt(10)), Interval(dt(11), dt(12))]


def test_interval_covered_requires_full_coverage() -> None:
    covering = [Interval(dt(9), dt(10)), Interval(dt(10), dt(11))]

    assert interval_covered(Interval(dt(9), dt(11)), covering)
    assert not interval_covered(Interval(dt(9, 30), dt(11, 30)), covering)
