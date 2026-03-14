"""Unit tests for exact immutable fetch behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    build_default_policy_profile,
)
from app.core.ports import StoredSkillVersion, StoredSkillVersionContent
from app.core.skill_fetch import SkillFetchService
from app.core.skill_models import SkillVersionNotFoundError


class FakeVersionReader:
    """Stub version reader keyed by exact immutable coordinates."""

    def __init__(
        self,
        *,
        version: StoredSkillVersion | None = None,
        content: StoredSkillVersionContent | None = None,
    ) -> None:
        self._version = version
        self._content = content

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        if self._version is None:
            return None
        if (self._version.slug, self._version.version) != (slug, version):
            return None
        return self._version

    def get_version_content(
        self,
        *,
        slug: str,
        version: str,
    ) -> StoredSkillVersionContent | None:
        if self._content is None:
            return None
        if (self._content.slug, self._content.version) != (slug, version):
            return None
        return self._content


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _caller(*scopes: str) -> CallerIdentity:
    return CallerIdentity(token="token", scopes=frozenset(scopes))


def _stored_version(*, lifecycle_status: str = "published") -> StoredSkillVersion:
    return StoredSkillVersion(
        slug="python.lint",
        version="1.0.0",
        version_checksum_digest="version-digest",
        content_checksum_digest="content-digest",
        content_size_bytes=18,
        rendered_summary="Lint Python files.",
        name="Python Lint",
        description="Linting skill",
        tags=("python", "lint"),
        headers={"runtime": "python"},
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        token_estimate=128,
        maturity_score=0.9,
        security_score=0.95,
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
        provenance=None,
        lifecycle_changed_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        published_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        relationships=(),
    )


def _stored_content(*, lifecycle_status: str = "published") -> StoredSkillVersionContent:
    return StoredSkillVersionContent(
        slug="python.lint",
        version="1.0.0",
        raw_markdown="# Python Lint\n",
        checksum_digest="content-digest",
        size_bytes=len(b"# Python Lint\n"),
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
    )


@pytest.mark.unit
def test_get_version_metadata_returns_immutable_detail() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(version=_stored_version()),
        governance_policy=_governance_policy(),
    )

    detail = service.get_version_metadata(
        caller=_caller("read"),
        slug="python.lint",
        version="1.0.0",
    )

    assert detail.slug == "python.lint"
    assert detail.version == "1.0.0"
    assert detail.content.checksum.digest == "content-digest"


@pytest.mark.unit
def test_get_content_returns_markdown_document() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(content=_stored_content()),
        governance_policy=_governance_policy(),
    )

    document = service.get_content(
        caller=_caller("read"),
        slug="python.lint",
        version="1.0.0",
    )

    assert document.raw_markdown == "# Python Lint\n"
    assert document.checksum.digest == "content-digest"
    assert document.size_bytes == len(b"# Python Lint\n")


@pytest.mark.unit
def test_get_version_metadata_raises_not_found_for_unknown_coordinate() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.get_version_metadata(
            caller=_caller("read"),
            slug="python.missing",
            version="9.9.9",
        )


@pytest.mark.unit
def test_get_content_applies_exact_read_policy() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(content=_stored_content(lifecycle_status="archived")),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(PolicyViolation):
        service.get_content(
            caller=_caller("read"),
            slug="python.lint",
            version="1.0.0",
        )
