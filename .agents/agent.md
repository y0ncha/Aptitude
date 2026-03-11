# Aptitude Agent Contract

## General Idea
Aptitude is a Python-based, execution-agnostic registry server for immutable
skills with deterministic dependency metadata contracts, explicit relationships,
policy governance, and auditable outcomes.

## Source and Instruction Files
1. Product and architecture intent: [`docs/overview.md`](../docs/overview.md)
2. Server/Resolver boundary contract: [`docs/scope.md`](../docs/scope.md)
3. Server product requirements: [`docs/prd.md`](../docs/prd.md)
4. Repo operating rules: [`rules/repo.md`](rules/repo.md)
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

## Collaboration and Learning (Mandatory)
- Keep Yonatan involved in non-trivial design and implementation decisions.
- Teach while building: explain relevant Python/FastAPI/backend concepts and
  system design tradeoffs in short, concrete terms.
- For non-trivial decisions, present options with pros, cons, and impact when
  the tradeoff is still open.
- Keep changes incremental and reviewable with clear test notes.

## Core Invariants
- Published skill versions are immutable.
- Resolver-side solving is deterministic for the same request, resolver version,
  and pinned registry state.
- Dependencies and relationships are explicit and typed.
- Governance and policy enforcement are centralized in the server.
- Server returns immutable metadata contracts and audit records; it does not
  return canonical solved bundles or execution plans.
- Layering dependency direction is strict:
  - `app/interface/**` may import only core-facing modules (not persistence).
  - `app/core/**` must not import persistence modules directly.
  - Persistence must be injected via core-defined ports/interfaces.
  - `app/main.py` is the composition root allowed to wire core to persistence.

## Module README Discipline
- Every module directory under `app/` must contain a `README.md`.
- If code changes in a module, update that module README in the same change.
- If a module is added, renamed, or removed, add/update/remove the corresponding README.
- Keep `app/README.md` updated as the index of module responsibilities.
