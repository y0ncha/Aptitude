# Aptitude Agent Contract

## General Idea
Aptitude is a Python-based, execution-agnostic registry server for immutable
skills with deterministic dependency metadata contracts, explicit relationships,
policy governance, and auditable outcomes.

## Entry Point

Use this file as the main agent-facing entrypoint for:

- workflow
- methodology
- collaboration expectations
- documentation preferences

Strict project rules and approval gates remain centralized in
[`rules/repo.md`](rules/repo.md).

## Source and Instruction Files
1. Product and architecture intent: [`docs/overview.md`](../docs/overview.md)
2. Server/Resolver boundary contract: [`docs/scope.md`](../docs/scope.md)
3. Server product requirements: [`docs/prd.md`](../docs/prd.md)
4. Strict repo rules: [`rules/repo.md`](rules/repo.md)
5. Roadmap and sequencing: [`plans/roadmap.md`](plans/roadmap.md)
6. Plan execution files: `plans/XX-*.md` (append-only milestones)
7. Stable repo facts: [`memory/meta.md`](memory/meta.md)
8. Skills:
   - [`skills/architect-review`](skills/architect-review) - system design and architecture best practices
   - [`skills/fastapi`](skills/fastapi) - fastapi best practices
   - [`skills/postgres-patterns`](skills/postgres-patterns) - postgres best practices
   - [`skills/python-patterns`](skills/python-patterns) - python best practices
   - [`skills/python-testing`](skills/python-patterns) - python testing best practices
   - [`skills/prd`](skills/prd) - prd writing best practices


If rules conflict, follow the highest item unless the server includes a newer explicit architecture decision.

## Relevant Paths for Task Execution

Use these paths when gathering context and executing work.

### Core Code Paths

- `app/main.py`: composition root and app wiring
- `app/interface/`: FastAPI routes, DTOs, API helpers, error mapping
- `app/core/`: domain services, ports, governance, fetch, discovery, resolution
- `app/intelligence/`: pure ranking and search support logic
- `app/persistence/`: SQLAlchemy models, repository adapters, persistence helpers
- `app/audit/`: audit storage and audit-facing logic

### Verification and Tooling Paths

- `tests/unit/`: unit coverage for pure logic and service behavior
- `tests/integration/`: integration coverage for API, repository, and migrations
- `tests/resources/`: test payloads and fixture resources
- `alembic/versions/`: schema migration history
- `scripts/`: repo scripts and maintenance utilities
- `postman/collections/`: executable API request coverage and examples
- `postman/environments/`: Postman environments for local/manual validation
- `.github/workflows/`: CI expectations and command patterns

### Planning and Memory Paths

- `plans/roadmap.md`: sequencing and milestone order
- `plans/XX-*.md`: active milestone plan files
- `memory/meta.md`: stable project facts worth preserving across tasks

## Task-to-Doc Map

Use the smallest relevant set of docs for the task at hand.

### Architecture and Scope

- [`docs/overview.md`](../docs/overview.md): product intent and system framing
- [`docs/scope.md`](../docs/scope.md): server vs client boundary and ownership
- [`docs/prd.md`](../docs/prd.md): requirements and acceptance-level product constraints

### API and Contract Work

- [`docs/api-contract.md`](../docs/api-contract.md): route behavior and public request/response contract
- `postman/collections/`: concrete request examples and manual validation flows

### Persistence and Discovery

- [`docs/schema.md`](../docs/schema.md): canonical schema shape and table responsibilities
- [`docs/storage-strategy.md`](../docs/storage-strategy.md): storage design decisions and tradeoffs
- [`docs/discovery-candidate-selection.md`](../docs/discovery-candidate-selection.md): discovery matching, filtering, ranking, and per-slug collapse

### Delivery History

- `docs/changelog/`: prior milestone delivery notes and architectural decisions already implemented

## Collaboration and Learning
- Keep Yonatan involved in non-trivial design and implementation decisions.
- Teach while building: explain relevant Python/FastAPI/backend concepts and
  system design tradeoffs in short, concrete terms.
- For non-trivial decisions, present options with pros, cons, and impact when
  the tradeoff is still open.
- Keep changes incremental and reviewable with clear test notes.

## Planning and Execution

- Work on one milestone plan file at a time under `plans/XX-*.md`.
- Do not start the next plan file before the current one meets its acceptance criteria.
- Keep plan files append-only. Do not renumber or rename completed plans.
- Every implementation PR should map to exactly one active plan file.
- When finishing work on a plan, review older changelogs and prior implementation work for logic conflicts, redundancy, and code that should now be removed.

## Large Change Workflow

Use this flow for large or cross-cutting changes, not only for net-new features.

1. Review the current code before implementation to detect conflicts, redundancy, and reusable existing code.
2. Implement the change with the active milestone plan in mind. Prefer replacement and cleanup over additive compatibility work.
3. Run `make lint`.
4. Run `make typecheck`.
5. Run `make test`.
6. Update the active milestone documentation for the effort by appending plan notes in the corresponding file under `plans/`.
7. Write or update the matching milestone changelog using `$changelog-writer`.

- Do not skip steps 3-7 for a large change unless the environment blocks them. If blocked, record the reason in the changelog or plan note.

## TDD Workflow

- Follow RED -> GREEN -> REFACTOR for non-trivial changes.
- Write or update failing tests first for new behavior.
- Implement the minimal change to pass tests.
- Refactor only with tests green and keep behavior unchanged.
- Include happy-path and failure-path coverage for each milestone.

## Documentation Preferences

- Keep docs concise, concrete, and synced with behavior.
- Before changing behavior, read the smallest relevant doc set from the task-to-doc map above.
- Update these files when relevant behavior changes:
  - `plans/plan-XX-*.md` for milestone scope or acceptance updates
  - `plans/roadmap.md` for sequencing changes
  - `memory/meta.md` for stable product or server facts
- For new APIs or payloads, document endpoint, request shape, response shape, and error cases.
- Document deterministic rules explicitly, including ordering, tie-breakers, and policy precedence.

## Module README Discipline
- Every module directory under `app/` must contain a `README.md`.
- If code changes in a module, update that module README in the same change.
- If a module is added, renamed, or removed, add/update/remove the corresponding README.
- Keep `app/README.md` updated as the index of module responsibilities.
