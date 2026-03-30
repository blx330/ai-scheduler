from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.availability import utcnow
from app.infrastructure.db.types import GUID


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    manual_availability_intervals = relationship(
        "ManualAvailabilityInterval",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preference_inputs = relationship("UserPreferenceInput", back_populates="user", cascade="all, delete-orphan")
    parsed_preferences = relationship("UserParsedPreference", back_populates="user", cascade="all, delete-orphan")
    organized_schedule_requests = relationship("ScheduleRequest", back_populates="organizer")
    schedule_request_participations = relationship("ScheduleRequestParticipant", back_populates="user")
    organized_dance_events = relationship("DanceEvent", back_populates="organizer")
    dance_event_participations = relationship("DanceEventParticipant", back_populates="user")
    calendar_connections = relationship("CalendarConnection", back_populates="user", cascade="all, delete-orphan")
    calendar_busy_intervals = relationship("CalendarBusyInterval", back_populates="user", cascade="all, delete-orphan")
