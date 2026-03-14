# app.interface module

Server interface boundary.

## Purpose

Hosts externally exposed API boundaries and request/response contracts.

## Key Modules

- `api/`: HTTP routers for health and skill catalog endpoints.
- `dto/`: Service-specific DTO modules for publish, discovery, resolution, status, and exact metadata fetch contracts.
- `__init__.py`: package marker.

## Boundary Rule

Interface code depends on core services/contracts and must not bypass core
behavior by calling persistence adapters directly.
