from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routers._planning_serializers import serialize_event, serialize_practice_session
from app.api.schemas.events import DanceEventCreate, DanceEventRead, DanceEventUpdate
from app.api.schemas.planning import PracticeSessionRead
from app.application.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=DanceEventRead, status_code=status.HTTP_201_CREATED)
def create_event(payload: DanceEventCreate, db: Session = Depends(get_db)) -> DanceEventRead:
    try:
        event = EventService(db).create_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_event(event)


@router.get("", response_model=list[DanceEventRead])
def list_events(db: Session = Depends(get_db)) -> list[DanceEventRead]:
    events = EventService(db).list_events()
    return [serialize_event(event) for event in events]


@router.get("/{event_id}", response_model=DanceEventRead)
def get_event(event_id: UUID, db: Session = Depends(get_db)) -> DanceEventRead:
    event = EventService(db).get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_event(event)


@router.patch("/{event_id}", response_model=DanceEventRead)
def update_event(
    event_id: UUID,
    payload: DanceEventUpdate,
    db: Session = Depends(get_db),
) -> DanceEventRead:
    try:
        event = EventService(db).update_event(event_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_event(event)


@router.get("/{event_id}/sessions", response_model=list[PracticeSessionRead])
def list_event_sessions(event_id: UUID, db: Session = Depends(get_db)) -> list[PracticeSessionRead]:
    sessions = EventService(db).list_sessions(event_id)
    if sessions is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return [serialize_practice_session(session) for session in sessions]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: UUID, db: Session = Depends(get_db)) -> None:
    deleted = EventService(db).delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
