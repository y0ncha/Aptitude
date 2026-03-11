"""Integration tests for normalized skill registry endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from app.main import create_app


@pytest.fixture
def migrated_registry_database(require_integration_database: str) -> str:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", require_integration_database)
    command.upgrade(config, "head")
    return require_integration_database


def _request(
    slug: str,
    version: str,
    *,
    raw_markdown: str = "# Python Lint\n\nLint Python files.\n",
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
        "relationships": {
            "depends_on": depends_on or [],
            "extends": extends or [],
            "conflicts_with": conflicts_with or [],
            "overlaps_with": overlaps_with or [],
        },
    }


def _publish(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/skill-versions", json=payload)
    assert response.status_code == 201, response.text
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
        _publish(client, _request(slug, "2.0.0", raw_markdown="# v2\n"))

        identity = client.get(f"/skills/{slug}")
        versions = client.get(f"/skills/{slug}/versions")
        metadata = client.get(f"/skills/{slug}/versions/2.0.0")
        content = client.get(f"/skills/{slug}/versions/2.0.0/content")

    assert identity.status_code == 200
    assert identity.json()["slug"] == slug
    assert identity.json()["current_version"]["version"] == "2.0.0"

    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()["versions"]] == ["2.0.0", "1.0.0"]

    assert metadata.status_code == 200
    body = metadata.json()
    assert body["slug"] == slug
    assert body["version"] == "2.0.0"
    assert body["content"]["size_bytes"] == len(b"# v2\n")
    assert body["content_download_path"] == f"/skills/{slug}/versions/2.0.0/content"

    assert content.status_code == 200
    assert content.text == "# v2\n"
    assert content.headers["etag"] == body["content"]["checksum"]["digest"]
    assert content.headers["cache-control"] == "public, immutable"


@pytest.mark.integration
def test_duplicate_publish_returns_409(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.lint.{uuid4().hex}"

    with TestClient(create_app()) as client:
        payload = _request(slug, "1.0.0")
        _publish(client, payload)
        duplicate = client.post("/skill-versions", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_SKILL_VERSION"


@pytest.mark.integration
def test_relationship_batch_returns_all_edge_families(
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

        response = client.post(
            "/resolution/relationships:batch",
            json={"coordinates": [{"slug": slug, "version": "1.0.0"}]},
        )

    assert response.status_code == 200
    relationships = response.json()["results"][0]["relationships"]
    assert [item["edge_type"] for item in relationships] == [
        "depends_on",
        "extends",
        "conflicts_with",
        "overlaps_with",
    ]
    assert relationships[0]["target_version"]["slug"] == dependency_slug
    assert relationships[1]["target_version"]["slug"] == extension_slug
    assert relationships[2]["target_version"] is None
    assert relationships[3]["target_version"]["slug"] == overlap_slug


@pytest.mark.integration
def test_discovery_search_uses_slug_and_content_size(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    slug = f"python.discovery.{suffix}"

    with TestClient(create_app()) as client:
        _publish(client, _request(slug, "1.0.0", raw_markdown="# old\n"))
        _publish(client, _request(slug, "2.0.0", raw_markdown="# much newer content\n"))

        response = client.get("/discovery/skills/search", params={"q": slug})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["slug"] == slug
    assert result["version"] == "2.0.0"
    assert result["content_size_bytes"] == len(b"# much newer content\n")


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
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_publish_backfills_normalized_search_documents(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.searchdoc.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, _request(slug, "1.0.0", raw_markdown="# Search Doc\n"))

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT slug, normalized_slug, content_size_bytes
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
    finally:
        engine.dispose()
