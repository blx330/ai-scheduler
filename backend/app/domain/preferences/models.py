from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.common.enums import Weekday


class TimeRangePreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_range(self) -> "TimeRangePreference":
        if self.start_local >= self.end_local:
            raise ValueError("Time range start must be before end")
        return self


class PreferredPracticeTime(str, Enum):
    EARLY_MORNING = "early_morning"
    MID_MORNING = "mid_morning"
    LATE_MORNING = "late_morning"


class CachedPracticePreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_days: list[str] = Field(default_factory=list)
    avoid_days: list[str] = Field(default_factory=list)
    earliest_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    latest_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    notes: Optional[str] = None
    summary: Optional[str] = None

    @field_validator("preferred_days", "avoid_days", mode="before")
    @classmethod
    def normalize_days(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Days must be a list")
        normalized: list[str] = []
        for item in value:
            day_name = _normalize_day_name(item)
            if day_name and day_name not in normalized:
                normalized.append(day_name)
        return normalized

    @model_validator(mode="after")
    def validate_times(self) -> "CachedPracticePreference":
        if self.earliest_time and self.latest_time and self.earliest_time >= self.latest_time:
            raise ValueError("Earliest time must be before latest time")
        return self

    def is_useful(self) -> bool:
        return bool(
            self.preferred_days
            or self.avoid_days
            or self.earliest_time
            or self.latest_time
        )

    def summary_text(self) -> str:
        if self.summary and self.summary.strip():
            return self.summary.strip()
        return summarize_cached_preference(self)


class ParsedPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0")
    timezone: str
    preferred_weekdays: list[Weekday] = Field(default_factory=list)
    disallowed_weekdays: list[Weekday] = Field(default_factory=list)
    preferred_time_ranges: list[TimeRangePreference] = Field(default_factory=list)
    disallowed_time_ranges: list[TimeRangePreference] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_overlap(self) -> "ParsedPreference":
        if set(self.preferred_weekdays) & set(self.disallowed_weekdays):
            raise ValueError("A weekday cannot be both preferred and disallowed")
        return self


def build_preferred_practice_time_range(preference: PreferredPracticeTime) -> TimeRangePreference:
    windows = {
        PreferredPracticeTime.EARLY_MORNING: ("08:00", "09:00"),
        PreferredPracticeTime.MID_MORNING: ("09:00", "11:00"),
        PreferredPracticeTime.LATE_MORNING: ("11:00", "12:00"),
    }
    start_local, end_local = windows[preference]
    return TimeRangePreference(start_local=start_local, end_local=end_local, weight=1.0)


def merge_parsed_preferences(
    base_preference: Optional[ParsedPreference],
    overlay_preference: Optional[ParsedPreference],
    timezone_name: str,
) -> Optional[ParsedPreference]:
    if base_preference is None:
        return overlay_preference
    if overlay_preference is None:
        return base_preference

    preferred_time_ranges = list(base_preference.preferred_time_ranges)
    for item in overlay_preference.preferred_time_ranges:
        if not any(existing.start_local == item.start_local and existing.end_local == item.end_local for existing in preferred_time_ranges):
            preferred_time_ranges.append(item)

    disallowed_time_ranges = list(base_preference.disallowed_time_ranges)
    for item in overlay_preference.disallowed_time_ranges:
        if not any(existing.start_local == item.start_local and existing.end_local == item.end_local for existing in disallowed_time_ranges):
            disallowed_time_ranges.append(item)

    return ParsedPreference.model_validate(
        {
            "schema_version": overlay_preference.schema_version or base_preference.schema_version,
            "timezone": timezone_name,
            "preferred_weekdays": _merge_weekdays(
                base_preference.preferred_weekdays,
                overlay_preference.preferred_weekdays,
            ),
            "disallowed_weekdays": _merge_weekdays(
                base_preference.disallowed_weekdays,
                overlay_preference.disallowed_weekdays,
            ),
            "preferred_time_ranges": [item.model_dump(mode="python") for item in preferred_time_ranges],
            "disallowed_time_ranges": [item.model_dump(mode="python") for item in disallowed_time_ranges],
            "notes": overlay_preference.notes or base_preference.notes,
        }
    )


def merge_preferred_practice_time(
    preference: Optional[ParsedPreference],
    timezone_name: str,
    preferred_practice_time: Optional[PreferredPracticeTime | str],
) -> Optional[ParsedPreference]:
    if preferred_practice_time is None:
        return preference

    normalized_preference = (
        preferred_practice_time
        if isinstance(preferred_practice_time, PreferredPracticeTime)
        else PreferredPracticeTime(preferred_practice_time)
    )
    overlay_preference = ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": timezone_name,
            "preferred_weekdays": [],
            "disallowed_weekdays": [],
            "preferred_time_ranges": [build_preferred_practice_time_range(normalized_preference).model_dump(mode="python")],
            "disallowed_time_ranges": [],
            "notes": None,
        }
    )
    return merge_parsed_preferences(preference, overlay_preference, timezone_name)


def merge_cached_practice_preference(
    preference: Optional[ParsedPreference],
    timezone_name: str,
    cached_payload: Optional[dict],
) -> Optional[ParsedPreference]:
    if not cached_payload:
        return preference
    try:
        cached = CachedPracticePreference.model_validate(cached_payload)
    except ValueError:
        return preference
    overlay_preference = cached_practice_preference_to_parsed_preference(cached, timezone_name)
    return merge_parsed_preferences(preference, overlay_preference, timezone_name)


def cached_practice_preference_to_parsed_preference(
    cached_preference: CachedPracticePreference,
    timezone_name: str,
) -> Optional[ParsedPreference]:
    if not cached_preference.is_useful():
        return None

    window_start = "08:00"
    window_end = "12:00"
    preferred_start = _max_time_str(cached_preference.earliest_time or window_start, window_start)
    preferred_end = _min_time_str(cached_preference.latest_time or window_end, window_end)

    preferred_time_ranges: list[dict[str, object]] = []
    if preferred_start < preferred_end:
        preferred_time_ranges.append(
            {
                "start_local": preferred_start,
                "end_local": preferred_end,
                "weight": 1.0,
            }
        )

    return ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": timezone_name,
            "preferred_weekdays": [_weekday_from_name(day_name).value for day_name in cached_preference.preferred_days],
            "disallowed_weekdays": [_weekday_from_name(day_name).value for day_name in cached_preference.avoid_days],
            "preferred_time_ranges": preferred_time_ranges,
            "disallowed_time_ranges": [],
            "notes": cached_preference.summary_text(),
        }
    )


def summarize_cached_preference(cached_preference: CachedPracticePreference) -> str:
    parts: list[str] = []
    if cached_preference.preferred_days:
        parts.append(f"prefers {', '.join(cached_preference.preferred_days)}")
    if cached_preference.avoid_days:
        parts.append(f"avoids {', '.join(cached_preference.avoid_days)}")
    if cached_preference.earliest_time:
        parts.append(f"never before {_humanize_time(cached_preference.earliest_time)}")
    if cached_preference.latest_time:
        parts.append(f"not after {_humanize_time(cached_preference.latest_time)}")
    if cached_preference.notes and cached_preference.notes.strip():
        parts.append(cached_preference.notes.strip())
    return ", ".join(parts)


def _merge_weekdays(base_weekdays: list[Weekday], overlay_weekdays: list[Weekday]) -> list[str]:
    merged: list[str] = []
    for weekday in [*base_weekdays, *overlay_weekdays]:
        if weekday.value not in merged:
            merged.append(weekday.value)
    return merged


def _normalize_day_name(value: object) -> str | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    aliases = {
        "mon": "Monday",
        "monday": "Monday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "tuesday": "Tuesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "thu": "Thursday",
        "thurs": "Thursday",
        "thursday": "Thursday",
        "fri": "Friday",
        "friday": "Friday",
        "sat": "Saturday",
        "saturday": "Saturday",
        "sun": "Sunday",
        "sunday": "Sunday",
    }
    return aliases.get(token)


def _weekday_from_name(day_name: str) -> Weekday:
    mapping = {
        "Monday": Weekday.MON,
        "Tuesday": Weekday.TUE,
        "Wednesday": Weekday.WED,
        "Thursday": Weekday.THU,
        "Friday": Weekday.FRI,
        "Saturday": Weekday.SAT,
        "Sunday": Weekday.SUN,
    }
    return mapping[day_name]


def _humanize_time(value: str) -> str:
    return datetime.strptime(value, "%H:%M").strftime("%-I:%M %p")


def _max_time_str(left: str, right: str) -> str:
    return left if left >= right else right


def _min_time_str(left: str, right: str) -> str:
    return left if left <= right else right
