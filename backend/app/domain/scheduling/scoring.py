from datetime import time
from zoneinfo import ZoneInfo

from app.domain.availability.interval_ops import interval_covered
from app.domain.availability.models import Interval
from app.domain.common.enums import Weekday
from app.domain.preferences.models import ParsedPreference, TimeRangePreference
from app.domain.scheduling.models import ParticipantContext, ScheduleParticipantStatus, ScheduleResult, ScheduleSlot

OPTIONAL_ATTENDEE_SCORE = 1.5
PREFERRED_WEEKDAY_SCORE = 0.75
DISALLOWED_WEEKDAY_SCORE = -1.0
PREFERRED_TIME_RANGE_SCORE = 1.0
DISALLOWED_TIME_RANGE_SCORE = -1.0
TIME_TIER_1_SCORE = 6.0
TIME_TIER_2_SCORE = 3.0
TIME_TIER_3_SCORE = 1.0


def score_slot(slot: ScheduleSlot, participants: list[ParticipantContext], timezone_name: str = "UTC") -> ScheduleResult:
    slot_interval = Interval(slot.start_at, slot.end_at)
    optional_available_count = 0
    optional_score = 0.0
    preference_score = 0.0
    preference_signals = 0.0
    participant_statuses: list[ScheduleParticipantStatus] = []

    for participant in participants:
        available = interval_covered(slot_interval, participant.effective_availability)
        participant_statuses.append(
            ScheduleParticipantStatus(user_id=participant.user_id, role=participant.role, available=available)
        )
        if not available:
            continue
        if participant.role == "optional":
            optional_available_count += 1
            optional_score += OPTIONAL_ATTENDEE_SCORE
        if participant.preference is not None:
            user_score, user_signals = preference_bonus_for_user(slot, participant.preference, participant.timezone)
            preference_score += user_score
            preference_signals += user_signals

    time_of_day_score = score_time_tier(slot, timezone_name)
    total_score = optional_score + preference_score + time_of_day_score
    return ScheduleResult(
        rank=0,
        start_at=slot.start_at,
        end_at=slot.end_at,
        total_score=round(total_score, 2),
        score_breakdown={
            "optional_attendees": round(optional_score, 2),
            "preference_bonus": round(preference_score, 2),
            "time_tier_bonus": round(time_of_day_score, 2),
            "preference_signals": round(preference_signals, 2),
        },
        explanation="",
        required_participants_satisfied=True,
        optional_available_count=optional_available_count,
        participant_statuses=participant_statuses,
    )


def preference_bonus_for_user(slot: ScheduleSlot, preference: ParsedPreference, timezone_name: str) -> tuple[float, float]:
    zone = ZoneInfo(timezone_name)
    local_start = slot.start_at.astimezone(zone)
    local_end = slot.end_at.astimezone(zone)

    weekday_value = Weekday(local_start.strftime("%a").upper()[:3])
    weekday_score = 0.0
    weekday_signal = 0.0
    if weekday_value in preference.disallowed_weekdays:
        weekday_score = DISALLOWED_WEEKDAY_SCORE
        weekday_signal = 1.0
    elif weekday_value in preference.preferred_weekdays:
        weekday_score = PREFERRED_WEEKDAY_SCORE
        weekday_signal = 1.0

    time_score = 0.0
    time_signal = 0.0
    if overlaps_any_range(local_start.time(), local_end.time(), preference.disallowed_time_ranges):
        time_score = DISALLOWED_TIME_RANGE_SCORE
        time_signal = 1.0
    elif _matches_any_range(local_start.time(), local_end.time(), preference.preferred_time_ranges):
        time_score = PREFERRED_TIME_RANGE_SCORE
        time_signal = 1.0

    return weekday_score + time_score, weekday_signal + time_signal


def score_time_tier(slot: ScheduleSlot, timezone_name: str) -> float:
    zone = ZoneInfo(timezone_name)
    local_start = slot.start_at.astimezone(zone).time()
    local_end = slot.end_at.astimezone(zone).time()

    if _time_in_range(local_start, local_end, time(18, 0), time(22, 0)):
        return TIME_TIER_1_SCORE
    if _time_in_range(local_start, local_end, time(16, 0), time(18, 0)):
        return TIME_TIER_2_SCORE
    if _time_in_range(local_start, local_end, time(22, 0), time(0, 0)):
        return TIME_TIER_2_SCORE
    return TIME_TIER_3_SCORE


def _matches_any_range(start_at: time, end_at: time, ranges: list[TimeRangePreference]) -> bool:
    return any(start_at >= _to_time(item.start_local) and end_at <= _to_time(item.end_local) for item in ranges)


def overlaps_any_range(start_at: time, end_at: time, ranges: list[TimeRangePreference]) -> bool:
    return any(start_at < _to_time(item.end_local) and end_at > _to_time(item.start_local) for item in ranges)


def _to_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def _time_in_range(start_at: time, end_at: time, range_start: time, range_end: time) -> bool:
    """
    Returns true when the full slot is contained in [range_start, range_end).
    Handles a wrapping end boundary (e.g. 22:00 -> 00:00).
    """
    slot_start_minutes = start_at.hour * 60 + start_at.minute
    slot_end_minutes = end_at.hour * 60 + end_at.minute
    if slot_end_minutes <= slot_start_minutes:
        slot_end_minutes += 24 * 60

    range_start_minutes = range_start.hour * 60 + range_start.minute
    range_end_minutes = range_end.hour * 60 + range_end.minute
    if range_end_minutes <= range_start_minutes:
        range_end_minutes += 24 * 60

    return slot_start_minutes >= range_start_minutes and slot_end_minutes <= range_end_minutes
