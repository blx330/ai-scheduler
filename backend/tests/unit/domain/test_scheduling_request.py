from datetime import date, time

import pytest
from pydantic import ValidationError

from app.domain.common.enums import Weekday
from app.domain.scheduling.requests import SchedulingRequest

EXAMPLE = {
    "event_name": "Hip Hop",
    "session_count": 3,
    "earliest_date": None,
    "latest_date": "2026-10-19",
    "min_days_between": 2,
    "required_attendees": ["Maya", "Jordan"],
    "optional_attendees": [],
    "allowed_weekdays": [],
    "blocked_weekdays": ["FRI"],
    "earliest_start_time": None,
    "latest_end_time": None,
    "room": "Studio B",
    "unsupported_phrases": [],
}


def _request(**overrides) -> SchedulingRequest:
    return SchedulingRequest.model_validate({**EXAMPLE, **overrides})


def test_parses_the_example_request() -> None:
    request = _request()

    assert request.event_name == "Hip Hop"
    assert request.session_count == 3
    assert request.latest_date == date(2026, 10, 19)
    assert request.min_days_between == 2
    assert request.required_attendees == ["Maya", "Jordan"]
    assert request.blocked_weekdays == [Weekday.FRI]
    assert request.room == "Studio B"


def test_minimal_request_needs_only_the_event_name() -> None:
    request = SchedulingRequest.model_validate({"event_name": "Hip Hop"})

    assert request.session_count is None
    assert request.required_attendees == []
    assert request.day_time_constraints().is_unconstrained


def test_extra_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _request(duration_minutes=90)


def test_missing_event_name_is_rejected() -> None:
    payload = {key: value for key, value in EXAMPLE.items() if key != "event_name"}
    with pytest.raises(ValidationError, match="event_name"):
        SchedulingRequest.model_validate(payload)


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_event_name_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _request(event_name=value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_count", 0),
        ("session_count", 21),
        ("session_count", "three"),
        ("session_count", 2.5),
        ("session_count", True),
        ("min_days_between", -1),
        ("min_days_between", 31),
        ("latest_date", "Oct 20"),
        ("latest_date", "2026-02-30"),
        ("earliest_start_time", "6pm"),
        ("earliest_start_time", "25:00"),
        ("blocked_weekdays", ["Funday"]),
        ("blocked_weekdays", "FRI"),
        ("required_attendees", "Maya"),
        ("required_attendees", [42]),
        ("room", ""),
    ],
)
def test_wrong_types_and_out_of_range_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _request(**{field: value})


def test_weekday_spellings_are_normalized_without_guessing() -> None:
    request = _request(blocked_weekdays=["fri", "Saturday", "SUN"])

    assert request.blocked_weekdays == [Weekday.FRI, Weekday.SAT, Weekday.SUN]


def test_earliest_date_after_latest_date_is_rejected() -> None:
    with pytest.raises(ValidationError, match="earliest_date 2026-10-20 is after latest_date 2026-10-19"):
        _request(earliest_date="2026-10-20", latest_date="2026-10-19")


def test_earliest_time_after_latest_time_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Earliest start 22:00 must be before latest end 18:00"):
        _request(earliest_start_time="22:00", latest_end_time="18:00")


def test_latest_end_before_the_practice_window_opens_is_rejected() -> None:
    with pytest.raises(ValidationError, match="8:00 AM"):
        _request(latest_end_time="07:00")


def test_latest_end_of_midnight_is_allowed() -> None:
    assert _request(earliest_start_time="22:00", latest_end_time="00:00").latest_end_time == time(0, 0)


def test_day_both_allowed_and_blocked_is_rejected() -> None:
    with pytest.raises(ValidationError, match="both allowed and blocked: FRI"):
        _request(allowed_weekdays=["FRI", "SAT"], blocked_weekdays=["FRI"])


def test_person_both_required_and_optional_is_rejected() -> None:
    with pytest.raises(ValidationError, match="both required and optional: maya"):
        _request(required_attendees=["Maya"], optional_attendees=["maya"])


def test_names_are_trimmed_and_deduplicated_case_insensitively() -> None:
    request = _request(required_attendees=[" Maya ", "maya", "Jordan"])

    assert request.required_attendees == ["Maya", "Jordan"]


def test_day_time_constraints_carry_over() -> None:
    rules = _request(allowed_weekdays=["SAT"], blocked_weekdays=[], earliest_start_time="18:00").day_time_constraints()

    assert rules.allowed_weekdays == frozenset({Weekday.SAT})
    assert rules.earliest_start_local == time(18, 0)


def test_unsupported_phrases_are_kept_for_the_caller_to_reject() -> None:
    request = _request(unsupported_phrases=["evenings", "90-minute sessions"])

    assert request.unsupported_phrases == ["evenings", "90-minute sessions"]
