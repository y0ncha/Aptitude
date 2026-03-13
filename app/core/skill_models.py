"""Core skill registry domain models and errors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.governance import (
    LifecycleStatus,
    ProvenanceMetadata,
    SkillGovernanceInput,
    TrustTier,
)
from app.core.ports import RelationshipEdgeType

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
