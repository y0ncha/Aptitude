"""Shared adapter helpers for skill-related HTTP routers."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.skill_models import (
    CreateSkillVersionCommand,
    ProvenanceMetadata,
    SkillChecksum,
    SkillContentInput,
    SkillGovernanceInput,
    SkillMetadata,
    SkillMetadataInput,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionStatusUpdate,
)
from app.core.skill_resolution import ResolvedSkillDependencies
from app.interface.api.errors import serialize_validation_errors
from app.interface.dto.skills import (
    ChecksumResponse,
    DependencySelectorRequest,
    DependencySelectorResponse,
    ExactRelationshipSelectorRequest,
    ProvenanceResponse,
    SkillContentSummaryResponse,
    SkillDependencyResolutionResponse,
    SkillGovernanceRequest,
    SkillMetadataResponse,
    SkillVersionCreateRequest,
    SkillVersionMetadataResponse,
    SkillVersionStatusResponse,
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


def to_metadata_response(detail: SkillVersionDetail) -> SkillVersionMetadataResponse:
    """Convert a core detail projection into the immutable metadata response schema."""
    return SkillVersionMetadataResponse(
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
        published_at=detail.published_at,
    )


def to_dependency_resolution_response(
    resolved: ResolvedSkillDependencies,
) -> SkillDependencyResolutionResponse:
    """Convert resolved dependencies into the public response payload."""
    return SkillDependencyResolutionResponse(
        slug=resolved.slug,
        version=resolved.version,
        depends_on=[
            DependencySelectorResponse(
                slug=item.slug,
                version=item.version,
                version_constraint=item.version_constraint,
                optional=item.optional,
                markers=list(item.markers),
            )
            for item in resolved.depends_on
        ],
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
