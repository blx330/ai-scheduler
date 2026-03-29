from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas.availability import AvailabilityCreate, AvailabilityRead
from app.api.schemas.common import MessageResponse
from app.application.services.availability_service import AvailabilityService
from app.application.services.user_service import UserService

router = APIRouter(prefix="/users/{user_id}/availability", tags=["availability"])


@router.post("", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
def create_availability(
    user_id: UUID,
    payload: AvailabilityCreate,
    db: Session = Depends(get_db),
) -> AvailabilityRead:
    user = UserService(db).get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        interval = AvailabilityService(db).create_interval(user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AvailabilityRead.model_validate(interval)


@router.get("", response_model=list[AvailabilityRead])
def list_availability(user_id: UUID, db: Session = Depends(get_db)) -> list[AvailabilityRead]:
    user = UserService(db).get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    intervals = AvailabilityService(db).list_intervals(user_id=user_id)
    return [AvailabilityRead.model_validate(interval) for interval in intervals]


@router.delete("/{interval_id}", response_model=MessageResponse)
def delete_availability(
    user_id: UUID,
    interval_id: UUID,
    db: Session = Depends(get_db),
) -> MessageResponse:
    deleted = AvailabilityService(db).delete_interval(user_id=user_id, interval_id=interval_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Availability interval not found")
    return MessageResponse(message="Availability interval deleted")
