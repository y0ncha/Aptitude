# Aptitude Scope: Server vs Client

## Purpose

This document defines the hard boundary between `aptitude-server` and the
client-side `aptitude-client`.

The boundary exists for two reasons:

1. High-performance discovery should happen close to the indexed metadata.
2. Agentic selection and dependency solving should stay close to user intent,
   runtime context, and lock generation.

In short:

- `aptitude-server` is the registry and retrieval system.
- `aptitude-client` is the client-side decision and execution-planning system.

## Architectural Rule

Use this rule consistently:

- Server owns data-local work.
- Client owns decision-local work.

Data-local work means operations that are fastest and cheapest when executed
near the database or search index, such as metadata filtering, full-text
lookup over descriptions, and exact version retrieval.

Decision-local work means operations that depend on prompt intent, environment,
policy, user preferences, installed state, lock semantics, or runtime
constraints, such as reranking, final selection, dependency solving, and
execution planning.

## Ecosystem Analogy

- `aptitude-server` = package registry / catalog service (PyPI, npm registry, Maven repository role).
- `aptitude-client` = package manager / client runtime (pip, npm client, Maven client role).

The registry stores immutable packages and searchable metadata.
The client decides what to use and how to compose it.

## Design Goals

- Keep `GET /skills/search` fast for metadata + description search.
- Prevent agents from scanning the entire catalog client-side.
- Preserve immutable, cache-friendly fetches for exact `(skill_id, version)` reads.
- Keep prompt interpretation and final selection outside the server so the
  search API remains stable, scalable, and easy to cache.
- Allow client policy and ranking logic to evolve independently of registry
  storage and indexing logic.

## Agentic Search Definition

Agentic search is the workflow where an AI agent or client:

1. interprets a user request,
2. converts it into structured search criteria,
3. retrieves candidate skills from the registry,
4. reranks those candidates using task context,
5. selects versions,
6. resolves dependencies,
7. produces a lock and execution plan.

The server supports agentic search by exposing fast, indexed discovery
primitives. The server does not perform the agent's reasoning or final choice.

## Ownership Matrix

| Capability | Server Owner | client Owner | Notes                                                              |
| --- | --- |--------------|--------------------------------------------------------------------|
| Immutable artifact storage | Yes | No           | Registry source of truth                                           |
| Publish validation and provenance enforcement | Yes | No           | Includes integrity, schema, trust, lifecycle checks                |
| Version metadata storage | Yes | No           | Manifest and derived metadata are registry concerns                |
| Search index maintenance | Yes | No           | Includes full-text, metadata filters, and denormalized read models |
| Metadata + description candidate retrieval | Yes | No           | Must happen close to indexes for low latency                       |
| Deterministic base search ranking | Yes | No           | Advisory ranking only; no runtime solve semantics                  |
| Search response explanation fields | Yes | No           | Helps clients understand why a result matched                      |
| Prompt interpretation | No | Yes          | User request normalization belongs to the client                   |
| Query construction from prompt/context | No | Yes          | Client translates intent into `q`, filters, limits, and sort hints |
| Personalized or context-aware reranking | No | Yes          | Depends on workspace, org policy, current task, installed state    |
| Final candidate selection | No | Yes          | Server returns candidates, not the final answer                    |
| Dependency metadata storage per version | Yes | No           | Direct declarations are published metadata                         |
| Canonical dependency graph traversal | No | Yes          | Built per request by the client                                    |
| Deterministic dependency solving algorithm | No | Yes          | Versioned and traceable in the client                              |
| Lock generation and replay | No | Yes          | Runtime reproducibility belongs to the client                      |
| Runtime execution planning | No | Yes          | Converts locked skills into an executable plan                     |
| Server-side governance at publish/read boundary | Yes | Partial      | client may add stricter runtime gates                              |
| Local search/result caching | No | Yes          | Client may keep short-lived request-local or session-local caches  |
| Catalog snapshotting for stable reads | Yes | Partial      | Server exposes stable index state; client chooses when to pin it   |
| Audit of publish/read lifecycle events | Yes | Partial      | client separately audits local decisions and executions            |

## Search and Resolution Flow

### Discovery Flow for Fast Agentic Search

1. User or agent submits a prompt to the client.
2. client extracts search intent:
   `q`, tags, language, trust tier, lifecycle visibility, freshness, and other filters.
3. client calls the registry discovery API.
4. Server executes indexed retrieval over:
   - name
   - description
   - tags
   - structured metadata
   - lifecycle and trust filters
5. Server returns a compact candidate set with stable ordering and explanation fields.
6. client reranks or prunes that candidate set using runtime context.
7. client fetches exact version details for chosen candidates.
8. client performs dependency expansion, conflict handling, and lock generation locally.

### Exact Fetch and Execution Flow

1. client selects concrete `(skill_id, version)` coordinates.
2. client fetches immutable metadata and artifact identity from the server.
3. client verifies checksums, expands dependencies, and builds a lock.
4. client produces the execution plan and trace output.

## What the Server Must Do

- Expose stable APIs for publish, fetch, list, and search.
- Maintain searchable indexes for metadata and descriptions.
- Support deterministic candidate retrieval with stable tie-breaks.
- Return compact search results so clients do not over-fetch full manifests
  during discovery.
- Serve exact immutable version records and artifact identity for selected versions.
- Enforce publish/read governance and lifecycle visibility.
- Optionally maintain denormalized read models and secondary indexes when they
  improve query performance, as long as they do not become the source of truth
  for resolution outcomes.

## What the Server Must Not Do

- Parse end-user prompts to decide which skill is best.
- Run LLM inference in the critical search path.
- Return canonical solved bundles or dependency closures as the source of truth.
- Own lock generation, plugin execution, runtime scoring, or execution planning.
- Require clients to understand server internals, tables, or storage layout.

## What the client/Client Must Do

- Own the main user entrypoint: MCP, CLI, SDK, or agent runtime.
- Interpret prompts and convert them into structured search requests.
- Use registry search as candidate generation, not as final decision making.
- Apply local policy, installed-state awareness, environment constraints, and
  task context to rerank or filter candidates.
- Fetch exact metadata for finalists and resolve dependencies recursively.
- Generate deterministic lock output with traceable decision records.
- Execute or hand off an execution plan outside the registry.

## What the client/Client Must Not Do

- Read or write server databases directly.
- Rebuild the full catalog by crawling every manifest for routine discovery.
- Treat server advisory ranking as final authority.
- Depend on undocumented internal tables or denormalized search read models.

## Performance Rationale

This separation is required for speed and scalability.

### Why search belongs on the server

- Search over metadata + description is an indexed retrieval problem.
- Running it on the server avoids shipping large catalogs to clients.
- Server-side retrieval can use PostgreSQL full-text indexes, trigram indexes,
  metadata indexes, and later a dedicated search engine without changing the
  client contract.
- Search results become cacheable and horizontally scalable at the API layer.

### Why final selection belongs on the client

- Final selection depends on prompt nuance, local policy, installed toolchain,
  previous choices, workspace context, and dependency-solving strategy.
- These inputs are not registry state and should not be embedded into registry
  request handlers.
- Keeping selection in the client prevents server coupling to agent behavior
  and avoids turning discovery endpoints into expensive, low-cacheability RPCs.

### Why dependency solving belongs on the client

- Solving is iterative and context-sensitive.
- Different client versions may intentionally use different policies or tie-breaks.
- Runtime reproducibility must be tied to a lock generated by the client,
  not to a mutable server-side solve result.

## API and Contract Expectations

### Server APIs

The server must expose registry-oriented contracts such as:

- `POST /skills/publish`
- `GET /skills/{id}/{version}`
- `GET /skills/{id}`
- `GET /skills/search`
- Optional governance endpoints (`deprecate`, `archive`, `trust/admin`)

`GET /skills/search` should be designed for candidate generation, not final
decision making. It should accept textual search and structured filters, and it
should return stable ordering plus ranking explanation hints.

### client APIs

The client owns the user-facing orchestration surface, such as:

- `resolve_and_plan` via MCP
- `aptitude resolve "<prompt>"` via CLI
- SDK methods that combine search, reranking, solve, lock, and execution planning

The client output should include:

- selected skills and versions
- lock hash
- client version
- decision trace
- plugin/policy decisions
- execution plan

## Boundary Rules (Hard)

- client cannot read or write server DB tables or private services directly.
- Server cannot be the source of truth for runtime dependency resolution outcomes.
- Search retrieval on metadata and descriptions belongs to the server.
- Prompt interpretation, reranking, and final selection belong to the client.
- Server ranking is advisory; client choice is authoritative.
- Reproducibility is lock-based: production executions must use client lock output.
- Any client policy or scoring that changes selected versions must be explicit
  and recorded in client trace output.
- Denormalized search indexes and read models are allowed on the server, but
  they must remain derived data, not canonical resolution state.

## Non-Goals

- Building a monolith that couples registry persistence, prompt interpretation,
  search reasoning, and runtime orchestration.
- Reintroducing server-side canonical graph solving as an MVP dependency.
- Forcing clients to crawl the full catalog to search by description or metadata.
- Allowing plugins or client heuristics to silently mutate lock results
  without trace evidence.
- Making the registry responsible for personalized or environment-specific tool choice.

## Assumptions to Validate

- Initial target scale: up to 10k skills and up to 200 nodes in resolved lock sets.
- Search p95 should stay low enough that agent workflows can use registry search
  as an interactive primitive rather than a batch job.
- client plugin budget target: <= 150 ms median overhead per plugin.
- client versions are pinned per environment to control drift.
