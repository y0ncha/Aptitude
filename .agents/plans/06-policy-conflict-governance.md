# Plan 06 — Policy, Conflict, and Governance

## Goal
Enforce centralized governance for trust tiers, lifecycle transitions, and conflict/overlap metadata at publish and discovery boundaries.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Policy config: pydantic-settings + environment overrides

## Scope
- Add relationship metadata types `conflicts_with` and `overlaps_with` as publish-time declarations.
- Add policy profiles controlling publish permissions and discovery visibility.
- Implement trust-tier gating and provenance requirements.
- Implement lifecycle transitions (`published`, `deprecated`, `archived`).
- Clean up superseded persistence structures created before the normalized PostgreSQL cutover, including legacy compatibility tables and mirror columns that no longer serve runtime reads.
- Keep policy authority in server for publish/read/search visibility; resolver may apply additional runtime policy interpretation after retrieval.
- Explicitly avoid server-side overlap winner selection and dependency conflict solving.

## Architecture Impact
- Strengthens policy engine in core domain.
- Adds governance controls at server interface boundary.
- Improves enterprise readiness without coupling repository to runtime solver logic.

## Deliverables
- Policy profile schema and loader.
- Publish-time policy validation with deterministic reason codes.
- Endpoint: `PATCH /v1/skills/{skill_id}/versions/{version}/status`.
- Trust-tier and lifecycle fields exposed on repository read models.
- Audit event coverage for policy and lifecycle changes.
- Cleanup migration plan for legacy persistence artifacts such as `skill_relationship_edges`, `skill_version_checksums`, and compatibility mirror columns retained during migration `0005`.
- Learning note on policy-as-data and governance boundaries.

## Acceptance Criteria
- Policy-rejected publishes are blocked with clear rationale.
- Deprecated and archived states affect server-side search candidate retrieval and exact-read visibility by documented policy.
- Trust profile restrictions are enforced on publish and privileged updates.
- Conflict/overlap metadata is persisted and returned deterministically.
- Legacy tables and columns replaced by normalized storage are either removed or explicitly documented as temporary compatibility state with an exit path.
- No server-side canonical dependency resolution behavior is introduced.

## Test Plan
- Policy allow/deny scenario tests.
- Lifecycle transition and visibility tests.
- Trust-tier validation tests.
- Migration coverage for dropping or retiring legacy compatibility tables/columns without breaking current publish, fetch, relationship, and discovery paths.
- Regression tests for deterministic policy reason codes and metadata projection.
