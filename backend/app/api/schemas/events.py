from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_timezone_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include timezone information")
    return value


class DanceEventParticipantCreate(BaseModel):
    user_id: UUID
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"required", "optional"}:
            raise ValueError("Participant role must be 'required' or 'optional'")
        return value


class DanceEventCreate(BaseModel):
    name: str
    description: str | None = None
    organizer_user_id: UUID
    duration_minutes: int
    earliest_start_date: date | None = None
    min_days_apart: int = 0
    latest_schedule_at: datetime
    required_session_count: int
    participants: list[DanceEventParticipantCreate]

    @field_validator("latest_schedule_at")
    @classmethod
    def validate_latest_schedule_at(cls, value: datetime) -> datetime:
        validated = _validate_timezone_aware(value)
        assert validated is not None
        return validated

    @field_validator("duration_minutes", "required_session_count", "min_days_apart")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Value must be zero or positive")
        return value

    @field_validator("duration_minutes", "required_session_count")
    @classmethod
    def validate_strict_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be positive")
        return value


class DanceEventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    organizer_user_id: UUID | None = None
    duration_minutes: int | None = None
    earliest_start_date: date | None = None
    min_days_apart: int | None = None
    latest_schedule_at: datetime | None = None
    required_session_count: int | None = None
    status: str | None = None
    participants: list[DanceEventParticipantCreate] | None = None

    @field_validator("latest_schedule_at")
    @classmethod
    def validate_latest_schedule_at(cls, value: datetime | None) -> datetime | None:
        return _validate_timezone_aware(value)

    @field_validator("duration_minutes", "required_session_count")
    @classmethod
    def validate_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Value must be positive")
        return value

    @field_validator("min_days_apart")
    @classmethod
    def validate_min_days_apart(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Minimum days apart must be zero or positive")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"unscheduled", "partially_scheduled", "scheduled", "completed", "archived"}:
            raise ValueError("Unsupported event status")
        return value


class DanceEventParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    role: str


class DanceEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    organizer_user_id: UUID
    duration_minutes: int
    earliest_start_date: date | None
    min_days_apart: int
    latest_schedule_at: datetime
    required_session_count: int
    confirmed_session_count: int
    remaining_session_count: int
    status: str
    participants: list[DanceEventParticipantRead] = Field(default_factory=list)
