from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_google_calendar_client, get_settings, require_organizer
from app.api.routers._planning_serializers import serialize_event, serialize_practice_session
from app.api.schemas.events import DanceEventCreate, DanceEventDeleteWarnings, DanceEventRead, DanceEventUpdate
from app.api.schemas.planning import PracticeSessionRead
from app.application.services.auth_service import SessionIdentity
from app.application.services.event_service import EventService
from app.application.services.google_calendar_service import GoogleCalendarService
from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=DanceEventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: DanceEventCreate, db: Session = Depends(get_db), _: SessionIdentity = Depends(require_organizer)
) -> DanceEventRead:
    try:
        event = EventService(db).create_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_event(event)


@router.get("", response_model=list[DanceEventRead])
def list_events(db: Session = Depends(get_db), _: SessionIdentity = Depends(get_current_user)) -> list[DanceEventRead]:
    events = EventService(db).list_events()
    return [serialize_event(event) for event in events]


@router.get("/{event_id}", response_model=DanceEventRead)
def get_event(event_id: UUID, db: Session = Depends(get_db), _: SessionIdentity = Depends(get_current_user)) -> DanceEventRead:
    event = EventService(db).get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_event(event)


@router.patch("/{event_id}", response_model=DanceEventRead)
def update_event(
    event_id: UUID,
    payload: DanceEventUpdate,
    db: Session = Depends(get_db),
    _: SessionIdentity = Depends(require_organizer),
) -> DanceEventRead:
    try:
        event = EventService(db).update_event(event_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_event(event)


@router.get("/{event_id}/sessions", response_model=list[PracticeSessionRead])
def list_event_sessions(
    event_id: UUID, db: Session = Depends(get_db), _: SessionIdentity = Depends(get_current_user)
) -> list[PracticeSessionRead]:
    sessions = EventService(db).list_sessions(event_id)
    if sessions is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return [serialize_practice_session(session) for session in sessions]


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={200: {"model": DanceEventDeleteWarnings, "description": "Deleted, but some Google events remain"}},
)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
    _: SessionIdentity = Depends(require_organizer),
) -> Response:
    warnings = EventService(db).delete_event(event_id, google_calendar_service=GoogleCalendarService(db, settings, client))
    if warnings is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if warnings:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"warnings": warnings})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
