from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# Google validates the id_token's signature server-side and hands back its claims --
# avoids pulling in a JWT/JWK-verification library for a login flow this small.
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_ID_TOKEN_SCOPES = ["openid", "email", "profile"]
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    name: str | None


class GoogleIdentityProvider(Protocol):
    def build_authorization_url(self, state: str) -> str:
        ...

    def exchange_code(self, code: str) -> GoogleIdentity:
        ...


class GoogleIdentityClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_ID_TOKEN_SCOPES),
                "prompt": "select_account",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> GoogleIdentity:
        response = self._requests().post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        self._raise_for_google_error(response, "Google sign-in token exchange")
        id_token = response.json().get("id_token")
        if not id_token:
            raise RuntimeError("Google sign-in token exchange did not return an id_token")
        return self._verify_id_token(id_token)

    def _verify_id_token(self, id_token: str) -> GoogleIdentity:
        response = self._requests().get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token}, timeout=30)
        self._raise_for_google_error(response, "Google sign-in token verification")
        claims = response.json()
        if claims.get("aud") != self.client_id:
            raise RuntimeError("Google sign-in token was issued for a different app")
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise RuntimeError("Google sign-in token has an unexpected issuer")
        email = claims.get("email")
        subject = claims.get("sub")
        if not email or not subject:
            raise RuntimeError("Google sign-in token is missing email or subject claims")
        return GoogleIdentity(
            subject=subject,
            email=email.strip().lower(),
            email_verified=str(claims.get("email_verified", "false")).lower() == "true",
            name=claims.get("name"),
        )

    @staticmethod
    def _requests():
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests must be installed to use Google sign-in") from exc
        return requests

    @staticmethod
    def _raise_for_google_error(response: Any, operation: str) -> None:
        if 200 <= int(response.status_code) < 300:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = None
        message = None
        if isinstance(payload, dict):
            message = payload.get("error_description") or payload.get("error")
        raise RuntimeError(f"{operation} failed: {message or f'HTTP {response.status_code}'}")


class NoopGoogleIdentityProvider:
    def __init__(self, missing_env_vars: list[str]) -> None:
        self.missing_env_vars = missing_env_vars

    def _raise_unconfigured(self, operation: str) -> None:
        missing_vars = ", ".join(self.missing_env_vars)
        logger.warning(
            "Google sign-in noop provider called for operation '%s'. Missing env vars: [%s]",
            operation,
            missing_vars,
        )
        raise RuntimeError(f"Google sign-in not configured for operation '{operation}'. Missing env vars: [{missing_vars}]")

    def build_authorization_url(self, state: str) -> str:
        self._raise_unconfigured("build_authorization_url")

    def exchange_code(self, code: str) -> GoogleIdentity:
        self._raise_unconfigured("exchange_code")


def build_google_identity_client(
    client_id: str | None,
    client_secret: str | None,
    redirect_uri: str | None,
) -> GoogleIdentityProvider:
    missing_env_vars = []
    if not client_id or not client_id.strip():
        missing_env_vars.append("GOOGLE_CLIENT_ID")
    if not client_secret or not client_secret.strip():
        missing_env_vars.append("GOOGLE_CLIENT_SECRET")
    if not redirect_uri or not redirect_uri.strip():
        missing_env_vars.append("GOOGLE_LOGIN_REDIRECT_URI")
    if not missing_env_vars:
        return GoogleIdentityClient(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    logger.warning(
        "Google sign-in not configured. Missing env vars: [%s]. Login will be unavailable.",
        ", ".join(missing_env_vars),
    )
    return NoopGoogleIdentityProvider(missing_env_vars=missing_env_vars)
