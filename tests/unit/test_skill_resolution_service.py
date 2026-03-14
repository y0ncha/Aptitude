"""Unit tests for exact dependency resolution behavior."""

from __future__ import annotations

import pytest

from app.core.governance import CallerIdentity, GovernancePolicy, build_default_policy_profile
from app.core.ports import (
    ExactSkillCoordinate,
    StoredRelationshipSelector,
    StoredSkillRelationshipSource,
)
from app.core.skill_models import SkillVersionNotFoundError
from app.core.skill_resolution import SkillResolutionService


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


@pytest.mark.unit
def test_get_direct_dependencies_returns_only_depends_on_selectors() -> None:
    source = StoredSkillRelationshipSource(
        slug="python.source",
        version="1.0.0",
        lifecycle_status="published",
        trust_tier="internal",
        relationships=(
            StoredRelationshipSelector(
                edge_type="depends_on",
                ordinal=0,
                slug="python.dep",
                version="2.0.0",
                version_constraint=None,
                optional=True,
                markers=("linux",),
            ),
            StoredRelationshipSelector(
                edge_type="extends",
                ordinal=0,
                slug="python.base",
                version="1.0.0",
                version_constraint=None,
                optional=None,
                markers=(),
            ),
        ),
    )
    service = SkillResolutionService(
        relationship_reader=FakeRelationshipReader(source),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
    )

    result = service.get_direct_dependencies(
        caller=CallerIdentity(token="reader", scopes=frozenset({"read"})),
        slug="python.source",
        version="1.0.0",
    )

    assert result.slug == "python.source"
    assert result.version == "1.0.0"
    assert len(result.depends_on) == 1
    assert result.depends_on[0].slug == "python.dep"
    assert result.depends_on[0].version == "2.0.0"
    assert result.depends_on[0].optional is True
    assert result.depends_on[0].markers == ("linux",)


@pytest.mark.unit
def test_get_direct_dependencies_raises_not_found_for_unknown_coordinate() -> None:
    service = SkillResolutionService(
        relationship_reader=FakeRelationshipReader(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.get_direct_dependencies(
            caller=CallerIdentity(token="reader", scopes=frozenset({"read"})),
            slug="python.missing",
            version="9.9.9",
        )
