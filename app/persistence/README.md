# app.persistence module

Persistence adapters and storage infrastructure.

## Purpose

Implements core persistence ports for:

- PostgreSQL metadata persistence (SQLAlchemy)
- filesystem immutable artifact storage
- dependency metadata edge read model (`depends_on`, `extends`) with selector preservation
- advisory search read model and indexed candidate retrieval
- database lifecycle/readiness

## Key Files

- `db.py`: engine/session lifecycle and readiness probe adapter.
- `artifact_store.py`: filesystem artifact adapter.
- `skill_registry_repository.py`: SQLAlchemy adapter for skill catalog persistence
  plus dependency edge and advisory search read-model writes from authored manifest contracts.
- `models/`: ORM models.

## Contracts

Adapters in this package implement protocols defined in `app.core.ports`.
