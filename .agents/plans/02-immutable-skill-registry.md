# Plan 02 — Immutable Skill Catalog

## Goal
Support publish and fetch of `skill@version` with strict immutability and integrity verification as the server source of truth.

## Stack Alignment
- Runtime: Python 3.12+
- API surface: FastAPI endpoints with Pydantic v2 models
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL from milestone 1 (SQLite optional for isolated local tests only)

## Scope
- Define `SkillManifest` schema and validation.
- Persist versioned skill records in DB.
- Store immutable artifact payloads in PostgreSQL.
- Compute and store checksums.
- Expose publish/fetch/list endpoints as immutable retrieval primitives for client-owned search, selection, and solve flows.
- Keep all writes API-mediated; no direct client writes to server persistence.
- Exclude runtime prompt orchestration, reranking, final tool selection, lock generation, and plugin execution (client scope).

## Architecture Impact
- Implements core artifact catalog responsibilities.
- Connects interface, persistence, and audit layers for skill lifecycle events.
- Establishes immutable artifact semantics required by client lock reproducibility.

## Deliverables
- Endpoint: `POST /skills/publish`.
- Endpoint: `GET /skills/{id}/{version}`.
- Endpoint: `GET /skills/{id}` for version listing.
- Tables for skills, versions, artifact payloads, checksums, and provenance basics.
- Immutable PostgreSQL storage convention for small whole-document skill artifacts.
- Audit event emission for publish and read.
- Learning note on idempotency and immutable data modeling.

## Acceptance Criteria
- New versions can be published and retrieved reliably.
- Re-publish of existing `skill_id+version` is rejected deterministically.
- Checksum mismatch is detected and reported.
- Published artifacts are never modified in place.
- Server write path is 100% API-enforced.
- Exact version reads remain stable and reusable by client lock/replay flows.

## Test Plan
- Integration test: publish three versions and fetch each.
- Negative test: duplicate version publish fails.
- Negative test: corrupted artifact checksum fails integrity check.
- Regression test: retrieval output is stable across repeated requests.
