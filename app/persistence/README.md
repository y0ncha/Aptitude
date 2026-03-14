# app.persistence module

Persistence adapters and storage infrastructure.

## Purpose

Implements core persistence ports for:

- PostgreSQL metadata persistence (SQLAlchemy)
- digest-addressed immutable markdown storage in PostgreSQL
- authored relationship selector preservation for exact dependency reads
- exact immutable metadata and content lookup for one `slug@version`
- advisory search read model and indexed candidate retrieval
- database lifecycle/readiness

## Key Files

- `db.py`: engine/session lifecycle and readiness probe adapter.
- `skill_registry_repository.py`: SQLAlchemy adapter for skill catalog persistence
  plus selector and advisory search read-model writes from authored manifest contracts.
- `models/`: ORM models.

## Contracts

Adapters in this package implement protocols defined in `app.core.ports`.
