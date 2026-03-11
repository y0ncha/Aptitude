"""Typed application settings loaded from environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.governance import CallerScope, LifecycleStatus, PolicyProfile, PublishRule, TrustTier


class PublishRuleSettings(BaseModel):
    """Serializable publish-rule configuration for one trust tier."""

    required_scope: CallerScope
    provenance_required: bool = False


def _default_publish_rules() -> dict[TrustTier, PublishRuleSettings]:
    return {
        "untrusted": PublishRuleSettings(required_scope="publish"),
        "internal": PublishRuleSettings(required_scope="publish", provenance_required=True),
        "verified": PublishRuleSettings(required_scope="admin", provenance_required=True),
    }


def _default_lifecycle_transitions() -> dict[LifecycleStatus, tuple[LifecycleStatus, ...]]:
    return {
        "published": ("deprecated", "archived"),
        "deprecated": ("published", "archived"),
        "archived": (),
    }


class PolicyProfileSettings(BaseModel):
    """Serializable policy-profile configuration loaded from settings."""

    publish_rules: dict[TrustTier, PublishRuleSettings] = Field(
        default_factory=_default_publish_rules
    )
    lifecycle_transitions: dict[LifecycleStatus, tuple[LifecycleStatus, ...]] = Field(
        default_factory=_default_lifecycle_transitions
    )
    discovery_default_statuses: tuple[LifecycleStatus, ...] = ("published",)
    discovery_read_statuses: tuple[LifecycleStatus, ...] = ("published", "deprecated")
    discovery_admin_statuses: tuple[LifecycleStatus, ...] = (
        "published",
        "deprecated",
        "archived",
    )
    exact_read_statuses: tuple[LifecycleStatus, ...] = ("published", "deprecated")


class Settings(BaseSettings):
    """Application configuration values."""

    database_url: str = Field(alias="DATABASE_URL")
    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_name: str = Field(default="aptitude-server", alias="APP_NAME")
    artifact_root_dir: str = Field(default="./.data/artifacts", alias="ARTIFACT_ROOT_DIR")
    auth_tokens: dict[str, tuple[CallerScope, ...]] = Field(
        default_factory=dict,
        alias="AUTH_TOKENS_JSON",
    )
    policy_profiles: dict[str, PolicyProfileSettings] = Field(
        default_factory=dict,
        alias="POLICY_PROFILES_JSON",
    )
    active_policy_profile: str = Field(default="default", alias="ACTIVE_POLICY_PROFILE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_active_policy_profile(self) -> Settings:
        if self.active_policy_profile not in self.effective_policy_profiles:
            raise ValueError(
                f"Unknown active policy profile: {self.active_policy_profile!r}. "
                "Define it in POLICY_PROFILES_JSON or use 'default'."
            )
        return self

    @property
    def effective_policy_profiles(self) -> dict[str, PolicyProfileSettings]:
        """Return built-in and settings-supplied policy profiles."""
        return {"default": PolicyProfileSettings(), **self.policy_profiles}

    @property
    def active_policy(self) -> PolicyProfile:
        """Return the configured active policy profile as a core domain object."""
        configured = self.effective_policy_profiles[self.active_policy_profile]
        return PolicyProfile(
            name=self.active_policy_profile,
            publish_rules={
                tier: PublishRule(
                    required_scope=rule.required_scope,
                    provenance_required=rule.provenance_required,
                )
                for tier, rule in configured.publish_rules.items()
            },
            lifecycle_transitions=configured.lifecycle_transitions,
            discovery_default_statuses=configured.discovery_default_statuses,
            discovery_read_statuses=configured.discovery_read_statuses,
            discovery_admin_statuses=configured.discovery_admin_statuses,
            exact_read_statuses=configured.exact_read_statuses,
        )


@lru_cache
def get_settings() -> Settings:
    """Return memoized settings for the running process."""
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear cached settings; mainly used by tests and startup wiring."""
    get_settings.cache_clear()
