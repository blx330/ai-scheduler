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
    settings = Settings(database_url="sqlite:///ignored.db")
    return create_app(settings=settings, session_factory=session_factory)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
