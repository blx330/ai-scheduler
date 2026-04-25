from datetime import datetime, timedelta, timezone

from app.infrastructure.db.models import CalendarConnection
from app.infrastructure.integrations.google_calendar.client import GoogleCreatedEvent


def test_planning_run_avoids_shared_participant_conflicts(client) -> None:
    organizer = _create_user(client, "Coach", "coach@example.com")
    dancer_one = _create_user(client, "A", "a@example.com")
    dancer_two = _create_user(client, "B", "b@example.com")
    dancer_three = _create_user(client, "C", "c@example.com")

    for user in (dancer_one, dancer_two, dancer_three):
        _add_availability(client, user["id"], "2026-04-01T09:00:00Z", "2026-04-01T12:00:00Z")

    first_event = _create_event(
        client,
        name="Alpha Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-01T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_one["id"], "role": "required"},
            {"user_id": dancer_two["id"], "role": "required"},
        ],
    )
    second_event = _create_event(
        client,
        name="Beta Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-01T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_two["id"], "role": "required"},
            {"user_id": dancer_three["id"], "role": "required"},
        ],
    )

    response = _create_planning_run(
        client,
        event_ids=[first_event["id"], second_event["id"]],
        horizon_start="2026-04-01T09:00:00Z",
        horizon_end="2026-04-01T12:00:00Z",
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    first_slot = body["results"][0]["recommendations"][0]
    second_slot = body["results"][1]["recommendations"][0]
    assert first_slot["start_at"] == "2026-04-01T09:00:00Z"
    assert second_slot["start_at"] != first_slot["start_at"]
    assert second_slot["start_at"] in {"2026-04-01T10:00:00Z", "2026-04-01T11:00:00Z"}


def test_planning_run_respects_shared_room_for_disjoint_events(client) -> None:
    organizer = _create_user(client, "Coach Room", "coach-room@example.com")
    dancer_one = _create_user(client, "D1", "d1@example.com")
    dancer_two = _create_user(client, "D2", "d2@example.com")
    dancer_three = _create_user(client, "D3", "d3@example.com")
    dancer_four = _create_user(client, "D4", "d4@example.com")

    for user in (dancer_one, dancer_two, dancer_three, dancer_four):
        _add_availability(client, user["id"], "2026-04-02T09:00:00Z", "2026-04-02T12:00:00Z")

    first_event = _create_event(
        client,
        name="Room Alpha",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-02T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_one["id"], "role": "required"},
            {"user_id": dancer_two["id"], "role": "required"},
        ],
    )
    second_event = _create_event(
        client,
        name="Room Beta",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-02T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_three["id"], "role": "required"},
            {"user_id": dancer_four["id"], "role": "required"},
        ],
    )

    response = _create_planning_run(
        client,
        event_ids=[first_event["id"], second_event["id"]],
        horizon_start="2026-04-02T09:00:00Z",
        horizon_end="2026-04-02T12:00:00Z",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["recommendations"][0]["start_at"] == "2026-04-02T09:00:00Z"
    assert body["results"][1]["recommendations"][0]["start_at"] == "2026-04-02T10:00:00Z"


def test_planning_run_returns_fallback_when_one_required_participant_is_missing(client) -> None:
    organizer = _create_user(client, "Coach Fallback", "coach-fallback@example.com")
    dancer_one = _create_user(client, "Solo A", "solo-a@example.com")
    dancer_two = _create_user(client, "Solo B", "solo-b@example.com")

    _add_availability(client, dancer_one["id"], "2026-04-03T09:00:00Z", "2026-04-03T10:00:00Z")
    _add_availability(client, dancer_two["id"], "2026-04-03T10:00:00Z", "2026-04-03T11:00:00Z")

    event = _create_event(
        client,
        name="Fallback Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-03T11:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_one["id"], "role": "required"},
            {"user_id": dancer_two["id"], "role": "required"},
        ],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-03T09:00:00Z",
        horizon_end="2026-04-03T11:00:00Z",
    )

    assert response.status_code == 200
    body = response.json()
    recommendation = body["results"][0]["recommendations"][0]
    assert recommendation["is_fallback"] is True
    assert len(recommendation["missing_required_user_ids"]) == 1
    assert recommendation["explanation"]["missing_required_user_ids"] == recommendation["missing_required_user_ids"]


def test_planning_run_prefers_fully_attended_before_partial_fallback(client) -> None:
    organizer = _create_user(client, "Coach Full First", "coach-full-first@example.com")
    always_available = _create_user(client, "Always", "always@example.com")
    limited = _create_user(client, "Limited", "limited@example.com")

    _add_availability(client, always_available["id"], "2026-04-03T08:00:00Z", "2026-04-03T20:00:00Z")
    _add_availability(client, limited["id"], "2026-04-03T18:00:00Z", "2026-04-03T20:00:00Z")

    event = _create_event(
        client,
        name="Full First Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-03T20:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": always_available["id"], "role": "required"},
            {"user_id": limited["id"], "role": "required"},
        ],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-03T08:00:00Z",
        horizon_end="2026-04-03T20:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    assert len(recommendations) == 3
    assert recommendations[0]["is_fallback"] is False
    assert recommendations[1]["is_fallback"] is False
    assert recommendations[0]["start_at"] == "2026-04-03T18:00:00Z"
    assert recommendations[1]["start_at"] == "2026-04-03T19:00:00Z"
    assert recommendations[2]["is_fallback"] is True
    assert recommendations[2]["missing_required_user_ids"]


def test_planning_run_keeps_top_three_fully_attended_when_available(client) -> None:
    organizer = _create_user(client, "Coach Full Top3", "coach-full-top3@example.com")
    required_one = _create_user(client, "Req One", "req-one@example.com")
    required_two = _create_user(client, "Req Two", "req-two@example.com")

    _add_availability(client, required_one["id"], "2026-04-03T16:00:00Z", "2026-04-03T22:00:00Z")
    _add_availability(client, required_two["id"], "2026-04-03T16:00:00Z", "2026-04-03T22:00:00Z")

    event = _create_event(
        client,
        name="Full Top Three",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-03T22:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": required_one["id"], "role": "required"},
            {"user_id": required_two["id"], "role": "required"},
        ],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-03T16:00:00Z",
        horizon_end="2026-04-03T22:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    assert len(recommendations) == 3
    assert all(item["is_fallback"] is False for item in recommendations)


def test_confirmed_sessions_affect_future_planning_runs(client) -> None:
    organizer = _create_user(client, "Coach Confirm", "coach-confirm@example.com")
    dancer_one = _create_user(client, "Confirm A", "confirm-a@example.com")
    dancer_two = _create_user(client, "Confirm B", "confirm-b@example.com")
    dancer_three = _create_user(client, "Confirm C", "confirm-c@example.com")
    dancer_four = _create_user(client, "Confirm D", "confirm-d@example.com")

    for user in (dancer_one, dancer_two, dancer_three, dancer_four):
        _add_availability(client, user["id"], "2026-04-04T09:00:00Z", "2026-04-04T12:00:00Z")

    first_event = _create_event(
        client,
        name="Confirmed Alpha",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-04T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_one["id"], "role": "required"},
            {"user_id": dancer_two["id"], "role": "required"},
        ],
    )
    second_event = _create_event(
        client,
        name="Confirmed Beta",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-04T12:00:00Z",
        required_session_count=1,
        participants=[
            {"user_id": dancer_three["id"], "role": "required"},
            {"user_id": dancer_four["id"], "role": "required"},
        ],
    )

    first_run = _create_planning_run(
        client,
        event_ids=[first_event["id"]],
        horizon_start="2026-04-04T09:00:00Z",
        horizon_end="2026-04-04T12:00:00Z",
    )
    first_run_payload = first_run.json()
    top_result_id = first_run_payload["results"][0]["recommendations"][0]["id"]

    confirm_response = client.post(
        f"/api/v1/planning-runs/{first_run_payload['id']}/confirm",
        json={"result_ids": [top_result_id]},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["confirmed_sessions"][0]["start_at"] == "2026-04-04T09:00:00Z"

    sessions_response = client.get(f"/api/v1/events/{first_event['id']}/sessions")
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["status"] == "confirmed"

    second_run = _create_planning_run(
        client,
        event_ids=[second_event["id"]],
        horizon_start="2026-04-04T09:00:00Z",
        horizon_end="2026-04-04T12:00:00Z",
    )
    assert second_run.status_code == 200
    assert second_run.json()["results"][0]["recommendations"][0]["start_at"] == "2026-04-04T10:00:00Z"

    overview_response = client.get(
        "/api/v1/calendar/overview",
        params={"start": "2026-04-04T09:00:00Z", "end": "2026-04-04T12:00:00Z"},
    )
    assert overview_response.status_code == 200
    assert overview_response.json()["practice_sessions"][0]["start_at"] == "2026-04-04T09:00:00Z"


def test_planning_run_orders_by_score_descending_before_time_tiebreak(client) -> None:
    organizer = _create_user(
        client,
        "Coach Evening Rank",
        "coach-evening-rank@example.com",
        preferred_practice_time="late_morning",
    )
    dancer = _create_user(client, "Evening Rank Dancer", "evening-rank-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-05T08:00:00Z", "2026-04-05T23:00:00Z")

    event = _create_event(
        client,
        name="Evening Ranking Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-05T23:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-05T06:00:00Z",
        horizon_end="2026-04-05T23:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    assert recommendations[0]["start_at"] == "2026-04-05T18:00:00Z"
    assert recommendations[1]["start_at"] == "2026-04-05T19:00:00Z"
    assert recommendations[2]["start_at"] == "2026-04-05T20:00:00Z"
    assert recommendations[0]["score_breakdown"]["time_tier_bonus"] == 6.0
    assert recommendations[2]["score_breakdown"]["time_tier_bonus"] == 6.0


def test_planning_run_uses_saved_preferred_practice_time_for_scoring(client) -> None:
    organizer = _create_user(
        client,
        "Coach Preference",
        "coach-preference@example.com",
        preferred_practice_time="mid_morning",
    )
    dancer = _create_user(client, "Preference Dancer", "preference-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-06T08:00:00Z", "2026-04-06T12:00:00Z")

    event = _create_event(
        client,
        name="Preference Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-06T12:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-06T08:00:00Z",
        horizon_end="2026-04-06T12:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    earliest_slot = next(item for item in recommendations if item["start_at"] == "2026-04-06T08:00:00Z")
    preferred_slot = next(item for item in recommendations if item["start_at"] == "2026-04-06T09:00:00Z")
    assert earliest_slot["score_breakdown"]["organizer_preference_bonus"] == 0.0
    assert preferred_slot["score_breakdown"]["organizer_preference_bonus"] == 1.0
    assert any(
        reason["code"] == "organizer_preference_bonus" for reason in preferred_slot["explanation"]["reasons"]
    )


def test_planning_run_uses_cached_free_text_preferences_for_scoring(client, app) -> None:
    class FakeProfileParser:
        version = "fake-profile-v1"

        def parse(self, raw_text: str, timezone_name: str) -> dict:
            assert raw_text == "mid-morning only"
            assert timezone_name == "UTC"
            return {
                "preferred_days": [],
                "avoid_days": [],
                "earliest_time": "09:00",
                "latest_time": "11:00",
                "notes": raw_text,
                "summary": "prefers 9:00 AM to 11:00 AM",
            }

    app.state.user_profile_preference_parser = FakeProfileParser()

    organizer = _create_user(
        client,
        "Coach Parsed Preference",
        "coach-parsed-preference@example.com",
        preferred_practice_time_raw="mid-morning only",
    )
    dancer = _create_user(client, "Parsed Dancer", "parsed-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-06T08:00:00Z", "2026-04-06T12:00:00Z")

    event = _create_event(
        client,
        name="Parsed Preference Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-06T12:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-06T08:00:00Z",
        horizon_end="2026-04-06T12:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    earliest_slot = next(item for item in recommendations if item["start_at"] == "2026-04-06T08:00:00Z")
    preferred_slot = next(item for item in recommendations if item["start_at"] == "2026-04-06T09:00:00Z")
    assert earliest_slot["score_breakdown"]["organizer_preference_bonus"] == 0.0
    assert preferred_slot["score_breakdown"]["organizer_preference_bonus"] == 1.0
    assert any(
        reason["code"] == "organizer_preference_bonus" for reason in preferred_slot["explanation"]["reasons"]
    )


def test_planning_run_respects_earliest_start_date_and_min_days_apart(client) -> None:
    organizer = _create_user(client, "Coach Spacing", "coach-spacing@example.com")
    dancer = _create_user(client, "Spacing Dancer", "spacing-dancer@example.com")

    for day in range(12, 19):
        _add_availability(
            client,
            dancer["id"],
            f"2026-04-{day:02d}T08:00:00Z",
            f"2026-04-{day:02d}T12:00:00Z",
        )

    event = _create_event(
        client,
        name="Spacing Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        earliest_start_date="2026-04-12",
        min_days_apart=3,
        latest_schedule_at="2026-04-18T12:00:00Z",
        required_session_count=2,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-11T08:00:00Z",
        horizon_end="2026-04-18T12:00:00Z",
    )

    assert response.status_code == 200
    groups = response.json()["results"]
    first_practice = next(group for group in groups if group["session_index"] == 1)
    second_practice = next(group for group in groups if group["session_index"] == 2)
    assert first_practice["recommendations"][0]["start_at"] == "2026-04-12T08:00:00Z"
    assert second_practice["recommendations"][0]["start_at"] == "2026-04-15T08:00:00Z"
    assert all(item["start_at"] >= "2026-04-15T08:00:00Z" for item in second_practice["recommendations"])


def test_planning_run_prunes_slots_that_cannot_complete_full_spacing_sequence(client) -> None:
    organizer = _create_user(client, "Coach Sequence", "coach-sequence@example.com")
    dancer = _create_user(client, "Sequence Dancer", "sequence-dancer@example.com")

    for day in (12, 13, 16, 17, 20):
        _add_availability(
            client,
            dancer["id"],
            f"2026-04-{day:02d}T08:00:00Z",
            f"2026-04-{day:02d}T12:00:00Z",
        )

    event = _create_event(
        client,
        name="Sequence Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=240,
        earliest_start_date="2026-04-12",
        min_days_apart=3,
        latest_schedule_at="2026-04-20T12:00:00Z",
        required_session_count=3,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-12T08:00:00Z",
        horizon_end="2026-04-20T12:00:00Z",
    )

    assert response.status_code == 200
    groups = response.json()["results"]
    first_practice = next(group for group in groups if group["session_index"] == 1)
    second_practice = next(group for group in groups if group["session_index"] == 2)
    third_practice = next(group for group in groups if group["session_index"] == 3)

    first_dates = {item["start_at"][:10] for item in first_practice["recommendations"]}
    second_dates = {item["start_at"][:10] for item in second_practice["recommendations"]}
    third_dates = {item["start_at"][:10] for item in third_practice["recommendations"]}

    assert {"2026-04-12", "2026-04-13"} & first_dates
    assert {"2026-04-16", "2026-04-17"} & second_dates
    assert "2026-04-20" in third_dates


def test_planning_run_returns_no_results_when_only_forbidden_window_is_available(client) -> None:
    organizer = _create_user(client, "Coach Forbidden", "coach-forbidden@example.com")
    dancer = _create_user(client, "Forbidden Dancer", "forbidden-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-07T02:00:00Z", "2026-04-07T05:00:00Z")

    event = _create_event(
        client,
        name="Forbidden Window Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-07T05:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-07T02:00:00Z",
        horizon_end="2026-04-07T05:00:00Z",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_results"
    assert body["message"] == "No availability found between 8:00 AM and 12:00 AM."
    assert body["results"] == []


def test_event_can_be_archived_and_deleted(client) -> None:
    organizer = _create_user(client, "Coach Archive", "coach-archive@example.com")
    dancer = _create_user(client, "Archive Dancer", "archive-dancer@example.com")
    event = _create_event(
        client,
        name="Archive Me",
        organizer_user_id=organizer["id"],
        duration_minutes=120,
        latest_schedule_at="2026-04-08T23:00:00Z",
        required_session_count=2,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    update_response = client.patch(
        f"/api/v1/events/{event['id']}",
        json={"status": "archived"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "archived"

    delete_response = client.delete(f"/api/v1/events/{event['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/events/{event['id']}")
    assert get_response.status_code == 404


def test_user_cannot_be_deleted_while_assigned_to_dance(client) -> None:
    organizer = _create_user(client, "Coach Protect", "coach-protect@example.com")
    dancer = _create_user(client, "Protected Dancer", "protected-dancer@example.com")
    _create_event(
        client,
        name="Keep Participant",
        organizer_user_id=organizer["id"],
        duration_minutes=90,
        latest_schedule_at="2026-04-09T23:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    delete_response = client.delete(f"/api/v1/users/{dancer['id']}")
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "Remove this person from all dances before deleting them from the app"


def test_unschedule_practice_removes_google_event_and_clears_calendar(client, app) -> None:
    class FakeGoogleClient:
        def __init__(self) -> None:
            self.deleted_events: list[tuple[str, str]] = []

        def create_event(
            self,
            access_token: str,
            calendar_id: str,
            title: str,
            start_at: datetime,
            end_at: datetime,
            timezone_name: str,
            attendee_emails: list[str],
            description=None,
        ) -> GoogleCreatedEvent:
            assert access_token == "live-token"
            assert calendar_id == "primary"
            assert title == "Unschedule Dance Practice 1"
            return GoogleCreatedEvent(
                event_id="practice_evt_123",
                html_link="https://calendar.google.com/event?eid=practice_evt_123",
                status="confirmed",
                calendar_id=calendar_id,
                start_at=start_at,
                end_at=end_at,
            )

        def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
            assert access_token == "live-token"
            self.deleted_events.append((calendar_id, event_id))

        def build_authorization_url(self, state: str) -> str:  # pragma: no cover - unused in this test
            return state

        def exchange_code(self, code: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def refresh_access_token(self, refresh_token: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def list_calendars(self, access_token: str):  # pragma: no cover - unused in this test
            return []

        def get_free_busy(self, access_token: str, calendar_ids: list[str], time_min: datetime, time_max: datetime):  # pragma: no cover - unused in this test
            return []

    fake_client = FakeGoogleClient()
    app.state.google_calendar_client = fake_client

    organizer = _create_user(client, "Coach Unschedule", "coach-unschedule@example.com")
    dancer = _create_user(client, "Unschedule Dancer", "unschedule-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-10T08:00:00Z", "2026-04-10T12:00:00Z")

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=organizer["id"],
                provider="google",
                status="configured",
                access_token="live-token",
                scopes="https://www.googleapis.com/auth/calendar",
                token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                selected_busy_calendar_ids_json=["primary"],
                selected_write_calendar_id="primary",
            )
        )
        session.commit()
    finally:
        session.close()

    event = _create_event(
        client,
        name="Unschedule Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-10T12:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    planning_run = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-10T08:00:00Z",
        horizon_end="2026-04-10T12:00:00Z",
    ).json()
    result_id = planning_run["results"][0]["recommendations"][0]["id"]

    confirm_response = client.post(
        f"/api/v1/planning-runs/{planning_run['id']}/confirm",
        json={"result_ids": [result_id]},
    )
    assert confirm_response.status_code == 200
    practice_session = confirm_response.json()["confirmed_sessions"][0]
    assert practice_session["google_calendar_event_id"] == "practice_evt_123"

    delete_response = client.delete(f"/api/v1/practices/{practice_session['id']}/schedule")
    assert delete_response.status_code == 200
    assert delete_response.json()["unscheduled"] is True
    assert delete_response.json()["google_event_deleted"] is True
    assert fake_client.deleted_events == [("primary", "practice_evt_123")]

    sessions_response = client.get(f"/api/v1/events/{event['id']}/sessions")
    assert sessions_response.status_code == 200
    assert sessions_response.json() == []

    event_response = client.get(f"/api/v1/events/{event['id']}")
    assert event_response.status_code == 200
    assert event_response.json()["status"] == "unscheduled"


def test_unschedule_practice_still_succeeds_when_google_delete_fails(client, app) -> None:
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
            description=None,
        ) -> GoogleCreatedEvent:
            return GoogleCreatedEvent(
                event_id="practice_evt_456",
                html_link="https://calendar.google.com/event?eid=practice_evt_456",
                status="confirmed",
                calendar_id=calendar_id,
                start_at=start_at,
                end_at=end_at,
            )

        def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
            raise RuntimeError("Google Calendar event deletion failed: already deleted")

        def build_authorization_url(self, state: str) -> str:  # pragma: no cover - unused in this test
            return state

        def exchange_code(self, code: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def refresh_access_token(self, refresh_token: str):  # pragma: no cover - unused in this test
            raise NotImplementedError

        def list_calendars(self, access_token: str):  # pragma: no cover - unused in this test
            return []

        def get_free_busy(self, access_token: str, calendar_ids: list[str], time_min: datetime, time_max: datetime):  # pragma: no cover - unused in this test
            return []

    app.state.google_calendar_client = FakeGoogleClient()

    organizer = _create_user(client, "Coach Delete Fail", "coach-delete-fail@example.com")
    dancer = _create_user(client, "Delete Fail Dancer", "delete-fail-dancer@example.com")
    _add_availability(client, dancer["id"], "2026-04-11T08:00:00Z", "2026-04-11T12:00:00Z")

    session = app.state.session_factory()
    try:
        session.add(
            CalendarConnection(
                user_id=organizer["id"],
                provider="google",
                status="configured",
                access_token="live-token",
                scopes="https://www.googleapis.com/auth/calendar",
                token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                selected_busy_calendar_ids_json=["primary"],
                selected_write_calendar_id="primary",
            )
        )
        session.commit()
    finally:
        session.close()

    event = _create_event(
        client,
        name="Delete Fail Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-11T12:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    planning_run = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-11T08:00:00Z",
        horizon_end="2026-04-11T12:00:00Z",
    ).json()
    result_id = planning_run["results"][0]["recommendations"][0]["id"]

    confirm_response = client.post(
        f"/api/v1/planning-runs/{planning_run['id']}/confirm",
        json={"result_ids": [result_id]},
    )
    assert confirm_response.status_code == 200
    practice_session = confirm_response.json()["confirmed_sessions"][0]

    delete_response = client.delete(f"/api/v1/practices/{practice_session['id']}/schedule")
    assert delete_response.status_code == 200
    assert delete_response.json()["unscheduled"] is True
    assert delete_response.json()["google_event_deleted"] is False
    assert "already deleted" in delete_response.json()["warning"]

    sessions_response = client.get(f"/api/v1/events/{event['id']}/sessions")
    assert sessions_response.status_code == 200
    assert sessions_response.json() == []


def _create_user(
    client,
    display_name: str,
    email: str,
    preferred_practice_time: str | None = None,
    preferred_practice_time_raw: str | None = None,
) -> dict:
    payload = {
        "display_name": display_name,
        "timezone": "UTC",
        "email": email,
    }
    if preferred_practice_time is not None:
        payload["preferred_practice_time"] = preferred_practice_time
    if preferred_practice_time_raw is not None:
        payload["preferred_practice_time_raw"] = preferred_practice_time_raw

    response = client.post(
        "/api/v1/users",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def _add_availability(client, user_id: str, start_at: str, end_at: str) -> None:
    response = client.post(
        f"/api/v1/users/{user_id}/availability",
        json={"start_at": start_at, "end_at": end_at},
    )
    assert response.status_code == 201


def _create_event(
    client,
    name: str,
    organizer_user_id: str,
    duration_minutes: int,
    latest_schedule_at: str,
    required_session_count: int,
    participants: list[dict],
    earliest_start_date: str | None = None,
    min_days_apart: int = 0,
) -> dict:
    response = client.post(
        "/api/v1/events",
        json={
            "name": name,
            "description": None,
            "organizer_user_id": organizer_user_id,
            "duration_minutes": duration_minutes,
            "earliest_start_date": earliest_start_date,
            "min_days_apart": min_days_apart,
            "latest_schedule_at": latest_schedule_at,
            "required_session_count": required_session_count,
            "participants": participants,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_planning_run(client, event_ids: list[str], horizon_start: str, horizon_end: str):
    return client.post(
        "/api/v1/planning-runs",
        json={
            "event_ids": event_ids,
            "horizon_start": horizon_start,
            "horizon_end": horizon_end,
            "slot_step_minutes": 60,
        },
    )
