from __future__ import annotations

from datetime import date, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.schemas.planning import PlanningRunRead
from app.domain.common.enums import Weekday
from app.domain.scheduling.requests import MAX_SESSIONS_PER_REQUEST, SchedulingRequest

MAX_REQUEST_TEXT_CHARS = 1_000


class SchedulingRequestParseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REQUEST_TEXT_CHARS)]


class ProposalParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    role: Literal["required", "optional"]


class SchedulingProposal(BaseModel):
    """Everything confirm needs, by id. The server re-validates all of it on confirm;
    the client echoing it back proves nothing."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    session_count: int = Field(ge=1, le=MAX_SESSIONS_PER_REQUEST)
    earliest_date: date | None
    latest_date: date
    min_days_apart: int = Field(ge=0)
    participants: list[ProposalParticipant] = Field(min_length=1)
    allowed_weekdays: list[Weekday]
    blocked_weekdays: list[Weekday]
    earliest_start_time: time | None
    latest_end_time: time | None
    room_id: UUID | None


class ReviewEvent(BaseModel):
    id: UUID
    name: str
    organizer_timezone: str
    duration_minutes: int
    confirmed_session_count: int


class ReviewRoom(BaseModel):
    id: UUID
    name: str


class ReviewParticipant(BaseModel):
    user_id: UUID
    display_name: str
    role: Literal["required", "optional"]
    change: Literal["added", "role_changed", "unchanged"]


class FieldChange(BaseModel):
    field: str
    label: str
    before: str
    after: str


class SchedulingRequestReview(BaseModel):
    request_text: str
    parsed: SchedulingRequest
    proposal: SchedulingProposal
    event: ReviewEvent
    room: ReviewRoom | None
    participants: list[ReviewParticipant]
    changes: list[FieldChange]
    sessions_to_plan: int
    notes: list[str]


class SchedulingRequestConfirmResponse(BaseModel):
    event_id: UUID
    planning_run: PlanningRunRead
