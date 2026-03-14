# Plan 12 - Optional Evaluation Signals and Snapshotting

## Goal
Leave room for post-launch discovery improvements through derived evaluation signals while keeping the hard-cut MVP contract simple and treating snapshot APIs as optional follow-up work rather than baseline obligations.

## Positioning
This milestone is post-launch and optional. It is not part of MVP readiness, read-contract reset, contract freeze, or release hardening.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Background execution: APScheduler for simple runs, with queue-backed workers only if scale proves necessary

## Scope
- Add derived evaluation signals only if they materially improve `POST /discovery` over the slug-only baseline from Plan 07.
- Keep evaluation outputs limited to mutable derived metadata used for advisory retrieval and ranking support.
- Treat catalog snapshots as deferred and trigger-based, not as a default roadmap commitment.
- If evaluation signals are exposed, add them inside the existing `POST /discovery` request or response shape rather than by creating new public discovery route families.
- If snapshotting is justified, represent snapshot selection within the existing discovery or batch-fetch contract by default instead of creating separate public snapshot route trees.
- Keep all evaluation and snapshot work separate from canonical dependency declarations, immutable metadata/content fetch, and digest-backed content storage.
- Preserve the hard server/client boundary: no server-side solving, final candidate selection, lock generation, or execution planning.
- Do not reintroduce deleted route families or alternate single-item fetch surfaces as part of this optional work.

## Trigger Criteria
- Discovery quality issues cannot be addressed with the existing slug-only candidate baseline and deterministic base ranking alone.
- Real consumers need auditable, pinned latest-state discovery views in addition to immutable exact coordinates.
- Operational evidence shows evaluation-derived metadata changes are frequent enough that snapshotting materially improves debugging, reproducibility, or audit workflows.

## Architecture Impact
- Keeps future discovery enhancements decoupled from core registry correctness.
- Prevents speculative features from turning into MVP obligations.
- Protects resolution and batch fetch semantics from being entangled with mutable derived metadata.

## Deliverables
- Derived evaluation run model and result storage only if trigger criteria are met.
- Discovery extension rules limited to the existing `POST /discovery` contract.
- Optional snapshot design note describing how pinned latest-state views fit into the existing endpoint surface when justified.
- Documentation note stating that exact coordinates and client-generated locks remain the default reproducibility mechanism.

## Acceptance Criteria
- If implemented, evaluation updates derived metadata only and never mutates immutable version identity, dependency declarations, metadata snapshots, or content payloads.
- Snapshot APIs are not added unless one or more trigger criteria are explicitly satisfied.
- Resolution and batch fetch remain independent of evaluation state and snapshot state.
- The milestone remains clearly marked optional and post-launch in roadmap and plan language.
- No part of the plan reintroduces deleted route families, single-item fetch, or server-side solving semantics.
- Optional discovery work keeps the public endpoint surface simple and does not create new public route families when existing requests can carry the needed state.

## Test Plan
- Integration test verifying evaluation-derived metadata updates do not affect resolution or immutable fetch behavior.
- Determinism test proving exact coordinate fetch stays stable regardless of evaluation state.
- If snapshots are introduced, repeated reads against a pinned snapshot return stable discovery results for the same request body.
- Audit test covering evaluation and snapshot events when those features are enabled.
