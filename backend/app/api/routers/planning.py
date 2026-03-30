from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routers._planning_serializers import (
    serialize_busy_interval,
    serialize_planning_run,
    serialize_practice_session,
)
from app.api.schemas.planning import (
    CalendarOverviewRead,
    PlanningRunConfirmRequest,
    PlanningRunConfirmResponse,
    PlanningRunCreate,
    PlanningRunRead,
)
from app.application.services.planning_service import PlanningService
from app.domain.common.datetime_utils import ensure_utc

router = APIRouter(tags=["planning"])


@router.post("/planning-runs", response_model=PlanningRunRead)
def create_planning_run(
    payload: PlanningRunCreate,
    db: Session = Depends(get_db),
) -> PlanningRunRead:
    try:
        run = PlanningService(db).create_planning_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_planning_run(run)


@router.get("/planning-runs/{run_id}", response_model=PlanningRunRead)
def get_planning_run(run_id: UUID, db: Session = Depends(get_db)) -> PlanningRunRead:
    run = PlanningService(db).get_planning_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Planning run not found")
    return serialize_planning_run(run)


@router.post("/planning-runs/{run_id}/confirm", response_model=PlanningRunConfirmResponse)
def confirm_planning_results(
    run_id: UUID,
    payload: PlanningRunConfirmRequest,
    db: Session = Depends(get_db),
) -> PlanningRunConfirmResponse:
    try:
        run, confirmed_sessions = PlanningService(db).confirm_results(run_id, payload.result_ids)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Planning run not found" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return PlanningRunConfirmResponse(
        planning_run_id=run.id,
        confirmed_sessions=[serialize_practice_session(session) for session in confirmed_sessions],
    )


@router.get("/calendar/overview", response_model=CalendarOverviewRead)
def get_calendar_overview(
    start: datetime,
    end: datetime,
    db: Session = Depends(get_db),
) -> CalendarOverviewRead:
    try:
        busy_intervals, practice_sessions = PlanningService(db).get_calendar_overview(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CalendarOverviewRead(
        start_at=ensure_utc(start),
        end_at=ensure_utc(end),
        busy_intervals=[serialize_busy_interval(interval) for interval in busy_intervals],
        practice_sessions=[serialize_practice_session(session) for session in practice_sessions],
    )
