from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from app.domain.common.enums import UserRole
from app.infrastructure.integrations.google_identity.client import GoogleIdentity
from tests.auth_helpers import log_in

ADMIN_EMAIL = "admin@example.com"
ROSTER_EMAIL = "roster-member@example.com"
UNKNOWN_EMAIL = "stranger@example.com"


class FakeGoogleIdentityClient:
    def __init__(self, identity: GoogleIdentity) -> None:
        self.identity = identity
        self.last_state = ""

    def build_authorization_url(self, state: str) -> str:
        self.last_state = state
        return f"https://accounts.google.com/fake-auth?state={state}"

    def exchange_code(self, code: str) -> GoogleIdentity:
        assert code == "fake-code"
        return self.identity


def _login_via_google(anon_client, app, identity: GoogleIdentity):
    app.state.google_identity_client = FakeGoogleIdentityClient(identity)
    start = anon_client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert start.status_code in (302, 307)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    return anon_client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": state},
        follow_redirects=False,
    )


def _event_payload(organizer_user_id) -> dict:
    return {
        "name": "Contemporary Showcase",
        "description": None,
        "organizer_user_id": str(organizer_user_id),
        "duration_minutes": 60,
        "earliest_start_date": None,
        "min_days_apart": 0,
        "latest_schedule_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "required_session_count": 1,
        "participants": [{"user_id": str(organizer_user_id), "role": "required"}],
    }


def test_protected_endpoint_rejects_anonymous_requests(anon_client) -> None:
    response = anon_client.get("/api/v1/users")
    assert response.status_code == 401


def test_invalid_session_cookie_is_rejected(anon_client) -> None:
    anon_client.cookies.set("session", "not-a-valid-token")
    response = anon_client.get("/api/v1/users")
    assert response.status_code == 401


def test_organizer_only_endpoint_rejects_member(anon_client) -> None:
    log_in(anon_client, role=UserRole.MEMBER.value)
    response = anon_client.post("/api/v1/events", json=_event_payload(uuid4()))
    assert response.status_code == 403


def test_organizer_only_endpoint_allows_organizer(client) -> None:
    organizer = client.post(
        "/api/v1/users", json={"display_name": "Organizer", "timezone": "UTC", "email": "org@example.com"}
    ).json()
    response = client.post("/api/v1/events", json=_event_payload(organizer["id"]))
    assert response.status_code == 201


def test_member_can_edit_their_own_availability_but_not_someone_elses(client) -> None:
    member_id = uuid4()
    other_member_id = uuid4()

    log_in(client, role=UserRole.MEMBER.value, user_id=member_id)
    own_availability = client.post(
        f"/api/v1/users/{member_id}/availability",
        json={
            "start_at": "2026-04-01T10:00:00Z",
            "end_at": "2026-04-01T12:00:00Z",
        },
    )
    # 404 (no such user) proves the auth check passed and the request reached the
    # service layer -- 403 would mean the self-check itself rejected it.
    assert own_availability.status_code == 404

    other_availability = client.post(
        f"/api/v1/users/{other_member_id}/availability",
        json={
            "start_at": "2026-04-01T10:00:00Z",
            "end_at": "2026-04-01T12:00:00Z",
        },
    )
    assert other_availability.status_code == 403


def test_auth_me_returns_current_user_profile(client) -> None:
    created = client.post(
        "/api/v1/users", json={"display_name": "Dana", "timezone": "UTC", "email": "dana@example.com"}
    ).json()

    log_in(client, role=UserRole.MEMBER.value, user_id=created["id"])
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["display_name"] == "Dana"
    assert body["role"] == UserRole.MEMBER.value


def test_auth_me_without_cookie_is_401(anon_client) -> None:
    assert anon_client.get("/api/v1/auth/me").status_code == 401


def test_auth_me_for_deleted_account_clears_cookie_and_401s(anon_client) -> None:
    log_in(anon_client, role=UserRole.ORGANIZER.value, user_id=uuid4())
    response = anon_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert _cookie_is_cleared(response.headers["set-cookie"])


def test_logout_clears_cookie(client) -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert _cookie_is_cleared(response.headers["set-cookie"])


def _cookie_is_cleared(set_cookie_header: str) -> bool:
    # The TestClient's own cookie jar doesn't purge on Max-Age=0 (an httpx quirk), so
    # assert on the Set-Cookie header the server actually sent instead.
    return 'session=""' in set_cookie_header and "Max-Age=0" in set_cookie_header


def test_google_login_redirects_with_a_signed_state(anon_client, app) -> None:
    app.state.google_identity_client = FakeGoogleIdentityClient(
        GoogleIdentity(subject="sub-1", email=ADMIN_EMAIL, email_verified=True, name="Admin")
    )
    response = anon_client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert "state=" in response.headers["location"]


def test_google_callback_provisions_organizer_for_admin_email(anon_client, app) -> None:
    app.state.settings.admin_emails = [ADMIN_EMAIL]
    identity = GoogleIdentity(subject="admin-sub", email=ADMIN_EMAIL, email_verified=True, name="Admin Person")

    callback = _login_via_google(anon_client, app, identity)

    assert callback.status_code in (302, 307)
    assert "session" in anon_client.cookies

    me = anon_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == UserRole.ORGANIZER.value
    assert me.json()["email"] == ADMIN_EMAIL


def test_google_callback_rejects_unknown_email(anon_client, app) -> None:
    app.state.settings.admin_emails = []
    identity = GoogleIdentity(subject="stranger-sub", email=UNKNOWN_EMAIL, email_verified=True, name="Stranger")

    callback = _login_via_google(anon_client, app, identity)

    assert callback.status_code in (302, 307)
    assert "login_error" in callback.headers["location"]
    assert "session" not in anon_client.cookies


def test_google_callback_matches_existing_roster_member_by_email_and_links_subject(client, anon_client, app) -> None:
    roster_member = client.post(
        "/api/v1/users", json={"display_name": "Roster Member", "timezone": "UTC", "email": ROSTER_EMAIL}
    ).json()
    assert roster_member["role"] == UserRole.MEMBER.value

    identity = GoogleIdentity(subject="roster-sub", email=ROSTER_EMAIL, email_verified=True, name="Roster Member")
    callback = _login_via_google(anon_client, app, identity)
    assert callback.status_code in (302, 307)

    me = anon_client.get("/api/v1/auth/me").json()
    assert me["id"] == roster_member["id"]
    assert me["role"] == UserRole.MEMBER.value

    # Second login with the same Google subject but a changed email still resolves to
    # the same roster row -- matched by subject, not email, once linked.
    anon_client.cookies.delete("session")
    changed_email_identity = GoogleIdentity(
        subject="roster-sub", email="new-address@example.com", email_verified=True, name="Roster Member"
    )
    second_callback = _login_via_google(anon_client, app, changed_email_identity)
    assert second_callback.status_code in (302, 307)
    assert anon_client.get("/api/v1/auth/me").json()["id"] == roster_member["id"]


def test_demo_login_is_not_found_without_admin_reset_token(anon_client) -> None:
    response = anon_client.get("/api/v1/auth/demo-login", follow_redirects=False)
    assert response.status_code == 404


def test_demo_login_grants_an_organizer_session_when_demo_mode_is_on(anon_client, app) -> None:
    app.state.settings.admin_reset_token = "demo-token"
    response = anon_client.get("/api/v1/auth/demo-login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "session" in anon_client.cookies

    me = anon_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == UserRole.ORGANIZER.value


def test_organizer_can_promote_a_member_to_organizer(client) -> None:
    member = client.post(
        "/api/v1/users", json={"display_name": "Future Organizer", "timezone": "UTC", "email": "future@example.com"}
    ).json()
    assert member["role"] == UserRole.MEMBER.value

    response = client.patch(f"/api/v1/users/{member['id']}/role", json={"role": UserRole.ORGANIZER.value})
    assert response.status_code == 200
    assert response.json()["role"] == UserRole.ORGANIZER.value


def test_member_cannot_promote_anyone(anon_client) -> None:
    log_in(anon_client, role=UserRole.MEMBER.value)
    response = anon_client.patch(f"/api/v1/users/{uuid4()}/role", json={"role": UserRole.ORGANIZER.value})
    assert response.status_code == 403
