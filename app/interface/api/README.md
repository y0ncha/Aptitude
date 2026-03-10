# app.interface.api module

HTTP API routers for the service.

## Purpose

Defines FastAPI routes, request validation, response schemas, and API error
mapping for health and skill catalog operations.

## Key Files

- `health.py`: liveness/readiness endpoints (`/healthz`, `/readyz`).
- `skills.py`: publish/fetch/list immutable skill version endpoints, including
  authored dependency declarations with exact versions or validated version constraints.
- `__init__.py`: package marker.

## Notes

Business decisions should stay in core services; routers should focus on API
contract validation, dependency declaration syntax checks, and error translation.
`GET /skills/search` is intentionally not implemented yet in this module; the
future search API remains candidate generation only and does not move resolver
decision logic into the server.
