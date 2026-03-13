# Plan 12 - Minimal Auth Boundary and Token Governance

## Goal
Introduce a minimal, maintainable authentication boundary for `aptitude-server` that keeps opaque bearer-token auth simple while separating transport parsing, authorization rules, and token-source configuration into distinct layers.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Configuration: pydantic-settings plus environment overrides or secret-manager injection
- Architecture style: layered/hexagonal boundary between interface, core auth policy, and token-source adapter

## Scope
- Keep authentication based on opaque bearer tokens and scope mapping such as `read`, `publish`, and `admin`.
- Keep FastAPI responsible only for extracting bearer credentials from HTTP requests.
- Move token validation, caller identity construction, and scope enforcement into a dedicated auth layer outside route dependencies.
- Add a small port/adapter boundary for token lookup so the initial implementation can remain settings-backed while allowing later replacement with a secret manager or identity adapter.
- Standardize auth error codes and request handling across publish, fetch, list, discovery, relationship, and lifecycle routes.
- Document the intended security posture: internal-service auth, static opaque tokens, and no delegated end-user identity.
- Preserve current external API behavior where possible to avoid unnecessary client churn.

## Out of Scope
- OAuth2 authorization flows, login screens, refresh tokens, or browser session auth.
- JWT issuance, JWKS validation, external identity providers, or token introspection.
- Per-user RBAC, multitenancy, or organization-level authorization models.
- Fine-grained object permissions beyond the existing route-level scopes and governance policy.

## Architecture Impact
- Clarifies layer ownership by removing authentication decisions from the FastAPI transport boundary.
- Keeps the system intentionally simple while avoiding a hard dependency on environment-shape auth in core request handling.
- Creates a clean replacement seam if the service later needs stronger machine-to-machine auth without rewriting route handlers.

## Deliverables
- Core auth service or policy module that authenticates opaque tokens into a `CallerIdentity`.
- Auth token lookup port with an initial settings-backed adapter.
- Thin FastAPI dependencies that only parse credentials and delegate auth decisions.
- Shared scope-enforcement helpers for `read`, `publish`, and `admin`.
- Architecture note describing why the service intentionally stays with opaque bearer tokens instead of OAuth2/JWT at this stage.

## Acceptance Criteria
- Route handlers and FastAPI dependencies no longer contain token lookup or authorization decision logic beyond request parsing and delegation.
- Opaque bearer tokens remain the only supported auth mechanism.
- The settings-backed token map can be swapped behind a port without changing route handlers or core policy code.
- Auth failures remain deterministic with stable error codes for missing credentials, invalid tokens, and insufficient scope.
- No OAuth2, JWT, or end-user identity concepts are introduced into the public API, configuration model, or runtime flow.

## Test Plan
- Unit tests for auth service success and failure paths.
- Unit tests for scope enforcement against `read`, `publish`, and `admin`.
- Interface tests confirming FastAPI dependencies translate auth failures into the expected HTTP responses.
- Regression tests showing all protected routes still enforce the same access semantics after the auth-layer refactor.
