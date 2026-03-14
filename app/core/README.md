# app.core module

Core domain logic and cross-layer contracts.

## Purpose

Defines business behavior for immutable skill catalog operations and the ports
that infrastructure layers implement.

## Key Files

- `skill_registry.py`: immutable publish/status service + shared domain errors/models.
- `skill_discovery.py`: discovery service facade for ordered candidate slug retrieval.
- `skill_resolution.py`: exact direct dependency read service for authored `depends_on` selectors.
- `skill_fetch.py`: immutable metadata and markdown batch fetch service.
- `skill_search.py`: advisory search query/result models and implementation reused by discovery.
- `ports.py`: protocol contracts for publish, exact version reads, relationship reads, discovery, artifacts, audit, and readiness.
- `dependencies.py`: FastAPI dependency providers and typed aliases
  (`SettingsDep`, `ReadinessServiceDep`, `SkillRegistryServiceDep`, `SkillDiscoveryServiceDep`, `SkillResolutionServiceDep`, `SkillFetchServiceDep`) that read process-scoped services from `request.app.state`.
- `readiness.py`: readiness domain service and report models.
- `settings.py`: typed environment configuration.
- `logging.py`: centralized logging config for application and `uvicorn.*` loggers.

## Boundaries

- Core must not import persistence implementations directly.
- Persistence and audit adapters implement core-defined protocols.
- Core publishes immutable manifest metadata but does not solve dependency
  graphs, generate locks, or build execution plans.
- Core discovery remains candidate retrieval only; ranking is advisory and not authoritative for resolver choice.
- Core resolution returns only direct authored dependency selectors; no transitive traversal or solving belongs here.
- Core fetch composes PostgreSQL-backed metadata and markdown reads in ordered batches.
- Logging configuration is defined once in core and reused by runtime entrypoints.
- Dependency providers in `dependencies.py` assume startup has initialized
  the process-scoped services stored under `app.state`.
