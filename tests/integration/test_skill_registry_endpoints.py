"""Integration tests for the hard-cut registry API surface."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default as email_policy
from typing import Any
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
    name: str = "Python Lint",
    description: str = "Linting skill",
    tags: list[str] | None = None,
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
            "name": name,
            "description": description,
            "tags": tags or ["python", "lint"],
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


def _parse_multipart_parts(response: Any) -> list[Any]:
    content_type = response.headers["content-type"]
    raw = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + response.content
    message = BytesParser(policy=email_policy).parsebytes(raw)
    assert message.is_multipart()
    return list(message.iter_parts())


@pytest.mark.integration
def test_publish_discovery_resolution_and_batch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    dependency_slug = f"python.dep.{suffix}"
    source_slug = f"python.source.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            _request(
                dependency_slug,
                "1.0.0",
                name="Python Dependency",
                description="Base dependency",
            ),
        )
        published = _publish(
            client,
            _request(
                source_slug,
                "2.0.0",
                raw_markdown="# v2\n",
                name="Python Hard Cut Source",
                description="Hard cut discovery candidate",
                tags=["python", "lint", "hard-cut"],
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": f"skills/{source_slug}",
                },
                depends_on=[{"slug": dependency_slug, "version": "1.0.0"}],
                extends=[{"slug": "python.base", "version": "1.0.0"}],
            ),
        )

        discovery = client.post(
            "/discovery",
            json={
                "name": "  Python Hard Cut Source  ",
                "description": "  Hard cut discovery candidate  ",
                "tags": ["python", "hard-cut", "python"],
            },
            headers=_headers("reader-token"),
        )
        resolution = client.get(
            f"/resolution/{source_slug}/2.0.0",
            headers=_headers("reader-token"),
        )
        metadata = client.post(
            "/fetch/metadata:batch",
            json={
                "coordinates": [
                    {"slug": source_slug, "version": "2.0.0"},
                    {"slug": "python.missing", "version": "9.9.9"},
                ]
            },
            headers=_headers("reader-token"),
        )
        content = client.post(
            "/fetch/content:batch",
            json={
                "coordinates": [
                    {"slug": source_slug, "version": "2.0.0"},
                    {"slug": "python.missing", "version": "9.9.9"},
                ]
            },
            headers=_headers("reader-token"),
        )

    assert "relationships" not in published
    assert "content_download_path" not in published

    assert discovery.status_code == 200
    assert discovery.json()["candidates"] == [source_slug]

    assert resolution.status_code == 200
    resolution_body = resolution.json()
    assert resolution_body == {
        "slug": source_slug,
        "version": "2.0.0",
        "depends_on": [
            {
                "slug": dependency_slug,
                "version": "1.0.0",
                "version_constraint": None,
                "optional": None,
                "markers": [],
            }
        ],
    }

    assert metadata.status_code == 200
    metadata_body = metadata.json()
    assert [item["status"] for item in metadata_body["results"]] == ["found", "not_found"]
    assert metadata_body["results"][0]["coordinate"] == {"slug": source_slug, "version": "2.0.0"}
    assert metadata_body["results"][0]["item"]["slug"] == source_slug
    assert metadata_body["results"][0]["item"]["version"] == "2.0.0"
    assert "relationships" not in metadata_body["results"][0]["item"]
    assert "content_download_path" not in metadata_body["results"][0]["item"]
    assert metadata_body["results"][1]["item"] is None

    assert content.status_code == 200
    assert content.headers["content-type"].startswith("multipart/mixed; boundary=")
    parts = _parse_multipart_parts(content)
    assert len(parts) == 2
    assert parts[0]["X-Aptitude-Slug"] == source_slug
    assert parts[0]["X-Aptitude-Version"] == "2.0.0"
    assert parts[0]["X-Aptitude-Status"] == "found"
    assert parts[0]["ETag"] == published["content"]["checksum"]["digest"]
    assert parts[0]["Cache-Control"] == "public, immutable"
    assert parts[0]["Content-Length"] == str(len(b"# v2\n"))
    assert parts[0].get_payload(decode=True).decode("utf-8") == "# v2\n"
    assert parts[1]["X-Aptitude-Slug"] == "python.missing"
    assert parts[1]["X-Aptitude-Version"] == "9.9.9"
    assert parts[1]["X-Aptitude-Status"] == "not_found"
    assert parts[1].get_payload(decode=True) == b""


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
        discovery_missing = client.post(
            "/discovery",
            json={"name": "Python Lint"},
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_AUTH_TOKEN"
    assert insufficient.status_code == 403
    assert insufficient.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    assert discovery_missing.status_code == 401
    assert discovery_missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


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
        archived = _update_status(client, slug=slug, version="1.0.0", status="archived")
        invalid_transition = client.patch(
            f"/skills/{slug}/versions/1.0.0/status",
            json={"status": "published"},
            headers=_headers("admin-token"),
        )

    assert deprecated["status"] == "deprecated"
    assert deprecated["is_current_default"] is False
    assert archived["status"] == "archived"
    assert archived["is_current_default"] is False
    assert invalid_transition.status_code == 403
    assert invalid_transition.json()["error"]["code"] == "POLICY_STATUS_TRANSITION_FORBIDDEN"


@pytest.mark.integration
def test_governance_applies_to_discovery_resolution_and_batch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    published_slug = f"python.discovery.published.{suffix}"
    deprecated_slug = f"python.discovery.deprecated.{suffix}"
    archived_slug = f"python.discovery.archived.{suffix}"
    internal_slug = f"python.discovery.internal.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            _request(
                published_slug,
                "1.0.0",
                name="Python Discovery Published",
                description="Published discovery candidate",
            ),
        )
        _publish(
            client,
            _request(
                deprecated_slug,
                "1.0.0",
                name="Python Discovery Deprecated",
                description="Deprecated discovery candidate",
            ),
        )
        _publish(
            client,
            _request(
                archived_slug,
                "1.0.0",
                name="Python Discovery Archived",
                description="Archived discovery candidate",
            ),
        )
        _publish(
            client,
            _request(
                internal_slug,
                "1.0.0",
                name="Python Discovery Internal",
                description="Internal discovery candidate",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "ddeeff00112233445566778899aabbccddeeff00",
                    "tree_path": f"skills/{internal_slug}",
                },
            ),
        )

        _update_status(client, slug=deprecated_slug, version="1.0.0", status="deprecated")
        _update_status(client, slug=archived_slug, version="1.0.0", status="archived")

        published_discovery = client.post(
            "/discovery",
            json={"name": "Python Discovery"},
            headers=_headers("reader-token"),
        )
        archived_resolution_forbidden = client.get(
            f"/resolution/{archived_slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        archived_resolution_admin = client.get(
            f"/resolution/{archived_slug}/1.0.0",
            headers=_headers("admin-token"),
        )
        archived_metadata_forbidden = client.post(
            "/fetch/metadata:batch",
            json={"coordinates": [{"slug": archived_slug, "version": "1.0.0"}]},
            headers=_headers("reader-token"),
        )
        archived_metadata_admin = client.post(
            "/fetch/metadata:batch",
            json={"coordinates": [{"slug": archived_slug, "version": "1.0.0"}]},
            headers=_headers("admin-token"),
        )
        archived_content_forbidden = client.post(
            "/fetch/content:batch",
            json={"coordinates": [{"slug": archived_slug, "version": "1.0.0"}]},
            headers=_headers("reader-token"),
        )

    assert published_discovery.status_code == 200
    assert set(published_discovery.json()["candidates"]) == {
        published_slug,
        internal_slug,
    }
    assert deprecated_slug not in published_discovery.json()["candidates"]
    assert archived_slug not in published_discovery.json()["candidates"]

    assert archived_resolution_forbidden.status_code == 403
    assert archived_resolution_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_resolution_admin.status_code == 200
    assert archived_resolution_admin.json()["slug"] == archived_slug

    assert archived_metadata_forbidden.status_code == 403
    assert archived_metadata_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_metadata_admin.status_code == 200
    assert archived_metadata_admin.json()["results"][0]["status"] == "found"

    assert archived_content_forbidden.status_code == 403
    assert archived_content_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"


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
