# Repo Rules

## Architecture Boundaries
- Interface layer validates requests and maps DTOs.
- Core layer owns immutable catalog lifecycle, integrity checks, and policy decisions.
- Intelligence layer provides metadata and relationship signals, not runtime solving.
- Persistence layer stores artifacts, metadata indexes, and edges.
- Audit layer records publish/read/governance/evaluation events.
- Dependency direction is strict:
  - `interface -> core`
  - `core -> intelligence` (when present)
  - `core` depends on persistence only through core-defined ports/interfaces
  - `persistence` implements core ports and may import core abstractions
- Forbidden imports:
  - `app/interface/**` must not import `app/persistence/**`
  - `app/core/**` must not import `app/persistence/**`
- Composition root exception:
  - `app/main.py` may wire core services to persistence adapters.

## Required Invariants
- Immutable skill versions.
- Dependency declarations are returned exactly as authored for each immutable version.
- Explicit typed relationships (`depends_on`, `conflicts_with`, `overlaps_with`, `extends`).
- Execution-agnostic server behavior.
- No server-owned `/resolve`, bundle, report, or execution-planning APIs.

## Naming Convention
- Use `kebab-case` for new filenames, rule identifiers, and plan slugs unless an external framework/tool requires a different format.

## Planning and Execution
- Work on one milestone plan file at a time (`.agents/plans/plan-XX-*.md`).
- Do not start the next plan file before the current one meets its acceptance criteria.
- Keep plan files append-only: do not renumber or rename completed plans.
- Every implementation PR should map to exactly one active plan file.
- When finishing work on a plan, review older changelogs and prior implementation
  work for logic conflicts, redundant code, or obsolete code that can now be removed.

## TDD Workflow
- Follow RED -> GREEN -> REFACTOR for non-trivial changes.
- Write or update failing tests first for new behavior.
- Implement the minimal change to pass tests.
- Refactor only with tests green and keep behavior unchanged.
- Include happy-path and failure-path coverage for each milestone.

## Documentation Guidelines
- Keep docs concise, concrete, and synced with behavior.
- Update these files when relevant behavior changes:
  - `.agents/plans/plan-XX-*.md` for milestone scope/acceptance updates
  - `.agents/plans/roadmap.md` for sequencing changes
  - `.agents/memory/meta.md` for stable product/server facts
- For new APIs or payloads, document endpoint, request shape, response shape, and error cases.
- Document deterministic rules explicitly (ordering, tie-breakers, policy precedence).

## Mandatory Outputs
- Stable manifest, integrity, and artifact metadata contracts for exact version reads.
- Deterministic version listings and boundary-safe error envelopes.
