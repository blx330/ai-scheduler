from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_google_calendar_client, get_settings
from app.api.schemas.planning import PracticeUnscheduleResponse
from app.application.services.google_calendar_service import GoogleCalendarService
from app.application.services.planning_service import PlanningService
from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider

router = APIRouter(prefix="/practices", tags=["practices"])


@router.delete("/{practice_id}/schedule", response_model=PracticeUnscheduleResponse)
def unschedule_practice(
    practice_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> PracticeUnscheduleResponse:
    planning_service = PlanningService(db)
    practice_session = planning_service.get_practice_session(practice_id)
    if practice_session is None:
        raise HTTPException(status_code=404, detail="Practice session not found")

    google_event_deleted = False
    warning = None
    google_service = GoogleCalendarService(db, settings, client)
    try:
        google_event_deleted = google_service.delete_event_for_practice_session(practice_id)
    except (ValueError, RuntimeError) as exc:
        warning = str(exc)

    unscheduled_session = planning_service.unschedule_practice_session(practice_id)
    if unscheduled_session is None:
        raise HTTPException(status_code=404, detail="Practice session not found")

    return PracticeUnscheduleResponse(
        practice_id=practice_id,
        dance_event_id=practice_session.dance_event_id,
        unscheduled=True,
        google_event_deleted=google_event_deleted,
        warning=warning,
    )
