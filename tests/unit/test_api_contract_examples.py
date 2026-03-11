"""Validation tests for shared OpenAPI examples."""

from __future__ import annotations

from typing import Any

import pytest

from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
    LIST_SUCCESS_EXAMPLE,
    PUBLISH_REQUEST_EXAMPLE,
    RELATIONSHIP_BATCH_SUCCESS_EXAMPLE,
    SEARCH_INVALID_REQUEST_ERROR_EXAMPLE,
    SEARCH_SUCCESS_EXAMPLE,
    SKILL_IDENTITY_SUCCESS_EXAMPLE,
    SKILL_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills import (
    SkillIdentityResponse,
    SkillRelationshipBatchResponse,
    SkillSearchResponse,
    SkillVersionCreateRequest,
    SkillVersionListResponse,
    SkillVersionResponse,
)


@pytest.mark.unit
def test_publish_request_example_matches_request_contract() -> None:
    request = SkillVersionCreateRequest.model_validate(PUBLISH_REQUEST_EXAMPLE)

    assert request.slug == "python.lint"
    assert request.relationships.depends_on


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "model"),
    [
        (SKILL_VERSION_RESPONSE_EXAMPLE, SkillVersionResponse),
        (SKILL_IDENTITY_SUCCESS_EXAMPLE, SkillIdentityResponse),
        (LIST_SUCCESS_EXAMPLE, SkillVersionListResponse),
        (SEARCH_SUCCESS_EXAMPLE, SkillSearchResponse),
        (RELATIONSHIP_BATCH_SUCCESS_EXAMPLE, SkillRelationshipBatchResponse),
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
        DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
        SKILL_NOT_FOUND_ERROR_EXAMPLE,
        SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
        CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
        SEARCH_INVALID_REQUEST_ERROR_EXAMPLE,
    ],
)
def test_error_examples_match_error_envelope_contract(payload: dict[str, object]) -> None:
    envelope = ErrorEnvelope.model_validate(payload)

    assert envelope.error.code
