"""Core normalized skill registry service."""

from __future__ import annotations

import hashlib
from typing import cast

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    ProvenanceMetadata,
    SkillGovernanceInput,
)
from app.core.ports import (
    AuditPort,
    ContentRecordInput,
    CreateSkillVersionRecord,
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    RelationshipSelectorRecordInput,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
)
from app.core.skill_models import (
    SHA256_ALGORITHM,
    CreateSkillVersionCommand,
    DuplicateSkillVersionError,
    SkillChecksum,
    SkillContentDocument,
    SkillContentInput,
    SkillMetadata,
    SkillMetadataInput,
    SkillRegistryError,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionNotFoundError,
    SkillVersionStatusUpdate,
)
from app.core.skill_version_projections import to_skill_version_detail

__all__ = [
    "SHA256_ALGORITHM",
    "CreateSkillVersionCommand",
    "DuplicateSkillVersionError",
    "ProvenanceMetadata",
    "SkillChecksum",
    "SkillContentDocument",
    "SkillContentInput",
    "SkillGovernanceInput",
    "SkillMetadata",
    "SkillMetadataInput",
    "SkillRegistryError",
    "SkillRelationshipSelector",
    "SkillRelationshipsInput",
    "SkillVersionDetail",
    "SkillVersionNotFoundError",
    "SkillVersionStatusUpdate",
]


class SkillRegistryService:
    """Core service for immutable publish plus lifecycle updates."""

    def __init__(
        self,
        *,
        registry: SkillRegistryPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._registry = registry
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy

    def publish_version(
        self,
        *,
        caller: CallerIdentity,
        command: CreateSkillVersionCommand,
    ) -> SkillVersionDetail:
        """Publish one immutable normalized version."""
        if self._registry.version_exists(slug=command.slug, version=command.version):
            raise DuplicateSkillVersionError(slug=command.slug, version=command.version)

        self._governance_policy.evaluate_publish(
            caller=caller,
            governance=command.governance,
        )

        content_bytes = command.content.raw_markdown.encode("utf-8")
        checksum_digest = hashlib.sha256(content_bytes).hexdigest()

        try:
            stored = self._registry.create_version(
                record=CreateSkillVersionRecord(
                    slug=command.slug,
                    version=command.version,
                    content=ContentRecordInput(
                        raw_markdown=command.content.raw_markdown,
                        rendered_summary=command.content.rendered_summary,
                        size_bytes=len(content_bytes),
                        checksum_digest=checksum_digest,
                    ),
                    metadata=MetadataRecordInput(
                        name=command.metadata.name,
                        description=command.metadata.description,
                        tags=command.metadata.tags,
                        headers=command.metadata.headers,
                        inputs_schema=command.metadata.inputs_schema,
                        outputs_schema=command.metadata.outputs_schema,
                        token_estimate=command.metadata.token_estimate,
                        maturity_score=command.metadata.maturity_score,
                        security_score=command.metadata.security_score,
                    ),
                    governance=GovernanceRecordInput(
                        trust_tier=command.governance.trust_tier,
                        provenance=command.governance.provenance,
                    ),
                    relationships=_to_relationship_record_inputs(command.relationships),
                    version_checksum_digest=checksum_digest,
                )
            )
        except DuplicateSkillVersionError:
            raise
        except SkillRegistryPersistenceError as exc:
            raise SkillRegistryError("Failed to persist immutable skill version.") from exc

        self._audit_recorder.record_event(
            event_type="skill.version_published",
            payload={
                "slug": command.slug,
                "version": command.version,
                "checksum_algorithm": SHA256_ALGORITHM,
                "checksum_digest": checksum_digest,
                "trust_tier": command.governance.trust_tier,
                "policy_profile": self._governance_policy.profile_name,
            },
        )
        return to_skill_version_detail(stored=stored)

    def update_version_status(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
        note: str | None = None,
    ) -> SkillVersionStatusUpdate:
        """Transition lifecycle state for one immutable version."""
        stored = self._registry.get_version(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)

        self._governance_policy.evaluate_transition(
            caller=caller,
            current_status=stored.lifecycle_status,
            next_status=lifecycle_status,
        )

        updated = self._registry.update_version_status(
            slug=slug,
            version=version,
            lifecycle_status=lifecycle_status,
        )
        if updated is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)

        self._audit_recorder.record_event(
            event_type="skill.version_status_updated",
            payload={
                "slug": slug,
                "version": version,
                "previous_status": stored.lifecycle_status,
                "status": updated.lifecycle_status,
                "policy_profile": self._governance_policy.profile_name,
                "note": note,
            },
        )
        return SkillVersionStatusUpdate(
            slug=updated.slug,
            version=updated.version,
            status=updated.lifecycle_status,
            trust_tier=updated.trust_tier,
            lifecycle_changed_at=updated.lifecycle_changed_at,
            is_current_default=updated.is_current_default,
        )


def _to_relationship_record_inputs(
    relationships: SkillRelationshipsInput,
) -> tuple[RelationshipSelectorRecordInput, ...]:
    rows: list[RelationshipSelectorRecordInput] = []
    for edge_type, selectors in (
        ("depends_on", relationships.depends_on),
        ("extends", relationships.extends),
        ("conflicts_with", relationships.conflicts_with),
        ("overlaps_with", relationships.overlaps_with),
    ):
        for ordinal, selector in enumerate(selectors):
            rows.append(
                RelationshipSelectorRecordInput(
                    edge_type=cast(
                        RelationshipEdgeType,
                        edge_type,
                    ),
                    ordinal=ordinal,
                    slug=selector.slug,
                    version=selector.version,
                    version_constraint=selector.version_constraint,
                    optional=selector.optional,
                    markers=selector.markers,
                )
            )
    return tuple(rows)
