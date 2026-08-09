import pytest

from app.infrastructure.auth.session_tokens import InvalidTokenError, sign_token, verify_token


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
