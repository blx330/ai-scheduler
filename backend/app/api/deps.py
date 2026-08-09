from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.services.auth_service import SessionIdentity, decode_session
from app.infrastructure.auth.session_tokens import InvalidTokenError
from app.infrastructure.config import Settings
from app.infrastructure.integrations.google_calendar.client import GoogleCalendarProvider
from app.infrastructure.integrations.google_identity.client import GoogleIdentityProvider
from app.infrastructure.integrations.llm.profile_preference_parser import (
    UserProfilePreferenceParser,
    build_user_profile_preference_parser,
)

SESSION_COOKIE_NAME = "session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_user_profile_preference_parser(request: Request) -> UserProfilePreferenceParser:
    parser = getattr(request.app.state, "user_profile_preference_parser", None)
    if parser is not None:
        return parser
    settings = get_settings(request)
    return build_user_profile_preference_parser(api_key=settings.gemini_api_key, model=settings.gemini_model)


def get_google_calendar_client(request: Request) -> GoogleCalendarProvider:
    return request.app.state.google_calendar_client


def get_google_identity_client(request: Request) -> GoogleIdentityProvider:
    return request.app.state.google_identity_client


def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionIdentity:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    try:
        return decode_session(token, settings.session_secret or "")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid") from exc


def require_organizer(current_user: SessionIdentity = Depends(get_current_user)) -> SessionIdentity:
    if not current_user.is_organizer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action requires the organizer role")
    return current_user


def require_self_or_organizer(
    user_id: UUID,
    current_user: SessionIdentity = Depends(get_current_user),
) -> SessionIdentity:
    if not current_user.is_organizer and current_user.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage your own profile")
    return current_user
