"""Typed application settings loaded from environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration values."""

    database_url: str = Field(alias="DATABASE_URL")
    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_name: str = Field(default="aptitude-server", alias="APP_NAME")
    artifact_root_dir: str = Field(default="./.data/artifacts", alias="ARTIFACT_ROOT_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return memoized settings for the running process."""
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear cached settings; mainly used by tests and startup wiring."""
    get_settings.cache_clear()
