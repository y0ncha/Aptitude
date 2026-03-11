# Plan 11 - Discovery / Resolution / Fetch Service Split

## Goal
Make the read side of `aptitude-server` explicit and future-proof by separating discovery, direct relationship reads, and exact fetch behavior into distinct service surfaces without changing the single-process deployment model.

## Stack Alignment
- API framework: FastAPI with OpenAPI-first contracts
- Runtime: Python 3.12+
- Data layer: PostgreSQL metadata/read models via SQLAlchemy 2.0
- Artifact backend: PostgreSQL split tables for metadata and digest-addressed payload rows

## Scope
- Introduce explicit `discovery`, `resolution`, and `fetch` routers and core services.
- Keep discovery advisory and data-local, consistent with plan `05-metadata-search-ranking.md`.
- Add direct relationship read APIs for authored `depends_on` and `extends` edges only; no transitive traversal or solver behavior.
- Add exact metadata fetch and artifact streaming APIs with ordered batch reads and PostgreSQL-backed payload retrieval.
- Preserve legacy combined search/fetch routes as deprecated compatibility facades during transition.
- Keep the fetch contract aligned with the split-table PostgreSQL direction in `10-hybrid-artifact-storage-and-git-provenance.md`.

## Architecture Impact
- Hardens the server/client boundary by making discovery, relationship lookup, and exact fetch separate public capabilities.
- Prevents relationship reads from drifting into server-side solving.
- Separates discovery and exact fetch query paths while keeping one transactional persistence system.

## Deliverables
- New routers:
  - `GET /discovery/skills/search`
  - `POST /resolution/relationships:batch`
  - `POST /fetch/skill-versions:batch`
  - `GET /fetch/skills/{skill_id}/{version}`
  - `GET /fetch/skills/{skill_id}/{version}/artifact`
- New core services and read ports for discovery, direct relationship lookup, and exact fetch.
- Fetch DTOs with immutable artifact identity fields instead of storage-relative paths as the primary contract.
- Deprecated legacy route docs for `GET /skills/search` and `GET /skills/{skill_id}/{version}`.

## Acceptance Criteria
- Discovery remains advisory and identical in behavior to the legacy search route.
- Resolution returns only direct authored `depends_on` and `extends` edges in manifest order.
- Resolution never expands transitive graphs or selects versions for constraints.
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
