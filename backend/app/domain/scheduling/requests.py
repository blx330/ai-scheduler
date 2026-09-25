"""The structured form of an organizer's plain-English scheduling request.

This is the contract the LLM must satisfy. Everything here is checkable without the
database; resolving names to real members, rooms and events (and checking dates
against "today") happens in the application layer.

Null or empty means "the request did not say", never "clear this", so an unstated
field keeps the event's saved value instead of being guessed.
"""

from __future__ import annotations

from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.domain.common.enums import Weekday
from app.domain.scheduling.constraints import WEEKDAY_BY_INDEX, DayTimeConstraints
from app.domain.scheduling.global_planner import PRACTICE_WINDOW_START_LOCAL

MAX_SESSIONS_PER_REQUEST = 20
MAX_MIN_DAYS_BETWEEN = 30
MAX_ATTENDEES_PER_ROLE = 50

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100, strict=True)]

_WEEKDAY_ALIASES: dict[str, Weekday] = {}
for _day, _full in zip(
    WEEKDAY_BY_INDEX, ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"), strict=True
):
    _WEEKDAY_ALIASES[_day.value.lower()] = _day
    _WEEKDAY_ALIASES[_full] = _day


class SchedulingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, strict=True)]
    session_count: int | None = Field(default=None, ge=1, le=MAX_SESSIONS_PER_REQUEST, strict=True)
    # Inclusive bounds on the organizer-local dates a session may fall on.
    earliest_date: date | None = None
    latest_date: date | None = None
    min_days_between: int | None = Field(default=None, ge=0, le=MAX_MIN_DAYS_BETWEEN, strict=True)
    required_attendees: list[Name] = Field(default_factory=list, max_length=MAX_ATTENDEES_PER_ROLE)
    optional_attendees: list[Name] = Field(default_factory=list, max_length=MAX_ATTENDEES_PER_ROLE)
    allowed_weekdays: list[Weekday] = Field(default_factory=list)
    blocked_weekdays: list[Weekday] = Field(default_factory=list)
    earliest_start_time: time | None = None
    # 00:00 means midnight at the end of the day.
    latest_end_time: time | None = None
    room: Name | None = None

    @field_validator("allowed_weekdays", "blocked_weekdays", mode="before")
    @classmethod
    def normalize_weekdays(cls, value: object) -> object:
        """Accept unambiguous spellings ("FRI", "fri", "Friday"); reject anything else."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Weekdays must be a list")
        normalized: list[Weekday] = []
        for item in value:
            if not isinstance(item, str) or item.strip().lower() not in _WEEKDAY_ALIASES:
                raise ValueError(f"Unknown weekday {item!r}; use MON, TUE, WED, THU, FRI, SAT or SUN")
            day = _WEEKDAY_ALIASES[item.strip().lower()]
            if day not in normalized:
                normalized.append(day)
        return [day for day in WEEKDAY_BY_INDEX if day in normalized]

    @field_validator("required_attendees", "optional_attendees", mode="before")
    @classmethod
    def null_list_means_unstated(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("required_attendees", "optional_attendees")
    @classmethod
    def dedupe_names(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for name in value:
            if name.casefold() not in seen:
                seen.add(name.casefold())
                unique.append(name)
        return unique

    @model_validator(mode="after")
    def validate_consistency(self) -> SchedulingRequest:
        if self.earliest_date and self.latest_date and self.earliest_date > self.latest_date:
            raise ValueError(f"earliest_date {self.earliest_date} is after latest_date {self.latest_date}")
        both_roles = {name.casefold() for name in self.required_attendees} & {
            name.casefold() for name in self.optional_attendees
        }
        if both_roles:
            raise ValueError(f"People cannot be both required and optional: {', '.join(sorted(both_roles))}")
        latest = self.latest_end_time
        if latest is not None and latest != time(0, 0) and latest <= PRACTICE_WINDOW_START_LOCAL:
            raise ValueError(
                f"latest_end_time {latest:%H:%M} is before practices can start; "
                "practices are only scheduled between 8:00 AM and 12:00 AM"
            )
        self.day_time_constraints()  # raises ValueError on contradictory day/time rules
        return self

    def day_time_constraints(self) -> DayTimeConstraints:
        return DayTimeConstraints(
            allowed_weekdays=frozenset(self.allowed_weekdays),
            blocked_weekdays=frozenset(self.blocked_weekdays),
            earliest_start_local=self.earliest_start_time,
            latest_end_local=self.latest_end_time,
        )
