"""Unit tests for normalized skill DTO validation rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.interface.dto.skills import SkillRelationshipBatchRequest, SkillVersionCreateRequest


def _request() -> dict[str, object]:
    return {
        "slug": "python.lint",
        "version": "1.2.3",
        "content": {"raw_markdown": "# Python Lint\n"},
        "metadata": {"name": "Python Lint", "tags": ["python", "lint"]},
        "governance": {"trust_tier": "untrusted"},
        "relationships": {
            "depends_on": [],
            "extends": [],
            "conflicts_with": [],
            "overlaps_with": [],
        },
    }


@pytest.mark.unit
def test_publish_request_accepts_all_relationship_families() -> None:
    request = SkillVersionCreateRequest.model_validate(
        {
            **_request(),
            "relationships": {
                "depends_on": [{"slug": "core.base", "version": "1.0.0"}],
                "extends": [{"slug": "python.base", "version": "2.0.0"}],
                "conflicts_with": [{"slug": "ruby.lint", "version": "1.0.0"}],
                "overlaps_with": [{"slug": "python.format", "version": "1.0.0"}],
            },
        }
    )

    assert request.slug == "python.lint"
    assert request.relationships.depends_on[0].version == "1.0.0"
    assert request.relationships.conflicts_with[0].slug == "ruby.lint"


@pytest.mark.unit
def test_publish_request_accepts_dependency_constraints_and_markers() -> None:
    request = SkillVersionCreateRequest.model_validate(
        {
            **_request(),
            "relationships": {
                "depends_on": [
                    {
                        "slug": "core.base",
                        "version_constraint": ">=1.0.0,<2.0.0",
                        "optional": True,
                        "markers": ["linux", "gpu"],
                    }
                ]
            },
        }
    )

    depends_on = request.relationships.depends_on[0]
    assert depends_on.version is None
    assert depends_on.version_constraint == ">=1.0.0,<2.0.0"
    assert depends_on.optional is True
    assert depends_on.markers == ["linux", "gpu"]


@pytest.mark.unit
def test_publish_request_accepts_governance_block_with_provenance() -> None:
    request = SkillVersionCreateRequest.model_validate(
        {
            **_request(),
            "governance": {
                "trust_tier": "internal",
                "provenance": {
                    "repo_url": "https://github.com/acme/python-lint",
                    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                    "tree_path": "skills/python/lint",
                },
            },
        }
    )

    assert request.governance.trust_tier == "internal"
    assert request.governance.provenance is not None
    assert request.governance.provenance.commit_sha.endswith("4567")


@pytest.mark.unit
def test_publish_request_rejects_ambiguous_dependency_version_selectors() -> None:
    with pytest.raises(ValidationError):
        SkillVersionCreateRequest.model_validate(
            {
                **_request(),
                "relationships": {
                    "depends_on": [
                        {
                            "slug": "core.base",
                            "version": "1.0.0",
                            "version_constraint": ">=1.0.0,<2.0.0",
                        }
                    ]
                },
            }
        )


@pytest.mark.unit
def test_publish_request_rejects_invalid_dependency_constraint_syntax() -> None:
    with pytest.raises(ValidationError):
        SkillVersionCreateRequest.model_validate(
            {
                **_request(),
                "relationships": {
                    "depends_on": [{"slug": "core.base", "version_constraint": "latest"}]
                },
            }
        )


@pytest.mark.unit
def test_publish_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SkillVersionCreateRequest.model_validate({**_request(), "extra_field": "not allowed"})


@pytest.mark.unit
def test_relationship_batch_request_uses_independent_default_edge_type_lists() -> None:
    first = SkillRelationshipBatchRequest.model_validate(
        {"coordinates": [{"slug": "python.lint", "version": "1.0.0"}]}
    )
    second = SkillRelationshipBatchRequest.model_validate(
        {"coordinates": [{"slug": "python.format", "version": "2.0.0"}]}
    )

    assert first.edge_types == [
        "depends_on",
        "extends",
        "conflicts_with",
        "overlaps_with",
    ]
    assert second.edge_types == [
        "depends_on",
        "extends",
        "conflicts_with",
        "overlaps_with",
    ]
    assert first.edge_types is not second.edge_types
