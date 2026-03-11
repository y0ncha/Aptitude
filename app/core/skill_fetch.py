"""Core exact fetch service for normalized version metadata and markdown reads."""

from __future__ import annotations

from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import ExactSkillCoordinate, SkillVersionReadPort
from app.core.skill_registry import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentDocument,
    SkillVersionDetail,
    SkillVersionNotFoundError,
    SkillVersionSummary,
    to_skill_version_summary,
)


class SkillFetchService:
    """Read-only service for exact immutable metadata and markdown content access."""

    def __init__(
        self,
        *,
        version_reader: SkillVersionReadPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._version_reader = version_reader
        self._governance_policy = governance_policy

    def get_version_metadata(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillVersionDetail:
        """Return one immutable version metadata projection without raw markdown."""
        stored = self._version_reader.get_version(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        self._governance_policy.ensure_exact_read_allowed(
            caller=caller,
            lifecycle_status=stored.lifecycle_status,
        )
        from app.core.skill_registry import _to_detail  # local import avoids export churn

        return _to_detail(stored=stored)

    def get_version_metadata_batch(
        self,
        *,
        caller: CallerIdentity,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[SkillVersionSummary, ...]:
        """Return ordered exact metadata summaries for the requested coordinates."""
        stored_versions = self._version_reader.get_version_summaries_batch(coordinates=coordinates)
        by_key = {(item.slug, item.version): item for item in stored_versions}
        return tuple(
            to_skill_version_summary(stored=by_key[(coordinate.slug, coordinate.version)])
            for coordinate in coordinates
            if (coordinate.slug, coordinate.version) in by_key
            and self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=by_key[(coordinate.slug, coordinate.version)].lifecycle_status,
            )
        )

    def get_content(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillContentDocument:
        """Return raw markdown content for one immutable version."""
        stored = self._version_reader.get_version_content(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        self._governance_policy.ensure_exact_read_allowed(
            caller=caller,
            lifecycle_status=stored.lifecycle_status,
        )

        return SkillContentDocument(
            raw_markdown=stored.raw_markdown,
            checksum=SkillChecksum(
                algorithm=SHA256_ALGORITHM,
                digest=stored.checksum_digest,
            ),
            size_bytes=stored.size_bytes,
            published_at=stored.published_at,
        )
