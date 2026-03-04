# Plan 04 — Repository API Contract V1

## Goal
Stabilize public API contracts and validation behavior to keep consumers insulated from internal refactors.

## Stack Alignment
- API framework: FastAPI (OpenAPI-first contract generation)
- Validation layer: Pydantic v2 request/response models
- Runtime: Python 3.12+
- Data layer compatibility: SQLAlchemy 2.0 + Alembic

## Scope
- Define OpenAPI v1 for implemented endpoints.
- Add DTO layer separate from core domain models.
- Standardize error envelope and error codes.
- Enforce request/response validation rules.

## Architecture Impact
- Hardens repository interface layer as stable contract boundary.
- Prevents leakage of internal models to clients.

## Deliverables
- OpenAPI spec covering all current v1 endpoints.
- Unified error response shape and status mapping.
- Validation middleware for payload and query constraints.
- Contract tests generated from spec examples.
- Learning note on anti-corruption layer and compatibility design.

## Acceptance Criteria
- API behavior matches OpenAPI examples.
- Invalid payloads fail with consistent error format.
- Existing endpoints keep backward-compatible response fields.

## Test Plan
- Contract tests for request and response examples.
- Negative tests for schema validation failures.
- Compatibility tests for existing endpoints after refactor.
- Snapshot tests for error envelope consistency.
