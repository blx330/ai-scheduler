from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.preferences.models import PreferredPracticeTime


class UserCreate(BaseModel):
    display_name: str
    timezone: str
    email: Optional[str] = None
    preferred_practice_time: Optional[PreferredPracticeTime] = None
    preferred_practice_time_raw: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return value


class UserUpdate(BaseModel):
    preferred_practice_time: Optional[PreferredPracticeTime] = None
    preferred_practice_time_raw: Optional[str] = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    timezone: str
    email: Optional[str]
    preferred_practice_time: Optional[PreferredPracticeTime]
    preferred_practice_time_raw: Optional[str]
    preferred_practice_time_parsed: Optional[dict]
    preferred_practice_time_summary: Optional[str]
    created_at: datetime
