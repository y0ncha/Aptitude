"""Shared pytest fixtures for the service skeleton."""

from __future__ import annotations

import json
import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"
DEFAULT_AUTH_TOKENS = {
    "reader-token": ["read"],
    "publisher-token": ["read", "publish"],
    "admin-token": ["read", "publish", "admin"],
}


def _database_is_available(database_url: str) -> bool:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()


def _reset_database(database_url: str) -> None:
    """Drop and recreate the public schema for a clean integration DB."""
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO public"))
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Ensure tests never share cached settings state."""
    from app.core.settings import reset_settings_cache

    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture(autouse=True)
def default_auth_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide explicit auth tokens for all tests exercising HTTP routes."""
    monkeypatch.setenv("AUTH_TOKENS_JSON", json.dumps(DEFAULT_AUTH_TOKENS))


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    """Return a PostgreSQL URL used by integration tests."""
    return os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def require_integration_database(integration_database_url: str) -> str:
    """Skip integration tests when PostgreSQL is not reachable."""
    if not _database_is_available(integration_database_url):
        pytest.skip(
            "PostgreSQL is not reachable for integration tests. "
            "Run `make db-up` and set TEST_DATABASE_URL if needed.",
        )
    return integration_database_url


@pytest.fixture
def clean_integration_database(require_integration_database: str) -> str:
    """Provide a blank Postgres schema for integration tests."""
    _reset_database(require_integration_database)
    return require_integration_database
