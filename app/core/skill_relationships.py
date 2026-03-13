"""Core direct-relationship query service for immutable skill versions."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import (
    ExactSkillCoordinate,
    RelationshipEdgeType,
    SkillRelationshipReadPort,
    SkillVersionReadPort,
)
from app.core.skill_models import SkillRelationship, SkillRelationshipSelector
from app.core.skill_version_projections import to_skill_version_reference

SUPPORTED_RELATIONSHIP_EDGE_TYPES: tuple[RelationshipEdgeType, ...] = (
    "depends_on",
    "extends",
    "conflicts_with",
    "overlaps_with",
)


@dataclass(frozen=True, slots=True)
class SkillRelationshipBatchItem:
    """Ordered direct-relationship lookup result for one source coordinate."""

    coordinate: ExactSkillCoordinate
    relationships: tuple[SkillRelationship, ...] | None


class SkillRelationshipService:
    """Read-only direct relationship service with no solving behavior."""

    def __init__(
        self,
        *,
        relationship_reader: SkillRelationshipReadPort,
        version_reader: SkillVersionReadPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._relationship_reader = relationship_reader
        self._version_reader = version_reader
        self._governance_policy = governance_policy

    def get_direct_relationships(
        self,
        *,
        caller: CallerIdentity,
        coordinates: tuple[ExactSkillCoordinate, ...],
        edge_types: tuple[RelationshipEdgeType, ...],
    ) -> tuple[SkillRelationshipBatchItem, ...]:
        """Return authored direct relationships for the requested sources."""
        normalized_edge_types = _normalize_edge_types(edge_types)
        stored_sources = self._relationship_reader.get_relationship_sources_batch(
            coordinates=coordinates
        )
        source_by_key = {(item.slug, item.version): item for item in stored_sources}

        exact_target_coordinates: list[ExactSkillCoordinate] = []
        authored_relationships: dict[tuple[str, str], tuple[SkillRelationship, ...]] = {}
        for coordinate in coordinates:
            stored = source_by_key.get((coordinate.slug, coordinate.version))
            if stored is None:
                continue
            if not self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=stored.lifecycle_status,
            ):
                continue

            relationships: list[SkillRelationship] = []
            for selector in stored.relationships:
                if selector.edge_type not in normalized_edge_types:
                    continue
                if selector.version is not None:
                    exact_target_coordinates.append(
                        ExactSkillCoordinate(slug=selector.slug, version=selector.version)
                    )
                relationships.append(
                    SkillRelationship(
                        edge_type=selector.edge_type,
                        selector=SkillRelationshipSelector(
                            slug=selector.slug,
                            version=selector.version,
                            version_constraint=selector.version_constraint,
                            optional=selector.optional,
                            markers=selector.markers,
                        ),
                        target_version=None,
                    )
                )
            authored_relationships[(coordinate.slug, coordinate.version)] = tuple(relationships)

        exact_target_summaries = self._version_reader.get_version_summaries_batch(
            coordinates=tuple(exact_target_coordinates)
        )
        target_by_key = {
            (item.slug, item.version): to_skill_version_reference(stored=item)
            for item in exact_target_summaries
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=item.lifecycle_status,
            )
        }

        return tuple(
            SkillRelationshipBatchItem(
                coordinate=coordinate,
                relationships=(
                    None
                    if (coordinate.slug, coordinate.version) not in authored_relationships
                    else tuple(
                        SkillRelationship(
                            edge_type=item.edge_type,
                            selector=item.selector,
                            target_version=(
                                None
                                if item.selector.version is None
                                else target_by_key.get((item.selector.slug, item.selector.version))
                            ),
                        )
                        for item in authored_relationships[(coordinate.slug, coordinate.version)]
                    )
                ),
            )
            for coordinate in coordinates
        )


def _normalize_edge_types(
    edge_types: tuple[RelationshipEdgeType, ...],
) -> tuple[RelationshipEdgeType, ...]:
    seen: set[RelationshipEdgeType] = set()
    normalized: list[RelationshipEdgeType] = []
    for edge_type in edge_types:
        if edge_type in seen:
            continue
        seen.add(edge_type)
        normalized.append(edge_type)
    return tuple(normalized or SUPPORTED_RELATIONSHIP_EDGE_TYPES)
