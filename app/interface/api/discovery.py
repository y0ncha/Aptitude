"""HTTP contract for advisory discovery endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.dependencies import SkillDiscoveryServiceDep
from app.core.skill_search import SkillSearchQuery
from app.interface.api.errors import error_response
from app.interface.api.skill_api_support import to_search_result_response, validation_errors
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    SEARCH_INVALID_REQUEST_ERROR_EXAMPLE,
    SEARCH_SUCCESS_EXAMPLE,
)
from app.interface.dto.skills import SkillSearchRequest, SkillSearchResponse

router = APIRouter(tags=["discovery"])

OpenAPIResponses = dict[int | str, dict[str, Any]]

SEARCH_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Compact advisory skill candidates returned successfully.",
        "content": {"application/json": {"example": SEARCH_SUCCESS_EXAMPLE}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The discovery request is invalid.",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {"value": INVALID_REQUEST_ERROR_EXAMPLE},
                    "missing_selector": {"value": SEARCH_INVALID_REQUEST_ERROR_EXAMPLE},
                }
            }
        },
    },
}


@router.get(
    "/discovery/skills/search",
    operation_id="searchDiscoverySkills",
    summary="Search skill discovery metadata",
    description=(
        "Return compact advisory candidates from indexed metadata and description search. "
        "This route is discovery-only: it does not resolve relationships, choose a final "
        "candidate, or perform dependency solving."
    ),
    response_model=SkillSearchResponse,
    response_model_exclude_unset=True,
    responses=SEARCH_RESPONSES,
)
def search_skills(
    discovery_service: SkillDiscoveryServiceDep,
    q: Annotated[str | None, Query(description="Full-text discovery query.")] = None,
    tag: Annotated[
        list[str] | None,
        Query(description="Repeatable tag filter; all values must match."),
    ] = None,
    language: Annotated[
        str | None,
        Query(description="Language alias filter implemented as a normalized tag."),
    ] = None,
    fresh_within_days: Annotated[
        int | None,
        Query(ge=0, description="Maximum age in days since publication."),
    ] = None,
    max_content_size_bytes: Annotated[
        int | None,
        Query(ge=0, description="Maximum allowed markdown size in bytes."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=50, description="Maximum number of skill candidates to return."),
    ] = 20,
) -> SkillSearchResponse | JSONResponse:
    """Search indexed metadata and return compact advisory candidates."""
    try:
        request = SkillSearchRequest(
            q=q,
            tags=tag or [],
            language=language,
            fresh_within_days=fresh_within_days,
            max_content_size_bytes=max_content_size_bytes,
            limit=limit,
        )
    except ValidationError as exc:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_REQUEST",
            message="Search request validation failed.",
            details={"errors": validation_errors(exc)},
        )

    results = discovery_service.search(
        query=SkillSearchQuery(
            q=request.q,
            tags=tuple(request.tags),
            language=request.language,
            fresh_within_days=request.fresh_within_days,
            max_footprint_bytes=request.max_content_size_bytes,
            limit=request.limit,
        )
    )
    return SkillSearchResponse(results=[to_search_result_response(item) for item in results])
