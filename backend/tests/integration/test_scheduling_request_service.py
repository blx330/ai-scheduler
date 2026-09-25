"""SchedulingRequestService: grounds parsed requests in real data and never guesses."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest

from app.api.schemas.scheduling_requests import SchedulingProposal
from app.application.services.scheduling_request_service import (
    SchedulingRequestRejected,
    SchedulingRequestService,
)
from app.domain.common.enums import Weekday
from app.domain.scheduling.requests import SchedulingRequest
from app.infrastructure.db.models import (
    DanceEvent,
    DanceEventParticipant,
    ManualAvailabilityInterval,
    PracticeSession,
    Room,
    User,
)
from app.infrastructure.integrations.llm.scheduling_request_parser import (
    ParseContext,
    SchedulingRequestParseError,
    SchedulingRequestParserUnavailable,
    UnconfiguredSchedulingRequestParser,
)

# Friday 2026-09-25, 12:30 in New York.
NOW = datetime(2026, 9, 25, 16, 30, tzinfo=UTC)
NY = "America/New_York"


class FakeParser:
    version = "fake"

    def __init__(self, result: SchedulingRequest | Exception) -> None:
        self.result = result
        self.contexts: list[ParseContext] = []
        self.texts: list[str] = []

    def parse(self, text: str, context: ParseContext) -> SchedulingRequest:
        self.texts.append(text)
        self.contexts.append(context)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture()
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def world(db):
    organizer = User(display_name="Coach Kim", email="coach@example.com", timezone=NY, role="organizer")
    maya = User(display_name="Maya Chen", email="maya@example.com", timezone=NY)
    jordan = User(display_name="Jordan Lee", email="jordan@example.com", timezone=NY)
    sam = User(display_name="Sam Park", email="sam@example.com", timezone=NY)
    db.add_all([organizer, maya, jordan, sam])
    db.flush()
    event = DanceEvent(
        name="Hip Hop",
        organizer_user_id=organizer.id,
        duration_minutes=60,
        min_days_apart=0,
        latest_schedule_at=datetime(2026, 11, 1, 4, 0, tzinfo=UTC),  # Nov 1 00:00 NY
        required_session_count=1,
    )
    db.add(event)
    db.flush()
    db.add(DanceEventParticipant(dance_event_id=event.id, user_id=sam.id, role="required"))
    studio_a = Room(name="Studio A", is_active=True)
    studio_b = Room(name="Studio B", is_active=True)
    db.add_all([studio_a, studio_b])
    db.commit()
    return {
        "organizer": organizer,
        "maya": maya,
        "jordan": jordan,
        "sam": sam,
        "event": event,
        "studio_b": studio_b,
    }


def _request(**fields) -> SchedulingRequest:
    return SchedulingRequest.model_validate({"event_name": "Hip Hop", **fields})


def _service(db, result) -> tuple[SchedulingRequestService, FakeParser]:
    parser = FakeParser(result)
    return SchedulingRequestService(db, parser, now=lambda: NOW), parser


def _parse(db, **fields):
    service, _ = _service(db, _request(**fields))
    return service.parse("Schedule some Hip Hop rehearsals")


def _rejection(db, **fields) -> list[str]:
    with pytest.raises(SchedulingRequestRejected) as excinfo:
        _parse(db, **fields)
    return excinfo.value.errors


# --- happy path -------------------------------------------------------------------


def test_example_request_resolves_to_ids_and_hard_constraints(db, world) -> None:
    review = _parse(
        db,
        session_count=3,
        latest_date="2026-10-19",
        min_days_between=2,
        required_attendees=["Maya Chen", "Jordan Lee"],
        blocked_weekdays=["FRI"],
        room="Studio B",
    )

    proposal = review.proposal
    assert proposal.event_id == world["event"].id
    assert proposal.session_count == 3
    assert proposal.latest_date == date(2026, 10, 19)
    assert proposal.min_days_apart == 2
    assert proposal.blocked_weekdays == [Weekday.FRI]
    assert proposal.room_id == world["studio_b"].id
    roles = {item.user_id: item.role for item in proposal.participants}
    assert roles == {world["maya"].id: "required", world["jordan"].id: "required", world["sam"].id: "required"}
    assert review.event.name == "Hip Hop"
    assert review.room is not None and review.room.name == "Studio B"
    assert review.sessions_to_plan == 3


def test_parser_is_grounded_on_real_names_and_organizer_today(db, world) -> None:
    service, parser = _service(db, _request())
    service.parse("anything")

    [context] = parser.contexts
    assert context.today == date(2026, 9, 25)
    assert context.event_names == ["Hip Hop"]
    assert context.member_names == ["Coach Kim", "Jordan Lee", "Maya Chen", "Sam Park"]
    assert context.room_names == ["Studio A", "Studio B"]


def test_unstated_fields_keep_the_events_saved_values(db, world) -> None:
    review = _parse(db)

    assert review.proposal.session_count == 1
    assert review.proposal.latest_date == date(2026, 10, 31)
    assert review.proposal.min_days_apart == 0
    assert review.changes == []


def test_review_lists_before_and_after_for_each_change(db, world) -> None:
    review = _parse(db, session_count=3, blocked_weekdays=["FRI"], required_attendees=["Maya Chen"])

    changes = {change.field: (change.before, change.after) for change in review.changes}
    assert changes["session_count"] == ("1", "3")
    assert changes["blocked_weekdays"] == ("none", "FRI")
    participants = {item.display_name: item.change for item in review.participants}
    assert participants == {"Maya Chen": "added", "Sam Park": "unchanged"}


def test_names_match_case_insensitively_and_by_unique_first_name(db, world) -> None:
    review = _parse(db, required_attendees=["maya chen", "Jordan"], room="studio b")

    names = {item.display_name for item in review.participants if item.role == "required"}
    assert names == {"Maya Chen", "Jordan Lee", "Sam Park"}
    assert review.room is not None and review.room.name == "Studio B"


def test_optional_attendee_can_demote_an_existing_required_one(db, world) -> None:
    review = _parse(db, required_attendees=["Maya Chen"], optional_attendees=["Sam Park"])

    sam = next(item for item in review.participants if item.display_name == "Sam Park")
    assert (sam.role, sam.change) == ("optional", "role_changed")


# --- rejections: never guess ---------------------------------------------------------


def test_unknown_event_is_rejected_with_known_names(db, world) -> None:
    errors = _rejection(db, event_name="Salsa")

    assert errors == ['Unknown dance "Salsa". Known dances: Hip Hop.']


def test_unknown_member_and_room_are_all_reported_at_once(db, world) -> None:
    errors = _rejection(db, required_attendees=["Maia"], optional_attendees=["Zed"], room="Studio Z")

    assert 'Unknown member "Maia".' in errors[0]
    assert 'Unknown member "Zed".' in errors[1]
    assert errors[2] == 'Unknown room "Studio Z". Known rooms: Studio A, Studio B.'


def test_ambiguous_first_name_is_rejected_not_guessed(db, world) -> None:
    db.add(User(display_name="Maya Singh", email="maya2@example.com", timezone=NY))
    db.commit()

    errors = _rejection(db, required_attendees=["Maya"])

    assert errors == ['"Maya" matches more than one member (Maya Chen, Maya Singh). Use their full name.']


def test_inactive_room_is_unknown(db, world) -> None:
    world["studio_b"].is_active = False
    db.commit()

    assert _rejection(db, room="Studio B")[0].startswith('Unknown room "Studio B"')


def test_past_dates_are_rejected(db, world) -> None:
    errors = _rejection(db, earliest_date="2026-09-01", latest_date="2026-09-20")

    assert "earliest date 2026-09-01 is in the past (today is 2026-09-25 in America/New_York)." in errors
    assert "latest date 2026-09-20 is in the past (today is 2026-09-25 in America/New_York)." in errors


def test_deadline_beyond_the_planning_horizon_is_rejected(db, world) -> None:
    errors = _rejection(db, latest_date="2027-06-01")

    assert errors == ["latest date 2027-06-01 is more than 179 days away; the planner looks at most 180 days ahead."]


def test_new_earliest_date_after_saved_deadline_is_rejected(db, world) -> None:
    errors = _rejection(db, earliest_date="2026-11-05")

    assert errors == ["earliest date 2026-11-05 is after the latest date 2026-10-31."]


def test_spacing_that_cannot_fit_the_window_is_rejected(db, world) -> None:
    errors = _rejection(db, session_count=3, min_days_between=2, earliest_date="2026-10-17", latest_date="2026-10-19")

    assert errors == [
        "3 sessions at least 2 days apart need at least 5 days, but 2026-10-17 to 2026-10-19 has only 3."
    ]


def test_cannot_drop_below_already_confirmed_sessions(db, world) -> None:
    event = world["event"]
    event.required_session_count = 2
    for index in (1, 2):
        db.add(
            PracticeSession(
                dance_event_id=event.id,
                session_index=index,
                start_at=datetime(2026, 10, index, 22, tzinfo=UTC),
                end_at=datetime(2026, 10, index, 23, tzinfo=UTC),
                status="confirmed",
                room_id=world["studio_b"].id,
            )
        )
    db.commit()

    errors = _rejection(db, session_count=1)

    assert errors == ["Hip Hop already has 2 confirmed sessions, so the total cannot be 1."]


def test_nothing_left_to_plan_is_rejected(db, world) -> None:
    db.add(
        PracticeSession(
            dance_event_id=world["event"].id,
            session_index=1,
            start_at=datetime(2026, 10, 1, 22, tzinfo=UTC),
            end_at=datetime(2026, 10, 1, 23, tzinfo=UTC),
            status="confirmed",
            room_id=world["studio_b"].id,
        )
    )
    db.commit()

    assert _rejection(db) == ["Hip Hop already has all 1 sessions confirmed; ask for a higher total to plan more."]


def test_unsupported_phrases_reject_the_whole_request(db, world) -> None:
    errors = _rejection(db, session_count=3, unsupported_phrases=["evenings"])

    assert errors == [
        'Could not turn "evenings" into a scheduling rule. Rephrase it with explicit days or clock times '
        '(for example "after 6pm" or "no Fridays"), or remove it.'
    ]


def test_missing_event_name_is_rejected(db, world) -> None:
    service, _ = _service(db, SchedulingRequest.model_construct(event_name=""))
    with pytest.raises(SchedulingRequestRejected) as excinfo:
        service.parse("book a room")

    assert excinfo.value.errors == ["Could not tell which dance this request is for. Known dances: Hip Hop."]


def test_parser_errors_propagate_unchanged(db, world) -> None:
    for error in (SchedulingRequestParseError("bad json"), SchedulingRequestParserUnavailable("no key")):
        service, _ = _service(db, error)
        with pytest.raises(type(error)):
            service.parse("anything")


def test_unconfigured_parser_fails_before_any_partial_result(db, world) -> None:
    service = SchedulingRequestService(db, UnconfiguredSchedulingRequestParser(), now=lambda: NOW)

    with pytest.raises(SchedulingRequestParserUnavailable):
        service.parse("anything")


def test_prompt_injection_naming_an_unknown_room_is_rejected(db, world) -> None:
    """Whatever the model is talked into emitting, unknown entities cannot get through."""
    errors = _rejection(db, room="Studio Z; DROP TABLE rooms", required_attendees=["Admin"])

    assert any(error.startswith('Unknown room "Studio Z; DROP TABLE rooms"') for error in errors)
    assert any(error.startswith('Unknown member "Admin"') for error in errors)


# --- confirm ----------------------------------------------------------------------------


def _add_evening_availability(db, users: list[User], days: range) -> None:
    for user in users:
        for day in days:
            # 18:00-22:00 New York (EDT, UTC-4)
            db.add(
                ManualAvailabilityInterval(
                    user_id=user.id,
                    start_at=datetime(2026, 10, day, 22, tzinfo=UTC),
                    end_at=datetime(2026, 10, day + 1, 2, tzinfo=UTC),
                )
            )
    db.commit()


def test_confirm_applies_constraints_and_runs_the_existing_planner(db, world) -> None:
    _add_evening_availability(db, [world["maya"], world["jordan"], world["sam"]], range(1, 20))
    review = _parse(
        db,
        session_count=3,
        latest_date="2026-10-19",
        min_days_between=2,
        required_attendees=["Maya Chen", "Jordan Lee"],
        blocked_weekdays=["FRI"],
        room="Studio B",
    )
    service, _ = _service(db, _request())

    event, run = service.confirm(review.proposal)

    assert event.required_session_count == 3
    assert event.min_days_apart == 2
    assert event.blocked_weekdays_json == ["FRI"]
    assert event.latest_schedule_at.astimezone(UTC) == datetime(2026, 10, 20, 4, tzinfo=UTC)
    assert run.room_id == world["studio_b"].id
    starts = [result.start_at for result in run.results if result.rank == 1]
    assert len(starts) == 3
    from zoneinfo import ZoneInfo

    local = sorted(start.replace(tzinfo=UTC).astimezone(ZoneInfo(NY)) for start in starts)
    assert all(item.weekday() != 4 for item in local)  # no Fridays
    assert all((b.date() - a.date()).days >= 2 for a, b in zip(local, local[1:], strict=False))
    assert all(item.date() <= date(2026, 10, 19) for item in local)
    assert all(item.time() >= time(18, 0) for item in local)  # evenings preferred by tier


def test_confirm_revalidates_instead_of_trusting_the_client(db, world) -> None:
    review = _parse(db, session_count=2)
    tampered = review.proposal.model_copy(update={"room_id": uuid4()})
    service, _ = _service(db, _request())

    with pytest.raises(SchedulingRequestRejected, match="Room not found"):
        service.confirm(tampered)


def test_confirm_rejects_unknown_participant_ids(db, world) -> None:
    review = _parse(db)
    payload = review.proposal.model_dump()
    payload["participants"].append({"user_id": uuid4(), "role": "required"})
    service, _ = _service(db, _request())

    with pytest.raises(SchedulingRequestRejected, match="Unknown member id"):
        service.confirm(SchedulingProposal.model_validate(payload))


def test_confirm_rejects_proposal_that_went_stale(db, world) -> None:
    """A proposal reviewed yesterday for 'today' must not book the past."""
    review = _parse(db, earliest_date="2026-09-25")
    service = SchedulingRequestService(db, FakeParser(_request()), now=lambda: datetime(2026, 9, 27, 16, tzinfo=UTC))

    with pytest.raises(SchedulingRequestRejected, match="earliest date 2026-09-25 is in the past"):
        service.confirm(review.proposal)


def test_request_rules_that_contradict_saved_rules_are_rejected_not_crashed(db, world) -> None:
    world["event"].latest_end_time_local = time(18, 0)
    world["event"].blocked_weekdays_json = ["SAT"]
    db.commit()

    errors = _rejection(db, earliest_start_time="22:00", allowed_weekdays=["SAT"])

    assert errors == [
        "Earliest start 22:00 must be before latest end 18:00 "
        "(the latest end was already saved on Hip Hop; state a new one to replace it).",
        "Days cannot be both allowed and blocked: SAT "
        "(the blocked days were already saved on Hip Hop; state new ones to replace them).",
    ]
