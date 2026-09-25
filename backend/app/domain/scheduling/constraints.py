"""Organizer-set hard rules on which days and times an event may be practiced.

These are hard gates, unlike member preferences, which only nudge the score. They
are checked in the planner's candidate filter (so fallbacks and the multi-session
lookahead obey them too) and again when a session is confirmed, so a manual time
override cannot bypass them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo

from app.domain.common.enums import Weekday
from app.domain.common.time_of_day import MINUTES_PER_DAY, contained_in_range, slot_minutes
from app.domain.scheduling.models import ScheduleSlot

# datetime.weekday() index -> Weekday. strftime("%a") would honour LC_TIME.
WEEKDAY_BY_INDEX = (
    Weekday.MON,
    Weekday.TUE,
    Weekday.WED,
    Weekday.THU,
    Weekday.FRI,
    Weekday.SAT,
    Weekday.SUN,
)


@dataclass(frozen=True)
class DayTimeConstraints:
    # Empty means every day is allowed.
    allowed_weekdays: frozenset[Weekday] = field(default_factory=frozenset)
    blocked_weekdays: frozenset[Weekday] = field(default_factory=frozenset)
    earliest_start_local: time | None = None
    # time(0, 0) means the end of the day (midnight), not the start of it.
    latest_end_local: time | None = None

    def __post_init__(self) -> None:
        overlap = self.allowed_weekdays & self.blocked_weekdays
        if overlap:
            days = ", ".join(day.value for day in WEEKDAY_BY_INDEX if day in overlap)
            raise ValueError(f"Days cannot be both allowed and blocked: {days}")
        if self.earliest_start_local is not None and self.latest_end_local is not None:
            if _minutes(self.earliest_start_local) >= _end_minutes(self.latest_end_local):
                raise ValueError(
                    f"Earliest start {self.earliest_start_local:%H:%M} must be before "
                    f"latest end {self.latest_end_local:%H:%M}"
                )

    @property
    def is_unconstrained(self) -> bool:
        return (
            not self.allowed_weekdays
            and not self.blocked_weekdays
            and self.earliest_start_local is None
            and self.latest_end_local is None
        )

    def rejection_reason(self, slot: ScheduleSlot, zone: ZoneInfo) -> str | None:
        """None when the slot satisfies every rule, else a stable rejection code."""
        local_start = slot.start_at.astimezone(zone)
        weekday = WEEKDAY_BY_INDEX[local_start.weekday()]
        if weekday in self.blocked_weekdays:
            return "blocked_weekday"
        if self.allowed_weekdays and weekday not in self.allowed_weekdays:
            return "weekday_not_allowed"
        if self.earliest_start_local is None and self.latest_end_local is None:
            return None
        start_minutes, end_minutes = slot_minutes(local_start, slot.end_at.astimezone(zone))
        window_start = 0 if self.earliest_start_local is None else _minutes(self.earliest_start_local)
        window_end = MINUTES_PER_DAY if self.latest_end_local is None else _end_minutes(self.latest_end_local)
        if not contained_in_range(start_minutes, end_minutes, window_start, window_end):
            return "outside_time_window"
        return None


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _end_minutes(value: time) -> int:
    minutes = _minutes(value)
    return MINUTES_PER_DAY if minutes == 0 else minutes
