from app.domain.availability.models import Interval
from app.domain.common.datetime_utils import ensure_utc


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: (item.start_at, item.end_at))
    merged = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start_at <= last.end_at:
            merged[-1] = Interval(start_at=last.start_at, end_at=max(last.end_at, current.end_at))
            continue
        merged.append(current)
    return merged


def subtract_intervals(available: list[Interval], busy: list[Interval]) -> list[Interval]:
    free = merge_intervals(available)
    blocked = merge_intervals(busy)
    results: list[Interval] = []
    for open_interval in free:
        remaining = [open_interval]
        for busy_interval in blocked:
            next_remaining: list[Interval] = []
            for interval in remaining:
                if busy_interval.end_at <= interval.start_at or busy_interval.start_at >= interval.end_at:
                    next_remaining.append(interval)
                    continue
                if busy_interval.start_at > interval.start_at:
                    next_remaining.append(Interval(interval.start_at, busy_interval.start_at))
                if busy_interval.end_at < interval.end_at:
                    next_remaining.append(Interval(busy_interval.end_at, interval.end_at))
            remaining = next_remaining
            if not remaining:
                break
        results.extend(remaining)
    return merge_intervals(results)


def interval_covered(interval: Interval, covering_intervals: list[Interval]) -> bool:
    return any(
        covering.start_at <= interval.start_at and covering.end_at >= interval.end_at
        for covering in merge_intervals(covering_intervals)
    )


def build_effective_availability(manual_intervals, busy_intervals) -> list[Interval]:
    manual = [Interval(ensure_utc(item.start_at), ensure_utc(item.end_at)) for item in manual_intervals]
    busy = [Interval(ensure_utc(item.start_at), ensure_utc(item.end_at)) for item in busy_intervals]
    if not manual:
        return []
    return subtract_intervals(manual, busy)
