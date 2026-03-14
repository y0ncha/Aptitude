"""HTTP contract for exact first-degree dependency reads."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse

from app.core.dependencies import ReadCallerDep, SkillResolutionServiceDep
from app.core.skill_models import SkillVersionNotFoundError
from app.interface.api.errors import error_response
from app.interface.api.skill_api_support import to_dependency_resolution_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    RESOLUTION_RESPONSE_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
)
from app.interface.dto.skills import SkillDependencyResolutionResponse
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["resolution"])

ApiResponses = dict[int | str, dict[str, Any]]

RESOLUTION_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Direct dependency declarations returned successfully.",
        "content": {"application/json": {"example": RESOLUTION_RESPONSE_EXAMPLE}},
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The path parameters are invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    },
}


@router.get(
    "/resolution/{slug}/{version}",
    operation_id="getDirectDependencies",
    summary="Read direct immutable dependencies",
    description=(
        "Return authored direct `depends_on` declarations for one exact immutable version. "
        "This route does not recurse, solve version constraints, or return non-dependency "
        "relationship families."
    ),
    response_model=SkillDependencyResolutionResponse,
    response_model_exclude_unset=True,
    responses=RESOLUTION_RESPONSES,
)
def get_direct_dependencies(
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill to resolve."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to resolve."),
    ],
    resolution_service: SkillResolutionServiceDep,
    caller: ReadCallerDep,
) -> SkillDependencyResolutionResponse | JSONResponse:
    """Return direct dependency selectors exactly as authored."""
    try:
        resolved = resolution_service.get_direct_dependencies(
            caller=caller,
            slug=slug,
            version=version,
        )
    except SkillVersionNotFoundError as exc:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )

    return to_dependency_resolution_response(resolved)
