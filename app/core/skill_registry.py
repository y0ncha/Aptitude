"""Core immutable skill catalog service and domain models."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.ports import (
    ArtifactAlreadyExistsError,
    ArtifactStoreError,
    ArtifactStorePort,
    AuditPort,
    ChecksumExpectation,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
    StoredSkillVersion,
    StoredSkillVersionSummary,
)

SHA256_ALGORITHM = "sha256"


@dataclass(frozen=True, slots=True)
class SkillRelationshipRef:
    """Typed relationship reference to another immutable skill version."""

    skill_id: str
    version: str

    def to_json(self) -> dict[str, str]:
        """Return JSON-ready representation."""
        return {"skill_id": self.skill_id, "version": self.version}


@dataclass(frozen=True, slots=True)
class SkillDependencyRef:
    """Typed direct dependency declaration authored for immutable metadata."""

    skill_id: str
    version: str | None = None
    version_constraint: str | None = None
    optional: bool | None = None
    markers: tuple[str, ...] | None = None

    def to_json(self) -> dict[str, Any]:
        """Return authored dependency metadata without injecting defaults."""
        payload: dict[str, Any] = {"skill_id": self.skill_id}
        if self.version is not None:
            payload["version"] = self.version
        if self.version_constraint is not None:
            payload["version_constraint"] = self.version_constraint
        if self.optional is not None:
            payload["optional"] = self.optional
        if self.markers is not None:
            payload["markers"] = list(self.markers)
        return payload


@dataclass(frozen=True, slots=True)
class SkillManifestData:
    """Core manifest data passed from interface to core."""

    schema_version: str
    skill_id: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    depends_on: tuple[SkillDependencyRef, ...]
    extends: tuple[SkillRelationshipRef, ...]
    conflicts_with: tuple[SkillRelationshipRef, ...]
    overlaps_with: tuple[SkillRelationshipRef, ...]
    raw_manifest_json: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        """Return deterministic JSON projection used for persistence."""
        if self.raw_manifest_json is not None:
            return deepcopy(self.raw_manifest_json)

        return {
            "schema_version": self.schema_version,
            "skill_id": self.skill_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "depends_on": [item.to_json() for item in self.depends_on],
            "extends": [item.to_json() for item in self.extends],
            "conflicts_with": [item.to_json() for item in self.conflicts_with],
            "overlaps_with": [item.to_json() for item in self.overlaps_with],
        }


@dataclass(frozen=True, slots=True)
class SkillChecksum:
    """Checksum metadata used by API responses."""

    algorithm: str
    digest: str


@dataclass(frozen=True, slots=True)
class SkillArtifactMetadata:
    """Immutable artifact metadata returned by API responses."""

    relative_path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SkillVersionDetail:
    """Detailed immutable skill version projection."""

    skill_id: str
    version: str
    manifest_json: dict[str, Any]
    checksum: SkillChecksum
    artifact: SkillArtifactMetadata
    published_at: datetime
    artifact_bytes: bytes | None = None


@dataclass(frozen=True, slots=True)
class SkillVersionSummary:
    """Summary projection used by list endpoint."""

    skill_id: str
    version: str
    manifest_json: dict[str, Any]
    checksum: SkillChecksum
    artifact: SkillArtifactMetadata
    published_at: datetime


class SkillRegistryError(RuntimeError):
    """Base domain error for immutable skill catalog operations."""


class InvalidManifestError(SkillRegistryError):
    """Raised when manifest is invalid for the requested publish operation."""


class DuplicateSkillVersionError(SkillRegistryError):
    """Raised when immutable skill version already exists."""

    def __init__(self, *, skill_id: str, version: str) -> None:
        super().__init__(f"Skill version already exists: {skill_id}@{version}")
        self.skill_id = skill_id
        self.version = version


class SkillVersionNotFoundError(SkillRegistryError):
    """Raised when requested immutable skill version does not exist."""

    def __init__(self, *, skill_id: str, version: str) -> None:
        super().__init__(f"Skill version not found: {skill_id}@{version}")
        self.skill_id = skill_id
        self.version = version


class IntegrityCheckFailedError(SkillRegistryError):
    """Raised when stored checksum does not match artifact bytes."""

    def __init__(self, *, skill_id: str, version: str) -> None:
        super().__init__(f"Integrity check failed for skill version: {skill_id}@{version}")
        self.skill_id = skill_id
        self.version = version


class ArtifactStorageFailureError(SkillRegistryError):
    """Raised when artifact persistence fails."""


class SkillRegistryService:
    """Core service for immutable publish, fetch, and list operations."""

    def __init__(
        self,
        *,
        registry: SkillRegistryPort,
        artifact_store: ArtifactStorePort,
        audit_recorder: AuditPort,
    ) -> None:
        self._registry = registry
        self._artifact_store = artifact_store
        self._audit_recorder = audit_recorder

    def publish_version(
        self, *, manifest: SkillManifestData, artifact_bytes: bytes
    ) -> SkillVersionDetail:
        """Publish an immutable `skill@version` and return persisted projection."""
        if self._registry.version_exists(
            skill_id=manifest.skill_id,
            version=manifest.version,
        ):
            raise DuplicateSkillVersionError(
                skill_id=manifest.skill_id,
                version=manifest.version,
            )

        checksum_digest = hashlib.sha256(artifact_bytes).hexdigest()
        manifest_json = manifest.to_json()

        try:
            artifact_result = self._artifact_store.store_immutable_artifact(
                skill_id=manifest.skill_id,
                version=manifest.version,
                artifact_bytes=artifact_bytes,
                manifest_json=manifest_json,
            )
        except ArtifactAlreadyExistsError as exc:
            raise DuplicateSkillVersionError(
                skill_id=manifest.skill_id, version=manifest.version
            ) from exc
        except ArtifactStoreError as exc:
            raise ArtifactStorageFailureError("Artifact storage failed during publish.") from exc

        checksum = ChecksumExpectation(algorithm=SHA256_ALGORITHM, digest=checksum_digest)

        try:
            stored = self._registry.create_version(
                manifest_json=manifest_json,
                artifact_relative_path=artifact_result.relative_path,
                artifact_size_bytes=artifact_result.size_bytes,
                checksum=checksum,
            )
        except DuplicateSkillVersionError:
            raise
        except SkillRegistryPersistenceError as exc:
            raise ArtifactStorageFailureError(
                "Failed to persist immutable skill version metadata."
            ) from exc

        self._audit_recorder.record_event(
            event_type="skill.version_published",
            payload={
                "skill_id": manifest.skill_id,
                "version": manifest.version,
                "checksum_algorithm": SHA256_ALGORITHM,
                "checksum_digest": checksum_digest,
            },
        )
        return _to_detail(stored=stored, artifact_bytes=None)

    def get_version(self, *, skill_id: str, version: str) -> SkillVersionDetail:
        """Return immutable version and verify checksum on every read."""
        stored = self._registry.get_version(skill_id=skill_id, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(skill_id=skill_id, version=version)

        try:
            artifact_bytes = self._artifact_store.read_artifact(
                relative_path=stored.artifact_relative_path
            )
        except ArtifactStoreError as exc:
            raise ArtifactStorageFailureError("Artifact storage read failed.") from exc
        computed_checksum = hashlib.sha256(artifact_bytes).hexdigest()
        if computed_checksum != stored.checksum_digest:
            self._audit_recorder.record_event(
                event_type="skill.integrity_violation_detected",
                payload={
                    "skill_id": skill_id,
                    "version": version,
                    "expected_checksum": stored.checksum_digest,
                    "actual_checksum": computed_checksum,
                },
            )
            raise IntegrityCheckFailedError(skill_id=skill_id, version=version)

        self._audit_recorder.record_event(
            event_type="skill.version_read",
            payload={"skill_id": skill_id, "version": version},
        )
        return _to_detail(stored=stored, artifact_bytes=artifact_bytes)

    def list_versions(self, *, skill_id: str) -> tuple[SkillVersionSummary, ...]:
        """Return deterministic summaries for all versions of a skill."""
        versions = self._registry.list_versions(skill_id=skill_id)
        self._audit_recorder.record_event(
            event_type="skill.versions_listed",
            payload={"skill_id": skill_id, "count": len(versions)},
        )
        return tuple(_to_summary(stored=record) for record in versions)


def _to_detail(*, stored: StoredSkillVersion, artifact_bytes: bytes | None) -> SkillVersionDetail:
    return SkillVersionDetail(
        skill_id=stored.skill_id,
        version=stored.version,
        manifest_json=stored.manifest_json,
        checksum=SkillChecksum(
            algorithm=stored.checksum_algorithm,
            digest=stored.checksum_digest,
        ),
        artifact=SkillArtifactMetadata(
            relative_path=stored.artifact_relative_path,
            size_bytes=stored.artifact_size_bytes,
        ),
        published_at=stored.published_at,
        artifact_bytes=artifact_bytes,
    )


def _to_summary(*, stored: StoredSkillVersionSummary) -> SkillVersionSummary:
    return SkillVersionSummary(
        skill_id=stored.skill_id,
        version=stored.version,
        manifest_json=stored.manifest_json,
        checksum=SkillChecksum(
            algorithm=stored.checksum_algorithm,
            digest=stored.checksum_digest,
        ),
        artifact=SkillArtifactMetadata(
            relative_path=stored.artifact_relative_path,
            size_bytes=stored.artifact_size_bytes,
        ),
        published_at=stored.published_at,
    )
