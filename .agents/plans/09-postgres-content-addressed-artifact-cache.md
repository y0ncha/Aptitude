# Plan 09 — PostgreSQL Content-Addressed Artifact Storage

## Goal
Improve read performance and storage efficiency by introducing content-addressed artifact storage in PostgreSQL with immutable HTTP cache semantics.

## Stack Alignment
- Runtime: Python 3.12+
- API surface: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL as the source of truth for artifact identity, artifact payloads, and version mapping

## Scope
- Introduce split PostgreSQL tables for metadata and payload storage (for example, `skill_versions` plus `artifact_objects` keyed by `sha256_digest`).
- Map immutable `skill_id+version` records to artifact digest (`skill_versions -> artifact_objects.sha256_digest`).
- Enforce deterministic digest binding and immutability constraints at publish time.
- Add HTTP cache behavior for immutable reads (`ETag`, `Cache-Control: immutable`, conditional `If-None-Match` support).
- Keep resolver ownership boundaries intact (no server-side dependency closure solving).

## Architecture Impact
- Adds a content-addressed storage layer while preserving existing registry API contracts.
- Reduces duplicate artifact payload writes for identical content across versions.
- Keeps discovery and exact fetch logically separate through schema and query-path design rather than separate storage backends.
- Improves metadata and artifact fetch efficiency through cache validation and `304` reuse.

## Deliverables
- Alembic migration for split-table artifact schema and `skill_version` mapping.
- Repository and service-layer changes for publish path digest computation and deduplicated writes.
- API support for stable `ETag` values on immutable reads and conditional response handling.
- Integrity checks aligned to digest-addressed mapping and audit emission.
- Learning note on content-addressed modeling tradeoffs in PostgreSQL.

## Acceptance Criteria
- Publishing identical artifact content across different versions reuses a single digest-addressed artifact row.
- Each immutable `skill_id+version` maps to exactly one digest and cannot be overwritten.
- Immutable read endpoints return stable `ETag` and `Cache-Control` headers.
- Requests with matching `If-None-Match` return `304 Not Modified`.
- Existing registry boundary rules remain unchanged (no resolver-owned semantics added).

## Test Plan
- Integration test: publish multiple versions with identical content and verify digest deduplication behavior.
- Integration test: publish different content and verify distinct digests are stored and mapped correctly.
- API test: immutable read returns expected `ETag` and cache headers.
- API test: conditional request with matching `If-None-Match` returns `304`.
- Regression test: duplicate `skill_id+version` publish remains deterministically rejected.

## Change Note (2026-03-10)
- This plan is the canonical storage direction for skill artifacts.
- Retain the digest-addressed identity, deduplication, and immutable HTTP cache semantics from this plan.
- Use PostgreSQL only, with split metadata and payload tables; do not add filesystem or object-storage persistence for current skill artifacts.
