# app.interface.api module

HTTP API routers for the service.

## Purpose

Defines FastAPI routes, request validation, response schemas, and API error
mapping for health and skill catalog operations.

## Key Files

- `health.py`: liveness/readiness endpoints (`/healthz`, `/readyz`).
- `discovery.py`: advisory metadata + description search routes under `/discovery`.
- `resolution.py`: direct relationship read routes under `/resolution`.
- `fetch.py`: exact metadata fetch and artifact streaming routes under `/fetch`.
- `skills.py`: publish/list routes plus deprecated compatibility wrappers for legacy search/fetch paths.
- `__init__.py`: package marker.

## Notes

Business decisions should stay in core services; routers should focus on API
contract validation, dependency declaration syntax checks, and error translation.
`GET /discovery/skills/search` remains candidate generation only and does not
move resolver decision logic into the server.
`POST /resolution/relationships:batch` returns direct authored relationships
only; it is not a solver.
`/fetch` routes separate metadata reads from artifact bytes so the public API
does not depend on filesystem layout details.
