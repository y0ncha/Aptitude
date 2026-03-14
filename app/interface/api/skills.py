"""Primary normalized skill write and lifecycle routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse

from app.core.dependencies import (
    AdminCallerDep,
    PublishCallerDep,
    SkillRegistryServiceDep,
)
from app.core.skill_registry import (
    DuplicateSkillVersionError,
    SkillRegistryError,
    SkillVersionNotFoundError,
)
from app.interface.api.errors import error_response
from app.interface.api.skill_api_support import (
    to_create_command,
    to_metadata_response,
    to_version_status_response,
)
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
    PUBLISH_REQUEST_EXAMPLE,
    SKILL_VERSION_METADATA_RESPONSE_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_STATUS_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills import (
    SkillVersionCreateRequest,
    SkillVersionMetadataResponse,
    SkillVersionStatusResponse,
    SkillVersionStatusUpdateRequest,
)
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["skills"])

ApiResponses = dict[int | str, dict[str, Any]]

REQUEST_VALIDATION_ERROR_RESPONSE: ApiResponses = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The request body, path parameters, or query parameters are invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    }
}

PUBLISH_RESPONSES: ApiResponses = {
    status.HTTP_201_CREATED: {
        "description": "Immutable skill version published successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_METADATA_RESPONSE_EXAMPLE}},
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` already exists.",
        "content": {"application/json": {"example": DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE}},
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Normalized content or metadata persistence failed.",
        "content": {"application/json": {"example": CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}

STATUS_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Lifecycle status updated successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_STATUS_RESPONSE_EXAMPLE}},
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}


@router.post(
    "/skill-versions",
    operation_id="createSkillVersion",
    summary="Publish an immutable skill version",
    description=(
        "Create a new immutable skill version from a normalized JSON payload containing "
        "markdown content, structured metadata, and authored relationships."
    ),
    response_model=SkillVersionMetadataResponse,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    responses=PUBLISH_RESPONSES,
    openapi_extra={
        "requestBody": {"content": {"application/json": {"example": PUBLISH_REQUEST_EXAMPLE}}}
    },
)
def create_skill_version(
    request: SkillVersionCreateRequest,
    registry_service: SkillRegistryServiceDep,
    caller: PublishCallerDep,
) -> SkillVersionMetadataResponse | JSONResponse:
    """Publish one immutable normalized skill version."""
    try:
        stored = registry_service.publish_version(caller=caller, command=to_create_command(request))
        return to_metadata_response(stored)
    except DuplicateSkillVersionError as exc:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_SKILL_VERSION",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )
    except SkillRegistryError as exc:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONTENT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.patch(
    "/skills/{slug}/versions/{version}/status",
    operation_id="updateSkillVersionStatus",
    summary="Update immutable version lifecycle status",
    description="Transition the lifecycle state for one immutable skill version.",
    response_model=SkillVersionStatusResponse,
    response_model_exclude_unset=True,
    responses=STATUS_RESPONSES,
)
def update_skill_version_status(
    request: SkillVersionStatusUpdateRequest,
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to update."),
    ],
) -> SkillVersionStatusResponse | JSONResponse:
    """Update lifecycle state for one immutable version."""
    try:
        updated = registry_service.update_version_status(
            caller=caller,
            slug=slug,
            version=version,
            lifecycle_status=request.status,
            note=request.note,
        )
        return to_version_status_response(updated)
    except SkillVersionNotFoundError as exc:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )
