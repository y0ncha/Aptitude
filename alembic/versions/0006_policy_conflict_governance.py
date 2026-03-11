"""Add version-level governance and remove legacy compatibility mirrors.

Revision ID: 0006_policy_conflict_governance
Revises: 0005_normalized_skill_storage_api_cleanup
Create Date: 2026-03-11
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_policy_conflict_governance"
down_revision = "0005_normalized_skill_storage_api_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_version_governance_columns()
    _add_search_document_governance_columns()
    _backfill_governance_defaults()
    _recompute_current_version_ids()

    op.drop_table("skill_relationship_edges")
    op.drop_table("skill_version_checksums")

    op.drop_column("skills", "status")
    op.drop_column("skills", "skill_id")

    op.drop_column("skill_versions", "is_published")
    op.drop_column("skill_versions", "artifact_size_bytes")
    op.drop_column("skill_versions", "artifact_rel_path")
    op.drop_column("skill_versions", "manifest_json")


def downgrade() -> None:
    _restore_legacy_skill_columns()
    _restore_legacy_version_columns()
    _restore_legacy_projection_tables()
    _backfill_legacy_compatibility_state()
    _drop_search_document_governance_columns()
    _drop_version_governance_columns()


def _add_version_governance_columns() -> None:
    op.add_column(
        "skill_versions",
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "lifecycle_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "trust_tier",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'untrusted'"),
        ),
    )
    op.add_column("skill_versions", sa.Column("provenance_repo_url", sa.Text(), nullable=True))
    op.add_column("skill_versions", sa.Column("provenance_commit_sha", sa.Text(), nullable=True))
    op.add_column("skill_versions", sa.Column("provenance_tree_path", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_skill_versions_lifecycle_status",
        "skill_versions",
        "lifecycle_status IN ('published', 'deprecated', 'archived')",
    )
    op.create_check_constraint(
        "ck_skill_versions_trust_tier",
        "skill_versions",
        "trust_tier IN ('untrusted', 'internal', 'verified')",
    )


def _add_search_document_governance_columns() -> None:
    op.add_column(
        "skill_search_documents",
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.add_column(
        "skill_search_documents",
        sa.Column(
            "trust_tier",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'untrusted'"),
        ),
    )
    op.create_check_constraint(
        "ck_skill_search_documents_lifecycle_status",
        "skill_search_documents",
        "lifecycle_status IN ('published', 'deprecated', 'archived')",
    )
    op.create_check_constraint(
        "ck_skill_search_documents_trust_tier",
        "skill_search_documents",
        "trust_tier IN ('untrusted', 'internal', 'verified')",
    )
    op.create_index(
        "ix_skill_search_documents_lifecycle_status",
        "skill_search_documents",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_skill_search_documents_trust_tier",
        "skill_search_documents",
        ["trust_tier"],
    )


def _backfill_governance_defaults() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE skill_versions
            SET
                lifecycle_status = 'published',
                lifecycle_changed_at = COALESCE(published_at, CURRENT_TIMESTAMP),
                trust_tier = 'untrusted'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE skill_search_documents AS doc
            SET
                lifecycle_status = sv.lifecycle_status,
                trust_tier = sv.trust_tier
            FROM skill_versions AS sv
            WHERE sv.id = doc.skill_version_fk
            """
        )
    )


def _recompute_current_version_ids() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    sv.skill_fk,
                    sv.id,
                    sv.published_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY sv.skill_fk
                        ORDER BY
                            CASE sv.lifecycle_status
                                WHEN 'published' THEN 0
                                WHEN 'deprecated' THEN 1
                                ELSE 2
                            END,
                            sv.published_at DESC,
                            sv.id DESC
                    ) AS row_num
                FROM skill_versions AS sv
                WHERE sv.lifecycle_status IN ('published', 'deprecated')
            )
            UPDATE skills AS s
            SET
                current_version_id = ranked.id,
                updated_at = COALESCE(ranked.published_at, s.updated_at)
            FROM ranked
            WHERE ranked.skill_fk = s.id
              AND ranked.row_num = 1
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE skills
            SET current_version_id = NULL
            WHERE id NOT IN (
                SELECT DISTINCT skill_fk
                FROM skill_versions
                WHERE lifecycle_status IN ('published', 'deprecated')
            )
            """
        )
    )


def _restore_legacy_skill_columns() -> None:
    op.add_column("skills", sa.Column("skill_id", sa.Text(), nullable=True))
    op.add_column(
        "skills",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.create_unique_constraint("uq_skills_skill_id", "skills", ["skill_id"])


def _restore_legacy_version_columns() -> None:
    op.add_column(
        "skill_versions",
        sa.Column("manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("skill_versions", sa.Column("artifact_rel_path", sa.Text(), nullable=True))
    op.add_column(
        "skill_versions",
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True),
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


def _restore_legacy_projection_tables() -> None:
    op.create_table(
        "skill_version_checksums",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_version_fk",
            sa.BigInteger(),
            sa.ForeignKey("skill_versions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("algorithm", sa.String(length=20), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "algorithm = 'sha256'",
            name="ck_skill_version_checksums_algorithm",
        ),
        sa.CheckConstraint(
            "char_length(digest) = 64",
            name="ck_skill_version_checksums_digest_length",
        ),
    )
    op.create_table(
        "skill_relationship_edges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_skill_version_fk",
            sa.BigInteger(),
            sa.ForeignKey("skill_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("target_skill_id", sa.Text(), nullable=False),
        sa.Column("target_version_selector", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "edge_type IN ('depends_on', 'extends')",
            name="ck_skill_relationship_edges_edge_type",
        ),
        sa.UniqueConstraint(
            "source_skill_version_fk",
            "edge_type",
            "target_skill_id",
            "target_version_selector",
            name="uq_skill_relationship_edges_source_type_target_selector",
        ),
    )
    op.create_index(
        "ix_skill_relationship_edges_source_edge_type",
        "skill_relationship_edges",
        ["source_skill_version_fk", "edge_type"],
    )
    op.create_index(
        "ix_skill_relationship_edges_target_skill_selector_edge_type",
        "skill_relationship_edges",
        ["target_skill_id", "target_version_selector", "edge_type"],
    )


def _backfill_legacy_compatibility_state() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE skills SET skill_id = slug"))
    bind.execute(
        sa.text(
            """
            UPDATE skills AS s
            SET status = COALESCE(cv.lifecycle_status, 'published')
            FROM skill_versions AS cv
            WHERE cv.id = s.current_version_id
            """
        )
    )
    bind.execute(sa.text("UPDATE skills SET status = COALESCE(status, 'published')"))
    bind.execute(
        sa.text(
            """
            UPDATE skill_versions AS sv
            SET
                artifact_rel_path = format('db://skills/%s/%s/content.md', s.slug, sv.version),
                artifact_size_bytes = sc.storage_size_bytes,
                is_published = (sv.lifecycle_status <> 'archived'),
                manifest_json = jsonb_strip_nulls(
                    jsonb_build_object(
                        'skill_id', s.slug,
                        'version', sv.version,
                        'name', sm.name,
                        'description', sm.description,
                        'tags', to_jsonb(COALESCE(sm.tags, ARRAY[]::text[])),
                        'headers', sm.headers,
                        'inputs_schema', sm.inputs_schema,
                        'outputs_schema', sm.outputs_schema,
                        'token_estimate', sm.token_estimate,
                        'maturity_score', sm.maturity_score,
                        'security_score', sm.security_score,
                        'depends_on', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_strip_nulls(
                                        jsonb_build_object(
                                            'skill_id', selector.target_slug,
                                            'version', selector.target_version,
                                            'version_constraint', selector.version_constraint,
                                            'optional', selector.optional,
                                            'markers',
                                            to_jsonb(
                                                COALESCE(selector.markers, ARRAY[]::text[])
                                            )
                                        )
                                    )
                                    ORDER BY selector.ordinal
                                )
                                FROM skill_relationship_selectors AS selector
                                WHERE selector.source_skill_version_fk = sv.id
                                  AND selector.edge_type = 'depends_on'
                            ),
                            '[]'::jsonb
                        ),
                        'extends', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_strip_nulls(
                                        jsonb_build_object(
                                            'skill_id', selector.target_slug,
                                            'version', selector.target_version
                                        )
                                    )
                                    ORDER BY selector.ordinal
                                )
                                FROM skill_relationship_selectors AS selector
                                WHERE selector.source_skill_version_fk = sv.id
                                  AND selector.edge_type = 'extends'
                            ),
                            '[]'::jsonb
                        ),
                        'conflicts_with', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_strip_nulls(
                                        jsonb_build_object(
                                            'skill_id', selector.target_slug,
                                            'version', selector.target_version
                                        )
                                    )
                                    ORDER BY selector.ordinal
                                )
                                FROM skill_relationship_selectors AS selector
                                WHERE selector.source_skill_version_fk = sv.id
                                  AND selector.edge_type = 'conflicts_with'
                            ),
                            '[]'::jsonb
                        ),
                        'overlaps_with', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_strip_nulls(
                                        jsonb_build_object(
                                            'skill_id', selector.target_slug,
                                            'version', selector.target_version
                                        )
                                    )
                                    ORDER BY selector.ordinal
                                )
                                FROM skill_relationship_selectors AS selector
                                WHERE selector.source_skill_version_fk = sv.id
                                  AND selector.edge_type = 'overlaps_with'
                            ),
                            '[]'::jsonb
                        )
                    )
                )
            FROM skills AS s
            JOIN skill_metadata AS sm
              ON sm.id = sv.metadata_fk
            JOIN skill_contents AS sc
              ON sc.id = sv.content_fk
            WHERE s.id = sv.skill_fk
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO skill_version_checksums (skill_version_fk, algorithm, digest)
            SELECT id, 'sha256', checksum_digest
            FROM skill_versions
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO skill_relationship_edges (
                source_skill_version_fk,
                edge_type,
                target_skill_id,
                target_version_selector
            )
            SELECT
                selector.source_skill_version_fk,
                selector.edge_type,
                selector.target_slug,
                COALESCE(selector.target_version, selector.version_constraint)
            FROM skill_relationship_selectors AS selector
            WHERE selector.edge_type IN ('depends_on', 'extends')
              AND COALESCE(selector.target_version, selector.version_constraint) IS NOT NULL
            ON CONFLICT ON CONSTRAINT uq_skill_relationship_edges_source_type_target_selector
            DO NOTHING
            """
        )
    )

    op.alter_column("skills", "skill_id", nullable=False)
    op.alter_column("skill_versions", "manifest_json", nullable=False)
    op.alter_column("skill_versions", "artifact_rel_path", nullable=False)
    op.alter_column("skill_versions", "artifact_size_bytes", nullable=False)


def _drop_search_document_governance_columns() -> None:
    op.drop_index("ix_skill_search_documents_trust_tier", table_name="skill_search_documents")
    op.drop_index(
        "ix_skill_search_documents_lifecycle_status",
        table_name="skill_search_documents",
    )
    op.drop_constraint(
        "ck_skill_search_documents_trust_tier",
        "skill_search_documents",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_search_documents_lifecycle_status",
        "skill_search_documents",
        type_="check",
    )
    op.drop_column("skill_search_documents", "trust_tier")
    op.drop_column("skill_search_documents", "lifecycle_status")


def _drop_version_governance_columns() -> None:
    op.drop_constraint("ck_skill_versions_trust_tier", "skill_versions", type_="check")
    op.drop_constraint("ck_skill_versions_lifecycle_status", "skill_versions", type_="check")
    op.drop_column("skill_versions", "provenance_tree_path")
    op.drop_column("skill_versions", "provenance_commit_sha")
    op.drop_column("skill_versions", "provenance_repo_url")
    op.drop_column("skill_versions", "trust_tier")
    op.drop_column("skill_versions", "lifecycle_changed_at")
    op.drop_column("skill_versions", "lifecycle_status")
