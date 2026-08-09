import pytest

from app.infrastructure.integrations.google_identity.client import (
    GoogleIdentityClient,
    NoopGoogleIdentityProvider,
    build_google_identity_client,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload or {}


class FakeRequests:
    def __init__(self, token_response: FakeResponse, tokeninfo_response: FakeResponse) -> None:
        self.token_response = token_response
        self.tokeninfo_response = tokeninfo_response

    def post(self, url, data=None, timeout=None):
        assert "token" in url
        return self.token_response

    def get(self, url, params=None, timeout=None):
        assert "tokeninfo" in url
        return self.tokeninfo_response


def _client_with_fake_requests(fake_requests: FakeRequests) -> GoogleIdentityClient:
    client = GoogleIdentityClient(client_id="client-id", client_secret="client-secret", redirect_uri="http://x/callback")
    client._requests = lambda: fake_requests
    return client


def test_build_authorization_url_requests_openid_email_profile_scopes() -> None:
    client = GoogleIdentityClient(client_id="client-id", client_secret="secret", redirect_uri="http://x/callback")
    url = client.build_authorization_url("state-token")
    assert "scope=openid+email+profile" in url
    assert "state=state-token" in url
    assert "client_id=client-id" in url


def test_exchange_code_verifies_id_token_and_extracts_identity() -> None:
    fake_requests = FakeRequests(
        token_response=FakeResponse(200, {"id_token": "fake-id-token"}),
        tokeninfo_response=FakeResponse(
            200,
            {
                "sub": "12345",
                "email": "Dancer@Example.com",
                "email_verified": "true",
                "aud": "client-id",
                "iss": "https://accounts.google.com",
                "name": "Dancer Person",
            },
        ),
    )
    client = _client_with_fake_requests(fake_requests)

    identity = client.exchange_code("auth-code")

    assert identity.subject == "12345"
    assert identity.email == "dancer@example.com"
    assert identity.email_verified is True
    assert identity.name == "Dancer Person"


def test_exchange_code_rejects_a_token_issued_for_a_different_client() -> None:
    fake_requests = FakeRequests(
        token_response=FakeResponse(200, {"id_token": "fake-id-token"}),
        tokeninfo_response=FakeResponse(
            200, {"sub": "1", "email": "x@example.com", "aud": "someone-elses-client-id", "iss": "accounts.google.com"}
        ),
    )
    client = _client_with_fake_requests(fake_requests)

    with pytest.raises(RuntimeError, match="different app"):
        client.exchange_code("auth-code")


def test_exchange_code_rejects_an_unexpected_issuer() -> None:
    fake_requests = FakeRequests(
        token_response=FakeResponse(200, {"id_token": "fake-id-token"}),
        tokeninfo_response=FakeResponse(
            200, {"sub": "1", "email": "x@example.com", "aud": "client-id", "iss": "https://evil.example.com"}
        ),
    )
    client = _client_with_fake_requests(fake_requests)

    with pytest.raises(RuntimeError, match="issuer"):
        client.exchange_code("auth-code")


def test_exchange_code_requires_an_id_token_in_the_response() -> None:
    fake_requests = FakeRequests(token_response=FakeResponse(200, {}), tokeninfo_response=FakeResponse(200, {}))
    client = _client_with_fake_requests(fake_requests)

    with pytest.raises(RuntimeError, match="id_token"):
        client.exchange_code("auth-code")


def test_build_google_identity_client_falls_back_to_noop_when_unconfigured() -> None:
    provider = build_google_identity_client(client_id=None, client_secret=None, redirect_uri=None)
    assert isinstance(provider, NoopGoogleIdentityProvider)
    with pytest.raises(RuntimeError):
        provider.build_authorization_url("state")


def test_build_google_identity_client_returns_real_client_when_fully_configured() -> None:
    provider = build_google_identity_client(client_id="id", client_secret="secret", redirect_uri="http://x/callback")
    assert isinstance(provider, GoogleIdentityClient)
