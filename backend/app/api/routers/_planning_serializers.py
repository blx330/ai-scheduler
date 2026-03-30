from __future__ import annotations

from collections import OrderedDict
from uuid import UUID

from app.api.schemas.events import DanceEventParticipantRead, DanceEventRead
from app.api.schemas.planning import (
    CalendarBusyIntervalRead,
    PlanningExplanationRead,
    PlanningExplanationReasonRead,
    PlanningParticipantStatusRead,
    PlanningRecommendationRead,
    PlanningRunRead,
    PlanningSessionRecommendationGroupRead,
    PracticeSessionRead,
)
from app.domain.common.datetime_utils import ensure_utc
from app.infrastructure.db.models import CalendarBusyInterval, DanceEvent, PlanningRun, PlanningRunResult, PracticeSession


def serialize_event(event: DanceEvent) -> DanceEventRead:
    confirmed_session_count = sum(1 for session in event.practice_sessions if session.status == "confirmed")
    remaining_session_count = max(event.required_session_count - confirmed_session_count, 0)
    return DanceEventRead(
        id=event.id,
        name=event.name,
        description=event.description,
        organizer_user_id=event.organizer_user_id,
        duration_minutes=event.duration_minutes,
        latest_schedule_at=ensure_utc(event.latest_schedule_at),
        required_session_count=event.required_session_count,
        confirmed_session_count=confirmed_session_count,
        remaining_session_count=remaining_session_count,
        status=event.status,
        participants=[
            DanceEventParticipantRead(user_id=participant.user_id, role=participant.role)
            for participant in sorted(event.participants, key=lambda item: (item.role, str(item.user_id)))
        ],
    )


def serialize_practice_session(session: PracticeSession) -> PracticeSessionRead:
    return PracticeSessionRead(
        id=session.id,
        dance_event_id=session.dance_event_id,
        session_index=session.session_index,
        start_at=ensure_utc(session.start_at),
        end_at=ensure_utc(session.end_at),
        status=session.status,
        room_id=session.room_id,
        source_run_id=session.source_run_id,
        total_score=float(session.total_score) if session.total_score is not None else None,
        is_fallback=session.is_fallback,
        missing_required_user_ids=[UUID(value) for value in session.missing_required_user_ids_json or []],
        score_breakdown={key: float(value) for key, value in (session.score_breakdown_json or {}).items()},
        explanation=_serialize_explanation(session.explanation_json or {}),
    )


def serialize_planning_run(run: PlanningRun) -> PlanningRunRead:
    grouped_results: OrderedDict[tuple[UUID, int], PlanningSessionRecommendationGroupRead] = OrderedDict()
    ordered_results = sorted(
        run.results,
        key=lambda item: (item.dance_event.name if item.dance_event else "", item.session_index, item.rank),
    )
    for result in ordered_results:
        key = (result.dance_event_id, result.session_index)
        if key not in grouped_results:
            grouped_results[key] = PlanningSessionRecommendationGroupRead(
                dance_event_id=result.dance_event_id,
                dance_name=result.dance_event.name if result.dance_event else "",
                session_index=result.session_index,
                recommendations=[],
            )
        grouped_results[key].recommendations.append(serialize_planning_result(result))

    return PlanningRunRead(
        id=run.id,
        room_id=run.room_id,
        status=run.status,
        horizon_start=ensure_utc(run.horizon_start),
        horizon_end=ensure_utc(run.horizon_end),
        slot_step_minutes=run.slot_step_minutes,
        event_ids=[UUID(value) for value in run.event_ids_json or []],
        results=list(grouped_results.values()),
    )


def serialize_planning_result(result: PlanningRunResult) -> PlanningRecommendationRead:
    return PlanningRecommendationRead(
        id=result.id,
        dance_event_id=result.dance_event_id,
        dance_name=result.dance_event.name if result.dance_event else "",
        session_index=result.session_index,
        rank=result.rank,
        room_id=result.room_id,
        start_at=ensure_utc(result.start_at),
        end_at=ensure_utc(result.end_at),
        total_score=float(result.total_score),
        score_breakdown={key: float(value) for key, value in (result.score_breakdown_json or {}).items()},
        explanation=_serialize_explanation(result.explanation_json or {}),
        is_fallback=result.is_fallback,
        missing_required_user_ids=[UUID(value) for value in result.missing_required_user_ids_json or []],
        optional_available_count=_optional_available_count(result.participant_statuses_json or []),
        participant_statuses=[PlanningParticipantStatusRead(**item) for item in result.participant_statuses_json or []],
    )


def serialize_busy_interval(interval: CalendarBusyInterval) -> CalendarBusyIntervalRead:
    return CalendarBusyIntervalRead(
        id=interval.id,
        user_id=interval.user_id,
        start_at=ensure_utc(interval.start_at),
        end_at=ensure_utc(interval.end_at),
    )


def _serialize_explanation(explanation_json: dict) -> PlanningExplanationRead:
    reasons = []
    for reason in explanation_json.get("reasons", []):
        normalized = dict(reason)
        normalized["missing_required_user_ids"] = [
            UUID(value) for value in normalized.get("missing_required_user_ids", [])
        ]
        reasons.append(PlanningExplanationReasonRead(**normalized))
    return PlanningExplanationRead(
        summary=explanation_json.get("summary", ""),
        reasons=reasons,
        missing_required_user_ids=[UUID(value) for value in explanation_json.get("missing_required_user_ids", [])],
    )


def _optional_available_count(participant_statuses_json: list[dict]) -> int:
    return sum(1 for item in participant_statuses_json if item.get("role") == "optional" and item.get("available"))
