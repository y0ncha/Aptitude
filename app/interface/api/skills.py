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
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Path, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

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
from app.interface.api.errors import error_response, serialize_validation_errors
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    FETCH_SUCCESS_EXAMPLE,
    INTEGRITY_CHECK_FAILED_ERROR_EXAMPLE,
    INVALID_MANIFEST_ERROR_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
    LIST_SUCCESS_EXAMPLE,
    PUBLISH_MULTIPART_FORM_EXAMPLE,
    PUBLISH_SUCCESS_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
)
from app.interface.dto.skills import (
    SEMVER_PATTERN,
    SKILL_ID_PATTERN,
    ArtifactMetadataResponse,
    ChecksumResponse,
    DependencyDeclaration,
    RelationshipRef,
    SkillManifest,
    SkillVersionDetailResponse,
    SkillVersionFetchResponse,
    SkillVersionListResponse,
    SkillVersionSummaryResponse,
)

# A single router groups all skill-registry endpoints under one tag so the API
# surface is discoverable in generated OpenAPI docs.
router = APIRouter(tags=["skills"])


# ===== OpenAPI schemas and shared response metadata =====#

# FastAPI expects route-level OpenAPI response metadata to allow either integer
# HTTP status codes or string keys such as "default".
OpenAPIResponses = dict[int | str, dict[str, Any]]

REQUEST_VALIDATION_ERROR_RESPONSE: OpenAPIResponses = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": (
            "The request payload, form fields, path parameters, or query parameters are invalid."
        ),
        "content": {"application/json": {"example": INVALID_REQUEST_ERROR_EXAMPLE}},
    }
}

PUBLISH_RESPONSES: OpenAPIResponses = {
    status.HTTP_201_CREATED: {
        "description": "Immutable skill version published successfully.",
        "content": {"application/json": {"example": PUBLISH_SUCCESS_EXAMPLE}},
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `skill_id@version` already exists.",
        "content": {"application/json": {"example": DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorEnvelope,
        "description": "The request is invalid or the manifest JSON violates the publish contract.",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {"value": INVALID_REQUEST_ERROR_EXAMPLE},
                    "invalid_manifest": {"value": INVALID_MANIFEST_ERROR_EXAMPLE},
                }
            }
        },
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Artifact persistence failed while publishing the version.",
        "content": {"application/json": {"example": ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE}},
    },
}

FETCH_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Immutable skill version fetched successfully.",
        "content": {"application/json": {"example": FETCH_SUCCESS_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `skill_id@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Artifact retrieval or integrity verification failed.",
        "content": {
            "application/json": {
                "examples": {
                    "integrity_check_failed": {"value": INTEGRITY_CHECK_FAILED_ERROR_EXAMPLE},
                    "artifact_storage_failure": {"value": ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE},
                }
            }
        },
    },
}

LIST_RESPONSES: OpenAPIResponses = {
    status.HTTP_200_OK: {
        "description": "Published versions listed successfully.",
        "content": {"application/json": {"example": LIST_SUCCESS_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}


@router.post(
    "/skills/publish",
    operation_id="publishSkillVersion",
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
    responses=PUBLISH_RESPONSES,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "examples": {
                        "publish": {
                            "summary": "Publish a new immutable skill version",
                            "value": PUBLISH_MULTIPART_FORM_EXAMPLE,
                        }
                    }
                }
            }
        }
    },
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
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_MANIFEST",
            message="Manifest validation failed.",
            details={"errors": _validation_errors(exc)},
        )
    except InvalidManifestError as exc:
        # Domain-level manifest rejection from the core service.
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_MANIFEST",
            message=str(exc),
        )
    except DuplicateSkillVersionError as exc:
        # Immutable publish conflict: the exact skill_id/version already exists.
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_SKILL_VERSION",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except ArtifactStorageFailureError as exc:
        # Persistence/storage failure while writing the artifact.
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ARTIFACT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.get(
    "/skills/{skill_id}/{version}",
    operation_id="getSkillVersion",
    summary="Fetch one immutable skill version",
    description=(
        "Return the stored manifest, artifact metadata, checksum, and the artifact "
        "itself as a base64-encoded string. The core service verifies the artifact "
        "checksum on every read and fails the request if integrity validation fails."
    ),
    response_model=SkillVersionFetchResponse,
    response_model_exclude_unset=True,
    responses=FETCH_RESPONSES,
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
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except IntegrityCheckFailedError as exc:
        # Raised when the stored artifact no longer matches its recorded checksum.
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTEGRITY_CHECK_FAILED",
            message=str(exc),
            details={"skill_id": exc.skill_id, "version": exc.version},
        )
    except ArtifactStorageFailureError as exc:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ARTIFACT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.get(
    "/skills/{skill_id}",
    operation_id="listSkillVersions",
    summary="List published versions for a skill",
    description=(
        "Return every published immutable version for `skill_id`. Results are "
        "deterministic and ordered newest-first by publication timestamp."
    ),
    response_model=SkillVersionListResponse,
    response_model_exclude_unset=True,
    responses=LIST_RESPONSES,
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
    return serialize_validation_errors(exc)


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
