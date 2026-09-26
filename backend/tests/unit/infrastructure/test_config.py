"""ADMIN_EMAILS is a plain comma-separated value in .env, not JSON. pydantic-settings
decodes list fields as JSON before validators run, so without NoDecode a blank
`ADMIN_EMAILS=` (what .env.example ships) crashed startup."""

from app.infrastructure.config import Settings


def _settings(**env: str) -> Settings:
    # _env_file=None keeps a developer's real .env out of the test.
    return Settings(_env_file=None, database_url="sqlite:///ignored.db", **env)


def test_blank_admin_emails_means_no_admins(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "")
    assert _settings().admin_emails == []


def test_admin_emails_are_split_trimmed_and_lowercased(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", " Captain@Example.com ,member@example.com,, ")
    assert _settings().admin_emails == ["captain@example.com", "member@example.com"]


def test_admin_emails_default_is_empty(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    assert _settings().admin_emails == []
