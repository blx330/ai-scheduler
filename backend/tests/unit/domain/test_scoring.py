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
    tier_2_slot_late = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 22, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 23, 0, tzinfo=UTC),
    )
    tier_3_slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=UTC),
    )

    assert score_time_tier(tier_1_slot, "UTC") == 6.0
    assert score_time_tier(tier_2_slot_afternoon, "UTC") == 3.0
    assert score_time_tier(tier_2_slot_late, "UTC") == 3.0
    assert score_time_tier(tier_3_slot, "UTC") == 1.0


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
