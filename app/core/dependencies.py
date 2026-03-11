"""Reusable FastAPI dependencies for core services and settings.

This module centralizes dependency wiring for request handlers so interface code
can declare typed dependencies with minimal boilerplate.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.readiness import ReadinessService
from app.core.settings import Settings, get_settings
from app.core.skill_discovery import SkillDiscoveryService
from app.core.skill_fetch import SkillFetchService
from app.core.skill_registry import SkillRegistryService
from app.core.skill_relationships import SkillRelationshipService

# Shared settings dependency used by route handlers and adapters.
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_readiness_service(request: Request) -> ReadinessService:
    """Return the process-scoped readiness service from app state.

    Raises:
        RuntimeError: If startup wiring did not initialize `readiness_service`.
    """
    service = getattr(request.app.state, "readiness_service", None)
    if not isinstance(service, ReadinessService):
        raise RuntimeError("Readiness service is not initialized.")
    return service


# Typed alias for injecting the readiness service via FastAPI dependencies.
ReadinessServiceDep = Annotated[ReadinessService, Depends(get_readiness_service)]


def get_skill_registry_service(request: Request) -> SkillRegistryService:
    """Return the immutable skill catalog service from app state.

    Raises:
        RuntimeError: If startup wiring did not initialize
            `skill_registry_service`.
    """
    service = getattr(request.app.state, "skill_registry_service", None)
    if not isinstance(service, SkillRegistryService):
        raise RuntimeError("Skill catalog service is not initialized.")
    return service


# Typed alias for injecting the skill catalog service in endpoint signatures.
SkillRegistryServiceDep = Annotated[SkillRegistryService, Depends(get_skill_registry_service)]


def get_skill_discovery_service(request: Request) -> SkillDiscoveryService:
    """Return the process-scoped discovery service from app state."""
    service = getattr(request.app.state, "skill_discovery_service", None)
    if not isinstance(service, SkillDiscoveryService):
        raise RuntimeError("Skill discovery service is not initialized.")
    return service


SkillDiscoveryServiceDep = Annotated[SkillDiscoveryService, Depends(get_skill_discovery_service)]


def get_skill_fetch_service(request: Request) -> SkillFetchService:
    """Return the process-scoped exact fetch service from app state."""
    service = getattr(request.app.state, "skill_fetch_service", None)
    if not isinstance(service, SkillFetchService):
        raise RuntimeError("Skill fetch service is not initialized.")
    return service


SkillFetchServiceDep = Annotated[SkillFetchService, Depends(get_skill_fetch_service)]


def get_skill_relationship_service(request: Request) -> SkillRelationshipService:
    """Return the process-scoped relationship service from app state."""
    service = getattr(request.app.state, "skill_relationship_service", None)
    if not isinstance(service, SkillRelationshipService):
        raise RuntimeError("Skill relationship service is not initialized.")
    return service


SkillRelationshipServiceDep = Annotated[
    SkillRelationshipService, Depends(get_skill_relationship_service)
]
