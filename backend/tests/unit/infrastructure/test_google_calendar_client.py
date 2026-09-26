
from datetime import UTC, datetime, timedelta

import pytest
import requests

from app.infrastructure.integrations.google_calendar.client import GoogleCalendarClient

NOW = datetime(2026, 4, 1, 18, tzinfo=UTC)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


def test_raise_for_google_error_uses_google_message() -> None:
    response = FakeResponse(
        403,
        payload={
            "error": {
                "message": "Google Calendar API has not been used in project 123 before or it is disabled.",
            }
        },
    )

    try:
        GoogleCalendarClient._raise_for_google_error(response, "Google Calendar free/busy lookup")
    except RuntimeError as exc:
        assert str(exc) == (
            "Google Calendar free/busy lookup failed: "
            "Google Calendar API has not been used in project 123 before or it is disabled."
        )
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError for non-2xx Google response")


def test_raise_for_google_error_falls_back_to_response_text() -> None:
    response = FakeResponse(500, payload=None, text="upstream calendar error")

    try:
        GoogleCalendarClient._raise_for_google_error(response, "Google Calendar list")
    except RuntimeError as exc:
        assert str(exc) == "Google Calendar list failed: upstream calendar error"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError for non-2xx Google response")


class _RaisingRequests:
    """Every HTTP verb fails at the transport layer, the way `requests` does offline."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def _raise(self, *args, **kwargs):
        raise self.exc

    post = get = patch = delete = _raise


def _client(exc: Exception) -> GoogleCalendarClient:
    client = GoogleCalendarClient(client_id="id", client_secret="secret", redirect_uri="http://x/callback")
    client._requests = lambda: _RaisingRequests(exc)
    return client


@pytest.mark.parametrize(
    "call",
    [
        lambda client: client.exchange_code("code"),
        lambda client: client.refresh_access_token("refresh-token-secret"),
        lambda client: client.list_calendars("access-token-secret"),
        lambda client: client.get_free_busy("access-token-secret", ["primary"], NOW, NOW + timedelta(days=1)),
        lambda client: client.create_event("access-token-secret", "primary", "Practice", NOW, NOW + timedelta(hours=1), "UTC", []),
        lambda client: client.update_event("access-token-secret", "primary", "evt", NOW, NOW + timedelta(hours=1), "UTC"),
        lambda client: client.delete_event("access-token-secret", "primary", "evt"),
    ],
)
def test_network_failures_become_runtime_errors_without_leaking_urls_or_tokens(call) -> None:
    exc = requests.ConnectionError("HTTPSConnectionPool(host='oauth2.googleapis.com'): ?token=access-token-secret")
    with pytest.raises(RuntimeError) as excinfo:
        call(_client(exc))
    message = str(excinfo.value)
    assert "secret" not in message
    assert "http" not in message.lower()
    assert "googleapis" not in message
    assert excinfo.value.__cause__ is exc


def test_raise_for_google_error_keeps_the_oauth_error_code_when_error_is_a_string() -> None:
    response = FakeResponse(
        400, payload={"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
    )
    with pytest.raises(RuntimeError, match="invalid_grant") as excinfo:
        GoogleCalendarClient._raise_for_google_error(response, "Google OAuth token refresh")
    assert "Token has been expired or revoked." in str(excinfo.value)
