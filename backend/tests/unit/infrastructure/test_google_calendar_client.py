from typing import Optional

from app.infrastructure.integrations.google_calendar.client import GoogleCalendarClient


class FakeResponse:
    def __init__(self, status_code: int, payload: Optional[dict] = None, text: str = "") -> None:
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
