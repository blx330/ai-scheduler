from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.availability import utcnow
from app.infrastructure.db.types import GUID


class DanceEvent(Base):
    __tablename__ = "dance_events"
    __table_args__ = (
        Index("ix_dance_event_deadline", "latest_schedule_at"),
        Index("ix_dance_event_organizer_created", "organizer_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    earliest_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    min_days_apart: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_schedule_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    required_session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unscheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    organizer = relationship("User", back_populates="organized_dance_events")
    participants = relationship("DanceEventParticipant", back_populates="dance_event", cascade="all, delete-orphan")
    practice_sessions = relationship("PracticeSession", back_populates="dance_event", cascade="all, delete-orphan")
    planning_results = relationship("PlanningRunResult", back_populates="dance_event")


class DanceEventParticipant(Base):
    __tablename__ = "dance_event_participants"
    __table_args__ = (
        UniqueConstraint("dance_event_id", "user_id", name="uq_dance_event_participant"),
        Index("ix_dance_event_participant_role", "dance_event_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    dance_event_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    dance_event = relationship("DanceEvent", back_populates="participants")
    user = relationship("User", back_populates="dance_event_participations")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    practice_sessions = relationship("PracticeSession", back_populates="room")
    planning_runs = relationship("PlanningRun", back_populates="room")
    planning_results = relationship("PlanningRunResult", back_populates="room")


class PlanningRun(Base):
    __tablename__ = "planning_runs"
    __table_args__ = (Index("ix_planning_run_created", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_step_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    event_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    room = relationship("Room", back_populates="planning_runs")
    results = relationship("PlanningRunResult", back_populates="planning_run", cascade="all, delete-orphan")
    practice_sessions = relationship("PracticeSession", back_populates="source_run")


class PlanningRunResult(Base):
    __tablename__ = "planning_run_results"
    __table_args__ = (
        UniqueConstraint("planning_run_id", "dance_event_id", "session_index", "rank", name="uq_planning_result_rank"),
        Index("ix_planning_result_event_session", "dance_event_id", "session_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    planning_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("planning_runs.id", ondelete="CASCADE"), nullable=False)
    dance_event_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    session_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_score: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    participant_statuses_json: Mapped[list] = mapped_column(JSON, nullable=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_required_user_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    planning_run = relationship("PlanningRun", back_populates="results")
    dance_event = relationship("DanceEvent", back_populates="planning_results")
    room = relationship("Room", back_populates="planning_results")


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index("ix_practice_session_event_session", "dance_event_id", "session_index"),
        Index("ix_practice_session_time", "start_at", "end_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    dance_event_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False)
    session_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    source_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("planning_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_calendar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_calendar_html_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_required_user_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    dance_event = relationship("DanceEvent", back_populates="practice_sessions")
    room = relationship("Room", back_populates="practice_sessions")
    source_run = relationship("PlanningRun", back_populates="practice_sessions")
