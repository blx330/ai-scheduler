from app.infrastructure.integrations.llm.profile_preference_parser import (
    StubUserProfilePreferenceParser,
    build_user_profile_preference_parser,
)


def _parse(text: str) -> dict:
    return StubUserProfilePreferenceParser().parse(text, timezone_name="UTC")


def test_not_before_sets_only_earliest_time() -> None:
    # Regression test: "not before 9am" previously matched the latest-time pattern
    # too (via the "before 9am" substring), setting earliest_time == latest_time.
    result = _parse("not before 9am")
    assert result["earliest_time"] == "09:00"
    assert result["latest_time"] is None


def test_never_before_sets_only_earliest_time() -> None:
    result = _parse("never before 9am")
    assert result["earliest_time"] == "09:00"
    assert result["latest_time"] is None


def test_not_after_sets_only_latest_time() -> None:
    result = _parse("not after 6pm")
    assert result["latest_time"] == "18:00"
    assert result["earliest_time"] is None


def test_bare_before_sets_latest_time() -> None:
    result = _parse("free before 9am")
    assert result["latest_time"] == "09:00"
    assert result["earliest_time"] is None


def test_bare_after_sets_earliest_time() -> None:
    result = _parse("free after 6pm")
    assert result["earliest_time"] == "18:00"
    assert result["latest_time"] is None


def test_avoid_day_is_not_also_preferred() -> None:
    result = _parse("avoid Fridays, prefer weekends")
    assert "Friday" not in result["preferred_days"]
    assert "Friday" in result["avoid_days"]
    assert "Saturday" in result["preferred_days"]
    assert "Sunday" in result["preferred_days"]


def test_mornings_only_defaults_latest_time_when_unset() -> None:
    result = _parse("mornings only")
    assert result["latest_time"] == "12:00"


def test_mornings_only_does_not_override_explicit_latest_time() -> None:
    result = _parse("mornings only, not after 10am")
    assert result["latest_time"] == "10:00"


def test_empty_text_produces_no_preferences() -> None:
    result = _parse("")
    assert result["preferred_days"] == []
    assert result["avoid_days"] == []
    assert result["earliest_time"] is None
    assert result["latest_time"] is None
    assert result["notes"] is None


def test_build_parser_returns_stub_when_no_api_key() -> None:
    parser = build_user_profile_preference_parser(api_key="")
    assert isinstance(parser, StubUserProfilePreferenceParser)
