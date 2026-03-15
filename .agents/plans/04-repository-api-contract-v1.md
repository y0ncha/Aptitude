# Plan 04 — Server API Contract V1

## Goal
Stabilize public repository API contracts and validation behavior to keep consumers insulated from internal refactors and aligned to the PyPI-like server/resolver boundary.

## Stack Alignment
- API framework: FastAPI
- Validation layer: Pydantic v2 request/response models
- Runtime: Python 3.12+
- Data layer compatibility: SQLAlchemy 2.0 + Alembic

## Scope
- Define the v1 public API contract for implemented repository endpoints.
- Add DTO layer separate from core domain models.
- Standardize error envelope and error codes.
- Enforce request/response validation rules.
- Lock server-facing contract required by `docs/scope.md`: publish, exact fetch, list versions, dependency metadata retrieval, and discovery read models for candidate generation.

## Architecture Impact
- Hardens server interface layer as stable contract boundary.
- Prevents leakage of internal models to clients.
- Enables resolver teams to treat server APIs as durable input contracts.

## Deliverables
- Public API documentation covering all current v1 endpoints.
- Contract coverage for:
  - `POST /skills/publish`
  - `GET /skills/{id}/{version}`
  - `GET /skills/{id}`
  - `GET /v1/skills/search` (if implemented in this phase, otherwise documented as pending v1.1)
- Unified error response shape and status mapping.
- Validation middleware for payload and query constraints.
- Search contract notes clarifying that `GET /v1/skills/search` is for indexed candidate retrieval and advisory ranking, not final resolver choice.
- Provider/consumer contract tests generated from spec examples.
- Learning note on anti-corruption layer and compatibility design.

## Acceptance Criteria
- API behavior matches documented examples.
- Invalid payloads fail with consistent error format.
- Existing endpoints keep backward-compatible response fields.
- No contract drift against required repository endpoints.
- Contract explicitly documents that prompt interpretation, reranking, final selection, and dependency solving are resolver-owned.

## Test Plan
- Contract tests for request and response examples.
- Negative tests for schema validation failures.
- Compatibility tests for existing endpoints after refactor.
- Snapshot tests for error envelope consistency.

## Historical Contract Note From Plans 07-09 (2026-03-15)
- This milestone predates the hard-cut read simplification and contract freeze.
- The final public contract is `POST /skill-versions`, `POST /discovery`, public `GET /resolution/{slug}/{version}`, exact `GET` metadata/content fetch under `/skills/{slug}/versions/{version}`, and `PATCH /skills/{slug}/versions/{version}/status`.
- List routes and legacy search paths described above are historical context only and should not be treated as the current public baseline.
