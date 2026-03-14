# Plan 11 - Operability and Release Readiness

## Goal
Harden `aptitude-server` for repeatable deployment and reliable operation after the hard-cut read contract, PostgreSQL storage model, and governance behavior are finalized.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Quality gates: pytest, ruff, mypy, coverage thresholds

## Scope
- Add structured logs, correlation IDs, and audit trace stitching across:
  - publish
  - `POST /discovery`
  - `GET /resolution/{slug}/{version}`
  - `POST /fetch/metadata:batch`
  - `POST /fetch/content:batch`
  - lifecycle and governance paths
- Add metrics, dashboards, alerts, and SLO instrumentation for the final route set and PostgreSQL-only storage model.
- Add Docker packaging, startup/run instructions, and CI quality gates.
- Add runbooks for incidents on publish, discovery, resolution, metadata batch fetch, content batch fetch, lifecycle, and governance operations.
- Keep operability work internal to instrumentation, packaging, and runbooks; do not add new public registry-business endpoints, debug routes, or alternate discovery/resolution/fetch variants.
- Validate performance and reliability against the finalized API and storage shape from Plans 08-10 rather than against deleted routes or transitional storage semantics.

## Architecture Impact
- Adds deployment and observability infrastructure without reopening contract or storage decisions.
- Makes the final registry behavior measurable and supportable.
- Prevents hardening work from preserving removed routes indirectly through dashboards, alerts, or runbooks.

## Deliverables
- Structured logging conventions and correlation ID propagation.
- Metrics endpoint plus counters, timers, and error-rate tracking for final registry operations.
- Dashboards and alerts for discovery, resolution, metadata fetch, content fetch, publish, and governance flows.
- Dockerfile and local/prod run instructions.
- CI pipeline stages for unit, integration, lint, type-check, and coverage gates.
- Operational runbooks aligned to the hard-cut public contract and PostgreSQL-only runtime architecture.

## Acceptance Criteria
- End-to-end registry flows are observable through logs, metrics, and audit trace data.
- CI blocks merges on failing quality gates.
- Containerized startup and migration flow work against the final service shape.
- Discovery and immutable fetch SLO instrumentation align with the KPIs in `docs/prd.md`.
- Resolution and content batch fetch reliability instrumentation exist for the final contract.
- Operability work does not add public business-endpoint variants to support diagnostics or release operations.
- Runbooks and alerts assume PostgreSQL-only storage and never reference deleted route families or non-PostgreSQL artifact backends.

## Test Plan
- End-to-end integration test covering publish -> discovery -> resolution -> metadata batch fetch -> content batch fetch -> lifecycle update.
- CI smoke test in a containerized environment.
- Audit/log correlation test for a complete registry request path.
- Performance/load validation for discovery, resolution, and batch fetch on the finalized route set.
- Alerting and metrics sanity test for publish failures, exact-read failures, resolution failures, and discovery latency regression.
