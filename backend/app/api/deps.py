from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider
from app.infrastructure.integrations.llm.parser import PreferenceParser, build_preference_parser


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_preference_parser(request: Request) -> PreferenceParser:
    parser = getattr(request.app.state, "preference_parser", None)
    if parser is not None:
        return parser
    settings = get_settings(request)
    return build_preference_parser(
        settings.parser_mode,
        api_key=settings.groq_api_key or settings.feather_api_key,
    )


def get_google_calendar_client(request: Request) -> GoogleCalendarProvider:
    return request.app.state.google_calendar_client
