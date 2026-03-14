# app.interface.api module

HTTP API routers for the service.

## Purpose

Defines FastAPI routes, request validation, response schemas, and error
translation for the service's public HTTP contract. This package is the thin
adapter layer between FastAPI and core services.

## Key Files

- `health.py`: liveness/readiness endpoints (`/healthz`, `/readyz`).
- `discovery.py`: body-based candidate lookup route at `/discovery`.
- `resolution.py`: exact first-degree dependency read route at
  `/resolution/{slug}/{version}`.
- `fetch.py`: immutable metadata and markdown batch fetch routes under
  `/fetch/...`.
- `skills.py`: publish and lifecycle-status routes.
- `errors.py`: stable JSON error envelope helpers and FastAPI exception
  handlers.
- `skill_api_support.py`: DTO-to-core translation helpers and shared response
  mappers for skill routes.
- `__init__.py`: package marker.

## Route Surface

- `GET /healthz`: process liveness probe.
- `GET /readyz`: dependency readiness probe with a `503` response when the
  service is not ready.
- `POST /discovery`: discovery-only candidate lookup returning ordered slug
  candidates.
- `GET /resolution/{slug}/{version}`: direct authored `depends_on`
  declarations for one immutable version.
- `POST /fetch/metadata:batch`: ordered immutable metadata fetch for exact
  coordinates.
- `POST /fetch/content:batch`: ordered immutable markdown fetch as
  `multipart/mixed`.
- `POST /skill-versions`: immutable skill version publication.
- `PATCH /skills/{slug}/versions/{version}/status`: lifecycle-status transition
  for one immutable version.

## Notes

Routers should stay thin. They validate HTTP input, call a core service, and
translate results into public DTOs without embedding business policy.
`errors.py` owns the public error envelope so request validation failures,
policy violations, and explicit API errors share one JSON shape.
`skill_api_support.py` centralizes mapping code so route handlers do not
duplicate DTO conversion or publish-command assembly.
`POST /discovery` is candidate generation only and does not choose final
matches, solve dependencies, or plan execution.
`GET /resolution/{slug}/{version}` returns direct authored dependencies only;
it does not expand transitive graphs or select versions for constraints.
The batch fetch routes intentionally separate immutable metadata from markdown
bytes so the public API stays batch-oriented and exact-read policy remains
consistent across both read modes.
