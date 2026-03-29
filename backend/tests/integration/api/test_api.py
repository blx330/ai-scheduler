from datetime import datetime, timezone
from datetime import timedelta
from typing import Optional

from app.infrastructure.db.models import CalendarBusyInterval, CalendarConnection
from app.infrastructure.integrations.google_calendar.client import GoogleCreatedEvent


def test_user_availability_schedule_run_happy_path(client) -> None:
    user_one = client.post(
        "/api/v1/users",
        json={"display_name": "Alice", "timezone": "UTC", "email": "alice@example.com"},
    ).json()
    user_two = client.post(
        "/api/v1/users",
        json={"display_name": "Bob", "timezone": "UTC", "email": "bob@example.com"},
    ).json()
    user_three = client.post(
        "/api/v1/users",
        json={"display_name": "Cara", "timezone": "UTC", "email": "cara@example.com"},
    ).json()

    for user_id in (user_one["id"], user_two["id"]):
        response = client.post(
            f"/api/v1/users/{user_id}/availability",
            json={"start_at": "2026-03-23T09:00:00Z", "end_at": "2026-03-23T12:00:00Z"},
        )
        assert response.status_code == 201

    response = client.post(
        f"/api/v1/users/{user_three['id']}/availability",
        json={"start_at": "2026-03-23T10:00:00Z", "end_at": "2026-03-23T11:00:00Z"},
    )
    assert response.status_code == 201

    parse_response = client.post(
        "/api/v1/preferences/parse-preview",
        json={"user_id": user_one["id"], "raw_text": "prefer mornings but not before 9"},
    )
    assert parse_response.status_code == 201
    parsed_payload = parse_response.json()
    assert parsed_payload["parsed_preference"]["timezone"] == "UTC"

    schedule_response = client.post(
        "/api/v1/schedule-requests",
        json={
            "title": "Weekly sync",
            "organizer_user_id": user_one["id"],
            "duration_minutes": 60,
            "horizon_start": "2026-03-23T09:00:00Z",
            "horizon_end": "2026-03-23T12:00:00Z",
            "slot_step_minutes": 60,
            "daily_window_start_local": "09:00:00",
            "daily_window_end_local": "12:00:00",
            "participants": [
                {"user_id": user_one["id"], "role": "required"},
                {"user_id": user_two["id"], "role": "required"},
                {"user_id": user_three["id"], "role": "optional"},
            ],
        },
    )
    assert schedule_response.status_code == 201
    schedule_request = schedule_response.json()

    run_response = client.post(f"/api/v1/schedule-requests/{schedule_request['id']}/run")
    assert run_response.status_code == 200

    body = run_response.json()
    assert body["status"] == "completed"
    assert len(body["results"]) == 3
    assert body["results"][0]["start_at"] == "2026-03-23T10:00:00Z"
    assert body["results"][0]["optional_available_count"] == 1


def test_parse_preview_returns_422_for_invalid_structured_output(client, app) -> None:
    client.post("/api/v1/users", json={"display_name": "Dana", "timezone": "UTC"})
    user_id = client.get("/api/v1/users").json()[0]["id"]

    class BadParser:
        version = "bad-v1"

        def parse(self, raw_text: str, timezone_name: str) -> dict:
            return {"schema_version": "1.0", "timezone": timezone_name, "preferred_weekdays": ["BAD"]}

    app.state.preference_parser = BadParser()

    response = client.post(
        "/api/v1/preferences/parse-preview",
        json={"user_id": user_id, "raw_text": "broken"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Parser returned invalid structured output"


def test_create_user_returns_422_for_invalid_timezone(client) -> None:
    response = client.post(
        "/api/v1/users",
        json={"display_name": "Bad TZ", "timezone": "Not/AZone"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "timezone"]


def test_connected_google_users_can_schedule_without_manual_availability(client, app) -> None:
    organizer = client.post(
        "/api/v1/users",
        json={"display_name": "Org", "timezone": "UTC", "email": "org@example.com"},
    ).json()
    attendee = client.post(
        "/api/v1/users",
        json={"display_name": "Attendee", "timezone": "UTC", "email": "attendee@example.com"},
    ).json()

    session = app.state.session_factory()
    try:
        organizer_connection = CalendarConnection(
            user_id=organizer["id"],
            provider="google",
            status="configured",
            refresh_token="refresh-org",
            selected_busy_calendar_ids_json=["primary"],
            selected_write_calendar_id="primary",
        )
        attendee_connection = CalendarConnection(
            user_id=attendee["id"],
            provider="google",
            status="configured",
            refresh_token="refresh-attendee",
            selected_busy_calendar_ids_json=["primary"],
        )
        session.add(organizer_connection)
        session.add(attendee_connection)
        session.flush()
        session.add(
            CalendarBusyInterval(
                user_id=attendee["id"],
                calendar_connection_id=attendee_connection.id,
                start_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()

    schedule_response = client.post(
        "/api/v1/schedule-requests",
        json={
            "title": "Calendar-backed sync",
            "organizer_user_id": organizer["id"],
            "duration_minutes": 60,
            "horizon_start": "2026-03-23T09:00:00Z",
            "horizon_end": "2026-03-23T12:00:00Z",
            "slot_step_minutes": 60,
            "daily_window_start_local": "09:00:00",
            "daily_window_end_local": "12:00:00",
            "participants": [
                {"user_id": organizer["id"], "role": "required"},
                {"user_id": attendee["id"], "role": "required"},
            ],
        },
    )
    assert schedule_response.status_code == 201

    run_response = client.post(f"/api/v1/schedule-requests/{schedule_response.json()['id']}/run")
    assert run_response.status_code == 200

    body = run_response.json()
    assert body["status"] == "completed"
    assert body["results"][0]["start_at"] == "2026-03-23T10:00:00Z"


def test_confirm_schedule_run_creates_calendar_event_with_fake_google_client(client, app) -> None:
    class FakeGoogleClient:
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
            assert access_token == "live-token"
            assert calendar_id == "primary"
            assert title == "Planning"
            assert attendee_emails == ["attendee@example.com"]
            return GoogleCreatedEvent(
                event_id="evt_123",
                html_link="https://calendar.google.com/event?eid=evt_123",
                status="confirmed",
                calendar_id=calendar_id,
                start_at=start_at,
                end_at=end_at,
            )

        def build_authorization_url(self, state: str) -> str:  # pragma: no cover - unused in this test
            return f"https://example.com/oauth?state={state}"

        def exchange_code(self, code: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def refresh_access_token(self, refresh_token: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def list_calendars(self, access_token: str):  # pragma: no cover - unused in this test
            return []

        def get_free_busy(self, access_token: str, calendar_ids: list[str], time_min: datetime, time_max: datetime):  # pragma: no cover - unused in this test
            return []

    app.state.google_calendar_client = FakeGoogleClient()

    organizer = client.post(
        "/api/v1/users",
        json={"display_name": "Org", "timezone": "UTC", "email": "org@example.com"},
    ).json()
    attendee = client.post(
        "/api/v1/users",
        json={"display_name": "Attendee", "timezone": "UTC", "email": "attendee@example.com"},
    ).json()

    session = app.state.session_factory()
    try:
        organizer_connection = CalendarConnection(
            user_id=organizer["id"],
            provider="google",
            status="configured",
            access_token="live-token",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            selected_busy_calendar_ids_json=["primary"],
            selected_write_calendar_id="primary",
        )
        attendee_connection = CalendarConnection(
            user_id=attendee["id"],
            provider="google",
            status="configured",
            access_token="attendee-token",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            selected_busy_calendar_ids_json=["primary"],
        )
        session.add(organizer_connection)
        session.add(attendee_connection)
        session.commit()
    finally:
        session.close()

    schedule_response = client.post(
        "/api/v1/schedule-requests",
        json={
            "title": "Planning",
            "organizer_user_id": organizer["id"],
            "duration_minutes": 60,
            "horizon_start": "2026-03-23T09:00:00Z",
            "horizon_end": "2026-03-23T12:00:00Z",
            "slot_step_minutes": 60,
            "daily_window_start_local": "09:00:00",
            "daily_window_end_local": "12:00:00",
            "participants": [
                {"user_id": organizer["id"], "role": "required"},
                {"user_id": attendee["id"], "role": "required"},
            ],
        },
    )
    run_response = client.post(f"/api/v1/schedule-requests/{schedule_response.json()['id']}/run")
    confirm_response = client.post(
        f"/api/v1/schedule-runs/{run_response.json()['id']}/confirm",
        json={"rank": 1},
    )

    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["event_id"] == "evt_123"
    assert body["calendar_id"] == "primary"
