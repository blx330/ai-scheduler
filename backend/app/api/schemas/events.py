from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_timezone_aware(value: Optional[datetime]) -> Optional[datetime]:
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
    description: Optional[str] = None
    organizer_user_id: UUID
    duration_minutes: int
    latest_schedule_at: datetime
    required_session_count: int
    participants: list[DanceEventParticipantCreate]

    @field_validator("latest_schedule_at")
    @classmethod
    def validate_latest_schedule_at(cls, value: datetime) -> datetime:
        validated = _validate_timezone_aware(value)
        assert validated is not None
        return validated

    @field_validator("duration_minutes", "required_session_count")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be positive")
        return value


class DanceEventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    organizer_user_id: Optional[UUID] = None
    duration_minutes: Optional[int] = None
    latest_schedule_at: Optional[datetime] = None
    required_session_count: Optional[int] = None
    status: Optional[str] = None
    participants: Optional[list[DanceEventParticipantCreate]] = None

    @field_validator("latest_schedule_at")
    @classmethod
    def validate_latest_schedule_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _validate_timezone_aware(value)

    @field_validator("duration_minutes", "required_session_count")
    @classmethod
    def validate_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("Value must be positive")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
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
    description: Optional[str]
    organizer_user_id: UUID
    duration_minutes: int
    latest_schedule_at: datetime
    required_session_count: int
    confirmed_session_count: int
    remaining_session_count: int
    status: str
    participants: list[DanceEventParticipantRead] = Field(default_factory=list)
