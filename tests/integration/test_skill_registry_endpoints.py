"""Integration tests for immutable skill registry endpoints."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.main import create_app


@pytest.fixture
def migrated_registry_database(require_integration_database: str) -> str:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", require_integration_database)
    command.upgrade(config, "head")
    return require_integration_database


def _manifest(
    skill_id: str,
    version: str,
    *,
    depends_on: list[dict[str, object]] | None = None,
    extends: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "skill_id": skill_id,
        "version": version,
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"],
        "depends_on": depends_on or [],
        "extends": extends or [],
        "conflicts_with": [],
        "overlaps_with": [],
    }


def _publish(
    *,
    client: TestClient,
    skill_id: str,
    version: str,
    artifact_bytes: bytes,
    depends_on: list[dict[str, object]] | None = None,
    extends: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/skills/publish",
        data={
            "manifest": json.dumps(
                _manifest(
                    skill_id=skill_id,
                    version=version,
                    depends_on=depends_on,
                    extends=extends,
                )
            )
        },
        files={"artifact": ("artifact.bin", artifact_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assert_invalid_request(response: object, *, location: list[str] | None = None) -> None:
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert body["error"]["message"] == "Request validation failed."
    assert isinstance(body["error"]["details"]["errors"], list)
    if location is not None:
        assert body["error"]["details"]["errors"][0]["loc"] == location


@pytest.mark.integration
def test_publish_fetch_and_list_skill_versions(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))
    skill_id = f"python.lint.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client=client, skill_id=skill_id, version="1.0.0", artifact_bytes=b"v1")
        _publish(client=client, skill_id=skill_id, version="1.1.0", artifact_bytes=b"v11")
        _publish(client=client, skill_id=skill_id, version="2.0.0", artifact_bytes=b"v2")

        for expected in ["1.0.0", "1.1.0", "2.0.0"]:
            response = client.get(f"/skills/{skill_id}/{expected}")
            assert response.status_code == 200
            body = response.json()
            assert body["skill_id"] == skill_id
            assert body["version"] == expected
            assert body["checksum"]["algorithm"] == "sha256"
            assert base64.b64decode(body["artifact_base64"]) in {b"v1", b"v11", b"v2"}

        list_first = client.get(f"/skills/{skill_id}")
        list_second = client.get(f"/skills/{skill_id}")

    assert list_first.status_code == 200
    assert list_second.status_code == 200
    assert list_first.json() == list_second.json()
    assert [item["version"] for item in list_first.json()["versions"]] == [
        "2.0.0",
        "1.1.0",
        "1.0.0",
    ]


@pytest.mark.integration
def test_duplicate_publish_returns_409(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))
    skill_id = f"python.lint.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client=client,
            skill_id=skill_id,
            version="1.0.0",
            artifact_bytes=b"v1",
        )
        duplicate = client.post(
            "/skills/publish",
            data={"manifest": json.dumps(_manifest(skill_id=skill_id, version="1.0.0"))},
            files={"artifact": ("artifact.bin", b"v1", "application/octet-stream")},
        )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_SKILL_VERSION"


@pytest.mark.integration
def test_fetch_detects_corrupted_artifact_checksum(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(artifact_root))
    skill_id = f"python.lint.{uuid4().hex}"

    with TestClient(create_app()) as client:
        publish = _publish(
            client=client, skill_id=skill_id, version="1.0.0", artifact_bytes=b"trusted"
        )
        relative_path = publish["artifact_metadata"]["relative_path"]
        artifact_path = artifact_root / relative_path
        artifact_path.write_bytes(b"tampered")
        corrupted = client.get(f"/skills/{skill_id}/1.0.0")

    assert corrupted.status_code == 500
    assert corrupted.json()["error"]["code"] == "INTEGRITY_CHECK_FAILED"


@pytest.mark.integration
def test_fetch_returns_dependency_metadata_in_stable_order(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))
    suffix = uuid4().hex
    skill_id = f"python.dep.{suffix}"
    dependency_a = f"shared.a.{suffix}"
    dependency_b = f"shared.b.{suffix}"
    extension_a = f"base.a.{suffix}"
    extension_b = f"base.b.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client=client,
            skill_id=skill_id,
            version="1.0.0",
            artifact_bytes=b"v1",
            depends_on=[
                {
                    "skill_id": dependency_b,
                    "version_constraint": ">=2.0.0,<3.0.0",
                    "optional": True,
                    "markers": ["linux", "gpu"],
                },
                {"skill_id": dependency_a, "version": "1.0.0"},
            ],
            extends=[
                {"skill_id": extension_b, "version": "3.0.0"},
                {"skill_id": extension_a, "version": "2.1.0"},
            ],
        )
        first = client.get(f"/skills/{skill_id}/1.0.0")
        second = client.get(f"/skills/{skill_id}/1.0.0")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["manifest"]["depends_on"] == [
        {
            "skill_id": dependency_b,
            "version_constraint": ">=2.0.0,<3.0.0",
            "optional": True,
            "markers": ["linux", "gpu"],
        },
        {"skill_id": dependency_a, "version": "1.0.0"},
    ]
    assert first.json()["manifest"]["extends"] == [
        {"skill_id": extension_b, "version": "3.0.0"},
        {"skill_id": extension_a, "version": "2.1.0"},
    ]


@pytest.mark.integration
def test_publish_rejects_malformed_dependency_declarations(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))
    skill_id = f"python.invalid.{uuid4().hex}"

    invalid_manifest = {
        "schema_version": "1.0",
        "skill_id": skill_id,
        "version": "1.0.0",
        "name": "Python Lint",
        "depends_on": [{"skill_id": "missing.version"}],
    }

    with TestClient(create_app()) as client:
        response = client.post(
            "/skills/publish",
            data={"manifest": json.dumps(invalid_manifest)},
            files={"artifact": ("artifact.bin", b"v1", "application/octet-stream")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_MANIFEST"


@pytest.mark.integration
def test_publish_rejects_invalid_dependency_constraint_syntax(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))
    skill_id = f"python.invalid.constraint.{uuid4().hex}"

    invalid_manifest = {
        "schema_version": "1.0",
        "skill_id": skill_id,
        "version": "1.0.0",
        "name": "Python Lint",
        "depends_on": [{"skill_id": "shared.base", "version_constraint": "latest"}],
    }

    with TestClient(create_app()) as client:
        response = client.post(
            "/skills/publish",
            data={"manifest": json.dumps(invalid_manifest)},
            files={"artifact": ("artifact.bin", b"v1", "application/octet-stream")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_MANIFEST"


@pytest.mark.integration
def test_fetch_rejects_invalid_skill_id_path(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    with TestClient(create_app()) as client:
        response = client.get("/skills/invalid%20skill/1.0.0")

    _assert_invalid_request(response, location=["path", "skill_id"])


@pytest.mark.integration
def test_fetch_rejects_invalid_version_path(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    with TestClient(create_app()) as client:
        response = client.get("/skills/python.lint/latest")

    _assert_invalid_request(response, location=["path", "version"])


@pytest.mark.integration
def test_publish_rejects_missing_manifest_form_field(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/skills/publish",
            files={"artifact": ("artifact.bin", b"v1", "application/octet-stream")},
        )

    _assert_invalid_request(response, location=["body", "manifest"])


@pytest.mark.integration
def test_publish_rejects_missing_artifact_upload(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/skills/publish",
            data={"manifest": json.dumps(_manifest(skill_id="python.lint", version="1.0.0"))},
        )

    _assert_invalid_request(response, location=["body", "artifact"])


@pytest.mark.integration
def test_publish_rejects_malformed_manifest_json(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/skills/publish",
            data={"manifest": "not-json"},
            files={"artifact": ("artifact.bin", b"v1", "application/octet-stream")},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_MANIFEST"
    assert body["error"]["message"] == "Manifest validation failed."
    assert body["error"]["details"]["errors"][0]["type"] == "json_invalid"
