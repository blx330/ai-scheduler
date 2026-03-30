from datetime import datetime, timezone
from uuid import uuid4

from app.infrastructure.db.models import UserParsedPreference, UserPreferenceInput


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


def test_late_night_penalty_changes_slot_ranking(client, app) -> None:
    organizer = _create_user(client, "Coach Night", "coach-night@example.com")
    dancer = _create_user(client, "Night Owl", "night-owl@example.com")
    _add_availability(client, dancer["id"], "2026-04-05T20:00:00Z", "2026-04-05T23:00:00Z")
    _insert_preference(
        app,
        user_id=dancer["id"],
        preference_input_id=uuid4(),
        preferred_time_ranges=[{"start_local": "22:00", "end_local": "23:00", "weight": 1.0}],
    )

    event = _create_event(
        client,
        name="Late Night Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-05T23:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )

    response = _create_planning_run(
        client,
        event_ids=[event["id"]],
        horizon_start="2026-04-05T20:00:00Z",
        horizon_end="2026-04-05T23:00:00Z",
    )

    assert response.status_code == 200
    recommendations = response.json()["results"][0]["recommendations"]
    assert recommendations[0]["start_at"] == "2026-04-05T20:00:00Z"
    late_slot = next(item for item in recommendations if item["start_at"] == "2026-04-05T22:00:00Z")
    assert late_slot["score_breakdown"]["late_night_penalty"] == -1.0


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


def _create_user(client, display_name: str, email: str) -> dict:
    response = client.post(
        "/api/v1/users",
        json={"display_name": display_name, "timezone": "UTC", "email": email},
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
) -> dict:
    response = client.post(
        "/api/v1/events",
        json={
            "name": name,
            "description": None,
            "organizer_user_id": organizer_user_id,
            "duration_minutes": duration_minutes,
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


def _insert_preference(app, user_id: str, preference_input_id, preferred_time_ranges: list[dict]) -> None:
    session = app.state.session_factory()
    try:
        input_row = UserPreferenceInput(
            id=preference_input_id,
            user_id=user_id,
            raw_text="prefer late slot",
            status="parsed",
            parser_version="test-v1",
            parsed_at=datetime.now(timezone.utc),
        )
        parsed_row = UserParsedPreference(
            preference_input_id=input_row.id,
            user_id=user_id,
            schema_version="1.0",
            timezone="UTC",
            constraints_json={
                "schema_version": "1.0",
                "timezone": "UTC",
                "preferred_weekdays": [],
                "disallowed_weekdays": [],
                "preferred_time_ranges": preferred_time_ranges,
                "disallowed_time_ranges": [],
                "notes": "test",
            },
        )
        session.add(input_row)
        session.add(parsed_row)
        session.commit()
    finally:
        session.close()
