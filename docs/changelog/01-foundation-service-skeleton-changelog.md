# Milestone 01 Changelog - Foundation Service Skeleton

This document reviews the implementation of [.agents/plans/01-foundation-service-skeleton.md](/Users/yonatan/Dev/aptitude-server/.agents/plans/01-foundation-service-skeleton.md) with a system-design focus.

The emphasis is on **why** each architectural decision was made, how the parts fit together, and what to keep in mind for upcoming milestones.

## 1) Why this milestone exists

Milestone 01 establishes infrastructure, boundaries, and operational safety before domain behavior.  
The goal is to avoid early coupling that would make later milestones expensive to change.

Core drivers:
- A stable service skeleton that is runnable immediately.
- Explicit dependency direction between layers.
- Reproducible schema evolution from day one.
- Operational clarity through liveness/readiness semantics.
- A testing baseline that supports safe iteration.

## 2) Current system state (architecture)

```mermaid
flowchart TB
    Client["Client / Probe / TestClient"] --> API["Interface Layer\napp/interface/api/health.py"]
    API --> Core["Core Layer\nsettings + logging + DI + readiness service"]
    Core --> Port["Core Port\nDatabaseReadinessPort"]
    Port --> Persist["Persistence Adapter\nSQLAlchemyDatabaseReadinessProbe"]

    App["App Factory + Lifespan\napp/main.py"] --> Core
    App --> Persist

    Persist --> DB["PostgreSQL\n(or SQLite for isolated checks)"]
    Alembic["Alembic Migrations"] --> DB

    Audit["Audit Layer (Planned)\napp/audit"]:::placeholder
    Intel["Intelligence Layer (Planned)\napp/intelligence"]:::placeholder

    classDef placeholder fill:#f6f6f6,stroke:#999,stroke-dasharray: 5 5;
```

Why this shape:
- Interface remains thin, so HTTP concerns do not absorb domain logic ([health router](/Users/yonatan/Dev/aptitude-server/app/interface/api/health.py)).
- Core owns process-level cross-cutting concerns (config, logging, DI), making startup and runtime behavior consistent ([settings](/Users/yonatan/Dev/aptitude-server/app/core/settings.py), [dependencies](/Users/yonatan/Dev/aptitude-server/app/core/dependencies.py), [readiness service](/Users/yonatan/Dev/aptitude-server/app/core/readiness.py)).
- Persistence is centralized for connection lifecycle and infrastructure adapters ([DB lifecycle](/Users/yonatan/Dev/aptitude-server/app/persistence/db.py)).
- Composition root wiring in `app/main.py` keeps dependency direction strict while still allowing runtime assembly ([app/main.py](/Users/yonatan/Dev/aptitude-server/app/main.py)).
- Placeholders for `audit` and `intelligence` make future boundaries explicit now, reducing refactor cost later ([audit package](/Users/yonatan/Dev/aptitude-server/app/audit/__init__.py), [intelligence package](/Users/yonatan/Dev/aptitude-server/app/intelligence/__init__.py)).

## 3) Request lifecycle and operational semantics

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI App
    participant R as Health Router
    participant S as Core ReadinessService
    participant AD as Persistence Probe
    participant P as PostgreSQL

    Note over A: Startup (lifespan): load settings, configure logging, init engine

    C->>A: GET /healthz
    A->>R: route to get_healthz()
    R-->>C: 200 {status: ok, service, environment}

    C->>A: GET /readyz
    A->>R: route to get_readyz()
    R->>S: get_status()
    S->>AD: ping()
    AD->>P: SELECT 1
    alt DB reachable
      P-->>AD: success
      R-->>C: 200 {status: ready}
    else DB unreachable
      P-->>AD: error
      R-->>C: 503 {status: not_ready, detail}
    end
```

Why two endpoints:
- `/healthz` answers “is process alive?” and should be cheap/stable ([endpoint](/Users/yonatan/Dev/aptitude-server/app/interface/api/health.py)).
- `/readyz` answers “can this instance serve real traffic?” and includes dependency checks ([endpoint](/Users/yonatan/Dev/aptitude-server/app/interface/api/health.py), [core readiness](/Users/yonatan/Dev/aptitude-server/app/core/readiness.py), [DB probe](/Users/yonatan/Dev/aptitude-server/app/persistence/db.py)).
- This separation supports safer deployments, restarts, and traffic routing ([integration coverage](/Users/yonatan/Dev/aptitude-server/tests/integration/test_health_endpoints.py)).

## 4) Why each major decision was taken

### 4.1 App factory + lifespan
- `create_app()` enables deterministic app construction in tests and runtime ([app factory](/Users/yonatan/Dev/aptitude-server/app/main.py), [health integration tests](/Users/yonatan/Dev/aptitude-server/tests/integration/test_health_endpoints.py)).
- Lifespan startup/shutdown centralizes resource management (engine init/dispose), reducing hidden side effects ([lifespan wiring](/Users/yonatan/Dev/aptitude-server/app/main.py), [engine lifecycle](/Users/yonatan/Dev/aptitude-server/app/persistence/db.py)).

### 4.2 Typed settings (`pydantic-settings`)
- Required `DATABASE_URL` enforces fail-fast startup for critical infrastructure ([settings model](/Users/yonatan/Dev/aptitude-server/app/core/settings.py), [unit test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_settings.py)).
- Defaults (`APP_ENV`, `LOG_LEVEL`, `APP_NAME`) keep local setup simple but explicit ([settings model](/Users/yonatan/Dev/aptitude-server/app/core/settings.py)).
- Typed config reduces “stringly typed” runtime errors and improves testability ([settings model](/Users/yonatan/Dev/aptitude-server/app/core/settings.py), [unit test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_settings.py)).

### 4.3 SQLAlchemy 2.0 + Alembic
- Chosen to align with roadmap and milestone contract.
- Engine/session lifecycle in one module prevents inconsistent DB handling across handlers ([DB module](/Users/yonatan/Dev/aptitude-server/app/persistence/db.py)).
- Versioned migrations make schema state reproducible and auditable ([alembic env](/Users/yonatan/Dev/aptitude-server/alembic/env.py), [baseline migration](/Users/yonatan/Dev/aptitude-server/alembic/versions/0001_baseline_audit_event.py), [migration integration test](/Users/yonatan/Dev/aptitude-server/tests/integration/test_migrations.py)).

### 4.4 Layered readiness refactor (strict boundaries)
- Introduced core port `DatabaseReadinessPort` and core `ReadinessService` ([port](/Users/yonatan/Dev/aptitude-server/app/core/ports.py), [service](/Users/yonatan/Dev/aptitude-server/app/core/readiness.py)).
- Replaced direct route-level persistence access with interface -> core dependency ([health API deps](/Users/yonatan/Dev/aptitude-server/app/interface/api/health.py), [dependency providers](/Users/yonatan/Dev/aptitude-server/app/core/dependencies.py)).
- Implemented persistence adapter `SQLAlchemyDatabaseReadinessProbe` and wired it only in `app/main.py` ([probe adapter](/Users/yonatan/Dev/aptitude-server/app/persistence/db.py), [composition root](/Users/yonatan/Dev/aptitude-server/app/main.py)).
- Added architecture tests to fail on `interface -> persistence` and `core -> persistence` imports ([layering test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_layering_imports.py)).

### 4.5 Baseline `audit_events` table
- Minimal schema to validate migration mechanics without introducing domain complexity ([migration](/Users/yonatan/Dev/aptitude-server/alembic/versions/0001_baseline_audit_event.py), [ORM model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/audit_event.py)).
- Gives a concrete target for upgrade/downgrade testing ([migration integration test](/Users/yonatan/Dev/aptitude-server/tests/integration/test_migrations.py)).

Schema reference for [0001_baseline_audit_event.py](/Users/yonatan/Dev/aptitude-server/alembic/versions/0001_baseline_audit_event.py):

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `id` | `Integer` | No | Primary key, autoincrement | Stable identifier for each audit row. |
| `event_type` | `String(100)` | No | Required | Event category name for auditable actions. |
| `payload` | `JSON` | Yes | Optional | Structured event metadata payload. |
| `created_at` | `DateTime(timezone=True)` | No | `CURRENT_TIMESTAMP` | Event creation timestamp. |

### 4.6 Test split (unit + integration)
- Unit tests cover strict configuration behavior quickly ([settings unit tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_settings.py), [readiness unit tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_readiness_service.py)).
- Integration tests validate behavior at service and migration boundaries ([health integration tests](/Users/yonatan/Dev/aptitude-server/tests/integration/test_health_endpoints.py), [migration integration tests](/Users/yonatan/Dev/aptitude-server/tests/integration/test_migrations.py)).
- DB-dependent tests skip cleanly when Postgres is unavailable, preserving local dev flow ([integration fixture](/Users/yonatan/Dev/aptitude-server/tests/conftest.py)).

### 4.7 Tooling and quality gates
- `Makefile` provides one-command workflows and keeps execution habits consistent ([Makefile](/Users/yonatan/Dev/aptitude-server/Makefile)).
- `ruff` + `mypy` enforce readability and type contracts before future complexity arrives ([tool config](/Users/yonatan/Dev/aptitude-server/pyproject.toml)).
- `UV_CACHE_DIR=.uv-cache` avoids environment-specific cache permission issues ([Makefile](/Users/yonatan/Dev/aptitude-server/Makefile)).

## 5) Layer boundaries (future-safe rules)

```mermaid
flowchart LR
    Interface["Interface"] --> Core["Core"]
    Core --> Port["Core Ports / Protocols"]
    Persistence["Persistence Adapter"] --> Port

    Persistence -.X.-> Interface
    Core -.X.-> Persistence
    Audit["Audit (Planned)"]:::placeholder -. independent .- Core
    Intelligence["Intelligence (Planned)"]:::placeholder -. independent .- Core

    classDef placeholder fill:#f6f6f6,stroke:#999,stroke-dasharray: 5 5;
```

Rules to preserve:
- `interface` depends only on core-facing modules ([interface package](/Users/yonatan/Dev/aptitude-server/app/interface/__init__.py), [layering test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_layering_imports.py)).
- `core` depends on persistence only through core-defined ports/interfaces ([core ports](/Users/yonatan/Dev/aptitude-server/app/core/ports.py), [layering test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_layering_imports.py)).
- `app/main.py` is the composition root allowed to wire core and persistence ([composition root](/Users/yonatan/Dev/aptitude-server/app/main.py)).
- `persistence` must never import API/router code ([persistence package](/Users/yonatan/Dev/aptitude-server/app/persistence/__init__.py), [layering test](/Users/yonatan/Dev/aptitude-server/tests/unit/test_layering_imports.py)).
- Keep future policy/resolution logic out of route handlers; place it in dedicated core modules.

## 6) Tradeoffs and known limitations

- No domain resolver/registry logic yet by design (scope control).
- Integration tests currently depend on an external running Postgres instance.
- Readiness probe currently checks connectivity only (`SELECT 1`) via a persistence adapter, not migration drift or deeper invariants.
- Logging uses stdlib baseline; structured correlation fields can be added in later operability milestone.

These are acceptable for Milestone 01 because the objective is a stable skeleton, not full behavior.

## 7) Notes for future milestones

1. Milestone 02 (immutable skill registry):
- Introduce core service modules for registry behavior, not in route files.
- Add persistence repositories instead of direct session-level access from handlers.

2. Milestone 03 (deterministic resolution):
- Add deterministic ordering rules in core layer with explicit tie-breakers.
- Record resolution reasoning in audit structures early.

3. API contract growth:
- Keep response DTOs in interface layer and avoid leaking ORM models.
- Add explicit error models as endpoints expand.

4. Readiness hardening:
- Extend `/readyz` to include migration-head check once release process exists.
- Consider separate degraded-state semantics if partial dependencies are introduced.

## 8) Learning takeaways (system design with Python/FastAPI)

- Start with architecture boundaries before feature logic to protect long-term velocity.
- Use typed configuration and explicit startup wiring to turn operational failures into early, understandable failures.
- Separate liveness from readiness to match real deployment behavior.
- Keep migration discipline from the first table; it prevents hidden state drift.
- Treat tests as architectural checks: unit tests protect contracts, integration tests protect boundaries.
