from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.preferences.models import PreferredPracticeTime


class UserCreate(BaseModel):
    display_name: str
    timezone: str
    email: str | None = None
    preferred_practice_time: PreferredPracticeTime | None = None
    preferred_practice_time_raw: str | None = None

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
    preferred_practice_time_raw: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    timezone: str
    email: str | None
    preferred_practice_time: PreferredPracticeTime | None
    preferred_practice_time_raw: str | None
    preferred_practice_time_parsed: dict | None
    preferred_practice_time_summary: str | None
    created_at: datetime
