"""Unit coverage for persistence adapter helpers."""

from __future__ import annotations

from app.core.ports import MetadataRecordInput
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.skill_registry_repository_support import (
    build_contains_pattern,
    build_search_document_source,
    sort_relationship_selectors,
)


def test_sort_relationship_selectors_uses_canonical_edge_family_order() -> None:
    selectors = [
        SkillRelationshipSelector(edge_type="overlaps_with", ordinal=0, target_slug="overlap"),
        SkillRelationshipSelector(edge_type="conflicts_with", ordinal=0, target_slug="conflict"),
        SkillRelationshipSelector(edge_type="extends", ordinal=1, target_slug="extends-1"),
        SkillRelationshipSelector(edge_type="depends_on", ordinal=1, target_slug="depends-1"),
        SkillRelationshipSelector(edge_type="extends", ordinal=0, target_slug="extends-0"),
        SkillRelationshipSelector(edge_type="depends_on", ordinal=0, target_slug="depends-0"),
    ]

    ordered = sort_relationship_selectors(selectors)

    assert [(item.edge_type, item.ordinal) for item in ordered] == [
        ("depends_on", 0),
        ("depends_on", 1),
        ("extends", 0),
        ("extends", 1),
        ("conflicts_with", 0),
        ("overlaps_with", 0),
    ]


def test_build_contains_pattern_normalizes_none_and_escapes_like_wildcards() -> None:
    assert build_contains_pattern(None) is None
    assert build_contains_pattern("python.discovery") == "%python.discovery%"
    assert build_contains_pattern(r"python\_%") == r"%python\\\_\%%"


def test_build_search_document_source_combines_searchable_fields() -> None:
    source = build_search_document_source(
        slug="Python.Discovery",
        metadata=MetadataRecordInput(
            name="  Python Hard Cut Source  ",
            description=" Hard cut discovery candidate ",
            tags=("Python", "hard-cut", "python"),
            headers=None,
            inputs_schema=None,
            outputs_schema=None,
            token_estimate=None,
            maturity_score=None,
            security_score=None,
        ),
    )

    assert "python.discovery" in source
    assert "python hard cut source" in source
    assert "hard cut discovery candidate" in source
    assert "hard-cut" in source
