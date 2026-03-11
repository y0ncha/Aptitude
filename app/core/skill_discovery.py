"""Core discovery service for indexed advisory candidate retrieval."""

from __future__ import annotations

from app.core.skill_search import SkillSearchService


class SkillDiscoveryService(SkillSearchService):
    """Named discovery service facade over the existing advisory search implementation."""
