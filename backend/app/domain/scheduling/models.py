from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Optional, Union
from uuid import UUID

from app.domain.availability.models import Interval
from app.domain.preferences.models import ParsedPreference


@dataclass(frozen=True)
class ParticipantContext:
    user_id: UUID
    role: str
    timezone: str
    effective_availability: list[Interval]
    preference: Optional[ParsedPreference] = None


@dataclass(frozen=True)
class ScheduleInput:
    schedule_request_id: UUID
    title: str
    organizer_timezone: str
    duration_minutes: int
    horizon_start: datetime
    horizon_end: datetime
    slot_step_minutes: int
    daily_window_start_local: Optional[time]
    daily_window_end_local: Optional[time]
    participants: list[ParticipantContext]


@dataclass(frozen=True)
class ScheduleSlot:
    start_at: datetime
    end_at: datetime

    @classmethod
    def from_start(cls, start_at: datetime, duration_minutes: int) -> "ScheduleSlot":
        return cls(start_at=start_at, end_at=start_at + timedelta(minutes=duration_minutes))


@dataclass(frozen=True)
class ScheduleParticipantStatus:
    user_id: UUID
    role: str
    available: bool

    def model_dump(self, mode: str = "python") -> dict[str, Union[str, bool]]:
        return {"user_id": str(self.user_id) if mode == "json" else self.user_id, "role": self.role, "available": self.available}


@dataclass
class ScheduleResult:
    rank: int
    start_at: datetime
    end_at: datetime
    total_score: float
    score_breakdown: dict[str, float]
    explanation: str
    required_participants_satisfied: bool
    optional_available_count: int
    participant_statuses: list[ScheduleParticipantStatus] = field(default_factory=list)


@dataclass
class ScheduleRunView:
    id: UUID
    schedule_request_id: UUID
    status: str
    results: list[ScheduleResult]
