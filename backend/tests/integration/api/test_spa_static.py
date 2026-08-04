from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.main import create_app


def _bundled_app(session_factory, static_dir):
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html><body>SPA shell</body></html>")
    (static_dir / "favicon.svg").write_text("<svg></svg>")
    assets_dir = static_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "index-abc123.js").write_text("console.log('app')")

    settings = Settings(
        database_url="sqlite:///ignored.db", auto_sync_enabled=False, GEMINI_API_KEY=""
    )
    return create_app(settings=settings, session_factory=session_factory, static_dir=static_dir)


def test_direct_navigation_to_a_client_side_route_serves_the_spa_shell(session_factory, tmp_path) -> None:
    # Regression test: StaticFiles(html=True) alone only serves index.html for "/" --
    # a direct visit or refresh on a React Router route like /calendar 404'd with a
    # bare JSON error instead of loading the app.
    app = _bundled_app(session_factory, tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/calendar")
        assert response.status_code == 200
        assert "SPA shell" in response.text

        nested = client.get("/members/some-id")
        assert nested.status_code == 200
        assert "SPA shell" in nested.text


def test_real_static_assets_are_served_directly_not_the_spa_shell(session_factory, tmp_path) -> None:
    app = _bundled_app(session_factory, tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/assets/index-abc123.js")
        assert response.status_code == 200
        assert "console.log" in response.text

        favicon = client.get("/favicon.svg")
        assert favicon.status_code == 200
        assert "<svg" in favicon.text


def test_unmatched_api_paths_still_404_instead_of_falling_back_to_the_spa_shell(
    session_factory, tmp_path
) -> None:
    app = _bundled_app(session_factory, tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/api/v1/totally-bogus-path")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
