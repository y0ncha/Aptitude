"""HTTP contract for body-based discovery candidate lookup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.dependencies import ReadCallerDep, SkillDiscoveryServiceDep
from app.core.skill_discovery import SkillDiscoveryRequest as CoreSkillDiscoveryRequest
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    DISCOVERY_REQUEST_EXAMPLE,
    DISCOVERY_RESPONSE_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
)
from app.interface.dto.skills import SkillDiscoveryRequest, SkillDiscoveryResponse

router = APIRouter(tags=["discovery"])

ApiResponses = dict[int | str, dict[str, Any]]

DISCOVERY_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Ordered candidate slugs returned successfully.",
        "content": {"application/json": {"example": DISCOVERY_RESPONSE_EXAMPLE}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The discovery request is invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    },
}


@router.post(
    "/discovery",
    operation_id="discoverSkillCandidates",
    summary="Discover candidate skill slugs",
    description=(
        "Return ordered candidate slugs from indexed metadata and description search. "
        "This route is discovery-only: it does not resolve dependencies, choose a final "
        "candidate, or perform solver behavior."
    ),
    response_model=SkillDiscoveryResponse,
    response_model_exclude_unset=True,
    responses=DISCOVERY_RESPONSES,
    openapi_extra={
        "requestBody": {"content": {"application/json": {"example": DISCOVERY_REQUEST_EXAMPLE}}}
    },
)
def discover_skills(
    request: SkillDiscoveryRequest,
    discovery_service: SkillDiscoveryServiceDep,
    caller: ReadCallerDep,
) -> SkillDiscoveryResponse:
    """Return ordered candidate slugs for the provided discovery request."""
    candidates = discovery_service.discover_candidates(
        caller=caller,
        request=CoreSkillDiscoveryRequest(
            name=request.name,
            description=request.description,
            tags=tuple(request.tags),
        ),
    )
    return SkillDiscoveryResponse(candidates=list(candidates))
