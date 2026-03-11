"""Normalize skill storage into PostgreSQL-backed content, metadata, and selectors.

Revision ID: 0005_normalized_skill_storage_api_cleanup
Revises: 0004_metadata_search_ranking
Create Date: 2026-03-11
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_normalized_skill_storage_api_cleanup"
down_revision = "0004_metadata_search_ranking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("slug", sa.Text(), nullable=True))
    op.add_column(
        "skills",
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "skills",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "skill_contents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("raw_markdown", sa.Text(), nullable=False),
        sa.Column("rendered_summary", sa.Text(), nullable=True),
        sa.Column("storage_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_digest", sa.String(length=64), nullable=False, unique=True),
    )
    op.create_table(
        "skill_metadata",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("inputs_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outputs_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("maturity_score", sa.Float(), nullable=True),
        sa.Column("security_score", sa.Float(), nullable=True),
    )
    op.add_column("skill_versions", sa.Column("content_fk", sa.BigInteger(), nullable=True))
    op.add_column("skill_versions", sa.Column("metadata_fk", sa.BigInteger(), nullable=True))
    op.add_column(
        "skill_versions",
        sa.Column("checksum_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_foreign_key(
        "fk_skill_versions_content_fk",
        "skill_versions",
        "skill_contents",
        ["content_fk"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_skill_versions_metadata_fk",
        "skill_versions",
        "skill_metadata",
        ["metadata_fk"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_skill_versions_content_fk", "skill_versions", ["content_fk"])
    op.create_index("ix_skill_versions_metadata_fk", "skill_versions", ["metadata_fk"])

    op.create_table(
        "skill_relationship_selectors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_skill_version_fk", sa.BigInteger(), nullable=False),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("target_slug", sa.Text(), nullable=False),
        sa.Column("target_version", sa.Text(), nullable=True),
        sa.Column("version_constraint", sa.Text(), nullable=True),
        sa.Column("optional", sa.Boolean(), nullable=True),
        sa.Column(
            "markers",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "edge_type IN ('depends_on', 'extends', 'conflicts_with', 'overlaps_with')",
            name="ck_skill_relationship_selectors_edge_type",
        ),
        sa.ForeignKeyConstraint(
            ["source_skill_version_fk"],
            ["skill_versions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_skill_relationship_selectors_source_edge_type_ordinal",
        "skill_relationship_selectors",
        ["source_skill_version_fk", "edge_type", "ordinal"],
    )

    op.create_table(
        "skill_dependencies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("from_version_fk", sa.BigInteger(), nullable=False),
        sa.Column("to_version_fk", sa.BigInteger(), nullable=False),
        sa.Column("constraint_type", sa.Text(), nullable=False),
        sa.Column("version_constraint", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "constraint_type IN ('depends_on', 'extends', 'conflicts_with', 'overlaps_with')",
            name="ck_skill_dependencies_constraint_type",
        ),
        sa.ForeignKeyConstraint(["from_version_fk"], ["skill_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_version_fk"], ["skill_versions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_skill_dependencies_from_version_fk",
        "skill_dependencies",
        ["from_version_fk"],
    )
    op.create_index(
        "ix_skill_dependencies_to_version_fk",
        "skill_dependencies",
        ["to_version_fk"],
    )
    op.create_index(
        "uq_skill_dependencies_exact_edge",
        "skill_dependencies",
        ["from_version_fk", "to_version_fk", "constraint_type"],
        unique=True,
    )

    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE skills SET slug = skill_id, updated_at = created_at WHERE slug IS NULL")
    )

    version_rows = bind.execute(
        sa.text(
            """
            SELECT
                sv.id,
                s.skill_id,
                sv.version,
                sv.manifest_json,
                sv.artifact_rel_path,
                sv.artifact_size_bytes,
                sv.published_at,
                svc.digest AS checksum_digest
            FROM skill_versions AS sv
            JOIN skills AS s
              ON s.id = sv.skill_fk
            LEFT JOIN skill_version_checksums AS svc
              ON svc.skill_version_fk = sv.id
            ORDER BY sv.id
            """
        )
    ).mappings()
    version_targets = {
        (str(row["skill_id"]), str(row["version"])): int(row["id"]) for row in version_rows
    }

    # Re-run query because mappings iterator was consumed.
    version_rows = bind.execute(
        sa.text(
            """
            SELECT
                sv.id,
                s.skill_id,
                sv.version,
                sv.manifest_json,
                sv.artifact_rel_path,
                sv.artifact_size_bytes,
                sv.published_at,
                svc.digest AS checksum_digest
            FROM skill_versions AS sv
            JOIN skills AS s
              ON s.id = sv.skill_fk
            LEFT JOIN skill_version_checksums AS svc
              ON svc.skill_version_fk = sv.id
            ORDER BY sv.id
            """
        )
    ).mappings()

    for row in version_rows:
        skill_id = str(row["skill_id"])
        version = str(row["version"])
        manifest = _ensure_manifest_dict(row["manifest_json"])
        raw_markdown = _read_legacy_markdown(
            relative_path=str(row["artifact_rel_path"]),
            manifest=manifest,
            skill_id=skill_id,
            version=version,
        )
        content_checksum = hashlib.sha256(raw_markdown.encode("utf-8")).hexdigest()
        size_bytes = len(raw_markdown.encode("utf-8"))
        rendered_summary = None

        content_id = bind.execute(
            sa.text(
                """
                INSERT INTO skill_contents (
                    raw_markdown,
                    rendered_summary,
                    storage_size_bytes,
                    checksum_digest
                )
                VALUES (:raw_markdown, :rendered_summary, :storage_size_bytes, :checksum_digest)
                ON CONFLICT (checksum_digest) DO UPDATE
                SET checksum_digest = EXCLUDED.checksum_digest
                RETURNING id
                """
            ),
            {
                "raw_markdown": raw_markdown,
                "rendered_summary": rendered_summary,
                "storage_size_bytes": size_bytes,
                "checksum_digest": content_checksum,
            },
        ).scalar_one()

        metadata_id = bind.execute(
            sa.text(
                """
                INSERT INTO skill_metadata (
                    name,
                    description,
                    tags,
                    headers,
                    inputs_schema,
                    outputs_schema,
                    token_estimate,
                    maturity_score,
                    security_score
                )
                VALUES (
                    :name,
                    :description,
                    :tags,
                    CAST(:headers AS jsonb),
                    CAST(:inputs_schema AS jsonb),
                    CAST(:outputs_schema AS jsonb),
                    :token_estimate,
                    :maturity_score,
                    :security_score
                )
                RETURNING id
                """
            ),
            {
                "name": str(manifest.get("name") or row["skill_id"]),
                "description": (
                    manifest.get("description")
                    if isinstance(manifest.get("description"), str)
                    else None
                ),
                "tags": _tags_from_manifest(manifest),
                "headers": _json_or_none(manifest.get("headers")),
                "inputs_schema": _json_or_none(manifest.get("inputs_schema")),
                "outputs_schema": _json_or_none(manifest.get("outputs_schema")),
                "token_estimate": _optional_int(manifest.get("token_estimate")),
                "maturity_score": _optional_float(manifest.get("maturity_score")),
                "security_score": _optional_float(manifest.get("security_score")),
            },
        ).scalar_one()

        bind.execute(
            sa.text(
                """
                UPDATE skill_versions
                SET
                    content_fk = :content_fk,
                    metadata_fk = :metadata_fk,
                    checksum_digest = :checksum_digest,
                    created_at = COALESCE(created_at, published_at),
                    is_published = true,
                    artifact_size_bytes = COALESCE(artifact_size_bytes, :artifact_size_bytes),
                    artifact_rel_path = :artifact_rel_path
                WHERE id = :skill_version_id
                """
            ),
            {
                "content_fk": content_id,
                "metadata_fk": metadata_id,
                "checksum_digest": content_checksum,
                "artifact_size_bytes": size_bytes,
                "artifact_rel_path": f"db://skills/{skill_id}/{version}/content.md",
                "skill_version_id": int(row["id"]),
            },
        )

        for selector in _relationship_selectors_from_manifest(manifest):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO skill_relationship_selectors (
                        source_skill_version_fk,
                        edge_type,
                        ordinal,
                        target_slug,
                        target_version,
                        version_constraint,
                        optional,
                        markers
                    )
                    VALUES (
                        :source_skill_version_fk,
                        :edge_type,
                        :ordinal,
                        :target_slug,
                        :target_version,
                        :version_constraint,
                        :optional,
                        :markers
                    )
                    """
                ),
                {
                    "source_skill_version_fk": int(row["id"]),
                    **selector,
                },
            )
            target_version = selector["target_version"]
            if target_version is None:
                continue
            target_id = version_targets.get((selector["target_slug"], target_version))
            if target_id is None:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO skill_dependencies (
                        from_version_fk,
                        to_version_fk,
                        constraint_type,
                        version_constraint
                    )
                    VALUES (
                        :from_version_fk,
                        :to_version_fk,
                        :constraint_type,
                        :version_constraint
                    )
                    ON CONFLICT (from_version_fk, to_version_fk, constraint_type) DO NOTHING
                    """
                ),
                {
                    "from_version_fk": int(row["id"]),
                    "to_version_fk": target_id,
                    "constraint_type": selector["edge_type"],
                    "version_constraint": selector["version_constraint"],
                },
            )

    bind.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    skill_fk,
                    id,
                    published_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY skill_fk
                        ORDER BY published_at DESC, id DESC
                    ) AS row_num
                FROM skill_versions
            )
            UPDATE skills AS s
            SET
                current_version_id = ranked.id,
                updated_at = ranked.published_at
            FROM ranked
            WHERE ranked.skill_fk = s.id
              AND ranked.row_num = 1
            """
        )
    )

    op.alter_column("skills", "slug", nullable=False)
    op.alter_column("skill_versions", "content_fk", nullable=False)
    op.alter_column("skill_versions", "metadata_fk", nullable=False)
    op.alter_column("skill_versions", "checksum_digest", nullable=False)

    op.create_index("uq_skills_slug", "skills", ["slug"], unique=True)
    op.create_foreign_key(
        "fk_skills_current_version_id",
        "skills",
        "skill_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _drop_legacy_search_documents()
    _create_normalized_search_documents()
    _backfill_normalized_search_documents()


def downgrade() -> None:
    _drop_normalized_search_documents()
    _create_legacy_search_documents()
    _backfill_legacy_search_documents()

    op.drop_constraint("fk_skills_current_version_id", "skills", type_="foreignkey")
    op.drop_index("uq_skills_slug", table_name="skills")

    op.drop_index("uq_skill_dependencies_exact_edge", table_name="skill_dependencies")
    op.drop_index("ix_skill_dependencies_to_version_fk", table_name="skill_dependencies")
    op.drop_index("ix_skill_dependencies_from_version_fk", table_name="skill_dependencies")
    op.drop_table("skill_dependencies")

    op.drop_index(
        "ix_skill_relationship_selectors_source_edge_type_ordinal",
        table_name="skill_relationship_selectors",
    )
    op.drop_table("skill_relationship_selectors")

    op.drop_index("ix_skill_versions_metadata_fk", table_name="skill_versions")
    op.drop_index("ix_skill_versions_content_fk", table_name="skill_versions")
    op.drop_constraint("fk_skill_versions_metadata_fk", "skill_versions", type_="foreignkey")
    op.drop_constraint("fk_skill_versions_content_fk", "skill_versions", type_="foreignkey")
    op.drop_column("skill_versions", "is_published")
    op.drop_column("skill_versions", "created_at")
    op.drop_column("skill_versions", "checksum_digest")
    op.drop_column("skill_versions", "metadata_fk")
    op.drop_column("skill_versions", "content_fk")

    op.drop_table("skill_metadata")
    op.drop_table("skill_contents")

    op.drop_column("skills", "updated_at")
    op.drop_column("skills", "status")
    op.drop_column("skills", "current_version_id")
    op.drop_column("skills", "slug")


def _artifact_root() -> Path:
    return Path(os.environ.get("ARTIFACT_ROOT_DIR", "./.data/artifacts")).resolve()


def _read_legacy_markdown(
    *,
    relative_path: str,
    manifest: dict[str, Any],
    skill_id: str,
    version: str,
) -> str:
    path = Path(relative_path)
    if not path.is_absolute():
        path = _artifact_root() / path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _build_missing_artifact_markdown(
            manifest=manifest,
            skill_id=skill_id,
            version=version,
            relative_path=relative_path,
        )
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Legacy artifact is not valid UTF-8 markdown: {path}") from exc


def _build_missing_artifact_markdown(
    *,
    manifest: dict[str, Any],
    skill_id: str,
    version: str,
    relative_path: str,
) -> str:
    title = manifest.get("name") if isinstance(manifest.get("name"), str) else skill_id
    description = (
        manifest.get("description").strip()
        if isinstance(manifest.get("description"), str) and manifest.get("description").strip()
        else None
    )
    tags = _tags_from_manifest(manifest)

    lines = [f"# {title}", ""]
    if description is not None:
        lines.extend([description, ""])
    if tags:
        lines.extend([f"Tags: {', '.join(tags)}", ""])
    lines.extend(
        [
            "> Original markdown artifact was unavailable during migration.",
            f"> Legacy artifact reference: `{relative_path}`.",
            f"> Skill version: `{skill_id}@{version}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _ensure_manifest_dict(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("Legacy manifest_json row is not a JSON object.")


def _tags_from_manifest(manifest: dict[str, Any]) -> list[str]:
    raw_tags = manifest.get("tags")
    if not isinstance(raw_tags, list):
        return []
    return [str(item) for item in raw_tags if isinstance(item, str)]


def _json_or_none(value: object) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _relationship_selectors_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    selectors: list[dict[str, Any]] = []
    for edge_type in ("depends_on", "extends", "conflicts_with", "overlaps_with"):
        raw_entries = manifest.get(edge_type)
        if not isinstance(raw_entries, list):
            continue
        for ordinal, item in enumerate(raw_entries):
            if not isinstance(item, dict):
                continue
            target_slug = item.get("skill_id")
            if not isinstance(target_slug, str) or not target_slug:
                continue
            target_version = item.get("version") if isinstance(item.get("version"), str) else None
            version_constraint = (
                item.get("version_constraint")
                if isinstance(item.get("version_constraint"), str)
                else None
            )
            optional = item.get("optional") if isinstance(item.get("optional"), bool) else None
            markers = item.get("markers") if isinstance(item.get("markers"), list) else []
            selectors.append(
                {
                    "edge_type": edge_type,
                    "ordinal": ordinal,
                    "target_slug": target_slug,
                    "target_version": target_version,
                    "version_constraint": version_constraint,
                    "optional": optional,
                    "markers": [str(marker) for marker in markers if isinstance(marker, str)],
                }
            )
    return selectors


def _drop_legacy_search_documents() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_normalized_tags_gin")
    op.execute("DROP TRIGGER IF EXISTS trg_skill_search_documents_vector ON skill_search_documents")
    op.execute("DROP FUNCTION IF EXISTS update_skill_search_documents_vector()")
    op.drop_index(
        "ix_skill_search_documents_artifact_size_bytes",
        table_name="skill_search_documents",
    )
    op.drop_index("ix_skill_search_documents_published_at", table_name="skill_search_documents")
    op.drop_index("ix_skill_search_documents_normalized_name", table_name="skill_search_documents")
    op.drop_index(
        "ix_skill_search_documents_normalized_skill_id",
        table_name="skill_search_documents",
    )
    op.drop_table("skill_search_documents")


def _create_normalized_search_documents() -> None:
    op.create_table(
        "skill_search_documents",
        sa.Column(
            "skill_version_fk",
            sa.BigInteger(),
            sa.ForeignKey("skill_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("normalized_slug", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "normalized_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            nullable=False,
            server_default=sa.text("''::tsvector"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("usage_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_skill_search_documents_normalized_slug",
        "skill_search_documents",
        ["normalized_slug"],
    )
    op.create_index(
        "ix_skill_search_documents_normalized_name",
        "skill_search_documents",
        ["normalized_name"],
    )
    op.create_index(
        "ix_skill_search_documents_published_at",
        "skill_search_documents",
        ["published_at"],
    )
    op.create_index(
        "ix_skill_search_documents_content_size_bytes",
        "skill_search_documents",
        ["content_size_bytes"],
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_documents_normalized_tags_gin
        ON skill_search_documents
        USING gin (normalized_tags)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_skill_search_documents_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple'::regconfig, NEW.normalized_slug), 'A')
                || setweight(to_tsvector('simple'::regconfig, NEW.normalized_name), 'A')
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        array_to_string(COALESCE(NEW.normalized_tags, ARRAY[]::text[]), ' ')
                    ),
                    'B'
                )
                || setweight(
                    to_tsvector('simple'::regconfig, COALESCE(NEW.description, '')),
                    'C'
                );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_skill_search_documents_vector
        BEFORE INSERT OR UPDATE OF
            normalized_slug,
            normalized_name,
            normalized_tags,
            description
        ON skill_search_documents
        FOR EACH ROW
        EXECUTE FUNCTION update_skill_search_documents_vector()
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_documents_search_vector_gin
        ON skill_search_documents
        USING gin (search_vector)
        """
    )


def _backfill_normalized_search_documents() -> None:
    op.execute(
        """
        INSERT INTO skill_search_documents (
            skill_version_fk,
            slug,
            normalized_slug,
            version,
            name,
            normalized_name,
            description,
            tags,
            normalized_tags,
            search_vector,
            published_at,
            content_size_bytes,
            usage_count
        )
        SELECT
            sv.id,
            s.slug,
            lower(s.slug),
            sv.version,
            sm.name,
            lower(sm.name),
            sm.description,
            sm.tags,
            COALESCE(
                ARRAY(
                    SELECT lower(tag_value)
                    FROM unnest(sm.tags) AS tag_value
                ),
                ARRAY[]::text[]
            ),
            setweight(to_tsvector('simple'::regconfig, lower(s.slug)), 'A')
                || setweight(to_tsvector('simple'::regconfig, lower(sm.name)), 'A')
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        COALESCE(
                            array_to_string(
                                ARRAY(
                                    SELECT lower(tag_value)
                                    FROM unnest(sm.tags) AS tag_value
                                ),
                                ' '
                            ),
                            ''
                        )
                    ),
                    'B'
                )
                || setweight(
                    to_tsvector('simple'::regconfig, COALESCE(sm.description, '')),
                    'C'
                ),
            sv.published_at,
            sc.storage_size_bytes,
            0
        FROM skill_versions AS sv
        JOIN skills AS s
          ON s.id = sv.skill_fk
        JOIN skill_metadata AS sm
          ON sm.id = sv.metadata_fk
        JOIN skill_contents AS sc
          ON sc.id = sv.content_fk
        ON CONFLICT (skill_version_fk) DO NOTHING
        """
    )


def _drop_normalized_search_documents() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_normalized_tags_gin")
    op.execute("DROP TRIGGER IF EXISTS trg_skill_search_documents_vector ON skill_search_documents")
    op.execute("DROP FUNCTION IF EXISTS update_skill_search_documents_vector()")
    op.drop_index(
        "ix_skill_search_documents_content_size_bytes",
        table_name="skill_search_documents",
    )
    op.drop_index("ix_skill_search_documents_published_at", table_name="skill_search_documents")
    op.drop_index("ix_skill_search_documents_normalized_name", table_name="skill_search_documents")
    op.drop_index("ix_skill_search_documents_normalized_slug", table_name="skill_search_documents")
    op.drop_table("skill_search_documents")


def _create_legacy_search_documents() -> None:
    op.create_table(
        "skill_search_documents",
        sa.Column(
            "skill_version_fk",
            sa.BigInteger(),
            sa.ForeignKey("skill_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("normalized_skill_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "normalized_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            nullable=False,
            server_default=sa.text("''::tsvector"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("usage_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_skill_search_documents_normalized_skill_id",
        "skill_search_documents",
        ["normalized_skill_id"],
    )
    op.create_index(
        "ix_skill_search_documents_normalized_name",
        "skill_search_documents",
        ["normalized_name"],
    )
    op.create_index(
        "ix_skill_search_documents_published_at",
        "skill_search_documents",
        ["published_at"],
    )
    op.create_index(
        "ix_skill_search_documents_artifact_size_bytes",
        "skill_search_documents",
        ["artifact_size_bytes"],
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_documents_normalized_tags_gin
        ON skill_search_documents
        USING gin (normalized_tags)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_skill_search_documents_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple'::regconfig, NEW.normalized_skill_id), 'A')
                || setweight(to_tsvector('simple'::regconfig, NEW.normalized_name), 'A')
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        array_to_string(COALESCE(NEW.normalized_tags, ARRAY[]::text[]), ' ')
                    ),
                    'B'
                )
                || setweight(
                    to_tsvector('simple'::regconfig, COALESCE(NEW.description, '')),
                    'C'
                );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_skill_search_documents_vector
        BEFORE INSERT OR UPDATE OF
            normalized_skill_id,
            normalized_name,
            normalized_tags,
            description
        ON skill_search_documents
        FOR EACH ROW
        EXECUTE FUNCTION update_skill_search_documents_vector()
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_documents_search_vector_gin
        ON skill_search_documents
        USING gin (search_vector)
        """
    )


def _backfill_legacy_search_documents() -> None:
    op.execute(
        """
        INSERT INTO skill_search_documents (
            skill_version_fk,
            skill_id,
            normalized_skill_id,
            version,
            name,
            normalized_name,
            description,
            tags,
            normalized_tags,
            search_vector,
            published_at,
            artifact_size_bytes,
            usage_count
        )
        SELECT
            sv.id,
            s.skill_id,
            lower(s.skill_id),
            sv.version,
            COALESCE(sv.manifest_json ->> 'name', s.skill_id),
            lower(COALESCE(sv.manifest_json ->> 'name', s.skill_id)),
            NULLIF(sv.manifest_json ->> 'description', ''),
            COALESCE(
                ARRAY(
                    SELECT jsonb_array_elements_text(
                        COALESCE(sv.manifest_json -> 'tags', '[]'::jsonb)
                    )
                ),
                ARRAY[]::text[]
            ),
            COALESCE(
                ARRAY(
                    SELECT lower(tag_value)
                    FROM jsonb_array_elements_text(
                        COALESCE(sv.manifest_json -> 'tags', '[]'::jsonb)
                    ) AS tag_value
                ),
                ARRAY[]::text[]
            ),
            setweight(to_tsvector('simple'::regconfig, lower(s.skill_id)), 'A')
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        lower(COALESCE(sv.manifest_json ->> 'name', s.skill_id))
                    ),
                    'A'
                )
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        COALESCE(
                            array_to_string(
                                ARRAY(
                                    SELECT lower(tag_value)
                                    FROM jsonb_array_elements_text(
                                        COALESCE(sv.manifest_json -> 'tags', '[]'::jsonb)
                                    ) AS tag_value
                                ),
                                ' '
                            ),
                            ''
                        )
                    ),
                    'B'
                )
                || setweight(
                    to_tsvector(
                        'simple'::regconfig,
                        COALESCE(NULLIF(sv.manifest_json ->> 'description', ''), '')
                    ),
                    'C'
                ),
            sv.published_at,
            sv.artifact_size_bytes,
            0
        FROM skill_versions AS sv
        JOIN skills AS s
          ON s.id = sv.skill_fk
        ON CONFLICT (skill_version_fk) DO NOTHING
        """
    )
