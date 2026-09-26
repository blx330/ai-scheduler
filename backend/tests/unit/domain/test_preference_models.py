"""Free-text preferences ("not before 7pm") are cached as earliest/latest times and
converted into scoring ranges. The conversion has to use the planner's real 8 AM to
midnight practice window: an older 8 AM to noon clamp silently dropped every
evening preference, which is what nearly every student dancer actually writes."""

from app.domain.preferences.models import (
    CachedPracticePreference,
    cached_practice_preference_to_parsed_preference,
)


def _ranges(cached: CachedPracticePreference) -> list[tuple[str, str]]:
    parsed = cached_practice_preference_to_parsed_preference(cached, "America/New_York")
    assert parsed is not None
    return [(item.start_local, item.end_local) for item in parsed.preferred_time_ranges]


def test_earliest_time_alone_prefers_from_then_until_midnight() -> None:
    assert _ranges(CachedPracticePreference(earliest_time="19:00")) == [("19:00", "24:00")]


def test_latest_time_alone_prefers_from_eight_am_until_then() -> None:
    assert _ranges(CachedPracticePreference(latest_time="22:00")) == [("08:00", "22:00")]


def test_both_times_prefer_exactly_that_window() -> None:
    assert _ranges(CachedPracticePreference(earliest_time="09:00", latest_time="11:00")) == [("09:00", "11:00")]


def test_days_only_preference_has_no_time_range() -> None:
    assert _ranges(CachedPracticePreference(preferred_days=["Saturday"])) == []


def test_earliest_before_the_practice_window_is_clamped_to_it() -> None:
    assert _ranges(CachedPracticePreference(earliest_time="06:00", latest_time="10:00")) == [("08:00", "10:00")]
