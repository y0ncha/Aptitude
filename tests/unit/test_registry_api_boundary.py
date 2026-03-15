"""Unit tests for the public registry API route surface."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.main import create_app


def _routes() -> set[tuple[str, str]]:
    app = create_app()
    return {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


@pytest.mark.unit
def test_public_route_surface_exposes_exact_get_fetch_routes() -> None:
    routes = _routes()

    assert ("/skill-versions", "POST") in routes
    assert ("/discovery", "POST") in routes
    assert ("/resolution/{slug}/{version}", "GET") in routes
    assert ("/skills/{slug}/versions/{version}", "GET") in routes
    assert ("/skills/{slug}/versions/{version}/content", "GET") in routes
    assert ("/skills/{slug}/versions/{version}/status", "PATCH") in routes


@pytest.mark.unit
def test_public_route_surface_excludes_removed_route_families() -> None:
    routes = _routes()

    assert ("/discovery/skills/search", "GET") not in routes
    assert ("/resolution/relationships:batch", "POST") not in routes
    assert ("/fetch/metadata:batch", "POST") not in routes
    assert ("/fetch/content:batch", "POST") not in routes
    assert ("/skills/{slug}", "GET") not in routes
    assert ("/skills/{slug}/versions", "GET") not in routes


@pytest.mark.unit
def test_openapi_contract_matches_exact_get_fetch_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    assert "/discovery" in paths
    assert "/resolution/{slug}/{version}" in paths
    assert "/skills/{slug}/versions/{version}" in paths
    assert "/skills/{slug}/versions/{version}/content" in paths
    assert "post" in paths["/discovery"]
    assert "get" in paths["/resolution/{slug}/{version}"]
    assert "get" in paths["/skills/{slug}/versions/{version}"]
    assert "get" in paths["/skills/{slug}/versions/{version}/content"]
    assert "/discovery/skills/search" not in paths
    assert "/resolution/relationships:batch" not in paths
    assert "/fetch/metadata:batch" not in paths
    assert "/fetch/content:batch" not in paths
    assert "/skills/{slug}" not in paths
    assert "/skills/{slug}/versions" not in paths
