# aptitude-server

![Python Version](https://img.shields.io/badge/python-3.12+-3776AB?logo=python)
![License](https://img.shields.io/github/license/y0ncha/aptitude-server)
![Last Commit](https://img.shields.io/github/last-commit/y0ncha/aptitude-server)
![Issues](https://img.shields.io/github/issues/y0ncha/aptitude-server)
![Status](https://img.shields.io/badge/status-active--development-blue)

`aptitude-server` is the registry service in the Aptitude ecosystem.
It stores immutable skill artifacts and versioned metadata so clients can
publish skills, fetch exact versions, and rely on registry-backed discovery
instead of crawling the full catalog.

## What This Service Owns

- Immutable `skill_id@version` publication
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
  -> PostgreSQL + artifact storage + audit log
```

The server keeps immutable records and exposes stable registry APIs.
The client uses those APIs to retrieve candidates, choose versions, solve
dependencies, and build reproducible lock output.

## Current Scope

The current implementation is intentionally registry-first.

Implemented now:

- FastAPI service with health and readiness endpoints
- Immutable publish API for skill manifest + artifact
- Exact fetch by `skill_id` and `version`
- Version listing per skill
- Checksum verification on artifact reads
- PostgreSQL-backed metadata persistence and filesystem artifact storage
- Direct dependency declaration validation and retrieval

Planned next:

- Search and candidate retrieval APIs
- Richer governance and lifecycle controls
- Discovery metadata and evaluation signals

## Current API

Available endpoints today:

- `GET /healthz`
- `GET /readyz`
- `POST /skills/publish`
- `GET /skills/{skill_id}/{version}`
- `GET /skills/{skill_id}`

Planned but not yet implemented:

- `GET /skills/search`

Search remains a future discovery API for candidate generation only. When it is
added, prompt interpretation, reranking, final selection, dependency solving,
and execution planning will remain client-owned responsibilities.

When the service is running locally, OpenAPI docs are available at
`http://127.0.0.1:8000/docs`.
The pinned standalone OpenAPI contract for the current v1 surface is committed at
`docs/openapi/repository-api-v1.json`.

## Tech At A Glance

- Python 3.12+
- FastAPI + Pydantic v2
- PostgreSQL + SQLAlchemy + Alembic
- Filesystem artifact storage
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
