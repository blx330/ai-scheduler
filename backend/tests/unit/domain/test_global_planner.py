from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.availability.models import Interval
from app.domain.scheduling.global_planner import PlanningEventInput, plan_practice_sessions
from app.domain.scheduling.models import ParticipantContext

ORGANIZER_TZ = "America/New_York"
ZONE = ZoneInfo(ORGANIZER_TZ)


def _utc(hour: int, minute: int = 0, day: int = 10) -> datetime:
    """A wall-clock time in the organizer's timezone, as UTC."""
    return datetime(2026, 6, day, hour, minute, tzinfo=ZONE).astimezone(timezone.utc)


def _local_hhmm(value: datetime) -> str:
    return value.astimezone(ZONE).strftime("%H:%M")


def _participant(role: str, availability: list[Interval]) -> ParticipantContext:
    return ParticipantContext(
        user_id=uuid4(),
        role=role,
        timezone=ORGANIZER_TZ,
        effective_availability=availability,
        preference=None,
    )


def _event(participants: list[ParticipantContext], **overrides) -> PlanningEventInput:
    defaults = dict(
        dance_event_id=uuid4(),
        dance_name="Waltz",
        organizer_user_id=participants[0].user_id,
        organizer_timezone=ORGANIZER_TZ,
        organizer_preference=None,
        duration_minutes=60,
        earliest_start_date=None,
        min_days_apart=0,
        latest_schedule_at=_utc(0, 0, day=11),
        pending_session_indices=(1,),
        confirmed_session_starts=[],
        participants=participants,
    )
    defaults.update(overrides)
    return PlanningEventInput(**defaults)


def _plan(event: PlanningEventInput, max_results: int = 3):
    return plan_practice_sessions(
        events=[event],
        fixed_reservations=[],
        room_id=uuid4(),
        planning_horizon_start=_utc(8),
        planning_horizon_end=_utc(0, 0, day=11),
        slot_step_minutes=30,
        max_results_per_session=max_results,
    )


def test_feasible_slot_outranks_fallback_even_in_a_lower_time_tier() -> None:
    """A slot where every required dancer can attend must never be outranked by a
    fallback, even when the fallback sits in a higher-scoring time tier."""
    # The only overlap is 09:00-10:00 (a low-scoring morning tier). Dancer B is also
    # free 18:00-19:00, which is the top-scoring evening tier but infeasible for A.
    dancer_a = _participant("required", [Interval(_utc(9), _utc(10))])
    dancer_b = _participant("required", [Interval(_utc(9), _utc(10)), Interval(_utc(18), _utc(19))])

    recommendations = _plan(_event([dancer_a, dancer_b]))

    assert recommendations, "planner returned nothing"
    top = recommendations[0]
    assert _local_hhmm(top.start_at) == "09:00"
    assert top.is_fallback is False
    assert top.missing_required_user_ids == []


def test_fallbacks_never_displace_feasible_slots_in_the_result_list() -> None:
    dancer_a = _participant("required", [Interval(_utc(9), _utc(10))])
    dancer_b = _participant("required", [Interval(_utc(9), _utc(10)), Interval(_utc(18), _utc(19))])

    recommendations = _plan(_event([dancer_a, dancer_b]))

    feasible = [item for item in recommendations if not item.is_fallback]
    assert len(feasible) == 1
    # every fallback must rank below every feasible option
    first_fallback = next((i for i, r in enumerate(recommendations) if r.is_fallback), len(recommendations))
    last_feasible = max(i for i, r in enumerate(recommendations) if not r.is_fallback)
    assert last_feasible < first_fallback


def test_fallbacks_never_drop_more_than_one_required_participant() -> None:
    """A slot nobody can attend is noise, not a recommendation."""
    dancer_a = _participant("required", [Interval(_utc(9), _utc(10))])
    dancer_b = _participant("required", [Interval(_utc(9), _utc(10))])
    dancer_c = _participant("required", [Interval(_utc(9), _utc(10)), Interval(_utc(18), _utc(19))])

    recommendations = _plan(_event([dancer_a, dancer_b, dancer_c]))

    for item in recommendations:
        assert len(item.missing_required_user_ids) <= 1, (
            f"{_local_hhmm(item.start_at)} drops {len(item.missing_required_user_ids)} required participants"
        )


def test_fallback_explanation_matches_the_actual_missing_count() -> None:
    dancer_a = _participant("required", [Interval(_utc(9), _utc(10))])
    dancer_b = _participant("required", [Interval(_utc(9), _utc(10)), Interval(_utc(18), _utc(19))])

    recommendations = _plan(_event([dancer_a, dancer_b]))

    fallbacks = [item for item in recommendations if item.is_fallback]
    assert fallbacks, "expected at least one fallback in this scenario"
    for item in fallbacks:
        reason = next(r for r in item.explanation["reasons"] if r["code"] == "fallback_missing_required")
        assert len(reason["missing_required_user_ids"]) == len(item.missing_required_user_ids)
        # the message must not claim a feasible slot was unavailable when one exists
        assert "No fully feasible slot was found" not in reason["message"]


def test_planner_plans_the_gap_when_a_later_session_is_already_confirmed() -> None:
    """Confirming session 2 before session 1 must leave session 1 plannable."""
    dancer = _participant("required", [Interval(_utc(9), _utc(0, 0, day=11))])
    event = _event([dancer], pending_session_indices=(1,))

    recommendations = _plan(event)

    assert recommendations
    assert {item.session_index for item in recommendations} == {1}


def test_planner_uses_actual_pending_indices_not_a_contiguous_range() -> None:
    dancer = _participant("required", [Interval(_utc(9), _utc(0, 0, day=11))])
    # sessions 1 and 3 pending, session 2 already confirmed
    event = _event([dancer], pending_session_indices=(1, 3), min_days_apart=0)

    recommendations = _plan(event)

    assert {item.session_index for item in recommendations} == {1, 3}


def test_optional_attendee_is_not_counted_as_free_for_two_events_at_once() -> None:
    """A person booked into one event's slot cannot also be scored as an available
    optional for another event at the same time."""
    room = uuid4()
    # Only one hour is available to anyone, so both events must contend for it.
    window = [Interval(_utc(18), _utc(19))]
    shared = _participant("required", window)
    optional_shared = ParticipantContext(
        user_id=shared.user_id,
        role="optional",
        timezone=ORGANIZER_TZ,
        effective_availability=window,
        preference=None,
    )
    other_required = _participant("required", window)

    first = _event([shared], dance_name="Alpha", latest_schedule_at=_utc(0, 0, day=11))
    second = _event([other_required, optional_shared], dance_name="Beta", latest_schedule_at=_utc(0, 0, day=11))

    recommendations = plan_practice_sessions(
        events=[first, second],
        fixed_reservations=[],
        room_id=room,
        planning_horizon_start=_utc(8),
        planning_horizon_end=_utc(0, 0, day=11),
        slot_step_minutes=60,
        max_results_per_session=1,
    )

    by_event = {item.dance_name: item for item in recommendations}
    if "Alpha" in by_event and "Beta" in by_event:
        alpha, beta = by_event["Alpha"], by_event["Beta"]
        overlapping = alpha.start_at < beta.end_at and alpha.end_at > beta.start_at
        if overlapping:
            assert beta.optional_available_count == 0, (
                "shared person was counted as an available optional while booked elsewhere"
            )


def test_late_night_penalty_applies_to_slots_ending_at_midnight() -> None:
    """Midnight is the latest end the practice window allows, so it must not escape
    the penalty just because its local hour wraps to 0."""
    from app.domain.scheduling.global_planner import LATE_NIGHT_PENALTY, _late_night_penalty
    from app.domain.scheduling.models import ScheduleSlot

    def penalty(start_hour: int, duration_minutes: int) -> float:
        return _late_night_penalty(ScheduleSlot.from_start(_utc(start_hour), duration_minutes), ZONE)

    assert penalty(21, 180) == LATE_NIGHT_PENALTY  # 21:00-00:00
    assert penalty(20, 240) == LATE_NIGHT_PENALTY  # 20:00-00:00
    assert penalty(22, 120) == LATE_NIGHT_PENALTY  # 22:00-00:00
    assert penalty(21, 120) == LATE_NIGHT_PENALTY  # 21:00-23:00
    # ending exactly at 22:00 is not late night
    assert penalty(20, 120) == 0.0
    assert penalty(18, 120) == 0.0


def test_fallback_penalty_scales_with_the_number_of_missing_participants() -> None:
    from app.domain.scheduling.global_planner import _build_scoring_metadata

    event = _event([_participant("required", [Interval(_utc(9), _utc(10))])])
    common = dict(
        slot=None,
        event=event,
        reservations=[],
        base_score_breakdown={},
        optional_available_count=0,
    )
    from app.domain.scheduling.models import ScheduleSlot

    common["slot"] = ScheduleSlot.from_start(_utc(18), 60)

    one_missing, _ = _build_scoring_metadata(missing_required_user_ids=[uuid4()], **common)
    two_missing, _ = _build_scoring_metadata(missing_required_user_ids=[uuid4(), uuid4()], **common)

    assert two_missing["fallback_penalty"] < one_missing["fallback_penalty"] < 0
