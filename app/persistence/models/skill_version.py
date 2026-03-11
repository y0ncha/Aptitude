"""Normalized immutable skill version model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base

if TYPE_CHECKING:
    from app.persistence.models.skill import Skill
    from app.persistence.models.skill_content import SkillContent
    from app.persistence.models.skill_dependency import SkillDependency
    from app.persistence.models.skill_metadata import SkillMetadata
    from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
    from app.persistence.models.skill_version_checksum import SkillVersionChecksum


class SkillVersion(Base):
    """Represents one immutable published version bound to normalized content and metadata."""

    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_fk", "version", name="uq_skill_versions_skill_fk_version"),
        Index(
            "ix_skill_versions_skill_fk_published_at_id",
            "skill_fk",
            "published_at",
            "id",
        ),
        Index("ix_skill_versions_skill_fk_version", "skill_fk", "version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    content_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_contents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    metadata_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_metadata.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    checksum_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_published: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("true"),
    )
    # Legacy compatibility mirror retained for reversible migration safety.
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifact_rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    skill: Mapped[Skill] = relationship(
        back_populates="versions",
        foreign_keys=[skill_fk],
    )
    content: Mapped[SkillContent] = relationship()
    metadata_row: Mapped[SkillMetadata] = relationship()
    checksum: Mapped[SkillVersionChecksum | None] = relationship(
        back_populates="skill_version",
        uselist=False,
    )
    relationship_selectors: Mapped[list[SkillRelationshipSelector]] = relationship(
        cascade="all, delete-orphan",
        order_by="SkillRelationshipSelector.ordinal",
        back_populates="skill_version",
    )
    dependencies_from: Mapped[list[SkillDependency]] = relationship(
        cascade="all, delete-orphan",
        foreign_keys="SkillDependency.from_version_fk",
        back_populates="source_version",
    )
