from datetime import datetime, timezone
from datetime import timedelta
from typing import Optional

from app.infrastructure.config import Settings
from app.infrastructure.db.models import CalendarBusyInterval, CalendarConnection
from app.infrastructure.integrations.google_calendar.client import GoogleBusyInterval, GoogleCalendarSummary, GoogleCreatedEvent
from app.infrastructure.integrations.llm.profile_preference_parser import GroqUserProfilePreferenceParser
from app.main import create_app


def test_create_user_returns_422_for_invalid_timezone(client) -> None:
    response = client.post(
        "/api/v1/users",
        json={"display_name": "Bad TZ", "timezone": "Not/AZone"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "timezone"]


def test_user_profile_can_store_preferred_practice_time(client) -> None:
    create_response = client.post(
        "/api/v1/users",
        json={
            "display_name": "Profile User",
            "timezone": "UTC",
            "email": "profile-user@example.com",
            "preferred_practice_time": "mid_morning",
        },
    )

    assert create_response.status_code == 201
    user = create_response.json()
    assert user["preferred_practice_time"] == "mid_morning"

    update_response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"preferred_practice_time": "late_morning"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["preferred_practice_time"] == "late_morning"

    read_response = client.get(f"/api/v1/users/{user['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["preferred_practice_time"] == "late_morning"


def test_user_profile_caches_parsed_free_text_preferences(client, app) -> None:
    class FakeProfileParser:
        version = "fake-profile-v1"

        def parse(self, raw_text: str, timezone_name: str) -> dict:
            assert timezone_name == "UTC"
            return {
                "preferred_days": ["Saturday", "Sunday"],
                "avoid_days": ["Friday"],
                "earliest_time": "09:00",
                "latest_time": "12:00",
                "notes": raw_text,
                "summary": "prefers weekends, avoids Fridays, never before 9:00 AM",
            }

    app.state.user_profile_preference_parser = FakeProfileParser()

    response = client.post(
        "/api/v1/users",
        json={
            "display_name": "Profile Parse User",
            "timezone": "UTC",
            "email": "profile-parse@example.com",
            "preferred_practice_time_raw": "weekends, never before 9am, avoid Fridays",
        },
    )

    assert response.status_code == 201
    user = response.json()
    assert user["preferred_practice_time_raw"] == "weekends, never before 9am, avoid Fridays"
    assert user["preferred_practice_time_parsed"] == {
        "preferred_days": ["Saturday", "Sunday"],
        "avoid_days": ["Friday"],
        "earliest_time": "09:00",
        "latest_time": "12:00",
        "notes": "weekends, never before 9am, avoid Fridays",
        "summary": "prefers weekends, avoids Fridays, never before 9:00 AM",
    }
    assert user["preferred_practice_time_summary"] == (
        "Understood: prefers weekends, avoids Fridays, never before 9:00 AM"
    )


def test_app_bootstraps_groq_profile_parser_from_groq_env(monkeypatch, session_factory) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-demo-key")
    settings = Settings(database_url="sqlite:///ignored.db")

    app = create_app(settings=settings, session_factory=session_factory)

    parser = app.state.user_profile_preference_parser
    assert isinstance(parser, GroqUserProfilePreferenceParser)
    assert settings.groq_api_key == "groq-demo-key"
    assert parser.api_key == "groq-demo-key"


def test_connected_google_users_can_plan_without_manual_availability(client, app) -> None:
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
                start_at=datetime(2026, 3, 23, 8, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()

    event_response = client.post(
        "/api/v1/events",
        json={
            "name": "Calendar-backed rehearsal",
            "description": None,
            "organizer_user_id": organizer["id"],
            "duration_minutes": 60,
            "earliest_start_date": "2026-03-23",
            "min_days_apart": 0,
            "latest_schedule_at": "2026-03-23T12:00:00Z",
            "required_session_count": 1,
            "participants": [
                {"user_id": attendee["id"], "role": "required"},
            ],
        },
    )
    assert event_response.status_code == 201

    run_response = client.post(
        "/api/v1/planning-runs",
        json={
            "event_ids": [event_response.json()["id"]],
            "horizon_start": "2026-03-23T08:00:00Z",
            "horizon_end": "2026-03-23T12:00:00Z",
            "slot_step_minutes": 60,
        },
    )
    assert run_response.status_code == 200

    body = run_response.json()
    assert body["status"] == "completed"
    top_recommendation = body["results"][0]["recommendations"][0]
    assert top_recommendation["start_at"] == "2026-03-23T09:00:00Z"


def test_google_connection_with_identity_only_scope_requires_reconnect(client, app) -> None:
    user = client.post(
        "/api/v1/users",
        json={"display_name": "Scoped User", "timezone": "UTC", "email": "scoped@example.com"},
    ).json()

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=user["id"],
                provider="google",
                status="connected",
                access_token="live-token",
                refresh_token="refresh-token",
                scopes="openid email profile",
                token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(f"/api/v1/users/{user['id']}/google/connection")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["status"] == "reauthorization_required"


def test_google_busy_sync_persists_selected_calendars_and_overview_returns_intervals(client, app) -> None:
    selected_calendar_id = "dance-team@example.com"
    synced_interval = GoogleBusyInterval(
        calendar_id=selected_calendar_id,
        start_at=datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 24, 16, 0, tzinfo=timezone.utc),
    )

    class FakeGoogleClient:
        def __init__(self) -> None:
            self.last_free_busy_request = None

        def build_authorization_url(self, state: str) -> str:  # pragma: no cover - unused in this test
            return f"https://example.com/oauth?state={state}"

        def exchange_code(self, code: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def refresh_access_token(self, refresh_token: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def list_calendars(self, access_token: str) -> list[GoogleCalendarSummary]:
            assert access_token == "live-token"
            return [
                GoogleCalendarSummary(
                    id="primary",
                    summary="Primary",
                    primary=True,
                    access_role="owner",
                    time_zone="UTC",
                ),
                GoogleCalendarSummary(
                    id=selected_calendar_id,
                    summary="Dance Team",
                    primary=False,
                    access_role="reader",
                    time_zone="UTC",
                ),
            ]

        def get_free_busy(self, access_token: str, calendar_ids: list[str], time_min: datetime, time_max: datetime):
            assert access_token == "live-token"
            self.last_free_busy_request = {
                "calendar_ids": calendar_ids,
                "time_min": time_min,
                "time_max": time_max,
            }
            return [synced_interval]

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
        ) -> GoogleCreatedEvent:  # pragma: no cover - unused in this test
            raise NotImplementedError

    fake_client = FakeGoogleClient()
    app.state.google_calendar_client = fake_client

    user = client.post(
        "/api/v1/users",
        json={"display_name": "Calendar User", "timezone": "UTC", "email": "calendar@example.com"},
    ).json()

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=user["id"],
                provider="google",
                status="connected",
                access_token="live-token",
                token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        session.commit()
    finally:
        session.close()

    select_response = client.post(
        f"/api/v1/users/{user['id']}/google/calendars/select",
        json={
            "busy_calendar_ids": [selected_calendar_id],
            "write_calendar_id": "primary",
        },
    )
    assert select_response.status_code == 200
    assert select_response.json()["selected_busy_calendar_ids"] == [selected_calendar_id]

    sync_response = client.post(
        f"/api/v1/users/{user['id']}/google/sync-busy",
        json={
            "horizon_start": "2026-03-23T00:00:00Z",
            "horizon_end": "2026-03-30T00:00:00Z",
        },
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["synced_interval_count"] == 1
    assert sync_response.json()["calendar_ids"] == [selected_calendar_id]
    assert fake_client.last_free_busy_request == {
        "calendar_ids": [selected_calendar_id],
        "time_min": datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        "time_max": datetime(2026, 3, 30, 0, 0, tzinfo=timezone.utc),
    }

    overview_response = client.get(
        "/api/v1/calendar/overview",
        params={
            "start": "2026-03-23T00:00:00Z",
            "end": "2026-03-30T00:00:00Z",
        },
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert len(overview["busy_intervals"]) == 1
    assert overview["busy_intervals"][0]["user_id"] == user["id"]
    assert overview["busy_intervals"][0]["start_at"] == "2026-03-24T14:00:00Z"
    assert overview["busy_intervals"][0]["end_at"] == "2026-03-24T16:00:00Z"
