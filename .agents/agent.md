# Aptitude Agent Contract

## General Idea
Aptitude is a Go-based, execution-agnostic repository for immutable skills with deterministic dependency resolution, explicit relationships, policy governance, and auditable outcomes.

## Source and Instruction Files
1. Product and architecture intent: [`docs/overview.md`](../docs/overview.md)
2. Repo operating rules: [`rules/repo.md`](rules/repo.md)
3. Roadmap and sequencing: [`plans/roadmap.md`](plans/roadmap.md)
4. Plan execution files: `plans/XX-*.md` (append-only milestones)
5. Stable repo facts: [`memory/meta.md`](memory/meta.md)
6. Skills for TDD and pyhton + FastAPI back-end + Postgres best practices: [`skills`](skills/)

If rules conflict, follow the highest item unless the repository includes a newer explicit architecture decision.

## Collaboration and Learning (Mandatory)
- Keep Yonatan involved in non-trivial design and implementation decisions.
- Teach while building: explain relevant Go concepts and system design tradeoffs in short, concrete terms.
- For non-trivial decisions, always present at least two design options with pros, cons, and impact.
- Ask explicitly which option Yonatan prefers before locking the approach.
- Keep changes incremental and reviewable with clear test notes.

## Core Invariants
- Published skill versions are immutable.
- Resolution is deterministic for the same request and repository state.
- Dependencies and relationships are explicit and typed.
- Governance and policy enforcement are centralized in the repository.
- Resolution decisions remain explainable through `ResolutionReport` and audit records.
