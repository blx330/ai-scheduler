from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.main import create_app


def _app_with_admin_token(session_factory, token: str):
    settings = Settings(
        database_url="sqlite:///ignored.db",
        auto_sync_enabled=False,
        GEMINI_API_KEY="",
        ADMIN_RESET_TOKEN=token,
    )
    return create_app(settings=settings, session_factory=session_factory)


def test_reset_demo_is_not_found_when_no_token_is_configured(client) -> None:
    # The default `client` fixture builds Settings() without ADMIN_RESET_TOKEN set.
    response = client.post("/api/v1/admin/reset-demo", headers={"X-Admin-Token": "anything"})
    assert response.status_code == 404


def test_reset_demo_rejects_missing_or_wrong_token(session_factory) -> None:
    app = _app_with_admin_token(session_factory, "correct-token")
    with TestClient(app) as test_client:
        assert test_client.post("/api/v1/admin/reset-demo").status_code == 401
        assert (
            test_client.post("/api/v1/admin/reset-demo", headers={"X-Admin-Token": "wrong"}).status_code == 401
        )


def test_reset_demo_reseeds_data_with_the_correct_token(session_factory) -> None:
    app = _app_with_admin_token(session_factory, "correct-token")
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/admin/reset-demo", headers={"X-Admin-Token": "correct-token"})
        assert response.status_code == 200
        assert response.json() == {"status": "reset"}

        users = test_client.get("/api/v1/users").json()
        events = test_client.get("/api/v1/events").json()
        assert len(users) == 4
        assert {event["name"] for event in events} == {"Contemporary Showcase", "Nutcracker", "Solo Piece"}
