from __future__ import annotations

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class GoogleOAuthStartRequest(BaseModel):
    user_id: UUID


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: str


class GoogleCalendarSummaryRead(BaseModel):
    id: str
    summary: str
    primary: bool
    access_role: str
    time_zone: Optional[str] = None


class GoogleCalendarConnectionRead(BaseModel):
    user_id: UUID
    connected: bool
    status: str
    account_email: Optional[str] = None
    selected_busy_calendar_ids: list[str]
    selected_write_calendar_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class GoogleCalendarSelectionUpdate(BaseModel):
    busy_calendar_ids: list[str]
    write_calendar_id: Optional[str] = None


class GoogleBusySyncRequest(BaseModel):
    horizon_start: datetime
    horizon_end: datetime

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include timezone information")
        return value


class GoogleBusySyncResponse(BaseModel):
    user_id: UUID
    synced_interval_count: int
    calendar_ids: list[str]
