"""Integration tests for authenticated registry, fetch, discovery, and governance routes."""

from __future__ import annotations

from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from app.main import create_app


@pytest.fixture
def migrated_registry_database(clean_integration_database: str) -> str:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "head")
    return clean_integration_database


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _request(
    slug: str,
    version: str,
    *,
    raw_markdown: str = "# Python Lint\n\nLint Python files.\n",
    trust_tier: str = "untrusted",
    provenance: dict[str, str] | None = None,
    depends_on: list[dict[str, object]] | None = None,
    extends: list[dict[str, object]] | None = None,
    conflicts_with: list[dict[str, object]] | None = None,
    overlaps_with: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "slug": slug,
        "version": version,
        "content": {
            "raw_markdown": raw_markdown,
            "rendered_summary": "Lint Python files.",
        },
        "metadata": {
            "name": "Python Lint",
            "description": "Linting skill",
            "tags": ["python", "lint"],
            "headers": {"runtime": "python"},
            "inputs_schema": {"type": "object"},
            "outputs_schema": {"type": "object"},
            "token_estimate": 128,
            "maturity_score": 0.9,
            "security_score": 0.95,
        },
        "governance": {
            "trust_tier": trust_tier,
            "provenance": provenance,
        },
        "relationships": {
            "depends_on": depends_on or [],
            "extends": extends or [],
            "conflicts_with": conflicts_with or [],
            "overlaps_with": overlaps_with or [],
        },
    }


def _publish(
    client: TestClient,
    payload: dict[str, object],
    *,
    token: str = "publisher-token",
) -> dict[str, object]:
    response = client.post("/skill-versions", json=payload, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _update_status(
    client: TestClient,
    *,
    slug: str,
    version: str,
    status: str,
    token: str = "admin-token",
    note: str | None = None,
) -> dict[str, object]:
    response = client.patch(
        f"/skills/{slug}/versions/{version}/status",
        json={"status": status, "note": note},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.integration
def test_publish_fetch_identity_and_list_versions(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.lint.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, _request(slug, "1.0.0", raw_markdown="# v1\n"))
        _publish(
            client,
            _request(
                slug,
                "2.0.0",
                raw_markdown="# v2\n",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": f"skills/{slug}",
                },
            ),
        )

        identity = client.get(f"/skills/{slug}", headers=_headers("reader-token"))
        versions = client.get(f"/skills/{slug}/versions", headers=_headers("reader-token"))
        metadata = client.get(
            f"/skills/{slug}/versions/2.0.0",
            headers=_headers("reader-token"),
        )
        content = client.get(
            f"/skills/{slug}/versions/2.0.0/content",
            headers=_headers("reader-token"),
        )

    assert identity.status_code == 200
    assert identity.json()["slug"] == slug
    assert identity.json()["status"] == "published"
    assert identity.json()["current_version"]["version"] == "2.0.0"
    assert identity.json()["current_version"]["lifecycle_status"] == "published"
    assert identity.json()["current_version"]["trust_tier"] == "internal"

    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()["versions"]] == ["2.0.0", "1.0.0"]
    assert versions.json()["versions"][0]["trust_tier"] == "internal"

    assert metadata.status_code == 200
    body = metadata.json()
    assert body["slug"] == slug
    assert body["version"] == "2.0.0"
    assert body["lifecycle_status"] == "published"
    assert body["trust_tier"] == "internal"
    assert body["provenance"]["repo_url"] == "https://github.com/example/skills"
    assert body["content"]["size_bytes"] == len(b"# v2\n")
    assert body["content_download_path"] == f"/skills/{slug}/versions/2.0.0/content"

    assert content.status_code == 200
    assert content.text == "# v2\n"
    assert content.headers["etag"] == body["content"]["checksum"]["digest"]
    assert content.headers["cache-control"] == "public, immutable"


@pytest.mark.integration
def test_authentication_and_scope_failures_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.auth.{uuid4().hex}"
    payload = _request(slug, "1.0.0")

    with TestClient(create_app()) as client:
        missing = client.post("/skill-versions", json=payload)
        invalid = client.post(
            "/skill-versions",
            json=payload,
            headers=_headers("not-a-real-token"),
        )
        insufficient = client.post(
            "/skill-versions",
            json=payload,
            headers=_headers("reader-token"),
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_AUTH_TOKEN"
    assert insufficient.status_code == 403
    assert insufficient.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.integration
def test_publish_enforces_trust_tier_policy(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex

    with TestClient(create_app()) as client:
        internal_without_provenance = client.post(
            "/skill-versions",
            json=_request(f"python.internal.{suffix}", "1.0.0", trust_tier="internal"),
            headers=_headers("publisher-token"),
        )
        verified_without_admin = client.post(
            "/skill-versions",
            json=_request(
                f"python.verified.{suffix}",
                "1.0.0",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": "skills/python.verified",
                },
            ),
            headers=_headers("publisher-token"),
        )
        verified_with_admin = client.post(
            "/skill-versions",
            json=_request(
                f"python.verified-admin.{suffix}",
                "1.0.0",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "bbccddeeff00112233445566778899aabbccdde0",
                    "tree_path": "skills/python.verified-admin",
                },
            ),
            headers=_headers("admin-token"),
        )

    assert internal_without_provenance.status_code == 403
    assert internal_without_provenance.json()["error"]["code"] == "POLICY_PROVENANCE_REQUIRED"
    assert verified_without_admin.status_code == 403
    assert verified_without_admin.json()["error"]["code"] == "POLICY_PUBLISH_FORBIDDEN"
    assert verified_with_admin.status_code == 201
    assert verified_with_admin.json()["trust_tier"] == "verified"


@pytest.mark.integration
def test_status_transitions_recompute_current_default(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.lifecycle.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, _request(slug, "1.0.0"))
        _publish(client, _request(slug, "2.0.0"))

        deprecated = _update_status(client, slug=slug, version="2.0.0", status="deprecated")
        identity_after_deprecate = client.get(f"/skills/{slug}", headers=_headers("reader-token"))

        archived = _update_status(client, slug=slug, version="1.0.0", status="archived")
        identity_after_archive = client.get(f"/skills/{slug}", headers=_headers("reader-token"))

        invalid_transition = client.patch(
            f"/skills/{slug}/versions/1.0.0/status",
            json={"status": "published"},
            headers=_headers("admin-token"),
        )

    assert deprecated["status"] == "deprecated"
    assert deprecated["is_current_default"] is False
    assert identity_after_deprecate.status_code == 200
    assert identity_after_deprecate.json()["current_version"]["version"] == "1.0.0"
    assert identity_after_deprecate.json()["status"] == "published"

    assert archived["status"] == "archived"
    assert archived["is_current_default"] is False
    assert identity_after_archive.status_code == 200
    assert identity_after_archive.json()["current_version"]["version"] == "2.0.0"
    assert identity_after_archive.json()["status"] == "deprecated"

    assert invalid_transition.status_code == 403
    assert invalid_transition.json()["error"]["code"] == "POLICY_STATUS_TRANSITION_FORBIDDEN"


@pytest.mark.integration
def test_relationship_batch_returns_all_edge_families_and_redacts_hidden_targets(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    slug = f"python.source.{suffix}"
    dependency_slug = f"python.dep.{suffix}"
    extension_slug = f"python.ext.{suffix}"
    overlap_slug = f"python.overlap.{suffix}"

    with TestClient(create_app()) as client:
        _publish(client, _request(dependency_slug, "1.0.0"))
        _publish(client, _request(extension_slug, "2.0.0"))
        _publish(client, _request(overlap_slug, "3.0.0"))
        _publish(
            client,
            _request(
                slug,
                "1.0.0",
                depends_on=[{"slug": dependency_slug, "version": "1.0.0"}],
                extends=[{"slug": extension_slug, "version": "2.0.0"}],
                conflicts_with=[{"slug": "python.conflict", "version": "9.9.9"}],
                overlaps_with=[{"slug": overlap_slug, "version": "3.0.0"}],
            ),
        )

        _update_status(client, slug=dependency_slug, version="1.0.0", status="archived")

        response = client.post(
            "/resolution/relationships:batch",
            json={"coordinates": [{"slug": slug, "version": "1.0.0"}]},
            headers=_headers("reader-token"),
        )
        admin_response = client.post(
            "/resolution/relationships:batch",
            json={"coordinates": [{"slug": slug, "version": "1.0.0"}]},
            headers=_headers("admin-token"),
        )

    assert response.status_code == 200
    relationships = response.json()["results"][0]["relationships"]
    assert [item["edge_type"] for item in relationships] == [
        "depends_on",
        "extends",
        "conflicts_with",
        "overlaps_with",
    ]
    assert relationships[0]["selector"]["slug"] == dependency_slug
    assert relationships[0]["target_version"] is None
    assert relationships[1]["target_version"]["slug"] == extension_slug
    assert relationships[2]["target_version"] is None
    assert relationships[3]["target_version"]["slug"] == overlap_slug

    assert admin_response.status_code == 200
    assert admin_response.json()["results"][0]["relationships"][0]["target_version"]["slug"] == (
        dependency_slug
    )


@pytest.mark.integration
def test_discovery_filters_and_exact_reads_follow_governance_visibility(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    published_slug = f"python.discovery.published.{suffix}"
    deprecated_slug = f"python.discovery.deprecated.{suffix}"
    archived_slug = f"python.discovery.archived.{suffix}"
    trusted_slug = f"python.discovery.internal.{suffix}"

    with TestClient(create_app()) as client:
        _publish(client, _request(published_slug, "1.0.0", raw_markdown="# published\n"))
        _publish(client, _request(deprecated_slug, "1.0.0", raw_markdown="# deprecated\n"))
        _publish(client, _request(archived_slug, "1.0.0", raw_markdown="# archived\n"))
        _publish(
            client,
            _request(
                trusted_slug,
                "1.0.0",
                raw_markdown="# trusted\n",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "ddeeff00112233445566778899aabbccddeeff00",
                    "tree_path": f"skills/{trusted_slug}",
                },
            ),
        )

        _update_status(client, slug=deprecated_slug, version="1.0.0", status="deprecated")
        _update_status(client, slug=archived_slug, version="1.0.0", status="archived")

        default_search = client.get(
            "/discovery/skills/search",
            params={"q": "python.discovery"},
            headers=_headers("reader-token"),
        )
        deprecated_search = client.get(
            "/discovery/skills/search",
            params={"q": "python.discovery", "status": "deprecated"},
            headers=_headers("reader-token"),
        )
        archived_forbidden = client.get(
            "/discovery/skills/search",
            params={"q": "python.discovery", "status": "archived"},
            headers=_headers("reader-token"),
        )
        archived_admin = client.get(
            "/discovery/skills/search",
            params={"q": "python.discovery", "status": "archived"},
            headers=_headers("admin-token"),
        )
        internal_only = client.get(
            "/discovery/skills/search",
            params={"q": "python.discovery", "trust_tier": "internal"},
            headers=_headers("reader-token"),
        )
        archived_fetch = client.get(
            f"/skills/{archived_slug}/versions/1.0.0",
            headers=_headers("reader-token"),
        )
        archived_fetch_admin = client.get(
            f"/skills/{archived_slug}/versions/1.0.0",
            headers=_headers("admin-token"),
        )

    assert default_search.status_code == 200
    assert {item["slug"] for item in default_search.json()["results"]} == {
        published_slug,
        trusted_slug,
    }

    assert deprecated_search.status_code == 200
    assert {item["slug"] for item in deprecated_search.json()["results"]} == {deprecated_slug}

    assert archived_forbidden.status_code == 403
    assert archived_forbidden.json()["error"]["code"] == "POLICY_DISCOVERY_FORBIDDEN"

    assert archived_admin.status_code == 200
    assert {item["slug"] for item in archived_admin.json()["results"]} == {archived_slug}

    assert internal_only.status_code == 200
    assert {item["slug"] for item in internal_only.json()["results"]} == {trusted_slug}

    assert archived_fetch.status_code == 403
    assert archived_fetch.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_fetch_admin.status_code == 200
    assert archived_fetch_admin.json()["lifecycle_status"] == "archived"


@pytest.mark.integration
def test_publish_rejects_invalid_dependency_constraint(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.invalid.{uuid4().hex}"

    with TestClient(create_app()) as client:
        response = client.post(
            "/skill-versions",
            json=_request(
                slug,
                "1.0.0",
                depends_on=[{"slug": "python.base", "version_constraint": "latest"}],
            ),
            headers=_headers("publisher-token"),
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_publish_backfills_normalized_search_documents_with_governance(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.searchdoc.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            _request(
                slug,
                "1.0.0",
                raw_markdown="# Search Doc\n",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "ccddeeff00112233445566778899aabbccddeeff",
                    "tree_path": f"skills/{slug}",
                },
            ),
        )

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            slug,
                            normalized_slug,
                            content_size_bytes,
                            lifecycle_status,
                            trust_tier
                        FROM skill_search_documents
                        WHERE slug = :slug
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            assert row["slug"] == slug
            assert row["normalized_slug"] == slug
            assert row["content_size_bytes"] == len(b"# Search Doc\n")
            assert row["lifecycle_status"] == "published"
            assert row["trust_tier"] == "internal"
    finally:
        engine.dispose()
