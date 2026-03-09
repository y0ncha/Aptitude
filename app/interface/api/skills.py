"""HTTP contract for immutable skill catalog operations.

This router is intentionally thin. It is responsible for:

- validating incoming request payloads with FastAPI and Pydantic
- preserving authored manifest metadata when translating it to core models
- converting domain errors from ``SkillRegistryService`` into a stable JSON
  error envelope

Routes exposed by this module:

- ``POST /skills/publish`` publishes a new immutable ``skill_id@version``
- ``GET /skills/{skill_id}/{version}`` fetches one immutable version and its
  artifact as base64 text
- ``GET /skills/{skill_id}`` lists all published versions for a skill in
  deterministic newest-first order

File overview:
- Defines the public HTTP schemas for publishing, fetching, and listing skills.
- Keeps business logic delegated to the core registry service.
- Normalizes validation and domain failures into stable API responses.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Path, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.dependencies import SkillRegistryServiceDep
from app.core.skill_registry import (
    ArtifactStorageFailureError,
    DuplicateSkillVersionError,
    IntegrityCheckFailedError,
    InvalidManifestError,
    SkillDependencyRef,
    SkillManifestData,
    SkillRelationshipRef,
    SkillVersionDetail,
    SkillVersionNotFoundError,
)

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

# A single router groups all skill-registry endpoints under one tag so the API
# surface is discoverable in generated OpenAPI docs.
router = APIRouter(tags=["skills"])

# FastAPI expects route-level OpenAPI response metadata to allow either integer
# HTTP status codes or string keys such as "default".
OpenAPIResponses = dict[int | str, dict[str, Any]]


class RelationshipRef(BaseModel):
    """Typed manifest reference to another immutable skill version.

    This schema is reused for relationship lists such as:
    - ``extends``
    - ``conflicts_with``
    - ``overlaps_with``

    Each reference points at one exact immutable version, not a range.
    """

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

    # Reject unknown fields so the manifest contract stays explicit and stable.
    model_config = ConfigDict(extra="forbid")


class DependencyDeclaration(BaseModel):
    """Direct dependency contract authored for a specific immutable version.

    A dependency can target either:
    - one exact immutable version via ``version``, or
    - a constrained range via ``version_constraint``

    The model enforces that exactly one selector is provided.
    """

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

    # Unknown keys are rejected to avoid accidental schema drift.
    model_config = ConfigDict(extra="forbid")

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, value: list[str] | None) -> list[str] | None:
        """Validate authored marker tokens.

        The API preserves marker values exactly, but only if each token matches
        the small allowed grammar. This keeps persistence and comparison simple.
        """
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
    """Validated immutable skill manifest contract.

    This is the public request/response shape exposed by the API. It is also the
    shape restored from stored manifest JSON when versions are fetched or listed.
    """

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

    # Forbid extra keys so manifests remain predictable and versionable.
    model_config = ConfigDict(extra="forbid")


class ErrorBody(BaseModel):
    """Error detail object for API error envelope.

    Separating the inner body from the envelope keeps the response extensible
    while preserving a stable top-level contract: ``{"error": {...}}``.
    """

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable summary of the failure.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured metadata to help clients debug the error.",
    )


class ErrorEnvelope(BaseModel):
    """Standardized error envelope for milestone 02 endpoints."""

    error: ErrorBody = Field(description="Normalized error payload.")


class ChecksumResponse(BaseModel):
    """Checksum metadata attached to a stored artifact.

    Returned on publish, fetch, and list so clients can verify immutability and
    detect artifact changes or corruption.
    """

    algorithm: str = Field(description="Checksum algorithm used for the artifact.")
    digest: str = Field(description="Hex digest of the stored artifact.")


class ArtifactMetadataResponse(BaseModel):
    """Immutable metadata describing where and how large the artifact is."""

    relative_path: str = Field(
        description="Artifact path relative to the configured artifact root."
    )
    size_bytes: int = Field(description="Stored artifact size in bytes.")


class SkillVersionDetailResponse(BaseModel):
    """Metadata returned after a successful publish or fetch.

    This is the base response shape shared by:
    - publish responses
    - fetch responses (extended with artifact bytes)
    """

    skill_id: str = Field(description="Stable identifier of the skill.")
    version: str = Field(description="Immutable semantic version of the skill.")
    manifest: SkillManifest = Field(description="Validated manifest as stored by the service.")
    checksum: ChecksumResponse = Field(description="Checksum metadata for integrity checks.")
    artifact_metadata: ArtifactMetadataResponse = Field(
        description="Location and size metadata for the immutable artifact."
    )
    published_at: datetime = Field(description="UTC timestamp when the version was published.")


class SkillVersionFetchResponse(SkillVersionDetailResponse):
    """Fetch response that includes the binary artifact encoded for JSON transport.

    The artifact is returned as base64 because this endpoint serves JSON rather
    than a streaming binary payload.
    """

    artifact_base64: str = Field(
        description="Artifact bytes encoded as a base64 ASCII string.",
    )


class SkillVersionSummaryResponse(BaseModel):
    """Summary view for one immutable skill version in a list response.

    The shape mirrors the detail response minus the binary artifact content.
    """

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


# Shared OpenAPI error documentation for the publish endpoint.
PUBLISH_ERROR_RESPONSES: OpenAPIResponses = {
    status.HTTP_409_CONFLICT: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `skill_id@version` already exists.",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The manifest JSON is malformed or violates the manifest contract.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Artifact persistence failed while publishing the version.",
    },
}

# Shared OpenAPI error documentation for the fetch endpoint.
FETCH_ERROR_RESPONSES: OpenAPIResponses = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `skill_id@version` does not exist.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Artifact retrieval or integrity verification failed.",
    },
}


@router.post(
    "/skills/publish",
    summary="Publish an immutable skill version",
    description=(
        "Accept multipart form data containing a JSON `manifest` string and a binary "
        "`artifact` upload. The manifest is validated at the API boundary, converted "
        "to core domain models, and persisted only if the same `skill_id@version` "
        "does not already exist."
    ),
    response_model=SkillVersionDetailResponse,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    responses=PUBLISH_ERROR_RESPONSES,
)
async def publish_skill_version(
    manifest: Annotated[
        str,
        Form(description="Manifest JSON string describing the immutable skill version."),
    ],
    artifact: Annotated[
        UploadFile,
        File(description="Binary artifact associated with the published version."),
    ],
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionDetailResponse | JSONResponse:
    """Publish immutable `skill@version` metadata and artifact.

    The endpoint itself stays intentionally small:
    1. FastAPI parses the multipart request.
    2. The helper validates and converts the manifest.
    3. The core registry service performs the actual publish.
    4. Domain exceptions are mapped to stable HTTP error envelopes.
    """
    return await _publish_from_payload(
        manifest=manifest,
        artifact=artifact,
        registry_service=registry_service,
    )


async def _publish_from_payload(
    *,
    manifest: str,
    artifact: UploadFile,
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionDetailResponse | JSONResponse:
    """Validate publish payload, enforce immutability, and persist the version.

    This helper centralizes publish flow so the route remains declarative and the
    behavior is easy to test in isolation.
    """
    try:
        # Parse the JSON string from multipart form data into the public API model.
        parsed_manifest = _parse_manifest(manifest)

        # Read the uploaded artifact into memory before passing it to the core service.
        artifact_bytes = await artifact.read()

        # Delegate persistence and immutability checks to the service layer.
        stored = registry_service.publish_version(
            manifest=_to_manifest_data(parsed_manifest),
            artifact_bytes=artifact_bytes,
        )

        # Convert the service-layer projection back into the HTTP response schema.
        return _to_detail_response(stored=stored)
    except ValidationError as exc:
        # Pydantic validation failure at the API boundary.
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_MANIFEST",
            message="Manifest validation failed.",
            details={"errors": _validation_errors(exc)},
        )
    except InvalidManifestError as exc:
        # Domain-level manifest rejection from the core service.
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_MANIFEST",
            message=str(exc),
        )
    except DuplicateSkillVersionError as exc:
        # Immutable publish conflict: the exact skill_id/version already exists.
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_SKILL_VERSION",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except ArtifactStorageFailureError as exc:
        # Persistence/storage failure while writing the artifact.
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ARTIFACT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.get(
    "/skills/{skill_id}/{version}",
    summary="Fetch one immutable skill version",
    description=(
        "Return the stored manifest, artifact metadata, checksum, and the artifact "
        "itself as a base64-encoded string. The core service verifies the artifact "
        "checksum on every read and fails the request if integrity validation fails."
    ),
    response_model=SkillVersionFetchResponse,
    response_model_exclude_unset=True,
    responses=FETCH_ERROR_RESPONSES,
)
def get_skill_version(
    skill_id: Annotated[
        str,
        Path(
            pattern=SKILL_ID_PATTERN,
            description="Stable identifier of the skill to fetch.",
        ),
    ],
    version: Annotated[
        str,
        Path(
            pattern=SEMVER_PATTERN,
            description="Exact immutable semantic version to fetch.",
        ),
    ],
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionFetchResponse | JSONResponse:
    """Fetch immutable skill version and base64 encoded artifact.

    Path validation guarantees that malformed identifiers or versions are
    rejected before the request reaches the service layer.
    """
    return _fetch_skill_version(
        skill_id=skill_id,
        version=version,
        registry_service=registry_service,
    )


def _fetch_skill_version(
    *,
    skill_id: str,
    version: str,
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionFetchResponse | JSONResponse:
    """Fetch and verify immutable version payload.

    On success, the response includes both metadata and the base64-encoded
    artifact bytes. On failure, domain/storage errors are normalized into the
    router's standard error envelope.
    """
    try:
        stored = registry_service.get_version(skill_id=skill_id, version=version)
        return _to_fetch_response(stored=stored)
    except SkillVersionNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except IntegrityCheckFailedError as exc:
        # Raised when the stored artifact no longer matches its recorded checksum.
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTEGRITY_CHECK_FAILED",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except ArtifactStorageFailureError as exc:
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ARTIFACT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.get(
    "/skills/{skill_id}",
    summary="List published versions for a skill",
    description=(
        "Return every published immutable version for `skill_id`. Results are "
        "deterministic and ordered newest-first by publication timestamp."
    ),
    response_model=SkillVersionListResponse,
    response_model_exclude_unset=True,
)
def list_skill_versions(
    skill_id: Annotated[
        str,
        Path(
            pattern=SKILL_ID_PATTERN,
            description="Stable identifier of the skill whose versions should be listed.",
        ),
    ],
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionListResponse:
    """List immutable versions for a skill in deterministic order."""
    return _list_skill_versions(skill_id=skill_id, registry_service=registry_service)


def _list_skill_versions(
    *,
    skill_id: str,
    registry_service: SkillRegistryServiceDep,
) -> SkillVersionListResponse:
    """List immutable versions for a skill in deterministic order.

    The core service supplies the ordering guarantee. This helper only projects
    domain objects into the public response schema.
    """
    versions = registry_service.list_versions(skill_id=skill_id)
    return SkillVersionListResponse(
        skill_id=skill_id,
        versions=[
            SkillVersionSummaryResponse(
                skill_id=item.skill_id,
                version=item.version,
                # Re-validate stored manifest JSON through the public API schema so
                # the HTTP contract stays consistent on read.
                manifest=SkillManifest.model_validate(item.manifest_json),
                checksum=ChecksumResponse(
                    algorithm=item.checksum.algorithm,
                    digest=item.checksum.digest,
                ),
                artifact_metadata=ArtifactMetadataResponse(
                    relative_path=item.artifact.relative_path,
                    size_bytes=item.artifact.size_bytes,
                ),
                published_at=item.published_at,
            )
            for item in versions
        ],
    )


def _parse_manifest(raw_manifest: str) -> SkillManifest:
    """Parse the JSON manifest form field into the public API manifest schema.

    The publish endpoint accepts the manifest as a multipart text field rather
    than a standalone JSON request body, so parsing happens explicitly here.
    """
    return SkillManifest.model_validate_json(raw_manifest)


def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Return JSON-safe Pydantic validation errors for the public error envelope.

    ``ValidationError.errors()`` may include raw exception instances in
    ``ctx.error`` for custom validators, which breaks JSON serialization.
    Pydantic's JSON serializer already normalizes those values to strings.
    """
    return json.loads(exc.json())


def _to_manifest_data(manifest: SkillManifest) -> SkillManifestData:
    """Translate validated API models into immutable core manifest data.

    `raw_manifest_json` preserves the authored payload shape for persistence and
    subsequent reads, while the tuple-based fields give the core layer immutable
    typed structures.

    Conversion rules:
    - list-like API fields become tuples for immutability in the core layer
    - relationship and dependency entries become dedicated core reference models
    - the original manifest shape is preserved as JSON-compatible data
    """
    return SkillManifestData(
        schema_version=manifest.schema_version,
        skill_id=manifest.skill_id,
        version=manifest.version,
        name=manifest.name,
        description=manifest.description,
        tags=tuple(manifest.tags),
        depends_on=tuple(_to_dependency(item) for item in manifest.depends_on or []),
        extends=tuple(_to_relationship(item) for item in manifest.extends or []),
        conflicts_with=tuple(_to_relationship(item) for item in manifest.conflicts_with or []),
        overlaps_with=tuple(_to_relationship(item) for item in manifest.overlaps_with or []),
        raw_manifest_json=manifest.model_dump(exclude_unset=True, mode="json"),
    )


def _to_relationship(reference: RelationshipRef) -> SkillRelationshipRef:
    """Project an API relationship reference into the core domain shape.

    This is a thin adapter whose main purpose is keeping API-layer models from
    leaking into the core service boundary.
    """
    return SkillRelationshipRef(skill_id=reference.skill_id, version=reference.version)


def _to_dependency(reference: DependencyDeclaration) -> SkillDependencyRef:
    """Project an API dependency declaration into the core domain shape.

    Marker lists are converted to tuples for immutability, while preserving
    ``None`` when the field was not authored.
    """
    return SkillDependencyRef(
        skill_id=reference.skill_id,
        version=reference.version,
        version_constraint=reference.version_constraint,
        optional=reference.optional,
        markers=tuple(reference.markers) if reference.markers is not None else None,
    )


def _to_detail_response(*, stored: SkillVersionDetail) -> SkillVersionDetailResponse:
    """Convert a core detail projection into the publish response schema.

    The service returns a domain object. This helper reshapes it into the exact
    public HTTP contract used by the publish endpoint.
    """
    return SkillVersionDetailResponse(
        skill_id=stored.skill_id,
        version=stored.version,
        manifest=SkillManifest.model_validate(stored.manifest_json),
        checksum=ChecksumResponse(
            algorithm=stored.checksum.algorithm,
            digest=stored.checksum.digest,
        ),
        artifact_metadata=ArtifactMetadataResponse(
            relative_path=stored.artifact.relative_path,
            size_bytes=stored.artifact.size_bytes,
        ),
        published_at=stored.published_at,
    )


def _to_fetch_response(*, stored: SkillVersionDetail) -> SkillVersionFetchResponse:
    """Convert a core detail projection into the fetch response schema.

    Unlike the publish response, fetch also requires binary artifact content.
    Those bytes are JSON-encoded as base64 text.
    """
    if stored.artifact_bytes is None:
        raise ArtifactStorageFailureError("Artifact bytes were not returned for fetch response.")
    return SkillVersionFetchResponse(
        skill_id=stored.skill_id,
        version=stored.version,
        manifest=SkillManifest.model_validate(stored.manifest_json),
        checksum=ChecksumResponse(
            algorithm=stored.checksum.algorithm,
            digest=stored.checksum.digest,
        ),
        artifact_metadata=ArtifactMetadataResponse(
            relative_path=stored.artifact.relative_path,
            size_bytes=stored.artifact.size_bytes,
        ),
        published_at=stored.published_at,
        artifact_base64=base64.b64encode(stored.artifact_bytes).decode("ascii"),
    )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Return the stable JSON error envelope used by this router.

    Keeping all error construction in one helper ensures:
    - the same envelope shape across endpoints
    - consistent JSON serialization behavior
    - stable machine-readable error codes for clients
    """
    payload = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
