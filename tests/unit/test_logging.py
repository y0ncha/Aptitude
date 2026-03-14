"""Unit tests for centralized logging configuration."""

from __future__ import annotations

import logging
import sys

import pytest

from app.core.logging import LOG_FORMAT, build_logging_config, configure_logging


@pytest.mark.unit
def test_build_logging_config_uses_shared_format_for_app_and_libraries() -> None:
    config = build_logging_config("INFO")

    assert config["formatters"]["default"]["format"] == LOG_FORMAT
    assert config["handlers"]["default"]["stream"] == "ext://sys.stdout"
    assert config["root"]["level"] == logging.INFO
    assert config["loggers"]["app"]["handlers"] == ["default"]
    assert config["loggers"]["app"]["level"] == logging.INFO
    assert config["loggers"]["uvicorn.error"]["handlers"] == ["default"]
    assert config["loggers"]["uvicorn.error"]["propagate"] is False
    assert config["loggers"]["uvicorn.access"]["level"] == logging.INFO
    assert config["loggers"]["uvicorn.access"]["propagate"] is False
    assert config["loggers"]["watchfiles"]["level"] == logging.WARNING
    assert config["loggers"]["sqlalchemy"]["handlers"] == ["default"]
    assert config["loggers"]["sqlalchemy"]["level"] == logging.WARNING
    assert config["loggers"]["psycopg"]["handlers"] == ["default"]
    assert config["loggers"]["psycopg"]["level"] == logging.WARNING


@pytest.mark.unit
def test_configure_logging_wires_root_and_library_loggers_to_stdout() -> None:
    configure_logging("invalid-level")

    root_logger = logging.getLogger()
    app_logger = logging.getLogger("app.main")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")

    assert root_logger.level == logging.INFO
    assert app_logger.level == logging.NOTSET
    assert uvicorn_error_logger.level == logging.INFO
    assert uvicorn_error_logger.propagate is False
    assert app_logger.parent is logging.getLogger("app")
    assert root_logger.handlers[0].stream is sys.stdout
    assert root_logger.handlers[0].formatter is not None
    assert root_logger.handlers[0].formatter._fmt == LOG_FORMAT  # noqa: SLF001
    assert uvicorn_error_logger.handlers[0].stream is sys.stdout
    assert uvicorn_error_logger.handlers[0].formatter is not None
    assert uvicorn_error_logger.handlers[0].formatter._fmt == LOG_FORMAT  # noqa: SLF001


@pytest.mark.unit
def test_build_logging_config_keeps_noisy_libraries_verbose_in_debug() -> None:
    config = build_logging_config("DEBUG")

    assert config["loggers"]["uvicorn.access"]["level"] == logging.DEBUG
    assert config["loggers"]["watchfiles"]["level"] == logging.DEBUG
    assert config["loggers"]["sqlalchemy"]["level"] == logging.DEBUG
    assert config["loggers"]["psycopg"]["level"] == logging.DEBUG
