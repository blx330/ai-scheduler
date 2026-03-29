from __future__ import annotations

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
