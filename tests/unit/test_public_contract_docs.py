"""Unit tests guarding the frozen public contract documentation."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

REMOVED_PUBLIC_READ_ROUTE_MARKERS = (
    "/discovery/skills/search",
    "/resolution/relationships:batch",
    "/fetch/metadata:batch",
    "/fetch/content:batch",
)

CURRENT_CONTRACT_DOCS = (
    REPO_ROOT / "docs/api-contract.md",
    REPO_ROOT / "docs/scope.md",
    REPO_ROOT / "docs/prd.md",
    REPO_ROOT / ".agents/plans/roadmap.md",
)

FROZEN_FUTURE_PLAN_DOCS = tuple(sorted((REPO_ROOT / ".agents/plans").glob("1[0-4]-*.md")))


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    CURRENT_CONTRACT_DOCS + FROZEN_FUTURE_PLAN_DOCS,
    ids=lambda path: path.name,
)
def test_current_contract_docs_do_not_reintroduce_removed_public_read_routes(
    path: Path,
) -> None:
    document = path.read_text()

    for route_marker in REMOVED_PUBLIC_READ_ROUTE_MARKERS:
        assert route_marker not in document


@pytest.mark.unit
def test_api_contract_documents_the_frozen_public_read_surface() -> None:
    document = (REPO_ROOT / "docs/api-contract.md").read_text()

    assert "GET /resolution/{slug}/{version}" in document
    assert "GET /skills/{slug}/versions/{version}" in document
    assert "GET /skills/{slug}/versions/{version}/content" in document
    assert "Resolution remains a first-class public exact-read surface." in document
    assert "they do not add sibling public read route families or compatibility aliases" in document


@pytest.mark.unit
def test_roadmap_freezes_the_public_read_route_families_for_later_plans() -> None:
    document = (REPO_ROOT / ".agents/plans/roadmap.md").read_text()

    assert "Plans 09-14 keep the public route families fixed" in document
    assert "publish, discovery, resolution, exact metadata fetch, exact content fetch" in document
