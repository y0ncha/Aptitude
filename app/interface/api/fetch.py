"""HTTP contract for immutable metadata and markdown batch fetch endpoints."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Response, status

from app.core.dependencies import ReadCallerDep, SkillFetchServiceDep
from app.core.ports import ExactSkillCoordinate
from app.core.skill_fetch import SkillContentBatchItem
from app.interface.api.skill_api_support import to_metadata_batch_item_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    METADATA_BATCH_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills import SkillVersionBatchRequest, SkillVersionMetadataBatchResponse

router = APIRouter(tags=["fetch"])

ApiResponses = dict[int | str, dict[str, Any]]

REQUEST_VALIDATION_ERROR_RESPONSE: ApiResponses = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The request body is invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    }
}

METADATA_BATCH_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Ordered immutable metadata results returned successfully.",
        "content": {"application/json": {"example": METADATA_BATCH_RESPONSE_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}

CONTENT_BATCH_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Ordered immutable markdown parts returned successfully.",
        "content": {
            "multipart/mixed": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                }
            }
        },
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}


@router.post(
    "/fetch/metadata:batch",
    operation_id="batchGetImmutableMetadata",
    summary="Fetch immutable metadata in batch",
    description=(
        "Return immutable metadata envelopes for an ordered list of exact coordinates. "
        "Missing coordinates are returned as `not_found` items."
    ),
    response_model=SkillVersionMetadataBatchResponse,
    response_model_exclude_unset=True,
    responses=METADATA_BATCH_RESPONSES,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "coordinates": [
                            {"slug": "python.lint", "version": "1.2.3"},
                            {"slug": "python.missing", "version": "9.9.9"},
                        ]
                    }
                }
            }
        }
    },
)
def fetch_metadata_batch(
    request: SkillVersionBatchRequest,
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> SkillVersionMetadataBatchResponse:
    """Return immutable metadata results in request order."""
    results = fetch_service.get_version_metadata_batch(
        caller=caller,
        coordinates=_coordinates(request),
    )
    return SkillVersionMetadataBatchResponse(
        results=[to_metadata_batch_item_response(item) for item in results]
    )


@router.post(
    "/fetch/content:batch",
    operation_id="batchGetImmutableContent",
    summary="Fetch immutable markdown content in batch",
    description=(
        "Return immutable markdown content as `multipart/mixed` in request order. "
        "Each part includes coordinate and status headers."
    ),
    response_model=None,
    responses=CONTENT_BATCH_RESPONSES,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "coordinates": [
                            {"slug": "python.lint", "version": "1.2.3"},
                            {"slug": "python.missing", "version": "9.9.9"},
                        ]
                    }
                }
            }
        }
    },
)
def fetch_content_batch(
    request: SkillVersionBatchRequest,
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> Response:
    """Return immutable markdown content as multipart in request order."""
    items = fetch_service.get_content_batch(
        caller=caller,
        coordinates=_coordinates(request),
    )
    boundary = f"aptitude-{uuid4().hex}"
    return Response(
        content=_multipart_body(items=items, boundary=boundary),
        media_type=f"multipart/mixed; boundary={boundary}",
    )


def _coordinates(request: SkillVersionBatchRequest) -> tuple[ExactSkillCoordinate, ...]:
    return tuple(
        ExactSkillCoordinate(slug=item.slug, version=item.version) for item in request.coordinates
    )


def _multipart_body(*, items: tuple[SkillContentBatchItem, ...], boundary: str) -> bytes:
    body = bytearray()
    for item in items:
        headers = [
            "Content-Type: text/markdown; charset=utf-8",
            f"X-Aptitude-Slug: {item.coordinate.slug}",
            f"X-Aptitude-Version: {item.coordinate.version}",
            f"X-Aptitude-Status: {'not_found' if item.item is None else 'found'}",
        ]
        content = b""
        if item.item is not None:
            headers.extend(
                [
                    f"ETag: {item.item.checksum.digest}",
                    "Cache-Control: public, immutable",
                    f"Content-Length: {item.item.size_bytes}",
                ]
            )
            content = item.item.raw_markdown.encode("utf-8")

        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend("\r\n".join(headers).encode("utf-8"))
        body.extend(b"\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body)
