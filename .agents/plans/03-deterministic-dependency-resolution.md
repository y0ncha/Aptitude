# Plan 03 — Deterministic Dependency Metadata Contracts

## Goal
Provide deterministic, client-consumable dependency metadata contracts as immutable inputs to client-side dependency solving.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL from milestone 1 (SQLite optional for isolated local tests only)

## Scope
- Add manifest structures for direct dependency declarations (`depends_on`, version constraints, optional markers).
- Persist dependency declarations exactly as published for each immutable version.
- Preserve authored dependency declaration ordering across repeated reads.
- Validate schema and constraint syntax at publish time.
- Expose dependency metadata within exact version/read contracts.
- Explicitly exclude transitive graph solving, canonical graph traversal as source of truth, lock generation, bundle assembly, and execution planning.

## Architecture Impact
- Clarifies server/client responsibility boundaries at contract level.
- Increases compatibility guarantees for client deterministic solving and lock replay.
- Prevents compute-heavy solver logic from leaking into repository service.

## Deliverables
- Contract updates for `GET /skills/{id}/{version}` to include dependency declarations and integrity envelope.
- Schema validation for dependency constraints and declaration shape.
- Stable serialization rules for dependency lists/maps without reinterpreting them as solved output.
- Learning note on manifest contracts vs solver outcomes.

## Acceptance Criteria
- Server returns dependency declarations exactly as authored for each immutable version.
- Invalid dependency specification payloads are rejected at publish time with stable error codes.
- Same version read request returns stable authored dependency ordering across repeated calls.
- No server endpoint returns canonical solved dependency closure.

## Test Plan
- Contract tests validating dependency envelope shape against client fixtures.
- Negative tests for malformed constraints and invalid dependency declarations.
- Snapshot tests verifying deterministic dependency serialization.
- Boundary test proving solver-owned behavior is absent from server API surface.
