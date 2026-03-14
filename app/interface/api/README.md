# app.interface.api module

HTTP API routers for the service.

## Purpose

Defines FastAPI routes, request validation, response schemas, and error
translation for the service's public HTTP contract. This package is the thin
adapter layer between FastAPI and core services.

## Key Files

- `health.py`: liveness/readiness endpoints (`/healthz`, `/readyz`).
- `discovery.py`: advisory metadata and description search routes under
  `/discovery`.
- `resolution.py`: direct immutable relationship read routes under
  `/resolution`.
- `fetch.py`: exact immutable metadata and markdown content routes under
  `/skills/{slug}/versions/...`.
- `skills.py`: publish, identity, version-list, and lifecycle-status routes.
- `errors.py`: stable JSON error envelope helpers and FastAPI exception
  handlers.
- `skill_api_support.py`: DTO-to-core translation helpers and shared response
  mappers for skill routes.
- `__init__.py`: package marker.

## Route Surface

- `GET /healthz`: process liveness probe.
- `GET /readyz`: dependency readiness probe with a `503` response when the
  service is not ready.
- `GET /discovery/skills/search`: discovery-only candidate search over indexed
  skill metadata.
- `POST /resolution/relationships:batch`: direct authored relationship lookup
  for exact immutable versions.
- `GET /skills/{slug}`: logical skill identity lookup.
- `GET /skills/{slug}/versions`: deterministic listing of immutable versions
  for one skill.
- `GET /skills/{slug}/versions/{version}`: exact immutable metadata fetch.
- `GET /skills/{slug}/versions/{version}/content`: raw markdown fetch with
  immutable cache headers.
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
`GET /discovery/skills/search` is candidate generation only and does not choose
final matches, solve dependencies, or plan execution.
`POST /resolution/relationships:batch` returns direct authored relationships
only; it does not expand transitive graphs or select versions for constraints.
The exact fetch routes intentionally separate metadata from markdown bytes so
the public API does not expose storage layout details and can attach cache
headers to content downloads cleanly.
