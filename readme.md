# Aptitude Repository

![Python Version](https://img.shields.io/badge/python-3.12+-3776AB?logo=python)
![License](https://img.shields.io/github/license/y0ncha/aptitude)
![Last Commit](https://img.shields.io/github/last-commit/y0ncha/aptitude)
![Issues](https://img.shields.io/github/issues/yoncha/aptitude)
![Status](https://img.shields.io/badge/status-active--development-blue)

Aptitude is a versioned, dependency-aware skill repository for AI systems.  
It manages skills as atomic, immutable, and composable capability units rather than ad hoc prompt fragments.

The repository provides:

- Deterministic versioning
- Explicit dependency modeling
- Structured metadata enrichment
- Evaluation-based ranking
- Secure skill supply chain governance

---

## Design Principles

- Skills are immutable and independently versioned
- All relationships are explicit and typed
- Resolution is centralized and deterministic
- Metadata drives optimization, not heuristics
- The repository is execution-agnostic
- Reproducibility is guaranteed by version + repository state

---

## Architecture (High-Level)

Client / Loader / SDK  
→ Repository Interface  
→ Core Domain (Registry + Resolver + Policy)  
→ Intelligence Layer (Graph + Metadata)  
→ Persistence (Artifacts + Index + Graph Store)

---

## Current Status

The project is under active development and currently in planning-to-implementation transition.

Roadmap and implementation plan: [`docs/overview.md`](docs/overview.md) (Planning + Tech Stack sections).

---

## Planned Stack

- API: FastAPI + Pydantic v2
- Runtime: Python 3.12+
- Data: PostgreSQL (default from first milestone)
- ORM/migrations: SQLAlchemy 2.0 + Alembic
- Jobs: APScheduler (MVP), Celery + Redis (scale)
- Quality: pytest, ruff, mypy

---

## Getting Started (once service scaffold is added)

### Requirements

- Python 3.12+
- PostgreSQL 15+
- `uv` (recommended) or `pip`
- Docker (optional)

### Run locally (planned)

```bash
uv venv
source .venv/bin/activate
uv pip install fastapi "uvicorn[standard]" sqlalchemy alembic pydantic-settings
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/aptitude"
uvicorn app.main:app --reload
```
