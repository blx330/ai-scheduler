from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_google_calendar_client, get_settings
from app.api.schemas.schedule import (
    CreatedEventRead,
    ScheduleRequestCreate,
    ScheduleRequestParticipantRead,
    ScheduleRequestRead,
    ScheduleRunConfirmRequest,
    ScheduleRunRead,
)
from app.application.services.google_calendar_service import GoogleCalendarService
from app.application.services.scheduling_service import SchedulingService
from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider

router = APIRouter(tags=["schedule-requests"])


@router.post("/schedule-requests", response_model=ScheduleRequestRead, status_code=status.HTTP_201_CREATED)
def create_schedule_request(
    payload: ScheduleRequestCreate,
    db: Session = Depends(get_db),
) -> ScheduleRequestRead:
    try:
        schedule_request = SchedulingService(db).create_schedule_request(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_schedule_request(schedule_request)


@router.get("/schedule-requests", response_model=list[ScheduleRequestRead])
def list_schedule_requests(db: Session = Depends(get_db)) -> list[ScheduleRequestRead]:
    requests = SchedulingService(db).list_schedule_requests()
    return [_serialize_schedule_request(item) for item in requests]


@router.get("/schedule-requests/{schedule_request_id}", response_model=ScheduleRequestRead)
def get_schedule_request(schedule_request_id: UUID, db: Session = Depends(get_db)) -> ScheduleRequestRead:
    schedule_request = SchedulingService(db).get_schedule_request(schedule_request_id)
    if schedule_request is None:
        raise HTTPException(status_code=404, detail="Schedule request not found")
    return _serialize_schedule_request(schedule_request)


@router.post("/schedule-requests/{schedule_request_id}/run", response_model=ScheduleRunRead)
def run_schedule_request(schedule_request_id: UUID, db: Session = Depends(get_db)) -> ScheduleRunRead:
    run = SchedulingService(db).run_schedule_request(schedule_request_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Schedule request not found")
    return ScheduleRunRead(
        id=run.id,
        schedule_request_id=run.schedule_request_id,
        status=run.status,
        results=run.results,
    )


@router.get("/schedule-runs/{schedule_run_id}", response_model=ScheduleRunRead)
def get_schedule_run(schedule_run_id: UUID, db: Session = Depends(get_db)) -> ScheduleRunRead:
    run = SchedulingService(db).get_schedule_run(schedule_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Schedule run not found")
    return ScheduleRunRead(
        id=run.id,
        schedule_request_id=run.schedule_request_id,
        status=run.status,
        results=run.results,
    )


@router.post("/schedule-runs/{schedule_run_id}/confirm", response_model=CreatedEventRead)
def confirm_schedule_run(
    schedule_run_id: UUID,
    payload: ScheduleRunConfirmRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> CreatedEventRead:
    try:
        created_event = GoogleCalendarService(db, settings, client).create_event_for_schedule_run(
            schedule_run_id=schedule_run_id,
            rank=payload.rank,
            calendar_id=payload.calendar_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CreatedEventRead(
        event_id=created_event.event_id,
        html_link=created_event.html_link,
        status=created_event.status,
        calendar_id=created_event.calendar_id,
        start_at=created_event.start_at,
        end_at=created_event.end_at,
    )


def _serialize_schedule_request(schedule_request) -> ScheduleRequestRead:
    return ScheduleRequestRead(
        id=schedule_request.id,
        title=schedule_request.title,
        organizer_user_id=schedule_request.organizer_user_id,
        duration_minutes=schedule_request.duration_minutes,
        horizon_start=schedule_request.horizon_start,
        horizon_end=schedule_request.horizon_end,
        slot_step_minutes=schedule_request.slot_step_minutes,
        daily_window_start_local=schedule_request.daily_window_start_local,
        daily_window_end_local=schedule_request.daily_window_end_local,
        preferred_weekdays=schedule_request.preferred_weekdays_json or [],
        preferred_time_range_start_local=schedule_request.preferred_time_range_start_local,
        preferred_time_range_end_local=schedule_request.preferred_time_range_end_local,
        status=schedule_request.status,
        participants=[
            ScheduleRequestParticipantRead(user_id=item.user_id, role=item.role)
            for item in getattr(schedule_request, "participants", [])
        ],
    )
