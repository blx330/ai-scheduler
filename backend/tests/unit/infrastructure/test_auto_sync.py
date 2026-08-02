import uuid

from app.application.services.google_calendar_service import GoogleCalendarService
from app.infrastructure.db.models import CalendarConnection, User
from app.infrastructure.scheduling.auto_sync import sync_all_connections


def _seed_user(session, status: str) -> uuid.UUID:
    user = User(id=uuid.uuid4(), display_name="Member", email=f"{uuid.uuid4()}@example.com", timezone="UTC")
    session.add(user)
    session.add(CalendarConnection(user_id=user.id, status=status))
    session.commit()
    return user.id


def test_sync_all_connections_syncs_only_connected_or_configured_users(monkeypatch, session_factory) -> None:
    session = session_factory()
    connected_id = _seed_user(session, "connected")
    configured_id = _seed_user(session, "configured")
    disconnected_id = _seed_user(session, "disconnected")
    session.close()

    synced_user_ids = []

    def fake_sync_busy_intervals(self, user_id, horizon_start, horizon_end):
        synced_user_ids.append(user_id)

    monkeypatch.setattr(GoogleCalendarService, "sync_busy_intervals", fake_sync_busy_intervals)

    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)

    assert set(synced_user_ids) == {connected_id, configured_id}
    assert disconnected_id not in synced_user_ids


def test_sync_all_connections_continues_after_one_connection_fails(monkeypatch, session_factory) -> None:
    session = session_factory()
    failing_id = _seed_user(session, "connected")
    healthy_id = _seed_user(session, "connected")
    session.close()

    synced_user_ids = []

    def fake_sync_busy_intervals(self, user_id, horizon_start, horizon_end):
        if user_id == failing_id:
            raise RuntimeError("token revoked")
        synced_user_ids.append(user_id)

    monkeypatch.setattr(GoogleCalendarService, "sync_busy_intervals", fake_sync_busy_intervals)

    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)

    assert synced_user_ids == [healthy_id]
