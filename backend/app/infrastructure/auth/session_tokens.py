"""Stateless, signed tokens for the login session cookie and the OAuth `state` param.

Same HMAC-over-base64url shape as the existing Google Calendar OAuth state signer
(`google_calendar_service._sign_state`/`_verify_state`), plus an `exp` claim so a
session or login attempt can actually expire -- the calendar-connect state token has
no server-side session to protect, but a login session left permanently valid is a
real liability if a cookie ever leaks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class InvalidTokenError(ValueError):
    pass


def sign_token(payload: dict[str, Any], secret: str, max_age_seconds: int) -> str:
    if not secret:
        raise RuntimeError("SESSION_SECRET env var is not set. Set it to a long random string (e.g. openssl rand -hex 32).")
    body = {**payload, "iat": int(time.time()), "exp": int(time.time()) + max_age_seconds}
    encoded_payload = _b64encode(json.dumps(body).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64encode(signature)}"


def verify_token(token: str, secret: str) -> dict[str, Any]:
    if not secret:
        raise RuntimeError("SESSION_SECRET env var is not set. Set it to a long random string (e.g. openssl rand -hex 32).")
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidTokenError("Malformed token") from exc

    expected_signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    try:
        actual_signature = _b64decode(encoded_signature)
    except ValueError as exc:
        raise InvalidTokenError("Malformed token") from exc
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise InvalidTokenError("Invalid token signature")

    payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise InvalidTokenError("Token expired")
    return payload


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
