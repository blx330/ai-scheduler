from zoneinfo import ZoneInfo

from app.domain.availability.interval_ops import interval_covered
from app.domain.availability.models import Interval
from app.domain.common.enums import Weekday
from app.domain.common.time_of_day import (
    contained_in_range,
    overlap_minutes,
    overlaps_range,
    slot_minutes,
)
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

# (start minutes, end minutes, score) in organizer-local time. Anything not covered
# here scores TIME_TIER_3_SCORE.
TIME_TIERS = (
    (18 * 60, 22 * 60, TIME_TIER_1_SCORE),
    (16 * 60, 18 * 60, TIME_TIER_2_SCORE),
    (22 * 60, 24 * 60, TIME_TIER_2_SCORE),
)

# datetime.weekday() index -> Weekday. strftime("%a") would honour LC_TIME and raise
# a ValueError under a non-English locale.
WEEKDAY_BY_INDEX = (
    Weekday.MON,
    Weekday.TUE,
    Weekday.WED,
    Weekday.THU,
    Weekday.FRI,
    Weekday.SAT,
    Weekday.SUN,
)


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
    start_minutes, end_minutes = slot_minutes(local_start, local_end)

    weekday_value = WEEKDAY_BY_INDEX[local_start.weekday()]
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
    if overlaps_any_range(start_minutes, end_minutes, preference.disallowed_time_ranges):
        time_score = DISALLOWED_TIME_RANGE_SCORE
        time_signal = 1.0
    elif _matches_any_range(start_minutes, end_minutes, preference.preferred_time_ranges):
        time_score = PREFERRED_TIME_RANGE_SCORE
        time_signal = 1.0

    return weekday_score + time_score, weekday_signal + time_signal


def score_time_tier(slot: ScheduleSlot, timezone_name: str) -> float:
    """Time-of-day score, weighted by how much of the slot falls in each tier.

    Scoring by containment instead would drop every boundary-straddling slot into
    the lowest tier, making the ranking non-monotonic: a 17:00-19:00 practice would
    score below both 16:00-18:00 and 18:00-20:00.
    """
    zone = ZoneInfo(timezone_name)
    start_minutes, end_minutes = slot_minutes(slot.start_at.astimezone(zone), slot.end_at.astimezone(zone))
    duration = end_minutes - start_minutes
    if duration <= 0:
        return TIME_TIER_3_SCORE

    weighted_total = 0.0
    tiered_minutes = 0
    for range_start, range_end, tier_score in TIME_TIERS:
        overlap = overlap_minutes(start_minutes, end_minutes, range_start, range_end)
        weighted_total += overlap * tier_score
        tiered_minutes += overlap
    weighted_total += max(0, duration - tiered_minutes) * TIME_TIER_3_SCORE
    return round(weighted_total / duration, 2)


def _matches_any_range(start_minutes: int, end_minutes: int, ranges: list[TimeRangePreference]) -> bool:
    return any(
        contained_in_range(start_minutes, end_minutes, *_range_bounds(item)) for item in ranges
    )


def overlaps_any_range(start_minutes: int, end_minutes: int, ranges: list[TimeRangePreference]) -> bool:
    return any(overlaps_range(start_minutes, end_minutes, *_range_bounds(item)) for item in ranges)


def _range_bounds(item: TimeRangePreference) -> tuple[int, int]:
    return _to_minutes(item.start_local), _to_minutes(item.end_local)


def _to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)
