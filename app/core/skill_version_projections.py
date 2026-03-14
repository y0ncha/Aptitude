"""Shared stored-to-domain projections for immutable skill versions."""

from __future__ import annotations

from app.core.ports import (
    StoredSkillIdentity,
    StoredSkillVersion,
    StoredSkillVersionSummary,
)
from app.core.skill_models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentSummary,
    SkillMetadata,
    SkillVersionDetail,
    SkillVersionReference,
    SkillVersionSummary,
)


def to_skill_version_summary(
    *,
    stored: StoredSkillVersion | StoredSkillVersionSummary,
) -> SkillVersionSummary:
    """Project one stored version into the shared summary domain model."""
    return SkillVersionSummary(
        slug=stored.slug,
        version=stored.version,
        version_checksum=SkillChecksum(
            algorithm=SHA256_ALGORITHM,
            digest=stored.version_checksum_digest,
        ),
        content=SkillContentSummary(
            checksum=SkillChecksum(
                algorithm=SHA256_ALGORITHM,
                digest=stored.content_checksum_digest,
            ),
            size_bytes=stored.content_size_bytes,
            rendered_summary=stored.rendered_summary,
        ),
        metadata=SkillMetadata(
            name=stored.name,
            description=stored.description,
            tags=stored.tags,
            headers=getattr(stored, "headers", None),
            inputs_schema=getattr(stored, "inputs_schema", None),
            outputs_schema=getattr(stored, "outputs_schema", None),
            token_estimate=getattr(stored, "token_estimate", None),
            maturity_score=getattr(stored, "maturity_score", None),
            security_score=getattr(stored, "security_score", None),
        ),
        lifecycle_status=stored.lifecycle_status,
        trust_tier=stored.trust_tier,
        published_at=stored.published_at,
    )


def to_skill_version_detail(*, stored: StoredSkillVersion) -> SkillVersionDetail:
    """Project one stored version into the shared detailed domain model."""
    summary = to_skill_version_summary(stored=stored)
    return SkillVersionDetail(
        slug=summary.slug,
        version=summary.version,
        version_checksum=summary.version_checksum,
        content=summary.content,
        metadata=summary.metadata,
        lifecycle_status=stored.lifecycle_status,
        trust_tier=stored.trust_tier,
        provenance=stored.provenance,
        published_at=summary.published_at,
    )


def to_skill_version_reference(
    *,
    stored: StoredSkillVersion | StoredSkillVersionSummary,
) -> SkillVersionReference:
    """Project one stored version into the compact reference model."""
    summary = to_skill_version_summary(stored=stored)
    return SkillVersionReference(
        slug=summary.slug,
        version=summary.version,
        name=summary.metadata.name,
        description=summary.metadata.description,
        tags=summary.metadata.tags,
        lifecycle_status=summary.lifecycle_status,
        trust_tier=summary.trust_tier,
        published_at=summary.published_at,
    )


def to_current_version_reference(
    *,
    stored: StoredSkillIdentity,
    visible_versions: tuple[SkillVersionSummary, ...],
) -> SkillVersionReference | None:
    """Return the current visible version reference for one logical skill."""
    if stored.current_version is None:
        return None

    summary_by_version = {item.version: item for item in visible_versions}
    summary = summary_by_version.get(stored.current_version)
    if summary is None:
        return None

    return SkillVersionReference(
        slug=summary.slug,
        version=summary.version,
        name=summary.metadata.name,
        description=summary.metadata.description,
        tags=summary.metadata.tags,
        lifecycle_status=summary.lifecycle_status,
        trust_tier=summary.trust_tier,
        published_at=summary.published_at,
    )
