from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.preferences.models import CachedPracticePreference, PreferredPracticeTime
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.availability import utcnow
from app.infrastructure.db.types import GUID


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    preferred_practice_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_practice_time_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_practice_time_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    manual_availability_intervals = relationship(
        "ManualAvailabilityInterval",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    organized_dance_events = relationship("DanceEvent", back_populates="organizer")
    dance_event_participations = relationship("DanceEventParticipant", back_populates="user")
    calendar_connections = relationship("CalendarConnection", back_populates="user", cascade="all, delete-orphan")
    calendar_busy_intervals = relationship("CalendarBusyInterval", back_populates="user", cascade="all, delete-orphan")

    @property
    def preferred_practice_time_summary(self) -> str | None:
        if self.preferred_practice_time_parsed:
            try:
                cached = CachedPracticePreference.model_validate(self.preferred_practice_time_parsed)
            except ValueError:
                cached = None
            if cached is not None:
                summary = cached.summary_text()
                if summary:
                    return f"Understood: {summary}"
        if self.preferred_practice_time_raw:
            return "Could not parse preferences — raw text saved, defaults will be used."
        if self.preferred_practice_time:
            label = {
                PreferredPracticeTime.MORNING.value: "morning (8 AM-12 PM)",
                PreferredPracticeTime.AFTERNOON.value: "afternoon (12-4 PM)",
                PreferredPracticeTime.EVENING.value: "evening (4-8 PM)",
                PreferredPracticeTime.LATE_NIGHT.value: "late night (8 PM-12 AM)",
            }.get(self.preferred_practice_time)
            if label:
                return f"Understood: prefers {label}"
        return None
