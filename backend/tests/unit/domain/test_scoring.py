from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.availability.models import Interval
from app.domain.preferences.models import ParsedPreference
from app.domain.scheduling.models import ParticipantContext, ScheduleSlot
from app.domain.scheduling.scoring import preference_bonus_for_user, score_slot, score_time_tier


def test_preference_bonus_caps_to_one_signal_per_category() -> None:
    slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=UTC),
    )
    preference = ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": "UTC",
            "preferred_weekdays": ["MON", "TUE"],
            "disallowed_weekdays": [],
            "preferred_time_ranges": [
                {"start_local": "09:00", "end_local": "12:00", "weight": 1.0},
                {"start_local": "10:00", "end_local": "11:30", "weight": 1.0},
            ],
            "disallowed_time_ranges": [],
        }
    )

    score, signals = preference_bonus_for_user(slot, preference, "UTC")

    assert score == 1.75
    assert signals == 2.0


def test_score_slot_counts_optional_and_preference_bonuses() -> None:
    slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=UTC),
    )
    preference = ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": "UTC",
            "preferred_weekdays": ["MON"],
            "disallowed_weekdays": [],
            "preferred_time_ranges": [{"start_local": "09:00", "end_local": "12:00", "weight": 1.0}],
            "disallowed_time_ranges": [],
        }
    )
    participants = [
        ParticipantContext(
            user_id=uuid4(),
            role="required",
            timezone="UTC",
            effective_availability=[Interval(slot.start_at, slot.end_at)],
            preference=preference,
        ),
        ParticipantContext(
            user_id=uuid4(),
            role="optional",
            timezone="UTC",
            effective_availability=[Interval(slot.start_at, slot.end_at)],
            preference=None,
        ),
    ]

    result = score_slot(slot, participants)

    assert result.total_score == 4.25
    assert result.optional_available_count == 1
    assert result.score_breakdown["optional_attendees"] == 1.5
    assert result.score_breakdown["preference_bonus"] == 1.75
    assert result.score_breakdown["time_tier_bonus"] == 1.0


def test_time_tier_scoring_prioritizes_evening_slots() -> None:
    tier_1_slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 18, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 19, 0, tzinfo=UTC),
    )
    tier_2_slot_afternoon = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 16, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 17, 0, tzinfo=UTC),
    )
    late_evening_slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 22, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 23, 0, tzinfo=UTC),
    )
    tier_3_slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=UTC),
    )

    assert score_time_tier(tier_1_slot, "UTC") == 6.0
    assert score_time_tier(tier_2_slot_afternoon, "UTC") == 3.0
    assert score_time_tier(late_evening_slot, "UTC") == 5.0
    assert score_time_tier(tier_3_slot, "UTC") == 1.0


def test_late_evening_ranks_just_below_prime_evening_and_above_afternoon() -> None:
    """Students have class during the day, so 10 PM-12 AM is a close second to 6-10 PM
    and must beat both 4-6 PM and daytime."""
    prime = score_time_tier(_ny_slot(19, 120), NY)
    late = score_time_tier(_ny_slot(22, 120), NY)
    afternoon = score_time_tier(_ny_slot(16, 120), NY)
    daytime = score_time_tier(_ny_slot(10, 120), NY)

    assert prime > late > afternoon > daytime


NY = "America/New_York"


def _ny_slot(start_hour: int, duration_minutes: int, day: int = 23) -> ScheduleSlot:
    """A slot expressed in New York wall-clock time."""
    start = datetime(2026, 3, day, start_hour, 0, tzinfo=ZoneInfo(NY)).astimezone(UTC)
    return ScheduleSlot.from_start(start, duration_minutes)


def test_time_tier_scoring_is_monotonic_across_tier_boundaries() -> None:
    """A slot straddling two tiers must score between them, never below both."""
    afternoon = score_time_tier(_ny_slot(16, 120), NY)  # fully in the 16-18 tier
    straddling = score_time_tier(_ny_slot(17, 120), NY)  # half 16-18, half 18-22
    evening = score_time_tier(_ny_slot(18, 120), NY)  # fully in the 18-22 tier

    assert afternoon < straddling < evening

    # a prime-evening slot must not be scored as the worst tier
    assert score_time_tier(_ny_slot(21, 120), NY) > score_time_tier(_ny_slot(9, 120), NY)
    assert score_time_tier(_ny_slot(19, 240), NY) > score_time_tier(_ny_slot(9, 240), NY)


def test_preferred_range_does_not_match_a_slot_ending_at_midnight() -> None:
    """A 21:00-00:00 slot must not count as matching an 08:00-12:00 morning preference."""
    preference = ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": NY,
            "preferred_weekdays": [],
            "disallowed_weekdays": [],
            "preferred_time_ranges": [{"start_local": "08:00", "end_local": "12:00", "weight": 1.0}],
            "disallowed_time_ranges": [],
        }
    )

    score, signals = preference_bonus_for_user(_ny_slot(21, 180), preference, NY)

    assert score == 0.0
    assert signals == 0.0


def test_disallowed_range_is_penalized_for_a_slot_ending_at_midnight() -> None:
    preference = ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": NY,
            "preferred_weekdays": [],
            "disallowed_weekdays": [],
            "preferred_time_ranges": [],
            "disallowed_time_ranges": [{"start_local": "23:30", "end_local": "23:45", "weight": 1.0}],
        }
    )

    score, signals = preference_bonus_for_user(_ny_slot(23, 60), preference, NY)

    assert score == -1.0
    assert signals == 1.0


def _slot(start_hour: int, end_hour: int) -> ScheduleSlot:
    return ScheduleSlot(
        start_at=datetime(2026, 3, 23, start_hour, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, end_hour, 0, tzinfo=UTC),
    )


def _interval(start_hour: int, end_hour: int) -> Interval:
    return Interval(datetime(2026, 3, 23, start_hour, 0, tzinfo=UTC), datetime(2026, 3, 23, end_hour, 0, tzinfo=UTC))


def test_unavailable_participant_status_says_why() -> None:
    """A flag has to name a cause a person can check: busy on their calendar,
    already booked for another practice, or simply never declared free then."""
    from app.domain.scheduling.models import BookedInterval

    busy_dancer = ParticipantContext(
        user_id=uuid4(),
        role="required",
        timezone="UTC",
        effective_availability=[],
        declared_availability=[_interval(9, 12)],
        busy_intervals=[_interval(10, 11)],
    )
    booked_dancer = ParticipantContext(
        user_id=uuid4(),
        role="required",
        timezone="UTC",
        effective_availability=[],
        declared_availability=[_interval(9, 12)],
        booked_intervals=[BookedInterval(_interval(10, 11), "Hip Hop Set session 2")],
    )
    undeclared_dancer = ParticipantContext(
        user_id=uuid4(),
        role="required",
        timezone="UTC",
        effective_availability=[],
        declared_availability=[_interval(14, 16)],
    )
    free_dancer = ParticipantContext(
        user_id=uuid4(),
        role="optional",
        timezone="UTC",
        effective_availability=[_interval(9, 12)],
        declared_availability=[_interval(9, 12)],
    )

    result = score_slot(_slot(10, 11), [busy_dancer, booked_dancer, undeclared_dancer, free_dancer])
    by_user = {status.user_id: status for status in result.participant_statuses}

    assert by_user[busy_dancer.user_id].reason == "busy"
    assert by_user[booked_dancer.user_id].reason == "booked"
    assert by_user[booked_dancer.user_id].detail == "Hip Hop Set session 2"
    assert by_user[undeclared_dancer.user_id].reason == "not_declared"
    assert by_user[free_dancer.user_id].reason is None
    assert by_user[free_dancer.user_id].model_dump(mode="json") == {
        "user_id": str(free_dancer.user_id),
        "role": "optional",
        "available": True,
        "reason": None,
        "detail": None,
    }


def test_booked_outranks_busy_as_the_stated_reason() -> None:
    """Being booked for another practice is the actionable cause (move that one),
    so it is reported even when the calendar is also busy at that time."""
    from app.domain.scheduling.models import BookedInterval

    dancer = ParticipantContext(
        user_id=uuid4(),
        role="required",
        timezone="UTC",
        effective_availability=[],
        declared_availability=[_interval(9, 12)],
        busy_intervals=[_interval(10, 11)],
        booked_intervals=[BookedInterval(_interval(10, 11), "Showcase session 1")],
    )
    [status] = score_slot(_slot(10, 11), [dancer]).participant_statuses
    assert (status.reason, status.detail) == ("booked", "Showcase session 1")
