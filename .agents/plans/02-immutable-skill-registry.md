# Plan 02 — Immutable Skill Registry

## Goal
Support publish and fetch of `skill@version` with strict immutability and integrity verification.

## Stack Alignment
- Runtime: Python 3.12+
- API surface: FastAPI endpoints with Pydantic v2 models
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL from milestone 1 (SQLite optional for isolated local tests only)

## Scope
- Define `SkillManifest` schema and validation.
- Persist versioned skill records in DB.
- Store artifact files in immutable path layout.
- Compute and store checksums.
- Expose publish/fetch/list endpoints.

## Architecture Impact
- Implements core asset registry responsibilities.
- Connects interface, persistence, and audit layers for skill lifecycle events.

## Deliverables
- Endpoint: `POST /v1/skills/{skill_id}/versions`.
- Endpoint: `GET /v1/skills/{skill_id}/versions/{version}`.
- Endpoint: `GET /v1/skills/{skill_id}/versions`.
- Tables for skills, versions, and checksums.
- Immutable artifact storage convention.
- Audit event emission for publish and read.
- Learning note on idempotency and immutable data modeling.

## Acceptance Criteria
- New versions can be published and retrieved reliably.
- Re-publish of existing `skill_id+version` is rejected deterministically.
- Checksum mismatch is detected and reported.
- Published artifacts are never modified in place.

## Test Plan
- Integration test: publish three versions and fetch each.
- Negative test: duplicate version publish fails.
- Negative test: corrupted artifact checksum fails integrity check.
- Regression test: retrieval output is stable across repeated requests.
