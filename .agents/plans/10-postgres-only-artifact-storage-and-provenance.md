# Plan 10 - PostgreSQL-Only Artifact Storage and Provenance Metadata

## Goal
Keep PostgreSQL as the only runtime persistence layer for registry metadata, digest mappings, and immutable artifact payloads, while capturing provenance strictly as publish-time metadata.

## Stack Alignment
- Runtime: Python 3.12+
- API surface: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Metadata authority: PostgreSQL for versions, manifests, lifecycle state, provenance metadata, and audit
- Artifact backend: PostgreSQL split metadata/payload tables keyed by immutable digest

## Scope
- Keep `skill_id+version`, artifact digests, and version-to-digest bindings canonical in PostgreSQL.
- Store artifact payloads in PostgreSQL only, using split metadata and payload tables aligned with `docs/storage-strategy-report.md`.
- Reuse identical payload rows by digest while preserving write-once version bindings.
- Capture provenance metadata such as `repo_url`, `commit_sha`, `tree_path`, publisher identity, and trust context at publish time.
- Preserve immutable HTTP cache semantics (`ETag`, conditional reads) derived from PostgreSQL-stored digests.
- Explicitly exclude filesystem storage, object storage, Git-backed reads, and any hybrid runtime storage model.
- Preserve client ownership boundaries: no server-side solving, lock generation, or final candidate selection.

## Architecture Impact
- Confirms the storage direction recommended in `docs/storage-strategy-report.md`: one transactional persistence system with separate discovery and exact-fetch query paths.
- Preserves deduplication and integrity guarantees without cross-store consistency failure modes.
- Treats provenance as advisory metadata and audit context, never as a second source of truth for runtime reads.

## Deliverables
- Alembic migration for PostgreSQL-only digest-addressed artifact payload tables and normalized provenance fields.
- Repository and service-layer changes so versions bind immutably to PostgreSQL payload rows.
- API and audit support for provenance metadata on publish and immutable cache headers on exact fetch.
- Documentation note explaining why PostgreSQL-only storage is the required architecture for the current product phase.

## Acceptance Criteria
- Publishing identical artifact content across different versions reuses a single PostgreSQL payload row while preserving distinct immutable version records.
- PostgreSQL remains the source of truth for version metadata, artifact payloads, digest mappings, lifecycle state, provenance metadata, and audit history.
- Exact fetch, search, and list behavior do not require access to a Git repository, working tree, local mirror, filesystem path, or object-store bucket.
- Provenance metadata is optional and, when supplied, is returned as advisory metadata rather than used as a storage backend or runtime read dependency.
- Immutable read endpoints return stable `ETag` and `Cache-Control` headers derived from the PostgreSQL-stored payload digest.

## Test Plan
- Integration test: publish multiple versions with identical content and verify payload deduplication plus stable digest mapping.
- Integration test: publish with provenance metadata and verify exact fetch returns the stored provenance fields.
- Regression test: artifact fetch continues to work when no provenance metadata is present.
- API test: conditional immutable reads return `304` with stable `ETag`.
- Persistence test: PostgreSQL-only split storage honors write-once semantics and digest-addressed lookup contracts.
