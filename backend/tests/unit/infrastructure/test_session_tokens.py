import hashlib
import hmac
import json
import time

import pytest

from app.application.services.auth_service import decode_session
from app.infrastructure.auth.session_tokens import InvalidTokenError, _b64encode, sign_token, verify_token


def test_sign_then_verify_roundtrips_the_payload() -> None:
    token = sign_token({"sub": "user-1", "role": "organizer"}, "secret", max_age_seconds=60)
    payload = verify_token(token, "secret")
    assert payload["sub"] == "user-1"
    assert payload["role"] == "organizer"
    assert "iat" in payload and "exp" in payload


def test_verify_rejects_a_tampered_signature() -> None:
    token = sign_token({"sub": "user-1"}, "secret", max_age_seconds=60)
    with pytest.raises(InvalidTokenError):
        verify_token(token, "a-different-secret")


def test_verify_rejects_an_expired_token() -> None:
    token = sign_token({"sub": "user-1"}, "secret", max_age_seconds=-1)
    with pytest.raises(InvalidTokenError):
        verify_token(token, "secret")


def test_verify_rejects_a_malformed_token() -> None:
    with pytest.raises(InvalidTokenError):
        verify_token("not-a-token-at-all", "secret")


def test_sign_requires_a_secret() -> None:
    with pytest.raises(RuntimeError):
        sign_token({"sub": "user-1"}, "", max_age_seconds=60)


def test_verify_requires_a_secret() -> None:
    with pytest.raises(RuntimeError):
        verify_token("whatever", "")


def _signed(body: bytes, secret: str = "secret") -> str:
    """A correctly signed token whose payload is whatever `body` is -- valid JSON or not."""
    encoded = _b64encode(body)
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


@pytest.mark.parametrize(
    "body",
    [
        b"not json at all",
        b"[1, 2, 3]",
        b'"just a string"',
        json.dumps({"sub": "x", "exp": "soon"}).encode(),
        json.dumps({"sub": "x", "exp": None}).encode(),
        json.dumps({"sub": "x", "exp": [1]}).encode(),
    ],
)
def test_verify_rejects_a_signed_but_malformed_payload(body: bytes) -> None:
    with pytest.raises(InvalidTokenError):
        verify_token(_signed(body), "secret")


@pytest.mark.parametrize(
    "payload",
    [
        {"purpose": "session", "role": "organizer"},
        {"purpose": "session", "sub": "not-a-uuid", "role": "organizer"},
        {"purpose": "session", "sub": 42, "role": "organizer"},
        {"purpose": "session", "sub": None, "role": "organizer"},
    ],
)
def test_decode_session_rejects_a_missing_or_invalid_subject(payload: dict) -> None:
    token = sign_token(payload, "secret", max_age_seconds=60)
    with pytest.raises(InvalidTokenError):
        decode_session(token, "secret")


def test_sign_token_reads_the_clock_once(monkeypatch) -> None:
    clock_reads: list[float] = []

    def fake_time() -> float:
        clock_reads.append(1_000.0)
        return 1_000.0

    monkeypatch.setattr(time, "time", fake_time)
    token = sign_token({"sub": "u"}, "secret", max_age_seconds=60)
    assert len(clock_reads) == 1
    payload = verify_token(token, "secret")
    assert payload["iat"] == 1_000 and payload["exp"] == 1_060
