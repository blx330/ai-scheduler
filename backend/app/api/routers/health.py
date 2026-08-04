from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.api.schemas.common import HealthResponse
from app.infrastructure.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", demo_mode=bool(settings.admin_reset_token))
