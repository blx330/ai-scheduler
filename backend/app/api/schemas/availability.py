from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class AvailabilityCreate(BaseModel):
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include timezone information")
        return value


class AvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    start_at: datetime
    end_at: datetime
