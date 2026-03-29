from datetime import datetime, time, timezone
from uuid import uuid4

from app.domain.availability.models import Interval
from app.domain.preferences.models import ParsedPreference
from app.domain.scheduling.engine import schedule_meeting
from app.domain.scheduling.models import ParticipantContext, ScheduleInput


def test_schedule_meeting_returns_ranked_top_slots() -> None:
    required_one = uuid4()
    required_two = uuid4()
    optional_user = uuid4()
    slot_start = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
    slot_end = datetime(2026, 3, 23, 12, 0, tzinfo=timezone.utc)
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

    schedule_input = ScheduleInput(
        schedule_request_id=uuid4(),
        title="demo",
        organizer_timezone="UTC",
        duration_minutes=60,
        horizon_start=slot_start,
        horizon_end=slot_end,
        slot_step_minutes=60,
        daily_window_start_local=time(9, 0),
        daily_window_end_local=time(12, 0),
        participants=[
            ParticipantContext(required_one, "required", "UTC", [Interval(slot_start, slot_end)], preference),
            ParticipantContext(required_two, "required", "UTC", [Interval(slot_start, slot_end)], None),
            ParticipantContext(optional_user, "optional", "UTC", [Interval(datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc), datetime(2026, 3, 23, 11, 0, tzinfo=timezone.utc))], None),
        ],
    )

    results = schedule_meeting(schedule_input)

    assert len(results) == 3
    assert results[0].rank == 1
    assert results[0].start_at == datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc)
    assert results[0].optional_available_count == 1
    assert results[1].start_at == datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
