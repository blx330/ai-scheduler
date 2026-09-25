"""HTTP contract for plain-English scheduling: parse returns a review and writes
nothing; only confirm changes the event and runs the planner."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.common.enums import UserRole
from app.domain.scheduling.requests import SchedulingRequest
from app.infrastructure.db.models import Room
from app.infrastructure.integrations.llm.scheduling_request_parser import (
    SchedulingRequestParseError,
    SchedulingRequestUpstreamError,
)
from app.main import create_app
from tests.auth_helpers import log_in
from tests.integration.api.test_planning_api import _add_availability, _create_event, _create_user

TODAY = datetime.now(UTC).date()


class FakeParser:
    version = "fake"

    def __init__(self) -> None:
        self.result: SchedulingRequest | Exception = SchedulingRequest(event_name="Hip Hop")

    def parse(self, text, context):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture()
def parser() -> FakeParser:
    return FakeParser()


@pytest.fixture()
def nl_client(session_factory, settings, parser):
    app = create_app(settings=settings, session_factory=session_factory, scheduling_request_parser=parser)
    with TestClient(app) as test_client:
        log_in(test_client, role=UserRole.ORGANIZER.value)
        yield test_client


@pytest.fixture()
def world(nl_client, session_factory):
    organizer = _create_user(nl_client, "Coach Kim", "coach@example.com")
    maya = _create_user(nl_client, "Maya Chen", "maya@example.com")
    jordan = _create_user(nl_client, "Jordan Lee", "jordan@example.com")
    for user in (maya, jordan):
        for offset in range(1, 15):
            day = TODAY + timedelta(days=offset)
            _add_availability(nl_client, user["id"], f"{day}T18:00:00Z", f"{day}T22:00:00Z")
    event = _create_event(
        nl_client,
        name="Hip Hop",
        organizer_user_id=organizer["id"],
        duration_minutes=60,
        latest_schedule_at=f"{TODAY + timedelta(days=30)}T00:00:00Z",
        required_session_count=1,
        participants=[{"user_id": maya["id"], "role": "required"}],
    )
    session = session_factory()
    session.add(Room(name="Studio B", is_active=True))
    session.commit()
    session.close()
    return {"event": event, "maya": maya, "jordan": jordan}


def _example(**overrides) -> SchedulingRequest:
    return SchedulingRequest.model_validate(
        {
            "event_name": "Hip Hop",
            "session_count": 3,
            "latest_date": str(TODAY + timedelta(days=14)),
            "min_days_between": 2,
            "required_attendees": ["Maya Chen", "Jordan Lee"],
            "blocked_weekdays": ["FRI"],
            "room": "Studio B",
            **overrides,
        }
    )


def _parse(client, text: str = "Schedule 3 Hip Hop rehearsals"):
    return client.post("/api/v1/scheduling-requests/parse", json={"text": text})


def test_parse_returns_a_review_and_changes_nothing(nl_client, world, parser) -> None:
    parser.result = _example()

    response = _parse(nl_client)

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"]["session_count"] == 3
    assert body["proposal"]["blocked_weekdays"] == ["FRI"]
    assert body["room"]["name"] == "Studio B"
    assert {item["display_name"]: item["change"] for item in body["participants"]} == {
        "Jordan Lee": "added",
        "Maya Chen": "unchanged",
    }
    event = nl_client.get(f"/api/v1/events/{world['event']['id']}").json()
    assert event["required_session_count"] == 1
    assert event["blocked_weekdays"] == []


def test_confirm_updates_the_event_and_returns_a_planning_run(nl_client, world, parser) -> None:
    parser.result = _example()
    proposal = _parse(nl_client).json()["proposal"]

    response = nl_client.post("/api/v1/scheduling-requests/confirm", json=proposal)

    assert response.status_code == 200
    body = response.json()
    run = body["planning_run"]
    assert run["status"] == "completed"
    top = [group["recommendations"][0] for group in run["results"] if group["recommendations"]]
    assert len(top) == 3
    days = sorted(date.fromisoformat(item["start_at"][:10]) for item in top)
    assert all(day.weekday() != 4 for day in days)
    assert all((b - a).days >= 2 for a, b in zip(days, days[1:], strict=False))
    event = nl_client.get(f"/api/v1/events/{world['event']['id']}").json()
    assert event["required_session_count"] == 3
    assert event["min_days_apart"] == 2
    assert event["blocked_weekdays"] == ["FRI"]


def test_rejection_lists_every_problem(nl_client, world, parser) -> None:
    parser.result = _example(required_attendees=["Maia"], room="Studio Z")

    response = _parse(nl_client)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"].startswith("Nothing was changed.")
    assert len(detail["errors"]) == 2
    assert detail["errors"][0].startswith('Unknown member "Maia"')
    assert detail["errors"][1].startswith('Unknown room "Studio Z"')


def test_invalid_model_output_is_a_loud_422(nl_client, world, parser) -> None:
    parser.result = SchedulingRequestParseError("The model's response was not valid JSON.", raw_output="oops")

    response = _parse(nl_client)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "not valid JSON" in detail["errors"][0]
    assert "oops" not in response.text


def test_upstream_failure_is_a_502(nl_client, world, parser) -> None:
    parser.result = SchedulingRequestUpstreamError("Gemini request failed: 503 overloaded")

    response = _parse(nl_client)

    assert response.status_code == 502
    assert "try again" in response.json()["detail"]["message"].lower()


def test_without_api_key_parse_is_503_not_a_stub(client) -> None:
    response = _parse(client)

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]["message"]


def test_confirm_rejects_tampered_proposal(nl_client, world, parser) -> None:
    parser.result = _example()
    proposal = _parse(nl_client).json()["proposal"]
    proposal["latest_date"] = str(TODAY - timedelta(days=1))

    response = nl_client.post("/api/v1/scheduling-requests/confirm", json=proposal)

    assert response.status_code == 422
    assert "in the past" in response.json()["detail"]["errors"][0]
    event = nl_client.get(f"/api/v1/events/{world['event']['id']}").json()
    assert event["required_session_count"] == 1


def test_confirm_rejects_unknown_fields(nl_client, world, parser) -> None:
    proposal = _parse(nl_client).json()["proposal"]

    response = nl_client.post("/api/v1/scheduling-requests/confirm", json={**proposal, "duration_minutes": 5})

    assert response.status_code == 422


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_parse_rejects_empty_or_oversized_text(nl_client, text: str) -> None:
    assert _parse(nl_client, text).status_code == 422


def test_members_cannot_use_scheduling_requests(nl_client, world) -> None:
    log_in(nl_client, role=UserRole.MEMBER.value)

    assert _parse(nl_client).status_code == 403
    assert nl_client.post("/api/v1/scheduling-requests/confirm", json={}).status_code == 403


def test_anonymous_users_cannot_use_scheduling_requests(anon_client) -> None:
    assert _parse(anon_client).status_code == 401
