"""Regression coverage for SQLAlchemy mapper configuration."""

from __future__ import annotations

from sqlalchemy.orm import configure_mappers


def test_persistence_models_configure_mappers() -> None:
    import app.persistence.models  # noqa: F401

    configure_mappers()
