# Milestone 01 Summary - Foundation Service Skeleton

Source plan: `.agents/plans/01-foundation-service-skeleton.md`

## Purpose

Milestone 01 creates a stable service foundation with explicit package boundaries, bootstrapping, and operational checks.
It intentionally focuses on infrastructure and architecture safety rails, not business/domain features.

## Delivered Scope

- Package structure and boundary baseline:
  - `app/interface`: transport layer (HTTP routers, response contracts)
  - `app/core`: bootstrap and shared application wiring
  - `app/intelligence`: reserved for ranking/graph logic in later milestones
  - `app/persistence`: database engine/session and readiness checks
  - `app/audit`: auditable persistence models
- Startup and composition:
  - `app/main.py`
  - `app/core/bootstrap.py`
- Environment configuration and logging:
  - `app/core/config.py`
  - `app/core/logging.py`
- Persistence wiring and health contract:
  - `DatabaseHealthChecker` protocol
  - `SQLAlchemyDatabaseHealthChecker`
- Migration baseline:
  - `alembic.ini`
  - `migrations/env.py`
  - `migrations/versions/0001_foundation_baseline.py` (creates `audit_events`)
- System endpoints:
  - `GET /healthz` (liveness)
  - `GET /readyz` (readiness)
- Developer workflow support:
  - `docker-compose.yml` (PostgreSQL)
  - `Makefile` commands for run/test/lint/typecheck/migrations
- Architecture rationale note:
  - `docs/notes/01-package-boundaries.md`

## Boundary Rules (Why They Matter)

Dependency direction is inward toward stable contracts:

1. `interface` may depend on contracts from `core` and `persistence`.
2. `core` owns wiring and composition, but avoids depending on interface internals.
3. `persistence` does not depend on `interface`.
4. `audit` depends on persistence base abstractions, not interface concerns.

This prevents API transport choices from leaking into database code and keeps readiness behavior testable via stubs.
Using `DatabaseHealthChecker` in the interface layer is the concrete example of this pattern.

## Validation and Quality Gates

- Unit tests:
  - `tests/unit/test_config.py`
- Integration tests:
  - `tests/integration/test_system_endpoints.py`
  - `tests/integration/test_migrations.py`
- Architecture enforcement:
  - `tests/architecture/test_layer_boundaries.py`
- Static checks:
  - `ruff`
  - `mypy`

Note: migration integration tests are expected to skip when `DATABASE_URL`/`TEST_DATABASE_URL` is not configured.

## How To Work With This Milestone Today (uv-first)

- Sync dependencies: `uv sync --group dev`
- Run service: `uv run uvicorn --factory app.main:create_app --reload --host 0.0.0.0 --port 8000`
- Run tests: `uv run pytest -q`
- Run lint/type checks:
  - `uv run ruff check .`
  - `uv run mypy app tests`

IDE note: configure the project interpreter to `.venv/bin/python` so import resolution matches `uv run`.

## Deferred Work (Intentional)

- Skill registry domain entities and flows
- Resolver/intelligence business logic
- Rich API feature surface beyond system endpoints

These are planned for the next milestones and should build on the boundaries introduced here.
