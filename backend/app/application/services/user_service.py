import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.users import UserCreate, UserUpdate
from app.domain.common.datetime_utils import ensure_utc
from app.domain.preferences.models import CachedPracticePreference
from app.infrastructure.db.models import (
    CalendarConnection,
    DanceEvent,
    DanceEventParticipant,
    ManualAvailabilityInterval,
    User,
)
from app.infrastructure.integrations.llm.profile_preference_parser import UserProfilePreferenceParser

logger = logging.getLogger(__name__)

# How long a just-created, still-empty account stays re-claimable by a repeat signup
# with the same email. Long enough to cover a form retry, short enough that an
# established account is never overwritable.
INCOMPLETE_REGISTRATION_WINDOW = timedelta(minutes=15)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreate, preference_parser: UserProfilePreferenceParser | None = None) -> User:
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
            # store normalized: the lookup strips and lower-cases, so storing raw let
            # " Alice@x.com" and "alice@x.com" coexist while matching each other
            email=_normalize_email(payload.email),
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

    def _find_user_by_email(self, email: str | None) -> User | None:
        normalized = _normalize_email(email)
        if not normalized:
            return None
        return self.db.scalars(select(User).where(func.lower(User.email) == normalized)).first()

    def _is_registration_incomplete(self, user: User) -> bool:
        """May a repeat signup with this email re-claim the existing account?

        Only for a brand-new account that holds nothing. Treating every user without a
        Google connection as "incomplete" -- the normal path for this app -- meant
        anyone could overwrite any account's name, timezone and preferences, and learn
        its id, just by posting a known email address.
        """
        if ensure_utc(user.created_at) < datetime.now(UTC) - INCOMPLETE_REGISTRATION_WINDOW:
            return False

        connections = self.db.scalars(
            select(CalendarConnection)
            .where(CalendarConnection.user_id == user.id)
            .where(CalendarConnection.provider == "google")
        ).all()
        if any(connection.refresh_token or connection.access_token for connection in connections):
            return False

        has_data = self.db.scalars(
            select(ManualAvailabilityInterval.id).where(ManualAvailabilityInterval.user_id == user.id).limit(1)
        ).first()
        if has_data is not None:
            return False
        organizes = self.db.scalars(
            select(DanceEvent.id).where(DanceEvent.organizer_user_id == user.id).limit(1)
        ).first()
        if organizes is not None:
            return False
        participates = self.db.scalars(
            select(DanceEventParticipant.id).where(DanceEventParticipant.user_id == user.id).limit(1)
        ).first()
        return participates is None

    def _reset_incomplete_user(
        self,
        user: User,
        payload: UserCreate,
        preference_parser: UserProfilePreferenceParser | None = None,
    ) -> None:
        user.display_name = payload.display_name
        user.timezone = payload.timezone
        user.email = _normalize_email(payload.email)
        user.preferred_practice_time = payload.preferred_practice_time.value if payload.preferred_practice_time else None
        user.preferred_practice_time_raw = None
        user.preferred_practice_time_parsed = None
        _apply_user_practice_preferences(user, payload, preference_parser)

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


def _normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower() or None


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
    if not raw_text:
        # Clearing the free-text preference must not also clear a preset set in this
        # same request -- that made saving any preset a silent no-op, because the UI
        # sends both fields and the preset branch above runs first.
        user.preferred_practice_time_parsed = None
        return

    # Free-text supersedes a preset only when text was actually supplied.
    user.preferred_practice_time = None

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
