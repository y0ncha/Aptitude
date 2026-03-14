# app module

Application package for the aptitude-server service.

## Purpose

`app/` contains the runtime composition root, domain/core services, interface layer,
audit adapter, persistence adapters/models, and placeholders for future
metadata-oriented intelligence work.

## Module Map

- `app/main.py`: FastAPI application creation, startup/shutdown wiring, and dev server runner with shared logging config + startup banner.
- `app/audit/`: audit port adapters.
- `app/core/`: domain services for immutable catalog reads/writes, settings, ports,
  advisory search, and dependency providers.
- `app/interface/`: API interface boundary for publish, discovery, exact dependency reads, and exact metadata/content fetch.
- `app/persistence/`: database/artifact adapters and ORM models for immutable
  manifests, integrity metadata, dependency declaration projections, and search read models.
- `app/intelligence/`: search-ranking helpers and future metadata/graph intelligence.

## Update Rule

When adding or changing modules under `app/`, update the matching module README
in the same commit.
