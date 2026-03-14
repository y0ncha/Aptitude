"""Create the canonical aptitude-server schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-13
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("slug", name="uq_skills_slug"),
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

    op.create_table(
        "skill_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("skill_fk", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("content_fk", sa.BigInteger(), nullable=False),
        sa.Column("metadata_fk", sa.BigInteger(), nullable=False),
        sa.Column("checksum_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
        sa.Column(
            "lifecycle_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "trust_tier",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'untrusted'"),
        ),
        sa.Column("provenance_repo_url", sa.Text(), nullable=True),
        sa.Column("provenance_commit_sha", sa.Text(), nullable=True),
        sa.Column("provenance_tree_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('published', 'deprecated', 'archived')",
            name="ck_skill_versions_lifecycle_status",
        ),
        sa.CheckConstraint(
            "trust_tier IN ('untrusted', 'internal', 'verified')",
            name="ck_skill_versions_trust_tier",
        ),
        sa.ForeignKeyConstraint(["skill_fk"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_fk"], ["skill_contents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["metadata_fk"], ["skill_metadata.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("skill_fk", "version", name="uq_skill_versions_skill_fk_version"),
    )
    op.create_index("ix_skill_versions_skill_fk", "skill_versions", ["skill_fk"])
    op.create_index("ix_skill_versions_content_fk", "skill_versions", ["content_fk"])
    op.create_index("ix_skill_versions_metadata_fk", "skill_versions", ["metadata_fk"])
    op.create_index(
        "ix_skill_versions_skill_fk_published_at_id",
        "skill_versions",
        ["skill_fk", "published_at", "id"],
    )
    op.create_index(
        "ix_skill_versions_skill_fk_version",
        "skill_versions",
        ["skill_fk", "version"],
    )

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
        sa.Column("markers", postgresql.ARRAY(sa.Text()), nullable=False),
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
        "skill_search_documents",
        sa.Column("skill_version_fk", sa.BigInteger(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("normalized_slug", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("normalized_tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
        sa.Column(
            "trust_tier",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'untrusted'"),
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            nullable=False,
            server_default=sa.text("''::tsvector"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "usage_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('published', 'deprecated', 'archived')",
            name="ck_skill_search_documents_lifecycle_status",
        ),
        sa.CheckConstraint(
            "trust_tier IN ('untrusted', 'internal', 'verified')",
            name="ck_skill_search_documents_trust_tier",
        ),
        sa.ForeignKeyConstraint(["skill_version_fk"], ["skill_versions.id"], ondelete="CASCADE"),
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
    op.create_index(
        "ix_skill_search_documents_normalized_tags_gin",
        "skill_search_documents",
        ["normalized_tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_skill_search_documents_search_vector_gin",
        "skill_search_documents",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("skill_search_documents")
    op.drop_table("skill_relationship_selectors")
    op.drop_table("skill_versions")
    op.drop_table("skill_metadata")
    op.drop_table("skill_contents")
    op.drop_table("skills")
    op.drop_table("audit_events")
