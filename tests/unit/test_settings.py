"""Unit tests for typed settings loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.governance import build_default_policy_profile
from app.core.settings import Settings


@pytest.mark.unit
def test_settings_load_valid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_NAME", "aptitude-test")

    settings = Settings(_env_file=None)
    default_policy = build_default_policy_profile()

    assert settings.database_url.endswith("/aptitude")
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.app_name == "aptitude-test"
    assert (
        settings.active_policy.discovery_default_statuses
        == default_policy.discovery_default_statuses
    )


@pytest.mark.unit
def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
