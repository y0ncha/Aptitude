# Plan 09 - Public API Simplification and Contract Freeze

## Goal
Freeze the final public registry contract around the hard-cut route split introduced in Plan 07, keep those endpoints simple through every later milestone, and prevent the roadmap from drifting back toward legacy read routes, compatibility facades, or single-item fetch helpers.

## Stack Alignment
- API framework: FastAPI with OpenAPI-first contracts
- Runtime: Python 3.12+
- Validation: Pydantic v2
- Data layer compatibility: SQLAlchemy 2.0 + Alembic

## Scope
- Freeze the public route families around:
  - publish
  - `POST /discovery`
  - `GET /resolution/{slug}/{version}`
  - `POST /fetch/metadata:batch`
  - `POST /fetch/content:batch`
  - lifecycle and governance operations
- Keep `resolution` as a first-class public surface rather than collapsing it into fetch.
- Keep fetch batch-only as the public contract; do not reintroduce public single-item metadata or content fetch routes.
- Treat the Plan 07 route set as the stable simple baseline for Plans 09-14; later work may refine payload fields, headers, and policy behavior, but it must not add new public read endpoint families.
- Remove roadmap commitments to:
  - public `/discovery/skills/search`
  - public `/skills/{slug}/versions/{version}`
  - public `/skills/{slug}/versions/{version}/content`
  - compatibility aliases or deprecation bridge routes for removed read APIs
- Keep the public contract registry-simple:
  - discovery returns candidate slugs
  - resolution returns direct dependency declarations
  - fetch returns immutable metadata and content for exact coordinates
- Do not introduce reranking, recursive solving, lock generation, or execution planning semantics into the server contract.

## Architecture Impact
- Sharpens the server/client boundary around stable registry primitives.
- Prevents internal service splits from being mistaken for temporary experiments that need compatibility support.
- Keeps the pre-release contract clean enough that the implementation can delete obsolete routes outright.

## Deliverables
- Final public route-set definition aligned to the hard-cut MVP read contract.
- Contract note clarifying that `resolution` is public and exact, but limited to first-degree dependency reads.
- Contract note clarifying that batch fetch is the only public immutable-read baseline.
- Endpoint simplicity rule stating that later milestones extend semantics inside the frozen route set instead of by adding sibling public routes.
- Removal plan for superseded route families and any compatibility language that survived older milestones.

## Acceptance Criteria
- The public roadmap describes `discovery`, `resolution`, and batch `fetch` as first-class public capabilities.
- No plan language treats `/resolution/*` as an internal-only experiment or a route family to be removed.
- No plan language keeps public single-item metadata or content fetch routes in the baseline contract.
- No compatibility facade, alias, or deprecation bridge is planned for removed read APIs.
- Later plans 10-14 preserve the same simple public read endpoint surface from Plan 07.
- The frozen contract remains execution-agnostic and excludes solving, reranking, lock generation, and runtime planning semantics.

## Test Plan
- OpenAPI review for the final publish, discovery, resolution, batch-fetch, and governance route set.
- Contract review confirming resolution remains public and exact-first-degree only.
- Regression review confirming removed single-item fetch routes are not reintroduced as convenience APIs.
- Documentation review confirming compatibility language has been removed from the final contract description.
