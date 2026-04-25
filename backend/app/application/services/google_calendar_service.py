from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.common.datetime_utils import ensure_utc
from app.infrastructure.config import Settings
from app.infrastructure.db.models import (
    CalendarBusyInterval,
    CalendarConnection,
    DanceEvent,
    DanceEventParticipant,
    PracticeSession,
    User,
)
from app.infrastructure.integrations.google_calendar.client import (
    GOOGLE_SCOPE_CALENDAR,
    GOOGLE_SCOPE_CALENDAR_FREEBUSY,
    GOOGLE_SCOPE_CALENDAR_READONLY,
    GoogleCalendarProvider,
    GoogleCalendarSummary,
    GoogleCreatedEvent,
)

logger = logging.getLogger(__name__)

GOOGLE_READ_SCOPES = frozenset(
    {
        GOOGLE_SCOPE_CALENDAR,
        GOOGLE_SCOPE_CALENDAR_FREEBUSY,
        GOOGLE_SCOPE_CALENDAR_READONLY,
    }
)
GOOGLE_WRITE_SCOPES = frozenset({GOOGLE_SCOPE_CALENDAR})


@dataclass(frozen=True)
class GoogleConnectionStatus:
    user_id: UUID
    connected: bool
    status: str
    account_email: str | None
    selected_busy_calendar_ids: list[str]
    selected_write_calendar_id: str | None
    token_expires_at: datetime | None


@dataclass(frozen=True)
class BusySyncResult:
    user_id: UUID
    synced_interval_count: int
    calendar_ids: list[str]


class GoogleCalendarService:
    def __init__(self, db: Session, settings: Settings, client: GoogleCalendarProvider) -> None:
        self.db = db
        self.settings = settings
        self.client = client

    def begin_oauth(self, user_id: UUID) -> str:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        state = _sign_state({"user_id": str(user_id)}, self.settings.oauth_state_secret)
        return self.client.build_authorization_url(state)

    def complete_oauth(self, code: str, state: str) -> str:
        payload = _verify_state(state, self.settings.oauth_state_secret)
        user_id = UUID(payload["user_id"])
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")

        tokens = self.client.exchange_code(code)
        connection = self._get_or_create_connection(user_id)
        connection.provider = "google"
        connection.status = "connected"
        connection.access_token = tokens.access_token
        connection.refresh_token = tokens.refresh_token or connection.refresh_token
        connection.token_expires_at = ensure_utc(tokens.expires_at)
        connection.scopes = tokens.scope
        connection.account_email = user.email
        self.db.add(connection)
        self.db.commit()

        query = urlencode({"google_connected": "1", "user_id": str(user_id)})
        return f"{self.settings.frontend_url.rstrip('/')}/?{query}"

    def get_connection_status(self, user_id: UUID) -> GoogleConnectionStatus:
        connection = self._find_connection(user_id)
        if connection is None:
            return GoogleConnectionStatus(
                user_id=user_id,
                connected=False,
                status="disconnected",
                account_email=None,
                selected_busy_calendar_ids=[],
                selected_write_calendar_id=None,
                token_expires_at=None,
            )
        connected = bool(connection.refresh_token or connection.access_token)
        status = connection.status
        if connected and not _has_any_scope(connection.scopes, GOOGLE_READ_SCOPES):
            connected = False
            status = "reauthorization_required"
        return GoogleConnectionStatus(
            user_id=user_id,
            connected=connected,
            status=status,
            account_email=connection.account_email,
            selected_busy_calendar_ids=list(connection.selected_busy_calendar_ids_json or []),
            selected_write_calendar_id=connection.selected_write_calendar_id,
            token_expires_at=connection.token_expires_at,
        )

    def list_calendars(self, user_id: UUID) -> list[GoogleCalendarSummary]:
        connection = self._require_connection(user_id)
        self._ensure_connection_has_scope(
            connection,
            GOOGLE_READ_SCOPES,
            "Google Calendar connection is missing read access. Reconnect Google and grant calendar access.",
        )
        access_token = self._ensure_access_token(connection)
        return self.client.list_calendars(access_token)

    def save_calendar_selection(
        self,
        user_id: UUID,
        busy_calendar_ids: list[str],
        write_calendar_id: str | None,
    ) -> GoogleConnectionStatus:
        connection = self._require_connection(user_id)
        available_ids = {calendar.id for calendar in self.list_calendars(user_id)}
        if busy_calendar_ids and not set(busy_calendar_ids).issubset(available_ids):
            raise ValueError("One or more busy calendars are not available")
        if write_calendar_id is not None and write_calendar_id not in available_ids:
            raise ValueError("Write calendar is not available")

        connection.selected_busy_calendar_ids_json = busy_calendar_ids
        connection.selected_write_calendar_id = write_calendar_id
        connection.status = "configured"
        self.db.add(connection)
        self.db.commit()
        logger.info(
            "Saved Google calendar selection for user %s with %d busy calendars and write calendar %s",
            user_id,
            len(busy_calendar_ids),
            write_calendar_id or "primary",
        )
        return self.get_connection_status(user_id)

    def sync_busy_intervals(self, user_id: UUID, horizon_start: datetime, horizon_end: datetime) -> BusySyncResult:
        connection = self._require_connection(user_id)
        self._ensure_connection_has_scope(
            connection,
            GOOGLE_READ_SCOPES,
            "Google Calendar connection is missing free/busy access. Reconnect Google and grant calendar access.",
        )
        calendar_ids = list(connection.selected_busy_calendar_ids_json or [])
        if not calendar_ids:
            calendar_ids = [connection.selected_write_calendar_id or "primary"]

        start_at = ensure_utc(horizon_start)
        end_at = ensure_utc(horizon_end)
        if end_at <= start_at:
            raise ValueError("Horizon end must be after horizon start")

        access_token = self._ensure_access_token(connection)
        busy_intervals = self.client.get_free_busy(
            access_token=access_token,
            calendar_ids=calendar_ids,
            time_min=start_at,
            time_max=end_at,
        )

        existing = list(
            self.db.scalars(
                select(CalendarBusyInterval)
                .where(CalendarBusyInterval.user_id == user_id)
                .where(CalendarBusyInterval.calendar_connection_id == connection.id)
                .where(CalendarBusyInterval.end_at > start_at)
                .where(CalendarBusyInterval.start_at < end_at)
            )
        )
        for interval in existing:
            self.db.delete(interval)

        for interval in busy_intervals:
            self.db.add(
                CalendarBusyInterval(
                    user_id=user_id,
                    calendar_connection_id=connection.id,
                    start_at=interval.start_at,
                    end_at=interval.end_at,
                )
            )

        self.db.commit()
        logger.info(
            "Synced %d Google busy intervals for user %s across calendars %s between %s and %s",
            len(busy_intervals),
            user_id,
            calendar_ids,
            start_at.isoformat(),
            end_at.isoformat(),
        )
        return BusySyncResult(
            user_id=user_id,
            synced_interval_count=len(busy_intervals),
            calendar_ids=calendar_ids,
        )

    def create_event_for_practice_session(
        self,
        practice_session_id: UUID,
        calendar_id: str | None = None,
    ) -> GoogleCreatedEvent:
        practice_session = self.db.scalars(
            select(PracticeSession)
            .where(PracticeSession.id == practice_session_id)
            .options(
                selectinload(PracticeSession.dance_event).selectinload(DanceEvent.organizer),
                selectinload(PracticeSession.dance_event)
                .selectinload(DanceEvent.participants)
                .selectinload(DanceEventParticipant.user),
            )
        ).one_or_none()
        if practice_session is None:
            raise ValueError("Practice session not found")

        dance_event = practice_session.dance_event
        connection = self._require_connection(dance_event.organizer_user_id)
        self._ensure_connection_has_scope(
            connection,
            GOOGLE_WRITE_SCOPES,
            "Google Calendar connection is missing write access. Reconnect Google and grant calendar access.",
        )
        access_token = self._ensure_access_token(connection)
        target_calendar_id = calendar_id or connection.selected_write_calendar_id or "primary"

        attendee_emails = []
        for participant in dance_event.participants:
            if participant.user_id == dance_event.organizer_user_id:
                continue
            if participant.user and participant.user.email:
                attendee_emails.append(participant.user.email)

        created_event = self.client.create_event(
            access_token=access_token,
            calendar_id=target_calendar_id,
            title=f"{dance_event.name} Practice {practice_session.session_index}",
            start_at=ensure_utc(practice_session.start_at),
            end_at=ensure_utc(practice_session.end_at),
            timezone_name=dance_event.organizer.timezone,
            attendee_emails=attendee_emails,
            description="Created by the AI scheduler demo app.",
        )

        practice_session.google_calendar_event_id = created_event.event_id
        practice_session.google_calendar_id = created_event.calendar_id
        practice_session.google_calendar_html_link = created_event.html_link
        self.db.add(practice_session)
        self.db.commit()
        self.db.refresh(practice_session)
        return created_event

    def delete_event_for_practice_session(self, practice_session_id: UUID) -> bool:
        practice_session = self.db.scalars(
            select(PracticeSession)
            .where(PracticeSession.id == practice_session_id)
            .options(selectinload(PracticeSession.dance_event).selectinload(DanceEvent.organizer))
        ).one_or_none()
        if practice_session is None:
            raise ValueError("Practice session not found")
        if not practice_session.google_calendar_event_id:
            return False

        connection = self._require_connection(practice_session.dance_event.organizer_user_id)
        self._ensure_connection_has_scope(
            connection,
            GOOGLE_WRITE_SCOPES,
            "Google Calendar connection is missing write access. Reconnect Google and grant calendar access.",
        )
        access_token = self._ensure_access_token(connection)
        target_calendar_id = practice_session.google_calendar_id or connection.selected_write_calendar_id or "primary"
        self.client.delete_event(
            access_token=access_token,
            calendar_id=target_calendar_id,
            event_id=practice_session.google_calendar_event_id,
        )
        return True

    def _ensure_access_token(self, connection: CalendarConnection) -> str:
        if connection.access_token and connection.token_expires_at:
            if ensure_utc(connection.token_expires_at) > datetime.now(timezone.utc):
                return connection.access_token
        if not connection.refresh_token:
            raise ValueError("Google Calendar connection is missing a refresh token")

        tokens = self.client.refresh_access_token(connection.refresh_token)
        connection.access_token = tokens.access_token
        connection.token_expires_at = ensure_utc(tokens.expires_at)
        connection.scopes = tokens.scope or connection.scopes
        self.db.add(connection)
        self.db.commit()
        return tokens.access_token

    def _find_connection(self, user_id: UUID) -> Optional[CalendarConnection]:
        statement = (
            select(CalendarConnection)
            .where(CalendarConnection.user_id == user_id)
            .where(CalendarConnection.provider == "google")
            .order_by(CalendarConnection.created_at.desc())
        )
        return self.db.scalars(statement).first()

    def _require_connection(self, user_id: UUID) -> CalendarConnection:
        connection = self._find_connection(user_id)
        if connection is None:
            raise ValueError("User does not have a Google Calendar connection")
        return connection

    def _get_or_create_connection(self, user_id: UUID) -> CalendarConnection:
        connection = self._find_connection(user_id)
        if connection is not None:
            return connection
        return CalendarConnection(user_id=user_id, provider="google", status="connected")

    @staticmethod
    def _ensure_connection_has_scope(
        connection: CalendarConnection,
        required_scopes: frozenset[str],
        error_message: str,
    ) -> None:
        if _has_any_scope(connection.scopes, required_scopes):
            return
        raise ValueError(error_message)


def _sign_state(payload: dict[str, str], secret: str) -> str:
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{encoded_payload}.{encoded_signature}"


def _verify_state(token: str, secret: str) -> dict[str, str]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid OAuth state") from exc

    expected_signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    actual_signature = _decode_base64(encoded_signature)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("Invalid OAuth state")
    return json.loads(_decode_base64(encoded_payload).decode("utf-8"))


def _decode_base64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _has_any_scope(scopes: str | None, required_scopes: frozenset[str]) -> bool:
    if not scopes:
        return False
    granted_scopes = {scope.strip() for scope in scopes.split() if scope.strip()}
    return bool(granted_scopes & required_scopes)
