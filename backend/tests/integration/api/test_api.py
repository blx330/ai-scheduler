import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.infrastructure.db.models import CalendarBusyInterval, CalendarConnection
from app.infrastructure.integrations.google_calendar.client import (
    GoogleBusyInterval,
    GoogleCalendarSummary,
    GoogleCreatedEvent,
    GoogleOAuthTokens,
)
from app.infrastructure.integrations.llm.profile_preference_parser import GeminiUserProfilePreferenceParser
from app.main import create_app


def test_create_user_returns_422_for_invalid_timezone(client) -> None:
    response = client.post(
        "/api/v1/users",
        json={"display_name": "Bad TZ", "timezone": "Not/AZone"},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "timezone" in response.json()["detail"]


def test_user_profile_can_store_preferred_practice_time(client) -> None:
    create_response = client.post(
        "/api/v1/users",
        json={
            "display_name": "Profile User",
            "timezone": "UTC",
            "email": "profile-user@example.com",
            "preferred_practice_time": "morning",
        },
    )

    assert create_response.status_code == 201
    user = create_response.json()
    assert user["preferred_practice_time"] == "morning"

    update_response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"preferred_practice_time": "afternoon"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["preferred_practice_time"] == "afternoon"

    read_response = client.get(f"/api/v1/users/{user['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["preferred_practice_time"] == "afternoon"


def test_saving_a_preset_alongside_a_null_raw_preference_keeps_the_preset(client) -> None:
    """The preferences UI sends both fields on every save; clearing the free-text one
    must not wipe the preset supplied in the same request."""
    user = client.post(
        "/api/v1/users",
        json={
            "display_name": "Both Fields",
            "timezone": "UTC",
            "email": "both-fields@example.com",
        },
    ).json()

    update_response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"preferred_practice_time": "morning", "preferred_practice_time_raw": None},
    )

    assert update_response.status_code == 200
    assert update_response.json()["preferred_practice_time"] == "morning"
    assert update_response.json()["preferred_practice_time_raw"] is None

    # and it must survive a round trip, not just the response body
    read_response = client.get(f"/api/v1/users/{user['id']}")
    assert read_response.json()["preferred_practice_time"] == "morning"


def test_free_text_preference_still_supersedes_a_preset(client) -> None:
    user = client.post(
        "/api/v1/users",
        json={
            "display_name": "Freeform Wins",
            "timezone": "UTC",
            "email": "freeform-wins@example.com",
            "preferred_practice_time": "morning",
        },
    ).json()

    update_response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"preferred_practice_time": None, "preferred_practice_time_raw": "weekends after 9am"},
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["preferred_practice_time"] is None
    assert body["preferred_practice_time_raw"] == "weekends after 9am"


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


def test_create_user_reuses_incomplete_registration_for_same_email(client) -> None:
    initial = client.post(
        "/api/v1/users",
        json={
            "display_name": "Cindy Placeholder",
            "timezone": "UTC",
            "email": "cindyhl654@gmail.com",
        },
    )
    assert initial.status_code == 201
    initial_user = initial.json()

    retry = client.post(
        "/api/v1/users",
        json={
            "display_name": "Cindy Final",
            "timezone": "America/New_York",
            "email": "cindyhl654@gmail.com",
        },
    )
    assert retry.status_code == 201
    retry_user = retry.json()
    assert retry_user["id"] == initial_user["id"]
    assert retry_user["display_name"] == "Cindy Final"
    assert retry_user["timezone"] == "America/New_York"


def test_create_user_cannot_take_over_an_account_that_has_data(client) -> None:
    """A signup retry may re-claim an empty new account, but never one already in use."""
    victim = client.post(
        "/api/v1/users",
        json={"display_name": "Victim", "timezone": "UTC", "email": "victim@example.com"},
    ).json()

    # the account is now in use, even though it has no Google connection
    availability = client.post(
        f"/api/v1/users/{victim['id']}/availability",
        json={"start_at": "2026-04-01T09:00:00Z", "end_at": "2026-04-01T12:00:00Z"},
    )
    assert availability.status_code == 201

    attacker = client.post(
        "/api/v1/users",
        json={"display_name": "Attacker", "timezone": "Pacific/Auckland", "email": "victim@example.com"},
    )

    assert attacker.status_code == 400
    assert attacker.json()["detail"] == "A user with that email already exists"

    unchanged = client.get(f"/api/v1/users/{victim['id']}").json()
    assert unchanged["display_name"] == "Victim"
    assert unchanged["timezone"] == "UTC"


def test_create_user_matches_email_case_insensitively_after_normalization(client) -> None:
    first = client.post(
        "/api/v1/users",
        json={"display_name": "Mixed Case", "timezone": "UTC", "email": "Mixed.Case@Example.com"},
    )
    assert first.status_code == 201
    assert first.json()["email"] == "mixed.case@example.com"

    client.post(
        f"/api/v1/users/{first.json()['id']}/availability",
        json={"start_at": "2026-04-01T09:00:00Z", "end_at": "2026-04-01T12:00:00Z"},
    )

    duplicate = client.post(
        "/api/v1/users",
        json={"display_name": "Other", "timezone": "UTC", "email": "  mixed.case@example.com  "},
    )
    assert duplicate.status_code == 400


def test_create_user_rejects_duplicate_email_when_registration_completed(client, app) -> None:
    created = client.post(
        "/api/v1/users",
        json={
            "display_name": "Connected User",
            "timezone": "UTC",
            "email": "connected-user@example.com",
        },
    )
    assert created.status_code == 201
    created_user = created.json()

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=created_user["id"],
                provider="google",
                status="connected",
                refresh_token="refresh-token",
            )
        )
        session.commit()
    finally:
        session.close()

    duplicate = client.post(
        "/api/v1/users",
        json={
            "display_name": "Another Person",
            "timezone": "UTC",
            "email": "connected-user@example.com",
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "A user with that email already exists"


def test_app_bootstraps_gemini_profile_parser_from_gemini_env(monkeypatch, session_factory) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")
    settings = Settings(database_url="sqlite:///ignored.db", auto_sync_enabled=False)

    app = create_app(settings=settings, session_factory=session_factory)

    parser = app.state.user_profile_preference_parser
    assert isinstance(parser, GeminiUserProfilePreferenceParser)
    assert settings.gemini_api_key == "gemini-demo-key"
    assert parser.api_key == "gemini-demo-key"


def test_auto_sync_task_not_created_when_disabled(session_factory) -> None:
    settings = Settings(database_url="sqlite:///ignored.db", auto_sync_enabled=False)
    app = create_app(settings=settings, session_factory=session_factory)

    with TestClient(app):
        assert app.state.auto_sync_task is None


def test_auto_sync_task_runs_when_enabled(monkeypatch, session_factory) -> None:
    calls = []

    async def fake_auto_sync_loop(loop_session_factory, loop_settings, loop_client) -> None:
        calls.append((loop_session_factory, loop_settings, loop_client))
        await asyncio.Event().wait()  # block until the lifespan cancels it, like the real loop

    monkeypatch.setattr("app.main.auto_sync_loop", fake_auto_sync_loop)

    settings = Settings(database_url="sqlite:///ignored.db", auto_sync_enabled=True)
    app = create_app(settings=settings, session_factory=session_factory)

    with TestClient(app):
        assert app.state.auto_sync_task is not None

    assert len(calls) == 1
    assert calls[0] == (session_factory, settings, app.state.google_calendar_client)


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
            # a busy sync has actually covered this window, so free time inside it is known
            busy_synced_at=datetime(2026, 3, 22, 0, 0, tzinfo=UTC),
            busy_synced_start_at=datetime(2026, 3, 23, 0, 0, tzinfo=UTC),
            busy_synced_end_at=datetime(2026, 3, 24, 0, 0, tzinfo=UTC),
        )
        session.add(organizer_connection)
        session.add(attendee_connection)
        session.flush()
        session.add(
            CalendarBusyInterval(
                user_id=attendee["id"],
                calendar_connection_id=attendee_connection.id,
                start_at=datetime(2026, 3, 23, 8, 0, tzinfo=UTC),
                end_at=datetime(2026, 3, 23, 9, 0, tzinfo=UTC),
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


def test_connected_but_never_synced_user_is_not_treated_as_free(client, app) -> None:
    """Holding a Google token says nothing about someone's schedule until a sync runs."""
    organizer = client.post(
        "/api/v1/users",
        json={"display_name": "Org NS", "timezone": "UTC", "email": "org-nosync@example.com"},
    ).json()
    attendee = client.post(
        "/api/v1/users",
        json={"display_name": "Attendee NS", "timezone": "UTC", "email": "attendee-nosync@example.com"},
    ).json()

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=attendee["id"],
                provider="google",
                status="configured",
                refresh_token="refresh-attendee",
                selected_busy_calendar_ids_json=["primary"],
                # no busy_synced_* values: connected, but never synced
            )
        )
        session.commit()
    finally:
        session.close()

    event_response = client.post(
        "/api/v1/events",
        json={
            "name": "Unsynced rehearsal",
            "description": None,
            "organizer_user_id": organizer["id"],
            "duration_minutes": 60,
            "earliest_start_date": "2026-03-23",
            "min_days_apart": 0,
            "latest_schedule_at": "2026-03-23T12:00:00Z",
            "required_session_count": 1,
            "participants": [{"user_id": attendee["id"], "role": "required"}],
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
    recommendations = body["results"][0]["recommendations"] if body["results"] else []
    # nothing may be offered as fully feasible for someone whose schedule is unknown
    assert all(item["is_fallback"] for item in recommendations)


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
                token_expires_at=datetime.now(UTC) + timedelta(hours=1),
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
        start_at=datetime(2026, 3, 24, 14, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 24, 16, 0, tzinfo=UTC),
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
            description: str | None = None,
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
                scopes="https://www.googleapis.com/auth/calendar",
                token_expires_at=datetime.now(UTC) + timedelta(hours=1),
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
        "time_min": datetime(2026, 3, 23, 0, 0, tzinfo=UTC),
        "time_max": datetime(2026, 3, 30, 0, 0, tzinfo=UTC),
    }

    overview_response = client.get(
        "/api/v1/calendar/overview",
        params={
            "start": "2026-03-23T00:00:00Z",
            "end": "2026-03-30T00:00:00Z",
            "user_ids": [user["id"]],
        },
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert len(overview["busy_intervals"]) == 1
    assert overview["busy_intervals"][0]["user_id"] == user["id"]
    assert overview["busy_intervals"][0]["start_at"] == "2026-03-24T14:00:00Z"
    assert overview["busy_intervals"][0]["end_at"] == "2026-03-24T16:00:00Z"

    # busy time is private: without an explicit user_ids filter, none is returned
    unscoped = client.get(
        "/api/v1/calendar/overview",
        params={"start": "2026-03-23T00:00:00Z", "end": "2026-03-30T00:00:00Z"},
    )
    assert unscoped.status_code == 200
    assert unscoped.json()["busy_intervals"] == []
    # confirmed practices remain visible; they are shared studio bookings
    assert "practice_sessions" in unscoped.json()


def test_google_oauth_state_links_connection_to_requested_user(client, app) -> None:
    class FakeGoogleClient:
        def __init__(self) -> None:
            self.last_state = ""

        def build_authorization_url(self, state: str) -> str:
            self.last_state = state
            return f"https://example.com/oauth?state={state}"

        def exchange_code(self, code: str) -> GoogleOAuthTokens:
            assert code == "auth-code"
            return GoogleOAuthTokens(
                access_token="token-from-exchange",
                refresh_token="refresh-from-exchange",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                scope="https://www.googleapis.com/auth/calendar",
            )

        def refresh_access_token(self, refresh_token: str) -> GoogleOAuthTokens:  # pragma: no cover - unused
            raise NotImplementedError

        def list_calendars(self, access_token: str) -> list[GoogleCalendarSummary]:  # pragma: no cover - unused
            return []

        def get_free_busy(self, access_token: str, calendar_ids: list[str], time_min: datetime, time_max: datetime):  # pragma: no cover - unused
            return []

        def create_event(
            self,
            access_token: str,
            calendar_id: str,
            title: str,
            start_at: datetime,
            end_at: datetime,
            timezone_name: str,
            attendee_emails: list[str],
            description: str | None = None,
        ) -> GoogleCreatedEvent:  # pragma: no cover - unused
            raise NotImplementedError

        def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:  # pragma: no cover - unused
            raise NotImplementedError

    fake_client = FakeGoogleClient()
    app.state.google_calendar_client = fake_client

    target_user = client.post(
        "/api/v1/users",
        json={"display_name": "OAuth Target", "timezone": "UTC", "email": "oauth-target@example.com"},
    ).json()

    start_response = client.post(
        "/api/v1/google/oauth/start",
        json={"user_id": target_user["id"]},
    )
    assert start_response.status_code == 200
    authorization_url = start_response.json()["authorization_url"]
    state = parse_qs(urlparse(authorization_url).query)["state"][0]
    assert state == fake_client.last_state

    callback_response = client.get(
        "/api/v1/google/oauth/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert callback_response.status_code in {302, 307}

    connection_response = client.get(f"/api/v1/users/{target_user['id']}/google/connection")
    assert connection_response.status_code == 200
    assert connection_response.json()["connected"] is True
