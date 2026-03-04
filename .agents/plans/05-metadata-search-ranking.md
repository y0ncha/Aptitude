# Plan 05 — Metadata Search and Ranking

## Goal
Provide discoverability and deterministic ranking using structured metadata signals.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Search and indexing: PostgreSQL native full-text and index strategy from milestone 1

## Scope
- Add metadata model (`freshness`, `footprint`, `usage_count`, provenance fields).
- Build indexing and query path for metadata-driven filtering.
- Add search endpoint with deterministic sorting.
- Return ranking explanation fields.

## Architecture Impact
- Expands intelligence layer (metadata engine and indexing).
- Keeps selection signals explicit and queryable.

## Deliverables
- Endpoint: `GET /v1/skills/search`.
- Metadata tables and PostgreSQL indexes (including full-text search support).
- Ranking rule chain with deterministic fallback.
- Search response fields for ranking rationale.
- Learning note on derived data vs source-of-truth separation.

## Acceptance Criteria
- Search results are relevant to filters and query text.
- Ranking is stable for equal-score candidates.
- Metadata updates never mutate skill artifacts.

## Test Plan
- Integration tests for filter combinations.
- Deterministic sort tests under tie conditions.
- PostgreSQL full-text tests for name, description, and tag matching.
- Regression tests for ranking rationale fields.
