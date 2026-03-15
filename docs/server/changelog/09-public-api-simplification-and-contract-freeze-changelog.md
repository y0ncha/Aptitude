# Milestone 09 Changelog - Public API Simplification and Contract Freeze

This changelog documents implementation of [.agents/plans/09-public-api-simplification-and-contract-freeze.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/09-public-api-simplification-and-contract-freeze.md).

The milestone did not add or remove runtime routes. It froze the already-implemented public contract in the primary docs, aligned milestone history with that decision, and added regression tests so later plans cannot drift back toward removed public read families.

## Scope Delivered

- The primary contract docs now state the freeze rule explicitly: public resolution remains first-class, exact `GET` metadata/content fetch is the baseline, and later plans extend semantics inside the existing route set instead of adding compatibility aliases or sibling read families: [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md), [.agents/plans/roadmap.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/roadmap.md), [docs/scope.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/scope.md), [docs/prd.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/prd.md).
- Historical milestone plans now carry superseding notes so pre-freeze list/search and batch-fetch text is not mistaken for the current public contract: [.agents/plans/04-repository-api-contract-v1.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/04-repository-api-contract-v1.md), [.agents/plans/07-mvp-read-api-hard-cut.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/07-mvp-read-api-hard-cut.md), [.agents/plans/09-public-api-simplification-and-contract-freeze.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/09-public-api-simplification-and-contract-freeze.md).
- Historical changelog entries that still referenced removed route families now point readers back to the frozen contract instead of reading as live API guidance: [docs/changelog/05-metadata-search-ranking-changelog.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/changelog/05-metadata-search-ranking-changelog.md), [docs/changelog/07-mvp-read-api-hard-cut-changelog.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/changelog/07-mvp-read-api-hard-cut-changelog.md).
- Regression coverage now protects both the FastAPI surface and the contract docs from route-family drift, and the manual HTTP sanity fixture now exercises the frozen publish/discovery/resolution/exact-fetch/lifecycle flow: [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py), [tests/unit/test_public_contract_docs.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_public_contract_docs.py), [tests/resources/test-main.http](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/resources/test-main.http).

## Architecture Snapshot

```mermaid
flowchart LR
    Client["Client / Operator"] --> Discovery["POST /discovery"]
    Client --> Resolution["GET /resolution/{slug}/{version}"]
    Client --> FetchMeta["GET /skills/{slug}/versions/{version}"]
    Client --> FetchContent["GET /skills/{slug}/versions/{version}/content"]
    Client --> Publish["POST /skill-versions"]
    Client --> Lifecycle["PATCH /skills/{slug}/versions/{version}/status"]

    Discovery --> Services["Existing FastAPI routers + core services"]
    Resolution --> Services
    FetchMeta --> Services
    FetchContent --> Services
    Publish --> Services
    Lifecycle --> Services

    Services --> Docs["Roadmap + contract docs"]
    Docs --> Tests["Route + documentation regression tests"]
    Services --> PG["PostgreSQL"]
```

Why this shape:
- Plan 09 freezes the public boundary around the already-implemented route families instead of adding migration aliases or compatibility facades: [app/main.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/main.py), [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md), [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py).
- The existing service split remains intact: discovery returns candidate slugs, resolution returns direct `depends_on`, and exact fetch keeps metadata and markdown separate while docs/tests prevent roadmap drift from re-expanding that surface: [app/interface/api/discovery.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/discovery.py), [app/interface/api/resolution.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/resolution.py), [app/interface/api/fetch.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/fetch.py), [tests/unit/test_public_contract_docs.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_public_contract_docs.py).

## Runtime Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI Route
    participant S as Core Service
    participant R as Repository

    C->>A: GET /resolution/{slug}/{version}
    A->>S: get_direct_dependencies(slug, version)
    S->>R: get_direct_dependencies(slug, version)
    R-->>S: authored selectors for one coordinate
    S-->>A: dependency-only response model
    A-->>C: 200 + exact first-degree dependency payload
```

## Design Notes

- This milestone is a contract freeze, not a transport refactor. The implemented FastAPI route surface already matched the desired boundary, so the work focused on primary docs, milestone notes, and regression coverage rather than on runtime compatibility code: [app/main.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/main.py), [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md).
- Historical delivery notes remain valuable, but they no longer stand alone as contract guidance. Superseding notes were added where older plans or changelogs described list/search or batch-fetch shapes that should not reappear in later milestones: [docs/changelog/05-metadata-search-ranking-changelog.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/changelog/05-metadata-search-ranking-changelog.md), [docs/changelog/07-mvp-read-api-hard-cut-changelog.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/changelog/07-mvp-read-api-hard-cut-changelog.md).
- No database schema changes ship in this milestone. The schema and service boundary from Plan 08 remain the runtime baseline; Plan 09 hardens the public contract language around that implementation: [docs/changelog/08-canonical-postgres-storage-finalization-changelog.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/changelog/08-canonical-postgres-storage-finalization-changelog.md), [docs/schema.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/schema.md).

## Schema Reference

Source: [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md), [.agents/plans/roadmap.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/roadmap.md), [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py).

### `public_route_surface`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `publish` | `POST /skill-versions` | No | Frozen public route family | Creates one immutable `slug@version` and remains the only public publish entrypoint. |
| `discovery` | `POST /discovery` | No | Slug-only candidate response | Keeps discovery limited to candidate generation without reranking or solve semantics. |
| `resolution` | `GET /resolution/{slug}/{version}` | No | Exact coordinate read | Preserves public first-degree dependency inspection as a separate registry primitive. |
| `exact_metadata_fetch` | `GET /skills/{slug}/versions/{version}` | No | Exact immutable read | Returns the metadata envelope for one coordinate without introducing batch or identity/list variants. |
| `exact_content_fetch` | `GET /skills/{slug}/versions/{version}/content` | No | Exact immutable read | Returns raw markdown for one coordinate with immutable caching semantics. |
| `lifecycle_status` | `PATCH /skills/{slug}/versions/{version}/status` | No | Governing write route | Keeps lifecycle transitions inside the same frozen route family rather than in separate governance trees. |

## Verification Notes

- Route-boundary regressions now fail if legacy search, relationship-batch, list, or batch-fetch routes reappear in FastAPI or OpenAPI output: [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py).
- Documentation regressions now fail if the roadmap, current contract docs, or later milestone plans reintroduce removed public read routes or stop stating the freeze rule explicitly: [tests/unit/test_public_contract_docs.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_public_contract_docs.py).
- Local manual validation uses the frozen route set end-to-end through publish, discovery, resolution, exact metadata fetch, exact content fetch, and lifecycle update requests: [tests/resources/test-main.http](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/resources/test-main.http).
- Verification command used for this milestone:
  - `uv run pytest tests/unit/test_registry_api_boundary.py tests/unit/test_public_contract_docs.py`
