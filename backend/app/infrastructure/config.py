from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "dance-practice-scheduler"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/scheduler"
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8000"
    oauth_state_secret: Optional[str] = Field(default=None, validation_alias="OAUTH_STATE_SECRET")
    groq_api_key: str = ""
    google_client_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, validation_alias="GOOGLE_REDIRECT_URI")

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
        return self
