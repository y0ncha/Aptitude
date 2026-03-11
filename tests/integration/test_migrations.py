"""Integration coverage for Alembic migration lifecycle."""

from __future__ import annotations

import json

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


@pytest.mark.integration
def test_migrations_upgrade_and_downgrade(require_integration_database: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", require_integration_database)

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    upgraded_engine = create_engine(require_integration_database)
    try:
        inspector = inspect(upgraded_engine)
        assert "audit_events" in inspector.get_table_names()
        assert "skills" in inspector.get_table_names()
        assert "skill_versions" in inspector.get_table_names()
        assert "skill_contents" in inspector.get_table_names()
        assert "skill_metadata" in inspector.get_table_names()
        assert "skill_relationship_selectors" in inspector.get_table_names()
        assert "skill_dependencies" in inspector.get_table_names()
        assert "skill_search_documents" in inspector.get_table_names()
    finally:
        upgraded_engine.dispose()

    command.downgrade(config, "base")

    downgraded_engine = create_engine(require_integration_database)
    try:
        inspector = inspect(downgraded_engine)
        assert "audit_events" not in inspector.get_table_names()
        assert "skills" not in inspector.get_table_names()
        assert "skill_versions" not in inspector.get_table_names()
        assert "skill_contents" not in inspector.get_table_names()
        assert "skill_metadata" not in inspector.get_table_names()
        assert "skill_relationship_selectors" not in inspector.get_table_names()
        assert "skill_dependencies" not in inspector.get_table_names()
        assert "skill_search_documents" not in inspector.get_table_names()
    finally:
        downgraded_engine.dispose()


@pytest.mark.integration
def test_0005_backfills_normalized_tables_from_legacy_rows(
    require_integration_database: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact_rel_path = "skills/migration.source/1.0.0/artifact.bin"
    artifact_path = artifact_root / artifact_rel_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("# Migration Source\n", encoding="utf-8")

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", require_integration_database)
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(artifact_root))

    command.downgrade(config, "base")
    command.upgrade(config, "0004_metadata_search_ranking")

    engine = create_engine(require_integration_database)
    try:
        with engine.begin() as connection:
            source_fk = connection.execute(
                text("INSERT INTO skills (skill_id) VALUES ('migration.source') RETURNING id")
            ).scalar_one()
            target_fk = connection.execute(
                text("INSERT INTO skills (skill_id) VALUES ('migration.target') RETURNING id")
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO skill_versions
                        (skill_fk, version, manifest_json, artifact_rel_path, artifact_size_bytes)
                    VALUES
                        (
                            :skill_fk,
                            '1.0.0',
                            CAST(:manifest_json AS jsonb),
                            :artifact_rel_path,
                            19
                        )
                    """
                ),
                {
                    "skill_fk": source_fk,
                    "artifact_rel_path": artifact_rel_path,
                    "manifest_json": json.dumps(
                        {
                            "skill_id": "migration.source",
                            "version": "1.0.0",
                            "name": "Migration Source",
                            "description": "Searchable migration skill",
                            "tags": ["Python", "Lint"],
                            "depends_on": [{"skill_id": "migration.target", "version": "1.0.0"}],
                            "extends": [],
                            "conflicts_with": [],
                            "overlaps_with": [],
                        }
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_versions
                        (skill_fk, version, manifest_json, artifact_rel_path, artifact_size_bytes)
                    VALUES
                        (
                            :skill_fk,
                            '1.0.0',
                            CAST(:manifest_json AS jsonb),
                            :artifact_rel_path,
                            10
                        )
                    """
                ),
                {
                    "skill_fk": target_fk,
                    "artifact_rel_path": artifact_rel_path,
                    "manifest_json": json.dumps(
                        {
                            "skill_id": "migration.target",
                            "version": "1.0.0",
                            "name": "Migration Target",
                            "tags": ["python"],
                        }
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_version_checksums (skill_version_fk, algorithm, digest)
                    SELECT id, 'sha256', :digest
                    FROM skill_versions
                    """
                ),
                {"digest": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2"},
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    upgraded_engine = create_engine(require_integration_database)
    try:
        with upgraded_engine.connect() as connection:
            content_row = (
                connection.execute(
                    text(
                        """
                    SELECT sc.raw_markdown, sm.name, s.slug
                    FROM skill_versions AS sv
                    JOIN skills AS s ON s.id = sv.skill_fk
                    JOIN skill_contents AS sc ON sc.id = sv.content_fk
                    JOIN skill_metadata AS sm ON sm.id = sv.metadata_fk
                    WHERE s.slug = 'migration.source'
                    """
                    )
                )
                .mappings()
                .one()
            )
            assert content_row["raw_markdown"] == "# Migration Source\n"
            assert content_row["name"] == "Migration Source"
            assert content_row["slug"] == "migration.source"

            dependency_row = connection.execute(
                text(
                    """
                    SELECT sd.constraint_type
                    FROM skill_dependencies AS sd
                    JOIN skill_versions AS sv ON sv.id = sd.from_version_fk
                    JOIN skills AS s ON s.id = sv.skill_fk
                    WHERE s.slug = 'migration.source'
                    """
                )
            ).scalar_one()
            assert dependency_row == "depends_on"

            search_row = (
                connection.execute(
                    text(
                        """
                    SELECT slug, normalized_slug, content_size_bytes
                    FROM skill_search_documents
                    WHERE slug = 'migration.source'
                    """
                    )
                )
                .mappings()
                .one()
            )
            assert search_row["normalized_slug"] == "migration.source"
            assert search_row["content_size_bytes"] == len(b"# Migration Source\n")
    finally:
        upgraded_engine.dispose()
