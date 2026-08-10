from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CurrentUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    email: str | None
    timezone: str
    role: str


class UserRoleUpdate(BaseModel):
    role: str
