from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from app.domain.availability.models import Interval
from app.domain.preferences.models import ParsedPreference


@dataclass(frozen=True)
class BookedInterval:
    """Time a participant is already committed to another practice."""

    interval: Interval
    label: str


@dataclass(frozen=True)
class ParticipantContext:
    user_id: UUID
    role: str
    timezone: str
    # What the planner schedules against: declared free time minus busy time minus
    # other practices. The raw pieces below exist only so an unavailable status can
    # say *why* (see ScheduleParticipantStatus.reason).
    effective_availability: list[Interval]
    preference: ParsedPreference | None = None
    declared_availability: list[Interval] = field(default_factory=list)
    busy_intervals: list[Interval] = field(default_factory=list)
    booked_intervals: list[BookedInterval] = field(default_factory=list)


@dataclass(frozen=True)
class ScheduleSlot:
    start_at: datetime
    end_at: datetime

    @classmethod
    def from_start(cls, start_at: datetime, duration_minutes: int) -> ScheduleSlot:
        return cls(start_at=start_at, end_at=start_at + timedelta(minutes=duration_minutes))


# Why a participant cannot attend a slot. Every "missing" flag the API shows is
# backed by one of these, so it can always be checked against real data.
UNAVAILABLE_BOOKED = "booked"  # already in another practice at that time
UNAVAILABLE_BUSY = "busy"  # a calendar busy interval overlaps
UNAVAILABLE_NOT_DECLARED = "not_declared"  # never marked free at that time


@dataclass(frozen=True)
class ScheduleParticipantStatus:
    user_id: UUID
    role: str
    available: bool
    reason: str | None = None
    detail: str | None = None

    def model_dump(self, mode: str = "python") -> dict[str, str | bool | None]:
        return {
            "user_id": str(self.user_id) if mode == "json" else self.user_id,
            "role": self.role,
            "available": self.available,
            "reason": self.reason,
            "detail": self.detail,
        }


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
