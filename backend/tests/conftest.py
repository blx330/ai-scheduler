from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import *  # noqa: F401,F403
from app.infrastructure.db.session import build_session_factory
from app.main import create_app


@pytest.fixture()
def session_factory(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    factory = build_session_factory(database_url)
    engine = factory.kw["bind"]
    Base.metadata.create_all(bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def app(session_factory):
    # Auto-sync is off and Gemini/Google settings are pinned to fixed values so behavior
    # doesn't depend on a developer's local .env (Settings loads env_file on every
    # construction, and this app documents live Google OAuth/Gemini setup, so real
    # credentials being present locally is plausible) — tests always exercise the
    # deterministic stub preference parser and a fixed OAuth signing secret, never a
    # real key. Each of these fields has a validation_alias (e.g. "GEMINI_API_KEY"), so
    # overriding it via the plain field-name kwarg is silently dropped in favor of the
    # real .env value (pydantic-settings merges sources by alias, and env/dotenv win
    # when both are present) — the alias name must be used here to actually override it.
    settings = Settings(
        database_url="sqlite:///ignored.db",
        auto_sync_enabled=False,
        GEMINI_API_KEY="",
        OAUTH_STATE_SECRET="test-oauth-state-secret",
        GOOGLE_CLIENT_ID="test-client-id",
        GOOGLE_CLIENT_SECRET="test-client-secret",
        GOOGLE_REDIRECT_URI="http://localhost:8000/api/v1/google/oauth/callback",
    )
    return create_app(settings=settings, session_factory=session_factory)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
