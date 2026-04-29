from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Optional, Protocol
from urllib.parse import quote, urlencode


GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
GOOGLE_EVENTS_URL_TEMPLATE = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
GOOGLE_SCOPE_CALENDAR = "https://www.googleapis.com/auth/calendar"
GOOGLE_SCOPE_CALENDAR_FREEBUSY = "https://www.googleapis.com/auth/calendar.freebusy"
GOOGLE_SCOPE_CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
GOOGLE_SCOPES = [
    GOOGLE_SCOPE_CALENDAR,
]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoogleOAuthTokens:
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    scope: Optional[str] = None
    token_type: str = "Bearer"


@dataclass(frozen=True)
class GoogleCalendarSummary:
    id: str
    summary: str
    primary: bool
    access_role: str
    time_zone: Optional[str]


@dataclass(frozen=True)
class GoogleBusyInterval:
    calendar_id: str
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class GoogleCreatedEvent:
    event_id: str
    html_link: Optional[str]
    status: str
    calendar_id: str
    start_at: datetime
    end_at: datetime


class GoogleCalendarProvider(Protocol):
    def build_authorization_url(self, state: str) -> str:
        ...

    def exchange_code(self, code: str) -> GoogleOAuthTokens:
        ...

    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthTokens:
        ...

    def list_calendars(self, access_token: str) -> list[GoogleCalendarSummary]:
        ...

    def get_free_busy(
        self,
        access_token: str,
        calendar_ids: list[str],
        time_min: datetime,
        time_max: datetime,
    ) -> list[GoogleBusyInterval]:
        ...

    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        title: str,
        start_at: datetime,
        end_at: datetime,
        timezone_name: str,
        attendee_emails: list[str],
        description: Optional[str] = None,
    ) -> GoogleCreatedEvent:
        ...

    def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        ...


class GoogleCalendarClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> GoogleOAuthTokens:
        response = self._requests().post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        self._raise_for_google_error(response, "Google OAuth token exchange")
        return self._build_tokens(response.json())

    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthTokens:
        response = self._requests().post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        self._raise_for_google_error(response, "Google OAuth token refresh")
        payload = response.json()
        payload["refresh_token"] = refresh_token
        return self._build_tokens(payload)

    def list_calendars(self, access_token: str) -> list[GoogleCalendarSummary]:
        response = self._requests().get(
            GOOGLE_CALENDAR_LIST_URL,
            headers=self._auth_headers(access_token),
            params={"minAccessRole": "reader"},
            timeout=30,
        )
        self._raise_for_google_error(response, "Google Calendar list")
        payload = response.json()
        return [
            GoogleCalendarSummary(
                id=item["id"],
                summary=item.get("summaryOverride") or item.get("summary") or item["id"],
                primary=bool(item.get("primary")),
                access_role=item.get("accessRole", ""),
                time_zone=item.get("timeZone"),
            )
            for item in payload.get("items", [])
        ]

    def get_free_busy(
        self,
        access_token: str,
        calendar_ids: list[str],
        time_min: datetime,
        time_max: datetime,
    ) -> list[GoogleBusyInterval]:
        response = self._requests().post(
            GOOGLE_FREEBUSY_URL,
            headers=self._auth_headers(access_token),
            json={
                "timeMin": time_min.astimezone(timezone.utc).isoformat(),
                "timeMax": time_max.astimezone(timezone.utc).isoformat(),
                "items": [{"id": calendar_id} for calendar_id in calendar_ids],
            },
            timeout=30,
        )
        self._raise_for_google_error(response, "Google Calendar free/busy lookup")
        payload = response.json()
        results: list[GoogleBusyInterval] = []
        for calendar_id, details in payload.get("calendars", {}).items():
            for interval in details.get("busy", []):
                results.append(
                    GoogleBusyInterval(
                        calendar_id=calendar_id,
                        start_at=_parse_google_datetime(interval["start"]),
                        end_at=_parse_google_datetime(interval["end"]),
                    )
                )
        return results

    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        title: str,
        start_at: datetime,
        end_at: datetime,
        timezone_name: str,
        attendee_emails: list[str],
        description: Optional[str] = None,
    ) -> GoogleCreatedEvent:
        encoded_calendar_id = quote(calendar_id, safe="")
        response = self._requests().post(
            GOOGLE_EVENTS_URL_TEMPLATE.format(calendar_id=encoded_calendar_id),
            headers=self._auth_headers(access_token),
            json={
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": start_at.astimezone(timezone.utc).isoformat(),
                    "timeZone": timezone_name,
                },
                "end": {
                    "dateTime": end_at.astimezone(timezone.utc).isoformat(),
                    "timeZone": timezone_name,
                },
                "attendees": [{"email": email} for email in attendee_emails],
            },
            timeout=30,
        )
        self._raise_for_google_error(response, "Google Calendar event creation")
        payload = response.json()
        return GoogleCreatedEvent(
            event_id=payload["id"],
            html_link=payload.get("htmlLink"),
            status=payload.get("status", "confirmed"),
            calendar_id=calendar_id,
            start_at=_parse_google_datetime(payload["start"]["dateTime"]),
            end_at=_parse_google_datetime(payload["end"]["dateTime"]),
        )

    def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        encoded_calendar_id = quote(calendar_id, safe="")
        encoded_event_id = quote(event_id, safe="")
        response = self._requests().delete(
            f"{GOOGLE_EVENTS_URL_TEMPLATE.format(calendar_id=encoded_calendar_id)}/{encoded_event_id}",
            headers=self._auth_headers(access_token),
            timeout=30,
        )
        self._raise_for_google_error(response, "Google Calendar event deletion")

    @staticmethod
    def _requests():
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests must be installed to use Google Calendar integration") from exc
        return requests

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_tokens(payload: dict[str, Any]) -> GoogleOAuthTokens:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 3600)))
        return GoogleOAuthTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )

    @staticmethod
    def _raise_for_google_error(response: Any, operation: str) -> None:
        if 200 <= int(response.status_code) < 300:
            return
        message = GoogleCalendarClient._extract_google_error_message(response)
        raise RuntimeError(f"{operation} failed: {message}")

    @staticmethod
    def _extract_google_error_message(response: Any) -> str:
        default_message = f"HTTP {response.status_code}"
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                message = error_payload.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()

                for detail in error_payload.get("details", []):
                    if isinstance(detail, dict):
                        detail_message = detail.get("message")
                        if isinstance(detail_message, str) and detail_message.strip():
                            return detail_message.strip()

        response_text = getattr(response, "text", "")
        if isinstance(response_text, str) and response_text.strip():
            return response_text.strip()
        return default_message


class NoopGoogleCalendarProvider:
    def __init__(self, missing_env_vars: list[str]) -> None:
        self.missing_env_vars = missing_env_vars

    def _raise_unconfigured(self, operation: str) -> None:
        missing_vars = ", ".join(self.missing_env_vars)
        logger.warning(
            "Google Calendar OAuth noop provider called for operation '%s'. Missing env vars: [%s]",
            operation,
            missing_vars,
        )
        raise RuntimeError(
            f"Google Calendar OAuth not configured for operation '{operation}'. "
            f"Missing env vars: [{missing_vars}]"
        )

    def build_authorization_url(self, state: str) -> str:
        self._raise_unconfigured("build_authorization_url")

    def exchange_code(self, code: str) -> GoogleOAuthTokens:
        self._raise_unconfigured("exchange_code")

    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthTokens:
        self._raise_unconfigured("refresh_access_token")

    def list_calendars(self, access_token: str) -> list[GoogleCalendarSummary]:
        self._raise_unconfigured("list_calendars")

    def get_free_busy(
        self,
        access_token: str,
        calendar_ids: list[str],
        time_min: datetime,
        time_max: datetime,
    ) -> list[GoogleBusyInterval]:
        self._raise_unconfigured("get_free_busy")

    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        title: str,
        start_at: datetime,
        end_at: datetime,
        timezone_name: str,
        attendee_emails: list[str],
        description: Optional[str] = None,
    ) -> GoogleCreatedEvent:
        self._raise_unconfigured("create_event")

    def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        self._raise_unconfigured("delete_event")


def build_google_calendar_client(
    client_id: Optional[str],
    client_secret: Optional[str],
    redirect_uri: Optional[str],
) -> GoogleCalendarProvider:
    missing_env_vars = []
    if not client_id or not client_id.strip():
        missing_env_vars.append("GOOGLE_CLIENT_ID")
    if not client_secret or not client_secret.strip():
        missing_env_vars.append("GOOGLE_CLIENT_SECRET")
    if not redirect_uri or not redirect_uri.strip():
        missing_env_vars.append("GOOGLE_REDIRECT_URI")
    if not missing_env_vars:
        return GoogleCalendarClient(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    logger.warning(
        "Google Calendar OAuth not configured. Missing env vars: [%s]. Calendar sync will be disabled.",
        ", ".join(missing_env_vars),
    )
    return NoopGoogleCalendarProvider(missing_env_vars=missing_env_vars)


def _parse_google_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
