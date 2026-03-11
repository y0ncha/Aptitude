"""Shared adapter helpers for skill-related HTTP routers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ValidationError

from app.core.skill_registry import (
    CreateSkillVersionCommand,
    ProvenanceMetadata,
    SkillChecksum,
    SkillContentInput,
    SkillGovernanceInput,
    SkillIdentity,
    SkillMetadata,
    SkillMetadataInput,
    SkillRelationship,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionReference,
    SkillVersionStatusUpdate,
    SkillVersionSummary,
)
from app.core.skill_relationships import SkillRelationshipBatchItem
from app.core.skill_search import SkillSearchResult
from app.interface.api.errors import serialize_validation_errors
from app.interface.dto.skills import (
    ChecksumResponse,
    CurrentSkillVersionResponse,
    DependencySelectorRequest,
    ExactRelationshipSelectorRequest,
    ProvenanceResponse,
    RelationshipSelectorResponse,
    SkillContentSummaryResponse,
    SkillGovernanceRequest,
    SkillIdentityResponse,
    SkillMetadataResponse,
    SkillMetadataSummaryResponse,
    SkillRelationshipBatchItemResponse,
    SkillRelationshipEdgeResponse,
    SkillRelationshipResponse,
    SkillSearchResultResponse,
    SkillVersionCoordinateRequest,
    SkillVersionCreateRequest,
    SkillVersionListResponse,
    SkillVersionReferenceResponse,
    SkillVersionRelationshipsResponse,
    SkillVersionResponse,
    SkillVersionStatusResponse,
    SkillVersionSummaryResponse,
)


def validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Return JSON-safe Pydantic validation details for the public error envelope."""
    return serialize_validation_errors(exc)


def to_create_command(request: SkillVersionCreateRequest) -> CreateSkillVersionCommand:
    """Translate validated API models into immutable core publish commands."""
    return CreateSkillVersionCommand(
        slug=request.slug,
        version=request.version,
        content=SkillContentInput(
            raw_markdown=request.content.raw_markdown,
            rendered_summary=request.content.rendered_summary,
        ),
        metadata=SkillMetadataInput(
            name=request.metadata.name,
            description=request.metadata.description,
            tags=tuple(request.metadata.tags),
            headers=request.metadata.headers,
            inputs_schema=request.metadata.inputs_schema,
            outputs_schema=request.metadata.outputs_schema,
            token_estimate=request.metadata.token_estimate,
            maturity_score=request.metadata.maturity_score,
            security_score=request.metadata.security_score,
        ),
        governance=_governance_input(request.governance),
        relationships=SkillRelationshipsInput(
            depends_on=tuple(
                _dependency_selector(item) for item in request.relationships.depends_on
            ),
            extends=tuple(_exact_selector(item) for item in request.relationships.extends),
            conflicts_with=tuple(
                _exact_selector(item) for item in request.relationships.conflicts_with
            ),
            overlaps_with=tuple(
                _exact_selector(item) for item in request.relationships.overlaps_with
            ),
        ),
    )


def to_skill_identity_response(identity: SkillIdentity) -> SkillIdentityResponse:
    """Convert a core identity projection into the public response schema."""
    return SkillIdentityResponse(
        slug=identity.slug,
        status=identity.status,
        current_version=(
            None
            if identity.current_version is None
            else CurrentSkillVersionResponse(
                version=identity.current_version.version,
                lifecycle_status=identity.current_version.lifecycle_status,
                trust_tier=identity.current_version.trust_tier,
                published_at=identity.current_version.published_at,
            )
        ),
        created_at=identity.created_at,
        updated_at=identity.updated_at,
    )


def to_version_response(detail: SkillVersionDetail) -> SkillVersionResponse:
    """Convert a core detail projection into the exact metadata response schema."""
    return SkillVersionResponse(
        slug=detail.slug,
        version=detail.version,
        version_checksum=_checksum_response(detail.version_checksum),
        content=_content_summary_response(
            detail.content.checksum,
            detail.content.size_bytes,
            detail.content.rendered_summary,
        ),
        metadata=_metadata_response(detail.metadata),
        lifecycle_status=detail.lifecycle_status,
        trust_tier=detail.trust_tier,
        provenance=_provenance_response(detail.provenance),
        relationships=SkillVersionRelationshipsResponse(
            depends_on=[_relationship_response(item) for item in detail.relationships.depends_on],
            extends=[_relationship_response(item) for item in detail.relationships.extends],
            conflicts_with=[
                _relationship_response(item) for item in detail.relationships.conflicts_with
            ],
            overlaps_with=[
                _relationship_response(item) for item in detail.relationships.overlaps_with
            ],
        ),
        published_at=detail.published_at,
        content_download_path=content_download_path(slug=detail.slug, version=detail.version),
    )


def to_version_summary_response(summary: SkillVersionSummary) -> SkillVersionSummaryResponse:
    """Convert a core version summary into the version-list response schema."""
    return SkillVersionSummaryResponse(
        slug=summary.slug,
        version=summary.version,
        version_checksum=_checksum_response(summary.version_checksum),
        content=_content_summary_response(
            summary.content.checksum,
            summary.content.size_bytes,
            summary.content.rendered_summary,
        ),
        metadata=SkillMetadataSummaryResponse(
            name=summary.metadata.name,
            description=summary.metadata.description,
            tags=list(summary.metadata.tags),
        ),
        lifecycle_status=summary.lifecycle_status,
        trust_tier=summary.trust_tier,
        published_at=summary.published_at,
    )


def to_version_list_response(
    *,
    slug: str,
    versions: tuple[SkillVersionSummary, ...],
) -> SkillVersionListResponse:
    """Build the deterministic version-list response."""
    return SkillVersionListResponse(
        slug=slug,
        versions=[to_version_summary_response(item) for item in versions],
    )


def to_related_version_response(reference: SkillVersionReference) -> SkillVersionReferenceResponse:
    """Convert a compact exact version reference into the public schema."""
    return SkillVersionReferenceResponse(
        slug=reference.slug,
        version=reference.version,
        name=reference.name,
        description=reference.description,
        tags=list(reference.tags),
        lifecycle_status=reference.lifecycle_status,
        trust_tier=reference.trust_tier,
        published_at=reference.published_at,
    )


def to_relationship_batch_item_response(
    *,
    item: SkillRelationshipBatchItem,
) -> SkillRelationshipBatchItemResponse:
    """Convert one relationship batch item into the public schema."""
    status: Literal["found", "not_found"]
    status = "not_found" if item.relationships is None else "found"
    return SkillRelationshipBatchItemResponse(
        status=status,
        coordinate=SkillVersionCoordinateRequest(
            slug=item.coordinate.slug,
            version=item.coordinate.version,
        ),
        relationships=(
            None
            if item.relationships is None
            else [
                SkillRelationshipEdgeResponse(
                    edge_type=relationship.edge_type,
                    selector=_selector_response(relationship.selector),
                    target_version=(
                        None
                        if relationship.target_version is None
                        else to_related_version_response(relationship.target_version)
                    ),
                )
                for relationship in item.relationships
            ]
        ),
    )


def to_search_result_response(item: SkillSearchResult) -> SkillSearchResultResponse:
    """Convert a core search result into the compact HTTP search card."""
    return SkillSearchResultResponse(
        slug=item.slug,
        version=item.version,
        name=item.name,
        description=item.description,
        tags=list(item.tags),
        lifecycle_status=item.lifecycle_status,
        trust_tier=item.trust_tier,
        published_at=item.published_at,
        freshness_days=item.freshness_days,
        content_size_bytes=item.content_size_bytes,
        usage_count=item.usage_count,
        matched_fields=list(item.matched_fields),
        matched_tags=list(item.matched_tags),
        reasons=list(item.reasons),
    )


def to_version_status_response(update: SkillVersionStatusUpdate) -> SkillVersionStatusResponse:
    """Convert a core lifecycle update result into the public schema."""
    return SkillVersionStatusResponse(
        slug=update.slug,
        version=update.version,
        status=update.status,
        trust_tier=update.trust_tier,
        lifecycle_changed_at=update.lifecycle_changed_at,
        is_current_default=update.is_current_default,
    )


def content_download_path(*, slug: str, version: str) -> str:
    """Return the stable API path clients should call to download markdown content."""
    return f"/skills/{slug}/versions/{version}/content"


def _dependency_selector(item: DependencySelectorRequest) -> SkillRelationshipSelector:
    return SkillRelationshipSelector(
        slug=item.slug,
        version=item.version,
        version_constraint=item.version_constraint,
        optional=item.optional,
        markers=tuple(item.markers),
    )


def _exact_selector(item: ExactRelationshipSelectorRequest) -> SkillRelationshipSelector:
    return SkillRelationshipSelector(slug=item.slug, version=item.version)


def _governance_input(item: SkillGovernanceRequest) -> SkillGovernanceInput:
    return SkillGovernanceInput(
        trust_tier=item.trust_tier,
        provenance=(
            None
            if item.provenance is None
            else ProvenanceMetadata(
                repo_url=item.provenance.repo_url,
                commit_sha=item.provenance.commit_sha,
                tree_path=item.provenance.tree_path,
            )
        ),
    )


def _checksum_response(checksum: SkillChecksum) -> ChecksumResponse:
    return ChecksumResponse(algorithm=checksum.algorithm, digest=checksum.digest)


def _content_summary_response(
    checksum: SkillChecksum,
    size_bytes: int,
    rendered_summary: str | None,
) -> SkillContentSummaryResponse:
    return SkillContentSummaryResponse(
        checksum=_checksum_response(checksum),
        size_bytes=size_bytes,
        rendered_summary=rendered_summary,
    )


def _metadata_response(metadata: SkillMetadata) -> SkillMetadataResponse:
    return SkillMetadataResponse(
        name=metadata.name,
        description=metadata.description,
        tags=list(metadata.tags),
        headers=metadata.headers,
        inputs_schema=metadata.inputs_schema,
        outputs_schema=metadata.outputs_schema,
        token_estimate=metadata.token_estimate,
        maturity_score=metadata.maturity_score,
        security_score=metadata.security_score,
    )


def _provenance_response(provenance: ProvenanceMetadata | None) -> ProvenanceResponse | None:
    if provenance is None:
        return None
    return ProvenanceResponse(
        repo_url=provenance.repo_url,
        commit_sha=provenance.commit_sha,
        tree_path=provenance.tree_path,
    )


def _selector_response(selector: SkillRelationshipSelector) -> RelationshipSelectorResponse:
    return RelationshipSelectorResponse(
        slug=selector.slug,
        version=selector.version,
        version_constraint=selector.version_constraint,
        optional=selector.optional,
        markers=list(selector.markers),
    )


def _relationship_response(relationship: SkillRelationship) -> SkillRelationshipResponse:
    return SkillRelationshipResponse(
        selector=_selector_response(relationship.selector),
        target_version=(
            None
            if relationship.target_version is None
            else to_related_version_response(relationship.target_version)
        ),
    )
