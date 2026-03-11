# app.persistence.models module

SQLAlchemy ORM models mapped to Aptitude Server tables.

## Purpose

Defines relational schema mappings used by persistence adapters and Alembic
migrations.

## Key Files

- `base.py`: declarative base class.
- `skill.py`: logical skill root table (`skills`).
- `skill_version.py`: immutable version metadata (`skill_versions`).
- `skill_version_checksum.py`: checksum metadata (`skill_version_checksums`).
- `skill_relationship_edge.py`: typed relationship edges (`skill_relationship_edges`)
  with authored target version selectors for dependency/read-model projections.
- `skill_search_document.py`: denormalized advisory search documents (`skill_search_documents`)
  for compact candidate retrieval.
- `audit_event.py`: audit event table (`audit_events`).
- `__init__.py`: package exports.

## Notes

Keep model docs aligned with Alembic migrations and persistence adapter behavior.
