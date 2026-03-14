"""HTTP contract for exact immutable metadata and markdown fetch endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Response, status
from fastapi.responses import JSONResponse

from app.core.dependencies import ReadCallerDep, SkillFetchServiceDep
from app.core.skill_models import SkillVersionNotFoundError
from app.interface.api.errors import error_response
from app.interface.api.skill_api_support import to_metadata_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    SKILL_VERSION_METADATA_RESPONSE_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
)
from app.interface.dto.skills import SkillVersionMetadataResponse
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["fetch"])

ApiResponses = dict[int | str, dict[str, Any]]

NOT_FOUND_RESPONSE: ApiResponses = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    }
}

PATH_VALIDATION_ERROR_RESPONSE: ApiResponses = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The path parameters are invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    }
}

METADATA_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Immutable metadata returned successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_METADATA_RESPONSE_EXAMPLE}},
    },
    **NOT_FOUND_RESPONSE,
    **PATH_VALIDATION_ERROR_RESPONSE,
}

CONTENT_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Immutable markdown content returned successfully.",
        "content": {
            "text/markdown": {
                "schema": {
                    "type": "string",
                }
            }
        },
    },
    **NOT_FOUND_RESPONSE,
    **PATH_VALIDATION_ERROR_RESPONSE,
}


@router.get(
    "/skills/{slug}/versions/{version}",
    operation_id="getImmutableMetadata",
    summary="Fetch immutable metadata",
    description="Return the immutable metadata envelope for one exact `slug@version`.",
    response_model=SkillVersionMetadataResponse,
    response_model_exclude_unset=True,
    responses=METADATA_RESPONSES,
)
def get_version_metadata(
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the requested skill."),
    ],
    version: Annotated[
        str,
        Path(
            pattern=SEMVER_PATTERN,
            description="Exact immutable semantic version of the requested skill.",
        ),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> SkillVersionMetadataResponse | JSONResponse:
    """Return the immutable metadata envelope for one exact coordinate."""
    try:
        detail = fetch_service.get_version_metadata(
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

    return to_metadata_response(detail)


@router.get(
    "/skills/{slug}/versions/{version}/content",
    operation_id="getImmutableContent",
    summary="Fetch immutable markdown content",
    description="Return the immutable markdown body for one exact `slug@version`.",
    response_model=None,
    responses=CONTENT_RESPONSES,
)
def get_version_content(
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the requested skill."),
    ],
    version: Annotated[
        str,
        Path(
            pattern=SEMVER_PATTERN,
            description="Exact immutable semantic version of the requested skill.",
        ),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> Response | JSONResponse:
    """Return the immutable markdown body for one exact coordinate."""
    try:
        document = fetch_service.get_content(
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

    return Response(
        content=document.raw_markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "ETag": document.checksum.digest,
            "Cache-Control": "public, immutable",
            "Content-Length": str(document.size_bytes),
        },
    )
