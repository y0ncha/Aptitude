# Milestone 04 Changelog - Repository API Contract V1

This changelog documents implementation alignment for [.agents/plans/04-repository-api-contract-v1.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/04-repository-api-contract-v1.md).

## Scope Delivered

- FastAPI now publishes explicit top-level API metadata for the stable v1 contract in [app/main.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/main.py), and the human-readable contract summary lives in [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md).
- The public skill routes in [app/interface/api/skills.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/skills.py) now carry stable `operation_id`s, shared response metadata, and example-backed request/response docs for `POST /skills/publish`, `GET /skills/{skill_id}/{version}`, and `GET /skills/{skill_id}`.
- Request validation failures are normalized through [app/interface/api/errors.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/errors.py) and [app/interface/dto/errors.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/dto/errors.py), so FastAPI-managed 422s and domain-level manifest failures share one error envelope while keeping distinct codes such as `INVALID_REQUEST` and `INVALID_MANIFEST`.
- Shared example payloads are centralized in [app/interface/dto/examples.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/dto/examples.py) and validated by [tests/unit/test_api_contract_examples.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_api_contract_examples.py) to keep the docs and DTOs in sync.
- Search is explicitly documented as deferred rather than stubbed. See [README.md](/Users/yonatan/Dev/Aptitude/aptitude-server/README.md) and [app/interface/api/README.md](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/README.md).

## Architecture Snapshot

```mermaid
flowchart LR
    Client["Client"] --> App["FastAPI App<br/>app/main.py"]
    App --> Skills["Skills Router<br/>app/interface/api/skills.py"]
    App --> Validation["RequestValidationError Handler<br/>app/interface/api/errors.py"]
    Skills --> DTOs["DTOs + Examples<br/>app/interface/dto"]
    App --> Docs["Swagger UI<br/>http://127.0.0.1:8000/docs"]
```

Why this shape:
- The API contract stays FastAPI-native instead of being hand-maintained separately, so runtime behavior and the interactive docs come from the same application wiring. See [app/main.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/main.py) and [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md).
- Error serialization is centralized once and reused across routes, which prevents path/query/form validation from drifting into FastAPI’s default 422 payload shape. See [app/interface/api/errors.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/errors.py) and [tests/integration/test_skill_registry_endpoints.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/integration/test_skill_registry_endpoints.py).

## Runtime Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Skills API
    participant V as Validation Handler
    participant S as SkillRegistryService

    C->>A: POST /skills/publish
    alt FastAPI request validation fails
        A->>V: RequestValidationError
        V-->>C: 422 INVALID_REQUEST
    else Manifest parses and validates
        A->>S: publish_version(...)
        S-->>A: SkillVersionDetail
        A-->>C: 201 Created
    else Manifest JSON/schema fails
        A-->>C: 422 INVALID_MANIFEST
    end
```

## Design Notes

- The stable public contract remains the unversioned `/skills/...` surface. This milestone versioned the contract via FastAPI metadata, not by adding `/v1` path aliases. See [app/main.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/main.py), [app/interface/api/skills.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/skills.py), and [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py).
- Manifest validation and generic request validation are intentionally split. Multipart/path/query/form failures return `INVALID_REQUEST`, while manifest JSON/schema failures inside the publish flow return `INVALID_MANIFEST`. See [app/interface/api/errors.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/errors.py), [app/interface/api/skills.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/skills.py), and [tests/integration/test_skill_registry_endpoints.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/integration/test_skill_registry_endpoints.py).
- This milestone changes public HTTP contracts only. No database migration or persistence model change was required.
- `GET /skills/search` remains out of the implementation and out of the documented API contract, which keeps the contract aligned with the current server/client boundary while milestone 05 owns discovery behavior. See [README.md](/Users/yonatan/Dev/Aptitude/aptitude-server/README.md), [app/interface/api/README.md](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/api/README.md), and [.agents/plans/05-metadata-search-ranking.md](/Users/yonatan/Dev/Aptitude/aptitude-server/.agents/plans/05-metadata-search-ranking.md).

## Schema Reference

Sources: [app/interface/dto/errors.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/dto/errors.py), [app/interface/dto/skills.py](/Users/yonatan/Dev/Aptitude/aptitude-server/app/interface/dto/skills.py), and [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md).

### `ErrorEnvelope`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `error` | `ErrorBody` | No | Required | Wraps every public API failure in one stable top-level object so clients never have to parse route-specific error shapes. |
| `error.code` | `string` | No | Required | Carries a machine-readable failure category such as `INVALID_REQUEST`, `INVALID_MANIFEST`, or `SKILL_VERSION_NOT_FOUND`. |
| `error.message` | `string` | No | Required | Provides a short human-readable summary suitable for logs and debugging output. |
| `error.details` | `object` | Yes | Omitted when not needed | Holds structured diagnostics such as field validation errors or missing skill coordinates without changing the envelope structure. |

### `Body_publishSkillVersion`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `manifest` | `string` | No | Required multipart form field | Preserves the authored manifest as a JSON string in multipart uploads so the publish route can validate it explicitly before crossing into the core layer. |
| `artifact` | `binary string` | No | Required multipart form field | Carries the immutable artifact payload associated with the published skill version. |

### `SkillVersionFetchResponse`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `skill_id` | `string` | No | Required | Echoes the immutable catalog identifier requested by the client. |
| `version` | `string` | No | Required semver | Pins the exact immutable version returned by the registry. |
| `manifest` | `SkillManifest` | No | Required | Returns the validated manifest contract as stored by the service. |
| `checksum` | `ChecksumResponse` | No | Required | Exposes the checksum metadata clients use to reason about artifact integrity. |
| `artifact_metadata` | `ArtifactMetadataResponse` | No | Required | Returns stable artifact location and size metadata without exposing storage internals beyond the contract. |
| `published_at` | `datetime` | No | Required UTC timestamp | Provides deterministic publication timing for read and list consumers. |
| `artifact_base64` | `string` | No | Required | Encodes the binary artifact into JSON-safe transport for exact fetch responses. |

## Verification Notes

- Runtime contract drift is covered by route-boundary and example validation tests alongside [docs/api-contract.md](/Users/yonatan/Dev/Aptitude/aptitude-server/docs/api-contract.md).
- Example payload validity is covered by [tests/unit/test_api_contract_examples.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_api_contract_examples.py), which validates both success payloads and error examples against the DTO layer.
- Public surface and boundary metadata are covered by [tests/unit/test_registry_api_boundary.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/unit/test_registry_api_boundary.py).
- Integration coverage for normalized invalid-request handling and manifest failures lives in [tests/integration/test_skill_registry_endpoints.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/integration/test_skill_registry_endpoints.py). These tests still require a reachable PostgreSQL instance through [tests/conftest.py](/Users/yonatan/Dev/Aptitude/aptitude-server/tests/conftest.py).
