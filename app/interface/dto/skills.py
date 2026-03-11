"""Normalized skill registry DTOs and validation constants."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMVER_CORE = (
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
SEMVER_PATTERN = rf"^{SEMVER_CORE}$"
SLUG_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$"
VERSION_CONSTRAINT_PATTERN = re.compile(
    rf"^\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*"
    rf"(?:,\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*)*$"
)
MARKER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
MAX_BATCH_ITEMS = 100

RelationshipEdgeType = Literal[
    "depends_on",
    "extends",
    "conflicts_with",
    "overlaps_with",
]
BatchItemStatus = Literal["found", "not_found"]
LifecycleStatus = Literal["published", "deprecated", "archived"]
TrustTier = Literal["untrusted", "internal", "verified"]


def _default_relationship_edge_types() -> list[RelationshipEdgeType]:
    return ["depends_on", "extends", "conflicts_with", "overlaps_with"]


class SkillVersionCoordinateRequest(BaseModel):
    """Exact immutable slug/version coordinate."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the requested skill.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Exact immutable semantic version of the requested skill.",
    )

    model_config = ConfigDict(extra="forbid")


class DependencySelectorRequest(BaseModel):
    """Direct dependency selector authored for one version."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the dependency skill.",
    )
    version: str | None = Field(
        default=None,
        pattern=SEMVER_PATTERN,
        description="Exact immutable dependency version.",
    )
    version_constraint: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Comma-separated semver comparators.",
    )
    optional: bool | None = Field(
        default=None,
        description="Whether consumers may omit this dependency at runtime.",
    )
    markers: list[str] = Field(
        default_factory=list,
        description="Execution markers preserved exactly as authored.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, value: list[str]) -> list[str]:
        for marker in value:
            if MARKER_PATTERN.fullmatch(marker) is None:
                raise ValueError(
                    "Dependency markers must contain only letters, numbers, '.', '_', ':', or '-'."
                )
        return value

    @model_validator(mode="after")
    def validate_version_selector(self) -> DependencySelectorRequest:
        if (self.version is None) == (self.version_constraint is None):
            raise ValueError(
                "Dependency selector must include exactly one of `version` or `version_constraint`."
            )
        if self.version_constraint is not None:
            if VERSION_CONSTRAINT_PATTERN.fullmatch(self.version_constraint) is None:
                raise ValueError(
                    "Dependency selector `version_constraint` must be a comma-separated list "
                    "of semver comparators."
                )
        return self


class ExactRelationshipSelectorRequest(BaseModel):
    """Exact immutable relationship selector for non-dependency edges."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the related skill.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Exact immutable semantic version of the related skill.",
    )

    model_config = ConfigDict(extra="forbid")


class SkillVersionContentRequest(BaseModel):
    """Markdown body provided at publish time."""

    raw_markdown: str = Field(description="Canonical markdown body for this immutable version.")
    rendered_summary: str | None = Field(
        default=None,
        description="Optional pre-rendered short summary stored alongside the markdown.",
    )

    model_config = ConfigDict(extra="forbid")


class SkillVersionMetadataRequest(BaseModel):
    """Structured query metadata provided at publish time."""

    name: str = Field(min_length=1, max_length=200, description="Human-readable skill name.")
    description: str | None = Field(
        default=None,
        description="Optional human-readable summary of the skill.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags used for categorization and discovery.",
    )
    headers: dict[str, Any] | None = Field(
        default=None,
        description="Flexible header-like attributes stored as JSON.",
    )
    inputs_schema: dict[str, Any] | None = Field(
        default=None,
        description="Structured input contract stored as JSON.",
    )
    outputs_schema: dict[str, Any] | None = Field(
        default=None,
        description="Structured output contract stored as JSON.",
    )
    token_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Approximate token footprint for ranking/filtering.",
    )
    maturity_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalized maturity score in the range [0, 1].",
    )
    security_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalized security score in the range [0, 1].",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SkillVersionRelationshipsRequest(BaseModel):
    """Grouped authored relationships provided at publish time."""

    depends_on: list[DependencySelectorRequest] = Field(default_factory=list)
    extends: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)
    conflicts_with: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)
    overlaps_with: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProvenanceRequest(BaseModel):
    """Minimal publish-time provenance metadata."""

    repo_url: str = Field(min_length=1, max_length=500)
    commit_sha: str = Field(min_length=7, max_length=64, pattern=r"^[0-9A-Fa-f]+$")
    tree_path: str | None = Field(default=None, min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class SkillGovernanceRequest(BaseModel):
    """Governance metadata supplied at publish time."""

    trust_tier: TrustTier = "untrusted"
    provenance: ProvenanceRequest | None = None

    model_config = ConfigDict(extra="forbid")


class SkillVersionCreateRequest(BaseModel):
    """Normalized JSON publish contract."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug for the skill identity.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Immutable semantic version being published.",
    )
    content: SkillVersionContentRequest
    metadata: SkillVersionMetadataRequest
    governance: SkillGovernanceRequest = Field(default_factory=SkillGovernanceRequest)
    relationships: SkillVersionRelationshipsRequest = Field(
        default_factory=SkillVersionRelationshipsRequest
    )

    model_config = ConfigDict(extra="forbid")


class ChecksumResponse(BaseModel):
    """Checksum metadata attached to stored content or versions."""

    algorithm: str = Field(description="Checksum algorithm used by the service.")
    digest: str = Field(description="Hex digest returned by the service.")


class SkillContentSummaryResponse(BaseModel):
    """Compact content metadata returned without the full markdown body."""

    checksum: ChecksumResponse
    size_bytes: int = Field(description="UTF-8 byte length of the stored markdown.")
    rendered_summary: str | None = Field(
        description="Optional pre-rendered short summary stored with the markdown.",
    )


class SkillMetadataSummaryResponse(BaseModel):
    """Compact metadata summary used in list and relationship responses."""

    name: str
    description: str | None
    tags: list[str]


class SkillMetadataResponse(SkillMetadataSummaryResponse):
    """Full normalized metadata block returned by exact fetch responses."""

    headers: dict[str, Any] | None = None
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None


class ProvenanceResponse(BaseModel):
    """Minimal provenance returned by exact version reads."""

    repo_url: str
    commit_sha: str
    tree_path: str | None = None


class RelationshipSelectorResponse(BaseModel):
    """Authored relationship selector preserved exactly as published."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the related skill.",
    )
    version: str | None = Field(
        default=None,
        pattern=SEMVER_PATTERN,
        description="Exact related version when the selector targets one immutable version.",
    )
    version_constraint: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Authored dependency constraint when the selector is version-ranged.",
    )
    optional: bool | None = Field(default=None)
    markers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SkillVersionReferenceResponse(BaseModel):
    """Compact exact version reference."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: list[str]
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime


class SkillRelationshipResponse(BaseModel):
    """One authored relationship plus optional exact target enrichment."""

    selector: RelationshipSelectorResponse
    target_version: SkillVersionReferenceResponse | None = None


class SkillVersionRelationshipsResponse(BaseModel):
    """Grouped relationships returned in exact fetch responses."""

    depends_on: list[SkillRelationshipResponse] = Field(default_factory=list)
    extends: list[SkillRelationshipResponse] = Field(default_factory=list)
    conflicts_with: list[SkillRelationshipResponse] = Field(default_factory=list)
    overlaps_with: list[SkillRelationshipResponse] = Field(default_factory=list)


class SkillVersionResponse(BaseModel):
    """Normalized exact immutable version metadata response."""

    slug: str
    version: str
    version_checksum: ChecksumResponse
    content: SkillContentSummaryResponse
    metadata: SkillMetadataResponse
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    provenance: ProvenanceResponse | None = None
    relationships: SkillVersionRelationshipsResponse
    published_at: datetime
    content_download_path: str


class SkillVersionSummaryResponse(BaseModel):
    """Summary view for one immutable version in version-list and batch responses."""

    slug: str
    version: str
    version_checksum: ChecksumResponse
    content: SkillContentSummaryResponse
    metadata: SkillMetadataSummaryResponse
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime


class CurrentSkillVersionResponse(BaseModel):
    """Current default version pointer for a skill identity."""

    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime


class SkillIdentityResponse(BaseModel):
    """Logical skill identity response."""

    slug: str
    status: LifecycleStatus
    current_version: CurrentSkillVersionResponse | None
    created_at: datetime
    updated_at: datetime


class SkillVersionListResponse(BaseModel):
    """Deterministic version list for one skill identity."""

    slug: str
    versions: list[SkillVersionSummaryResponse]


class SkillSearchRequest(BaseModel):
    """Validated query shape for advisory search requests."""

    q: str | None = Field(
        default=None,
        description="Optional full-text query over slugs, names, tags, and descriptions.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Repeated tag filters. Every provided tag must be present on a result.",
    )
    language: str | None = Field(
        default=None,
        description="Convenience alias for filtering by a language tag.",
    )
    fresh_within_days: int | None = Field(default=None, ge=0)
    max_content_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional maximum markdown size in bytes.",
    )
    status: list[LifecycleStatus] = Field(
        default_factory=list,
        description="Repeatable lifecycle-state filter.",
    )
    trust_tier: list[TrustTier] = Field(
        default_factory=list,
        description="Repeatable trust-tier filter.",
    )
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("q", "language")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def validate_has_selector(self) -> SkillSearchRequest:
        if (
            self.q is None
            and not self.tags
            and self.language is None
            and self.fresh_within_days is None
            and self.max_content_size_bytes is None
            and not self.status
            and not self.trust_tier
        ):
            raise ValueError("At least one search selector must be provided.")
        return self


class SkillSearchResultResponse(BaseModel):
    """Compact advisory candidate returned by the search API."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: list[str]
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime
    freshness_days: int
    content_size_bytes: int
    usage_count: int
    matched_fields: list[str]
    matched_tags: list[str]
    reasons: list[str]


class SkillSearchResponse(BaseModel):
    """Compact advisory search response."""

    results: list[SkillSearchResultResponse]


class SkillVersionStatusUpdateRequest(BaseModel):
    """Lifecycle transition request for one immutable version."""

    status: LifecycleStatus
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class SkillVersionStatusResponse(BaseModel):
    """Lifecycle status update response."""

    slug: str
    version: str
    status: LifecycleStatus
    trust_tier: TrustTier
    lifecycle_changed_at: datetime
    is_current_default: bool


class SkillRelationshipBatchRequest(BaseModel):
    """Ordered direct relationship query over immutable source versions."""

    coordinates: list[SkillVersionCoordinateRequest] = Field(
        min_length=1,
        max_length=MAX_BATCH_ITEMS,
    )
    edge_types: list[RelationshipEdgeType] = Field(
        default_factory=_default_relationship_edge_types,
    )

    model_config = ConfigDict(extra="forbid")


class SkillRelationshipEdgeResponse(BaseModel):
    """One direct authored relationship edge from an immutable source version."""

    edge_type: RelationshipEdgeType
    selector: RelationshipSelectorResponse
    target_version: SkillVersionReferenceResponse | None = None


class SkillRelationshipBatchItemResponse(BaseModel):
    """One ordered direct relationship lookup result."""

    status: BatchItemStatus
    coordinate: SkillVersionCoordinateRequest
    relationships: list[SkillRelationshipEdgeResponse] | None = None


class SkillRelationshipBatchResponse(BaseModel):
    """Ordered batch response for direct immutable relationship reads."""

    results: list[SkillRelationshipBatchItemResponse]
