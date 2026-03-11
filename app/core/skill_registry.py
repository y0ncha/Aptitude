"""Core normalized skill registry service and domain models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from app.core.ports import (
    AuditPort,
    ContentRecordInput,
    CreateSkillVersionRecord,
    MetadataRecordInput,
    RelationshipEdgeType,
    RelationshipSelectorRecordInput,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
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
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillVersionDetail:
    """Detailed immutable metadata projection without the raw markdown body."""

    slug: str
    version: str
    version_checksum: SkillChecksum
    content: SkillContentSummary
    metadata: SkillMetadata
    relationships: SkillVersionRelationships
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SkillIdentity:
    """Logical skill identity returned by the registry API."""

    slug: str
    status: str
    current_version: SkillVersionReference | None
    created_at: datetime
    updated_at: datetime


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
    ) -> None:
        self._registry = registry
        self._audit_recorder = audit_recorder

    def publish_version(self, *, command: CreateSkillVersionCommand) -> SkillVersionDetail:
        """Publish one immutable normalized version."""
        if self._registry.version_exists(slug=command.slug, version=command.version):
            raise DuplicateSkillVersionError(slug=command.slug, version=command.version)

        content_bytes = command.content.raw_markdown.encode("utf-8")
        checksum_digest = hashlib.sha256(content_bytes).hexdigest()
        legacy_manifest = _to_legacy_manifest_json(command=command)

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
                    relationships=_to_relationship_record_inputs(command.relationships),
                    version_checksum_digest=checksum_digest,
                    legacy_manifest_json=legacy_manifest,
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
            },
        )
        return _to_detail(stored=stored)

    def get_skill(self, *, slug: str) -> SkillIdentity:
        """Return one logical skill identity."""
        stored = self._registry.get_skill(slug=slug)
        if stored is None:
            raise SkillNotFoundError(slug=slug)

        current_version = None
        if stored.current_version is not None and stored.current_version_published_at is not None:
            current_version = SkillVersionReference(
                slug=stored.slug,
                version=stored.current_version,
                name="",
                description=None,
                tags=(),
                published_at=stored.current_version_published_at,
            )

        return SkillIdentity(
            slug=stored.slug,
            status=stored.status,
            current_version=current_version,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
        )

    def list_versions(self, *, slug: str) -> tuple[SkillVersionSummary, ...]:
        """Return deterministic summaries for all versions of a skill."""
        versions = self._registry.list_versions(slug=slug)
        if not versions:
            raise SkillNotFoundError(slug=slug)

        self._audit_recorder.record_event(
            event_type="skill.versions_listed",
            payload={"slug": slug, "count": len(versions)},
        )
        return tuple(to_skill_version_summary(stored=record) for record in versions)


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


def _to_legacy_manifest_json(command: CreateSkillVersionCommand) -> dict[str, Any]:
    """Return a compatibility mirror used only for legacy storage columns."""
    return {
        "schema_version": "1.0",
        "skill_id": command.slug,
        "version": command.version,
        "name": command.metadata.name,
        "description": command.metadata.description,
        "tags": list(command.metadata.tags),
        "depends_on": [_selector_to_legacy_json(item) for item in command.relationships.depends_on],
        "extends": [_selector_to_legacy_json(item) for item in command.relationships.extends],
        "conflicts_with": [
            _selector_to_legacy_json(item) for item in command.relationships.conflicts_with
        ],
        "overlaps_with": [
            _selector_to_legacy_json(item) for item in command.relationships.overlaps_with
        ],
    }


def _selector_to_legacy_json(selector: SkillRelationshipSelector) -> dict[str, Any]:
    payload: dict[str, Any] = {"skill_id": selector.slug}
    if selector.version is not None:
        payload["version"] = selector.version
    if selector.version_constraint is not None:
        payload["version_constraint"] = selector.version_constraint
    if selector.optional is not None:
        payload["optional"] = selector.optional
    if selector.markers:
        payload["markers"] = list(selector.markers)
    return payload
