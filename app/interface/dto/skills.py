"""Skill registry DTOs and validation constants."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Core semantic-version regex used both in request validation and path params.
# It accepts MAJOR.MINOR.PATCH plus optional prerelease/build metadata.
SEMVER_CORE = (
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
SEMVER_PATTERN = rf"^{SEMVER_CORE}$"

# Public skill identifiers are intentionally conservative and stable:
# - must start with an alphanumeric character
# - may then include letters, numbers, ".", "_", or "-"
# - capped at 128 characters
SKILL_ID_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$"

# Dependency constraints allow one or more comma-separated semver comparators,
# for example: ">=1.0.0,<2.0.0".
VERSION_CONSTRAINT_PATTERN = re.compile(
    rf"^\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*"
    rf"(?:,\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*)*$"
)

# Execution markers are preserved as authored, but constrained to a small token
# grammar so they remain safe and deterministic to store and compare.
MARKER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class RelationshipRef(BaseModel):
    """Typed manifest reference to another immutable skill version."""

    skill_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=SKILL_ID_PATTERN,
        description="Stable identifier of the related skill.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Exact semantic version of the related immutable skill.",
    )

    model_config = ConfigDict(extra="forbid")


class DependencyDeclaration(BaseModel):
    """Direct dependency contract authored for a specific immutable version."""

    skill_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=SKILL_ID_PATTERN,
        description="Stable identifier of the dependency skill.",
    )
    version: str | None = Field(
        default=None,
        pattern=SEMVER_PATTERN,
        description=(
            "Exact immutable dependency version. Mutually exclusive with `version_constraint`."
        ),
    )
    version_constraint: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Comma-separated semver comparators, for example `>=1.0.0,<2.0.0`. "
            "Mutually exclusive with `version`."
        ),
    )
    optional: bool | None = Field(
        default=None,
        description="Whether consumers may omit this dependency at runtime.",
    )
    markers: list[str] | None = Field(
        default=None,
        description="Execution markers preserved exactly as authored in the manifest.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, value: list[str] | None) -> list[str] | None:
        """Validate authored marker tokens."""
        if value is None:
            return None

        for marker in value:
            if MARKER_PATTERN.fullmatch(marker) is None:
                raise ValueError(
                    "Dependency declaration markers must be non-empty tokens "
                    "containing only letters, numbers, '.', '_', ':', or '-'."
                )

        return value

    @model_validator(mode="after")
    def validate_version_selector(self) -> DependencyDeclaration:
        """Ensure the dependency uses exactly one version-selection strategy."""
        if (self.version is None) == (self.version_constraint is None):
            raise ValueError(
                "Dependency declaration must include exactly one of `version` "
                "or `version_constraint`."
            )

        if self.version_constraint is not None:
            if VERSION_CONSTRAINT_PATTERN.fullmatch(self.version_constraint) is None:
                raise ValueError(
                    "Dependency declaration `version_constraint` must be a "
                    "comma-separated list of semver comparators."
                )

        return self


class SkillManifest(BaseModel):
    """Validated immutable skill manifest contract."""

    schema_version: str = Field(
        default="1.0",
        min_length=1,
        max_length=20,
        description="Manifest schema version understood by this API.",
    )
    skill_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=SKILL_ID_PATTERN,
        description="Stable catalog identifier for the skill.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Immutable semantic version being published or fetched.",
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable skill name.",
    )
    description: str | None = Field(
        default=None,
        description="Optional human-readable summary of the skill.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags used for categorization and discovery.",
    )
    depends_on: list[DependencyDeclaration] | None = Field(
        default=None,
        description="Direct dependency declarations authored for this immutable version.",
    )
    extends: list[RelationshipRef] | None = Field(
        default=None,
        description="Other immutable skill versions this version extends.",
    )
    conflicts_with: list[RelationshipRef] | None = Field(
        default=None,
        description="Immutable skill versions known to conflict with this version.",
    )
    overlaps_with: list[RelationshipRef] | None = Field(
        default=None,
        description="Immutable skill versions with overlapping behavior or scope.",
    )

    model_config = ConfigDict(extra="forbid")


class ChecksumResponse(BaseModel):
    """Checksum metadata attached to a stored artifact."""

    algorithm: str = Field(description="Checksum algorithm used for the artifact.")
    digest: str = Field(description="Hex digest of the stored artifact.")


class ArtifactMetadataResponse(BaseModel):
    """Immutable metadata describing where and how large the artifact is."""

    relative_path: str = Field(
        description="Artifact path relative to the configured artifact root."
    )
    size_bytes: int = Field(description="Stored artifact size in bytes.")


class SkillVersionDetailResponse(BaseModel):
    """Metadata returned after a successful publish or fetch."""

    skill_id: str = Field(description="Stable identifier of the skill.")
    version: str = Field(description="Immutable semantic version of the skill.")
    manifest: SkillManifest = Field(description="Validated manifest as stored by the service.")
    checksum: ChecksumResponse = Field(description="Checksum metadata for integrity checks.")
    artifact_metadata: ArtifactMetadataResponse = Field(
        description="Location and size metadata for the immutable artifact."
    )
    published_at: datetime = Field(description="UTC timestamp when the version was published.")


class SkillVersionFetchResponse(SkillVersionDetailResponse):
    """Fetch response that includes the binary artifact encoded for JSON transport."""

    artifact_base64: str = Field(
        description="Artifact bytes encoded as a base64 ASCII string.",
    )


class SkillVersionSummaryResponse(BaseModel):
    """Summary view for one immutable skill version in a list response."""

    skill_id: str = Field(description="Stable identifier of the skill.")
    version: str = Field(description="Immutable semantic version of the skill.")
    manifest: SkillManifest = Field(description="Validated manifest for the listed version.")
    checksum: ChecksumResponse = Field(description="Checksum metadata for the artifact.")
    artifact_metadata: ArtifactMetadataResponse = Field(
        description="Location and size metadata for the immutable artifact."
    )
    published_at: datetime = Field(description="UTC timestamp when the version was published.")


class SkillVersionListResponse(BaseModel):
    """List of all known immutable versions for a skill."""

    skill_id: str = Field(description="Stable identifier of the skill.")
    versions: list[SkillVersionSummaryResponse] = Field(
        description="Published versions in deterministic reverse chronological order.",
    )
