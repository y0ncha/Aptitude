"""Database engine, session lifecycle, and readiness checks."""

from __future__ import annotations

from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.ports import DatabaseReadinessPort

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
_ENGINE_LOCK = Lock()


def init_engine(database_url: str) -> None:
    """Initialize the shared SQLAlchemy engine/session factory."""
    global _ENGINE, _SESSION_FACTORY

    with _ENGINE_LOCK:
        if _ENGINE is not None and str(_ENGINE.url) == database_url:
            return

        if _ENGINE is not None:
            _ENGINE.dispose()

        _ENGINE = create_engine(database_url, pool_pre_ping=True)
        _SESSION_FACTORY = sessionmaker(
            bind=_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )


def dispose_engine() -> None:
    """Dispose the shared SQLAlchemy engine."""
    global _ENGINE, _SESSION_FACTORY

    with _ENGINE_LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()

        _ENGINE = None
        _SESSION_FACTORY = None


def get_session_factory() -> sessionmaker[Session]:
    """Return initialized process session factory."""
    if _SESSION_FACTORY is None:
        raise RuntimeError("Database engine is not initialized.")
    return _SESSION_FACTORY


class SQLAlchemyDatabaseReadinessProbe(DatabaseReadinessPort):
    """Persistence adapter for database readiness checks."""

    def ping(self) -> tuple[bool, str | None]:
        """Execute a cheap probe query to verify DB readiness."""
        if _ENGINE is None:
            return False, "Database engine is not initialized."

        try:
            with _ENGINE.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, None
        except SQLAlchemyError as exc:
            return False, str(exc)
