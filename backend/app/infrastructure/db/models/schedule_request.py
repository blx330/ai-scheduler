from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.availability import utcnow
from app.infrastructure.db.types import GUID


class ScheduleRequest(Base):
    __tablename__ = "schedule_requests"
    __table_args__ = (Index("ix_schedule_request_organizer_created", "organizer_user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_step_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_window_start_local: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    daily_window_end_local: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    preferred_weekdays_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_time_range_start_local: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    preferred_time_range_end_local: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    organizer = relationship("User", back_populates="organized_schedule_requests")
    participants = relationship("ScheduleRequestParticipant", back_populates="schedule_request", cascade="all, delete-orphan")
    runs = relationship("ScheduleRun", back_populates="schedule_request", cascade="all, delete-orphan")


class ScheduleRequestParticipant(Base):
    __tablename__ = "schedule_request_participants"
    __table_args__ = (
        UniqueConstraint("schedule_request_id", "user_id", name="uq_schedule_request_participant"),
        Index("ix_schedule_request_participant_request_role", "schedule_request_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    schedule_request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schedule_requests.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    schedule_request = relationship("ScheduleRequest", back_populates="participants")
    user = relationship("User", back_populates="schedule_request_participations")


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (Index("ix_schedule_run_request_created", "schedule_request_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    schedule_request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schedule_requests.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    schedule_request = relationship("ScheduleRequest", back_populates="runs")
    results = relationship("ScheduleRunResult", back_populates="schedule_run", cascade="all, delete-orphan")


class ScheduleRunResult(Base):
    __tablename__ = "schedule_run_results"
    __table_args__ = (
        UniqueConstraint("schedule_run_id", "rank", name="uq_schedule_run_rank"),
        UniqueConstraint("schedule_run_id", "start_at", "end_at", name="uq_schedule_run_slot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    schedule_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schedule_runs.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_score: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)
    required_participants_satisfied: Mapped[bool] = mapped_column(nullable=False)
    optional_available_count: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_statuses_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    schedule_run = relationship("ScheduleRun", back_populates="results")
