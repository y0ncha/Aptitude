# Plan 07 — Evaluation and Repo State Reproducibility

## Goal
Add evaluation signals and repository state snapshots so ranking can evolve without breaking reproducibility.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Job execution: APScheduler (MVP), Celery + Redis for scale

## Scope
- Add evaluation run lifecycle and result storage.
- Normalize results to metadata quality score.
- Add `repo_state_id` snapshot creation.
- Support resolution pinned to snapshot state.

## Architecture Impact
- Connects intelligence signals to the core resolver while preserving deterministic replay.
- Extends the audit trail for evaluation-driven metadata changes.

## Deliverables
- Endpoint: `POST /v1/evaluations/runs`.
- Endpoint: `GET /v1/evaluations/runs/{run_id}`.
- Endpoint: `GET /v1/repo-states/{repo_state_id}`.
- Tables for evaluation runs, results, and repo state snapshots.
- Resolver support for pinned `repo_state_id`.
- Learning note on mutable signals over immutable artifacts.

## Acceptance Criteria
- Evaluation updates metadata but not artifact content or checksum.
- Pinned `repo_state_id` produces stable bundle and report outputs.
- Unpinned latest-state resolution can change only via documented signals.

## Test Plan
- Integration test that runs evaluation and verifies metadata update path.
- Determinism test with pinned state across repeated resolutions.
- Differential test for latest state vs pinned state behavior.
- Audit test that evaluation and snapshot events are fully recorded.
