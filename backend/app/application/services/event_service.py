from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas.events import DanceEventCreate, DanceEventUpdate
from app.domain.common.datetime_utils import ensure_utc
from app.infrastructure.db.models import DanceEvent, DanceEventParticipant, PracticeSession, User


class EventService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event(self, payload: DanceEventCreate) -> DanceEvent:
        organizer = self.db.get(User, payload.organizer_user_id)
        if organizer is None:
            raise ValueError("Organizer not found")

        normalized_roles = _normalize_participants(payload.participants)
        user_ids = {participant.user_id for participant in payload.participants}
        if normalized_roles.keys() != user_ids:
            raise ValueError("Duplicate participants could not be normalized")

        self._validate_participants(user_ids)

        event = DanceEvent(
            name=payload.name,
            description=payload.description,
            organizer_user_id=payload.organizer_user_id,
            duration_minutes=payload.duration_minutes,
            earliest_start_date=payload.earliest_start_date,
            min_days_apart=payload.min_days_apart,
            latest_schedule_at=ensure_utc(payload.latest_schedule_at),
            required_session_count=payload.required_session_count,
            status="unscheduled",
        )
        self.db.add(event)
        self.db.flush()

        for user_id, role in normalized_roles.items():
            self.db.add(DanceEventParticipant(dance_event_id=event.id, user_id=user_id, role=role))

        self.db.commit()
        return self.get_event(event.id)  # type: ignore[return-value]

    def list_events(self) -> list[DanceEvent]:
        statement = (
            select(DanceEvent)
            .order_by(DanceEvent.created_at.desc())
            .options(selectinload(DanceEvent.participants), selectinload(DanceEvent.practice_sessions))
        )
        return list(self.db.scalars(statement))

    def get_event(self, event_id: UUID) -> Optional[DanceEvent]:
        statement = (
            select(DanceEvent)
            .where(DanceEvent.id == event_id)
            .options(selectinload(DanceEvent.participants), selectinload(DanceEvent.practice_sessions))
        )
        return self.db.scalars(statement).one_or_none()

    def update_event(self, event_id: UUID, payload: DanceEventUpdate) -> Optional[DanceEvent]:
        event = self.get_event(event_id)
        if event is None:
            return None

        if payload.organizer_user_id is not None:
            organizer = self.db.get(User, payload.organizer_user_id)
            if organizer is None:
                raise ValueError("Organizer not found")
            event.organizer_user_id = payload.organizer_user_id
        if payload.name is not None:
            event.name = payload.name
        if "description" in payload.model_fields_set:
            event.description = payload.description
        if payload.duration_minutes is not None:
            event.duration_minutes = payload.duration_minutes
        if "earliest_start_date" in payload.model_fields_set:
            event.earliest_start_date = payload.earliest_start_date
        if payload.min_days_apart is not None:
            event.min_days_apart = payload.min_days_apart
        if payload.latest_schedule_at is not None:
            event.latest_schedule_at = ensure_utc(payload.latest_schedule_at)
        if payload.required_session_count is not None:
            event.required_session_count = payload.required_session_count
        if payload.status is not None:
            event.status = payload.status

        if payload.participants is not None:
            normalized_roles = _normalize_participants(payload.participants)
            self._validate_participants(set(normalized_roles))
            event.participants.clear()
            self.db.flush()
            for user_id, role in normalized_roles.items():
                event.participants.append(DanceEventParticipant(dance_event_id=event.id, user_id=user_id, role=role))

        confirmed_count = _count_confirmed_sessions(event.practice_sessions)
        if payload.status is None and event.status not in {"archived", "completed"}:
            event.status = _derive_event_status(event.required_session_count, confirmed_count)
        self.db.add(event)
        self.db.commit()
        return self.get_event(event.id)

    def list_sessions(self, event_id: UUID) -> Optional[list[PracticeSession]]:
        event = self.get_event(event_id)
        if event is None:
            return None
        return sorted(event.practice_sessions, key=lambda item: (item.session_index, item.start_at))

    def delete_event(self, event_id: UUID) -> bool:
        event = self.db.get(DanceEvent, event_id)
        if event is None:
            return False
        self.db.delete(event)
        self.db.commit()
        return True

    def _validate_participants(self, user_ids: set[UUID]) -> None:
        if not user_ids:
            raise ValueError("At least one participant is required")
        existing_users = set(self.db.scalars(select(User.id).where(User.id.in_(user_ids))))
        if existing_users != user_ids:
            raise ValueError("One or more participants do not exist")


def _normalize_participants(participants) -> dict[UUID, str]:
    normalized_roles: dict[UUID, str] = {}
    for participant in participants:
        if participant.role not in {"required", "optional"}:
            raise ValueError("Participant role must be 'required' or 'optional'")
        current_role = normalized_roles.get(participant.user_id)
        if current_role == "required" or participant.role == "required":
            normalized_roles[participant.user_id] = "required"
        else:
            normalized_roles[participant.user_id] = participant.role
    if not normalized_roles:
        raise ValueError("At least one participant is required")
    if all(role != "required" for role in normalized_roles.values()):
        raise ValueError("At least one required participant is required")
    return normalized_roles


def _derive_event_status(required_session_count: int, confirmed_session_count: int) -> str:
    if confirmed_session_count <= 0:
        return "unscheduled"
    if confirmed_session_count >= required_session_count:
        return "scheduled"
    return "partially_scheduled"


def _count_confirmed_sessions(practice_sessions: list[PracticeSession]) -> int:
    return sum(1 for session in practice_sessions if session.status == "confirmed")
