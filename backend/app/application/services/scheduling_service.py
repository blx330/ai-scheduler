from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import time
from datetime import timezone
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas.schedule import ScheduleRequestCreate
from app.domain.availability.interval_ops import build_effective_availability
from app.domain.common.datetime_utils import ensure_utc
from app.domain.common.enums import Weekday
from app.domain.preferences.models import ParsedPreference
from app.domain.scheduling.engine import schedule_meeting
from app.domain.scheduling.models import (
    ParticipantContext,
    ScheduleInput,
    ScheduleParticipantStatus,
    ScheduleResult,
)
from app.infrastructure.db.models import (
    CalendarBusyInterval,
    CalendarConnection,
    ManualAvailabilityInterval,
    ScheduleRequest,
    ScheduleRequestParticipant,
    ScheduleRun,
    ScheduleRunResult,
    User,
    UserParsedPreference,
)


@dataclass
class ScheduleRunResponse:
    id: UUID
    schedule_request_id: UUID
    status: str
    results: list[ScheduleResult]


class SchedulingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_schedule_request(self, payload: ScheduleRequestCreate) -> ScheduleRequest:
        organizer = self.db.get(User, payload.organizer_user_id)
        if organizer is None:
            raise ValueError("Organizer not found")

        normalized_roles: dict[UUID, str] = {}
        for participant in payload.participants:
            if participant.role not in {"required", "optional"}:
                raise ValueError("Participant role must be 'required' or 'optional'")
            current_role = normalized_roles.get(participant.user_id)
            if current_role == "required" or participant.role == "required":
                normalized_roles[participant.user_id] = "required"
            else:
                normalized_roles[participant.user_id] = participant.role
        normalized_roles[payload.organizer_user_id] = "required"
        participant_payloads = [
            {"user_id": user_id, "role": role}
            for user_id, role in normalized_roles.items()
        ]
        user_ids = set(normalized_roles)

        if payload.duration_minutes <= 0:
            raise ValueError("Duration minutes must be positive")
        if payload.slot_step_minutes <= 0:
            raise ValueError("Slot step minutes must be positive")
        if payload.horizon_end <= payload.horizon_start:
            raise ValueError("Horizon end must be after horizon start")

        existing_users = set(
            self.db.scalars(select(User.id).where(User.id.in_(user_ids)))
        )
        if existing_users != user_ids:
            raise ValueError("One or more participants do not exist")

        request_row = ScheduleRequest(
            title=payload.title,
            organizer_user_id=payload.organizer_user_id,
            duration_minutes=payload.duration_minutes,
            horizon_start=ensure_utc(payload.horizon_start),
            horizon_end=ensure_utc(payload.horizon_end),
            slot_step_minutes=payload.slot_step_minutes,
            daily_window_start_local=payload.daily_window_start_local,
            daily_window_end_local=payload.daily_window_end_local,
            preferred_weekdays_json=[weekday.value for weekday in payload.preferred_weekdays],
            preferred_time_range_start_local=payload.preferred_time_range_start_local,
            preferred_time_range_end_local=payload.preferred_time_range_end_local,
            status="draft",
        )
        self.db.add(request_row)
        self.db.flush()

        for participant in participant_payloads:
            self.db.add(
                ScheduleRequestParticipant(
                    schedule_request_id=request_row.id,
                    user_id=participant["user_id"],
                    role=participant["role"],
                )
            )

        self.db.commit()
        self.db.refresh(request_row)
        return request_row

    def list_schedule_requests(self) -> list[ScheduleRequest]:
        statement = (
            select(ScheduleRequest)
            .order_by(ScheduleRequest.created_at.desc())
            .options(selectinload(ScheduleRequest.participants))
        )
        return list(self.db.scalars(statement))

    def get_schedule_request(self, schedule_request_id: UUID) -> Optional[ScheduleRequest]:
        statement = (
            select(ScheduleRequest)
            .where(ScheduleRequest.id == schedule_request_id)
            .options(selectinload(ScheduleRequest.participants))
        )
        return self.db.scalars(statement).one_or_none()

    def run_schedule_request(self, schedule_request_id: UUID) -> Optional[ScheduleRunResponse]:
        schedule_request = self.get_schedule_request(schedule_request_id)
        if schedule_request is None:
            return None

        participants = schedule_request.participants
        user_ids = [participant.user_id for participant in participants]
        users = {
            user.id: user
            for user in self.db.scalars(select(User).where(User.id.in_(user_ids)))
        }
        connected_user_ids = {
            row.user_id
            for row in self.db.scalars(
                select(CalendarConnection)
                .where(CalendarConnection.user_id.in_(user_ids))
                .where(CalendarConnection.provider == "google")
            )
            if row.refresh_token or row.access_token
        }

        manual_by_user = defaultdict(list)
        for interval in self.db.scalars(
            select(ManualAvailabilityInterval)
            .where(ManualAvailabilityInterval.user_id.in_(user_ids))
            .where(ManualAvailabilityInterval.end_at > schedule_request.horizon_start)
            .where(ManualAvailabilityInterval.start_at < schedule_request.horizon_end)
            .order_by(ManualAvailabilityInterval.start_at.asc())
        ):
            manual_by_user[interval.user_id].append(interval)

        busy_by_user = defaultdict(list)
        for interval in self.db.scalars(
            select(CalendarBusyInterval)
            .where(CalendarBusyInterval.user_id.in_(user_ids))
            .where(CalendarBusyInterval.end_at > schedule_request.horizon_start)
            .where(CalendarBusyInterval.start_at < schedule_request.horizon_end)
            .order_by(CalendarBusyInterval.start_at.asc())
        ):
            busy_by_user[interval.user_id].append(interval)

        preference_rows = list(
            self.db.scalars(
                select(UserParsedPreference)
                .where(UserParsedPreference.user_id.in_(user_ids))
                .order_by(UserParsedPreference.created_at.desc())
            )
        )
        preferences_by_user: dict[UUID, ParsedPreference] = {}
        for row in preference_rows:
            if row.user_id not in preferences_by_user:
                preferences_by_user[row.user_id] = ParsedPreference.model_validate(row.constraints_json)

        participant_contexts: list[ParticipantContext] = []
        for participant in participants:
            user = users[participant.user_id]
            manual_intervals = manual_by_user.get(participant.user_id, [])
            if not manual_intervals and participant.user_id in connected_user_ids:
                manual_intervals = [
                    SimpleNamespace(
                        start_at=schedule_request.horizon_start,
                        end_at=schedule_request.horizon_end,
                    )
                ]
            effective = build_effective_availability(
                manual_intervals=manual_intervals,
                busy_intervals=busy_by_user.get(participant.user_id, []),
            )
            request_preference = None
            if participant.user_id == schedule_request.organizer_user_id:
                request_preference = _build_request_preference(
                    organizer_timezone=user.timezone,
                    preferred_weekdays=schedule_request.preferred_weekdays_json,
                    preferred_time_range_start_local=schedule_request.preferred_time_range_start_local,
                    preferred_time_range_end_local=schedule_request.preferred_time_range_end_local,
                )
            participant_contexts.append(
                ParticipantContext(
                    user_id=participant.user_id,
                    role=participant.role,
                    timezone=user.timezone,
                    effective_availability=effective,
                    preference=request_preference or preferences_by_user.get(participant.user_id),
                )
            )

        schedule_input = ScheduleInput(
            schedule_request_id=schedule_request.id,
            title=schedule_request.title,
            organizer_timezone=users[schedule_request.organizer_user_id].timezone,
            duration_minutes=schedule_request.duration_minutes,
            horizon_start=ensure_utc(schedule_request.horizon_start),
            horizon_end=ensure_utc(schedule_request.horizon_end),
            slot_step_minutes=schedule_request.slot_step_minutes,
            daily_window_start_local=schedule_request.daily_window_start_local,
            daily_window_end_local=schedule_request.daily_window_end_local,
            participants=participant_contexts,
        )
        ranked_slots = schedule_meeting(schedule_input)

        run_row = ScheduleRun(
            schedule_request_id=schedule_request.id,
            status="completed" if ranked_slots else "no_results",
            engine_version="pass2-v1",
        )
        self.db.add(run_row)
        self.db.flush()

        for slot in ranked_slots:
            self.db.add(
                ScheduleRunResult(
                    schedule_run_id=run_row.id,
                    rank=slot.rank,
                    start_at=slot.start_at,
                    end_at=slot.end_at,
                    total_score=slot.total_score,
                    score_breakdown_json=slot.score_breakdown,
                    explanation=slot.explanation,
                    required_participants_satisfied=slot.required_participants_satisfied,
                    optional_available_count=slot.optional_available_count,
                    participant_statuses_json=[status.model_dump(mode="json") for status in slot.participant_statuses],
                )
            )

        self.db.commit()
        return ScheduleRunResponse(
            id=run_row.id,
            schedule_request_id=run_row.schedule_request_id,
            status=run_row.status,
            results=ranked_slots,
        )

    def get_schedule_run(self, schedule_run_id: UUID) -> Optional[ScheduleRunResponse]:
        statement = (
            select(ScheduleRun)
            .where(ScheduleRun.id == schedule_run_id)
            .options(selectinload(ScheduleRun.results))
        )
        run = self.db.scalars(statement).one_or_none()
        if run is None:
            return None
        results = [
            ScheduleResult(
                rank=result.rank,
                start_at=result.start_at,
                end_at=result.end_at,
                total_score=float(result.total_score),
                score_breakdown={key: float(value) for key, value in result.score_breakdown_json.items()},
                explanation=result.explanation,
                required_participants_satisfied=result.required_participants_satisfied,
                optional_available_count=result.optional_available_count,
                participant_statuses=[
                    ScheduleParticipantStatus(**item) for item in result.participant_statuses_json
                ],
            )
            for result in sorted(run.results, key=lambda item: item.rank)
        ]
        return ScheduleRunResponse(
            id=run.id,
            schedule_request_id=run.schedule_request_id,
            status=run.status,
            results=results,
        )


def _build_request_preference(
    organizer_timezone: str,
    preferred_weekdays: list[str],
    preferred_time_range_start_local: Optional[time],
    preferred_time_range_end_local: Optional[time],
) -> Optional[ParsedPreference]:
    normalized_weekdays = [Weekday(value) for value in preferred_weekdays if value]
    preferred_time_ranges = []
    if preferred_time_range_start_local is not None and preferred_time_range_end_local is not None:
        preferred_time_ranges.append(
            {
                "start_local": preferred_time_range_start_local.strftime("%H:%M"),
                "end_local": preferred_time_range_end_local.strftime("%H:%M"),
                "weight": 1.0,
            }
        )
    if not normalized_weekdays and not preferred_time_ranges:
        return None
    return ParsedPreference.model_validate(
        {
            "schema_version": "1.0",
            "timezone": organizer_timezone,
            "preferred_weekdays": [weekday.value for weekday in normalized_weekdays],
            "disallowed_weekdays": [],
            "preferred_time_ranges": preferred_time_ranges,
            "disallowed_time_ranges": [],
            "notes": "Request-level structured preference",
        }
    )
