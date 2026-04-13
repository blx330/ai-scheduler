from __future__ import annotations

from collections import defaultdict
from datetime import date
import logging
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas.planning import PlanningRunCreate
from app.domain.availability.interval_ops import build_effective_availability
from app.domain.common.datetime_utils import ensure_utc
from app.domain.preferences.models import (
    ParsedPreference,
    merge_cached_practice_preference,
    merge_preferred_practice_time,
)
from app.domain.scheduling.global_planner import (
    PlanningEventInput,
    SessionReservation,
    plan_practice_sessions,
)
from app.domain.scheduling.models import ParticipantContext
from app.infrastructure.db.models import (
    CalendarConnection,
    CalendarBusyInterval,
    DanceEvent,
    PlanningRun,
    PlanningRunResult,
    PracticeSession,
    Room,
    User,
    UserParsedPreference,
)
from app.application.services.google_calendar_service import GoogleCalendarService

logger = logging.getLogger(__name__)


class PlanningService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_planning_run(self, payload: PlanningRunCreate) -> PlanningRun:
        horizon_start = ensure_utc(payload.horizon_start)
        horizon_end = ensure_utc(payload.horizon_end)
        if horizon_end <= horizon_start:
            raise ValueError("Planning horizon end must be after start")

        room = self._get_or_create_room(payload.room_id)
        events = self._load_events(payload.event_ids)
        event_inputs = self._build_event_inputs(events, horizon_start=horizon_start, horizon_end=horizon_end)
        fixed_reservations = self._load_confirmed_reservations(horizon_start=horizon_start, horizon_end=horizon_end)
        recommendations = plan_practice_sessions(
            events=event_inputs,
            fixed_reservations=fixed_reservations,
            room_id=room.id,
            planning_horizon_start=horizon_start,
            planning_horizon_end=horizon_end,
            slot_step_minutes=payload.slot_step_minutes,
        )

        run = PlanningRun(
            room_id=room.id,
            status="completed" if recommendations else "no_results",
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            slot_step_minutes=payload.slot_step_minutes,
            event_ids_json=[str(event_id) for event_id in payload.event_ids],
        )
        self.db.add(run)
        self.db.flush()

        for recommendation in recommendations:
            self.db.add(
                PlanningRunResult(
                    planning_run_id=run.id,
                    dance_event_id=recommendation.dance_event_id,
                    room_id=recommendation.room_id,
                    session_index=recommendation.session_index,
                    rank=recommendation.rank,
                    start_at=recommendation.start_at,
                    end_at=recommendation.end_at,
                    total_score=recommendation.total_score,
                    score_breakdown_json=recommendation.score_breakdown,
                    explanation_json=recommendation.explanation,
                    participant_statuses_json=[
                        status.model_dump(mode="json") for status in recommendation.participant_statuses
                    ],
                    is_fallback=recommendation.is_fallback,
                    missing_required_user_ids_json=[str(user_id) for user_id in recommendation.missing_required_user_ids],
                )
            )

        self.db.commit()
        return self.get_planning_run(run.id)  # type: ignore[return-value]

    def get_planning_run(self, run_id: UUID) -> Optional[PlanningRun]:
        statement = (
            select(PlanningRun)
            .where(PlanningRun.id == run_id)
            .options(
                selectinload(PlanningRun.results).selectinload(PlanningRunResult.dance_event),
                selectinload(PlanningRun.room),
            )
        )
        return self.db.scalars(statement).one_or_none()

    def confirm_results(
        self,
        run_id: UUID,
        result_ids: list[UUID],
        google_calendar_service: GoogleCalendarService | None = None,
    ) -> tuple[PlanningRun, list[PracticeSession]]:
        run = self.get_planning_run(run_id)
        if run is None:
            raise ValueError("Planning run not found")

        results = list(
            self.db.scalars(
                select(PlanningRunResult)
                .where(PlanningRunResult.planning_run_id == run_id)
                .where(PlanningRunResult.id.in_(result_ids))
                .options(
                    selectinload(PlanningRunResult.dance_event).selectinload(DanceEvent.participants),
                    selectinload(PlanningRunResult.dance_event).selectinload(DanceEvent.practice_sessions),
                    selectinload(PlanningRunResult.dance_event).selectinload(DanceEvent.organizer),
                )
            )
        )
        if len(results) != len(result_ids):
            raise ValueError("One or more planning results were not found")

        duplicate_targets = {
            (result.dance_event_id, result.session_index)
            for result in results
            if sum(
                1
                for candidate in results
                if candidate.dance_event_id == result.dance_event_id and candidate.session_index == result.session_index
            )
            > 1
        }
        if duplicate_targets:
            raise ValueError("Cannot confirm multiple recommendations for the same event session")

        confirmation_start = min(result.start_at for result in results)
        confirmation_end = max(result.end_at for result in results)
        active_reservations = self._load_confirmed_reservations(
            horizon_start=confirmation_start,
            horizon_end=confirmation_end,
        )

        confirmed_sessions: list[PracticeSession] = []
        confirmed_session_ids: list[UUID] = []
        selected_starts_by_event: dict[UUID, list[date]] = defaultdict(list)
        ordered_results = sorted(results, key=lambda item: (item.start_at, item.dance_event_id, item.session_index))
        for result in ordered_results:
            _validate_result_against_event_constraints(
                result=result,
                selected_starts=selected_starts_by_event[result.dance_event_id],
            )
            required_attendees = frozenset(_required_attendee_ids(result))
            if any(
                reservation.room_id == result.room_id
                and result.start_at < reservation.end_at
                and result.end_at > reservation.start_at
                for reservation in active_reservations
            ):
                raise ValueError("Selected planning result conflicts with an existing room reservation")
            if any(
                required_attendees & reservation.participant_user_ids
                and result.start_at < reservation.end_at
                and result.end_at > reservation.start_at
                for reservation in active_reservations
            ):
                raise ValueError("Selected planning result conflicts with an existing participant reservation")

            existing_session = self.db.scalars(
                select(PracticeSession)
                .where(PracticeSession.dance_event_id == result.dance_event_id)
                .where(PracticeSession.session_index == result.session_index)
                .where(PracticeSession.status == "confirmed")
            ).first()
            if existing_session is not None:
                raise ValueError("This event session is already confirmed")

            practice_session = PracticeSession(
                dance_event_id=result.dance_event_id,
                session_index=result.session_index,
                start_at=result.start_at,
                end_at=result.end_at,
                status="confirmed",
                room_id=result.room_id,
                source_run_id=run.id,
                total_score=float(result.total_score),
                is_fallback=result.is_fallback,
                missing_required_user_ids_json=list(result.missing_required_user_ids_json or []),
                score_breakdown_json=dict(result.score_breakdown_json or {}),
                explanation_json=dict(result.explanation_json or {}),
            )
            self.db.add(practice_session)
            self.db.flush()
            confirmed_sessions.append(practice_session)
            confirmed_session_ids.append(practice_session.id)
            selected_starts_by_event[result.dance_event_id].append(
                ensure_utc(result.start_at).astimezone(_organizer_zone_for_result(result)).date()
            )
            active_reservations.append(
                SessionReservation(
                    identifier=f"{result.dance_event_id}:{result.session_index}",
                    start_at=result.start_at,
                    end_at=result.end_at,
                    room_id=result.room_id,
                    participant_user_ids=required_attendees,
                    dance_event_id=result.dance_event_id,
                    session_index=result.session_index,
                )
            )

        affected_event_ids = {result.dance_event_id for result in results}
        affected_events = self.db.scalars(
            select(DanceEvent)
            .where(DanceEvent.id.in_(affected_event_ids))
            .options(selectinload(DanceEvent.practice_sessions))
        )
        for event in affected_events:
            confirmed_count = _count_confirmed_sessions(event.practice_sessions)
            event.status = _derive_event_status(event.required_session_count, confirmed_count)
            self.db.add(event)

        self.db.commit()
        if google_calendar_service is not None:
            for practice_session_id in confirmed_session_ids:
                try:
                    google_calendar_service.create_event_for_practice_session(practice_session_id)
                except (ValueError, RuntimeError) as exc:
                    logger.warning(
                        "Failed to create Google Calendar event for practice session %s: %s",
                        practice_session_id,
                        exc,
                    )
        confirmed_sessions = list(
            self.db.scalars(
                select(PracticeSession)
                .where(PracticeSession.id.in_(confirmed_session_ids))
                .order_by(PracticeSession.dance_event_id.asc(), PracticeSession.session_index.asc())
            )
        )
        run = self.get_planning_run(run_id)
        return run, sorted(confirmed_sessions, key=lambda item: (item.dance_event_id, item.session_index))

    def get_practice_session(self, practice_session_id: UUID) -> Optional[PracticeSession]:
        statement = (
            select(PracticeSession)
            .where(PracticeSession.id == practice_session_id)
            .options(
                selectinload(PracticeSession.dance_event).selectinload(DanceEvent.organizer),
                selectinload(PracticeSession.dance_event).selectinload(DanceEvent.practice_sessions),
            )
        )
        return self.db.scalars(statement).one_or_none()

    def unschedule_practice_session(self, practice_session_id: UUID) -> Optional[PracticeSession]:
        session = self.get_practice_session(practice_session_id)
        if session is None:
            return None

        event = session.dance_event
        self.db.delete(session)
        self.db.flush()

        remaining_confirmed = self.db.scalars(
            select(PracticeSession.id)
            .where(PracticeSession.dance_event_id == event.id)
            .where(PracticeSession.status == "confirmed")
        ).all()
        if event.status not in {"archived", "completed"}:
            event.status = _derive_event_status(event.required_session_count, len(remaining_confirmed))
        self.db.commit()
        return session

    def get_calendar_overview(self, horizon_start, horizon_end) -> tuple[list[CalendarBusyInterval], list[PracticeSession]]:
        start_at = ensure_utc(horizon_start)
        end_at = ensure_utc(horizon_end)
        if end_at <= start_at:
            raise ValueError("Calendar overview end must be after start")

        busy_intervals = list(
            self.db.scalars(
                select(CalendarBusyInterval)
                .where(CalendarBusyInterval.end_at > start_at)
                .where(CalendarBusyInterval.start_at < end_at)
                .order_by(CalendarBusyInterval.start_at.asc())
            )
        )
        practice_sessions = list(
            self.db.scalars(
                select(PracticeSession)
                .where(PracticeSession.status == "confirmed")
                .where(PracticeSession.end_at > start_at)
                .where(PracticeSession.start_at < end_at)
                .order_by(PracticeSession.start_at.asc())
            )
        )
        return busy_intervals, practice_sessions

    def _load_events(self, event_ids: list[UUID]) -> list[DanceEvent]:
        statement = (
            select(DanceEvent)
            .where(DanceEvent.id.in_(event_ids))
            .options(
                selectinload(DanceEvent.participants),
                selectinload(DanceEvent.practice_sessions),
                selectinload(DanceEvent.organizer),
            )
        )
        events = list(self.db.scalars(statement))
        if len(events) != len(event_ids):
            raise ValueError("One or more events were not found")
        return events

    def _build_event_inputs(
        self,
        events: list[DanceEvent],
        horizon_start,
        horizon_end,
    ) -> list[PlanningEventInput]:
        participant_user_ids = {participant.user_id for event in events for participant in event.participants}
        organizer_ids = {event.organizer_user_id for event in events}
        all_user_ids = participant_user_ids | organizer_ids

        users = {
            user.id: user
            for user in self.db.scalars(select(User).where(User.id.in_(all_user_ids)))
        }
        connected_user_ids = {
            row.user_id
            for row in self.db.scalars(
                select(CalendarConnection)
                .where(CalendarConnection.user_id.in_(participant_user_ids))
                .where(CalendarConnection.provider == "google")
            )
            if row.refresh_token or row.access_token
        }

        manual_by_user = defaultdict(list)
        from app.infrastructure.db.models import ManualAvailabilityInterval  # local import to avoid circular lint noise

        for interval in self.db.scalars(
            select(ManualAvailabilityInterval)
            .where(ManualAvailabilityInterval.user_id.in_(participant_user_ids))
            .where(ManualAvailabilityInterval.end_at > horizon_start)
            .where(ManualAvailabilityInterval.start_at < horizon_end)
            .order_by(ManualAvailabilityInterval.start_at.asc())
        ):
            manual_by_user[interval.user_id].append(interval)

        busy_by_user = defaultdict(list)
        for interval in self.db.scalars(
            select(CalendarBusyInterval)
            .where(CalendarBusyInterval.user_id.in_(participant_user_ids))
            .where(CalendarBusyInterval.end_at > horizon_start)
            .where(CalendarBusyInterval.start_at < horizon_end)
            .order_by(CalendarBusyInterval.start_at.asc())
        ):
            busy_by_user[interval.user_id].append(interval)

        preference_rows = list(
            self.db.scalars(
                select(UserParsedPreference)
                .where(UserParsedPreference.user_id.in_(all_user_ids))
                .order_by(UserParsedPreference.created_at.desc())
            )
        )
        preferences_by_user: dict[UUID, ParsedPreference] = {}
        for row in preference_rows:
            if row.user_id not in preferences_by_user:
                preferences_by_user[row.user_id] = ParsedPreference.model_validate(row.constraints_json)

        event_inputs: list[PlanningEventInput] = []
        for event in events:
            confirmed_count = _count_confirmed_sessions(event.practice_sessions)
            sessions_remaining = max(event.required_session_count - confirmed_count, 0)
            participant_contexts: list[ParticipantContext] = []
            for participant in event.participants:
                user = users.get(participant.user_id)
                if user is None:
                    raise ValueError("Event participant user not found")
                manual_intervals = manual_by_user.get(participant.user_id, [])
                if not manual_intervals and participant.user_id in connected_user_ids:
                    manual_intervals = [
                        SimpleNamespace(
                            start_at=horizon_start,
                            end_at=horizon_end,
                        )
                    ]
                effective = build_effective_availability(
                    manual_intervals=manual_intervals,
                    busy_intervals=busy_by_user.get(participant.user_id, []),
                )
                logger.info(
                    "planning participant availability event=%s user=%s role=%s manual_intervals=%s busy_intervals=%s effective_intervals=%s",
                    event.id,
                    participant.user_id,
                    participant.role,
                    len(manual_intervals),
                    len(busy_by_user.get(participant.user_id, [])),
                    len(effective),
                )
                merged_preference = merge_preferred_practice_time(
                    merge_cached_practice_preference(
                        preferences_by_user.get(participant.user_id),
                        user.timezone,
                        user.preferred_practice_time_parsed,
                    ),
                    user.timezone,
                    user.preferred_practice_time,
                )
                participant_contexts.append(
                    ParticipantContext(
                        user_id=participant.user_id,
                        role=participant.role,
                        timezone=user.timezone,
                        effective_availability=effective,
                        preference=merged_preference,
                    )
                )

            organizer = users.get(event.organizer_user_id)
            if organizer is None:
                raise ValueError("Event organizer not found")
            organizer_preference = merge_preferred_practice_time(
                merge_cached_practice_preference(
                    preferences_by_user.get(organizer.id),
                    organizer.timezone,
                    organizer.preferred_practice_time_parsed,
                ),
                organizer.timezone,
                organizer.preferred_practice_time,
            )
            logger.info(
                "planning event input event=%s name=%s duration_minutes=%s earliest_start_date=%s min_days_apart=%s latest_schedule_at=%s next_session_index=%s sessions_remaining=%s required_participants=%s",
                event.id,
                event.name,
                event.duration_minutes,
                event.earliest_start_date,
                event.min_days_apart,
                event.latest_schedule_at,
                confirmed_count + 1,
                sessions_remaining,
                sum(1 for participant in event.participants if participant.role == "required"),
            )
            event_inputs.append(
                PlanningEventInput(
                    dance_event_id=event.id,
                    dance_name=event.name,
                    organizer_user_id=organizer.id,
                    organizer_timezone=organizer.timezone,
                    organizer_preference=organizer_preference,
                    duration_minutes=event.duration_minutes,
                    earliest_start_date=event.earliest_start_date,
                    min_days_apart=event.min_days_apart,
                    latest_schedule_at=event.latest_schedule_at,
                    next_session_index=confirmed_count + 1,
                    sessions_remaining=sessions_remaining,
                    confirmed_session_starts=[
                        ensure_utc(session.start_at)
                        for session in event.practice_sessions
                        if session.status == "confirmed"
                    ],
                    participants=participant_contexts,
                )
            )
        return event_inputs

    def _load_confirmed_reservations(self, horizon_start, horizon_end) -> list[SessionReservation]:
        sessions = list(
            self.db.scalars(
                select(PracticeSession)
                .where(PracticeSession.status == "confirmed")
                .where(PracticeSession.end_at > horizon_start)
                .where(PracticeSession.start_at < horizon_end)
                .options(selectinload(PracticeSession.dance_event).selectinload(DanceEvent.participants))
            )
        )
        reservations: list[SessionReservation] = []
        for session in sessions:
            required_attendees = frozenset(
                participant.user_id
                for participant in session.dance_event.participants
                if participant.role == "required"
                and str(participant.user_id) not in set(session.missing_required_user_ids_json or [])
            )
            reservations.append(
                SessionReservation(
                    identifier=str(session.id),
                    start_at=ensure_utc(session.start_at),
                    end_at=ensure_utc(session.end_at),
                    room_id=session.room_id,
                    participant_user_ids=required_attendees,
                    dance_event_id=session.dance_event_id,
                    session_index=session.session_index,
                )
            )
        return reservations

    def _get_or_create_room(self, room_id: UUID | None) -> Room:
        if room_id is not None:
            room = self.db.get(Room, room_id)
            if room is None or not room.is_active:
                raise ValueError("Room not found")
            return room

        room = self.db.scalars(
            select(Room).where(Room.is_active.is_(True)).order_by(Room.created_at.asc())
        ).first()
        if room is not None:
            return room

        existing_room = self.db.scalars(select(Room).order_by(Room.created_at.asc())).first()
        if existing_room is not None:
            existing_room.is_active = True
            self.db.add(existing_room)
            self.db.flush()
            return existing_room

        room = Room(name="Shared Studio", is_active=True)
        self.db.add(room)
        self.db.flush()
        return room


def _required_attendee_ids(result: PlanningRunResult) -> list[UUID]:
    missing_required = {UUID(value) for value in result.missing_required_user_ids_json or []}
    required_ids = []
    for participant in result.dance_event.participants:
        if participant.role != "required":
            continue
        if participant.user_id in missing_required:
            continue
        required_ids.append(participant.user_id)
    return required_ids


def _derive_event_status(required_session_count: int, confirmed_session_count: int) -> str:
    if confirmed_session_count <= 0:
        return "unscheduled"
    if confirmed_session_count >= required_session_count:
        return "scheduled"
    return "partially_scheduled"


def _count_confirmed_sessions(practice_sessions: list[PracticeSession]) -> int:
    return sum(1 for session in practice_sessions if session.status == "confirmed")


def _validate_result_against_event_constraints(
    result: PlanningRunResult,
    selected_starts: list[date],
) -> None:
    dance_event = result.dance_event
    organizer_zone = _organizer_zone_for_result(result)
    local_date = ensure_utc(result.start_at).astimezone(organizer_zone).date()

    if dance_event.earliest_start_date is not None and local_date < dance_event.earliest_start_date:
        raise ValueError("Selected planning result is before the dance's earliest start date")

    if dance_event.min_days_apart <= 0:
        return

    existing_dates = {
        ensure_utc(session.start_at).astimezone(organizer_zone).date()
        for session in dance_event.practice_sessions
        if session.status == "confirmed"
    }
    existing_dates.update(selected_starts)
    if any(abs((local_date - other_date).days) < dance_event.min_days_apart for other_date in existing_dates):
        raise ValueError("Selected planning result violates the dance's minimum days apart rule")


def _organizer_zone_for_result(result: PlanningRunResult):
    from zoneinfo import ZoneInfo

    return ZoneInfo(result.dance_event.organizer.timezone)
