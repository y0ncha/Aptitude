"""Core exact dependency-resolution service for immutable skill versions."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import ExactSkillCoordinate, SkillRelationshipReadPort
from app.core.skill_models import SkillRelationshipSelector, SkillVersionNotFoundError


@dataclass(frozen=True, slots=True)
class ResolvedSkillDependencies:
    """Direct authored dependency selectors for one immutable skill version."""

    slug: str
    version: str
    depends_on: tuple[SkillRelationshipSelector, ...]


class SkillResolutionService:
    """Read-only exact dependency service with no solving behavior."""

    def __init__(
        self,
        *,
        relationship_reader: SkillRelationshipReadPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._relationship_reader = relationship_reader
        self._governance_policy = governance_policy

    def get_direct_dependencies(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> ResolvedSkillDependencies:
        """Return authored direct `depends_on` selectors for one exact version."""
        coordinate = ExactSkillCoordinate(slug=slug, version=version)
        stored_sources = self._relationship_reader.get_relationship_sources_batch(
            coordinates=(coordinate,),
        )
        if not stored_sources:
            raise SkillVersionNotFoundError(slug=slug, version=version)

        stored = stored_sources[0]
        self._governance_policy.ensure_exact_read_allowed(
            caller=caller,
            lifecycle_status=stored.lifecycle_status,
        )

        return ResolvedSkillDependencies(
            slug=stored.slug,
            version=stored.version,
            depends_on=tuple(
                SkillRelationshipSelector(
                    slug=selector.slug,
                    version=selector.version,
                    version_constraint=selector.version_constraint,
                    optional=selector.optional,
                    markers=selector.markers,
                )
                for selector in stored.relationships
                if selector.edge_type == "depends_on"
            ),
        )
