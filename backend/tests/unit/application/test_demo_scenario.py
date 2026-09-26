"""The demo scenario is data plus two pure expansion helpers; these tests pin the
helpers' timezone behaviour and keep the roster/dance definitions self-consistent."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.application.services.demo_scenario import (
    DANCES,
    DEMO_TIMEZONE,
    MEMBERS,
    OneOffBlock,
    WeeklyBlock,
    one_off_block_intervals,
    weekly_block_intervals,
)
from app.domain.common.enums import Weekday

NEW_YORK = ZoneInfo(DEMO_TIMEZONE)


def test_weekly_block_keeps_local_wall_time_across_the_dst_change() -> None:
    # Mon 2026-10-26 starts the last EDT week; Sun 2026-11-01 is the fall-back.
    block = WeeklyBlock(Weekday.TUE, time(18, 0), time(19, 30), "rehearsal")
    intervals = weekly_block_intervals(block, week_start=date(2026, 10, 26), weeks=2, zone=NEW_YORK)

    assert [item.start_at for item in intervals] == [
        datetime(2026, 10, 27, 22, 0, tzinfo=UTC),  # 18:00 EDT
        datetime(2026, 11, 3, 23, 0, tzinfo=UTC),  # 18:00 EST
    ]
    assert all((item.end_at - item.start_at).total_seconds() == 90 * 60 for item in intervals)


def test_weekly_block_ending_at_midnight_runs_to_the_end_of_the_local_day() -> None:
    block = WeeklyBlock(Weekday.SAT, time(20, 0), time(0, 0), "late")
    [interval] = weekly_block_intervals(block, week_start=date(2026, 9, 21), weeks=1, zone=NEW_YORK)
    assert interval.start_at == datetime(2026, 9, 27, 0, 0, tzinfo=UTC)  # Sat 20:00 EDT
    assert interval.end_at == datetime(2026, 9, 27, 4, 0, tzinfo=UTC)  # Sun 00:00 EDT


def test_one_off_block_is_relative_to_today_in_local_time() -> None:
    block = OneOffBlock(days_from_today=2, start=time(14, 0), end=time(14, 30), label="lab check")
    [interval] = one_off_block_intervals([block], today=date(2026, 9, 25), zone=NEW_YORK)
    assert interval.start_at == datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
    assert interval.end_at == datetime(2026, 9, 27, 18, 30, tzinfo=UTC)


def test_roster_keys_and_emails_are_unique() -> None:
    keys = [member.key for member in MEMBERS]
    emails = [member.email for member in MEMBERS]
    assert len(keys) == len(set(keys))
    assert len(emails) == len(set(emails))


def test_every_block_is_a_proper_same_day_window() -> None:
    for member in MEMBERS:
        for block in [*member.weekly_busy, *member.weekly_free]:
            assert block.start < block.end or block.end == time(0, 0), (member.key, block)
        for block in member.one_off_busy:
            assert block.days_from_today >= 0 and block.start < block.end, (member.key, block)


def test_availability_stays_inside_the_planner_practice_window() -> None:
    for member in MEMBERS:
        for block in member.weekly_free:
            assert block.start >= time(8, 0), (member.key, block)


def test_dances_reference_real_members_and_have_a_required_dancer() -> None:
    keys = {member.key for member in MEMBERS}
    for dance in DANCES:
        assert dance.organizer in keys
        assert dance.required, dance.name
        assert set(dance.required) <= keys and set(dance.optional) <= keys
        assert not set(dance.required) & set(dance.optional)
        assert set(dance.confirm_session_indices) <= set(range(1, dance.session_count + 1))


def test_exactly_one_member_has_no_availability_to_drive_the_fallback_story() -> None:
    without_availability = [member.key for member in MEMBERS if not member.weekly_free]
    assert len(without_availability) == 1
    [key] = without_availability
    fallback_dances = [dance for dance in DANCES if key in dance.required]
    assert len(fallback_dances) == 1
