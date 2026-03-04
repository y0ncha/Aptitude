# Milestone 01 Learning Note: Package Boundaries

This milestone establishes five explicit layers:

- `app/interface`: API routers and transport schemas only.
- `app/core`: bootstrap and configuration glue.
- `app/intelligence`: reserved for ranking and relationship logic in later milestones.
- `app/persistence`: database engine/session + readiness checks.
- `app/audit`: auditable record models.

## Dependency Direction

The dependency rule is inward toward stable contracts:

1. `interface` can depend on contracts in `core` and `persistence`.
2. `core` orchestrates wiring but does not depend on `interface` internals.
3. `persistence` never depends on `interface`.
4. `audit` depends on persistence base model only.

In this milestone, `DatabaseHealthChecker` is a persistence-layer contract consumed by the interface router. This keeps readiness API behavior independent from concrete DB implementation details and makes endpoint tests deterministic with stubs.

## Why This Matters for Later Milestones

- Milestone 02 can add skill registry persistence and API handlers without changing system endpoint contracts.
- Milestone 03 can introduce resolver services under `core`/`intelligence` while preserving interface shape.
- Milestones 04+ can enforce DTO anti-corruption boundaries with minimal refactoring.
