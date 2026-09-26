"""reset_demo() is what the public demo shows to every visitor, so it gets checked
like a feature: the roster, the class-shaped busy time, the dance states and the
planning run it leaves behind."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.application.services.auth_service import DEMO_GUEST_USER_ID
from app.application.services.demo_scenario import DANCES, DEMO_TIMEZONE, MEMBERS, member_by_key
from app.application.services.demo_seed_service import reset_demo
from app.domain.common.enums import UserRole
from app.infrastructure.db.models import (
    CalendarBusyInterval,
    DanceEvent,
    ManualAvailabilityInterval,
    PlanningRun,
    PlanningRunResult,
    PracticeSession,
    User,
)
from app.infrastructure.demo_guard import DEMO_ROW_LIMIT

NEW_YORK = ZoneInfo(DEMO_TIMEZONE)


def _users_by_email(db) -> dict[str, User]:
    return {user.email: user for user in db.scalars(select(User))}


def _local(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC).astimezone(NEW_YORK) if value.tzinfo is None else value.astimezone(NEW_YORK)


def test_reset_demo_seeds_the_roster_and_a_stable_demo_guest(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        users = _users_by_email(db)

        assert len(users) == len(MEMBERS) + 1
        guest = db.get(User, DEMO_GUEST_USER_ID)
        assert guest is not None
        assert guest.role == UserRole.ORGANIZER.value
        assert guest.timezone == DEMO_TIMEZONE

        for member in MEMBERS:
            user = users[member.email]
            assert user.display_name == member.display_name
            assert user.timezone == DEMO_TIMEZONE
            assert user.role == member.role.value
            if member.preferred_practice_time_raw:
                # Parsed by the deterministic stub at seed time, never by Gemini.
                assert user.preferred_practice_time_parsed is not None


def test_reset_demo_busy_time_follows_the_weekly_class_schedule(session_factory) -> None:
    cindy = member_by_key("cindy")
    cis_5210 = next(block for block in cindy.weekly_busy if block.label.startswith("CIS 5210 lecture"))
    with session_factory() as db:
        reset_demo(db)
        user = _users_by_email(db)[cindy.email]
        busy = [
            _local(item.start_at)
            for item in db.scalars(select(CalendarBusyInterval).where(CalendarBusyInterval.user_id == user.id))
        ]
        lecture_starts = [
            item
            for item in busy
            if item.strftime("%a").upper() == cis_5210.weekday.value and item.time() == cis_5210.start
        ]
        assert len(lecture_starts) >= 4
        assert all(item.tzinfo is not None for item in lecture_starts)


def test_reset_demo_availability_is_evening_and_weekend_shaped_in_local_time(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        intervals = list(db.scalars(select(ManualAvailabilityInterval)))
        assert intervals
        for interval in intervals:
            start, end = _local(interval.start_at), _local(interval.end_at)
            assert start.time() >= time(8, 0), start
            same_day = end.date() == start.date()
            ends_at_midnight = end.time() == time(0, 0) and (end.date() - start.date()).days == 1
            assert same_day or ends_at_midnight, (start, end)


def test_reset_demo_leaves_every_dance_status_represented(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        events = {event.name: event for event in db.scalars(select(DanceEvent))}
        assert set(events) == {dance.name for dance in DANCES}

        statuses = {event.status for event in events.values()}
        assert {"scheduled", "partially_scheduled", "unscheduled"} <= statuses

        showcase = events["Fall Showcase: Opening Number"]
        assert showcase.blocked_weekdays_json == ["FRI"]
        assert showcase.latest_end_time_local == time(22, 30)
        run_through = events["Full Run-Through (Tech Week)"]
        assert run_through.allowed_weekdays_json == ["SAT", "SUN"]


def test_reset_demo_confirmed_sessions_are_fully_feasible_and_scored(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        sessions = list(db.scalars(select(PracticeSession)))
        assert sessions
        planned = [session for session in sessions if session.source_run_id is not None]
        assert planned
        for session in sessions:
            assert session.status == "confirmed"
            assert session.is_fallback is False
        for session in planned:
            assert float(session.total_score) > 0


def test_reset_demo_new_member_without_availability_only_gets_fallback_slots(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        users = _users_by_email(db)
        nina = users[member_by_key("nina").email]
        feature = db.scalars(select(DanceEvent).where(DanceEvent.name == "New Member Feature")).one()
        results = list(db.scalars(select(PlanningRunResult).where(PlanningRunResult.dance_event_id == feature.id)))
        assert results
        assert all(result.is_fallback for result in results)
        assert all(result.missing_required_user_ids_json == [str(nina.id)] for result in results)


def test_reset_demo_is_idempotent_and_keeps_the_guest_id(session_factory) -> None:
    def counts(db):
        return tuple(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (User, DanceEvent, ManualAvailabilityInterval, CalendarBusyInterval, PlanningRun, PracticeSession)
        )

    with session_factory() as db:
        reset_demo(db)
        first = counts(db)
        reset_demo(db)
        second = counts(db)
        assert first == second
        assert db.get(User, DEMO_GUEST_USER_ID) is not None


def test_reset_demo_leaves_room_under_the_demo_row_cap(session_factory) -> None:
    with session_factory() as db:
        reset_demo(db)
        seeded_rows = sum(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (User, DanceEvent, ManualAvailabilityInterval)
        )
    assert seeded_rows <= DEMO_ROW_LIMIT // 2


def test_reset_demo_includes_a_rehearsal_already_held_this_week(session_factory) -> None:
    """The current week should never look empty, whatever weekday the reset runs
    on: the showcase's first rehearsal is seeded as held on Monday evening."""
    with session_factory() as db:
        reset_demo(db)
        showcase = db.scalars(select(DanceEvent).where(DanceEvent.name == "Fall Showcase: Opening Number")).one()
        sessions = {
            session.session_index: session
            for session in db.scalars(select(PracticeSession).where(PracticeSession.dance_event_id == showcase.id))
        }
        held = sessions[1]
        assert held.status == "confirmed"
        assert held.source_run_id is None
        held_start = _local(held.start_at)
        today = datetime.now(UTC).astimezone(NEW_YORK).date()
        assert held_start.weekday() == 0
        assert (today - held_start.date()).days == today.weekday()
        assert held_start.time() == time(19, 0)
        # The planner then filled the *next* session from the run, keeping the spacing rule.
        assert 2 in sessions
        assert sessions[2].source_run_id is not None
        assert (_local(sessions[2].start_at).date() - held_start.date()).days >= showcase.min_days_apart
        assert showcase.status == "partially_scheduled"
