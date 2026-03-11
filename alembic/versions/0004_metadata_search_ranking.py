"""Add metadata search read model and indexes.

Revision ID: 0004_metadata_search_ranking
Revises: 0003_deterministic_dependency_resolution
Create Date: 2026-03-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_metadata_search_ranking"
down_revision = "0003_deterministic_dependency_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
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


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_documents_normalized_tags_gin")
    op.execute("DROP TRIGGER IF EXISTS trg_skill_search_documents_vector ON skill_search_documents")
    op.execute("DROP FUNCTION IF EXISTS update_skill_search_documents_vector()")
    op.drop_index(
        "ix_skill_search_documents_artifact_size_bytes",
        table_name="skill_search_documents",
    )
    op.drop_index(
        "ix_skill_search_documents_published_at",
        table_name="skill_search_documents",
    )
    op.drop_index(
        "ix_skill_search_documents_normalized_name",
        table_name="skill_search_documents",
    )
    op.drop_index(
        "ix_skill_search_documents_normalized_skill_id",
        table_name="skill_search_documents",
    )
    op.drop_table("skill_search_documents")
