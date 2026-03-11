"""Unit tests for governance policy and settings behavior."""

from __future__ import annotations

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    SkillGovernanceInput,
)
from app.core.settings import Settings


@pytest.mark.unit
def test_settings_parse_auth_tokens_and_policy_profiles_from_json() -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
            "AUTH_TOKENS_JSON": {
                "reader": ["read"],
                "publisher": ["publish"],
                "admin": ["admin"],
            },
            "POLICY_PROFILES_JSON": {
                "strict": {
                    "publish_rules": {
                        "untrusted": {"required_scope": "admin", "provenance_required": True},
                        "internal": {"required_scope": "admin", "provenance_required": True},
                        "verified": {"required_scope": "admin", "provenance_required": True},
                    }
                }
            },
            "ACTIVE_POLICY_PROFILE": "strict",
        }
    )

    assert settings.auth_tokens["reader"] == ("read",)
    assert settings.active_policy_profile == "strict"
    assert (
        settings.effective_policy_profiles["strict"].publish_rules["untrusted"].required_scope
        == "admin"
    )


@pytest.mark.unit
def test_governance_policy_blocks_missing_provenance_for_internal_publish() -> None:
    policy = GovernancePolicy(profile=Settings.model_validate(
        {"DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"}
    ).active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.evaluate_publish(
            caller=CallerIdentity(token="publisher", scopes=frozenset({"publish"})),
            governance=SkillGovernanceInput(trust_tier="internal"),
        )

    assert exc_info.value.code == "POLICY_PROVENANCE_REQUIRED"


@pytest.mark.unit
def test_governance_policy_rejects_archived_to_published_transition() -> None:
    policy = GovernancePolicy(profile=Settings.model_validate(
        {"DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"}
    ).active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.evaluate_transition(
            caller=CallerIdentity(token="admin", scopes=frozenset({"admin"})),
            current_status="archived",
            next_status="published",
        )

    assert exc_info.value.code == "POLICY_STATUS_TRANSITION_FORBIDDEN"
