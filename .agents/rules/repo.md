# Repo Rules

## Purpose

This file centralizes the strict project rules for `aptitude-server`.

Use this file for hard constraints and invariants.

## Approval Gates

- Any database schema change requires explicit user approval before implementation.
- Any public API contract change requires explicit user approval before implementation.

Schema changes include:

- Alembic migrations
- SQLAlchemy model shape changes
- new or changed tables, columns, indexes, constraints, or relationships

API contract changes include:

- request or response schema changes
- endpoint additions, removals, or path changes
- behavior changes that alter the documented external contract
- interactive docs or public API contract changes

## Pre-Production Default

- This codebase is not in production yet.
- Prefer overwriting, deleting, and simplifying existing code over adding migrations, compatibility layers, or transitional glue.
- It is acceptable to break anything except tests when doing cleanup or structural improvements.

## Architecture Boundaries

- Interface layer validates requests and maps DTOs.
- Core layer owns immutable catalog lifecycle, integrity checks, and policy decisions.
- Intelligence layer provides metadata and relationship signals, not runtime solving.
- Persistence layer stores artifacts, metadata indexes, and edges.
- Audit layer records publish, read, governance, and evaluation events.

### Dependency Direction

- `interface -> core`
- `core -> intelligence` when present
- `core` depends on persistence only through core-defined ports and interfaces
- `persistence` implements core ports and may import core abstractions

### Forbidden Imports

- `app/interface/**` must not import `app/persistence/**`
- `app/core/**` must not import `app/persistence/**`

### Composition Root Exception

- `app/main.py` may wire core services to persistence adapters

## Required Product Invariants

- Skill versions are immutable.
- Dependency declarations are returned exactly as authored for each immutable version.
- Relationships stay explicitly typed: `depends_on`, `conflicts_with`, `overlaps_with`, `extends`.
- Server behavior remains execution-agnostic.
- The server must not own `/resolve`, bundle, report, or execution-planning APIs.

## Naming

- Use `kebab-case` for new filenames, rule identifiers, and plan slugs unless an external framework or tool requires a different format.

## Mandatory Outputs

- Stable manifest, integrity, and artifact metadata contracts for exact version reads.
- Deterministic version listings and boundary-safe error envelopes.
