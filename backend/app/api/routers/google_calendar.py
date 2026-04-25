from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_google_calendar_client, get_settings
from app.api.schemas.google_calendar import (
    GoogleBusySyncRequest,
    GoogleBusySyncResponse,
    GoogleCalendarConnectionRead,
    GoogleCalendarSelectionUpdate,
    GoogleCalendarSummaryRead,
    GoogleOAuthStartRequest,
    GoogleOAuthStartResponse,
)
from app.application.services.google_calendar_service import GoogleCalendarService
from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider

router = APIRouter(tags=["google-calendar"])


@router.get("/google-calendar/auth", response_model=GoogleOAuthStartResponse)
def start_google_oauth_for_user(
    user_id: UUID = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> GoogleOAuthStartResponse:
    try:
        authorization_url = GoogleCalendarService(db, settings, client).begin_oauth(user_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GoogleOAuthStartResponse(authorization_url=authorization_url)


@router.post("/google/oauth/start", response_model=GoogleOAuthStartResponse)
def start_google_oauth(
    payload: GoogleOAuthStartRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> GoogleOAuthStartResponse:
    try:
        authorization_url = GoogleCalendarService(db, settings, client).begin_oauth(payload.user_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GoogleOAuthStartResponse(authorization_url=authorization_url)


@router.get("/google/oauth/callback")
def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> RedirectResponse:
    service = GoogleCalendarService(db, settings, client)
    try:
        redirect_url = service.complete_oauth(code=code, state=state)
    except Exception as exc:  # noqa: BLE001 - callback should always redirect for the demo flow
        query = urlencode({"google_error": str(exc)})
        redirect_url = f"{settings.frontend_url.rstrip('/')}/?{query}"
    return RedirectResponse(url=redirect_url)


@router.get("/users/{user_id}/google/connection", response_model=GoogleCalendarConnectionRead)
def get_google_connection(
    user_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> GoogleCalendarConnectionRead:
    connection = GoogleCalendarService(db, settings, client).get_connection_status(user_id)
    return GoogleCalendarConnectionRead(
        user_id=connection.user_id,
        connected=connection.connected,
        status=connection.status,
        account_email=connection.account_email,
        selected_busy_calendar_ids=connection.selected_busy_calendar_ids,
        selected_write_calendar_id=connection.selected_write_calendar_id,
        token_expires_at=connection.token_expires_at,
    )


@router.get("/users/{user_id}/google/calendars", response_model=list[GoogleCalendarSummaryRead])
def list_google_calendars(
    user_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> list[GoogleCalendarSummaryRead]:
    try:
        calendars = GoogleCalendarService(db, settings, client).list_calendars(user_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        GoogleCalendarSummaryRead(
            id=item.id,
            summary=item.summary,
            primary=item.primary,
            access_role=item.access_role,
            time_zone=item.time_zone,
        )
        for item in calendars
    ]


@router.post("/users/{user_id}/google/calendars/select", response_model=GoogleCalendarConnectionRead)
def select_google_calendars(
    user_id: UUID,
    payload: GoogleCalendarSelectionUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> GoogleCalendarConnectionRead:
    try:
        connection = GoogleCalendarService(db, settings, client).save_calendar_selection(
            user_id=user_id,
            busy_calendar_ids=payload.busy_calendar_ids,
            write_calendar_id=payload.write_calendar_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GoogleCalendarConnectionRead(
        user_id=connection.user_id,
        connected=connection.connected,
        status=connection.status,
        account_email=connection.account_email,
        selected_busy_calendar_ids=connection.selected_busy_calendar_ids,
        selected_write_calendar_id=connection.selected_write_calendar_id,
        token_expires_at=connection.token_expires_at,
    )


@router.post("/users/{user_id}/google/sync-busy", response_model=GoogleBusySyncResponse)
def sync_google_busy_times(
    user_id: UUID,
    payload: GoogleBusySyncRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleCalendarProvider = Depends(get_google_calendar_client),
) -> GoogleBusySyncResponse:
    try:
        result = GoogleCalendarService(db, settings, client).sync_busy_intervals(
            user_id=user_id,
            horizon_start=payload.horizon_start,
            horizon_end=payload.horizon_end,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GoogleBusySyncResponse(
        user_id=result.user_id,
        synced_interval_count=result.synced_interval_count,
        calendar_ids=result.calendar_ids,
    )
