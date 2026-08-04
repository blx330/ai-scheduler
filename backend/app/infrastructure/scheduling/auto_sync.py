from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.google_calendar_service import GoogleCalendarService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import CalendarConnection
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider

logger = logging.getLogger(__name__)

_SYNCABLE_STATUSES = ("connected", "configured")


def sync_all_connections(
    session_factory: sessionmaker,
    settings: Settings,
    client: GoogleCalendarProvider,
    horizon_days: int,
) -> None:
    """Refresh busy intervals for every connected member in one sweep.

    Runs on a background thread on a timer, so one member's revoked token or
    a transient Google error must not stop the rest of the sweep.
    """
    db: Session = session_factory()
    try:
        connection_ids = list(
            db.scalars(select(CalendarConnection.user_id).where(CalendarConnection.status.in_(_SYNCABLE_STATUSES)))
        )
        now = datetime.now(UTC)
        horizon_end = now + timedelta(days=horizon_days)
        service = GoogleCalendarService(db, settings, client)
        for user_id in connection_ids:
            try:
                service.sync_busy_intervals(user_id=user_id, horizon_start=now, horizon_end=horizon_end)
            except (ValueError, RuntimeError):
                logger.warning("Auto-sync failed for user %s", user_id, exc_info=True)
    finally:
        db.close()


async def auto_sync_loop(
    session_factory: sessionmaker,
    settings: Settings,
    client: GoogleCalendarProvider,
) -> None:
    """Sweep every connected member's busy time on a timer until cancelled.

    The Google client and DB session are both synchronous, so the sweep runs in a
    worker thread via `to_thread` -- a bare `await` here would otherwise block the
    single event loop for the duration of every Google API round-trip.
    """
    while True:
        try:
            await asyncio.to_thread(
                sync_all_connections,
                session_factory,
                settings,
                client,
                settings.auto_sync_horizon_days,
            )
        except Exception:
            logger.exception("Auto-sync sweep failed")
        await asyncio.sleep(settings.auto_sync_interval_minutes * 60)
