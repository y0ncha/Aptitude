"""Application entrypoint and startup wiring."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.types import ExceptionHandler

from app.audit.recorder import SQLAlchemyAuditRecorder
from app.core.governance import GovernancePolicy, PolicyViolation
from app.core.logging import build_logging_config, configure_logging
from app.core.readiness import ReadinessService
from app.core.settings import get_settings, reset_settings_cache
from app.core.skill_discovery import SkillDiscoveryService
from app.core.skill_fetch import SkillFetchService
from app.core.skill_registry import SkillRegistryService
from app.core.skill_resolution import SkillResolutionService
from app.interface.api.discovery import router as discovery_router
from app.interface.api.errors import (
    ApiError,
    api_error_exception_handler,
    policy_violation_exception_handler,
    request_validation_exception_handler,
)
from app.interface.api.fetch import router as fetch_router
from app.interface.api.health import router as health_router
from app.interface.api.resolution import router as resolution_router
from app.interface.api.skills import router as skills_router
from app.persistence.db import (
    SQLAlchemyDatabaseReadinessProbe,
    dispose_engine,
    get_session_factory,
    init_engine,
)
from app.persistence.skill_registry_repository import SQLAlchemySkillRegistryRepository

STARTUP_BANNER = r"""
      //| |
     // | |
    //__| |     ___     ___ ___
   / ___  |   //   ) )   / /
  //    | |  //___/ /   / /
 //     | | //         / /      ()
================================================
"""

# Configure logging before lifespan starts so startup logs are consistently formatted.
configure_logging(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"
API_DESCRIPTION = """
Registry-first API for immutable skill publication, candidate discovery,
exact dependency reads, immutable metadata batch fetch, immutable content batch
fetch, and governed lifecycle updates.

The server owns data-local registry operations only. Prompt interpretation,
reranking, dependency solving, final selection, lock generation, and execution
planning remain client-owned behavior outside this API boundary.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize process-wide resources and tear them down on shutdown."""
    reset_settings_cache()
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.auth_tokens:
        logger.info("loaded %d auth token(s) from settings", len(settings.auth_tokens))
    else:
        logger.warning(
            "no auth tokens configured; authenticated endpoints will reject all bearer tokens"
        )
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    registry_repository = SQLAlchemySkillRegistryRepository(session_factory=session_factory)
    audit_recorder = SQLAlchemyAuditRecorder(session_factory=session_factory)
    governance_policy = GovernancePolicy(profile=settings.active_policy)
    app.state.skill_registry_service = SkillRegistryService(
        registry=registry_repository,
        audit_recorder=audit_recorder,
        governance_policy=governance_policy,
    )
    app.state.skill_discovery_service = SkillDiscoveryService(
        search_port=registry_repository,
        audit_recorder=audit_recorder,
        governance_policy=governance_policy,
    )
    app.state.skill_fetch_service = SkillFetchService(
        version_reader=registry_repository,
        governance_policy=governance_policy,
    )
    app.state.skill_resolution_service = SkillResolutionService(
        relationship_reader=registry_repository,
        governance_policy=governance_policy,
    )
    logger.info("service startup complete")
    try:
        yield
    finally:
        dispose_engine()
        logger.info("service shutdown complete")


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app = FastAPI(
        title="aptitude-server Service",
        description=API_DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
    )
    app.state.readiness_service = ReadinessService(
        database_probe=SQLAlchemyDatabaseReadinessProbe(),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, cast(object, request_validation_exception_handler)),
    )
    app.add_exception_handler(
        ApiError,
        cast(ExceptionHandler, cast(object, api_error_exception_handler)),
    )
    app.add_exception_handler(
        PolicyViolation,
        cast(ExceptionHandler, cast(object, policy_violation_exception_handler)),
    )
    app.include_router(health_router)
    app.include_router(discovery_router)
    app.include_router(resolution_router)
    app.include_router(fetch_router)
    app.include_router(skills_router)
    return app


app = create_app()


def run_dev_server() -> None:
    """Run uvicorn with the centralized aptitude logging configuration."""
    import uvicorn

    log_level = os.getenv("LOG_LEVEL", "INFO")
    print(STARTUP_BANNER)
    reload_enabled = os.getenv("UVICORN_RELOAD", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
        log_config=build_logging_config(log_level),
    )


if __name__ == "__main__":
    run_dev_server()
