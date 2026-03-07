"""Application entrypoint and startup wiring."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.audit.recorder import SQLAlchemyAuditRecorder
from app.core.logging import build_logging_config, configure_logging
from app.core.readiness import ReadinessService
from app.core.settings import get_settings, reset_settings_cache
from app.core.skill_registry import SkillRegistryService
from app.interface.api.health import router as health_router
from app.interface.api.skills import router as skills_router
from app.persistence.artifact_store import FileSystemArtifactStore
from app.persistence.db import (
    SQLAlchemyDatabaseReadinessProbe,
    dispose_engine,
    get_session_factory,
    init_engine,
)
from app.persistence.skill_registry_repository import SQLAlchemySkillRegistryRepository

STARTUP_BANNER = r"""                                    
    // | |                        
   //__| |     ___     ___ ___    
  / ___  |   //   ) )   / /       
 //    | |  //___/ /   / /        
//     | | //         / /      () 

"""

# Configure logging before lifespan starts so startup logs are consistently formatted.
configure_logging(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize process-wide resources and tear them down on shutdown."""
    reset_settings_cache()
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    app.state.skill_registry_service = SkillRegistryService(
        registry=SQLAlchemySkillRegistryRepository(session_factory=session_factory),
        artifact_store=FileSystemArtifactStore(root_dir=settings.artifact_root_dir),
        audit_recorder=SQLAlchemyAuditRecorder(session_factory=session_factory),
    )
    logger.info("service startup complete")
    try:
        yield
    finally:
        dispose_engine()
        logger.info("service shutdown complete")


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app = FastAPI(title="aptitude-server Service", lifespan=lifespan)
    app.state.readiness_service = ReadinessService(
        database_probe=SQLAlchemyDatabaseReadinessProbe(),
    )
    app.include_router(health_router)
    app.include_router(skills_router)
    return app


app = create_app()


def run_dev_server() -> None:
    """Run uvicorn with centralized logging config."""
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
