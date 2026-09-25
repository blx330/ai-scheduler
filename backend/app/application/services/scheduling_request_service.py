"""Plain-English scheduling requests: parse -> ground in real data -> review -> plan.

The LLM only proposes structure. This service decides whether that structure
refers to real dances, members and rooms and whether its dates make sense, and it
reports every problem it finds instead of guessing. Nothing is written until the
organizer confirms, and confirm re-runs every check against the ids it is sent
rather than trusting the reviewed payload.

Merge semantics against the event's saved settings:
- a field the request states overrides the saved value; an unstated field keeps it
- named attendees are added or have their role updated; nobody is removed
- session_count is the dance's total, including sessions already confirmed
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas.events import DanceEventParticipantCreate, DanceEventUpdate
from app.api.schemas.planning import MAX_HORIZON_DAYS, PlanningRunCreate
from app.api.schemas.scheduling_requests import (
    FieldChange,
    ProposalParticipant,
    ReviewEvent,
    ReviewParticipant,
    ReviewRoom,
    SchedulingProposal,
    SchedulingRequestReview,
)
from app.application.services.event_service import EventService
from app.application.services.planning_service import PlanningService
from app.domain.common.datetime_utils import ensure_utc
from app.domain.common.enums import Weekday
from app.domain.scheduling.constraints import DayTimeConstraints
from app.domain.scheduling.requests import SchedulingRequest
from app.infrastructure.db.models import DanceEvent, PlanningRun, Room, User
from app.infrastructure.integrations.llm.scheduling_request_parser import ParseContext, SchedulingRequestParser

# A deadline this many days out still fits in one planning run (MAX_HORIZON_DAYS)
# once the run starts partway through today.
MAX_DAYS_AHEAD = MAX_HORIZON_DAYS - 1
SLOT_STEP_MINUTES = 60
MAX_NAMES_IN_ERROR = 20
FALLBACK_NOTE = (
    "Slots where every required dancer can attend are always tried first, within 8:00 AM-12:00 AM "
    "and favoring 6-10 PM, then 10 PM-12 AM. Only if none exist may a fallback missing one required "
    "dancer be suggested; it is clearly flagged and needs a second confirmation."
)


class SchedulingRequestRejected(ValueError):
    """The request is well-formed but does not fit the real data. Carries every problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(" ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class _Plan:
    """A fully resolved request, before or after confirmation."""

    event: DanceEvent
    session_count: int
    earliest_date: date | None
    latest_date: date
    min_days_apart: int
    roles: dict[UUID, str]
    rules: DayTimeConstraints
    room: Room | None


class SchedulingRequestService:
    def __init__(
        self,
        db: Session,
        parser: SchedulingRequestParser,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.parser = parser
        self._now = now or (lambda: datetime.now(UTC))

    # --- parse -------------------------------------------------------------------

    def parse(self, text: str, requester_id: UUID | None = None) -> SchedulingRequestReview:
        events = self._events()
        users = list(self.db.scalars(select(User).order_by(User.display_name)))
        rooms = list(self.db.scalars(select(Room).where(Room.is_active.is_(True)).order_by(Room.name)))
        # The model resolves "Oct 20" / "next week" against the requester's today. The
        # dance isn't known yet; once it is, dates are re-checked in its organizer's zone.
        requester = next((user for user in users if user.id == requester_id), None)
        context_zone = requester.timezone if requester else events[0].organizer.timezone if events else "UTC"
        request = self.parser.parse(
            text,
            ParseContext(
                today=self._today(context_zone),
                timezone=context_zone,
                event_names=[event.name for event in events],
                member_names=[user.display_name for user in users],
                room_names=[room.name for room in rooms],
            ),
        )

        errors: list[str] = []
        if request.unsupported_phrases:
            errors.append(_unsupported_message(request.unsupported_phrases))
        event = _match_event(request.event_name, events, errors)
        roles_requested: dict[UUID, str] = {}
        for role, names in (("required", request.required_attendees), ("optional", request.optional_attendees)):
            for name in names:
                user = _match_member(name, users, errors)
                if user is not None:
                    roles_requested[user.id] = role
        room = _match_room(request.room, rooms, errors) if request.room is not None else None
        if event is None:
            raise SchedulingRequestRejected(errors)

        zone = ZoneInfo(event.organizer.timezone)
        saved_roles = {participant.user_id: participant.role for participant in event.participants}
        rules = _merge_rules(request, event, errors)
        if errors:
            raise SchedulingRequestRejected(errors)
        plan = _Plan(
            event=event,
            session_count=request.session_count or event.required_session_count,
            earliest_date=request.earliest_date or event.earliest_start_date,
            latest_date=request.latest_date or _saved_latest_date(event, zone),
            min_days_apart=event.min_days_apart if request.min_days_between is None else request.min_days_between,
            roles={**saved_roles, **roles_requested},
            rules=rules,
            room=room,
        )
        self._validate(plan)
        return self._review(text, request, plan, saved_roles)

    # --- confirm ---------------------------------------------------------------------

    def confirm(self, proposal: SchedulingProposal) -> tuple[DanceEvent, PlanningRun]:
        errors: list[str] = []
        event = next((item for item in self._events() if item.id == proposal.event_id), None)
        if event is None:
            raise SchedulingRequestRejected(["Dance not found."])
        known_user_ids = set(
            self.db.scalars(select(User.id).where(User.id.in_([item.user_id for item in proposal.participants])))
        )
        for participant in proposal.participants:
            if participant.user_id not in known_user_ids:
                errors.append(f"Unknown member id {participant.user_id}.")
        room: Room | None = None
        if proposal.room_id is not None:
            room = self.db.get(Room, proposal.room_id)
            if room is None or not room.is_active:
                errors.append("Room not found.")
        try:
            rules = DayTimeConstraints(
                allowed_weekdays=frozenset(proposal.allowed_weekdays),
                blocked_weekdays=frozenset(proposal.blocked_weekdays),
                earliest_start_local=proposal.earliest_start_time,
                latest_end_local=proposal.latest_end_time,
            )
        except ValueError as exc:
            errors.append(str(exc))
            rules = DayTimeConstraints()
        if errors:
            raise SchedulingRequestRejected(errors)

        plan = _Plan(
            event=event,
            session_count=proposal.session_count,
            earliest_date=proposal.earliest_date,
            latest_date=proposal.latest_date,
            min_days_apart=proposal.min_days_apart,
            roles={item.user_id: item.role for item in proposal.participants},
            rules=rules,
            room=room,
        )
        self._validate(plan)

        zone = ZoneInfo(event.organizer.timezone)
        deadline = _local_midnight(plan.latest_date + timedelta(days=1), zone)
        # Build (and so validate) the run request before touching the event, so a bad
        # horizon cannot leave the event updated with no plan to show for it.
        run_request = PlanningRunCreate(
            event_ids=[event.id],
            horizon_start=self._horizon_start(zone),
            horizon_end=deadline,
            slot_step_minutes=SLOT_STEP_MINUTES,
            room_id=room.id if room is not None else None,
        )
        update = DanceEventUpdate(
            required_session_count=plan.session_count,
            earliest_start_date=plan.earliest_date,
            latest_schedule_at=deadline,
            min_days_apart=plan.min_days_apart,
            participants=[
                DanceEventParticipantCreate(user_id=user_id, role=role) for user_id, role in plan.roles.items()
            ],
            allowed_weekdays=sorted(plan.rules.allowed_weekdays, key=_weekday_order),
            blocked_weekdays=sorted(plan.rules.blocked_weekdays, key=_weekday_order),
            earliest_start_time=plan.rules.earliest_start_local,
            latest_end_time=plan.rules.latest_end_local,
        )
        try:
            updated = EventService(self.db).update_event(event.id, update)
        except ValueError as exc:
            raise SchedulingRequestRejected([str(exc)]) from exc
        assert updated is not None
        run = PlanningService(self.db).create_planning_run(run_request)
        return updated, run

    # --- shared validation --------------------------------------------------------------

    def _validate(self, plan: _Plan) -> None:
        event = plan.event
        zone_name = event.organizer.timezone
        zone = ZoneInfo(zone_name)
        today = self._today(zone_name)
        errors: list[str] = []

        # A saved earliest date in the past is harmless (it is just a floor); only a
        # newly requested one is a mistake.
        if plan.earliest_date is not None and plan.earliest_date < today and plan.earliest_date != event.earliest_start_date:
            errors.append(f"earliest date {plan.earliest_date} is in the past (today is {today} in {zone_name}).")
        if plan.latest_date < today:
            errors.append(f"latest date {plan.latest_date} is in the past (today is {today} in {zone_name}).")
        elif (plan.latest_date - today).days > MAX_DAYS_AHEAD:
            errors.append(
                f"latest date {plan.latest_date} is more than {MAX_DAYS_AHEAD} days away; "
                f"the planner looks at most {MAX_HORIZON_DAYS} days ahead."
            )
        if plan.earliest_date is not None and plan.earliest_date > plan.latest_date:
            errors.append(f"earliest date {plan.earliest_date} is after the latest date {plan.latest_date}.")

        confirmed = _confirmed_count(event)
        pending = plan.session_count - confirmed
        if plan.session_count < confirmed:
            errors.append(
                f"{event.name} already has {confirmed} confirmed sessions, so the total cannot be {plan.session_count}."
            )
        elif pending == 0:
            errors.append(
                f"{event.name} already has all {confirmed} sessions confirmed; ask for a higher total to plan more."
            )

        if not any(role == "required" for role in plan.roles.values()):
            errors.append("At least one required dancer is needed.")

        if not errors and pending > 1 and plan.min_days_apart > 0:
            window_start = max(today, plan.earliest_date or today)
            available_days = (plan.latest_date - window_start).days + 1
            needed_days = (pending - 1) * plan.min_days_apart + 1
            if needed_days > available_days:
                errors.append(
                    f"{pending} sessions at least {plan.min_days_apart} days apart need at least {needed_days} days, "
                    f"but {window_start} to {plan.latest_date} has only {available_days}."
                )

        if not errors and _local_midnight(plan.latest_date + timedelta(days=1), zone) <= self._horizon_start(zone):
            errors.append(f"There is no time left before the latest date {plan.latest_date}.")
        if errors:
            raise SchedulingRequestRejected(errors)

    # --- helpers ------------------------------------------------------------------------

    def _events(self) -> list[DanceEvent]:
        statement = (
            select(DanceEvent)
            .order_by(DanceEvent.name)
            .options(
                selectinload(DanceEvent.participants),
                selectinload(DanceEvent.practice_sessions),
                selectinload(DanceEvent.organizer),
            )
        )
        return list(self.db.scalars(statement))

    def _today(self, zone_name: str) -> date:
        return self._now().astimezone(ZoneInfo(zone_name)).date()

    def _horizon_start(self, zone: ZoneInfo) -> datetime:
        """Now, rounded up to the next whole local hour so candidate slots start on the hour."""
        local_now = self._now().astimezone(zone)
        rounded = local_now.replace(minute=0, second=0, microsecond=0)
        if rounded < local_now:
            rounded += timedelta(hours=1)
        return rounded.astimezone(UTC)

    def _review(
        self,
        text: str,
        request: SchedulingRequest,
        plan: _Plan,
        saved_roles: dict[UUID, str],
    ) -> SchedulingRequestReview:
        event = plan.event
        zone = ZoneInfo(event.organizer.timezone)
        users = {
            user.id: user for user in self.db.scalars(select(User).where(User.id.in_(list(plan.roles))))
        }
        participants = [
            ReviewParticipant(
                user_id=user_id,
                display_name=users[user_id].display_name,
                role=role,  # type: ignore[arg-type]
                change=(
                    "added"
                    if user_id not in saved_roles
                    else "role_changed"
                    if saved_roles[user_id] != role
                    else "unchanged"
                ),
            )
            for user_id, role in sorted(plan.roles.items(), key=lambda item: users[item[0]].display_name.casefold())
        ]
        saved = {
            "session_count": str(event.required_session_count),
            "earliest_date": _show(event.earliest_start_date),
            "latest_date": str(_saved_latest_date(event, zone)),
            "min_days_apart": str(event.min_days_apart),
            "allowed_weekdays": _show_days(_saved_weekdays(event.allowed_weekdays_json)),
            "blocked_weekdays": _show_days(_saved_weekdays(event.blocked_weekdays_json)),
            "earliest_start_time": _show(event.earliest_start_time_local),
            "latest_end_time": _show(event.latest_end_time_local),
        }
        proposed = {
            "session_count": str(plan.session_count),
            "earliest_date": _show(plan.earliest_date),
            "latest_date": str(plan.latest_date),
            "min_days_apart": str(plan.min_days_apart),
            "allowed_weekdays": _show_days(plan.rules.allowed_weekdays),
            "blocked_weekdays": _show_days(plan.rules.blocked_weekdays),
            "earliest_start_time": _show(plan.rules.earliest_start_local),
            "latest_end_time": _show(plan.rules.latest_end_local),
        }
        labels = {
            "session_count": "Total sessions",
            "earliest_date": "Earliest date",
            "latest_date": "Latest date",
            "min_days_apart": "Minimum days apart",
            "allowed_weekdays": "Allowed days",
            "blocked_weekdays": "Blocked days",
            "earliest_start_time": "Start no earlier than",
            "latest_end_time": "End no later than",
        }
        changes = [
            FieldChange(field=field, label=labels[field], before=saved[field], after=proposed[field])
            for field in labels
            if saved[field] != proposed[field]
        ]
        confirmed = _confirmed_count(event)
        notes = [FALLBACK_NOTE]
        if plan.room is None:
            notes.append("No room was named, so the default shared room will be used.")
        return SchedulingRequestReview(
            request_text=text,
            parsed=request,
            proposal=SchedulingProposal(
                event_id=event.id,
                session_count=plan.session_count,
                earliest_date=plan.earliest_date,
                latest_date=plan.latest_date,
                min_days_apart=plan.min_days_apart,
                participants=[
                    ProposalParticipant(user_id=item.user_id, role=item.role) for item in participants
                ],
                allowed_weekdays=sorted(plan.rules.allowed_weekdays, key=_weekday_order),
                blocked_weekdays=sorted(plan.rules.blocked_weekdays, key=_weekday_order),
                earliest_start_time=plan.rules.earliest_start_local,
                latest_end_time=plan.rules.latest_end_local,
                room_id=plan.room.id if plan.room is not None else None,
            ),
            event=ReviewEvent(
                id=event.id,
                name=event.name,
                organizer_timezone=event.organizer.timezone,
                duration_minutes=event.duration_minutes,
                confirmed_session_count=confirmed,
            ),
            room=ReviewRoom(id=plan.room.id, name=plan.room.name) if plan.room is not None else None,
            participants=participants,
            changes=changes,
            sessions_to_plan=plan.session_count - confirmed,
            notes=notes,
        )


def _merge_rules(request: SchedulingRequest, event: DanceEvent, errors: list[str]) -> DayTimeConstraints:
    """Request rules over saved ones. The request is valid on its own, so a conflict
    here means it contradicts a saved rule; say which, so the fix is obvious."""
    saved_allowed = _saved_weekdays(event.allowed_weekdays_json)
    saved_blocked = _saved_weekdays(event.blocked_weekdays_json)
    allowed = frozenset(request.allowed_weekdays) or saved_allowed
    blocked = frozenset(request.blocked_weekdays) or saved_blocked
    earliest = request.earliest_start_time or event.earliest_start_time_local
    latest = request.latest_end_time or event.latest_end_time_local

    try:
        DayTimeConstraints(earliest_start_local=earliest, latest_end_local=latest)
    except ValueError as exc:
        saved = "earliest start" if request.earliest_start_time is None else "latest end"
        errors.append(f"{exc} (the {saved} was already saved on {event.name}; state a new one to replace it).")
        earliest = latest = None
    try:
        DayTimeConstraints(allowed_weekdays=allowed, blocked_weekdays=blocked)
    except ValueError as exc:
        saved = "allowed days" if not request.allowed_weekdays else "blocked days"
        errors.append(f"{exc} (the {saved} were already saved on {event.name}; state new ones to replace them).")
        allowed = blocked = frozenset()
    return DayTimeConstraints(
        allowed_weekdays=allowed, blocked_weekdays=blocked, earliest_start_local=earliest, latest_end_local=latest
    )


# --- name matching: exact (case-insensitive), then a unique first name; never fuzzy ---


def _match_event(name: str, events: list[DanceEvent], errors: list[str]) -> DanceEvent | None:
    known = _known("dances", [event.name for event in events])
    if not name.strip():
        errors.append(f"Could not tell which dance this request is for. {known}")
        return None
    matches = [event for event in events if event.name.casefold() == name.casefold()]
    if not matches:
        errors.append(f'Unknown dance "{name}". {known}')
        return None
    if len(matches) > 1:
        errors.append(f'More than one dance is named "{name}"; rename one on the Events page.')
        return None
    return matches[0]


def _match_member(name: str, users: list[User], errors: list[str]) -> User | None:
    matches = [user for user in users if user.display_name.casefold() == name.casefold()]
    if not matches and " " not in name.strip():
        matches = [user for user in users if user.display_name.split()[0].casefold() == name.casefold()]
    if not matches:
        errors.append(f'Unknown member "{name}". {_known("members", [user.display_name for user in users])}')
        return None
    if len(matches) > 1:
        names = ", ".join(sorted(user.display_name for user in matches))
        errors.append(f'"{name}" matches more than one member ({names}). Use their full name.')
        return None
    return matches[0]


def _match_room(name: str, rooms: list[Room], errors: list[str]) -> Room | None:
    matches = [room for room in rooms if room.name.casefold() == name.casefold()]
    if not matches:
        errors.append(f'Unknown room "{name}". {_known("rooms", [room.name for room in rooms])}')
        return None
    return matches[0]


def _known(kind: str, names: list[str]) -> str:
    if not names:
        return f"There are no {kind} yet."
    shown = ", ".join(sorted(names, key=str.casefold)[:MAX_NAMES_IN_ERROR])
    more = "" if len(names) <= MAX_NAMES_IN_ERROR else f" and {len(names) - MAX_NAMES_IN_ERROR} more"
    return f"Known {kind}: {shown}{more}."


def _unsupported_message(phrases: list[str]) -> str:
    quoted = ", ".join(f'"{phrase}"' for phrase in phrases)
    if len(phrases) == 1:
        return (
            f"Could not turn {quoted} into a scheduling rule. Rephrase it with explicit days or clock times "
            '(for example "after 6pm" or "no Fridays"), or remove it.'
        )
    return (
        f"Could not turn {quoted} into scheduling rules. Rephrase them with explicit days or clock times "
        '(for example "after 6pm" or "no Fridays"), or remove them.'
    )


# --- small conversions ----------------------------------------------------------------


def _confirmed_count(event: DanceEvent) -> int:
    return sum(1 for session in event.practice_sessions if session.status == "confirmed")


def _local_midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=zone).astimezone(UTC)


def _saved_latest_date(event: DanceEvent, zone: ZoneInfo) -> date:
    """Last local day a session can happen on, from the exclusive saved deadline."""
    return (ensure_utc(event.latest_schedule_at).astimezone(zone) - timedelta(microseconds=1)).date()


def _saved_weekdays(values: list[str] | None) -> frozenset[Weekday]:
    return frozenset(Weekday(value) for value in values or [])


def _weekday_order(day: Weekday) -> int:
    return list(Weekday).index(day)


def _show(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, time):
        return f"{value:%H:%M}"
    return str(value)


def _show_days(days: frozenset[Weekday]) -> str:
    return ", ".join(day.value for day in sorted(days, key=_weekday_order)) or "none"
