# Plan 11 - Discovery / Relationship / Fetch Surface Split

Legacy filename retained under the append-only roadmap rule. This plan does not introduce server-side resolution semantics.

## Goal
Make the read side of `aptitude-server` explicit and future-proof by separating discovery, direct relationship reads, and exact fetch behavior into distinct service surfaces without changing the single-process deployment model.

## Stack Alignment
- API framework: FastAPI with OpenAPI-first contracts
- Runtime: Python 3.12+
- Data layer: PostgreSQL metadata/read models via SQLAlchemy 2.0
- Artifact backend: PostgreSQL split tables for metadata and digest-addressed payload rows

## Scope
- Introduce explicit `discovery`, `relationships`, and `fetch` core services, with compatibility routing where legacy path names still contain `resolution`.
- Keep discovery advisory and data-local, consistent with plan `05-metadata-search-ranking.md`.
- Add direct relationship read APIs for authored `depends_on` and `extends` edges only; no transitive traversal or solver behavior.
- Add exact metadata fetch and artifact streaming APIs with ordered batch reads and PostgreSQL-backed payload retrieval.
- Preserve legacy combined search/fetch routes as deprecated compatibility facades during transition.
- Keep the fetch contract aligned with the PostgreSQL-only storage direction in `10-postgres-only-artifact-storage-and-provenance.md`.

## Architecture Impact
- Hardens the server/client boundary by making discovery, relationship lookup, and exact fetch separate public capabilities.
- Prevents relationship reads from drifting into server-side solving.
- Separates discovery and exact fetch query paths while keeping one transactional persistence system.

## Deliverables
- New routers:
  - `GET /discovery/skills/search`
  - `POST /resolution/relationships:batch` as a legacy compatibility path for direct relationship reads
  - `POST /fetch/skill-versions:batch`
  - `GET /fetch/skills/{skill_id}/{version}`
  - `GET /fetch/skills/{skill_id}/{version}/artifact`
- New core services and read ports for discovery, direct relationship lookup, and exact fetch.
- Fetch DTOs with immutable artifact identity fields instead of storage-relative paths as the primary contract.
- Deprecated legacy route docs for `GET /skills/search` and `GET /skills/{skill_id}/{version}`.

## Acceptance Criteria
- Discovery remains advisory and identical in behavior to the legacy search route.
- Direct relationship reads return only authored `depends_on` and `extends` edges in manifest order.
- The legacy `resolution` route name is documented as a compatibility label only; the server capability is direct relationship retrieval.
- Relationship reads never expand transitive graphs, select versions for constraints, or produce locks/plans.
- Batch fetch preserves request order and returns per-item `found` / `not_found` results.
- Exact metadata fetch avoids inlining artifact bytes.
- Artifact streaming remains checksum-verified and immutable-cache-friendly.

## Test Plan
- Unit tests for new DTOs and OpenAPI examples.
- OpenAPI path boundary tests covering both new and compatibility routes.
- Integration tests for:
  - metadata fetch plus artifact streaming
  - ordered batch fetch behavior
  - direct relationship reads and authored ordering
  - discovery parity between legacy and new routes
- Regression tests for legacy compatibility routes.

## Follow-up Notes
- March 10, 2026: typing hardening work for the split read-side surfaces is part of this milestone, not a separate plan.
- The follow-up keeps discovery parity and relationship/fetch behavior unchanged while tightening internal contracts:
  - shared conversion from `StoredSkillVersionSummary` to `SkillVersionSummary`
  - literal edge typing for direct relationship reads
  - non-optional FastAPI dependency signatures for discovery compatibility routes
- Verification for this follow-up must follow the large-change workflow in `.agents/rules/repo.md`: review current code first, then run `make lint`, `make typecheck`, `make test`, and update milestone documentation.
