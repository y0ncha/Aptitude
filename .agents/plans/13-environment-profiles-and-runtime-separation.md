# Plan 13 - Environment Profiles and Runtime Separation

## Summary
Standardize `dev`, `test`, and `prod` as explicit runtime profiles before any auth-mechanism refactor. This milestone defines how the same FastAPI service is configured and operated across environments while keeping the public endpoint surface unchanged and simple.

## Key Changes
- Add explicit environment/profile settings in `app/core/settings.py`:
  - `APP_ENV`: `dev | test | prod`
  - keep one env-driven settings model; do not introduce separate applications or per-environment forks
  - default `APP_ENV` remains `dev`
- Define environment intent and runtime expectations:
  - `dev`: fast local iteration
  - `test`: CI and integration environment with production-like behavior where practical
  - `prod`: deployment profile for real traffic
- Keep environment handling runtime-only:
  - route names, route count, prefixes, request shapes, and response shapes remain identical across all environments
  - no dev/test/prod-specific endpoint variants or helper routes
- Add explicit runner profiles in `Makefile` and docs:
  - `make run`: `APP_ENV=dev`
  - `make test`: `APP_ENV=test`
  - production docs specify `APP_ENV=prod`
- Standardize non-auth environment behavior as needed:
  - config validation
  - startup defaults
  - logging and debug posture
  - dependency wiring expectations
  - migration and deployment guidance
- Do not redesign auth in this milestone beyond the minimum configuration plumbing needed so the next milestone can manage auth cleanly in `test` and `prod`.

## Public Interfaces and Configuration
- New or standardized environment variable:
  - `APP_ENV=dev|test|prod`
- Behavioral contract:
  - no HTTP API shape changes to the hard-cut public contract
  - all three environments expose the same public endpoint surface
  - environment choice changes configuration and runtime posture, not the registry contract

## Acceptance Criteria
- `dev`, `test`, and `prod` are explicit, validated runtime profiles.
- The same public route surface is exposed in all environments.
- Environment-profile work does not add auth endpoints, debug endpoints, or alternate route variants.
- `test` is configured as a distinct environment rather than being treated as a loose variant of `dev`.
- The milestone leaves a clear foundation for the next plan to manage auth mechanisms in `test` and `prod` without revisiting environment structure.

## Test Plan
- Unit tests for settings validation:
  - `APP_ENV=dev` is accepted
  - `APP_ENV=test` is accepted
  - `APP_ENV=prod` is accepted
  - invalid environment values fail fast
- Startup/config tests:
  - each environment loads the expected runtime profile and defaults
  - environment selection does not alter route registration
- Regression tests:
  - existing API tests continue to target the same endpoint surface regardless of environment
  - no governance or route-shape changes occur solely because `APP_ENV` changes

## Assumptions and Defaults
- This milestone is intentionally placed before auth hardening so environment boundaries are explicit first.
- There is no separate `staging` profile in this milestone; staging should use `prod` semantics unless a later plan introduces a fourth profile.
- The repo keeps one FastAPI app and one settings model; environment behavior is controlled by validated settings and runner commands, not separate codebases.
