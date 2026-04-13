from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _validate_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include timezone information")
    return value


class PlanningRunCreate(BaseModel):
    event_ids: list[UUID]
    horizon_start: datetime
    horizon_end: datetime
    slot_step_minutes: int = 60
    room_id: Optional[UUID] = None

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def validate_datetimes(cls, value: datetime) -> datetime:
        return _validate_timezone_aware(value)

    @field_validator("slot_step_minutes")
    @classmethod
    def validate_slot_step(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Slot step minutes must be positive")
        return value

    @field_validator("event_ids")
    @classmethod
    def validate_event_ids(cls, value: list[UUID]) -> list[UUID]:
        if not value:
            raise ValueError("At least one event id is required")
        if len(set(value)) != len(value):
            raise ValueError("Event ids must be unique")
        return value


class PlanningExplanationReasonRead(BaseModel):
    code: str
    message: str
    score: Optional[float] = None
    missing_required_user_ids: list[UUID] = Field(default_factory=list)


class PlanningExplanationRead(BaseModel):
    summary: str
    reasons: list[PlanningExplanationReasonRead] = Field(default_factory=list)
    missing_required_user_ids: list[UUID] = Field(default_factory=list)


class PlanningParticipantStatusRead(BaseModel):
    user_id: UUID
    role: str
    available: bool


class PlanningRecommendationRead(BaseModel):
    id: Optional[UUID] = None
    dance_event_id: UUID
    dance_name: str
    session_index: int
    rank: int
    room_id: UUID
    start_at: datetime
    end_at: datetime
    total_score: float
    score_breakdown: dict[str, float]
    explanation: PlanningExplanationRead
    is_fallback: bool
    missing_required_user_ids: list[UUID] = Field(default_factory=list)
    optional_available_count: int
    participant_statuses: list[PlanningParticipantStatusRead] = Field(default_factory=list)


class PlanningSessionRecommendationGroupRead(BaseModel):
    dance_event_id: UUID
    dance_name: str
    session_index: int
    recommendations: list[PlanningRecommendationRead] = Field(default_factory=list)


class PlanningRunRead(BaseModel):
    id: UUID
    room_id: UUID
    status: str
    message: Optional[str] = None
    horizon_start: datetime
    horizon_end: datetime
    slot_step_minutes: int
    event_ids: list[UUID] = Field(default_factory=list)
    results: list[PlanningSessionRecommendationGroupRead] = Field(default_factory=list)


class PlanningRunConfirmRequest(BaseModel):
    result_ids: list[UUID]

    @field_validator("result_ids")
    @classmethod
    def validate_result_ids(cls, value: list[UUID]) -> list[UUID]:
        if not value:
            raise ValueError("At least one planning result id is required")
        if len(set(value)) != len(value):
            raise ValueError("Planning result ids must be unique")
        return value


class PracticeSessionRead(BaseModel):
    id: UUID
    dance_event_id: UUID
    session_index: int
    start_at: datetime
    end_at: datetime
    status: str
    room_id: UUID
    source_run_id: Optional[UUID] = None
    total_score: Optional[float] = None
    google_calendar_event_id: Optional[str] = None
    google_calendar_id: Optional[str] = None
    google_calendar_html_link: Optional[str] = None
    is_fallback: bool
    missing_required_user_ids: list[UUID] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    explanation: PlanningExplanationRead = Field(default_factory=lambda: PlanningExplanationRead(summary=""))


class PlanningRunConfirmResponse(BaseModel):
    planning_run_id: UUID
    confirmed_sessions: list[PracticeSessionRead] = Field(default_factory=list)


class CalendarBusyIntervalRead(BaseModel):
    id: UUID
    user_id: UUID
    start_at: datetime
    end_at: datetime


class CalendarOverviewRead(BaseModel):
    start_at: datetime
    end_at: datetime
    busy_intervals: list[CalendarBusyIntervalRead] = Field(default_factory=list)
    practice_sessions: list[PracticeSessionRead] = Field(default_factory=list)


class PracticeUnscheduleResponse(BaseModel):
    practice_id: UUID
    dance_event_id: UUID
    unscheduled: bool
    google_event_deleted: bool
    warning: Optional[str] = None
