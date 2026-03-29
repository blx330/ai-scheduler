from uuid import UUID

from pydantic import BaseModel

from app.domain.preferences.models import ParsedPreference


class ParsePreviewRequest(BaseModel):
    user_id: UUID
    raw_text: str


class ParsePreviewResponse(BaseModel):
    preference_input_id: UUID
    parsed_preference_id: UUID
    parsed_preference: ParsedPreference
