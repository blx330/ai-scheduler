"""Seed (or reset-and-reseed) the public shared demo.

reset_demo() truncates every domain table (FK-safe order) and reseeds from scratch,
so this module doubles as both the initial seed and the periodic demo-reset job
(see "POST /api/v1/admin/reset-demo" and the scheduled GitHub Actions workflow
that calls it). The roster, class schedules and dances live in demo_scenario.py;
this module only turns them into rows, going through the same service-layer calls
the real API uses (create_user / create_interval / create_event / update_event /
create_planning_run / confirm_results) so seeded data is exactly as internally
consistent as data created through the UI.

Run directly with: python -m scripts.seed_demo (see backend/scripts/seed_demo.py).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas.availability import AvailabilityCreate
from app.api.schemas.events import DanceEventCreate, DanceEventParticipantCreate, DanceEventUpdate
from app.api.schemas.planning import PlanningRunCreate
from app.api.schemas.users import UserCreate
from app.application.services.auth_service import DEMO_GUEST_EMAIL, DEMO_GUEST_USER_ID
from app.application.services.availability_service import AvailabilityService
from app.application.services.demo_scenario import (
    AVAILABILITY_WEEKS,
    BUSY_WEEKS,
    DANCES,
    DEMO_TIMEZONE,
    MEMBERS,
    PLANNING_HORIZON_DAYS,
    ROOM_NAME,
    one_off_block_intervals,
    weekly_block_intervals,
)
from app.application.services.event_service import EventService
from app.application.services.planning_service import PlanningService
from app.application.services.user_service import UserService
from app.domain.availability.models import Interval
from app.domain.common.enums import UserRole
from app.domain.scheduling.constraints import WEEKDAY_BY_INDEX
from app.infrastructure.db.models import (
    CalendarBusyInterval,
    CalendarConnection,
    DanceEvent,
    DanceEventParticipant,
    ManualAvailabilityInterval,
    PlanningRun,
    PlanningRunResult,
    PracticeSession,
    Room,
    User,
)
from app.infrastructure.integrations.llm.profile_preference_parser import StubUserProfilePreferenceParser

# Deletion order matters even though the FKs cascade: sqlite (used by CI) doesn't
# enforce ON DELETE CASCADE by default, so children must go before their parents.
_TABLES_CHILD_TO_PARENT = [
    PracticeSession,
    PlanningRunResult,
    PlanningRun,
    DanceEventParticipant,
    DanceEvent,
    CalendarBusyInterval,
    CalendarConnection,
    ManualAvailabilityInterval,
    Room,
    User,
]


def reset_demo(db: Session) -> None:
    """Wipe all domain data and reseed. Used for both the initial seed and demo resets."""
    _truncate_all(db)
    zone = ZoneInfo(DEMO_TIMEZONE)
    now = datetime.now(UTC)
    today = now.astimezone(zone).date()
    week_start = today - timedelta(days=today.weekday())

    _seed_demo_guest(db)
    users = _seed_members(db)
    _seed_room(db)
    _seed_availability(db, users, week_start, zone)
    _seed_busy_intervals(db, users, week_start, today, zone)
    events = _seed_dances(db, users, today, zone)
    _seed_held_sessions(db, events, week_start, zone)
    _seed_planning_run_and_confirmations(db, events, now)


def _truncate_all(db: Session) -> None:
    for model in _TABLES_CHILD_TO_PARENT:
        db.execute(delete(model))
    db.commit()


def _seed_demo_guest(db: Session) -> None:
    # Recreated with the same id every reset so a visitor signed in as the guest
    # keeps a valid session across the 4-hourly reset instead of being logged out.
    db.add(
        User(
            id=DEMO_GUEST_USER_ID,
            display_name="Demo Guest",
            email=DEMO_GUEST_EMAIL,
            timezone=DEMO_TIMEZONE,
            role=UserRole.ORGANIZER.value,
        )
    )
    db.commit()


def _seed_members(db: Session) -> dict[str, User]:
    service = UserService(db)
    # The stub parser is deterministic and offline, so resets never call Gemini and
    # every member's free-text preference is understood the same way each time.
    parser = StubUserProfilePreferenceParser()
    users: dict[str, User] = {}
    for spec in MEMBERS:
        user = service.create_user(
            UserCreate(
                display_name=spec.display_name,
                timezone=DEMO_TIMEZONE,
                email=spec.email,
                preferred_practice_time=spec.preferred_practice_time,
                preferred_practice_time_raw=spec.preferred_practice_time_raw,
            ),
            preference_parser=parser,
        )
        if spec.role is not UserRole.MEMBER:
            service.update_role(user.id, spec.role.value)
        users[spec.key] = user
    return users


def _seed_room(db: Session) -> None:
    db.add(Room(name=ROOM_NAME, is_active=True))
    db.commit()


def _seed_availability(db: Session, users: dict[str, User], week_start: date, zone: ZoneInfo) -> None:
    service = AvailabilityService(db)
    for spec in MEMBERS:
        for interval in _weekly_intervals(spec.weekly_free, week_start, AVAILABILITY_WEEKS, zone):
            service.create_interval(users[spec.key].id, AvailabilityCreate(start_at=interval.start_at, end_at=interval.end_at))


def _seed_busy_intervals(db: Session, users: dict[str, User], week_start: date, today: date, zone: ZoneInfo) -> None:
    # Synthetic busy time standing in for a synced Google Calendar, without any real
    # OAuth connection: calendar_connection_id is nullable, so these render on the
    # calendar's per-member overlay exactly like real synced busy time would.
    for spec in MEMBERS:
        intervals = [
            *_weekly_intervals(spec.weekly_busy, week_start, BUSY_WEEKS, zone),
            *one_off_block_intervals(spec.one_off_busy, today, zone),
        ]
        for interval in intervals:
            db.add(
                CalendarBusyInterval(
                    user_id=users[spec.key].id,
                    calendar_connection_id=None,
                    start_at=interval.start_at,
                    end_at=interval.end_at,
                )
            )
    db.commit()


def _seed_dances(db: Session, users: dict[str, User], today: date, zone: ZoneInfo) -> dict[str, DanceEvent]:
    service = EventService(db)
    events: dict[str, DanceEvent] = {}
    for spec in DANCES:
        event = service.create_event(
            DanceEventCreate(
                name=spec.name,
                description=spec.description,
                organizer_user_id=users[spec.organizer].id,
                duration_minutes=spec.duration_minutes,
                min_days_apart=spec.min_days_apart,
                latest_schedule_at=_end_of_local_day(today + timedelta(days=spec.deadline_days), zone),
                required_session_count=spec.session_count,
                participants=[
                    *(DanceEventParticipantCreate(user_id=users[key].id, role="required") for key in spec.required),
                    *(DanceEventParticipantCreate(user_id=users[key].id, role="optional") for key in spec.optional),
                ],
            )
        )
        # Day/time rules are only settable through the update path, same as the UI.
        updated = service.update_event(
            event.id,
            DanceEventUpdate(
                allowed_weekdays=list(spec.allowed_weekdays),
                blocked_weekdays=list(spec.blocked_weekdays),
                earliest_start_time=spec.earliest_start_time,
                latest_end_time=spec.latest_end_time,
            ),
        )
        assert updated is not None
        events[spec.key] = updated
    return events


def _seed_held_sessions(db: Session, events: dict[str, DanceEvent], week_start: date, zone: ZoneInfo) -> None:
    # Practices that already happened cannot come from a planning run (the planner
    # only looks forward), so they are the one thing written directly. They carry an
    # honest explanation instead of a score the engine never computed.
    room = db.scalars(select(Room).where(Room.name == ROOM_NAME)).one()
    for spec in DANCES:
        for session_index, (weekday, start) in enumerate(spec.held_this_week, start=1):
            day = week_start + timedelta(days=WEEKDAY_BY_INDEX.index(weekday))
            start_at = datetime.combine(day, start, tzinfo=zone).astimezone(UTC)
            db.add(
                PracticeSession(
                    dance_event_id=events[spec.key].id,
                    session_index=session_index,
                    start_at=start_at,
                    end_at=start_at + timedelta(minutes=spec.duration_minutes),
                    status="confirmed",
                    room_id=room.id,
                    source_run_id=None,
                    total_score=None,
                    explanation_json={
                        "summary": "Held earlier this week; confirmed before the current planning horizon.",
                        "reasons": [],
                        "missing_required_user_ids": [],
                    },
                )
            )
        if spec.held_this_week:
            events[spec.key].status = "partially_scheduled" if len(spec.held_this_week) < spec.session_count else "scheduled"
    db.commit()
    for event in events.values():
        db.refresh(event)


def _seed_planning_run_and_confirmations(db: Session, events: dict[str, DanceEvent], now: datetime) -> None:
    # Start on the next full hour so candidate slots land on :00 like the UI's.
    horizon_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    service = PlanningService(db)
    run = service.create_planning_run(
        PlanningRunCreate(
            event_ids=[event.id for event in events.values()],
            horizon_start=horizon_start,
            horizon_end=horizon_start + timedelta(days=PLANNING_HORIZON_DAYS),
        )
    )

    # Confirm the top-ranked fully-feasible pick for the sessions each dance asks
    # for, mirroring what an organizer would do, so the calendar isn't empty on
    # first load and every dance status (scheduled / partial / unscheduled) shows.
    picks = []
    for spec in DANCES:
        for session_index in spec.confirm_session_indices:
            pick = _top_feasible_result(run.results, events[spec.key].id, session_index)
            if pick is not None:
                picks.append(pick.id)
    if picks:
        service.confirm_results(run.id, picks)


def _top_feasible_result(results: list[PlanningRunResult], dance_event_id, session_index: int) -> PlanningRunResult | None:
    candidates = [
        result
        for result in results
        if result.dance_event_id == dance_event_id and result.session_index == session_index and not result.is_fallback
    ]
    return min(candidates, key=lambda result: result.rank, default=None)


def _weekly_intervals(blocks, week_start: date, weeks: int, zone: ZoneInfo) -> list[Interval]:
    return [interval for block in blocks for interval in weekly_block_intervals(block, week_start, weeks, zone)]


def _end_of_local_day(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=zone).astimezone(UTC)

