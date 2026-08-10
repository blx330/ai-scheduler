"""Shared helpers for authenticating a TestClient without a real Google login.

Tests that build their own Settings()/TestClient outside the `client` fixture (to
tweak ADMIN_RESET_TOKEN, static_dir, etc.) still hit routes that now require a
session cookie. Mint one directly with the same signer the app uses, rather than
running a fake OAuth round-trip per test.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.deps import SESSION_COOKIE_NAME
from app.domain.common.enums import UserRole
from app.infrastructure.auth.session_tokens import sign_token

TEST_SESSION_SECRET = "test-session-secret"


def session_cookie(role: str, user_id: UUID | None = None) -> str:
    return sign_token(
        {"purpose": "session", "sub": str(user_id or uuid4()), "role": role},
        TEST_SESSION_SECRET,
        max_age_seconds=3600,
    )


def log_in(test_client: TestClient, role: str = UserRole.ORGANIZER.value, user_id: UUID | None = None) -> UUID:
    resolved_user_id = user_id or uuid4()
    test_client.cookies.set(SESSION_COOKIE_NAME, session_cookie(role, resolved_user_id))
    return resolved_user_id
