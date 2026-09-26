"""Google sign-in: match/create a users row from a verified Google identity.

This app has no separate "account" concept -- a login just resolves to one of the
existing team-roster `users` rows (created by an organizer, same as before this
feature existed) or, for an admin email, provisions one. Everyone else who isn't on
the roster and isn't an admin email is rejected: this is a private team tool, not
open signup.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.common.enums import UserRole
from app.infrastructure.auth.session_tokens import InvalidTokenError, sign_token, verify_token
from app.infrastructure.config import Settings
from app.infrastructure.db.models import User
from app.infrastructure.integrations.google_identity.client import GoogleIdentity, GoogleIdentityProvider

LOGIN_STATE_MAX_AGE_SECONDS = 10 * 60
DEMO_GUEST_EMAIL = "demo-guest@ai-scheduler.local"
# Fixed so the guest row the demo seed recreates on every reset keeps the same id,
# and sessions issued before a reset stay valid.
DEMO_GUEST_USER_ID = UUID("00000000-0000-4000-8000-0000000d3e00")


@dataclass(frozen=True)
class LoginResult:
    user: User
    session_token: str


@dataclass(frozen=True)
class LoginStart:
    authorization_url: str
    # Random value the browser holds in a short-lived cookie; the callback must present
    # the same one, so a signed state cannot be replayed from a different browser.
    nonce: str


class UnknownGoogleAccountError(ValueError):
    """Raised when the Google account isn't linked to any team-roster profile."""


class AuthService:
    def __init__(self, db: Session, settings: Settings, identity_client: GoogleIdentityProvider) -> None:
        self.db = db
        self.settings = settings
        self.identity_client = identity_client

    def begin_login(self) -> LoginStart:
        nonce = secrets.token_urlsafe(32)
        state = sign_token({"purpose": "login_state", "nonce": nonce}, self._secret(), LOGIN_STATE_MAX_AGE_SECONDS)
        return LoginStart(authorization_url=self.identity_client.build_authorization_url(state), nonce=nonce)

    def complete_login(self, code: str, state: str, nonce: str | None) -> LoginResult:
        self._verify_state(state, nonce)
        identity = self.identity_client.exchange_code(code)
        user = self._resolve_user(identity)
        return LoginResult(user=user, session_token=self._issue_session(user))

    def demo_login(self) -> LoginResult:
        """Log in as a shared, always-organizer guest profile. Only ever called from a
        route gated on ADMIN_RESET_TOKEN being set -- i.e. only on the public demo
        deployment, where "anyone can edit anything" is already the documented model."""
        user = self._find_demo_guest()
        if user is None:
            user = User(
                id=DEMO_GUEST_USER_ID,
                display_name="Demo Guest",
                email=DEMO_GUEST_EMAIL,
                timezone="America/New_York",
                role=UserRole.ORGANIZER.value,
            )
            self.db.add(user)
            try:
                self.db.commit()
            except IntegrityError:
                # Two first visitors raced to create the guest; reuse the winner's row.
                self.db.rollback()
                user = self._find_demo_guest()
                if user is None:
                    raise
            self.db.refresh(user)
        return LoginResult(user=user, session_token=self._issue_session(user))

    def _find_demo_guest(self) -> User | None:
        user = self.db.get(User, DEMO_GUEST_USER_ID)
        if user is None:
            user = self.db.scalars(select(User).where(func.lower(User.email) == DEMO_GUEST_EMAIL)).first()
        return user

    def _resolve_user(self, identity: GoogleIdentity) -> User:
        user = self.db.scalars(select(User).where(User.google_subject_id == identity.subject)).first()
        # An unverified email proves nothing about who owns it; only the stable Google
        # subject id may be trusted for such an account.
        if user is None and not identity.email_verified:
            raise UnknownGoogleAccountError(
                f"Google has not verified the email {identity.email}, so it cannot be matched to a team profile."
            )
        if user is None:
            user = self.db.scalars(select(User).where(func.lower(User.email) == identity.email)).first()

        is_admin_email = identity.email_verified and identity.email in self.settings.admin_emails
        if user is None:
            if not is_admin_email:
                raise UnknownGoogleAccountError(
                    f"No team profile found for {identity.email}. Ask an organizer to add you first."
                )
            user = User(
                display_name=identity.name or identity.email,
                email=identity.email,
                timezone="UTC",
                role=UserRole.ORGANIZER.value,
                google_subject_id=identity.subject,
            )
            self.db.add(user)
        else:
            user.google_subject_id = identity.subject
            if is_admin_email:
                user.role = UserRole.ORGANIZER.value
        self.db.commit()
        self.db.refresh(user)
        return user

    def _issue_session(self, user: User) -> str:
        max_age_seconds = self.settings.session_cookie_max_age_days * 24 * 60 * 60
        return sign_token(
            {"purpose": "session", "sub": str(user.id), "role": user.role},
            self._secret(),
            max_age_seconds,
        )

    def _verify_state(self, state: str, nonce: str | None) -> None:
        try:
            payload = verify_token(state, self._secret())
        except InvalidTokenError as exc:
            raise ValueError("Invalid or expired sign-in attempt. Please try again.") from exc
        if payload.get("purpose") != "login_state":
            raise ValueError("Invalid sign-in state")
        expected_nonce = payload.get("nonce")
        if not nonce or not isinstance(expected_nonce, str) or not hmac.compare_digest(expected_nonce, nonce):
            raise ValueError("Invalid or expired sign-in attempt. Please try again.")

    def _secret(self) -> str:
        if not self.settings.session_secret:
            raise RuntimeError(
                "SESSION_SECRET env var is not set. Set it to a long random string (e.g. openssl rand -hex 32)."
            )
        return self.settings.session_secret


@dataclass(frozen=True)
class SessionIdentity:
    user_id: UUID
    role: str

    @property
    def is_organizer(self) -> bool:
        return self.role == UserRole.ORGANIZER.value


def decode_session(token: str, secret: str) -> SessionIdentity:
    payload = verify_token(token, secret)
    if payload.get("purpose") != "session":
        raise InvalidTokenError("Not a session token")
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Session token has no subject")
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise InvalidTokenError("Session token subject is not a user id") from exc
    return SessionIdentity(user_id=user_id, role=payload.get("role", UserRole.MEMBER.value))
