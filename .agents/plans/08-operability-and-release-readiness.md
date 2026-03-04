# Plan 08 — Operability and Release Readiness

## Goal
Harden the system for reliable operation, auditing, and repeatable deployment.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Quality gates: pytest, ruff, mypy, coverage thresholds

## Scope
- Complete audit event matrix across publish, resolve, policy, and evaluation flows.
- Add structured logs and correlation IDs.
- Add metrics endpoint and baseline instrumentation.
- Add Docker packaging and CI quality gates.

## Architecture Impact
- Strengthens observability and audit layer.
- Adds deployment and quality infrastructure without changing domain invariants.

## Deliverables
- Structured logging conventions and correlation ID propagation.
- Metrics endpoint and core counters and timers.
- Dockerfile and local run instructions.
- CI pipeline stages for unit, integration, lint, type-check, and coverage threshold.
- Operational runbook for replaying resolution decisions.
- Learning note on reliability and observability tradeoffs.

## Acceptance Criteria
- End-to-end flow is observable with logs, metrics, and audit trace.
- CI blocks merges on failing quality gates.
- Containerized service starts and runs migrations on startup path.
- Resolution debugging is reproducible from `ResolutionReport` and audit records.

## Test Plan
- End-to-end integration test for publish -> resolve -> evaluate -> resolve.
- `pytest` suite in CI with coverage and deterministic integration checks.
- Smoke test in containerized environment.
- Audit completeness test against the event matrix.
