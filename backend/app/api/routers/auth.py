from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    SESSION_COOKIE_NAME,
    get_current_user,
    get_db,
    get_google_identity_client,
    get_settings,
)
from app.api.schemas.auth import CurrentUserRead
from app.application.services.auth_service import (
    LOGIN_STATE_MAX_AGE_SECONDS,
    AuthService,
    SessionIdentity,
    UnknownGoogleAccountError,
)
from app.infrastructure.config import Settings
from app.infrastructure.db.models import User
from app.infrastructure.integrations.google_identity.client import GoogleIdentityProvider

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_NONCE_COOKIE_NAME = "login_nonce"


@router.get("/google/login")
def start_google_login(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleIdentityProvider = Depends(get_google_identity_client),
):
    try:
        start = AuthService(db, settings, client).begin_login()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    redirect = _redirect(start.authorization_url)
    redirect.set_cookie(
        key=LOGIN_NONCE_COOKIE_NAME,
        value=start.nonce,
        max_age=LOGIN_STATE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return redirect


@router.get("/google/callback")
def google_login_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleIdentityProvider = Depends(get_google_identity_client),
):
    try:
        result = AuthService(db, settings, client).complete_login(
            code=code, state=state, nonce=request.cookies.get(LOGIN_NONCE_COOKIE_NAME)
        )
    except UnknownGoogleAccountError as exc:
        return _redirect_with_error(settings, str(exc))
    except (ValueError, RuntimeError) as exc:
        return _redirect_with_error(settings, str(exc))

    redirect = _redirect(settings.frontend_url)
    redirect.delete_cookie(LOGIN_NONCE_COOKIE_NAME, path="/")
    _set_session_cookie(redirect, request, settings, result.session_token)
    return redirect


@router.get("/demo-login")
def demo_login(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GoogleIdentityProvider = Depends(get_google_identity_client),
):
    if not settings.admin_reset_token:
        # Same gate as /admin/reset-demo: only exists once a deployment opts into
        # being a public shared demo.
        raise HTTPException(status_code=404, detail="Not found")
    result = AuthService(db, settings, client).demo_login()
    redirect = _redirect(settings.frontend_url)
    _set_session_cookie(redirect, request, settings, result.session_token)
    return redirect


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=CurrentUserRead)
def get_current_user_profile(
    current_user: SessionIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # get_current_user already resolved the row (and 401s with a cleared cookie if
    # the account behind the session was deleted), so this cannot be None.
    return CurrentUserRead.model_validate(db.get(User, current_user.user_id))


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url)


def _redirect_with_error(settings: Settings, message: str):
    query = urlencode({"login_error": message})
    return _redirect(f"{settings.frontend_url.rstrip('/')}/?{query}")


def _set_session_cookie(redirect_response, request: Request, settings: Settings, token: str) -> None:
    redirect_response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_cookie_max_age_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
