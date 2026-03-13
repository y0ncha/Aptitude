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

`aptitude-server` is the registry service in the Aptitude ecosystem.
It stores immutable skill markdown, structured metadata, and relationship
selectors in PostgreSQL so clients can publish versions, fetch exact content,
and rely on registry-backed discovery instead of crawling the full catalog.

## What This Service Owns

- Immutable `slug@version` publication
- Exact version fetches with checksum-backed integrity validation
- Version metadata and direct dependency declarations
- Registry metadata that powers discovery APIs
- Publish/read auditability and lifecycle governance

## What It Does Not Own

`aptitude-server` is not the client runtime.
Prompt interpretation, reranking, dependency solving, lock generation, and
execution planning belong to the client-side runtime.

Use this rule consistently:

- Server owns data-local work
- Client owns decision-local work

In practice, that means the server behaves more like a package registry, while
the client behaves more like the package manager and runtime planner.

## How It Fits Together

```text
User / Agent
  -> Client
  -> aptitude-server
  -> PostgreSQL + audit log
```

The server keeps immutable records and exposes stable registry APIs.
The client uses those APIs to retrieve candidates, choose versions, solve
dependencies, and build reproducible lock output.

## Current Scope

The current implementation is intentionally registry-first.

Implemented now:

- FastAPI service with health and readiness endpoints
- Immutable publish API for normalized JSON payloads
- Exact metadata and content fetch by `slug` and `version`
- Version listing per skill
- Indexed advisory search over metadata and descriptions
- Direct relationship batch reads over authored selectors
- Lifecycle governance and status transitions
- PostgreSQL-backed content and metadata persistence
- Direct dependency declaration validation and retrieval

Planned next:

- Richer governance and lifecycle controls
- Discovery metadata and evaluation signals

## Current API

Available endpoints today:

- `GET /healthz`
- `GET /readyz`
- `GET /discovery/skills/search`
- `POST /resolution/relationships:batch`
- `POST /skill-versions`
- `GET /skills/{slug}`
- `GET /skills/{slug}/versions`
- `GET /skills/{slug}/versions/{version}`
- `GET /skills/{slug}/versions/{version}/content`
- `PATCH /skills/{slug}/versions/{version}/status`

`GET /discovery/skills/search` is a discovery API for candidate generation only. Prompt
interpretation, reranking, final selection, dependency solving, and execution
planning remain client-owned responsibilities.

When the service is running locally, OpenAPI docs are available at
`http://127.0.0.1:8000/docs`.
The pinned standalone OpenAPI contract for the current v1 surface is committed at
`docs/openapi/repository-api-v1.json`.

## Tech At A Glance

- Python 3.12+
- FastAPI + Pydantic v2
- PostgreSQL + SQLAlchemy + Alembic
- PostgreSQL-backed content and search projections
- Ruff, pytest, mypy

## Local Development

### Requirements

- Python 3.12+
- `uv`
- Docker (recommended for local PostgreSQL)

### Start the database

```bash
make db-up
```

This starts PostgreSQL on `localhost:5432` with the default database
`aptitude`.

### Install dependencies and run the server

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/aptitude"
make migrate-up
make run
```

`make run` uses the FastAPI CLI with the committed `app.main:app` entrypoint.
The app runs on `http://127.0.0.1:8000`.

### Useful commands

```bash
make lint
make test
make typecheck
make db-down
```

## More Context

- Product and architecture overview: [`docs/overview.md`](docs/overview.md)
- Server vs client boundary: [`docs/scope.md`](docs/scope.md)
