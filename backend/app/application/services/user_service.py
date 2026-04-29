import logging
from typing import Optional, Union

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models import DanceEvent, DanceEventParticipant
from app.api.schemas.users import UserCreate, UserUpdate
from app.domain.preferences.models import CachedPracticePreference
from app.infrastructure.db.models import CalendarConnection, User
from app.infrastructure.integrations.llm.profile_preference_parser import UserProfilePreferenceParser

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreate, preference_parser: Optional[UserProfilePreferenceParser] = None) -> User:
        existing_by_email = self._find_user_by_email(payload.email)
        if existing_by_email is not None:
            if self._is_registration_incomplete(existing_by_email):
                self._reset_incomplete_user(existing_by_email, payload, preference_parser)
                self.db.add(existing_by_email)
                self.db.commit()
                self.db.refresh(existing_by_email)
                return existing_by_email
            raise ValueError("A user with that email already exists")

        user = User(
            display_name=payload.display_name,
            timezone=payload.timezone,
            email=payload.email,
            preferred_practice_time=payload.preferred_practice_time.value if payload.preferred_practice_time else None,
        )
        _apply_user_practice_preferences(user, payload, preference_parser)
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

    def _find_user_by_email(self, email: Optional[str]) -> Optional[User]:
        if not email:
            return None
        normalized = email.strip()
        if not normalized:
            return None
        return self.db.scalars(select(User).where(func.lower(User.email) == normalized.lower())).first()

    def _is_registration_incomplete(self, user: User) -> bool:
        connections = self.db.scalars(
            select(CalendarConnection)
            .where(CalendarConnection.user_id == user.id)
            .where(CalendarConnection.provider == "google")
        ).all()
        if not connections:
            return True
        return not any(connection.refresh_token or connection.access_token for connection in connections)

    def _reset_incomplete_user(
        self,
        user: User,
        payload: UserCreate,
        preference_parser: Optional[UserProfilePreferenceParser] = None,
    ) -> None:
        user.display_name = payload.display_name
        user.timezone = payload.timezone
        user.email = payload.email
        user.preferred_practice_time = payload.preferred_practice_time.value if payload.preferred_practice_time else None
        user.preferred_practice_time_raw = None
        user.preferred_practice_time_parsed = None
        _apply_user_practice_preferences(user, payload, preference_parser)

    def update_user(
        self,
        user_id,
        payload: UserUpdate,
        preference_parser: Optional[UserProfilePreferenceParser] = None,
    ) -> Optional[User]:
        user = self.db.get(User, user_id)
        if user is None:
            return None

        _apply_user_practice_preferences(user, payload, preference_parser)

        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("A user with that email already exists") from exc
        self.db.refresh(user)
        return user

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


def _apply_user_practice_preferences(
    user: User,
    payload: Union[UserCreate, UserUpdate],
    preference_parser: Optional[UserProfilePreferenceParser],
) -> None:
    if "preferred_practice_time" in payload.model_fields_set:
        user.preferred_practice_time = payload.preferred_practice_time.value if payload.preferred_practice_time else None
        if payload.preferred_practice_time is None:
            user.preferred_practice_time_parsed = None

    if "preferred_practice_time_raw" not in payload.model_fields_set:
        return

    raw_text = (payload.preferred_practice_time_raw or "").strip()
    user.preferred_practice_time_raw = raw_text or None
    user.preferred_practice_time = None
    if not raw_text:
        user.preferred_practice_time_parsed = None
        return

    if preference_parser is None:
        user.preferred_practice_time_parsed = None
        return

    try:
        parsed_payload = preference_parser.parse(raw_text=raw_text, timezone_name=user.timezone)
        cached_preference = CachedPracticePreference.model_validate(parsed_payload)
        user.preferred_practice_time_parsed = (
            cached_preference.model_dump(mode="json") if cached_preference.is_useful() else None
        )
    except Exception as exc:  # noqa: BLE001 - parser boundary is untrusted, surface full error to caller
        logger.warning("Failed to parse cached practice preferences for user %s: %s", user.id, exc)
        raise ValueError(str(exc)) from exc
