"""Normalized skill identity model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base

if TYPE_CHECKING:
    from app.persistence.models.skill_version import SkillVersion


class Skill(Base):
    """Represents a logical skill identity keyed by public slug."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Legacy column retained as an internal compatibility mirror during the cutover.
    skill_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    current_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("skill_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'published'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list[SkillVersion]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        foreign_keys="SkillVersion.skill_fk",
    )
