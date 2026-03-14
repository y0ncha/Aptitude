"""Shared stored-to-domain projections for immutable skill versions."""

from __future__ import annotations

from app.core.ports import StoredSkillVersion
from app.core.skill_models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentSummary,
    SkillMetadata,
    SkillVersionDetail,
)


def to_skill_version_detail(*, stored: StoredSkillVersion) -> SkillVersionDetail:
    """Project one stored version into the shared detailed domain model."""
    return SkillVersionDetail(
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
            headers=stored.headers,
            inputs_schema=stored.inputs_schema,
            outputs_schema=stored.outputs_schema,
            token_estimate=stored.token_estimate,
            maturity_score=stored.maturity_score,
            security_score=stored.security_score,
        ),
        lifecycle_status=stored.lifecycle_status,
        trust_tier=stored.trust_tier,
        provenance=stored.provenance,
        published_at=stored.published_at,
    )
