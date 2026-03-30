from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api.routers import availability, events, google_calendar, health, planning, preferences, schedule_requests, users
from app.infrastructure.config import Settings
from app.infrastructure.db.session import build_session_factory
from app.infrastructure.integrations.google_calendar.client import build_google_calendar_client
from app.infrastructure.integrations.llm.parser import build_preference_parser


def create_app(
    settings: Optional[Settings] = None,
    session_factory=None,
    preference_parser=None,
    google_calendar_client=None,
) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title=app_settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = app_settings
    app.state.session_factory = session_factory or build_session_factory(app_settings.database_url)
    app.state.preference_parser = preference_parser or build_preference_parser(
        app_settings.parser_mode,
        api_key=app_settings.feather_api_key,
    )
    app.state.google_calendar_client = google_calendar_client or build_google_calendar_client(
        client_id=app_settings.google_client_id,
        client_secret=app_settings.google_client_secret,
        redirect_uri=app_settings.google_redirect_uri,
    )

    @app.exception_handler(OperationalError)
    async def handle_operational_error(_: Request, exc: OperationalError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database unavailable. Check DATABASE_URL and make sure Postgres is running.",
            },
        )

    @app.exception_handler(ProgrammingError)
    async def handle_programming_error(_: Request, exc: ProgrammingError) -> JSONResponse:
        detail = "Database query failed."
        if "does not exist" in str(exc).lower():
            detail = "Database schema is not initialized. Run `alembic upgrade head` from the backend directory."
        return JSONResponse(status_code=503, content={"detail": detail})

    app.include_router(health.router, prefix=app_settings.api_prefix)
    app.include_router(users.router, prefix=app_settings.api_prefix)
    app.include_router(availability.router, prefix=app_settings.api_prefix)
    app.include_router(preferences.router, prefix=app_settings.api_prefix)
    app.include_router(events.router, prefix=app_settings.api_prefix)
    app.include_router(planning.router, prefix=app_settings.api_prefix)
    app.include_router(schedule_requests.router, prefix=app_settings.api_prefix)
    app.include_router(google_calendar.router, prefix=app_settings.api_prefix)

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="demo")
    return app


app = create_app()
