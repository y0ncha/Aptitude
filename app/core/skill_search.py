"""Core advisory search service and domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.ports import AuditPort, SearchCandidatesRequest, SkillSearchPort
from app.intelligence.search_ranking import (
    build_search_audit_payload,
    build_search_explanation,
    normalize_search_request,
)


@dataclass(frozen=True, slots=True)
class SkillSearchQuery:
    """External advisory search request owned by the core layer."""

    q: str | None
    tags: tuple[str, ...]
    language: str | None
    fresh_within_days: int | None
    max_footprint_bytes: int | None
    limit: int


@dataclass(frozen=True, slots=True)
class SkillSearchResult:
    """Compact advisory search card returned to the API layer."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    published_at: datetime
    freshness_days: int
    content_size_bytes: int
    usage_count: int
    matched_fields: tuple[str, ...]
    matched_tags: tuple[str, ...]
    reasons: tuple[str, ...]


class SkillSearchService:
    """Read-only search service for indexed candidate retrieval."""

    def __init__(self, *, search_port: SkillSearchPort, audit_recorder: AuditPort) -> None:
        self._search_port = search_port
        self._audit_recorder = audit_recorder

    def search(self, *, query: SkillSearchQuery) -> tuple[SkillSearchResult, ...]:
        """Return compact, deterministically explained search candidates."""
        normalized_request = normalize_search_request(
            q=query.q,
            tags=query.tags,
            language=query.language,
            fresh_within_days=query.fresh_within_days,
            max_footprint_bytes=query.max_footprint_bytes,
            limit=query.limit,
        )
        stored_results = self._search_port.search_candidates(
                request=SearchCandidatesRequest(
                    query_text=normalized_request.query_text,
                    required_tags=normalized_request.effective_tags,
                    fresh_within_days=normalized_request.fresh_within_days,
                    max_content_size_bytes=normalized_request.max_footprint_bytes,
                    limit=normalized_request.limit,
                )
            )
        current_time = datetime.now(UTC)

        results = tuple(
            SkillSearchResult(
                slug=item.slug,
                version=item.version,
                name=item.name,
                description=item.description,
                tags=item.tags,
                published_at=item.published_at,
                freshness_days=max((current_time - item.published_at).days, 0),
                content_size_bytes=item.content_size_bytes,
                usage_count=item.usage_count,
                matched_fields=explanation.matched_fields,
                matched_tags=explanation.matched_tags,
                reasons=explanation.reasons,
            )
            for item in stored_results
            for explanation in (
                build_search_explanation(
                    query_terms=normalized_request.query_terms,
                    requested_tags=normalized_request.effective_tags,
                    slug=item.slug,
                    name=item.name,
                    description=item.description,
                    tags=item.tags,
                    exact_slug_match=item.exact_slug_match,
                    exact_name_match=item.exact_name_match,
                    lexical_score=item.lexical_score,
                    tag_overlap_count=item.tag_overlap_count,
                ),
            )
        )

        self._audit_recorder.record_event(
            event_type="skill.search_performed",
            payload=build_search_audit_payload(
                request=normalized_request,
                result_count=len(results),
            ),
        )
        return results
