# Plan 08 - Canonical PostgreSQL Storage Finalization

## Goal
Finalize the registry on a single PostgreSQL runtime storage model shaped directly around the hard-cut MVP read contract from Plan 07: discovery candidate lookup, exact first-degree dependency reads, exact immutable metadata fetch, and exact immutable content fetch. Storage finalization must stay behind that simple endpoint surface and must not create pressure for new public routes or route variants.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL as the only authoritative runtime store

## Scope
- Finalize PostgreSQL as the only runtime persistence layer for:
  - discovery-facing metadata
  - exact dependency declarations
  - immutable version metadata
  - digest-addressed immutable content payloads
  - lifecycle state, provenance metadata, and audit references
- Keep storage optimized for the Plan 07 public reads:
  - discovery lookup by `name`, optional `description`, and optional `tags`, returning slug candidates
  - exact direct dependency retrieval for one immutable `slug@version`
  - exact metadata fetch for one immutable coordinate
  - exact content fetch backed by digest-addressed PostgreSQL rows
- Keep discovery reads off raw content rows by default.
- Keep dependency rows canonical for exact first-degree reads only; do not optimize for server-side recursive traversal or solving.
- Deduplicate identical content payloads by digest and bind immutable `slug + version` records to those content rows.
- Keep storage concerns fully behind the fixed Plan 07 route set; schema and repository choices must not add public discovery, resolution, or fetch endpoint variants.
- Remove schema, repository, and migration artifacts that exist only to support deleted read routes or compatibility behavior.

## Architecture Impact
- Freezes PostgreSQL as the only runtime dependency for all public read paths.
- Aligns storage with the simplified public contract instead of preserving deleted batch-fetch shapes or legacy search variants.
- Prevents storage optimization from leaking complexity into the public API surface.
- Reduces long-term debt by making removed public routes irrelevant to schema design and repository shape.

## Deliverables
- Canonical schema direction for discovery metadata, dependency declarations, immutable version metadata, digest-backed content rows, lifecycle state, provenance, and audit references.
- Repository and service expectations for `POST /discovery`, `GET /resolution/{slug}/{version}`, `GET /skills/{slug}/versions/{version}`, and `GET /skills/{slug}/versions/{version}/content`.
- Cleanup plan for legacy tables, columns, or projections that only exist to serve removed public routes.
- Storage note clarifying that exact metadata and content reads are served directly from canonical PostgreSQL rows without route-specific compatibility structures.

## Acceptance Criteria
- PostgreSQL is the only planned runtime store for metadata, dependency declarations, content payloads, digest bindings, provenance, and audit references.
- Discovery queries do not need to touch raw content storage for routine candidate retrieval.
- Resolution reads return exact first-degree dependency declarations from canonical PostgreSQL rows.
- Metadata fetch is served from immutable version and metadata rows without reconstructing deleted batch DTOs.
- Content fetch is served from digest-addressed PostgreSQL content rows and does not require filesystem, Git, or object storage.
- Identical content payloads published under different versions reuse one digest-addressed content row.
- Storage finalization does not introduce any new public discovery, resolution, or fetch endpoint family.
- The plan does not preserve any schema or repository accommodations for the removed public read routes.

## Test Plan
- Integration test: publish identical content under multiple versions and verify digest deduplication.
- Integration test: publish distinct content and verify distinct digest rows plus exact content fetch behavior.
- Persistence test: discovery queries remain metadata-only and do not read raw content rows by default.
- Resolution test: exact `slug@version` lookup returns direct dependency declarations without recursive traversal.
- Cleanup test: legacy storage artifacts required only by removed routes are absent from the final schema direction.

## Implementation Notes

### 2026-03-14
- Rebaselined the canonical schema to remove `skill_dependencies` and `skills.current_version_id`; selector rows are now the only runtime dependency source and current-default status is derived from `skill_versions` ordering instead of a persisted pointer.
- Removed identity/list-only core and persistence APIs, narrowed the repository to publish/status plus the four Plan 07 read paths, and kept discovery on the `skill_search_documents` read model without touching raw content rows.
- Added integration coverage for digest deduplication, distinct content storage, exact metadata/content fetch, metadata-only discovery SQL, and the updated migration baseline.
- Verified with:
  - `uv run pytest tests/unit/test_skill_registry_service.py tests/unit/test_skill_version_projections.py tests/integration/test_migrations.py tests/integration/test_skill_registry_endpoints.py`
  - `uv run ruff check app tests alembic`
