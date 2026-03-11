"""Markdown content storage model."""

from __future__ import annotations

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillContent(Base):
    """Stores canonical markdown bodies in PostgreSQL text columns."""

    __tablename__ = "skill_contents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
