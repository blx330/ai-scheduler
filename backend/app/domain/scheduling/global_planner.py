from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.availability.interval_ops import subtract_intervals
from app.domain.availability.models import Interval
from app.domain.common.datetime_utils import ensure_utc
from app.domain.preferences.models import ParsedPreference
from app.domain.scheduling.candidate_generation import generate_candidate_starts
from app.domain.scheduling.models import ParticipantContext, ScheduleParticipantStatus, ScheduleSlot
from app.domain.scheduling.scoring import preference_bonus_for_user, score_slot

LATE_NIGHT_PENALTY = -1.0
SAME_DAY_PRACTICE_PENALTY = -0.35
BACK_TO_BACK_PENALTY = -0.5
FALLBACK_MISSING_REQUIRED_PENALTY = -2.5
BACK_TO_BACK_WINDOW = timedelta(minutes=15)
PRACTICE_WINDOW_START_LOCAL = time(8, 0)
PRACTICE_WINDOW_END_LOCAL = time(0, 0)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanningEventInput:
    dance_event_id: UUID
    dance_name: str
    organizer_user_id: UUID
    organizer_timezone: str
    organizer_preference: Optional[ParsedPreference]
    duration_minutes: int
    earliest_start_date: Optional[date]
    min_days_apart: int
    latest_schedule_at: datetime
    next_session_index: int
    sessions_remaining: int
    confirmed_session_starts: list[datetime]
    participants: list[ParticipantContext]

    @property
    def required_participant_ids(self) -> set[UUID]:
        return {participant.user_id for participant in self.participants if participant.role == "required"}

    @property
    def required_participant_count(self) -> int:
        return len(self.required_participant_ids)


@dataclass(frozen=True)
class SessionReservation:
    identifier: str
    start_at: datetime
    end_at: datetime
    room_id: UUID
    participant_user_ids: frozenset[UUID]
    dance_event_id: Optional[UUID] = None
    session_index: Optional[int] = None


@dataclass
class PlanningRecommendation:
    dance_event_id: UUID
    dance_name: str
    session_index: int
    rank: int
    room_id: UUID
    start_at: datetime
    end_at: datetime
    total_score: float
    score_breakdown: dict[str, float]
    explanation: dict[str, Any]
    is_fallback: bool
    missing_required_user_ids: list[UUID]
    optional_available_count: int
    participant_statuses: list[ScheduleParticipantStatus]

    @property
    def reserved_required_user_ids(self) -> frozenset[UUID]:
        return frozenset(
            status.user_id
            for status in self.participant_statuses
            if status.role == "required" and status.available
        )


@dataclass(frozen=True)
class CandidateOption:
    slot: ScheduleSlot
    base_score_breakdown: dict[str, float]
    optional_available_count: int
    participant_statuses: list[ScheduleParticipantStatus]
    missing_required_user_ids: list[UUID]

    @property
    def reserved_required_user_ids(self) -> frozenset[UUID]:
        return frozenset(
            status.user_id
            for status in self.participant_statuses
            if status.role == "required" and status.available and status.user_id not in self.missing_required_user_ids
        )


def plan_practice_sessions(
    events: list[PlanningEventInput],
    fixed_reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
    max_results_per_session: int = 3,
) -> list[PlanningRecommendation]:
    horizon_start = ensure_utc(planning_horizon_start)
    horizon_end = ensure_utc(planning_horizon_end)
    if horizon_end <= horizon_start:
        return []

    order_metadata = []
    for event in events:
        if event.sessions_remaining <= 0:
            continue
        feasible_count = count_feasible_slots(
            event=event,
            reservations=fixed_reservations,
            room_id=room_id,
            planning_horizon_start=horizon_start,
            planning_horizon_end=horizon_end,
            slot_step_minutes=slot_step_minutes,
        )
        order_metadata.append((event, feasible_count))

    ordered_events = [
        event
        for event, _ in sorted(
            order_metadata,
            key=lambda item: (
                ensure_utc(item[0].latest_schedule_at),
                -item[0].required_participant_count,
                item[1],
                item[0].dance_name.lower(),
            ),
        )
    ]

    planned_results: list[PlanningRecommendation] = []
    active_reservations = list(fixed_reservations)
    if not ordered_events:
        return planned_results

    max_rounds = max(event.sessions_remaining for event in ordered_events)
    for round_index in range(max_rounds):
        for event in ordered_events:
            if round_index >= event.sessions_remaining:
                continue
            session_index = event.next_session_index + round_index
            recommendations = build_ranked_recommendations(
                event=event,
                session_index=session_index,
                reservations=active_reservations,
                room_id=room_id,
                planning_horizon_start=horizon_start,
                planning_horizon_end=horizon_end,
                slot_step_minutes=slot_step_minutes,
                max_results=max_results_per_session,
            )
            planned_results.extend(recommendations)
            if recommendations:
                active_reservations.append(
                    SessionReservation(
                        identifier=f"{event.dance_event_id}:{session_index}",
                        start_at=recommendations[0].start_at,
                        end_at=recommendations[0].end_at,
                        room_id=room_id,
                        participant_user_ids=recommendations[0].reserved_required_user_ids,
                        dance_event_id=event.dance_event_id,
                        session_index=session_index,
                    )
                )

    return planned_results


def count_feasible_slots(
    event: PlanningEventInput,
    reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
) -> int:
    return len(
        _build_candidates(
            event=event,
            session_index=event.next_session_index,
            reservations=reservations,
            room_id=room_id,
            planning_horizon_start=planning_horizon_start,
            planning_horizon_end=planning_horizon_end,
            slot_step_minutes=slot_step_minutes,
            allowed_missing_required=0,
        )
    )


def build_ranked_recommendations(
    event: PlanningEventInput,
    session_index: int,
    reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
    max_results: int,
) -> list[PlanningRecommendation]:
    primary_candidates = _build_candidates(
        event=event,
        session_index=session_index,
        reservations=reservations,
        room_id=room_id,
        planning_horizon_start=planning_horizon_start,
        planning_horizon_end=planning_horizon_end,
        slot_step_minutes=slot_step_minutes,
        allowed_missing_required=0,
    )
    candidates = primary_candidates
    fallback_candidates: list[PlanningRecommendation] = []
    if len(candidates) < max_results:
        fallback_candidates = _build_candidates(
            event=event,
            session_index=session_index,
            reservations=reservations,
            room_id=room_id,
            planning_horizon_start=planning_horizon_start,
            planning_horizon_end=planning_horizon_end,
            slot_step_minutes=slot_step_minutes,
            allowed_missing_required=None,
            require_missing_required=True,
        )
    candidates = candidates + fallback_candidates

    ranked = sorted(
        candidates,
        key=lambda item: (-item.total_score, -item.optional_available_count, item.start_at),
    )[:max_results]
    for index, item in enumerate(ranked, start=1):
        item.rank = index
    return ranked


def _build_candidates(
    event: PlanningEventInput,
    session_index: int,
    reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
    allowed_missing_required: Optional[int],
    require_missing_required: bool = False,
) -> list[PlanningRecommendation]:
    candidate_options, candidate_starts_count, rejection_counts = _build_candidate_options(
        event=event,
        session_index=session_index,
        reservations=reservations,
        room_id=room_id,
        planning_horizon_start=planning_horizon_start,
        planning_horizon_end=planning_horizon_end,
        slot_step_minutes=slot_step_minutes,
        allowed_missing_required=allowed_missing_required,
        require_missing_required=require_missing_required,
    )
    recommendations: list[PlanningRecommendation] = []
    rejection_counts["no_valid_remaining_sequence"] = 0
    for option in candidate_options:
        if _remaining_session_count(event, session_index) > 0:
            future_reservations = [
                *reservations,
                _build_session_reservation(
                    event=event,
                    session_index=session_index,
                    slot=option.slot,
                    room_id=room_id,
                    participant_user_ids=option.reserved_required_user_ids,
                ),
            ]
            if not _can_complete_remaining_sessions(
                event=event,
                next_session_index=session_index + 1,
                reservations=future_reservations,
                room_id=room_id,
                planning_horizon_start=planning_horizon_start,
                planning_horizon_end=planning_horizon_end,
                slot_step_minutes=slot_step_minutes,
            ):
                rejection_counts["no_valid_remaining_sequence"] += 1
                continue
        score_breakdown, explanation = _build_scoring_metadata(
            slot=option.slot,
            event=event,
            reservations=reservations,
            base_score_breakdown=option.base_score_breakdown,
            optional_available_count=option.optional_available_count,
            missing_required_user_ids=option.missing_required_user_ids,
        )
        total_score = round(sum(score_breakdown.values()), 2)
        recommendations.append(
            PlanningRecommendation(
                dance_event_id=event.dance_event_id,
                dance_name=event.dance_name,
                session_index=session_index,
                rank=0,
                room_id=room_id,
                start_at=option.slot.start_at,
                end_at=option.slot.end_at,
                total_score=total_score,
                score_breakdown=score_breakdown,
                explanation=explanation,
                is_fallback=bool(option.missing_required_user_ids),
                missing_required_user_ids=option.missing_required_user_ids,
                optional_available_count=option.optional_available_count,
                participant_statuses=option.participant_statuses,
            )
        )
    logger.info(
        "planning candidates event=%s session_index=%s allowed_missing_required=%s generated_slots=%s accepted=%s rejections=%s horizon_start=%s horizon_end=%s duration_minutes=%s",
        event.dance_event_id,
        session_index,
        allowed_missing_required,
        candidate_starts_count,
        len(recommendations),
        rejection_counts,
        ensure_utc(planning_horizon_start),
        min(ensure_utc(planning_horizon_end), ensure_utc(event.latest_schedule_at)),
        event.duration_minutes,
    )
    return recommendations


def _build_candidate_options(
    event: PlanningEventInput,
    session_index: int,
    reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
    allowed_missing_required: Optional[int],
    require_missing_required: bool = False,
) -> tuple[list[CandidateOption], int, dict[str, int]]:
    prior_session_end, later_session_start = _same_dance_session_bounds(
        event=event,
        session_index=session_index,
        reservations=reservations,
    )
    effective_horizon_start = _candidate_horizon_start(event, planning_horizon_start)
    if prior_session_end is not None:
        effective_horizon_start = max(effective_horizon_start, ensure_utc(prior_session_end))
    horizon_end = min(ensure_utc(planning_horizon_end), ensure_utc(event.latest_schedule_at))
    if later_session_start is not None:
        horizon_end = min(horizon_end, ensure_utc(later_session_start))
    if horizon_end <= effective_horizon_start:
        return [], 0, {"empty_horizon": 1}

    adjusted_participants = _adjust_participants_for_reservations(event.participants, reservations)
    candidate_starts = generate_candidate_starts(
        horizon_start=effective_horizon_start,
        horizon_end=horizon_end,
        duration_minutes=event.duration_minutes,
        slot_step_minutes=slot_step_minutes,
        organizer_timezone=event.organizer_timezone,
        daily_window_start_local=PRACTICE_WINDOW_START_LOCAL,
        daily_window_end_local=PRACTICE_WINDOW_END_LOCAL,
    )

    organizer_zone = ZoneInfo(event.organizer_timezone)
    same_dance_dates = {
        ensure_utc(start_at).astimezone(organizer_zone).date()
        for start_at in event.confirmed_session_starts
    }
    same_dance_dates.update(
        ensure_utc(reservation.start_at).astimezone(organizer_zone).date()
        for reservation in reservations
        if reservation.dance_event_id == event.dance_event_id
    )
    rejection_counts = {
        "room_conflict": 0,
        "earliest_start_date": 0,
        "min_days_apart": 0,
        "before_prior_session": 0,
        "after_later_session": 0,
        "missing_required_over_limit": 0,
        "fallback_wrong_missing_required_count": 0,
    }
    options: list[CandidateOption] = []
    for start_at in candidate_starts:
        slot = ScheduleSlot.from_start(start_at=start_at, duration_minutes=event.duration_minutes)
        if prior_session_end is not None and slot.start_at < ensure_utc(prior_session_end):
            rejection_counts["before_prior_session"] += 1
            continue
        if later_session_start is not None and slot.end_at > ensure_utc(later_session_start):
            rejection_counts["after_later_session"] += 1
            continue
        slot_local_date = slot.start_at.astimezone(organizer_zone).date()
        if event.earliest_start_date is not None and slot_local_date < event.earliest_start_date:
            rejection_counts["earliest_start_date"] += 1
            continue
        if event.min_days_apart > 0 and any(
            abs((slot_local_date - other_date).days) < event.min_days_apart for other_date in same_dance_dates
        ):
            rejection_counts["min_days_apart"] += 1
            continue
        if _room_conflict(slot, room_id, reservations):
            rejection_counts["room_conflict"] += 1
            continue

        base_result = score_slot(slot, adjusted_participants, timezone_name=event.organizer_timezone)
        missing_required_user_ids = sorted(
            status.user_id
            for status in base_result.participant_statuses
            if status.role == "required" and not status.available
        )
        if allowed_missing_required is not None and len(missing_required_user_ids) > allowed_missing_required:
            rejection_counts["missing_required_over_limit"] += 1
            continue
        if require_missing_required and len(missing_required_user_ids) == 0:
            rejection_counts["fallback_wrong_missing_required_count"] += 1
            continue
        options.append(
            CandidateOption(
                slot=slot,
                base_score_breakdown=base_result.score_breakdown,
                optional_available_count=base_result.optional_available_count,
                participant_statuses=base_result.participant_statuses,
                missing_required_user_ids=missing_required_user_ids,
            )
        )
    return options, len(candidate_starts), rejection_counts


def _can_complete_remaining_sessions(
    event: PlanningEventInput,
    next_session_index: int,
    reservations: list[SessionReservation],
    room_id: UUID,
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    slot_step_minutes: int,
) -> bool:
    if next_session_index > event.next_session_index + event.sessions_remaining - 1:
        return True

    primary_options, _, _ = _build_candidate_options(
        event=event,
        session_index=next_session_index,
        reservations=reservations,
        room_id=room_id,
        planning_horizon_start=planning_horizon_start,
        planning_horizon_end=planning_horizon_end,
        slot_step_minutes=slot_step_minutes,
        allowed_missing_required=0,
    )
    candidate_options = primary_options
    if not candidate_options:
        candidate_options, _, _ = _build_candidate_options(
            event=event,
            session_index=next_session_index,
            reservations=reservations,
            room_id=room_id,
            planning_horizon_start=planning_horizon_start,
            planning_horizon_end=planning_horizon_end,
            slot_step_minutes=slot_step_minutes,
            allowed_missing_required=None,
            require_missing_required=True,
        )

    for option in candidate_options:
        future_reservations = [
            *reservations,
            _build_session_reservation(
                event=event,
                session_index=next_session_index,
                slot=option.slot,
                room_id=room_id,
                participant_user_ids=option.reserved_required_user_ids,
            ),
        ]
        if _can_complete_remaining_sessions(
            event=event,
            next_session_index=next_session_index + 1,
            reservations=future_reservations,
            room_id=room_id,
            planning_horizon_start=planning_horizon_start,
            planning_horizon_end=planning_horizon_end,
            slot_step_minutes=slot_step_minutes,
        ):
            return True
    return False


def _candidate_horizon_start(event: PlanningEventInput, planning_horizon_start: datetime) -> datetime:
    effective_horizon_start = ensure_utc(planning_horizon_start)
    if event.earliest_start_date is None:
        return effective_horizon_start
    organizer_zone = ZoneInfo(event.organizer_timezone)
    local_earliest_start = datetime.combine(
        event.earliest_start_date,
        PRACTICE_WINDOW_START_LOCAL,
        tzinfo=organizer_zone,
    )
    return max(effective_horizon_start, ensure_utc(local_earliest_start.astimezone(timezone.utc)))


def _same_dance_session_bounds(
    event: PlanningEventInput,
    session_index: int,
    reservations: list[SessionReservation],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    prior_session_end: Optional[datetime] = None
    later_session_start: Optional[datetime] = None
    for reservation in reservations:
        if reservation.dance_event_id != event.dance_event_id or reservation.session_index is None:
            continue
        if reservation.session_index < session_index:
            if prior_session_end is None or ensure_utc(reservation.end_at) > ensure_utc(prior_session_end):
                prior_session_end = ensure_utc(reservation.end_at)
        elif reservation.session_index > session_index:
            if later_session_start is None or ensure_utc(reservation.start_at) < ensure_utc(later_session_start):
                later_session_start = ensure_utc(reservation.start_at)
    return prior_session_end, later_session_start


def _adjust_participants_for_reservations(
    participants: list[ParticipantContext],
    reservations: list[SessionReservation],
) -> list[ParticipantContext]:
    participant_adjustments = _participant_reservation_intervals(participants, reservations)
    adjusted_participants: list[ParticipantContext] = []
    for participant in participants:
        reservation_busy = participant_adjustments.get(participant.user_id, [])
        adjusted_availability = subtract_intervals(participant.effective_availability, reservation_busy)
        adjusted_participants.append(
            ParticipantContext(
                user_id=participant.user_id,
                role=participant.role,
                timezone=participant.timezone,
                effective_availability=adjusted_availability,
                preference=participant.preference,
            )
        )
    return adjusted_participants


def _build_session_reservation(
    event: PlanningEventInput,
    session_index: int,
    slot: ScheduleSlot,
    room_id: UUID,
    participant_user_ids: frozenset[UUID],
) -> SessionReservation:
    return SessionReservation(
        identifier=f"{event.dance_event_id}:{session_index}",
        start_at=slot.start_at,
        end_at=slot.end_at,
        room_id=room_id,
        participant_user_ids=participant_user_ids,
        dance_event_id=event.dance_event_id,
        session_index=session_index,
    )


def _remaining_session_count(event: PlanningEventInput, session_index: int) -> int:
    return max((event.next_session_index + event.sessions_remaining - 1) - session_index, 0)


def _participant_reservation_intervals(
    participants: list[ParticipantContext],
    reservations: list[SessionReservation],
) -> dict[UUID, list[Interval]]:
    participant_ids = {participant.user_id for participant in participants}
    intervals: dict[UUID, list[Interval]] = {participant_id: [] for participant_id in participant_ids}
    for reservation in reservations:
        for participant_id in reservation.participant_user_ids:
            if participant_id not in participant_ids:
                continue
            intervals[participant_id].append(Interval(reservation.start_at, reservation.end_at))
    return intervals


def _room_conflict(slot: ScheduleSlot, room_id: UUID, reservations: list[SessionReservation]) -> bool:
    return any(
        reservation.room_id == room_id and slot.start_at < reservation.end_at and slot.end_at > reservation.start_at
        for reservation in reservations
    )


def _build_scoring_metadata(
    slot: ScheduleSlot,
    event: PlanningEventInput,
    reservations: list[SessionReservation],
    base_score_breakdown: dict[str, float],
    optional_available_count: int,
    missing_required_user_ids: list[UUID],
) -> tuple[dict[str, float], dict[str, Any]]:
    organizer_zone = ZoneInfo(event.organizer_timezone)
    relevant_reservations = [
        reservation
        for reservation in reservations
        if reservation.participant_user_ids & event.required_participant_ids
    ]

    participant_ids = {participant.user_id for participant in event.participants}
    organizer_preference_bonus = 0.0
    if event.organizer_preference is not None and event.organizer_user_id not in participant_ids:
        organizer_preference_bonus, _ = preference_bonus_for_user(slot, event.organizer_preference, event.organizer_timezone)
    late_night_penalty = _late_night_penalty(slot, organizer_zone)
    same_day_count = _same_day_reservation_count(slot, relevant_reservations, organizer_zone)
    same_day_penalty = round(same_day_count * SAME_DAY_PRACTICE_PENALTY, 2)
    back_to_back_count = _back_to_back_count(slot, relevant_reservations)
    back_to_back_penalty = round(back_to_back_count * BACK_TO_BACK_PENALTY, 2)
    fallback_penalty = FALLBACK_MISSING_REQUIRED_PENALTY if missing_required_user_ids else 0.0

    score_breakdown = {
        "optional_attendees": round(float(base_score_breakdown.get("optional_attendees", 0.0)), 2),
        "preference_bonus": round(float(base_score_breakdown.get("preference_bonus", 0.0)), 2),
        "time_tier_bonus": round(float(base_score_breakdown.get("time_tier_bonus", 0.0)), 2),
        "organizer_preference_bonus": round(organizer_preference_bonus, 2),
        "late_night_penalty": round(late_night_penalty, 2),
        "same_day_penalty": same_day_penalty,
        "back_to_back_penalty": back_to_back_penalty,
        "fallback_penalty": round(fallback_penalty, 2),
    }

    reasons: list[dict[str, Any]] = []
    if missing_required_user_ids:
        reasons.append(
            {
                "code": "fallback_missing_required",
                "message": "No fully feasible slot was found, so this fallback allows one required participant to miss.",
                "score": round(fallback_penalty, 2),
                "missing_required_user_ids": [str(user_id) for user_id in missing_required_user_ids],
            }
        )
    else:
        reasons.append(
            {
                "code": "required_available",
                "message": "All required participants are available for this practice.",
            }
        )

    if optional_available_count:
        reasons.append(
            {
                "code": "optional_attendees",
                "message": f"{optional_available_count} optional participant(s) can attend.",
                "score": round(score_breakdown["optional_attendees"], 2),
            }
        )
    if score_breakdown["preference_bonus"]:
        reasons.append(
            {
                "code": "preference_bonus",
                "message": "This slot matches participant scheduling preferences.",
                "score": round(score_breakdown["preference_bonus"], 2),
            }
        )
    if score_breakdown["time_tier_bonus"]:
        reasons.append(
            {
                "code": "time_tier_bonus",
                "message": "This slot falls in a preferred time-of-day tier.",
                "score": round(score_breakdown["time_tier_bonus"], 2),
            }
        )
    if score_breakdown["organizer_preference_bonus"]:
        reasons.append(
            {
                "code": "organizer_preference_bonus",
                "message": "This slot matches the organizer's saved practice-time preference.",
                "score": round(score_breakdown["organizer_preference_bonus"], 2),
            }
        )
    if late_night_penalty:
        reasons.append(
            {
                "code": "late_night_penalty",
                "message": "This practice ends after 10 PM in the organizer timezone.",
                "score": round(late_night_penalty, 2),
            }
        )
    if same_day_count:
        reasons.append(
            {
                "code": "same_day_penalty",
                "message": f"{same_day_count} other practice(s) already land on this day for required dancers.",
                "score": same_day_penalty,
            }
        )
    if back_to_back_count:
        reasons.append(
            {
                "code": "back_to_back_penalty",
                "message": f"{back_to_back_count} nearby practice(s) create a back-to-back schedule.",
                "score": back_to_back_penalty,
            }
        )

    summary = (
        "Fallback option within the 8:00 AM to 12:00 AM practice window with one or more missing required participants."
        if missing_required_user_ids
        else "Recommended practice within the 8:00 AM to 12:00 AM window with all required participants available."
    )
    explanation = {
        "summary": summary,
        "reasons": reasons,
        "missing_required_user_ids": [str(user_id) for user_id in missing_required_user_ids],
    }
    return score_breakdown, explanation


def _late_night_penalty(slot: ScheduleSlot, organizer_zone: ZoneInfo) -> float:
    local_start = slot.start_at.astimezone(organizer_zone)
    local_end = slot.end_at.astimezone(organizer_zone)
    if local_start.hour >= 22 or local_end.hour > 22 or (local_end.hour == 22 and local_end.minute > 0):
        return LATE_NIGHT_PENALTY
    return 0.0


def _same_day_reservation_count(
    slot: ScheduleSlot,
    reservations: list[SessionReservation],
    organizer_zone: ZoneInfo,
) -> int:
    slot_day = slot.start_at.astimezone(organizer_zone).date()
    return sum(1 for reservation in reservations if reservation.start_at.astimezone(organizer_zone).date() == slot_day)


def _back_to_back_count(slot: ScheduleSlot, reservations: list[SessionReservation]) -> int:
    return sum(
        1
        for reservation in reservations
        if abs(reservation.end_at - slot.start_at) <= BACK_TO_BACK_WINDOW
        or abs(reservation.start_at - slot.end_at) <= BACK_TO_BACK_WINDOW
    )
