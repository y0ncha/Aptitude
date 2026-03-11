"""Unit tests for direct relationship read behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.ports import (
    ExactSkillCoordinate,
    StoredRelationshipSelector,
    StoredSkillRelationshipSource,
    StoredSkillVersionSummary,
)
from app.core.skill_registry import SkillVersionReference
from app.core.skill_relationships import SkillRelationshipService


class FakeRelationshipReader:
    """Stub relationship source reader keyed by exact coordinate."""

    def __init__(self, *sources: StoredSkillRelationshipSource) -> None:
        self._sources = {(item.slug, item.version): item for item in sources}

    def get_relationship_sources_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillRelationshipSource, ...]:
        return tuple(
            source
            for coordinate in coordinates
            if (source := self._sources.get((coordinate.slug, coordinate.version))) is not None
        )


class FakeVersionReader:
    """Stub summary reader keyed by exact coordinate."""

    def __init__(self, *summaries: StoredSkillVersionSummary) -> None:
        self._summaries = {(item.slug, item.version): item for item in summaries}

    def get_version_summaries_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillVersionSummary, ...]:
        return tuple(
            summary
            for coordinate in coordinates
            if (summary := self._summaries.get((coordinate.slug, coordinate.version))) is not None
        )


@pytest.mark.unit
def test_get_direct_relationships_converts_exact_target_versions_to_domain_summaries() -> None:
    published_at = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    source = StoredSkillRelationshipSource(
        slug="python.source",
        version="1.0.0",
        relationships=(
            StoredRelationshipSelector(
                edge_type="depends_on",
                ordinal=0,
                slug="python.dep",
                version="2.0.0",
                version_constraint=None,
                optional=None,
                markers=(),
            ),
        ),
    )
    target = StoredSkillVersionSummary(
        slug="python.dep",
        version="2.0.0",
        version_checksum_digest="abc123",
        content_checksum_digest="abc123",
        content_size_bytes=128,
        rendered_summary=None,
        name="Python Dependency",
        description=None,
        tags=("python",),
        published_at=published_at,
    )
    service = SkillRelationshipService(
        relationship_reader=FakeRelationshipReader(source),
        version_reader=FakeVersionReader(target),
    )

    result = service.get_direct_relationships(
        coordinates=(ExactSkillCoordinate(slug="python.source", version="1.0.0"),),
        edge_types=("depends_on",),
    )

    relationship = result[0].relationships[0]
    assert isinstance(relationship.target_version, SkillVersionReference)
    assert relationship.target_version.slug == "python.dep"
    assert relationship.target_version.version == "2.0.0"
