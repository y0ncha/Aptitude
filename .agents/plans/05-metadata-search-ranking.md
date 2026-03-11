# Plan 05 — Normalized Metadata Search, Ranking, and Body Storage

## Goal
Provide high-performance candidate retrieval and advisory ranking over skill metadata while restructuring the PostgreSQL schema so identity, versioning, body storage, query metadata, and graph edges are cleanly separated.

This milestone is no longer just "add search." It is the schema-normalization step that makes search, exact fetch, and future governance features cheaper to evolve.

## Current Review Summary
The current implementation proves the API shape, but it keeps too much concern-mixing in one version row:

- `skill_versions.manifest_json` currently mixes human-readable metadata, dependency declarations, and authored content-facing fields.
- `skill_versions.artifact_rel_path` still points exact fetch at filesystem storage, which conflicts with the newer PostgreSQL-only storage direction.
- `skill_search_documents` is already compensating for the mixed source model by extracting discovery fields into a derived table.
- `skill_relationship_edges` preserves authored selectors, but it is still a projection from `manifest_json` rather than a first-class graph/relationship model.

The result is workable for MVP search, but it is not the right long-term source model for immutable versioning plus metadata-heavy discovery.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL as the only authoritative store for identity, versions, metadata, content, and derived search read models
- Search and indexing: PostgreSQL native full-text, B-tree, and GIN index strategy

## Target Source Model
Adopt the following source-of-truth split:

- `skills`
  - stable identity and lifecycle state
- `skill_versions`
  - immutable version rows and publication state
- `skill_contents`
  - authored markdown body and body-derived summary fields
- `skill_metadata`
  - queryable metadata used for filtering, ranking, and discovery payloads
- `skill_dependencies`
  - version-to-version graph edges plus authored constraint text
- `skill_search_documents`
  - optional denormalized read model for fast advisory discovery

This preserves one transactional database while separating:

- identity
- versioning
- body
- query metadata
- graph edges

## PostgreSQL / TOAST Strategy
Use PostgreSQL `text` for markdown storage.

- Store the canonical skill body in `skill_contents.raw_markdown`.
- Do not store markdown as `json`, `jsonb`, bytea blobs, or PostgreSQL large objects.
- Let PostgreSQL manage large variable-length rows with normal TOAST behavior.
- Default to `EXTENDED` storage behavior for `raw_markdown`; do not force `EXTERNAL` up front.
- Consider `ALTER COLUMN ... SET STORAGE EXTERNAL` only if profiling shows substring-heavy workflows where avoiding decompression materially helps.
- Keep list/search/rank query paths body-free so discovery requests do not touch TOASTed markdown unnecessarily.

## Scope
- Replace the current mixed `manifest_json` source model with normalized tables for identity, version, content, metadata, and dependencies.
- Keep immutable version rows write-once after publish; updating a published skill body must create a new `skill_versions` row.
- Store markdown body checksums and, where useful, metadata checksums for deduplication, integrity, and cache identity.
- Make search/list/filter APIs operate on metadata tables or derived read models without joining raw markdown by default.
- Preserve compact discovery payloads and deterministic ranking semantics.
- Keep ranking advisory; resolver remains authoritative for reranking, final selection, dependency solving, and lock output.
- Explicitly exclude prompt parsing, personalized ranking, environment-aware selection, and server-side solve behavior.

## Proposed Table Direction
Base schema direction for this milestone:

- `skills`
  - `id`
  - `slug`
  - `current_version_id`
  - `created_at`
  - `updated_at`
  - `status`
- `skill_versions`
  - `id`
  - `skill_id`
  - `version`
  - `content_id`
  - `metadata_id`
  - `checksum`
  - `created_at`
  - `published_at`
  - `is_published`
- `skill_contents`
  - `id`
  - `raw_markdown`
  - `rendered_summary`
  - `storage_size_bytes`
  - `checksum`
- `skill_metadata`
  - `id`
  - `name`
  - `description`
  - `tags`
  - `headers`
  - `inputs_schema`
  - `outputs_schema`
  - `token_estimate`
  - `maturity_score`
  - `security_score`
- `skill_dependencies`
  - `from_version_id`
  - `to_version_id`
  - `constraint_type`
  - `version_constraint`

## Query and Index Strategy
Index for the actual registry query path, not for hypothetical generic flexibility:

- `skills(slug)` unique
- `skills(status, updated_at)` for lifecycle/admin views if needed
- `skill_versions(skill_id, version)` unique
- `skill_versions(is_published, published_at DESC)`
- `skill_versions(content_id)`
- `skill_versions(metadata_id)`
- `skill_versions(checksum)` if used for version-level dedup or cache identity
- `skill_dependencies(from_version_id)`
- `skill_dependencies(to_version_id)`
- `GIN` on `skill_metadata.tags` if tags remain `text[]`
- `GIN` on `skill_metadata.headers` only if queried by containment
- `BTREE` on `skill_metadata.token_estimate`, `maturity_score`, `security_score`, and `published_at`-adjacent ranking fields when those become filter/sort inputs
- `GIN` on `skill_search_documents.search_vector` for advisory text search

Prefer typed columns first and `jsonb` second:

- Columns first for `slug`, `version`, `status`, `token_estimate`, scores, and `published_at`
- `jsonb` only for evolving structures such as header maps and IO schemas

## Deliverables
- Alembic design and migration plan from the current `manifest_json + filesystem artifact` layout to normalized PostgreSQL tables.
- Repository/service refactor plan for publish, fetch, list, and search paths.
- Canonical schema document for tables, keys, indexes, and ownership boundaries.
- Search/read-model design that keeps discovery metadata-centric and body-free.
- Ranking rule chain with deterministic fallback and rationale fields.
- Learning note on TOAST, typed columns vs `jsonb`, and immutable version storage.

## Acceptance Criteria
- Search results are relevant to filters and query text.
- Ranking is stable for equal-score candidates.
- Search/list APIs do not require reading `skill_contents.raw_markdown`.
- Published version bodies are never updated in place.
- Checksum-backed content identity is available for integrity and deduplication.
- Lifecycle state lives on identity/version rows, not hidden inside opaque JSON.
- Search contract clearly remains advisory and non-authoritative for final resolver choice.

## Migration Notes
- Backfill `skills.slug` from the existing `skills.skill_id`.
- Split `skill_versions.manifest_json` into:
  - one content row
  - one metadata row
  - one or more dependency rows
- Replace filesystem `artifact_rel_path` usage with PostgreSQL-backed content lookup aligned to the storage strategy plans.
- Preserve old API contracts during transition by reconstructing legacy DTOs from normalized tables.
- Keep `skill_search_documents` derived and rebuildable; it must not become the source of truth.

## Open Design Questions
- `skill_dependencies` as listed above assumes version-to-version edges. If authored dependency selectors can remain unresolved at publish time, add one extra target identity field or a small companion selector table rather than pushing the ambiguity back into `jsonb`.
- `current_version_id` should be treated as a mutable pointer on `skills`, while `skill_versions` rows remain immutable.
- Tags can start as `text[]` plus a GIN index; normalize later only if tag governance or analytics require first-class tag entities.

## Test Plan
- Migration test: backfill normalized tables from existing rows without checksum or content loss.
- Integration test: publish multiple versions and verify immutable version-row creation.
- Integration test: list/search endpoints avoid reading raw markdown content.
- PostgreSQL full-text tests for name, description, and tag matching.
- Deterministic sort tests under tie conditions.
- Regression tests for ranking rationale fields and compact candidate payload shape.
- Storage test: large markdown values persist correctly via `text` with normal PostgreSQL TOAST behavior.
