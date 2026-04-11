from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "scheduler-pass2"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/scheduler"
    parser_mode: str = "stub"
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8000"
    oauth_state_secret: str = "change-me-for-demo"
    feather_api_key: str = ""
    groq_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/google/oauth/callback"
