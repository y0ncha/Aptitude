"""HTTP contract for direct relationship-resolution read endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.dependencies import SkillRelationshipServiceDep
from app.core.ports import ExactSkillCoordinate
from app.core.skill_relationships import SkillRelationshipBatchItem
from app.interface.api.skill_api_support import to_related_version_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    INVALID_REQUEST_ERROR_EXAMPLE,
    RELATIONSHIP_BATCH_SUCCESS_EXAMPLE,
)
from app.interface.dto.skills import (
    RelationshipSelectorResponse,
    SkillRelationshipBatchItemResponse,
    SkillRelationshipBatchRequest,
    SkillRelationshipBatchResponse,
    SkillRelationshipEdgeResponse,
    SkillVersionCoordinateRequest,
)

router = APIRouter(tags=["resolution"])

OpenAPIResponses = dict[int | str, dict[str, Any]]

RELATIONSHIP_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Ordered direct relationship results returned successfully.",
        "content": {"application/json": {"example": RELATIONSHIP_BATCH_SUCCESS_EXAMPLE}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The relationship query request is invalid.",
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    },
}


@router.post(
    "/resolution/relationships:batch",
    operation_id="batchGetDirectSkillRelationships",
    summary="Read direct immutable relationships",
    description=(
        "Return authored direct `depends_on` and `extends` relationships for exact immutable "
        "source versions. This route does not expand transitive graphs, select versions for "
        "constraints, or emit solved dependency closures."
    ),
    response_model=SkillRelationshipBatchResponse,
    response_model_exclude_unset=True,
    responses=RELATIONSHIP_RESPONSES,
)
def batch_get_relationships(
    request: SkillRelationshipBatchRequest,
    relationship_service: SkillRelationshipServiceDep,
) -> SkillRelationshipBatchResponse:
    """Return direct authored relationships in request order."""
    results = relationship_service.get_direct_relationships(
        coordinates=tuple(
            ExactSkillCoordinate(slug=item.slug, version=item.version)
            for item in request.coordinates
        ),
        edge_types=tuple(request.edge_types),
    )
    return SkillRelationshipBatchResponse(
        results=[_to_relationship_batch_item_response(item) for item in results]
    )


def _to_relationship_batch_item_response(
    item: SkillRelationshipBatchItem,
) -> SkillRelationshipBatchItemResponse:
    if item.relationships is None:
        return SkillRelationshipBatchItemResponse(
            status="not_found",
            coordinate=SkillVersionCoordinateRequest(
                slug=item.coordinate.slug,
                version=item.coordinate.version,
            ),
            relationships=None,
        )

    return SkillRelationshipBatchItemResponse(
        status="found",
        coordinate=SkillVersionCoordinateRequest(
            slug=item.coordinate.slug,
            version=item.coordinate.version,
        ),
        relationships=[
            SkillRelationshipEdgeResponse(
                edge_type=relationship.edge_type,
                selector=RelationshipSelectorResponse(
                    slug=relationship.selector.slug,
                    version=relationship.selector.version,
                    version_constraint=relationship.selector.version_constraint,
                    optional=relationship.selector.optional,
                    markers=list(relationship.selector.markers),
                ),
                target_version=(
                    None
                    if relationship.target_version is None
                    else to_related_version_response(relationship.target_version)
                ),
            )
            for relationship in item.relationships
        ],
    )
