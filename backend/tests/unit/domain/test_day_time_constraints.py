from datetime import UTC, datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domain.availability.models import Interval
from app.domain.common.enums import Weekday
from app.domain.scheduling.constraints import DayTimeConstraints
from app.domain.scheduling.global_planner import PlanningEventInput, plan_practice_sessions
from app.domain.scheduling.models import ParticipantContext, ScheduleSlot

ORGANIZER_TZ = "America/New_York"
ZONE = ZoneInfo(ORGANIZER_TZ)
# 2026-06-10 is a Wednesday; 12 is a Friday, 13 a Saturday.
WED, THU, FRI, SAT = 10, 11, 12, 13


def _utc(hour: int, minute: int = 0, day: int = WED) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=ZONE).astimezone(UTC)


def _slot(day: int, hour: int, duration_minutes: int = 60) -> ScheduleSlot:
    return ScheduleSlot.from_start(_utc(hour, day=day), duration_minutes)


def _participant(role: str, availability: list[Interval]) -> ParticipantContext:
    return ParticipantContext(
        user_id=uuid4(), role=role, timezone=ORGANIZER_TZ, effective_availability=availability, preference=None
    )


def _whole_days(*days: int) -> list[Interval]:
    return [Interval(_utc(8, day=day), _utc(0, day=day + 1)) for day in days]


def _event(participants: list[ParticipantContext], constraints: DayTimeConstraints, **overrides) -> PlanningEventInput:
    defaults = dict(
        dance_event_id=uuid4(),
        dance_name="Hip Hop",
        organizer_user_id=participants[0].user_id,
        organizer_timezone=ORGANIZER_TZ,
        organizer_preference=None,
        duration_minutes=60,
        earliest_start_date=None,
        min_days_apart=0,
        latest_schedule_at=_utc(0, day=SAT + 2),
        pending_session_indices=(1,),
        confirmed_session_starts=[],
        participants=participants,
        day_time_constraints=constraints,
    )
    defaults.update(overrides)
    return PlanningEventInput(**defaults)


def _plan(event: PlanningEventInput, max_results: int = 20):
    return plan_practice_sessions(
        events=[event],
        fixed_reservations=[],
        room_id=uuid4(),
        planning_horizon_start=_utc(8, day=WED),
        planning_horizon_end=_utc(0, day=SAT + 2),
        slot_step_minutes=60,
        max_results_per_session=max_results,
    )


# --- value object ---------------------------------------------------------------


def test_unconstrained_permits_everything() -> None:
    assert DayTimeConstraints().rejection_reason(_slot(FRI, 9), ZONE) is None
    assert DayTimeConstraints().is_unconstrained


def test_blocked_weekday_rejects_slot_on_that_day() -> None:
    rules = DayTimeConstraints(blocked_weekdays=frozenset({Weekday.FRI}))
    assert rules.rejection_reason(_slot(FRI, 19), ZONE) == "blocked_weekday"
    assert rules.rejection_reason(_slot(SAT, 19), ZONE) is None


def test_allowed_weekdays_reject_every_other_day() -> None:
    rules = DayTimeConstraints(allowed_weekdays=frozenset({Weekday.SAT}))
    assert rules.rejection_reason(_slot(FRI, 19), ZONE) == "weekday_not_allowed"
    assert rules.rejection_reason(_slot(SAT, 19), ZONE) is None


def test_weekday_is_judged_in_organizer_timezone_not_utc() -> None:
    # 22:00 Friday in New York is already Saturday in UTC.
    rules = DayTimeConstraints(blocked_weekdays=frozenset({Weekday.SAT}))
    assert _slot(FRI, 22).start_at.weekday() == 5
    assert rules.rejection_reason(_slot(FRI, 22), ZONE) is None


def test_time_window_requires_whole_slot_inside() -> None:
    rules = DayTimeConstraints(earliest_start_local=time(18, 0), latest_end_local=time(21, 0))
    assert rules.rejection_reason(_slot(WED, 18), ZONE) is None
    assert rules.rejection_reason(_slot(WED, 20), ZONE) is None  # 20:00-21:00, ends exactly at the bound
    assert rules.rejection_reason(_slot(WED, 17), ZONE) == "outside_time_window"
    assert rules.rejection_reason(_slot(WED, 20, 90), ZONE) == "outside_time_window"


def test_latest_end_of_midnight_means_end_of_day() -> None:
    rules = DayTimeConstraints(earliest_start_local=time(22, 0), latest_end_local=time(0, 0))
    assert rules.rejection_reason(_slot(WED, 22, 120), ZONE) is None  # 22:00-00:00
    assert rules.rejection_reason(_slot(WED, 21), ZONE) == "outside_time_window"


def test_only_one_time_bound_is_allowed() -> None:
    earliest_only = DayTimeConstraints(earliest_start_local=time(18, 0))
    latest_only = DayTimeConstraints(latest_end_local=time(12, 0))
    assert earliest_only.rejection_reason(_slot(WED, 23), ZONE) is None
    assert earliest_only.rejection_reason(_slot(WED, 17), ZONE) == "outside_time_window"
    assert latest_only.rejection_reason(_slot(WED, 11), ZONE) is None
    assert latest_only.rejection_reason(_slot(WED, 12), ZONE) == "outside_time_window"


def test_day_both_allowed_and_blocked_is_rejected() -> None:
    with pytest.raises(ValueError, match="both allowed and blocked: FRI"):
        DayTimeConstraints(allowed_weekdays=frozenset({Weekday.FRI, Weekday.SAT}), blocked_weekdays=frozenset({Weekday.FRI}))


def test_earliest_not_before_latest_is_rejected() -> None:
    with pytest.raises(ValueError, match="Earliest start 21:00 must be before latest end 18:00"):
        DayTimeConstraints(earliest_start_local=time(21, 0), latest_end_local=time(18, 0))
    with pytest.raises(ValueError, match="must be before"):
        DayTimeConstraints(earliest_start_local=time(18, 0), latest_end_local=time(18, 0))


# --- planner integration ----------------------------------------------------------


def test_planner_never_recommends_a_blocked_weekday() -> None:
    dancer = _participant("required", _whole_days(FRI, SAT))
    results = _plan(_event([dancer], DayTimeConstraints(blocked_weekdays=frozenset({Weekday.FRI}))))

    assert {item.start_at.astimezone(ZONE).day for item in results if not item.is_fallback} == {SAT}
    assert all(item.start_at.astimezone(ZONE).day != FRI for item in results)


def test_planner_keeps_every_result_inside_the_time_window() -> None:
    dancer = _participant("required", _whole_days(WED))
    rules = DayTimeConstraints(earliest_start_local=time(9, 0), latest_end_local=time(12, 0))
    results = _plan(_event([dancer], rules))

    feasible = [item for item in results if not item.is_fallback]
    assert sorted(item.start_at.astimezone(ZONE).hour for item in feasible) == [9, 10, 11]
    assert all(item.start_at.astimezone(ZONE).hour in {9, 10, 11} for item in results)


def test_fallbacks_also_respect_day_rules() -> None:
    """A fallback may drop one required dancer, but never an organizer's hard rule."""
    both_free_friday = _whole_days(FRI)
    only_a_saturday = _whole_days(FRI, SAT)
    dancer_a = _participant("required", only_a_saturday)
    dancer_b = _participant("required", both_free_friday)
    results = _plan(_event([dancer_a, dancer_b], DayTimeConstraints(blocked_weekdays=frozenset({Weekday.FRI}))))

    assert results
    assert all(item.is_fallback for item in results)
    assert {item.start_at.astimezone(ZONE).day for item in results} == {SAT}


def test_multi_session_lookahead_respects_day_rules() -> None:
    """Two sessions, one day apart minimum, but only Saturday is allowed: impossible."""
    dancer = _participant("required", _whole_days(WED, THU, FRI, SAT))
    event = _event(
        [dancer],
        DayTimeConstraints(allowed_weekdays=frozenset({Weekday.SAT})),
        pending_session_indices=(1, 2),
        min_days_apart=1,
    )

    results = _plan(event)

    assert [item for item in results if item.session_index == 1] == []
