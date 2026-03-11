"""Exact immutable dependency edges between version rows."""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base


class SkillDependency(Base):
    """Stores exact version-to-version relationship edges when resolvable."""

    __tablename__ = "skill_dependencies"
    __table_args__ = (
        CheckConstraint(
            "constraint_type IN ('depends_on', 'extends', 'conflicts_with', 'overlaps_with')",
            name="ck_skill_dependencies_constraint_type",
        ),
        Index("ix_skill_dependencies_from_version_fk", "from_version_fk"),
        Index("ix_skill_dependencies_to_version_fk", "to_version_fk"),
        Index(
            "uq_skill_dependencies_exact_edge",
            "from_version_fk",
            "to_version_fk",
            "constraint_type",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_version_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_version_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    constraint_type: Mapped[str] = mapped_column(Text, nullable=False)
    version_constraint: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_version = relationship(
        "SkillVersion",
        foreign_keys=[from_version_fk],
        back_populates="dependencies_from",
    )
