from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models import DanceEvent, DanceEventParticipant
from app.api.schemas.users import UserCreate
from app.infrastructure.db.models import User


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreate) -> User:
        user = User(display_name=payload.display_name, timezone=payload.timezone, email=payload.email)
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("A user with that email already exists") from exc
        self.db.refresh(user)
        return user

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.created_at.asc())))

    def get_user(self, user_id):
        return self.db.get(User, user_id)

    def delete_user(self, user_id) -> bool:
        user = self.db.get(User, user_id)
        if user is None:
            return False

        organizes_event = self.db.scalars(
            select(DanceEvent.id).where(DanceEvent.organizer_user_id == user_id).limit(1)
        ).first()
        if organizes_event is not None:
            raise ValueError("Reassign or delete this person's dances before removing them from the app")

        participates_in_dance = self.db.scalars(
            select(DanceEventParticipant.id).where(DanceEventParticipant.user_id == user_id).limit(1)
        ).first()
        if participates_in_dance is not None:
            raise ValueError("Remove this person from all dances before deleting them from the app")

        self.db.delete(user)
        self.db.commit()
        return True
