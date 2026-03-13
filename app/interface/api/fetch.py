"""HTTP contract for exact immutable metadata and markdown content fetch endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.dependencies import ReadCallerDep, SkillFetchServiceDep
from app.core.skill_registry import SkillVersionNotFoundError
from app.interface.api.errors import error_response
from app.interface.api.skill_api_support import to_version_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills import SkillVersionResponse
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["fetch"])

OpenAPIResponses = dict[int | str, dict[str, Any]]

REQUEST_VALIDATION_ERROR_RESPONSE: OpenAPIResponses = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The request body or path parameters are invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    }
}

FETCH_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Exact immutable skill version metadata returned successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_RESPONSE_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
}

CONTENT_FETCH_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Markdown content returned successfully.",
        "content": {"text/markdown": {}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
}


@router.get(
    "/skills/{slug}/versions/{version}",
    operation_id="getExactSkillVersionMetadata",
    summary="Fetch exact immutable version metadata",
    description=(
        "Return the normalized metadata for one exact immutable skill version. "
        "This route does not inline the raw markdown body."
    ),
    response_model=SkillVersionResponse,
    response_model_exclude_unset=True,
    responses=FETCH_RESPONSES,
)
def get_skill_version_metadata(
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill to fetch."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to fetch."),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> SkillVersionResponse | JSONResponse:
    """Fetch one immutable version metadata projection without markdown bytes."""
    try:
        stored = fetch_service.get_version_metadata(caller=caller, slug=slug, version=version)
        return to_version_response(stored)
    except SkillVersionNotFoundError as exc:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )


@router.get(
    "/skills/{slug}/versions/{version}/content",
    operation_id="getExactSkillVersionContent",
    summary="Fetch exact immutable markdown content",
    description=(
        "Return the canonical markdown body for one exact immutable skill version with "
        "immutable cache headers."
    ),
    response_model=None,
    responses=CONTENT_FETCH_RESPONSES,
)
def get_skill_version_content(
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill to fetch."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to fetch."),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> Response | JSONResponse:
    """Return the raw markdown content for one immutable version."""
    try:
        stored = fetch_service.get_content(caller=caller, slug=slug, version=version)
    except SkillVersionNotFoundError as exc:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )

    return PlainTextResponse(
        content=stored.raw_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "ETag": stored.checksum.digest,
            "Cache-Control": "public, immutable",
            "Content-Length": str(stored.size_bytes),
        },
    )
