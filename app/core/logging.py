"""Logging bootstrap helpers."""

from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Any

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_LEVEL = logging.INFO


def _resolve_level(level: str) -> int:
    """Resolve a string level name to a stdlib logging constant."""
    return getattr(logging, level.upper(), DEFAULT_LOG_LEVEL)


def _noisy_library_level(resolved_level: int) -> int:
    """Clamp noisy framework loggers to WARNING unless the app runs in DEBUG."""
    return logging.WARNING if resolved_level > logging.DEBUG else resolved_level


def build_logging_config(level: str) -> dict[str, Any]:
    """Return logging config with one shared formatter across app and libraries."""
    resolved_level = _resolve_level(level)
    noisy_library_level = _noisy_library_level(resolved_level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["default"],
            "level": resolved_level,
        },
        "loggers": {
            "app": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "fastapi": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "watchfiles": {
                "handlers": ["default"],
                "level": noisy_library_level,
                "propagate": False,
            },
            "watchfiles.main": {
                "handlers": ["default"],
                "level": noisy_library_level,
                "propagate": False,
            },
            "sqlalchemy": {
                "handlers": ["default"],
                "level": noisy_library_level,
                "propagate": False,
            },
            "psycopg": {
                "handlers": ["default"],
                "level": noisy_library_level,
                "propagate": False,
            },
        },
    }


def configure_logging(level: str) -> None:
    """Configure process logging with a deterministic format."""
    dictConfig(build_logging_config(level))
