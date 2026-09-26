"""One student dance team's semester, used to seed the public demo.

The roster is a Penn team in America/New_York. Cindy's blocks mirror a real Fall
2026 course load (CIS 2400, CIS 5210, CIS 1951, ESE 2030, ESE 5430, LGST 1010 plus a
competitive-programming club); the meeting times are representative rather than
authoritative. Everyone else is synthetic but shaped the same way: recurring
classes, labs and shifts as busy time, evenings and weekends as declared free time,
and a few one-off conflicts (an exam, an interview) in the coming days.

Everything here is plain data plus two pure expansion helpers. Nothing touches the
database; see demo_seed_service.py for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.availability.models import Interval
from app.domain.common.enums import UserRole, Weekday
from app.domain.preferences.models import PreferredPracticeTime
from app.domain.scheduling.constraints import WEEKDAY_BY_INDEX

DEMO_TIMEZONE = "America/New_York"
DEMO_EMAIL_DOMAIN = "demo.aischeduler.dev"
ROOM_NAME = "Platt Studio"
# Recurring busy time is seeded a week further out than availability so the
# calendar still looks lived-in past the planning horizon.
BUSY_WEEKS = 5
AVAILABILITY_WEEKS = 4
PLANNING_HORIZON_DAYS = 14


@dataclass(frozen=True)
class WeeklyBlock:
    """A recurring block in organizer-local time. `end == 00:00` means midnight at
    the end of the day."""

    weekday: Weekday
    start: time
    end: time
    label: str


@dataclass(frozen=True)
class OneOffBlock:
    """A single block `days_from_today` days ahead, so the conflict is always in the
    near future no matter when the demo resets."""

    days_from_today: int
    start: time
    end: time
    label: str


@dataclass(frozen=True)
class MemberSpec:
    key: str
    display_name: str
    role: UserRole = UserRole.MEMBER
    preferred_practice_time: PreferredPracticeTime | None = None
    # Free text is parsed by the deterministic stub parser at seed time, so the
    # phrasing here has to be one the stub understands (see StubUserProfilePreferenceParser).
    preferred_practice_time_raw: str | None = None
    weekly_busy: tuple[WeeklyBlock, ...] = ()
    one_off_busy: tuple[OneOffBlock, ...] = ()
    weekly_free: tuple[WeeklyBlock, ...] = ()

    @property
    def email(self) -> str:
        return f"{self.key}@{DEMO_EMAIL_DOMAIN}"


@dataclass(frozen=True)
class DanceSpec:
    key: str
    name: str
    description: str
    organizer: str
    duration_minutes: int
    session_count: int
    deadline_days: int
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    min_days_apart: int = 0
    allowed_weekdays: tuple[Weekday, ...] = ()
    blocked_weekdays: tuple[Weekday, ...] = ()
    earliest_start_time: time | None = None
    latest_end_time: time | None = None
    # Rehearsals already held this week, as (weekday, local start). They take the
    # first session indices, so the current week has something on it whatever day
    # the reset runs, and they constrain what the planner may still propose.
    held_this_week: tuple[tuple[Weekday, time], ...] = ()
    # Session indices whose top recommendation the seed confirms, so the calendar
    # opens with upcoming practices already on it.
    confirm_session_indices: tuple[int, ...] = field(default_factory=tuple)


def _weekdays(*days: Weekday):
    return days


MON, TUE, WED, THU, FRI, SAT, SUN = WEEKDAY_BY_INDEX


def _block(days, start: time, end: time, label: str) -> tuple[WeeklyBlock, ...]:
    return tuple(WeeklyBlock(day, start, end, label) for day in days)


def _t(hour: int, minute: int = 0) -> time:
    return time(hour, minute)


MEMBERS: tuple[MemberSpec, ...] = (
    MemberSpec(
        key="cindy",
        display_name="Cindy Li",
        role=UserRole.ORGANIZER,
        preferred_practice_time_raw="Evenings after 6pm, no Fridays",
        weekly_busy=(
            *_block((MON, WED), _t(10, 15), _t(11, 45), "CIS 2400 lecture"),
            *_block((MON, WED), _t(12), _t(13, 30), "ESE 2030 lecture"),
            *_block((TUE, THU), _t(10, 15), _t(11, 45), "CIS 5210 lecture"),
            *_block((TUE, THU), _t(12), _t(13, 30), "LGST 1010 lecture"),
            *_block((TUE,), _t(17, 15), _t(18, 45), "CIS 1951 (iOS) lab"),
            *_block((WED,), _t(15, 30), _t(17), "CIS 5210 office hours"),
            *_block((THU,), _t(13, 45), _t(16, 45), "ESE 5430 seminar"),
            *_block((FRI,), _t(13, 45), _t(14, 45), "CIS 2400 recitation"),
            *_block((SAT,), _t(13), _t(16), "Penn competitive programming club"),
        ),
        one_off_busy=(
            OneOffBlock(2, _t(14), _t(14, 30), "CIS 5210 lab login check (Moore 100C)"),
            OneOffBlock(5, _t(16), _t(17), "Internship phone screen"),
            OneOffBlock(11, _t(18, 30), _t(20, 30), "CIS 2400 midterm"),
        ),
        weekly_free=(
            *_block((MON, TUE, WED, THU), _t(18), _t(23), "evenings"),
            *_block((FRI,), _t(17), _t(21), "early Friday evening"),
            *_block((SAT,), _t(10), _t(13), "Saturday morning"),
            *_block((SAT,), _t(16), _t(22), "Saturday evening"),
            *_block((SUN,), _t(10), _t(22), "Sunday"),
        ),
    ),
    MemberSpec(
        key="maya",
        display_name="Maya Chen",
        preferred_practice_time=PreferredPracticeTime.EVENING,
        weekly_busy=(
            *_block((MON, WED), _t(9), _t(10, 30), "MGMT 1010"),
            *_block((MON, WED), _t(10, 30), _t(12), "ACCT 1010"),
            *_block((TUE, THU), _t(13, 45), _t(15, 15), "STAT 1010"),
            *_block((FRI,), _t(15), _t(17), "Consulting club"),
        ),
        weekly_free=(
            *_block((MON, TUE, WED, THU, FRI), _t(18), _t(23), "evenings"),
            *_block((SAT, SUN), _t(12), _t(20), "weekend afternoons"),
        ),
    ),
    MemberSpec(
        key="jordan",
        display_name="Jordan Rivera",
        preferred_practice_time=PreferredPracticeTime.LATE_NIGHT,
        weekly_busy=(
            *_block((TUE, THU), _t(10, 15), _t(11, 45), "CIS 3200"),
            *_block((TUE, THU), _t(12), _t(13, 30), "CIS 4710"),
            *_block((MON, WED), _t(15, 30), _t(17), "CIS 4710 lab"),
            *_block((WED,), _t(19), _t(21), "TA office hours (CIS 1200)"),
        ),
        weekly_free=(
            *_block((MON, TUE, WED, THU), _t(17), _t(23), "evenings"),
            *_block((SUN,), _t(14), _t(21), "Sunday"),
        ),
    ),
    MemberSpec(
        key="priya",
        display_name="Priya Nair",
        preferred_practice_time_raw="Weekends are best, not before 7pm",
        weekly_busy=(
            *_block((MON, WED, FRI), _t(9), _t(10), "CHEM 1012"),
            *_block((TUE, THU), _t(10, 15), _t(11, 45), "BIOL 1101"),
            *_block((TUE,), _t(13, 45), _t(16, 45), "CHEM 1102 lab"),
            *_block((THU,), _t(13, 45), _t(16, 45), "BIOL 1101 lab"),
            *_block((SAT,), _t(9), _t(13), "MCAT prep"),
        ),
        one_off_busy=(OneOffBlock(8, _t(19), _t(21), "CHEM 1012 midterm"),),
        weekly_free=(
            *_block((MON, TUE, WED, THU, FRI), _t(19), _t(22, 30), "evenings"),
            *_block((SAT,), _t(14), _t(20), "Saturday"),
            *_block((SUN,), _t(10), _t(18), "Sunday"),
        ),
    ),
    MemberSpec(
        key="marcus",
        display_name="Marcus Williams",
        preferred_practice_time_raw="Tuesdays and Thursdays only, no Mondays",
        weekly_busy=(
            *_block((MON, WED, FRI), _t(17), _t(22), "Bookstore shift"),
            *_block((TUE, THU), _t(12), _t(13, 30), "ECON 0100"),
            *_block((TUE, THU), _t(15, 30), _t(17), "MATH 1400"),
        ),
        weekly_free=(
            *_block((TUE, THU), _t(17, 30), _t(23), "evenings off"),
            *_block((SAT, SUN), _t(11), _t(19), "weekends"),
        ),
    ),
    MemberSpec(
        key="sofia",
        display_name="Sofia Martinez",
        preferred_practice_time=PreferredPracticeTime.EVENING,
        weekly_busy=(
            *_block((MON, WED), _t(13, 45), _t(15, 15), "Thesis seminar"),
            *_block((THU,), _t(15, 30), _t(18, 30), "Senior seminar"),
            *_block((TUE,), _t(20), _t(22), "A cappella rehearsal"),
        ),
        weekly_free=(
            *_block((MON, TUE, WED, THU), _t(18), _t(23), "evenings"),
            *_block((FRI,), _t(16), _t(20), "Friday"),
            *_block((SAT,), _t(10), _t(18), "Saturday"),
            *_block((SUN,), _t(12), _t(18), "Sunday"),
        ),
    ),
    MemberSpec(
        key="ethan",
        display_name="Ethan Park",
        weekly_busy=(
            *_block((MON, WED, FRI), _t(10), _t(11), "MATH 1410"),
            *_block((MON, WED, FRI), _t(11), _t(12), "PHYS 0150"),
            *_block((TUE, THU), _t(12), _t(13, 30), "Writing seminar"),
            *_block((THU,), _t(18), _t(20), "Intramural soccer"),
        ),
        weekly_free=(
            *_block((MON, TUE, WED, THU, FRI), _t(19), _t(23, 30), "evenings"),
            *_block((SAT, SUN), _t(12), _t(22), "weekends"),
        ),
    ),
    MemberSpec(
        key="aisha",
        display_name="Aisha Okafor",
        preferred_practice_time_raw="Never Fridays, mornings are hard",
        weekly_busy=(
            *_block((TUE, THU), _t(7), _t(15), "Nursing clinical (HUP)"),
            *_block((MON, WED), _t(12), _t(13, 30), "NURS 2150"),
        ),
        weekly_free=(
            *_block((MON, WED), _t(18), _t(23), "evenings"),
            *_block((FRI,), _t(18), _t(22), "Friday (reluctantly)"),
            *_block((SAT, SUN), _t(13), _t(21), "weekends"),
        ),
    ),
    MemberSpec(
        key="leo",
        display_name="Leo Nguyen",
        preferred_practice_time=PreferredPracticeTime.LATE_NIGHT,
        weekly_busy=(*_block((MON, TUE, WED, THU, FRI), _t(9), _t(17), "Research lab (ESE)"),),
        weekly_free=(
            *_block((MON, TUE, WED, THU, FRI), _t(18, 30), _t(23), "evenings"),
            *_block((SAT,), _t(14), _t(20), "Saturday"),
            *_block((SUN,), _t(12), _t(20), "Sunday"),
        ),
    ),
    # Joined this week and has not entered availability yet -- the planner treats
    # her as unavailable, which is what makes every slot for her dance a fallback.
    MemberSpec(key="nina", display_name="Nina Kowalski"),
)


DANCES: tuple[DanceSpec, ...] = (
    DanceSpec(
        key="showcase",
        name="Fall Showcase: Opening Number",
        description=(
            "Full-cast opener for the fall showcase. Three 90-minute rehearsals before "
            "the run-through, spaced out so nobody rehearses two nights running. No "
            "Fridays, and out of the studio by 10:30 PM."
        ),
        organizer="cindy",
        duration_minutes=90,
        session_count=3,
        min_days_apart=2,
        deadline_days=18,
        required=("cindy", "maya", "jordan", "priya", "sofia", "ethan"),
        optional=("aisha", "leo", "marcus"),
        blocked_weekdays=_weekdays(FRI),
        latest_end_time=time(22, 30),
        held_this_week=((MON, time(19, 0)),),
        confirm_session_indices=(2,),
    ),
    DanceSpec(
        key="hiphop",
        name="Hip Hop Set",
        description=(
            "Small-group set. Two one-hour sessions; Marcus and Aisha can only do "
            "evenings, so nothing starts before 6 PM."
        ),
        organizer="cindy",
        duration_minutes=60,
        session_count=2,
        min_days_apart=1,
        deadline_days=21,
        required=("maya", "marcus", "ethan", "aisha"),
        optional=("jordan", "leo"),
        earliest_start_time=time(18, 0),
        confirm_session_indices=(1, 2),
    ),
    DanceSpec(
        key="feature",
        name="New Member Feature",
        description=(
            "Short feature to welcome Nina. She has not entered her availability yet, so "
            "the planner can only offer fallback slots that flag her as missing -- ask "
            "her to fill in her free time, then plan again."
        ),
        organizer="cindy",
        duration_minutes=45,
        session_count=1,
        deadline_days=12,
        required=("nina", "cindy", "maya"),
        optional=("sofia",),
    ),
    DanceSpec(
        key="runthrough",
        name="Full Run-Through (Tech Week)",
        description=(
            "Two-hour stumble-through with the whole team. Weekends only. Jordan has "
            "not declared any Saturday availability (no classes, just never marked "
            "himself free), so Saturdays are only offered as fallbacks that say so; "
            "Sunday afternoon fits everyone."
        ),
        organizer="cindy",
        duration_minutes=120,
        session_count=1,
        deadline_days=14,
        required=("cindy", "maya", "jordan", "priya", "marcus", "sofia", "ethan", "aisha", "leo"),
        optional=("nina",),
        allowed_weekdays=_weekdays(SAT, SUN),
    ),
)


def member_by_key(key: str) -> MemberSpec:
    return next(member for member in MEMBERS if member.key == key)


def weekly_block_intervals(block: WeeklyBlock, week_start: date, weeks: int, zone: ZoneInfo) -> list[Interval]:
    """Expand a recurring block into UTC intervals for `weeks` weeks from `week_start`
    (a Monday). Wall-clock times are kept across DST changes."""
    first_day = week_start + timedelta(days=WEEKDAY_BY_INDEX.index(block.weekday))
    return [
        _local_interval(first_day + timedelta(weeks=week), block.start, block.end, zone)
        for week in range(weeks)
    ]


def one_off_block_intervals(blocks: tuple[OneOffBlock, ...] | list[OneOffBlock], today: date, zone: ZoneInfo) -> list[Interval]:
    return [
        _local_interval(today + timedelta(days=block.days_from_today), block.start, block.end, zone)
        for block in blocks
    ]


def _local_interval(day: date, start: time, end: time, zone: ZoneInfo) -> Interval:
    end_day = day + timedelta(days=1) if end == time(0, 0) else day
    return Interval(
        start_at=datetime.combine(day, start, tzinfo=zone).astimezone(UTC),
        end_at=datetime.combine(end_day, end, tzinfo=zone).astimezone(UTC),
    )
