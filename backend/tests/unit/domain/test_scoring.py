from datetime import datetime, timezone
from uuid import uuid4

from app.domain.availability.models import Interval
from app.domain.preferences.models import ParsedPreference
from app.domain.scheduling.models import ParticipantContext, ScheduleSlot
from app.domain.scheduling.scoring import preference_bonus_for_user, score_slot


def test_preference_bonus_caps_to_one_signal_per_category() -> None:
    slot = ScheduleSlot(
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=timezone.utc),
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
        start_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 23, 11, 0, tzinfo=timezone.utc),
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

    assert result.total_score == 3.25
    assert result.optional_available_count == 1
    assert result.score_breakdown["optional_attendees"] == 1.5
    assert result.score_breakdown["preference_bonus"] == 1.75
