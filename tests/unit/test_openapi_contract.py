"""Tests for the pinned OpenAPI contract artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.main import create_app

OPENAPI_ARTIFACT_PATH = Path("docs/openapi/repository-api-v1.json")


@pytest.mark.unit
def test_runtime_openapi_matches_committed_contract() -> None:
    runtime_schema = create_app().openapi()
    committed_schema = json.loads(OPENAPI_ARTIFACT_PATH.read_text(encoding="utf-8"))

    assert runtime_schema == committed_schema
