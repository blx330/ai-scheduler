from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.availability import utcnow
from app.infrastructure.db.types import GUID


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"
    __table_args__ = (
        Index("ix_calendar_connection_user_provider", "user_id", "provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scaffold")
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_busy_calendar_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selected_write_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Window most recently covered by a successful busy sync. Without this, "has a
    # token" was treated as "we know this person's schedule", so a user who connected
    # Google but never synced was planned as free 24/7.
    busy_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    busy_synced_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    busy_synced_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="calendar_connections")
    busy_intervals = relationship("CalendarBusyInterval", back_populates="calendar_connection", cascade="all, delete-orphan")


class CalendarBusyInterval(Base):
    __tablename__ = "calendar_busy_intervals"
    __table_args__ = (
        Index("ix_calendar_busy_user_start", "user_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    calendar_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("calendar_connections.id", ondelete="CASCADE"),
        nullable=True,
    )
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="calendar_busy_intervals")
    calendar_connection = relationship("CalendarConnection", back_populates="busy_intervals")
