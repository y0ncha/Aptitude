"""Public request and response DTOs for skill APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.governance import LifecycleStatus, TrustTier
from app.interface.validation import (
    MARKER_PATTERN,
    MAX_BATCH_ITEMS,
    SEMVER_PATTERN,
    SLUG_PATTERN,
    VERSION_CONSTRAINT_PATTERN,
)

BatchItemStatus = Literal["found", "not_found"]


def _normalize_unique_tags(value: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in value:
        tag = item.strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


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


class DependencySelectorResponse(BaseModel):
    """Direct dependency selector returned by resolution."""

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
    optional: bool | None = Field(default=None)
    markers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


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
        return _normalize_unique_tags(value)


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


class SkillMetadataResponse(BaseModel):
    """Full normalized metadata block returned by immutable metadata reads."""

    name: str
    description: str | None
    tags: list[str]
    headers: dict[str, Any] | None = None
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None


class ProvenanceResponse(BaseModel):
    """Minimal provenance returned by immutable version reads."""

    repo_url: str
    commit_sha: str
    tree_path: str | None = None


class SkillVersionMetadataResponse(BaseModel):
    """Immutable metadata envelope returned by publish and metadata batch fetch."""

    slug: str
    version: str
    version_checksum: ChecksumResponse
    content: SkillContentSummaryResponse
    metadata: SkillMetadataResponse
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    provenance: ProvenanceResponse | None = None
    published_at: datetime


class SkillDiscoveryRequest(BaseModel):
    """Body-based discovery request."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Discovery `name` must not be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_discovery_tags(cls, value: list[str]) -> list[str]:
        return _normalize_unique_tags(value)


class SkillDiscoveryResponse(BaseModel):
    """Ordered candidate slugs returned by discovery."""

    candidates: list[str]


class SkillDependencyResolutionResponse(BaseModel):
    """Exact direct dependency declarations for one immutable version."""

    slug: str
    version: str
    depends_on: list[DependencySelectorResponse]


class SkillVersionBatchRequest(BaseModel):
    """Ordered exact immutable coordinate batch request."""

    coordinates: list[SkillVersionCoordinateRequest] = Field(
        min_length=1,
        max_length=MAX_BATCH_ITEMS,
    )

    model_config = ConfigDict(extra="forbid")


class SkillVersionMetadataBatchItemResponse(BaseModel):
    """One ordered immutable metadata batch result."""

    status: BatchItemStatus
    coordinate: SkillVersionCoordinateRequest
    item: SkillVersionMetadataResponse | None = None


class SkillVersionMetadataBatchResponse(BaseModel):
    """Ordered immutable metadata batch response."""

    results: list[SkillVersionMetadataBatchItemResponse]


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
