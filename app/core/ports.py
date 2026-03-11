"""Core ports that define boundary contracts for infrastructure adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

RelationshipEdgeType = Literal[
    "depends_on",
    "extends",
    "conflicts_with",
    "overlaps_with",
]


@dataclass(frozen=True, slots=True)
class ExactSkillCoordinate:
    """Exact immutable skill-version selector used by read paths."""

    slug: str
    version: str


@dataclass(frozen=True, slots=True)
class ContentRecordInput:
    """Normalized markdown body persisted for one immutable version."""

    raw_markdown: str
    rendered_summary: str | None
    size_bytes: int
    checksum_digest: str


@dataclass(frozen=True, slots=True)
class MetadataRecordInput:
    """Structured metadata persisted for one immutable version."""

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
class RelationshipSelectorRecordInput:
    """One authored selector preserved exactly as published."""

    edge_type: RelationshipEdgeType
    ordinal: int
    slug: str
    version: str | None
    version_constraint: str | None
    optional: bool | None
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CreateSkillVersionRecord:
    """Persistence payload for one immutable version creation."""

    slug: str
    version: str
    content: ContentRecordInput
    metadata: MetadataRecordInput
    relationships: tuple[RelationshipSelectorRecordInput, ...]
    version_checksum_digest: str
    legacy_manifest_json: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StoredRelationshipSelector:
    """Stored selector projection used by fetch and relationship reads."""

    edge_type: RelationshipEdgeType
    ordinal: int
    slug: str
    version: str | None
    version_constraint: str | None
    optional: bool | None
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoredSkillIdentity:
    """Stored logical skill identity projection."""

    slug: str
    status: str
    current_version: str | None
    current_version_published_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredSkillVersionSummary:
    """Stored summary projection used by list and relationship reads."""

    slug: str
    version: str
    version_checksum_digest: str
    content_checksum_digest: str
    content_size_bytes: int
    rendered_summary: str | None
    name: str
    description: str | None
    tags: tuple[str, ...]
    published_at: datetime


@dataclass(frozen=True, slots=True)
class StoredSkillVersion:
    """Stored detailed metadata projection for one immutable version."""

    slug: str
    version: str
    version_checksum_digest: str
    content_checksum_digest: str
    content_size_bytes: int
    rendered_summary: str | None
    name: str
    description: str | None
    tags: tuple[str, ...]
    headers: dict[str, Any] | None
    inputs_schema: dict[str, Any] | None
    outputs_schema: dict[str, Any] | None
    token_estimate: int | None
    maturity_score: float | None
    security_score: float | None
    published_at: datetime
    relationships: tuple[StoredRelationshipSelector, ...]


@dataclass(frozen=True, slots=True)
class StoredSkillVersionContent:
    """Stored markdown content projection."""

    slug: str
    version: str
    raw_markdown: str
    checksum_digest: str
    size_bytes: int
    published_at: datetime


@dataclass(frozen=True, slots=True)
class StoredSkillRelationshipSource:
    """Stored relationship-source projection for batch relationship reads."""

    slug: str
    version: str
    relationships: tuple[StoredRelationshipSelector, ...]


@dataclass(frozen=True, slots=True)
class SearchCandidatesRequest:
    """Normalized discovery request sent to the persistence search adapter."""

    query_text: str | None
    required_tags: tuple[str, ...]
    fresh_within_days: int | None
    max_content_size_bytes: int | None
    limit: int


@dataclass(frozen=True, slots=True)
class StoredSkillSearchCandidate:
    """Persistence projection for one ranked search candidate."""

    skill_version_fk: int
    slug: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    published_at: datetime
    content_size_bytes: int
    usage_count: int
    exact_slug_match: bool
    exact_name_match: bool
    lexical_score: float
    tag_overlap_count: int


class SkillRegistryPersistenceError(RuntimeError):
    """Raised for non-domain-specific persistence failures."""


class SkillRegistryPort(Protocol):
    """Persistence contract for immutable skill version records."""

    def version_exists(self, *, slug: str, version: str) -> bool:
        """Return whether a skill version already exists."""

    def create_version(self, *, record: CreateSkillVersionRecord) -> StoredSkillVersion:
        """Create one immutable normalized version."""

    def get_skill(self, *, slug: str) -> StoredSkillIdentity | None:
        """Return one logical skill identity, if present."""

    def list_versions(self, *, slug: str) -> tuple[StoredSkillVersionSummary, ...]:
        """Return deterministic summaries for all versions of a skill."""


class SkillVersionReadPort(Protocol):
    """Read-only persistence contract for exact immutable version metadata."""

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        """Return a specific immutable version, if present."""

    def get_version_content(self, *, slug: str, version: str) -> StoredSkillVersionContent | None:
        """Return raw markdown content for one immutable version, if present."""

    def get_version_summaries_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillVersionSummary, ...]:
        """Return summaries for exact immutable version coordinates."""


class SkillSearchPort(Protocol):
    """Persistence contract for advisory search candidate retrieval."""

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        """Return ranked skill candidates for the provided discovery request."""


class SkillRelationshipReadPort(Protocol):
    """Read-only persistence contract for authored relationship selector lookup."""

    def get_relationship_sources_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillRelationshipSource, ...]:
        """Return stored relationship sources for the requested coordinates."""


class AuditPort(Protocol):
    """Audit recording contract used by core services."""

    def record_event(self, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Persist a domain audit event."""


class DatabaseReadinessPort(Protocol):
    """Contract for probing database readiness from the core layer."""

    def ping(self) -> tuple[bool, str | None]:
        """Return (is_ready, detail)."""
