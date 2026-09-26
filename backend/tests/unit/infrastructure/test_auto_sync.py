import uuid

from sqlalchemy import select

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


def test_sync_all_connections_continues_after_an_unexpected_exception(monkeypatch, session_factory) -> None:
    session = session_factory()
    failing_id = _seed_user(session, "connected")
    healthy_id = _seed_user(session, "connected")
    session.close()

    synced_user_ids = []

    def fake_sync_busy_intervals(self, user_id, horizon_start, horizon_end):
        if user_id == failing_id:
            raise KeyError("start")  # e.g. Google returned an unexpected payload shape
        synced_user_ids.append(user_id)

    monkeypatch.setattr(GoogleCalendarService, "sync_busy_intervals", fake_sync_busy_intervals)

    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)

    assert synced_user_ids == [healthy_id]


def test_revoked_refresh_token_marks_connection_for_reauthorization_and_stops_retrying(
    monkeypatch, session_factory
) -> None:
    session = session_factory()
    revoked_id = _seed_user(session, "configured")
    healthy_id = _seed_user(session, "connected")
    session.close()

    attempts = []

    def fake_sync_busy_intervals(self, user_id, horizon_start, horizon_end):
        attempts.append(user_id)
        if user_id == revoked_id:
            raise RuntimeError("Google OAuth token refresh failed: invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(GoogleCalendarService, "sync_busy_intervals", fake_sync_busy_intervals)

    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)
    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)

    assert attempts == [revoked_id, healthy_id, healthy_id]
    with session_factory() as db:
        connection = db.scalars(select(CalendarConnection).where(CalendarConnection.user_id == revoked_id)).one()
        assert connection.status == "reauthorization_required"
        healthy = db.scalars(select(CalendarConnection).where(CalendarConnection.user_id == healthy_id)).one()
        assert healthy.status == "connected"


def test_other_runtime_errors_do_not_change_connection_status(monkeypatch, session_factory) -> None:
    session = session_factory()
    user_id = _seed_user(session, "connected")
    session.close()

    def fake_sync_busy_intervals(self, user_id, horizon_start, horizon_end):
        raise RuntimeError("Google Calendar free/busy lookup failed: HTTP 503")

    monkeypatch.setattr(GoogleCalendarService, "sync_busy_intervals", fake_sync_busy_intervals)
    sync_all_connections(session_factory, settings=object(), client=object(), horizon_days=30)

    with session_factory() as db:
        connection = db.scalars(select(CalendarConnection).where(CalendarConnection.user_id == user_id)).one()
        assert connection.status == "connected"
