"""Unit tests for normalized skill registry core behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import CallerIdentity, GovernancePolicy, build_default_policy_profile
from app.core.ports import (
    CreateSkillVersionRecord,
    StoredSkillIdentity,
    StoredSkillVersion,
    StoredSkillVersionStatus,
    StoredSkillVersionSummary,
)
from app.core.skill_registry import (
    CreateSkillVersionCommand,
    DuplicateSkillVersionError,
    SkillContentInput,
    SkillMetadataInput,
    SkillNotFoundError,
    SkillRegistryService,
    SkillRelationshipsInput,
)


class FakeRegistry:
    """In-memory stub for core registry tests."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StoredSkillVersion] = {}

    def version_exists(self, *, slug: str, version: str) -> bool:
        return (slug, version) in self._records

    def create_version(self, *, record: CreateSkillVersionRecord) -> StoredSkillVersion:
        key = (record.slug, record.version)
        if key in self._records:
            raise DuplicateSkillVersionError(slug=record.slug, version=record.version)

        stored = StoredSkillVersion(
            slug=record.slug,
            version=record.version,
            version_checksum_digest=record.version_checksum_digest,
            content_checksum_digest=record.content.checksum_digest,
            content_size_bytes=record.content.size_bytes,
            rendered_summary=record.content.rendered_summary,
            name=record.metadata.name,
            description=record.metadata.description,
            tags=record.metadata.tags,
            headers=record.metadata.headers,
            inputs_schema=record.metadata.inputs_schema,
            outputs_schema=record.metadata.outputs_schema,
            token_estimate=record.metadata.token_estimate,
            maturity_score=record.metadata.maturity_score,
            security_score=record.metadata.security_score,
            lifecycle_status="published",
            trust_tier=record.governance.trust_tier,
            provenance=record.governance.provenance,
            lifecycle_changed_at=datetime.now(tz=UTC),
            published_at=datetime.now(tz=UTC),
            relationships=(),
        )
        self._records[key] = stored
        return stored

    def get_skill(self, *, slug: str) -> StoredSkillIdentity | None:
        versions = [
            record for (stored_slug, _), record in self._records.items() if stored_slug == slug
        ]
        if not versions:
            return None
        current = max(versions, key=lambda item: (item.published_at, item.version))
        return StoredSkillIdentity(
            slug=slug,
            current_version=current.version,
            created_at=current.published_at,
            updated_at=current.published_at,
        )

    def list_versions(self, *, slug: str) -> tuple[StoredSkillVersionSummary, ...]:
        return tuple(
            StoredSkillVersionSummary(
                slug=record.slug,
                version=record.version,
                version_checksum_digest=record.version_checksum_digest,
                content_checksum_digest=record.content_checksum_digest,
                content_size_bytes=record.content_size_bytes,
                rendered_summary=record.rendered_summary,
                name=record.name,
                description=record.description,
                tags=record.tags,
                lifecycle_status=record.lifecycle_status,
                trust_tier=record.trust_tier,
                published_at=record.published_at,
            )
            for (stored_slug, _), record in self._records.items()
            if stored_slug == slug
        )

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        return self._records.get((slug, version))

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: str,
    ) -> StoredSkillVersionStatus | None:
        record = self._records.get((slug, version))
        if record is None:
            return None
        updated = StoredSkillVersion(
            slug=record.slug,
            version=record.version,
            version_checksum_digest=record.version_checksum_digest,
            content_checksum_digest=record.content_checksum_digest,
            content_size_bytes=record.content_size_bytes,
            rendered_summary=record.rendered_summary,
            name=record.name,
            description=record.description,
            tags=record.tags,
            headers=record.headers,
            inputs_schema=record.inputs_schema,
            outputs_schema=record.outputs_schema,
            token_estimate=record.token_estimate,
            maturity_score=record.maturity_score,
            security_score=record.security_score,
            lifecycle_status=lifecycle_status,
            trust_tier=record.trust_tier,
            provenance=record.provenance,
            lifecycle_changed_at=datetime.now(tz=UTC),
            published_at=record.published_at,
            relationships=record.relationships,
        )
        self._records[(slug, version)] = updated
        return StoredSkillVersionStatus(
            slug=slug,
            version=version,
            lifecycle_status=lifecycle_status,
            trust_tier=updated.trust_tier,
            lifecycle_changed_at=updated.lifecycle_changed_at,
            is_current_default=True,
        )


class FakeAuditRecorder:
    """Audit stub collecting event names."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        self.events.append(event_type)


def _command(slug: str, version: str) -> CreateSkillVersionCommand:
    return CreateSkillVersionCommand(
        slug=slug,
        version=version,
        content=SkillContentInput(raw_markdown="# Python Lint\n"),
        metadata=SkillMetadataInput(
            name="Python Lint",
            description="Linting skill",
            tags=("python", "lint"),
        ),
        relationships=SkillRelationshipsInput(),
    )


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _publish_caller() -> CallerIdentity:
    return CallerIdentity(token="publish", scopes=frozenset({"publish", "read"}))


def _read_caller() -> CallerIdentity:
    return CallerIdentity(token="read", scopes=frozenset({"read"}))


@pytest.mark.unit
def test_publish_version_returns_checksum_and_records_audit() -> None:
    registry = FakeRegistry()
    audit_recorder = FakeAuditRecorder()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    response = service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python.lint", version="1.0.0"),
    )

    assert response.slug == "python.lint"
    assert response.version == "1.0.0"
    assert response.version_checksum.algorithm == "sha256"
    assert response.content.size_bytes == len(b"# Python Lint\n")
    assert "skill.version_published" in audit_recorder.events


@pytest.mark.unit
def test_publish_version_rejects_duplicates() -> None:
    registry = FakeRegistry()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    command = _command(slug="python.lint", version="1.0.0")
    service.publish_version(caller=_publish_caller(), command=command)

    with pytest.raises(DuplicateSkillVersionError):
        service.publish_version(caller=_publish_caller(), command=command)


@pytest.mark.unit
def test_get_skill_raises_not_found_for_unknown_slug() -> None:
    service = SkillRegistryService(
        registry=FakeRegistry(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillNotFoundError):
        service.get_skill(caller=_read_caller(), slug="missing.skill")
