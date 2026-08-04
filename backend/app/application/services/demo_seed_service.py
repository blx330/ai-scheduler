"""Seed (or reset-and-reseed) realistic demo data for the public shared demo.

reset_demo() truncates every domain table (FK-safe order) and reseeds from scratch,
so this module doubles as both the initial seed and the periodic demo-reset job
(see the "POST /api/v1/admin/reset-demo" endpoint and the scheduled GitHub Actions
workflow that calls it). Everything here goes through the same service-layer calls
the real API uses -- create_user/create_interval/create_event/create_planning_run --
so seeded rows are exactly as internally consistent as data created through the UI.

Run directly with: python -m scripts.seed_demo (see backend/scripts/seed_demo.py).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.schemas.availability import AvailabilityCreate
from app.api.schemas.events import DanceEventCreate, DanceEventParticipantCreate
from app.api.schemas.planning import PlanningRunCreate
from app.api.schemas.users import UserCreate
from app.application.services.availability_service import AvailabilityService
from app.application.services.event_service import EventService
from app.application.services.planning_service import PlanningService
from app.application.services.user_service import UserService
from app.domain.preferences.models import PreferredPracticeTime
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

DEMO_MEMBERS = [
    {
        "display_name": "Alice Kim",
        "timezone": "America/New_York",
        "email": "alice@demo.aischeduler.dev",
        "preferred_practice_time": PreferredPracticeTime.MORNING,
    },
    {
        "display_name": "Bilal Osei",
        "timezone": "America/Chicago",
        "email": "bilal@demo.aischeduler.dev",
        "preferred_practice_time": PreferredPracticeTime.AFTERNOON,
    },
    {
        "display_name": "Carmen Ruiz",
        "timezone": "America/Los_Angeles",
        "email": "carmen@demo.aischeduler.dev",
        "preferred_practice_time": PreferredPracticeTime.EVENING,
    },
    {
        "display_name": "Dev Patel",
        "timezone": "America/New_York",
        "email": "dev@demo.aischeduler.dev",
        "preferred_practice_time": None,
    },
]

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


def _truncate_all(db: Session) -> None:
    for model in _TABLES_CHILD_TO_PARENT:
        db.execute(delete(model))
    db.commit()


def _seed_members(db: Session) -> list[User]:
    service = UserService(db)
    return [
        service.create_user(
            UserCreate(
                display_name=spec["display_name"],
                timezone=spec["timezone"],
                email=spec["email"],
                preferred_practice_time=spec["preferred_practice_time"],
            )
        )
        for spec in DEMO_MEMBERS
    ]


def _seed_availability(db: Session, users: list[User], today: date) -> None:
    service = AvailabilityService(db)
    for offset, user in enumerate(users):
        for day_offset in range(0, 14, 2):
            day = today + timedelta(days=day_offset)
            start_hour = 17 + (offset % 3)
            start = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=start_hour)
            end = start + timedelta(hours=2)
            service.create_interval(user.id, AvailabilityCreate(start_at=start, end_at=end))


def _seed_busy_intervals(db: Session, users: list[User], today: date) -> None:
    # Synthetic busy time simulating a synced Google Calendar, without any real OAuth
    # connection -- calendar_connection_id is nullable, so these render on the
    # calendar's per-member overlay exactly like real synced busy time would, letting
    # the demo look "already connected" without anyone touching Google OAuth.
    for offset, user in enumerate(users):
        for day_offset in range(1, 12, 3):
            day = today + timedelta(days=day_offset)
            start_hour = 9 + offset
            start = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=start_hour)
            end = start + timedelta(hours=1, minutes=30)
            db.add(CalendarBusyInterval(user_id=user.id, calendar_connection_id=None, start_at=start, end_at=end))
    db.commit()


def _seed_events(db: Session, users: list[User], today: date) -> list[DanceEvent]:
    service = EventService(db)
    deadline = lambda days: datetime.combine(today + timedelta(days=days), datetime.min.time(), tzinfo=UTC)  # noqa: E731
    return [
        service.create_event(
            DanceEventCreate(
                name="Contemporary Showcase",
                description="Spring showcase piece -- two practices needed before the deadline.",
                organizer_user_id=users[0].id,
                duration_minutes=90,
                min_days_apart=2,
                latest_schedule_at=deadline(21),
                required_session_count=2,
                participants=[
                    DanceEventParticipantCreate(user_id=users[0].id, role="required"),
                    DanceEventParticipantCreate(user_id=users[1].id, role="required"),
                    DanceEventParticipantCreate(user_id=users[2].id, role="optional"),
                ],
            )
        ),
        service.create_event(
            DanceEventCreate(
                name="Nutcracker",
                description="Winter production run-throughs.",
                organizer_user_id=users[1].id,
                duration_minutes=120,
                min_days_apart=3,
                latest_schedule_at=deadline(30),
                required_session_count=3,
                participants=[DanceEventParticipantCreate(user_id=user.id, role="required") for user in users],
            )
        ),
        service.create_event(
            DanceEventCreate(
                name="Solo Piece",
                description="Unscheduled -- left open so the demo shows all three status states.",
                organizer_user_id=users[3].id,
                duration_minutes=60,
                min_days_apart=1,
                latest_schedule_at=deadline(45),
                required_session_count=1,
                participants=[DanceEventParticipantCreate(user_id=users[3].id, role="required")],
            )
        ),
    ]


def _seed_planning_run(db: Session, events: list[DanceEvent], today: date) -> None:
    horizon_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    horizon_end = horizon_start + timedelta(days=14)
    run = PlanningService(db).create_planning_run(
        PlanningRunCreate(
            event_ids=[event.id for event in events],
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
    )
    if run is None:
        return

    # Confirm the top-ranked recommendation for the showcase's first session so the
    # calendar isn't empty on first load, mirroring what a real organizer would do.
    # Session indices are 1-based (see _pending_session_indices in planning_service.py).
    top_pick = next(
        (
            result
            for result in sorted(run.results, key=lambda r: r.rank)
            if result.dance_event_id == events[0].id and result.session_index == 1
        ),
        None,
    )
    if top_pick is not None:
        PlanningService(db).confirm_results(run.id, [top_pick.id])


def reset_demo(db: Session) -> None:
    """Wipe all domain data and reseed. Used for both the initial seed and demo resets."""
    _truncate_all(db)
    today = datetime.now(UTC).date()
    users = _seed_members(db)
    _seed_availability(db, users, today)
    _seed_busy_intervals(db, users, today)
    events = _seed_events(db, users, today)
    _seed_planning_run(db, events, today)
