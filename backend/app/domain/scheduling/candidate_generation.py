from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.common.datetime_utils import ensure_utc
from app.domain.common.time_of_day import contained_in_range, slot_minutes


def generate_candidate_starts(
    horizon_start: datetime,
    horizon_end: datetime,
    duration_minutes: int,
    slot_step_minutes: int,
    organizer_timezone: str,
    daily_window_start_local: time | None,
    daily_window_end_local: time | None,
) -> list[datetime]:
    results: list[datetime] = []
    cursor = ensure_utc(horizon_start)
    end_boundary = ensure_utc(horizon_end)
    duration_delta = timedelta(minutes=duration_minutes)
    step_delta = timedelta(minutes=slot_step_minutes)
    organizer_zone = ZoneInfo(organizer_timezone)
    while cursor + duration_delta <= end_boundary:
        slot_end = cursor + duration_delta
        if _within_daily_window(
            cursor,
            slot_end,
            organizer_zone,
            daily_window_start_local,
            daily_window_end_local,
        ):
            results.append(cursor)
        cursor += step_delta
    return results


def _within_daily_window(
    start_at: datetime,
    end_at: datetime,
    zone: ZoneInfo,
    window_start: time | None,
    window_end: time | None,
) -> bool:
    if window_start is None or window_end is None:
        return True
    start_minutes, end_minutes = slot_minutes(start_at.astimezone(zone), end_at.astimezone(zone))
    return contained_in_range(
        start_minutes,
        end_minutes,
        window_start.hour * 60 + window_start.minute,
        window_end.hour * 60 + window_end.minute,
    )
