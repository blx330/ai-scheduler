import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.application.services.demo_seed_service import reset_demo
from app.infrastructure.config import Settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-demo")
def reset_demo_endpoint(
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.admin_reset_token:
        # Only wired up once a deployment explicitly opts into being a public demo
        # (by setting ADMIN_RESET_TOKEN) -- absent that, this route doesn't exist.
        raise HTTPException(status_code=404, detail="Not found")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_reset_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    reset_demo(db)
    return {"status": "reset"}
