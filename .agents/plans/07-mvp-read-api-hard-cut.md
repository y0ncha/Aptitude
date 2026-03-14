# Plan 07 - MVP Read API Hard Cut

## Goal
Reset the MVP read surface to a minimal breaking-change contract that is easy to implement, document, and operate. This milestone is a hard cut: the public read API is reduced to four endpoints, and superseded routes are deleted rather than preserved behind compatibility layers.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL as the only runtime store

## Scope
- Freeze the public read contract to these endpoints only:
  - `POST /discovery`
  - `GET /resolution/{slug}/{version}`
  - `POST /fetch/metadata:batch`
  - `POST /fetch/content:batch`
- Define `POST /discovery` as a body-based candidate lookup:
  - request body: `name` required, `description` optional, `tags` optional
  - response body: ordered candidate list containing slugs only
- Define `GET /resolution/{slug}/{version}` as exact first-degree dependency retrieval:
  - exact `slug` and `version` are required
  - response returns direct dependency declarations exactly as authored
  - no recursive expansion, no version solving, no final candidate selection
- Define `POST /fetch/metadata:batch` as immutable metadata retrieval for an ordered list of `{ slug, version }` coordinates.
- Define `POST /fetch/content:batch` as immutable content retrieval for the same ordered coordinate list, returned as `multipart/mixed` with one `text/markdown` part per requested item.
- Explicitly remove the old public read baseline:
  - `GET /discovery/skills/search`
  - `POST /resolution/relationships:batch`
  - `GET /skills/{slug}/versions/{version}`
  - `GET /skills/{slug}/versions/{version}/content`
  - any public single-item fetch convenience route
- Do not use `HEAD` for metadata batch retrieval; batch metadata responses are body-carrying requests and stay on `POST`.
- Do not preserve compatibility aliases, DTO facades, mirror responses, or migration-only route shims.

## Architecture Impact
- Makes the server boundary explicit: discovery finds candidate identities, resolution returns direct dependencies, and fetch returns immutable version data.
- Removes internal route experiments from the public contract and keeps the MVP path short.
- Allows implementation to delete superseded code and schemas instead of carrying pre-release compatibility debt.

## Deliverables
- Final contract definition for the four public read endpoints, including request and response shapes.
- Shared coordinate batch request shape: `{ slug, version }`.
- Discovery response shape: ordered slug candidates only.
- Resolution response shape: direct dependency selectors exactly as stored.
- Metadata batch response shape with ordered results, `found | not_found` status, and full metadata envelope for found items.
- Content batch response shape using `multipart/mixed` with per-part coordinate and status headers.
- Removal note documenting that the superseded read routes are outside the MVP baseline and should be deleted, not wrapped.

## Acceptance Criteria
- The public MVP read contract contains only the four endpoints defined above.
- Discovery does not return versions, ranking rationale, or solved dependency information.
- Resolution returns first-degree dependency declarations only and never recurses.
- Metadata batch fetch preserves request order and returns `found | not_found` per requested coordinate.
- Content batch fetch returns `multipart/mixed` with one part per requested coordinate in request order.
- No part of the plan keeps `HEAD`, single-item fetch, or legacy route aliases in the public read baseline.

## Test Plan
- Contract review covering route names, verbs, request bodies, and response bodies for all four endpoints.
- Negative review confirming the removed read routes do not appear in the MVP baseline.
- Shape review confirming discovery is slug-only, resolution is first-degree only, and fetch is batch-only.
- Documentation review confirming the milestone requires deletion of superseded code paths rather than compatibility wrappers.
