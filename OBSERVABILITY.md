# AgentBanking / POS54 — Platform Observability

Canonical documentation for the OpenTelemetry-based observability stack delivered on
branch `fix/observability-round4`. It covers the collector-centric architecture, the
per-tenant telemetry contract, component coverage, the alert catalog and routing, and
runbooks for the highest-severity alerts.

This document describes what is **actually on the branch**. Code and configuration were
delivered and statically verified; the runtime stack is provisioned externally. See
[Verification status and honest gaps](#verification-status-and-honest-gaps) before
treating any metric name or alert expression as production-confirmed.

---

## Architecture

All telemetry converges on a single OpenTelemetry Collector
(`infra/observability/otel/otel-collector-config.yaml`, image
`otel/opentelemetry-collector-contrib:0.129.0`). Prometheus scrapes **only** the
collector's aggregated Prometheus exporter (`:8889`, namespace `pos54`) plus the
observability stack's own endpoints — middleware targets are scraped *inside* the
collector.

```
                          OTLP gRPC :4317 / OTLP HTTP :4318
 ┌──────────────────────────────────────────────────────────────────────┐
 │  SERVICES (in-process instrumentation)                               │
 │   TS api-server (NodeSDK, OTLP/HTTP)                                 │
 │   Go services   (shared/middleware/otel.go, OTLP/HTTP traces+metrics)│
 │   Python svcs   (shared/observability.py, OTLP/HTTP traces+metrics)  │
 │   Rust services (rust/otel-common, OTLP/tonic traces)                │
 │   APISIX (opentelemetry plugin → :4318)  Keycloak HA (→ :4317 gRPC)  │
 │   Permify (native OTLP → :4317)                                      │
 └───────────────┬──────────────────────────────────────────────────────┘
                 │ OTLP                                   Zipkin :9411 (Dapr 1.11 bridge)
                 ▼                                          ▲
        ┌─────────────────┐   prometheus receiver scrapes  │
        │  OTEL COLLECTOR │◄── apisix:9091, keycloak, permify:3476,
        │                 │    temporal:9090, minio, opensearch:9200,
        │  processors:    │    fluvio:9003, mojaloop x4, spark:4040,
        │   memory_limiter│    app:3000/api/metrics, middleware :8090-8093
        │   resourcedetect│   kafkametrics / postgresql / redis / hostmetrics
        │   transform/    │            ▲
        │     tenant      │────────────┘ (span attr tenant.id → resource attr)
        │   redact        │
        │   batch         │
        │  connector:     │── spanmetrics (dims: tenant.id, http.status_code)
        │   spanmetrics   │
        └──┬────┬────┬────┘
  prom :8889 │    │    │ otlp/tempo :4317        │ loki push
  (pos54_*)  │    │    ▼                         ▼
             ▼    │ ┌───────┐                ┌──────┐
       ┌──────────┐││ TEMPO │ traces         │ LOKI │ logs
       │PROMETHEUS││└───┬───┘                └──┬───┘
       │ + rules  ││    │                       │
       └──┬───┬───┘│    │                       │
          │   │    │    ▼                       ▼
          │   │    │  ┌───────────────────────────────┐
          │   └──┐ └──► GRAFANA 11.6.1 (provisioned)  │
          │      │    │  DS: Prometheus / Tempo        │
          ▼      │    │      (tracesToLogs→Loki,       │
   ┌─────────────┐│   │       serviceMap→Prometheus)   │
   │ ALERTMANAGER││   │      / Loki / Alertmanager     │
   │  severity + ││   │  Dashboards: platform-otel-    │
   │  team +     ││   │   overview, funds-flow-slo,    │
   │  tenant_id  ││   │   tenant-overview              │
   └──────┬──────┘│   └───────────────────────────────┘
          ▼       │
   ntfy-critical / ntfy-funds / ntfy-ops / ops-webhook
```

Key properties:

- **Traces**: OTLP (gRPC + HTTP) and Zipkin receivers → `memory_limiter →
  resourcedetection → transform/tenant → attributes/redact → batch` → exported to
  **Tempo** (local storage) and to the **spanmetrics connector** (RED metrics with
  dimensions `tenant.id` and `http.status_code` — exported Prometheus labels become
  `tenant_id` / `http_status_code`; `service_name` is automatic).
- **Metrics**: OTLP + Prometheus scrape of all middleware + `kafkametrics`,
  `postgresql`, `redis`, `hostmetrics` receivers + spanmetrics connector → Prometheus
  exporter on `:8889` with namespace `pos54`.
- **Logs**: OTLP logs pipeline → **Loki** (`http://loki:3100/loki/api/v1/push`).
- **Alerts**: Prometheus evaluates `infra/observability/prometheus/rules/*.rules.yml`
  and fires into **Alertmanager**, which routes by severity/team/tenant to ntfy topics
  and a placeholder ops webhook.
- The collector `attributes/redact` processor deletes `authorization`, `password`,
  `secret`, and `token` span attributes before anything leaves the collector.

---

## How to run

### Docker Compose (canonical stack)

The observability stack is a compose overlay on the root platform compose. It joins
the shared `54link-network` created by the root compose, so **start the platform
first** (or at least create the network).

```bash
# Required environment (fail-closed — startup aborts without these):
export GRAFANA_ADMIN_PASSWORD='...'   # Grafana admin password (no default)
export POSTGRES_PASSWORD='...'        # collector postgresql receiver credential

docker compose -f docker-compose.yml \
  -f infra/observability/docker-compose.observability.yml up -d
```

Optional overrides: every scrape target is env-overridable (`*_METRICS_TARGET`),
plus `TEMPO_ENDPOINT`, `LOKI_ENDPOINT`, `KAFKA_BROKERS`, `POSTGRES_ENDPOINT`,
`POSTGRES_USER`, `REDIS_ENDPOINT`, `SMTP_*`, `NTFY_TOKEN_*`.

Host ports (deliberately distinct from the legacy root-compose `monitoring` profile):

| Service      | Host port | Container port | Purpose                        |
|--------------|-----------|----------------|--------------------------------|
| prometheus   | 19090     | 9090           | metrics query / alerts         |
| grafana      | 13000     | 3000           | dashboards                     |
| tempo        | 13200     | 3200           | trace query API                |
| alertmanager | 19093     | 9093           | alert routing UI/API           |
| loki         | 13100     | 3100           | log query API                  |
| ntfy         | 18080     | 80             | alert push topics              |

Container images: `otel/opentelemetry-collector-contrib:0.129.0`,
`grafana/tempo:2.8.0`, `prom/prometheus:v3.2.1`, `prom/alertmanager:v0.28.1`,
`grafana/grafana:11.6.1`, `grafana/loki:3.2.1`, `binwiederhier/ntfy:v2.11.0`.

Service ports on `54link-network`: collector OTLP gRPC `4317`, OTLP HTTP `4318`,
Zipkin `9411`, aggregated Prometheus exporter `8889`.

### Kubernetes

`k8s/observability/otel-collector.yaml` deploys the same canonical collector
(image `0.129.0`, same config, Zipkin `9411` added as a service port) with the
trace exporter pointed at the in-cluster Tempo (`tempo.pos-shell.svc:4317`).
Apply it alongside the platform manifests; Prometheus/Tempo/Grafana deployment in
k8s is out of scope for this round.

### Application-side enablement

Every instrumented service is **env-gated** — nothing changes at runtime until an
OTLP endpoint is provided:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318   # TS / Go / Python (OTLP/HTTP)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317   # Rust (OTLP/tonic gRPC)
# optional: OTEL_SERVICE_NAME, OTEL_SERVICE_VERSION, ENVIRONMENT
```

Without the endpoint, TS/Rust tracing and Python OTel export are no-ops; Prometheus
`/metrics` endpoints and tenant middleware remain active regardless.

---

## Per-tenant telemetry design

Tenant attribution is a cross-language contract. Every hop uses W3C
`tracecontext` + `baggage` propagation, with the tenant id carried as baggage key
`tenant.id`:

```
 client --[x-tenant-id header]--> edge service
   1. middleware reads header (default "unknown")
   2. sets baggage tenant.id + span attribute tenant.id
   3. baggage propagates downstream on every outgoing call (W3C Baggage)
 collector
   4. transform/tenant processor copies span attribute tenant.id
      onto the RESOURCE (resource.attributes["tenant.id"],
      defaults to "unknown" when absent)
   5. spanmetrics connector aggregates with dimension tenant.id
 prometheus
   6. label sanitization: tenant.id → tenant_id on
      calls_total / duration_milliseconds_* series;
      resource_to_telemetry_conversion also surfaces resource attrs
 grafana / alertmanager
   7. tenant-overview dashboard template var + per-tenant alert
      grouping (group_by: [alertname, severity, tenant_id])
```

Per-language implementation (all equivalent, all defaulting to `"unknown"`):

| Language | Component | Mechanism |
|----------|-----------|-----------|
| TypeScript | `services/api-server-ts/server/middleware/tenantTelemetry.ts` | Express middleware: `x-tenant-id` → `propagation.createBaggage({tenant.id})` + active-span attribute; `getTenantIdFromContext()` for crons |
| Go | `services/shared/middleware/otel.go` | `TenantIDFromRequest` (`X-Tenant-ID`), `ContextWithTenant`/`TenantIDFromContext` (baggage), `OTelHTTPMiddleware` stamps `tenant.id` span attribute |
| Python | `services/shared/observability.py` → `TenantContextMiddleware` | `x-tenant-id` → `baggage.set_baggage("tenant.id", …)` + span attribute; import-safe pass-through without OTel installed |
| Rust | `services/rust/otel-common` | `tenant_id_from_headers()` + `record_tenant_span_attr()`; axum/warp middleware per service |

Business metrics carry a `tenant` label directly (`funds_flow_operations_total`,
`ledger_imbalance_detected_total`, `settlement_lag_seconds`, `payments_failed_total`)
so per-tenant alerting does not depend on span attribution alone.

**Tempo per-tenant note**: `infra/observability/tempo/tempo.yaml` ships with
`overrides: defaults: {}` plus a commented `per_tenant_override_config` example —
per-tenant ingestion rate limits / max trace size can be enabled by mounting an
overrides file; retention in Tempo is enforced per-tenant, not globally.

---

## Component coverage matrix

Honest status as of this branch. "Wired" = instrumentation code/config present on
`fix/observability-round4`. It does **not** imply runtime verification.

| Component | Coverage | Details |
|---|---|---|
| **api-server-ts** (`services/api-server-ts`) | ✅ Full: traces + metrics + business metrics | `server/_core/telemetry.ts`: NodeSDK, OTLP/HTTP traces, W3C tracecontext+baggage, resource `service.name/version/deployment.environment.name`, env-gated, `getTracer` export; imported as **first static import** in `server/_core/index.ts` so auto-instrumentation hooks express/pg/ioredis/kafkajs. `server/middleware/tenantTelemetry.ts` tenant baggage. `server/metrics.ts` prom-client registry incl. canonical `funds_flow_operations_total{operation,service,tenant,status}`, `ledger_imbalance_detected_total{ledger,tenant}`, `settlement_lag_seconds{tenant}` (buckets 1,5,15,60,300,900,3600), `payments_failed_total{service,tenant,reason}` + `recordFundsFlowOperation`; `server/settlementCron.ts` records cycle duration + success/error. Endpoint `GET /api/metrics` (scraped as job `pos-shell-app`, also directly by Prometheus). |
| **Go services** | ⚠️ Partial: shared middleware complete; 2 services wired | `services/shared/middleware/otel.go`: `InitTelemetry` (traces + OTLP/HTTP metrics, 30s PeriodicReader), tenant helpers, `OTelHTTPMiddleware` tenant stamping; previous API preserved. Wired: `services/gateway-service`, `services/tigerbeetle-core` (otelMiddleware, `/metrics` via promhttp, `WithInsecure` + warn when endpoint unset). TigerBeetle's legacy `/api/v1/metrics` JSON endpoint kept with a DEPRECATED comment. ~100 other Go services need the same 3-line pattern (see [gaps-and-followups](docs/observability/gaps-and-followups.md)). |
| **Python services** | ⚠️ Partial: shared module + 5 services wired | `services/shared/observability.py` (and identical `services/loyalty-service/shared/observability.py`): `init_observability(app, name, version)` — env-gated OTLP traces+metrics, guarded FastAPI/Requests/SQLAlchemy/Redis instrumentors, `TenantContextMiddleware`, prometheus_client canonical business metrics, `/metrics` route; never raises, import-safe without otel. Wired: payment-processing-service (funds-flow hooks in `api/transfers.py` withdraw/deposit/settlement_payout; `/metrics` added to RequiredHeadersMiddleware excludes), cips-integration, papss-integration, python/auth-service (also fixed a pre-existing NameError — no FastAPI app existed), ai-ml-services. |
| **Rust services** | ⚠️ Partial: new shared crate + 4 services wired | NEW `services/rust/otel-common`: `init_tracing` (env-gated OTLP/tonic + EnvFilter/fmt + OpenTelemetryLayer), `OtelGuard`, `tenant_id_from_headers`, `record_tenant_span_attr`, `metrics_handle` (prometheus text), `register_business_metrics` (`funds_flow_operations_total`, `payments_failed_total`). Wired: fraud-engine, tx-validator, ledger-bridge (axum `/metrics` + tenant middleware + business counters on score/validate/transfer), fluvio-consumer (warp `/metrics` now prometheus text; `payments_failed_total` on forward failure). ~85 other crates pending. |
| **Kafka** | ✅ Metrics | `kafkametrics` receiver (KRaft has no JMX exporter): brokers/topics/consumers scrapers against `kafka:9092`. |
| **Dapr** | ✅ Traces via Zipkin bridge | Dapr 1.11 supports only the Zipkin exporter → `infra/dapr/config.yaml` + HA config repoint to `http://otel-collector:9411/api/v2/spans`; collector zipkin receiver converts to OTLP. Upgrade Dapr for native OTLP (see gaps). |
| **Fluvio** | ✅ Metrics + consumer tracing | Collector scrapes SC `fluvio:9003/metrics`; `services/rust/fluvio-consumer` emits OTLP traces + prometheus `/metrics`. |
| **Temporal** | ✅ Server metrics; ⚠️ SDK traces TODO | Server prometheus on `temporal:9090` (HA dynamic-config: `timerType: histogram`, `listenAddress: 0.0.0.0:9090`); collector job `temporal`. SDK interceptors (Go/Python/TS) not yet instrumented — next layer. |
| **Postgres** | ✅ Metrics | Collector `postgresql` receiver (`postgres:5432`, `POSTGRES_PASSWORD` required) + existing python postgres-exporter scrape (`postgres-production:9090`). |
| **Keycloak** | ✅ Traces + metrics | HA (v26): native `KC_TELEMETRY_*` gRPC → `otel-collector:4317` on both nodes; metrics on management port 9000 (job `keycloak-ha`). Root-compose v24: legacy `/metrics` scrape (job `keycloak`, port 8080). |
| **Permify** | ✅ Full | NEW `infra/permify/permify-config.yaml`: native OTLP tracer + meter → `otel-collector:4317`; metrics scrape `permify:3476/metrics`. |
| **Redis** | ✅ Metrics | Collector `redis` receiver (`redis:6379`). |
| **Mojaloop** | ✅ Metrics | Prometheus `/metrics` scrape of ml-api-adapter:3000, account-lookup:4002, central-ledger-1:3001, central-settlement:3007. |
| **OpenSearch** | ✅ Metrics | `_prometheus/metrics` scrape (`opensearch-node-1:9200`, 30s). |
| **OpenAppSec** | ❌ GAP | No native OTel support. k8s CRD logs ship to `opensearch:5140`; best-effort log correlation only. See gaps doc. |
| **APISIX** | ✅ Full | Native `opentelemetry` plugin + `plugin_attr` → `http://otel-collector:4318` (root + HA configs; HA zipkin plugin removed); `prometheus` plugin scraped at `apisix:9091/apisix/prometheus/metrics`. |
| **TigerBeetle** | ❌ GAP (mitigated) | 0.16.43 exposes **no metrics endpoint**. Covered indirectly via tigerbeetle-core/-edge service metrics and CIPS/PAPSS TB-balance gauges. `TigerBeetleSidecarDown` alert is armed but intentionally silent until a sidecar exists. Upgrade path in gaps doc. |
| **Apache Sedona** | ➖ N/A (library) | Sedona is a Spark library with no own metrics server — covered via the Spark PrometheusServlet below. |
| **Spark / Lakehouse** | ✅ Metrics | NEW `infra/lakehouse/spark/metrics.properties` enables PrometheusServlet; scrape `spark-master:4040/metrics`. MinIO: `/minio/v2/metrics/cluster` scrape. Iceberg REST: HTTP spans via the reverse proxy (APISIX) in front of it. |
| **GeoLibre** | 📄 External — documented | External OSS GIS app (github.com/opengeos/GeoLibre). Instrumentation guide: [docs/observability/geolibre-instrumentation.md](docs/observability/geolibre-instrumentation.md). |
| **OTel collector itself** | ✅ | Internal telemetry (`otelcol_*`) scraped from `:8889`; `CollectorDroppingSpans` / `CollectorQueueFull` alerts. |

---

## Alert catalog

Three rule files under `infra/observability/prometheus/rules/`, evaluated by
Prometheus every 30s. Expressions marked `VERIFY` in the rule files depend on
metric names that must be confirmed against the deployed collector/receiver
versions — see [Verification status](#verification-status-and-honest-gaps).

### `funds-flow.rules.yml` — group `funds_flow` (team: funds-ops)

| Alert | Severity | Meaning |
|---|---|---|
| `HighTransactionErrorRate` | critical | `pos_transaction_errors_total / pos_transactions_total > 5%` over 5m |
| `FundsFlowOperationErrors` | critical | Per-tenant error ratio on `funds_flow_operations_total{status="error"}` > 3% over 5m |
| `LedgerImbalanceDetected` | critical | Any `ledger_imbalance_detected_total` increase in 10m — **page immediately** |
| `SettlementLagHigh` | warning | p95 of `settlement_lag_seconds` > 900s (15m) per tenant over 10m |
| `FraudAlertSpike` | critical | `pos_fraud_alerts_total` > 10/min over 5m |
| `PaymentFailuresSpike` | warning | `payments_failed_total` increase > 20 per tenant+reason over 5m |
| `FloatLockContention` | warning | `pos_float_locks_total` > 5/min over 5m |
| `CIPSTransferFailureRatio` | critical | `cips_transfers_total{status="failed"}` ratio > 5% over 5m |

### `middleware.rules.yml` — groups `middleware_availability`, `middleware_saturation` (team: platform-ops)

Availability (all critical, `up{job=…} == 0` for 3m):
`KafkaDown`, `PostgresDown`, `RedisDown`, `TemporalDown`, `KeycloakDown`
(covers both `keycloak` and `keycloak-ha` jobs), `PermifyDown`, `ApisixDown`,
`OpenSearchDown`, `MinioDown`, `FluvioDown`, `MojaloopMlApiDown`,
`MojaloopCentralLedgerDown`, `SparkDown`, `TigerBeetleSidecarDown`
(intentionally silent until a TigerBeetle sidecar exists).

| Saturation alert | Severity | Meaning |
|---|---|---|
| `KafkaConsumerLag` | warning | `kafka_consumer_group_lag > 1000` for 10m (VERIFY metric name vs collector 0.129.0) |
| `RedisMemoryHigh` | warning | Redis used/max memory > 85% for 5m |
| `PostgresConnectionsHigh` | warning | pg connections > 80% of max for 10m |
| `PostgresDeadlocks` | warning | > 5 deadlocks in 5m per database |
| `ApisixUpstream5xx` | critical | APISIX upstream 5xx rate > 0.5/s over 5m |
| `OpenSearchClusterRed` | critical | Cluster status RED for 3m |
| `MinioDiskLow` | warning | Cluster free disk < 15% for 10m |

### `platform.rules.yml` — groups `platform_availability`, `platform_red`, `collector_health` (team: platform-ops)

| Alert | Severity | Meaning |
|---|---|---|
| `PlatformAvailability` | critical | Any app-layer job down 5m (`pos-shell-app`, `health-checker`, `circuit-breaker`, `rate-limiter`, `metrics-collector`, `postgres-exporter`, `papss`) |
| `HighHttp5xxRate` | critical | spanmetrics error ratio (`calls_total{status_code="STATUS_CODE_ERROR"}`) > 5% per service over 5m |
| `HighP95Latency` | warning | spanmetrics p95 (`duration_milliseconds_bucket`) > 1000ms per service over 10m |
| `CollectorDroppingSpans` | critical | `otelcol_receiver_refused_spans_total` rate > 0 for 5m (memory-limiter pressure) |
| `CollectorQueueFull` | warning | exporter queue > 90% capacity for 10m |

### Alertmanager routing (`infra/observability/alertmanager/alertmanager.yml`)

```
route (default → ntfy-ops; group_by: [alertname, severity, tenant_id];
       group_wait 30s, group_interval 5m, repeat_interval 4h)
├── severity=critical → ntfy-critical  (continue: true)
│     └── severity=critical → ops-webhook   (automation/runbook trigger placeholder)
├── team=funds-ops    → ntfy-funds     (continue: true → also hits severity routes)
└── severity=warning  → ntfy-ops
```

Receivers are ntfy webhooks (`http://ntfy/ops-critical`, `/funds-ops`, `/ops`) with
bearer tokens from `NTFY_TOKEN_*` env vars, plus `ops-webhook`
(`http://ops-webhook:5000/alerts`, placeholder). Inhibit rule: a `critical` alert
silences `warning` alerts with the same `alertname`+`instance`.

**Adding a receiver** (e.g. Slack/PagerDuty):
1. Add a receiver block (`slack_configs:` / `pagerduty_configs:`) — secrets via env
   or `file_sd`, never inline.
2. Reference it from `route.routes` with a severity/team matcher.
3. Keep `continue: true` on the critical route so ntfy still fires.

---

## Runbooks (top 5)

### 1. `LedgerImbalanceDetected` (critical, funds-ops)

1. Acknowledge and page the funds-ops on-call — any ledger imbalance is a
   stop-the-line event.
2. Read `ledger` and `tenant` labels from the alert; open the tenant-overview
   Grafana dashboard filtered to that tenant.
3. In Tempo, search traces for `tenant.id=<tenant>` around the alert window;
   look for failed settlement/transfer spans (status=ERROR).
4. Check `funds_flow_operations_total{status="error"}` and
   `payments_failed_total` for the same tenant to find the failing operation.
5. Freeze automated settlement for the affected ledger/tenant (settlement cron
   toggle) before manual reconciliation.
6. Reconcile via the settlement reconciliation tooling; increment counts come
   from `pos_settlement_reconciliation_total{outcome="discrepancy"}`.
7. Post-incident: file a report with the trace IDs and metric snapshots.

### 2. `FundsFlowOperationErrors` (critical, funds-ops)

1. Identify `tenant` from the alert labels; check the error ratio trend on the
   funds-flow-slo dashboard.
2. Break down by `operation` and `service` labels on
   `funds_flow_operations_total{status="error"}` to localize the failing path.
3. Correlate with `payments_failed_total{reason=…}` for the same tenant.
4. Pull traces from Tempo (`tenant.id=<tenant>`, status=ERROR) for a failing
   operation sample.
5. If the failing service is an integration (cips/papss), check their
   `/metrics` and recent deploys; consider circuit-breaking the integration.
6. Escalate to the owning service team with trace IDs; monitor until the ratio
   drops below 3% for >10m.

### 3. `HighHttp5xxRate` (critical, platform-ops)

1. Alert carries `service_name` (spanmetrics) — start there.
2. Check whether `CollectorDroppingSpans` is also firing; if so, treat the
   collector as suspect first.
3. On the platform-otel-overview dashboard, compare error rate vs latency vs
   request volume for the service.
4. In Tempo, sample ERROR spans for the service; follow the trace to the
   failing downstream (pg/redis/kafka spans are auto-instrumented in TS).
5. Check dependency alerts (PostgresDown, RedisDown, KafkaDown) for the same
   window.
6. If a recent deploy correlates, roll back; otherwise scale/restart the
   service per its own runbook.

### 4. `KafkaConsumerLag` (warning, platform-ops)

1. Alert carries `group` and `topic` labels (from the kafkametrics receiver).
2. Confirm the lag is growing, not spiky: graph `kafka_consumer_group_lag` (or
   `pos_kafka_consumer_lag` from the TS app) over 1h.
3. Check consumer service health — the Rust fluvio-consumer and TS kafkajs
   consumers expose `/metrics`; look for error counters and restarts.
4. Verify broker health via `KafkaDown` / broker metrics; a single slow broker
   can manifest as lag.
5. Scale out the consumer group (add partitions/consumer replicas) if the
   consumers are CPU-bound.
6. If lag persists > 30m, escalate to platform-ops on-call with the topic/group.

### 5. Component down (`*Down` availability alerts, critical)

1. Read the `job` and `instance` labels; the job name maps 1:1 to a scrape job
   in `infra/observability/otel/otel-collector-config.yaml`.
2. `docker ps` / `kubectl get pods` for the component — distinguish
   process-down from network/DNS failure on `54link-network`.
3. Check the component's own logs (`docker logs <container>`); for k8s use
   Loki (`{service="<name>"}`).
4. If the process is up but the endpoint is unreachable, verify the metrics
   port/path in the collector config matches the deployment (e.g. Temporal
   metrics are on `:9090`, **not** the gRPC `:7233`).
5. Restart the component; if it flaps, check host resources via the
   hostmetrics dashboards.
6. Silence the alert in Alertmanager only if the component is intentionally
   down (maintenance); note `TigerBeetleSidecarDown` is expected-silent.

---

## Verification status and honest gaps

### What was executed/tested

| Artifact | Check | Result |
|---|---|---|
| `services/api-server-ts` changed files | `tsc --strict --noEmit` typecheck | Clean (run by implementing agent) |
| Python services + `services/shared/observability.py` | Real import test with pip-installed OTel 1.33.1 — no-op path (no endpoint) and full path (endpoint set) | Pass (run by implementing agent) |
| All YAML/JSON configs (collector, prometheus, rules, alertmanager, tempo, grafana, compose, middleware configs, dashboards) | Parse gates (YAML/JSON load) | Pass |
| Markdown docs (this round) | No parse gate required; code fences kept balanced | n/a |

### What was NOT verified (no toolchain / no live stack)

- **Go code not compiled.** `go.mod` edits were hand-written
  (`go.opentelemetry.io/otel v1.43.0`, `prometheus/client_golang v1.21.1`).
  The first build must run `go mod tidy`; the `go` directive may need a bump to
  1.24+. Treat gateway-service / tigerbeetle-core / shared middleware as
  unverified until compiled.
- **Rust code not compiled.** `services/rust/otel-common` and the four wired
  services were not built. Pre-existing compile drift in tx-validator,
  ledger-bridge, and fluvio-consumer was preserved verbatim (they likely did
  not compile before this change either).
- **PromQL metric names.** Several alert expressions carry `VERIFY` comments:
  collector `pos54` namespace prefixing of `up` / spanmetrics names
  (`pos54_calls_total`, `pos54_duration_milliseconds_bucket`), kafkametrics
  receiver name (`kafka_consumer_group_lag` vs `kafka.consumer_group.lag`),
  redis/postgresql receiver names, APISIX plugin metric names, OpenSearch
  cluster-status metric name. Confirm against collector 0.129.0 before rollout.
- **Collector config not run against a live stack.** The config parses and the
  component set is valid for 0.129.0, but no end-to-end pipeline test was run.
- **No E2E tests.** No trace was actually propagated across services in this
  round; the W3C tracecontext/baggage contract is code-reviewed, not
  runtime-proven.

### Residual risks

1. First Go/Rust builds may surface dependency or API mismatches (see above).
2. Availability alerts for receiver-collected components (Kafka, Postgres,
   Redis) may never fire because dedicated receivers do not emit `up` samples —
   the `VERIFY` comments in `middleware.rules.yml` describe the fallback
   signals to adopt.
3. Tempo local storage is single-node; no retention/compaction beyond the
   shipped defaults.
4. Alertmanager receivers use placeholder tokens/hosts (`NTFY_TOKEN_*`,
   `ops-webhook:5000`) that must be substituted at deploy time.
5. TigerBeetle and OpenAppSec have no native telemetry — see
   [docs/observability/gaps-and-followups.md](docs/observability/gaps-and-followups.md).

## Related documents

- [docs/observability/gaps-and-followups.md](docs/observability/gaps-and-followups.md) — gap register and next-wave work
- [docs/observability/geolibre-instrumentation.md](docs/observability/geolibre-instrumentation.md) — instrumenting the external GeoLibre GIS app
- `infra/observability/` — all stack configuration referenced above
