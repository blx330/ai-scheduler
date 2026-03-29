from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.common.enums import Weekday


class ScheduleRequestParticipantCreate(BaseModel):
    user_id: UUID
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"required", "optional"}:
            raise ValueError("Participant role must be 'required' or 'optional'")
        return value


class ScheduleRequestCreate(BaseModel):
    title: str
    organizer_user_id: UUID
    duration_minutes: int
    horizon_start: datetime
    horizon_end: datetime
    slot_step_minutes: int
    daily_window_start_local: Optional[time] = None
    daily_window_end_local: Optional[time] = None
    preferred_weekdays: list[Weekday] = Field(default_factory=list)
    preferred_time_range_start_local: Optional[time] = None
    preferred_time_range_end_local: Optional[time] = None
    participants: list[ScheduleRequestParticipantCreate]

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_daily_window(self) -> "ScheduleRequestCreate":
        if (self.daily_window_start_local is None) != (self.daily_window_end_local is None):
            raise ValueError("Daily scheduling window requires both start and end")
        if (
            self.daily_window_start_local is not None
            and self.daily_window_end_local is not None
            and self.daily_window_start_local >= self.daily_window_end_local
        ):
            raise ValueError("Daily scheduling window start must be before end")
        if (self.preferred_time_range_start_local is None) != (self.preferred_time_range_end_local is None):
            raise ValueError("Preferred time range requires both start and end")
        if (
            self.preferred_time_range_start_local is not None
            and self.preferred_time_range_end_local is not None
            and self.preferred_time_range_start_local >= self.preferred_time_range_end_local
        ):
            raise ValueError("Preferred time range start must be before end")
        return self


class ScheduleRequestParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    role: str


class ScheduleRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    organizer_user_id: UUID
    duration_minutes: int
    horizon_start: datetime
    horizon_end: datetime
    slot_step_minutes: int
    daily_window_start_local: Optional[time]
    daily_window_end_local: Optional[time]
    preferred_weekdays: list[Weekday] = Field(default_factory=list)
    preferred_time_range_start_local: Optional[time]
    preferred_time_range_end_local: Optional[time]
    status: str
    participants: list[ScheduleRequestParticipantRead] = Field(default_factory=list)


class SlotParticipantStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    role: str
    available: bool


class ScheduleRunResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    start_at: datetime
    end_at: datetime
    total_score: float
    score_breakdown: dict[str, float]
    explanation: str
    required_participants_satisfied: bool
    optional_available_count: int
    participant_statuses: list[SlotParticipantStatusRead]


class ScheduleRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_request_id: UUID
    status: str
    results: list[ScheduleRunResultRead]


class ScheduleRunConfirmRequest(BaseModel):
    rank: int
    calendar_id: Optional[str] = None


class CreatedEventRead(BaseModel):
    event_id: str
    html_link: Optional[str] = None
    status: str
    calendar_id: str
    start_at: datetime
    end_at: datetime
