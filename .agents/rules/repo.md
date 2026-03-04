# Repo Rules

## Architecture Boundaries
- Interface layer validates requests and maps DTOs.
- Core layer owns lifecycle, resolution, and policy decisions.
- Intelligence layer provides metadata and relationship signals.
- Persistence layer stores artifacts, metadata indexes, and edges.
- Audit layer records publish/deprecate/resolve/evaluate events.

## Required Invariants
- Immutable skill versions.
- Deterministic `ResolvedBundle` generation.
- Explicit typed relationships (`depends_on`, `conflicts_with`, `overlaps_with`, `extends`).
- Execution-agnostic repository behavior.

## Planning and Execution
- Work on one milestone plan file at a time (`.agents/plans/plan-XX-*.md`).
- Do not start the next plan file before the current one meets its acceptance criteria.
- Keep plan files append-only: do not renumber or rename completed plans.
- Every implementation PR should map to exactly one active plan file.

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
  - `.agents/memory/meta.md` for stable product/repo facts
- For new APIs or payloads, document endpoint, request shape, response shape, and error cases.
- Document deterministic rules explicitly (ordering, tie-breakers, policy precedence).

## Mandatory Outputs
- `ResolvedBundle` for resolution requests.
- `ResolutionReport` explaining selection and constraints.
