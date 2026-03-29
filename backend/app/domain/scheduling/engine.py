from app.domain.availability.interval_ops import interval_covered
from app.domain.availability.models import Interval
from app.domain.scheduling.candidate_generation import generate_candidate_starts
from app.domain.scheduling.models import ScheduleInput, ScheduleResult, ScheduleSlot
from app.domain.scheduling.scoring import score_slot


def schedule_meeting(schedule_input: ScheduleInput) -> list[ScheduleResult]:
    candidate_starts = generate_candidate_starts(
        horizon_start=schedule_input.horizon_start,
        horizon_end=schedule_input.horizon_end,
        duration_minutes=schedule_input.duration_minutes,
        slot_step_minutes=schedule_input.slot_step_minutes,
        organizer_timezone=schedule_input.organizer_timezone,
        daily_window_start_local=schedule_input.daily_window_start_local,
        daily_window_end_local=schedule_input.daily_window_end_local,
    )

    scored_slots: list[ScheduleResult] = []
    for start_at in candidate_starts:
        slot = ScheduleSlot.from_start(start_at=start_at, duration_minutes=schedule_input.duration_minutes)
        if not _required_participants_available(slot, schedule_input):
            continue
        scored_slots.append(score_slot(slot, schedule_input.participants))

    ranked = sorted(
        scored_slots,
        key=lambda item: (-item.total_score, -item.optional_available_count, item.start_at),
    )[:3]
    for index, result in enumerate(ranked, start=1):
        result.rank = index
        result.explanation = (
            f"Ranked #{index} because all required participants are available, "
            f"{result.optional_available_count} optional participants can join, "
            f"and the slot matched {int(result.score_breakdown['preference_signals'])} preference signals."
        )
    return ranked


def _required_participants_available(slot: ScheduleSlot, schedule_input: ScheduleInput) -> bool:
    slot_interval = Interval(slot.start_at, slot.end_at)
    for participant in schedule_input.participants:
        if participant.role != "required":
            continue
        if not interval_covered(slot_interval, participant.effective_availability):
            return False
    return True
