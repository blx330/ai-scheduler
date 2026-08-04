from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.main import create_app


def _demo_app(session_factory):
    settings = Settings(
        database_url="sqlite:///ignored.db",
        auto_sync_enabled=False,
        GEMINI_API_KEY="",
        ADMIN_RESET_TOKEN="demo-token",
    )
    return create_app(settings=settings, session_factory=session_factory)


def _create_user_payload(n: int) -> dict:
    return {"display_name": f"Guard Test {n}", "timezone": "UTC", "email": f"guard-{n}@example.com"}


def test_guard_is_a_no_op_when_admin_reset_token_is_unset(client) -> None:
    # Default `client` fixture has no ADMIN_RESET_TOKEN configured, so a burst of
    # mutating requests should never be rate-limited or capacity-limited.
    for n in range(10):
        response = client.post("/api/v1/users", json=_create_user_payload(n))
        assert response.status_code == 201


def test_row_cap_blocks_creation_once_the_demo_capacity_limit_is_reached(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("app.infrastructure.demo_guard.DEMO_ROW_LIMIT", 2)
    app = _demo_app(session_factory)
    with TestClient(app) as test_client:
        first = test_client.post("/api/v1/users", json=_create_user_payload(1))
        second = test_client.post("/api/v1/users", json=_create_user_payload(2))
        assert first.status_code == 201
        assert second.status_code == 201

        blocked = test_client.post("/api/v1/users", json=_create_user_payload(3))
        assert blocked.status_code == 429
        assert "capacity" in blocked.json()["detail"].lower()


def test_rate_limit_blocks_bursts_past_the_configured_threshold(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("app.infrastructure.demo_guard.RATE_LIMIT_MAX_REQUESTS", 2)
    app = _demo_app(session_factory)
    with TestClient(app) as test_client:
        statuses = [
            test_client.post("/api/v1/users", json=_create_user_payload(n)).status_code for n in range(3)
        ]
        assert statuses[:2] == [201, 201]
        assert statuses[2] == 429


def test_admin_reset_endpoint_itself_is_exempt_from_rate_limiting(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("app.infrastructure.demo_guard.RATE_LIMIT_MAX_REQUESTS", 1)
    app = _demo_app(session_factory)
    with TestClient(app) as test_client:
        headers = {"X-Admin-Token": "demo-token"}
        first = test_client.post("/api/v1/admin/reset-demo", headers=headers)
        second = test_client.post("/api/v1/admin/reset-demo", headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
