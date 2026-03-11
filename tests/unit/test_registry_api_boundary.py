"""Boundary tests for registry-only server API surface."""

from __future__ import annotations

import pytest

from app.main import create_app

_EXPECTED_PUBLIC_PATHS = {
    "/healthz",
    "/readyz",
    "/discovery/skills/search",
    "/resolution/relationships:batch",
    "/skill-versions",
    "/skills/{slug}",
    "/skills/{slug}/versions",
    "/skills/{slug}/versions/{version}",
    "/skills/{slug}/versions/{version}/content",
    "/skills/{slug}/versions/{version}/status",
}
_FORBIDDEN_PATHS = (
    "/resolve",
    "/v1/resolve",
    "/solve",
    "/v1/solve",
)
_FORBIDDEN_PREFIXES = (
    "/bundles/",
    "/v1/bundles/",
    "/locks/",
    "/v1/locks/",
    "/plans/",
    "/v1/plans/",
    "/reports/",
    "/v1/reports/",
)


@pytest.mark.unit
def test_openapi_excludes_client_runtime_endpoints() -> None:
    app = create_app()
    paths = set(app.openapi().get("paths", {}).keys())

    assert paths == _EXPECTED_PUBLIC_PATHS
    assert not any(path in paths for path in _FORBIDDEN_PATHS)
    assert not any(any(path.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES) for path in paths)


@pytest.mark.unit
def test_openapi_exposes_stable_v1_metadata() -> None:
    app = create_app()
    info = app.openapi()["info"]

    assert info["version"] == "1.0.0"
    assert "client-owned behavior" in info["description"]
