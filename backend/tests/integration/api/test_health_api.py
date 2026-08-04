from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.main import create_app


def test_health_reports_demo_mode_false_by_default(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "demo_mode": False}


def test_health_reports_demo_mode_true_when_admin_reset_token_is_set(session_factory) -> None:
    settings = Settings(
        database_url="sqlite:///ignored.db",
        auto_sync_enabled=False,
        GEMINI_API_KEY="",
        ADMIN_RESET_TOKEN="demo-token",
    )
    app = create_app(settings=settings, session_factory=session_factory)
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
        assert response.json() == {"status": "ok", "demo_mode": True}
