# Spectra architecture

Spectra is a modular observability workbench. Query adapters, semantic profiling, panel selection, alert transitions, and the canvas remain separate so additional data sources and visual plugins can be added without rewriting the application shell.

## Runtime topology

```text
                      ┌───────────────────────────────┐
Browser ── HTTP/WS ──▶│ FastAPI REST + WebSocket API   │
                      │ JWT/RBAC · ingest · dashboards│
                      └────────┬───────────┬──────────┘
                               │           │
                    ┌──────────▼──┐  ┌─────▼────────────────┐
                    │ Connector   │  │ Intelligence         │
                    │ Registry    │  │ Polars-compatible     │
                    │ DuckDB      │  │ Schema Profiler       │
                    │ Prometheus  │  │ Element Recommender   │
                    │ Postgres    │  │ NL Copilot            │
                    │ ClickHouse  │  └──────────────────────┘
                    │ Elastic     │
                    │ Event stream│
                    └────┬────────┘
                         │
     ┌───────────────────┼──────────────────────────┐
     ▼                   ▼                          ▼
 JSON/CSV/Parquet    Metrics / SQL          HTTP ingest & WS stream
 local data          external sources       telemetry simulator
                         │
                 ┌───────▼───────────────┐
                 │ React + TypeScript SPA│
                 │ Grid canvas / registry│
                 │ ECharts / D3 ecosystem│
                 └───────────────────────┘
```

## Request/data lifecycle

```text
Agent / simulator
       │ POST /api/v1/ingest (bounded batch)
       ▼
StreamConnector ──▶ bounded event buffer ──▶ WebSocket subscribers
       │                       │
       ▼                       └─▶ schema_profiler.profile()
DuckDB telemetry table                  │
       │                                 ├─▶ semantic column annotations
POST /api/v1/query                       └─▶ element_synthesizer.recommend()
       │                                                     │
       └─ read-only result rows + schema + recommendations ──┴─▶ Dashboard panels
```

## Main modules

- `backend/connectors/base.py`: connector contract, shared result object, common SQL read-only guard.
- `backend/connectors/`: embedded DuckDB, Prometheus HTTP API, PostgreSQL async pool, ClickHouse HTTP, Elasticsearch/OpenSearch Query DSL, bounded event stream.
- `backend/intelligence/schema_profiler.py`: bounded sampling, type and semantic inference, cardinality/null/statistics summaries, relationship discovery.
- `backend/intelligence/element_synthesizer.py`: confidence-ranked panel suggestions driven by semantic columns.
- `backend/intelligence/nl_copilot.py`: optional OpenAI-compatible chat endpoint; deterministic rule fallback is available with no model configured.
- `backend/alerting/engine.py`: threshold state machine, pending duration, firing/resolution and cooldown-protected generic webhook delivery.
- `backend/auth/rbac.py`: JWT roles and FastAPI dependencies. Anonymous requests are Viewer-only; edits require an authenticated Admin or Editor token.
- `frontend/src/elements/ElementRegistry.ts`: plugin map implementing one `PanelProps` contract.
- `frontend/src/components/DashboardCanvas.tsx`: grid, time controls, filters, export/import and live event subscription.

## Extension points

### Add a datasource

Implement `BaseConnector.query()`, return a `QueryResult`, and register the instance in `backend/main.py`. Put credentials in environment variables or a secrets manager; never check credentials into provisioning files.

### Add a visualization

Create a React component satisfying `PanelProps`, add its type to `ElementRegistry`, and use semantic config fields returned by the recommender. Dashboard JSON panel types are registry keys.

### Add deployment provisioning

Mount JSON/YAML dashboard files under `provisioning/dashboards/`. The API reads those files at startup/request time; use reviewed, trusted files only.

## Operational security notes

- Set unique `SPECTRA_JWT_SECRET`, bootstrap password and optional ingestion API key before exposing the service. Development defaults are not production credentials.
- SQL connectors accept a single read-only statement. The DuckDB adapter rejects mutating/admin statements and direct file/network table functions in user queries. External-file views are discovered only under `DATA_DIR`.
- Keep the API behind TLS and an identity-aware gateway in production; configure `CORS_ORIGINS` narrowly. Do not expose database ports to untrusted networks.
- In-memory event fanout is bounded and process-local. For HA/multi-worker delivery, replace it with a durable broker (e.g., NATS/Kafka/Redis Streams) and shared state.
- Scoped ingestion API keys are held in process memory, and tenant IDs are attached to ingested events. The reference storage/query path is not yet a complete tenant-isolation boundary; use separate instances or add tenant-enforced row policies before serving mutually untrusted tenants.
- The demo simulator is intentionally enabled by Compose and should not be used as a production traffic source.

## Current design boundary

This repository is a runnable reference implementation, not a claim of drop-in Grafana parity. OAuth/OIDC, tenant isolation across every storage adapter, durable alert state, full PromQL parsing, multi-node event delivery, advanced GeoIP enrichment, and production secret rotation require deployment-specific integration. LLM output must be reviewed before execution; arbitrary generated SQL is not auto-run by the service.
