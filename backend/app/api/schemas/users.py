from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.domain.preferences.models import PreferredPracticeTime

MAX_PREFERENCE_TEXT_CHARS = 1_000
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class UserCreate(BaseModel):
    display_name: DisplayName
    timezone: str
    email: str | None = Field(default=None, max_length=255)
    preferred_practice_time: PreferredPracticeTime | None = None
    preferred_practice_time_raw: str | None = Field(default=None, max_length=MAX_PREFERENCE_TEXT_CHARS)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return value


class UserUpdate(BaseModel):
    preferred_practice_time: PreferredPracticeTime | None = None
    preferred_practice_time_raw: str | None = Field(default=None, max_length=MAX_PREFERENCE_TEXT_CHARS)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    timezone: str
    email: str | None
    role: str
    preferred_practice_time: PreferredPracticeTime | None
    preferred_practice_time_raw: str | None
    preferred_practice_time_parsed: dict | None
    preferred_practice_time_summary: str | None
    created_at: datetime
