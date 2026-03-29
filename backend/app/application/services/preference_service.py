from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.domain.common.datetime_utils import ensure_utc
from app.domain.preferences.models import ParsedPreference
from app.infrastructure.db.models import User, UserParsedPreference, UserPreferenceInput
from app.infrastructure.integrations.llm.parser import PreferenceParser


@dataclass
class ParsePreviewResult:
    preference_input_id: UUID
    parsed_preference_id: UUID
    parsed_preference: ParsedPreference


class PreferenceService:
    def __init__(self, db: Session, parser: PreferenceParser) -> None:
        self.db = db
        self.parser = parser

    def parse_preview(self, user: User, raw_text: str) -> ParsePreviewResult:
        input_row = UserPreferenceInput(
            user_id=user.id,
            raw_text=raw_text,
            status="pending",
            parser_version=self.parser.version,
        )
        self.db.add(input_row)
        self.db.flush()

        raw_structured = self.parser.parse(raw_text=raw_text, timezone_name=user.timezone)
        try:
            parsed = ParsedPreference.model_validate(raw_structured)
        except ValidationError as exc:
            input_row.status = "failed"
            input_row.error_message = str(exc)
            self.db.commit()
            raise ValueError("Parser returned invalid structured output") from exc

        input_row.status = "parsed"
        input_row.parsed_at = ensure_utc(datetime.now(timezone.utc))
        parsed_row = UserParsedPreference(
            preference_input_id=input_row.id,
            user_id=user.id,
            schema_version=parsed.schema_version,
            timezone=parsed.timezone,
            constraints_json=parsed.model_dump(mode="json"),
        )
        self.db.add(parsed_row)
        self.db.commit()
        self.db.refresh(parsed_row)
        return ParsePreviewResult(
            preference_input_id=input_row.id,
            parsed_preference_id=parsed_row.id,
            parsed_preference=parsed,
        )
