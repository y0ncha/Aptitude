"""Governance models and policy evaluation for registry operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CallerScope = Literal["read", "publish", "admin"]
LifecycleStatus = Literal["published", "deprecated", "archived"]
TrustTier = Literal["untrusted", "internal", "verified"]

ALL_CALLER_SCOPES: tuple[CallerScope, ...] = ("read", "publish", "admin")
ALL_LIFECYCLE_STATUSES: tuple[LifecycleStatus, ...] = ("published", "deprecated", "archived")
ALL_TRUST_TIERS: tuple[TrustTier, ...] = ("untrusted", "internal", "verified")


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    """Authenticated caller context available to the interface and core layers."""

    token: str
    scopes: frozenset[CallerScope]

    def has_scope(self, scope: CallerScope) -> bool:
        """Return whether the caller can perform an operation requiring ``scope``."""
        return "admin" in self.scopes or scope in self.scopes


@dataclass(frozen=True, slots=True)
class ProvenanceMetadata:
    """Minimal publish-time provenance captured alongside immutable versions."""

    repo_url: str
    commit_sha: str
    tree_path: str | None = None


@dataclass(frozen=True, slots=True)
class SkillGovernanceInput:
    """Publish-time governance input owned by the core layer."""

    trust_tier: TrustTier = "untrusted"
    provenance: ProvenanceMetadata | None = None


@dataclass(frozen=True, slots=True)
class PublishRule:
    """Trust-tier-specific publish requirements."""

    required_scope: CallerScope
    provenance_required: bool = False


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    """Named policy profile resolved from settings."""

    name: str
    publish_rules: dict[TrustTier, PublishRule]
    lifecycle_transitions: dict[LifecycleStatus, tuple[LifecycleStatus, ...]]
    discovery_default_statuses: tuple[LifecycleStatus, ...]
    discovery_read_statuses: tuple[LifecycleStatus, ...]
    discovery_admin_statuses: tuple[LifecycleStatus, ...]
    exact_read_statuses: tuple[LifecycleStatus, ...]


class GovernanceError(RuntimeError):
    """Base governance-domain error."""


class PolicyViolation(GovernanceError):
    """Raised when policy blocks an otherwise valid request."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class GovernancePolicy:
    """Evaluate registry governance rules for publish, read, and lifecycle operations."""

    def __init__(self, *, profile: PolicyProfile) -> None:
        self._profile = profile
        # Validate that the profile defines publish rules for all trust tiers up-front
        missing_tiers = [tier for tier in ALL_TRUST_TIERS if tier not in profile.publish_rules]
        if missing_tiers:
            raise PolicyViolation(
                code="POLICY_PROFILE_INVALID",
                message="Policy profile is missing publish rules for some trust tiers.",
                details={
                    "profile": profile.name,
                    "missing_trust_tiers": tuple(missing_tiers),
                },
            )

    @property
    def profile_name(self) -> str:
        """Return the active policy profile name."""
        return self._profile.name

    def evaluate_publish(
        self,
        *,
        caller: CallerIdentity,
        governance: SkillGovernanceInput,
    ) -> None:
        """Validate publish permissions for the requested trust tier."""
        rule = self._profile.publish_rules[governance.trust_tier]
        if not caller.has_scope(rule.required_scope):
            raise PolicyViolation(
                code="POLICY_PUBLISH_FORBIDDEN",
                message="Caller is not allowed to publish with the requested trust tier.",
                details={
                    "required_scope": rule.required_scope,
                    "trust_tier": governance.trust_tier,
                },
            )
        if rule.provenance_required and governance.provenance is None:
            raise PolicyViolation(
                code="POLICY_PROVENANCE_REQUIRED",
                message="Provenance metadata is required for the requested trust tier.",
                details={"trust_tier": governance.trust_tier},
            )

    def evaluate_transition(
        self,
        *,
        caller: CallerIdentity,
        current_status: LifecycleStatus,
        next_status: LifecycleStatus,
    ) -> None:
        """Validate lifecycle transitions for status updates."""
        if not caller.has_scope("admin"):
            raise PolicyViolation(
                code="POLICY_STATUS_TRANSITION_FORBIDDEN",
                message="Caller is not allowed to update lifecycle status.",
                details={"required_scope": "admin"},
            )

        allowed_targets = self._profile.lifecycle_transitions.get(current_status, ())
        if next_status not in allowed_targets:
            raise PolicyViolation(
                code="POLICY_STATUS_TRANSITION_FORBIDDEN",
                message="The requested lifecycle transition is not allowed.",
                details={
                    "current_status": current_status,
                    "next_status": next_status,
                    "allowed_targets": list(allowed_targets),
                },
            )

    def ensure_exact_read_allowed(
        self,
        *,
        caller: CallerIdentity,
        lifecycle_status: LifecycleStatus,
    ) -> None:
        """Validate exact-read visibility for one stored version."""
        if lifecycle_status in self._profile.exact_read_statuses and caller.has_scope("read"):
            return
        if lifecycle_status == "archived" and caller.has_scope("admin"):
            return
        raise PolicyViolation(
            code="POLICY_EXACT_READ_FORBIDDEN",
            message="Caller is not allowed to read this lifecycle state.",
            details={"lifecycle_status": lifecycle_status},
        )

    def is_visible_in_list(
        self,
        *,
        caller: CallerIdentity,
        lifecycle_status: LifecycleStatus,
    ) -> bool:
        """Return whether a version is visible in identity/list responses."""
        try:
            self.ensure_exact_read_allowed(caller=caller, lifecycle_status=lifecycle_status)
        except PolicyViolation:
            return False
        return True

    def resolve_discovery_statuses(
        self,
        *,
        caller: CallerIdentity,
        requested_statuses: tuple[LifecycleStatus, ...],
    ) -> tuple[LifecycleStatus, ...]:
        """Return effective lifecycle filters for discovery."""
        if not requested_statuses:
            return self._profile.discovery_default_statuses

        allowed_statuses = (
            self._profile.discovery_admin_statuses
            if caller.has_scope("admin")
            else self._profile.discovery_read_statuses
        )
        forbidden = [status for status in requested_statuses if status not in allowed_statuses]
        if forbidden:
            raise PolicyViolation(
                code="POLICY_DISCOVERY_FORBIDDEN",
                message="Caller is not allowed to search the requested lifecycle states.",
                details={"requested_statuses": forbidden},
            )
        return requested_statuses

    def resolve_discovery_trust_tiers(
        self,
        *,
        requested_trust_tiers: tuple[TrustTier, ...],
    ) -> tuple[TrustTier, ...]:
        """Return effective trust-tier filters for discovery."""
        return requested_trust_tiers or ALL_TRUST_TIERS


def build_default_policy_profile() -> PolicyProfile:
    """Return the built-in default policy profile."""
    return PolicyProfile(
        name="default",
        publish_rules={
            "untrusted": PublishRule(required_scope="publish", provenance_required=False),
            "internal": PublishRule(required_scope="publish", provenance_required=True),
            "verified": PublishRule(required_scope="admin", provenance_required=True),
        },
        lifecycle_transitions={
            "published": ("deprecated", "archived"),
            "deprecated": ("published", "archived"),
            "archived": (),
        },
        discovery_default_statuses=("published",),
        discovery_read_statuses=("published", "deprecated"),
        discovery_admin_statuses=("published", "deprecated", "archived"),
        exact_read_statuses=("published", "deprecated"),
    )
