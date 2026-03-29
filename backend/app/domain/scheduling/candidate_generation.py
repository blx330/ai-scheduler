from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import Optional
from zoneinfo import ZoneInfo

from app.domain.common.datetime_utils import ensure_utc


def generate_candidate_starts(
    horizon_start: datetime,
    horizon_end: datetime,
    duration_minutes: int,
    slot_step_minutes: int,
    organizer_timezone: str,
    daily_window_start_local: Optional[time],
    daily_window_end_local: Optional[time],
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
    window_start: Optional[time],
    window_end: Optional[time],
) -> bool:
    if window_start is None or window_end is None:
        return True
    local_start = start_at.astimezone(zone)
    local_end = end_at.astimezone(zone)
    return (
        local_start.date() == local_end.date()
        and local_start.timetz().replace(tzinfo=None) >= window_start
        and local_end.timetz().replace(tzinfo=None) <= window_end
    )
