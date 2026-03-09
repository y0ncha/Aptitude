"""Boundary tests for registry-only server API surface."""

from __future__ import annotations

import pytest

from app.main import create_app

_FORBIDDEN_PATHS = (
    "/resolve",
    "/v1/resolve",
)
_FORBIDDEN_PREFIXES = (
    "/bundles/",
    "/v1/bundles/",
    "/reports/",
    "/v1/reports/",
)


@pytest.mark.unit
def test_openapi_excludes_resolver_endpoints() -> None:
    app = create_app()
    paths = set(app.openapi().get("paths", {}).keys())

    assert not any(path in paths for path in _FORBIDDEN_PATHS)
    assert not any(any(path.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES) for path in paths)
