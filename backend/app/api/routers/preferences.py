from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_preference_parser
from app.api.schemas.preferences import ParsePreviewRequest, ParsePreviewResponse
from app.application.services.preference_service import PreferenceService
from app.application.services.user_service import UserService
from app.infrastructure.integrations.llm.parser import PreferenceParser

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.post("/parse-preview", response_model=ParsePreviewResponse, status_code=status.HTTP_201_CREATED)
def parse_preview(
    payload: ParsePreviewRequest,
    db: Session = Depends(get_db),
    parser: PreferenceParser = Depends(get_preference_parser),
) -> ParsePreviewResponse:
    user = UserService(db).get_user(payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        parsed = PreferenceService(db, parser).parse_preview(user=user, raw_text=payload.raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParsePreviewResponse(
        preference_input_id=parsed.preference_input_id,
        parsed_preference_id=parsed.parsed_preference_id,
        parsed_preference=parsed.parsed_preference,
    )
