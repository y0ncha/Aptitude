# Milestone 02 Changelog - Immutable Skill Registry

This changelog documents implementation of [.agents/plans/02-immutable-skill-registry.md](/Users/yonatan/Dev/aptitude-server/.agents/plans/02-immutable-skill-registry.md).

## Scope Delivered

- Added immutable publish/fetch/list endpoints (canonical contract):
  - `POST /skills/publish`: Publishes a new immutable skill version (manifest + artifact), persists checksum/metadata, and rejects duplicate `skill_id+version` with `409` ([API route](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [core publish logic](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [repository uniqueness handling](/Users/yonatan/Dev/aptitude-server/app/persistence/skill_registry_repository.py)).
  - `GET /skills/{id}/{version}`: Fetches a specific immutable skill version and verifies checksum on read to detect corruption ([API route](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [core fetch + integrity check](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py)).
  - `GET /skills/{id}`: Lists available versions (and related metadata) for the given skill id ([API route](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [repository listing order](/Users/yonatan/Dev/aptitude-server/app/persistence/skill_registry_repository.py)).
- Added strict `SkillManifest` validation with SemVer and typed relationship fields ([manifest DTO](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [manifest unit tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_skill_manifest.py)).
- Added immutable artifact filesystem storage with deterministic path convention ([filesystem adapter](/Users/yonatan/Dev/aptitude-server/app/persistence/artifact_store.py)).
- Added checksum persistence and read-time checksum verification ([core checksum flow](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [checksum model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/skill_version_checksum.py), [migration](/Users/yonatan/Dev/aptitude-server/alembic/versions/0002_immutable_skill_registry.py)).
- Added audit event recording for publish/read/list and integrity violation detection ([audit events in core service](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [audit adapter](/Users/yonatan/Dev/aptitude-server/app/audit/recorder.py), [audit model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/audit_event.py)).
- Added PostgreSQL schema for `skills`, `skill_versions`, and `skill_version_checksums` ([migration](/Users/yonatan/Dev/aptitude-server/alembic/versions/0002_immutable_skill_registry.py), [skills model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/skill.py), [skill version model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/skill_version.py), [checksum model](/Users/yonatan/Dev/aptitude-server/app/persistence/models/skill_version_checksum.py)).

## Design Notes

- Duplicate publish is treated as a hard conflict (`409`) to keep immutability rules explicit ([duplicate guard in core](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [409 mapping in API](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [integration test](/Users/yonatan/Dev/aptitude-server/tests/integration/test_skill_registry_endpoints.py)).
- The service verifies checksum on every version fetch to detect silent filesystem corruption early ([core integrity check](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [integration corruption test](/Users/yonatan/Dev/aptitude-server/tests/integration/test_skill_registry_endpoints.py)).
- Artifacts are written using exclusive file creation and version-specific immutable paths to prevent in-place mutation ([artifact store write mode + path layout](/Users/yonatan/Dev/aptitude-server/app/persistence/artifact_store.py)).
- Relationship fields are present in milestone 02 manifests even before resolver logic, reducing migration churn for milestones 03 and 06 ([manifest schema](/Users/yonatan/Dev/aptitude-server/app/interface/api/skills.py), [manifest validation tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_skill_manifest.py)).
- API write path is centralized through repository endpoints and core service orchestration (`SkillRegistryService`) ([core service](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [repository adapter](/Users/yonatan/Dev/aptitude-server/app/persistence/skill_registry_repository.py), [composition wiring](/Users/yonatan/Dev/aptitude-server/app/main.py)).

## Idempotency and Immutable Modeling Learnings

- Immutable versioning and idempotency are related but distinct.
- This milestone intentionally chooses strict immutability over idempotent replay for duplicate `skill_id+version` publishes ([duplicate handling in core service](/Users/yonatan/Dev/aptitude-server/app/core/skill_registry.py), [duplicate conflict test](/Users/yonatan/Dev/aptitude-server/tests/integration/test_skill_registry_endpoints.py)).
- If idempotent replay is needed later, it should be implemented explicitly via idempotency keys or request fingerprints, not by silent overwrite behavior.

## Verification Notes

- Unit tests for manifest validation, registry core behavior, layering, and settings pass ([manifest tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_skill_manifest.py), [registry service tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_skill_registry_service.py), [layering tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_layering_imports.py), [settings tests](/Users/yonatan/Dev/aptitude-server/tests/unit/test_settings.py)).
- Integration tests for publish/fetch/list, duplicate conflict, and checksum mismatch are in place and require PostgreSQL availability ([endpoint integration tests](/Users/yonatan/Dev/aptitude-server/tests/integration/test_skill_registry_endpoints.py), [migration integration tests](/Users/yonatan/Dev/aptitude-server/tests/integration/test_migrations.py)).

## Current Schema Reference (0002)

Source migration: [0002_immutable_skill_registry.py](/Users/yonatan/Dev/aptitude-server/alembic/versions/0002_immutable_skill_registry.py).

### `skills` (logical skill identity)

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `id` | `BigInteger` | No | Primary key, autoincrement | Internal surrogate key for joins. |
| `skill_id` | `Text` | No | Unique | Stable external skill identifier shared by versions. |
| `created_at` | `DateTime(timezone=True)` | No | `CURRENT_TIMESTAMP` | Creation timestamp of the logical skill root. |

### `skill_versions` (immutable version metadata)

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `id` | `BigInteger` | No | Primary key, autoincrement | Internal row identifier for an immutable version. |
| `skill_fk` | `BigInteger` | No | FK -> `skills.id` (`ON DELETE CASCADE`) | Links a version to its parent skill. |
| `version` | `Text` | No | Unique with `skill_fk`; SemVer check constraint | Immutable version label (`skill_id + version` uniqueness boundary). |
| `manifest_json` | `JSONB` | No | Required | Canonical manifest snapshot for this version. |
| `artifact_rel_path` | `Text` | No | Required | Relative filesystem path to immutable artifact bytes. |
| `artifact_size_bytes` | `BigInteger` | No | Required | Artifact size used for metadata and integrity context. |
| `published_at` | `DateTime(timezone=True)` | No | `CURRENT_TIMESTAMP` | Publish timestamp for ordering/version history. |

Indexes and table constraints:
- `uq_skill_versions_skill_fk_version`: prevents duplicate `skill_id+version` pairs.
- `ix_skill_versions_skill_fk_published_at_id`: supports deterministic listing by publish time/id.
- `ix_skill_versions_skill_fk_version`: supports direct lookup by skill/version.

### `skill_version_checksums` (integrity metadata)

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `id` | `BigInteger` | No | Primary key, autoincrement | Internal checksum row identifier. |
| `skill_version_fk` | `BigInteger` | No | FK -> `skill_versions.id` (`ON DELETE CASCADE`), unique | One-to-one checksum record per immutable version. |
| `algorithm` | `String(20)` | No | Check: must equal `sha256` | Declares checksum algorithm. |
| `digest` | `String(64)` | No | Check: length must be `64` | Hex-encoded SHA-256 digest used for read-time integrity verification. |
| `created_at` | `DateTime(timezone=True)` | No | `CURRENT_TIMESTAMP` | Checksum record creation timestamp. |
