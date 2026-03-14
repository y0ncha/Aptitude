# aptitude-server

![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-managed-6E56CF?style=for-the-badge&logo=uv&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/sqlalchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=111111)
![Docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
[![DeepWiki](https://img.shields.io/badge/Ask-DeepWiki-0A66C2?style=for-the-badge&logo=data%3Aimage%2Fpng%3Bbase64%2CiVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAsVBMVEVHcEwmWMYZy38Akt0gwZoSaFIbYssUmr4gwJkBlN4WbNE4acofwZkBj9k4aMkBk94WgM0bsIM4aMkewJc2ZMM3Z8cbvIwYpHsewJYAftgBkt0fvpgBkt0cv44cv5wzYckAjtsCk90pasUboXsgwJkfwpYfwJg4aMoct44yXswAkd0BkN84Z8cBktwduZIjcO85lM4hwZo5acoBleA6a88iyaABmOQ8b9QhxZ0CnOoizaOW4DOvAAAAMHRSTlMAKCfW%2FAgWA%2F7%2FDfvMc9j7MU%2Frj3XBcRW%2FJMbe7kUxjI%2FlUzzz6tPQkJ%2BjVmW1oeulmmslAAAByUlEQVQ4y32Tia6jIBSGUVFcqliXtlq73rm3d50ERNC%2B%2F4PNQetoptMeE0PgC%2F9%2FFhCaBSH9Hz2J%2BONgPDl2DolSUWY%2FPL8oEQRCfPxHpFc3Ah5wHoiI6I05NXgjAOgQF3Jn1Dlo4XMPDDes09UE2d%2BREvl3lijBg4CrHNmrbcM2u9u5nwsRcAFfFHFY5sZ607Yua3GqpQiKE6G9cZHZThblZ4T2mLnMxde3ATASMUj72o0Pbs1fADDcLHqAjEDugJ3lC%2BztMGYTADcoLaFyH%2B02DP9%2BWS4ahrXE4laALFKcq8vZfscNY8312mxfr27bLJZjnsYhSDIHmUxLu9h9N%2Fep%2B7pazwoZQw%2B1Nwi33epu7c2p8RooeqCdAHMGoOJIq3CUwIMEniRIaHVe3ZVnO2Vgsh1MstEkQUXVUc%2BjXfk3zbemxS6%2BpQmlPtUeALJ8VKj4JHvAelBqFFdSS3h1SPzQKr%2F%2BaRa0%2B0cCIWtJLauG5U%2FfbgyG01uiNqQhyzA8ddKj1OvK28AsZyN3DKE4X6AEWrU1jJx9N7RFpdPxpHU%2FtMOQG9SjfTp3Yz8KgRVKpfx88Dqhpseq606h%2F%2Bzxfh6LJ8eEDKWbxx9XEDwqzP1SVgAAAABJRU5ErkJggg%3D%3D)](https://deepwiki.com/y0ncha/aptitude-server)
![Last Commit](https://img.shields.io/github/last-commit/y0ncha/aptitude-server?style=for-the-badge)

`aptitude-server` is the registry service in the Aptitude ecosystem. It stores immutable
skill artifacts, structured metadata, direct relationship selectors, lifecycle state, and
audit data in PostgreSQL so clients can publish exact versions, discover candidate slugs,
read direct dependencies, and fetch immutable metadata and content without crawling the
full catalog.

## Service Boundary

This repository follows the boundary defined in [`docs/scope.md`](docs/scope.md):

- Server owns data-local work: publish, discovery, resolution, fetch, governance, and audit.
- Client owns decision-local work: prompt interpretation, reranking, final selection,
  dependency solving, lock generation, and execution planning.

In practice:

- `aptitude-server` behaves like a package registry / catalog service.
- `aptitude-client` behaves like the package manager / runtime planner.

## Current Implementation

The current codebase is registry-first and aligned with the PRD's core responsibilities:

- FastAPI service with Swagger UI docs and PostgreSQL-backed persistence
- Immutable publication of normalized `slug@version` records
- Body-based discovery that returns ordered candidate slugs
- Exact dependency reads for authored `depends_on` selectors only
- Ordered immutable metadata batch fetch and `multipart/mixed` content batch fetch
- Lifecycle governance with `published`, `deprecated`, and `archived` states
- Scoped Bearer-token authorization for `read`, `publish`, and `admin`
- Optional publish-time provenance metadata (`repo_url`, `commit_sha`, `tree_path`)
- Audit recording for registry operations

The server does not perform client/runtime concerns from the PRD:

- prompt interpretation
- context-aware reranking
- final candidate choice
- dependency solving or closure expansion
- lock generation
- execution planning

## Storage Strategy

The current implementation follows the recommendation in
[`docs/storage-strategy.md`](docs/storage-strategy.md):

- PostgreSQL is the only persistence system.
- Discovery metadata and exact-fetch content are separated at the schema and query-path level.
- Immutable markdown content is stored once per digest and reused across versions.
- Version rows bind immutably to digest-addressed content.

This matches the current workload assumptions from the storage strategy doc: skill bodies are small
(`4-6 KB` on average), fetched as whole documents, and discovery plus exact fetch should stay
independently optimizable without introducing filesystem or object storage complexity.

## API Surface Today

The PRD describes the service in capability terms such as "publish" and "search". The current
HTTP surface implements those capabilities with the following routes:

- `GET /healthz`
- `GET /readyz`
- `POST /discovery`
- `GET /resolution/{slug}/{version}`
- `POST /fetch/metadata:batch`
- `POST /fetch/content:batch`
- `POST /skill-versions`
- `PATCH /skills/{slug}/versions/{version}/status`

Notes:

- All non-health endpoints require `Authorization: Bearer <token>`.
- `POST /skill-versions` is the current publish route for immutable version creation.
- `POST /discovery` is a discovery-only candidate-generation endpoint that returns slug
  candidates only.
- `GET /resolution/{slug}/{version}` returns only direct authored `depends_on`
  declarations, not solved graphs or other relationship families.
- `POST /fetch/content:batch` returns `multipart/mixed` with digest-backed `ETag`
  and `Cache-Control: public, immutable` headers on found parts.

When running locally, interactive docs are available at `http://127.0.0.1:8000/docs`.
The human-readable API reference is [`docs/api-contract.md`](docs/api-contract.md).

## Governance and Auth

The default policy model is implemented in code and consistent with the PRD's governance goals:

- Trust tiers: `untrusted`, `internal`, `verified`
- Lifecycle states: `published`, `deprecated`, `archived`
- Scopes: `read`, `publish`, `admin`

Default publish rules:

- `untrusted`: requires `publish`
- `internal`: requires `publish` and provenance metadata
- `verified`: requires `admin` and provenance metadata

Default visibility rules:

- Discovery defaults to `published`
- Read callers may search `published` and `deprecated`
- Admin callers may also search `archived`
- Exact reads allow `published` and `deprecated` for read callers; `archived` requires `admin`

Git is optional provenance only. The server does not require a Git checkout to publish, search,
or fetch exact versions at runtime.

## Caching and Integrity

Current integrity and caching behavior:

- Content digests use `sha256`
- Exact content responses expose digest-backed `ETag`
- Immutable content responses send `Cache-Control: public, immutable`

The PRD also calls out full conditional read behavior (`If-None-Match` -> `304 Not Modified`) as
part of the target contract. The README treats digest-backed `ETag` emission as implemented today
and the broader conditional-read contract as part of the documented direction.

## Local Development

### Requirements

- Python `3.12+`
- [`uv`](https://docs.astral.sh/uv/)
- Docker

### Start PostgreSQL

```bash
make db-up
```

This starts PostgreSQL on `localhost:5432` with the default database `aptitude`.

### Install dependencies

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

### Configure environment

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"
export AUTH_TOKENS_JSON='{"reader-token":["read"],"publisher-token":["read","publish"],"admin-token":["read","publish","admin"]}'
```

Optional settings:

- `LOG_LEVEL` defaults to `INFO`
- `ACTIVE_POLICY_PROFILE` defaults to `default`
- `POLICY_PROFILES_JSON` can define additional policy profiles

### Run migrations and start the API

```bash
make migrate-up
make run
```

The API runs on `http://127.0.0.1:8000`.

### Useful commands

```bash
make test
make lint
make format
make typecheck
make migrate-down
make db-down
```

## Project References

- Product requirements: [`docs/prd.md`](docs/prd.md)
- Server/client boundary: [`docs/scope.md`](docs/scope.md)
- Storage decision: [`docs/storage-strategy.md`](docs/storage-strategy.md)
- Product and architecture overview: [`docs/overview.md`](docs/overview.md)
- API contract: [`docs/api-contract.md`](docs/api-contract.md)
