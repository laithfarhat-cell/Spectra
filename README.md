# Spectra

[![CI](https://github.com/laithfarhat-cell/Spectra/actions/workflows/ci.yml/badge.svg)](https://github.com/laithfarhat-cell/Spectra/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white) ![React](https://img.shields.io/badge/React-TypeScript-149ECA?logo=react) ![License](https://img.shields.io/badge/License-Apache--2.0-blue)

**Spectra** is an open-source observability and telemetry dashboard reference platform. It combines a Python FastAPI service, embedded DuckDB analytics, pluggable query connectors, semantic schema profiling and a React dashboard canvas with a live demo stream.

> Start the stack and a telemetry generator together with `docker compose up --build`. Open [http://localhost:8000](http://localhost:8000) to explore the live system overview.

## Highlights

- **Discover data automatically**: profile timestamps, metrics, counters, dimensions, trace IDs, IP/MAC/URL/CVE values, severity, geo pairs and source/target graph edges; emit percentiles, cardinality, null ratios and skew.
- **Auto-build dashboards**: rank panel recommendations from inferred semantics; optional OpenAI-compatible or local Ollama-compatible chat endpoint with a deterministic fallback.
- **Bring multiple sources**: DuckDB over configured local CSV/JSON/JSONL/Parquet files, Prometheus HTTP API (instant and range queries), PostgreSQL, ClickHouse, Elasticsearch/OpenSearch Query DSL, plus HTTP event ingestion and WebSocket fanout.
- **Explore and visualize**: draggable/resizable panels, time selection, template-variable chips, live events, topology, time series, log explorer, distribution view, KPI sparkline, sortable/filterable data and CSV/JSON export.
- **Operate with guardrails**: parameterized connector configurations, read-only SQL filtering, bounded ingestion/event buffers, JWT roles, one-time scoped ingestion API keys, alert state transitions, webhook notifications and dashboard provisioning.
- **Dashboards as code**: import/export dashboard JSON; provision trusted JSON/YAML under `provisioning/dashboards/`.

## Quick start

### Docker Compose (recommended)

```bash
# For any exposed/non-local deployment, set unique secrets first.
export SPECTRA_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export SPECTRA_BOOTSTRAP_PASSWORD='choose-a-strong-password'
docker compose up --build
```

The `demo-stream` service waits for the API health check and posts generated metrics, traces, application events and synthetic security activity. API/UI are served from port 8000. The DuckDB database and imported files persist in the `spectra-data` volume.

For local-only exploration, the compose defaults allow the read-only demo UI to run without setting up credentials. Do **not** expose those development defaults publicly. Optional settings include `SPECTRA_INGEST_API_KEY`, `PROMETHEUS_URL`, `DATABASE_URL`, `CLICKHOUSE_URL`, `ELASTICSEARCH_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.

### Local development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Separate terminal
cd frontend
npm ci
npm run dev
```

Vite serves at `http://localhost:5173` and proxies `/api` and WebSocket requests to the FastAPI service. The server-side proxy target is configured in `frontend/vite.config.ts`.

## API quick tour

```bash
# Service health and in-memory event count
curl http://localhost:8000/api/v1/health

# Ingest ECS/OTel-style records (SPECTRA_INGEST_API_KEY optional in local mode)
curl -X POST http://localhost:8000/api/v1/ingest \
  -H 'content-type: application/json' \
  -d '{"events":[{"kind":"log","timestamp":1732100000,"service":"checkout","severity":"warning","message":"slow request","latency":825}]}'

# Query locally ingested telemetry (single read-only SQL statement)
curl -X POST http://localhost:8000/api/v1/query \
  -H 'content-type: application/json' \
  -d '{"datasource":"duckdb","query":"SELECT service, quantile_cont(latency, 0.95) AS p95 FROM telemetry GROUP BY service"}'

# Connect a WebSocket client to /api/v1/ws/stream
```

See `/docs` for the OpenAPI schema. Useful routes include `/api/v1/profile`, `/api/v1/copilot/generate`, `/api/v1/dashboards`, `/api/v1/alerts`, and `/api/v1/auth/token`.

## Datasource query forms

- `duckdb`: read-only SQL, with a `telemetry` table for ingested records and files mounted below `DATA_DIR` exposed as views named after the file.
- `postgres`, `clickhouse`: read-only SQL.
- `prometheus`: PromQL string; provide optional `start`, `end`, `step` query options for range queries.
- `elasticsearch`: JSON Query DSL string, read-only `_search` calls.
- `stream`: event buffer. The `/api/v1/stream` endpoint is convenient for recent records.

Connector credentials and URLs are environment-driven. Undefined optional sources may show unavailable in connector health; that does not prevent the embedded demo from running.

## Comparison (scope of this reference implementation)

| Capability | Spectra reference | Grafana |
|---|---|---|
| Dashboard canvas and JSON import/export | Included | Included |
| Common datasource families | DuckDB, Prometheus, PostgreSQL, ClickHouse, Elasticsearch/OpenSearch, event stream | Broad plugin ecosystem |
| Automatic semantic profiling and panel ranking | Included; deterministic heuristics | Typically configured per datasource/panel |
| Live event fanout | WebSocket; bounded, process-local buffer | Datasource/live-stream dependent |
| Alert rules | In-process threshold state machine + generic webhook | Mature managed/distributed alerting options |
| User access | JWT role dependencies; bootstrap flow | Mature teams, SSO and policy integrations |
| Enterprise scale / HA | Bring an external broker, identity provider and shared state | Mature deployment options |

Spectra prioritizes semantic discovery and a hackable open architecture; it is not yet a feature-complete or drop-in replacement. See [ARCHITECTURE.md](ARCHITECTURE.md) for deployment limits and extension guidance.

## Development & tests

```bash
.venv/bin/pytest -q
(cd frontend && npm ci && npm run build && npm test)
```

The Python suite exercises profiler inference and recommendations; Vitest checks the panel registry. CI runs backend tests and frontend build/tests on pushes and pull requests.

## License

Apache License 2.0. See [LICENSE](LICENSE).
