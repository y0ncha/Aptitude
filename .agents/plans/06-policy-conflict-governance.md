# Plan 06 — Policy, Conflict, and Governance

## Goal
Enforce centralized governance for conflicts, overlaps, trust tiers, and lifecycle states.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Policy config: pydantic-settings + environment overrides

## Scope
- Add relationship types `conflicts_with` and `overlaps_with`.
- Add policy profiles controlling resolution behavior.
- Implement trust-tier gating.
- Implement lifecycle transitions (`published`, `deprecated`, `archived`).

## Architecture Impact
- Strengthens policy engine in core domain.
- Adds governance controls at repository interface boundary.

## Deliverables
- Policy profile schema and loader.
- Conflict fail-fast behavior with reason codes.
- Overlap winner selection rule.
- Endpoint: `PATCH /v1/skills/{skill_id}/versions/{version}/status`.
- Trust-tier enforcement in the resolve path.
- Learning note on policy-as-data and constraint systems.

## Acceptance Criteria
- Conflicting compositions are blocked with clear rationale.
- Overlap resolution picks a deterministic winner by documented rule chain.
- Trust profile restrictions are enforced in resolution.
- Deprecation and archive states affect search and resolution consistently.

## Test Plan
- Conflict scenario tests.
- Overlap deterministic winner tests.
- Trust-tier allow and deny tests.
- Lifecycle transition and visibility tests.
