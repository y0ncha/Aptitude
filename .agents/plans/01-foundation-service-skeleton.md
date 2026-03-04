# Plan 01 — Foundation Service Skeleton

## Goal
Establish a runnable Python service (FastAPI) with clear layer boundaries, configuration, logging, and migration bootstrap.

## Stack Alignment
- Runtime: Python 3.12+
- API: FastAPI + Pydantic v2
- Data access and migrations: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL from milestone 1 (SQLite optional for isolated local tests only)

## Scope
- Create package layout for interface, core, intelligence, persistence, and audit layers.
- Add config loading and startup wiring.
- Add PostgreSQL connection and migration execution.
- Add health and readiness endpoints.

## Architecture Impact
- Introduces the repository interface boundary and dependency direction.
- Sets persistence and observability foundations without domain behavior.

## Deliverables
- Python service skeleton (`app/main.py` + `app/...` layout).
- Migration framework and initial schema baseline.
- Endpoint: `GET /healthz`.
- Endpoint: `GET /readyz`.
- Make targets for run, test, lint, and migrations.
- Learning note on package boundaries and dependency inversion.

## Acceptance Criteria
- Service starts locally with config from environment.
- PostgreSQL migrations run successfully on a clean setup.
- Health endpoints return expected status.
- `pytest` passes.

## Test Plan
- Unit tests for config validation.
- Integration test that starts the service and probes health endpoints.
- Integration test that runs migration up/down on a fresh PostgreSQL instance.
- Static checks (`ruff`, `mypy`) enforce boundaries and quality gates.
