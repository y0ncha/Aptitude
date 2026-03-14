"""Core batch fetch service for immutable metadata and markdown reads."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity, GovernancePolicy, LifecycleStatus
from app.core.ports import ExactSkillCoordinate, SkillVersionReadPort
from app.core.skill_models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentDocument,
    SkillVersionDetail,
)
from app.core.skill_version_projections import to_skill_version_detail


@dataclass(frozen=True, slots=True)
class SkillVersionMetadataBatchItem:
    """One ordered immutable metadata batch result."""

    coordinate: ExactSkillCoordinate
    item: SkillVersionDetail | None


@dataclass(frozen=True, slots=True)
class SkillContentBatchItem:
    """One ordered immutable content batch result."""

    coordinate: ExactSkillCoordinate
    item: SkillContentDocument | None


class SkillFetchService:
    """Read-only service for batch immutable metadata and markdown access."""

    def __init__(
        self,
        *,
        version_reader: SkillVersionReadPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._version_reader = version_reader
        self._governance_policy = governance_policy

    def get_version_metadata_batch(
        self,
        *,
        caller: CallerIdentity,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[SkillVersionMetadataBatchItem, ...]:
        """Return immutable version metadata in request order."""
        stored_versions = self._version_reader.get_versions_batch(coordinates=coordinates)
        stored_by_key = {(item.slug, item.version): item for item in stored_versions}
        self._ensure_batch_visibility(
            caller=caller,
            lifecycle_statuses=tuple(item.lifecycle_status for item in stored_versions),
        )

        return tuple(
            SkillVersionMetadataBatchItem(
                coordinate=coordinate,
                item=(
                    None
                    if (stored := stored_by_key.get((coordinate.slug, coordinate.version))) is None
                    else to_skill_version_detail(stored=stored)
                ),
            )
            for coordinate in coordinates
        )

    def get_content_batch(
        self,
        *,
        caller: CallerIdentity,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[SkillContentBatchItem, ...]:
        """Return immutable markdown content in request order."""
        stored_contents = self._version_reader.get_version_contents_batch(coordinates=coordinates)
        stored_by_key = {(item.slug, item.version): item for item in stored_contents}
        self._ensure_batch_visibility(
            caller=caller,
            lifecycle_statuses=tuple(item.lifecycle_status for item in stored_contents),
        )

        return tuple(
            SkillContentBatchItem(
                coordinate=coordinate,
                item=(
                    None
                    if (stored := stored_by_key.get((coordinate.slug, coordinate.version))) is None
                    else SkillContentDocument(
                        raw_markdown=stored.raw_markdown,
                        checksum=SkillChecksum(
                            algorithm=SHA256_ALGORITHM,
                            digest=stored.checksum_digest,
                        ),
                        size_bytes=stored.size_bytes,
                    )
                ),
            )
            for coordinate in coordinates
        )

    def _ensure_batch_visibility(
        self,
        *,
        caller: CallerIdentity,
        lifecycle_statuses: tuple[LifecycleStatus, ...],
    ) -> None:
        for lifecycle_status in lifecycle_statuses:
            self._governance_policy.ensure_exact_read_allowed(
                caller=caller,
                lifecycle_status=lifecycle_status,
            )
