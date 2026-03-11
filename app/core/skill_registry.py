"""Core normalized skill registry service and domain models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    ProvenanceMetadata,
    SkillGovernanceInput,
    TrustTier,
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
    StoredSkillIdentity,
    StoredSkillVersion,
    StoredSkillVersionSummary,
)

SHA256_ALGORITHM = "sha256"


@dataclass(frozen=True, slots=True)
class SkillRelationshipSelector:
    """Authored relationship selector preserved exactly as published."""

    slug: str
    version: str | None = None
    version_constraint: str | None = None
    optional: bool | None = None
    markers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillContentInput:
    """Publish-time markdown content."""

    raw_markdown: str
    rendered_summary: str | None = None


@dataclass(frozen=True, slots=True)
class SkillMetadataInput:
    """Publish-time structured metadata."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    headers: dict[str, Any] | None = None
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None


@dataclass(frozen=True, slots=True)
class SkillRelationshipsInput:
    """Grouped authored relationships for one immutable version."""

    depends_on: tuple[SkillRelationshipSelector, ...] = ()
    extends: tuple[SkillRelationshipSelector, ...] = ()
    conflicts_with: tuple[SkillRelationshipSelector, ...] = ()
    overlaps_with: tuple[SkillRelationshipSelector, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateSkillVersionCommand:
    """Publish command for one immutable normalized version."""

    slug: str
    version: str
    content: SkillContentInput
    metadata: SkillMetadataInput
    relationships: SkillRelationshipsInput
    governance: SkillGovernanceInput = SkillGovernanceInput()


@dataclass(frozen=True, slots=True)
class SkillChecksum:
    """Checksum metadata returned by API responses."""

    algorithm: str
    digest: str


@dataclass(frozen=True, slots=True)
class SkillContentSummary:
    """Compact content metadata returned without the full markdown body."""

    checksum: SkillChecksum
    size_bytes: int
    rendered_summary: str | None


@dataclass(frozen=True, slots=True)
class SkillContentDocument:
    """Full markdown content document."""

    raw_markdown: str
    checksum: SkillChecksum
    size_bytes: int
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Normalized structured metadata returned to clients."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    headers: dict[str, Any] | None
    inputs_schema: dict[str, Any] | None
    outputs_schema: dict[str, Any] | None
    token_estimate: int | None
    maturity_score: float | None
    security_score: float | None


@dataclass(frozen=True, slots=True)
class SkillVersionReference:
    """Compact exact version reference used by identity and relationship payloads."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillRelationship:
    """One authored relationship plus optional exact target enrichment."""

    edge_type: RelationshipEdgeType
    selector: SkillRelationshipSelector
    target_version: SkillVersionReference | None


@dataclass(frozen=True, slots=True)
class SkillVersionRelationships:
    """Grouped relationships returned in exact fetch responses."""

    depends_on: tuple[SkillRelationship, ...] = ()
    extends: tuple[SkillRelationship, ...] = ()
    conflicts_with: tuple[SkillRelationship, ...] = ()
    overlaps_with: tuple[SkillRelationship, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillVersionSummary:
    """Summary projection used by list and relationship responses."""

    slug: str
    version: str
    version_checksum: SkillChecksum
    content: SkillContentSummary
    metadata: SkillMetadata
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillVersionDetail:
    """Detailed immutable metadata projection without the raw markdown body."""

    slug: str
    version: str
    version_checksum: SkillChecksum
    content: SkillContentSummary
    metadata: SkillMetadata
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    provenance: ProvenanceMetadata | None
    relationships: SkillVersionRelationships
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillIdentity:
    """Logical skill identity returned by the registry API."""

    slug: str
    status: LifecycleStatus
    current_version: SkillVersionReference | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SkillVersionStatusUpdate:
    """Lifecycle update result returned by the registry API."""

    slug: str
    version: str
    status: LifecycleStatus
    trust_tier: TrustTier
    lifecycle_changed_at: datetime
    is_current_default: bool


class SkillRegistryError(RuntimeError):
    """Base domain error for immutable skill catalog operations."""


class DuplicateSkillVersionError(SkillRegistryError):
    """Raised when immutable skill version already exists."""

    def __init__(self, *, slug: str, version: str) -> None:
        super().__init__(f"Skill version already exists: {slug}@{version}")
        self.slug = slug
        self.version = version


class SkillVersionNotFoundError(SkillRegistryError):
    """Raised when requested immutable skill version does not exist."""

    def __init__(self, *, slug: str, version: str) -> None:
        super().__init__(f"Skill version not found: {slug}@{version}")
        self.slug = slug
        self.version = version


class SkillNotFoundError(SkillRegistryError):
    """Raised when a logical skill slug is unknown."""

    def __init__(self, *, slug: str) -> None:
        super().__init__(f"Skill not found: {slug}")
        self.slug = slug


class SkillRegistryService:
    """Core service for immutable publish plus identity/list reads."""

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
        return _to_detail(stored=stored)

    def get_skill(self, *, caller: CallerIdentity, slug: str) -> SkillIdentity:
        """Return one logical skill identity."""
        stored = self._registry.get_skill(slug=slug)
        if stored is None:
            raise SkillNotFoundError(slug=slug)

        visible_versions = self.list_versions(caller=caller, slug=slug)
        current_version = _current_version_reference(
            stored=stored,
            visible_versions=visible_versions,
        )
        status = (
            current_version.lifecycle_status
            if current_version is not None
            else visible_versions[0].lifecycle_status
        )

        return SkillIdentity(
            slug=stored.slug,
            status=status,
            current_version=current_version,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
        )

    def list_versions(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
    ) -> tuple[SkillVersionSummary, ...]:
        """Return deterministic summaries for all versions of a skill."""
        versions = self._registry.list_versions(slug=slug)
        if not versions:
            raise SkillNotFoundError(slug=slug)

        visible_versions = tuple(
            to_skill_version_summary(stored=record)
            for record in versions
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=record.lifecycle_status,
            )
        )
        if not visible_versions:
            raise SkillNotFoundError(slug=slug)

        self._audit_recorder.record_event(
            event_type="skill.versions_listed",
            payload={"slug": slug, "count": len(visible_versions)},
        )
        return visible_versions

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


def to_skill_version_summary(
    *,
    stored: StoredSkillVersion | StoredSkillVersionSummary,
) -> SkillVersionSummary:
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


def _to_detail(*, stored: StoredSkillVersion) -> SkillVersionDetail:
    relationships = _group_relationships(stored=stored)
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
        relationships=relationships,
        published_at=summary.published_at,
    )


def _group_relationships(*, stored: StoredSkillVersion) -> SkillVersionRelationships:
    grouped: dict[RelationshipEdgeType, list[SkillRelationship]] = {
        "depends_on": [],
        "extends": [],
        "conflicts_with": [],
        "overlaps_with": [],
    }
    for selector in stored.relationships:
        grouped[selector.edge_type].append(
            SkillRelationship(
                edge_type=selector.edge_type,
                selector=SkillRelationshipSelector(
                    slug=selector.slug,
                    version=selector.version,
                    version_constraint=selector.version_constraint,
                    optional=selector.optional,
                    markers=selector.markers,
                ),
                target_version=None,
            )
        )

    return SkillVersionRelationships(
        depends_on=tuple(grouped["depends_on"]),
        extends=tuple(grouped["extends"]),
        conflicts_with=tuple(grouped["conflicts_with"]),
        overlaps_with=tuple(grouped["overlaps_with"]),
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
                        Literal[
                            "depends_on",
                            "extends",
                            "conflicts_with",
                            "overlaps_with",
                        ],
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


def _current_version_reference(
    *,
    stored: StoredSkillIdentity,
    visible_versions: tuple[SkillVersionSummary, ...],
) -> SkillVersionReference | None:
    if stored.current_version is None or stored.current_version_published_at is None:
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
