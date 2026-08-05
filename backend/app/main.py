from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api.routers import admin, availability, events, google_calendar, health, planning, practices, users
from app.infrastructure.config import Settings
from app.infrastructure.db.session import build_session_factory
from app.infrastructure.demo_guard import DemoGuardMiddleware
from app.infrastructure.integrations.google_calendar.client import build_google_calendar_client
from app.infrastructure.integrations.llm.profile_preference_parser import build_user_profile_preference_parser
from app.infrastructure.scheduling.auto_sync import auto_sync_loop


def create_app(
    settings: Settings | None = None,
    session_factory=None,
    user_profile_preference_parser=None,
    google_calendar_client=None,
    static_dir: Path | None = None,
) -> FastAPI:
    app_settings = settings or Settings()
    session_factory = session_factory or build_session_factory(app_settings.database_url)
    google_calendar_client = google_calendar_client or build_google_calendar_client(
        client_id=app_settings.google_client_id,
        client_secret=app_settings.google_client_secret,
        redirect_uri=app_settings.google_redirect_uri,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        sync_task: asyncio.Task | None = None
        if app_settings.auto_sync_enabled:
            sync_task = asyncio.create_task(auto_sync_loop(session_factory, app_settings, google_calendar_client))
        _app.state.auto_sync_task = sync_task
        try:
            yield
        finally:
            if sync_task is not None:
                sync_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sync_task

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(DemoGuardMiddleware)
    app.state.settings = app_settings
    app.state.session_factory = session_factory
    app.state.user_profile_preference_parser = user_profile_preference_parser or build_user_profile_preference_parser(
        api_key=app_settings.gemini_api_key,
        model=app_settings.gemini_model,
    )
    app.state.google_calendar_client = google_calendar_client

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"] if part != "body")
            messages.append(f"{loc}: {error['msg']}" if loc else error["msg"])
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

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
    app.include_router(events.router, prefix=app_settings.api_prefix)
    app.include_router(planning.router, prefix=app_settings.api_prefix)
    app.include_router(practices.router, prefix=app_settings.api_prefix)
    app.include_router(google_calendar.router, prefix=app_settings.api_prefix)
    app.include_router(admin.router, prefix=app_settings.api_prefix)

    static_dir = static_dir or Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        index_path = static_dir / "index.html"

        api_prefix = app_settings.api_prefix.strip("/")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            # React Router routes (e.g. /calendar, /members/<id>) have no matching file
            # on disk -- StaticFiles(html=True) 404s on those instead of falling back to
            # index.html, so a direct visit or refresh on any route but "/" 404'd with a
            # bare JSON error instead of loading the app. Serve the real static asset
            # when the path matches one (JS/CSS/favicon/etc.), otherwise hand back
            # index.html and let the client-side router take over. Unmatched API paths
            # must stay real 404s, not silently become this catch-all's HTML response.
            if full_path == api_prefix or full_path.startswith(f"{api_prefix}/"):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (static_dir / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(static_dir):
                return FileResponse(candidate)
            return FileResponse(index_path)

    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Build the ASGI app on first attribute access rather than at import time.

    `uvicorn app.main:app` still resolves, but importing this module (as the test
    suite does, to reach `create_app`) no longer constructs a database engine and
    therefore no longer requires a reachable DATABASE_URL.
    """
    if name != "app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global _app
    if _app is None:
        _app = create_app()
    return _app
