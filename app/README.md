# app module

Application package for the aptitude-server service.

## Purpose

`app/` contains the runtime composition root, domain/core services, interface layer,
audit adapter, persistence adapters/models, and placeholders for future intelligence work.

## Module Map

- `app/main.py`: FastAPI application creation, startup/shutdown wiring, and dev server runner with shared logging config + startup banner.
- `app/audit/`: audit port adapters.
- `app/core/`: domain services, settings, ports, and dependency providers.
- `app/interface/`: API interface boundary.
- `app/persistence/`: database/artifact adapters and ORM models.
- `app/intelligence/`: placeholder for metadata/graph intelligence.

## Update Rule

When adding or changing modules under `app/`, update the matching module README
in the same commit.
