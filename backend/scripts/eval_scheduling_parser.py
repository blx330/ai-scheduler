"""Eval for plain-English scheduling requests.

Each case in evals/scheduling_requests.jsonl is run through the real
SchedulingRequestService against a fixed, freshly seeded roster, with "now"
pinned to Friday 2026-09-25 12:30 in New York. Two things are scored:

- parse accuracy: the parser's SchedulingRequest vs the labelled one, per field
  and as an exact match over all fields
- outcome accuracy: whether the whole pipeline correctly accepted or rejected
  the request (rejections include unknown names, infeasible dates, unsupported
  phrases and model output that fails validation)

Run live against Gemini (needs GEMINI_API_KEY; sends the eval texts and the
fixed synthetic roster below to Google):

    python -m scripts.eval_scheduling_parser [--model gemini-...] [--output evals/results/latest.json]

Gemini's free tier allows 5 requests/minute and 20/day per model, fewer than the
23 cases: pass --delay 13 to stay under the per-minute limit. If the daily quota
runs out, the partial report is still written to --output; continue it the next
day with --resume <that file> (or use a key with billing enabled).

`--oracle` replays the labels instead of calling a model; it must score 100%,
which is what tests/unit/test_scheduling_request_eval.py checks.
"""

from __future__ import annotations

import argparse
import json
import sys
import time as time_module
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.services.scheduling_request_service import SchedulingRequestRejected, SchedulingRequestService
from app.domain.scheduling.requests import SchedulingRequest
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import DanceEvent, DanceEventParticipant, Room, User
from app.infrastructure.integrations.llm.scheduling_request_parser import (
    GeminiSchedulingRequestParser,
    ParseContext,
    SchedulingRequestParseError,
    SchedulingRequestParser,
    SchedulingRequestUpstreamError,
    validate_model_output,
)

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "scheduling_requests.jsonl"
# Friday 2026-09-25, 12:30 in America/New_York.
NOW = datetime(2026, 9, 25, 16, 30, tzinfo=UTC)
ORGANIZER_TZ = "America/New_York"
MEMBERS = ["Maya Chen", "Jordan Lee", "Sam Park", "Priya Patel", "Alex Rivera", "Alex Kim", "Taylor Nguyen"]
ROOMS = ["Studio A", "Studio B", "Main Hall"]
# dance -> (saved total sessions, the one saved required dancer)
EVENTS = {
    "Hip Hop": (1, "Sam Park"),
    "K-Pop Cover": (2, "Priya Patel"),
    "Contemporary Duet": (2, "Maya Chen"),
    "Ballet Basics": (2, "Taylor Nguyen"),
}
FIELDS = list(SchedulingRequest.model_fields)
# Provider outages are retried with exponential backoff, then the run stops (never
# scoring an outage as a parse miss); finished cases are kept for --resume.
UPSTREAM_ATTEMPTS = 5


@dataclass(frozen=True)
class EvalCase:
    id: str
    text: str
    expected: dict[str, Any]
    expected_outcome: str


@dataclass
class CaseResult:
    id: str
    text: str
    expected_outcome: str
    actual_outcome: str
    outcome_correct: bool
    exact_match: bool
    wrong_fields: list[str]
    parse_error: str | None
    rejection_errors: list[str]
    parsed: dict[str, Any] | None


@dataclass
class EvalReport:
    parser: str
    results: list[CaseResult]
    field_accuracy: dict[str, float] = field(default_factory=dict)
    exact_match_accuracy: float = 0.0
    outcome_accuracy: float = 0.0
    # True when the provider stopped answering mid-run (e.g. daily quota). The
    # finished results are kept so --resume can complete the run later.
    incomplete: bool = False
    stopped_reason: str | None = None


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return [EvalCase(**json.loads(line)) for line in lines]


class OracleParser:
    """Returns each case's label, run through the same validation as model output."""

    version = "oracle"

    def __init__(self, cases: list[EvalCase]) -> None:
        self._by_text = {case.text: case.expected for case in cases}

    def parse(self, text: str, context: ParseContext) -> SchedulingRequest:
        return validate_model_output(json.dumps(self._by_text[text]))


class _RecordingParser:
    def __init__(self, inner: SchedulingRequestParser, sleep: Callable[[float], None]) -> None:
        self.inner = inner
        self.sleep = sleep
        self.output: SchedulingRequest | None = None
        self.error: SchedulingRequestParseError | None = None

    def parse(self, text: str, context: ParseContext) -> SchedulingRequest:
        for attempt in range(1, UPSTREAM_ATTEMPTS + 1):
            try:
                self.output = self.inner.parse(text, context)
                return self.output
            except SchedulingRequestParseError as exc:
                self.error = exc
                raise
            except SchedulingRequestUpstreamError:
                if attempt == UPSTREAM_ATTEMPTS:
                    raise
                self.sleep(2.0**attempt)
        raise AssertionError("unreachable")


def run_eval(
    cases: list[EvalCase],
    parser: SchedulingRequestParser,
    sleep: Callable[[float], None] = time_module.sleep,
    delay_seconds: float = 0.0,
    previous: list[CaseResult] | None = None,
) -> EvalReport:
    """Run every case not already in `previous`. Accuracy covers finished cases only."""
    done = {result.id: result for result in previous or []}
    report = EvalReport(parser=parser.version, results=[])
    calls = 0
    for case in cases:
        if case.id in done:
            report.results.append(done[case.id])
            continue
        if calls and delay_seconds:
            sleep(delay_seconds)
        calls += 1
        try:
            report.results.append(_run_case(case, parser, sleep))
        except SchedulingRequestUpstreamError as exc:
            report.incomplete = True
            report.stopped_reason = f"stopped at case {case.id!r}: {str(exc)[:200]}"
            break

    by_id = {case.id: case for case in cases}
    scored = [result for result in report.results if _expected_request(by_id[result.id])]
    for name in FIELDS:
        correct = sum(1 for result in scored if name not in result.wrong_fields)
        report.field_accuracy[name] = correct / len(scored) if scored else 0.0
    finished = report.results
    if finished:
        report.exact_match_accuracy = sum(result.exact_match for result in finished) / len(finished)
        report.outcome_accuracy = sum(result.outcome_correct for result in finished) / len(finished)
    return report


def _run_case(case: EvalCase, parser: SchedulingRequestParser, sleep: Callable[[float], None]) -> CaseResult:
    recorder = _RecordingParser(parser, sleep)
    rejection_errors: list[str] = []
    with _seeded_session() as db:
        try:
            SchedulingRequestService(db, recorder, now=lambda: NOW).parse(case.text)
            outcome = "accepted"
        except SchedulingRequestRejected as exc:
            outcome, rejection_errors = "rejected", exc.errors
        except SchedulingRequestParseError:
            outcome = "rejected"

    expected = _expected_request(case)
    parsed = recorder.output
    if expected is None:
        # The label itself is invalid: the right answer is output that fails validation.
        wrong_fields = [] if parsed is None else ["(should have failed validation)"]
    elif parsed is None:
        wrong_fields = list(FIELDS)
    else:
        wrong_fields = [
            name for name in FIELDS if _normalize(name, getattr(parsed, name)) != _normalize(name, getattr(expected, name))
        ]
    return CaseResult(
        id=case.id,
        text=case.text,
        expected_outcome=case.expected_outcome,
        actual_outcome=outcome,
        outcome_correct=outcome == case.expected_outcome,
        exact_match=not wrong_fields,
        wrong_fields=wrong_fields,
        parse_error=str(recorder.error) if recorder.error else None,
        rejection_errors=rejection_errors,
        parsed=parsed.model_dump(mode="json") if parsed else None,
    )


def _expected_request(case: EvalCase) -> SchedulingRequest | None:
    try:
        return SchedulingRequest.model_validate(case.expected)
    except ValueError:
        return None


def _normalize(name: str, value: Any) -> Any:
    if name == "unsupported_phrases":
        # Wording is free-form; what matters is whether anything was flagged.
        return bool(value)
    if name in {"required_attendees", "optional_attendees"}:
        return sorted(item.casefold() for item in value)
    if name in {"event_name", "room"} and value is not None:
        return value.casefold()
    return value


def _seeded_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    organizer = User(display_name="Coach Kim", email="coach@eval.test", timezone=ORGANIZER_TZ, role="organizer")
    members = {
        name: User(display_name=name, email=f"member{index}@eval.test", timezone=ORGANIZER_TZ)
        for index, name in enumerate(MEMBERS)
    }
    db.add_all([organizer, *members.values(), *(Room(name=name, is_active=True) for name in ROOMS)])
    db.flush()
    for name, (sessions, required) in EVENTS.items():
        event = DanceEvent(
            name=name,
            organizer_user_id=organizer.id,
            duration_minutes=60,
            min_days_apart=0,
            latest_schedule_at=datetime(2026, 12, 1, 5, 0, tzinfo=UTC),  # Dec 1 00:00 New York
            required_session_count=sessions,
        )
        db.add(event)
        db.flush()
        db.add(DanceEventParticipant(dance_event_id=event.id, user_id=members[required].id, role="required"))
    db.commit()
    return db


def format_report(report: EvalReport) -> str:
    n = len(report.results)
    lines = [f"Parser: {report.parser}  ({n} cases)"]
    if report.incomplete:
        lines.append(f"INCOMPLETE ({report.stopped_reason}); accuracy below covers finished cases only.")
        lines.append("Re-run with --resume <output file> once the provider is available.")
    lines += [
        f"Outcome accuracy (accept/reject): {report.outcome_accuracy:.1%} "
        f"({sum(r.outcome_correct for r in report.results)}/{n})",
        f"Exact-match parse accuracy:       {report.exact_match_accuracy:.1%} "
        f"({sum(r.exact_match for r in report.results)}/{n})",
        "Per-field accuracy:",
    ]
    lines += [f"  {name:<22} {value:.1%}" for name, value in report.field_accuracy.items()]
    misses = [r for r in report.results if not (r.exact_match and r.outcome_correct)]
    if misses:
        lines.append("Misses:")
        for result in misses:
            lines.append(
                f"  - {result.id}: outcome {result.actual_outcome} (expected {result.expected_outcome}); "
                f"wrong fields: {', '.join(result.wrong_fields) or 'none'}"
            )
            if result.parse_error:
                lines.append(f"      parse error: {result.parse_error}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from app.infrastructure.config import Settings

    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--model", default=None, help="Gemini model (default: GEMINI_MODEL setting)")
    args.add_argument("--oracle", action="store_true", help="replay labels instead of calling a model")
    args.add_argument("--output", type=Path, default=None, help="write the full JSON report here")
    args.add_argument("--delay", type=float, default=0.0, help="seconds to wait between cases (free tier: 13)")
    args.add_argument("--ids", default=None, help="comma-separated case ids to run (default: all)")
    args.add_argument("--resume", type=Path, default=None, help="JSON report from an incomplete run to continue")
    options = args.parse_args(argv)

    cases = load_cases()
    if options.ids:
        wanted = set(options.ids.split(","))
        unknown = wanted - {case.id for case in cases}
        if unknown:
            print(f"Unknown case ids: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        cases = [case for case in cases if case.id in wanted]
    if options.oracle:
        parser: SchedulingRequestParser = OracleParser(cases)
    else:
        settings = Settings()
        if not settings.gemini_api_key:
            print("GEMINI_API_KEY is not set; use --oracle for an offline run.", file=sys.stderr)
            return 2
        model = options.model or settings.gemini_model
        parser = GeminiSchedulingRequestParser(api_key=settings.gemini_api_key, model=model)
        parser.version = f"{parser.version} ({model})"

    previous = None
    if options.resume:
        previous = [CaseResult(**item) for item in json.loads(options.resume.read_text())["results"]]
    report = run_eval(
        cases, parser, delay_seconds=0.0 if options.oracle else options.delay, previous=previous
    )
    print(format_report(report))
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(json.dumps(asdict(report), indent=2, default=str) + "\n")
    return 1 if report.incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
