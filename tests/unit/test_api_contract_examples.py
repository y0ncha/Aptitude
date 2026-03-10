"""Validation tests for shared OpenAPI examples."""

from __future__ import annotations

from typing import Any

import pytest

from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    FETCH_SUCCESS_EXAMPLE,
    INTEGRITY_CHECK_FAILED_ERROR_EXAMPLE,
    INVALID_MANIFEST_ERROR_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
    LIST_SUCCESS_EXAMPLE,
    PUBLISH_MANIFEST_EXAMPLE,
    PUBLISH_SUCCESS_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
)
from app.interface.dto.skills import (
    SkillManifest,
    SkillVersionDetailResponse,
    SkillVersionFetchResponse,
    SkillVersionListResponse,
)


@pytest.mark.unit
def test_publish_manifest_example_matches_request_contract() -> None:
    manifest = SkillManifest.model_validate(PUBLISH_MANIFEST_EXAMPLE)

    assert manifest.skill_id == "python.lint"
    assert manifest.depends_on is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "model"),
    [
        (PUBLISH_SUCCESS_EXAMPLE, SkillVersionDetailResponse),
        (FETCH_SUCCESS_EXAMPLE, SkillVersionFetchResponse),
        (LIST_SUCCESS_EXAMPLE, SkillVersionListResponse),
    ],
)
def test_success_examples_match_response_contracts(
    payload: dict[str, object],
    model: type[Any],
) -> None:
    validated = model.model_validate(payload)

    assert validated is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        INVALID_REQUEST_ERROR_EXAMPLE,
        INVALID_MANIFEST_ERROR_EXAMPLE,
        DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
        SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
        INTEGRITY_CHECK_FAILED_ERROR_EXAMPLE,
        ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE,
    ],
)
def test_error_examples_match_error_envelope_contract(payload: dict[str, object]) -> None:
    envelope = ErrorEnvelope.model_validate(payload)

    assert envelope.error.code
