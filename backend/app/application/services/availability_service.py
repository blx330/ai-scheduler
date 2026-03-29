from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.availability import AvailabilityCreate
from app.domain.common.datetime_utils import ensure_utc
from app.infrastructure.db.models import ManualAvailabilityInterval


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_interval(self, user_id: UUID, payload: AvailabilityCreate) -> ManualAvailabilityInterval:
        start_at = ensure_utc(payload.start_at)
        end_at = ensure_utc(payload.end_at)
        if end_at <= start_at:
            raise ValueError("Availability end must be after start")
        interval = ManualAvailabilityInterval(user_id=user_id, start_at=start_at, end_at=end_at)
        self.db.add(interval)
        self.db.commit()
        self.db.refresh(interval)
        return interval

    def list_intervals(self, user_id: UUID) -> list[ManualAvailabilityInterval]:
        statement = (
            select(ManualAvailabilityInterval)
            .where(ManualAvailabilityInterval.user_id == user_id)
            .order_by(ManualAvailabilityInterval.start_at.asc())
        )
        return list(self.db.scalars(statement))

    def delete_interval(self, user_id: UUID, interval_id: UUID) -> bool:
        interval = self.db.get(ManualAvailabilityInterval, interval_id)
        if interval is None or interval.user_id != user_id:
            return False
        self.db.delete(interval)
        self.db.commit()
        return True
