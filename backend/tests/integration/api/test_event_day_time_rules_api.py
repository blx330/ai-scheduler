"""Organizer day/time rules stored on an event: persisted, enforced by the planner,
and re-enforced when a session is confirmed with a manual time override."""

from tests.integration.api.test_planning_api import (
    _add_availability,
    _create_event,
    _create_planning_run,
    _create_user,
)

# 2026-04-01 is a Wednesday, 2026-04-02 a Thursday. Every user here is in UTC.


def _event_with_dancer(client, availability: list[tuple[str, str]]) -> dict:
    organizer = _create_user(client, "Coach Rules", "coach-rules@example.com")
    dancer = _create_user(client, "Rules Dancer", "rules-dancer@example.com")
    for start_at, end_at in availability:
        _add_availability(client, dancer["id"], start_at, end_at)
    return _create_event(
        client,
        name="Rules Dance",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at="2026-04-03T00:00:00Z",
        required_session_count=1,
        participants=[{"user_id": dancer["id"], "role": "required"}],
    )


def _patch_rules(client, event_id: str, **rules):
    return client.patch(f"/api/v1/events/{event_id}", json=rules)


def test_new_event_has_no_day_time_rules(client) -> None:
    event = _event_with_dancer(client, [])

    assert event["allowed_weekdays"] == []
    assert event["blocked_weekdays"] == []
    assert event["earliest_start_time"] is None
    assert event["latest_end_time"] is None


def test_patch_persists_day_time_rules(client) -> None:
    event = _event_with_dancer(client, [])

    response = _patch_rules(
        client,
        event["id"],
        blocked_weekdays=["FRI"],
        allowed_weekdays=["WED", "THU"],
        earliest_start_time="18:00",
        latest_end_time="00:00",
    )

    assert response.status_code == 200
    body = client.get(f"/api/v1/events/{event['id']}").json()
    assert body["allowed_weekdays"] == ["WED", "THU"]
    assert body["blocked_weekdays"] == ["FRI"]
    assert body["earliest_start_time"] == "18:00:00"
    assert body["latest_end_time"] == "00:00:00"


def test_patch_can_clear_rules(client) -> None:
    event = _event_with_dancer(client, [])
    _patch_rules(client, event["id"], blocked_weekdays=["FRI"], earliest_start_time="18:00")

    response = _patch_rules(client, event["id"], blocked_weekdays=[], earliest_start_time=None)

    assert response.status_code == 200
    assert response.json()["blocked_weekdays"] == []
    assert response.json()["earliest_start_time"] is None


def test_patch_rejects_a_day_both_allowed_and_blocked(client) -> None:
    event = _event_with_dancer(client, [])

    response = _patch_rules(client, event["id"], allowed_weekdays=["FRI"], blocked_weekdays=["FRI"])

    assert response.status_code == 400
    assert "both allowed and blocked: FRI" in response.json()["detail"]


def test_patch_rejects_earliest_after_latest_even_across_two_requests(client) -> None:
    event = _event_with_dancer(client, [])
    assert _patch_rules(client, event["id"], latest_end_time="18:00").status_code == 200

    response = _patch_rules(client, event["id"], earliest_start_time="20:00")

    assert response.status_code == 400
    assert "must be before latest end" in response.json()["detail"]


def test_planning_run_skips_blocked_weekday(client) -> None:
    event = _event_with_dancer(
        client,
        [("2026-04-01T18:00:00Z", "2026-04-01T20:00:00Z"), ("2026-04-02T18:00:00Z", "2026-04-02T20:00:00Z")],
    )
    _patch_rules(client, event["id"], blocked_weekdays=["WED"])

    run = _create_planning_run(
        client, event_ids=[event["id"]], horizon_start="2026-04-01T08:00:00Z", horizon_end="2026-04-03T00:00:00Z"
    ).json()

    starts = [item["start_at"] for group in run["results"] for item in group["recommendations"]]
    assert starts
    assert all(start.startswith("2026-04-02") for start in starts)


def _single_result_run(client, **rules):
    event = _event_with_dancer(
        client,
        [("2026-04-01T18:00:00Z", "2026-04-01T20:00:00Z"), ("2026-04-02T18:00:00Z", "2026-04-02T20:00:00Z")],
    )
    _patch_rules(client, event["id"], **rules)
    run = _create_planning_run(
        client, event_ids=[event["id"]], horizon_start="2026-04-01T08:00:00Z", horizon_end="2026-04-03T00:00:00Z"
    ).json()
    return run, run["results"][0]["recommendations"][0]["id"]


def _confirm_override(client, run: dict, result_id: str, start_at: str, end_at: str):
    return client.post(
        f"/api/v1/planning-runs/{run['id']}/confirm",
        json={"confirmations": [{"result_id": result_id, "start_at": start_at, "end_at": end_at}]},
    )


def test_confirm_rejects_override_onto_a_blocked_weekday(client) -> None:
    run, result_id = _single_result_run(client, blocked_weekdays=["WED"])

    response = _confirm_override(client, run, result_id, "2026-04-01T18:00:00Z", "2026-04-01T19:00:00Z")

    assert response.status_code == 400
    assert "WED" in response.json()["detail"]


def test_confirm_rejects_override_outside_the_time_window(client) -> None:
    run, result_id = _single_result_run(client, earliest_start_time="18:00", latest_end_time="20:00")

    response = _confirm_override(client, run, result_id, "2026-04-02T10:00:00Z", "2026-04-02T11:00:00Z")

    assert response.status_code == 400
    assert "18:00" in response.json()["detail"] and "20:00" in response.json()["detail"]


def test_confirm_accepts_override_that_obeys_the_rules(client) -> None:
    run, result_id = _single_result_run(client, blocked_weekdays=["WED"], earliest_start_time="18:00")

    response = _confirm_override(client, run, result_id, "2026-04-02T19:00:00Z", "2026-04-02T20:00:00Z")

    assert response.status_code == 200
