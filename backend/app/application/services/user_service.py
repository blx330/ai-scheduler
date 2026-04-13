import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models import DanceEvent, DanceEventParticipant
from app.api.schemas.users import UserCreate, UserUpdate
from app.domain.preferences.models import CachedPracticePreference
from app.infrastructure.db.models import User
from app.infrastructure.integrations.llm.profile_preference_parser import UserProfilePreferenceParser

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreate, preference_parser: UserProfilePreferenceParser | None = None) -> User:
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

    def update_user(
        self,
        user_id,
        payload: UserUpdate,
        preference_parser: UserProfilePreferenceParser | None = None,
    ) -> User | None:
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
    payload: UserCreate | UserUpdate,
    preference_parser: UserProfilePreferenceParser | None,
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
    except Exception as exc:  # noqa: BLE001 - parser failures should not block profile saves
        logger.warning("Failed to parse cached practice preferences for user %s: %s", user.id, exc)
        user.preferred_practice_time_parsed = None
