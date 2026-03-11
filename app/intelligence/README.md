# app.intelligence module

Pure ranking, normalization, and metadata helper functions.

## Purpose

Holds execution-agnostic intelligence helpers that core services can call
without taking on persistence or HTTP concerns.

## Current State

- `search_ranking.py`: query normalization, explanation generation, and audit-payload redaction for advisory search.
- Future metadata enrichment and relationship graph helpers should follow the same pure-function pattern.
