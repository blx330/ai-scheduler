
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@db:5432/scheduler"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "dance-practice-scheduler"
    api_prefix: str = "/api/v1"
    database_url: str = DEFAULT_DATABASE_URL
    frontend_url: str = "http://localhost:8000"
    oauth_state_secret: str | None = Field(default=None, validation_alias="OAUTH_STATE_SECRET")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.6-flash", validation_alias="GEMINI_MODEL")
    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = Field(default=None, validation_alias="GOOGLE_REDIRECT_URI")
    # Login (who is this) is a separate OAuth flow/redirect URI from calendar connect
    # (sync this person's busy time) -- same Google client id/secret, different scopes
    # and a different Google Cloud Console redirect URI entry.
    google_login_redirect_uri: str | None = Field(default=None, validation_alias="GOOGLE_LOGIN_REDIRECT_URI")
    session_secret: str | None = Field(default=None, validation_alias="SESSION_SECRET")
    session_cookie_max_age_days: int = Field(default=30, validation_alias="SESSION_COOKIE_MAX_AGE_DAYS")
    # Emails that always get (or are upgraded to) the organizer role on login, and may
    # log in even before any matching users row exists -- bootstraps the first
    # organizer, since nobody starts out able to promote anyone.
    admin_emails: list[str] = Field(default_factory=list, validation_alias="ADMIN_EMAILS")
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 15
    auto_sync_horizon_days: int = 30
    # Gates POST /api/v1/admin/reset-demo. Left unset, that endpoint 404s -- it only
    # exists at all once a deployment explicitly opts into being a public shared demo.
    admin_reset_token: str = Field(default="", validation_alias="ADMIN_RESET_TOKEN")

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_comma_separated_admin_emails(cls, value):
        # A plain .env value ("a@x.com,b@y.com") isn't valid JSON, which is what
        # pydantic-settings expects by default for a list field read from the
        # environment -- split it by hand instead of asking users to write JSON in .env.
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def default_blank_database_url(cls, value):
        # A blank DATABASE_URL in .env overrides the field default with "", which
        # only surfaces later as an opaque "Could not parse SQLAlchemy URL". Treat
        # blank as unset so the documented compose default still applies.
        if value is None or (isinstance(value, str) and not value.strip()):
            import logging

            logging.getLogger(__name__).warning(
                "STARTUP WARNING: DATABASE_URL is blank; falling back to %s. "
                "Set DATABASE_URL in your .env file if you are not using the Docker Postgres service.",
                DEFAULT_DATABASE_URL,
            )
            return DEFAULT_DATABASE_URL
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def warn_missing_google_config(self) -> "Settings":
        import logging

        _cfg_logger = logging.getLogger(__name__)
        missing = []
        if not self.oauth_state_secret:
            missing.append("OAUTH_STATE_SECRET")
        if not self.google_client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not self.google_client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not self.google_redirect_uri:
            missing.append("GOOGLE_REDIRECT_URI")
        if missing:
            _cfg_logger.warning(
                "STARTUP WARNING: The following env vars are missing and Google "
                "Calendar integration will not work: %s. "
                "Set them in your .env file or hosting platform env vars.",
                missing,
            )

        missing_login = []
        if not self.session_secret:
            missing_login.append("SESSION_SECRET")
        if not self.google_client_id:
            missing_login.append("GOOGLE_CLIENT_ID")
        if not self.google_client_secret:
            missing_login.append("GOOGLE_CLIENT_SECRET")
        if not self.google_login_redirect_uri:
            missing_login.append("GOOGLE_LOGIN_REDIRECT_URI")
        if missing_login:
            _cfg_logger.warning(
                "STARTUP WARNING: The following env vars are missing and sign-in "
                "will not work: %s. Set them in your .env file or hosting platform env vars.",
                missing_login,
            )
        return self
