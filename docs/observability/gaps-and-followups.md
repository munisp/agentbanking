# Observability gaps & follow-ups register

Known gaps and deferred work from the round-4 OpenTelemetry rollout
(branch `fix/observability-round4`). Each entry states the current state, the
options, and the recommended next step. See [OBSERVABILITY.md](../../OBSERVABILITY.md)
for the delivered architecture and verification status.

| # | Gap | Impact | Recommendation |
|---|-----|--------|----------------|
| 1 | TigerBeetle has no metrics endpoint (0.16.43) | No direct ledger-DB telemetry | Service-level gauges (below) |
| 2 | OpenAppSec has no OTel support | Security events outside traces/metrics | Log-based correlation (below) |
| 3 | ~100 Go services not yet wired | Traces/metrics missing for most Go estate | 3-line pattern (below) |
| 4 | ~85 Rust crates not yet wired | Same for Rust estate | otel-common wiring |
| 5 | payment-processing `api/payment.py` hooks undecided | Possible double-counting | Decide idempotency semantics |
| 6 | Temporal SDK interceptors not instrumented | Workflow internals invisible | Next instrumentation layer |
| 7 | Dead root `server/` tree retains old `telemetry.ts` | Confusing duplicate | Remove in cleanup wave |
| 8 | Pre-existing Rust compile drift | tx-validator / ledger-bridge / fluvio-consumer may not build | Fix on first toolchain build |
| 9 | Go `go.mod` hand-edited, uncompiled | First build risk | `go mod tidy`, bump `go` directive |
| 10 | PromQL VERIFY comments unconfirmed | Alerts may never fire | Confirm names on live stack |
| 11 | Dapr 1.11 Zipkin-only tracing | Extra hop, no native OTLP | Upgrade Dapr |

---

## 1. TigerBeetle — no metrics endpoint (0.16.43)

**State.** The deployed TigerBeetle version exposes no `/metrics` or OTLP
interface. The collector deliberately does **not** invent a scrape job (see the
NOTE in `otel-collector-config.yaml`). The `TigerBeetleSidecarDown` alert is armed
against a `tigerbeetle-sidecar` job that does not exist yet, so it is
intentionally silent.

**Options.**
- **(a) Upgrade** to a TigerBeetle version with a metrics endpoint when one
  becomes available — cleanest, but tied to upstream release cadence and a data-
  format migration.
- **(b) Sidecar gauger**: a small service polling `tigerbeetle inspect` /
  `tigerbeetle version` (or a heartbeat write+read against a canary account) and
  exposing `up`-style gauges on `/metrics` for the collector to scrape.
- **(c) Rely on service-level gauges** — what we do today: `tigerbeetle-core`
  and `tigerbeetle-edge` expose promhttp `/metrics`, and the CIPS/PAPSS services
  publish TB-balance gauges. Client-side latency/error metrics surface TB
  degradation indirectly.

**Recommendation:** (c) now; add (b) as a next-wave sidecar so
`TigerBeetleSidecarDown` becomes live; revisit (a) at the next TB upgrade window.

## 2. OpenAppSec — no OTel support

**State.** OpenAppSec (k8s CRD-managed) has no native OTel tracing or Prometheus
metrics exporter usable by this stack. Its logs ship to OpenSearch
(`opensearch:5140`).

**Follow-up.** Treat OpenAppSec as log-observable only: build OpenSearch/Loki
dashboards over its log stream and correlate with traces best-effort via
timestamps and source IPs. Reassess if upstream adds an OTel/Prometheus exporter;
do not block the rollout on it.

## 3. ~100 Go services pending the 3-line wiring pattern

**State.** Only `gateway-service` and `tigerbeetle-core` are wired. The shared
middleware (`services/shared/middleware/otel.go`) already provides everything;
each remaining service needs exactly this pattern in `main.go`:

```go
// 1. Init telemetry (traces + OTLP metrics), keep the shutdown fn
shutdown, err := middleware.InitTelemetry("service-name", "1.0.0")
if err != nil {
    log.Printf("[service-name] telemetry init failed: %v", err) // warn, do not fatal
}

// 2. Expose Prometheus metrics
http.Handle("/metrics", promhttp.Handler())

// 3. Wrap the root handler (stamps tenant.id from X-Tenant-ID + baggage)
log.Fatal(http.ListenAndServe(":8080",
    middleware.OTelHTTPMiddleware("service-name", http.DefaultServeMux)))
```

…plus `defer middleware.GracefulHTTPShutdown(...)` / shutdown handling where the
service lifecycle allows. Roll out in dependency order (edge services first, so
trace context enters the mesh early).

## 4. ~85 Rust crates pending `otel-common` wiring

**State.** `services/rust/otel-common` is delivered and wired into fraud-engine,
tx-validator, ledger-bridge, fluvio-consumer. The remaining workspace crates need:
`init_tracing("crate-name")` at the top of `main` (hold the `OtelGuard`), a
`/metrics` route serving `metrics_handle()`, tenant middleware
(`tenant_id_from_headers` + `record_tenant_span_attr`), and
`register_business_metrics()` where funds-flow counters apply.

## 5. `api/payment.py` idempotency-ambiguous hooks

**State.** Funds-flow hooks were added to
`payment-processing-service/api/transfers.py` (withdraw / deposit /
settlement_payout). The `api/payment.py` paths were left untouched because it is
ambiguous whether a retried/idempotent payment attempt should increment
`funds_flow_operations_total` again — double-counting would poison the
`FundsFlowOperationErrors` error-ratio alert.

**Follow-up.** Decide the contract (count attempts vs count committed operations;
recommended: count committed operations only, with `status="error"` recorded once
per terminal failure) and then instrument `api/payment.py` accordingly.

## 6. Temporal SDK interceptors

**State.** The Temporal *server* is observable (prometheus `:9090`, histogram
timers via HA dynamic-config). Workflow/activity internals are not: SDK
interceptors for the Go, Python, and TS workers would produce spans per
workflow/activity with proper parentage.

**Follow-up.** Add `interceptor`/`tracing` packages per SDK
(`go.temporal.io/sdk/contrib/opentelemetry`, `temporalio.contrib.opentelemetry`,
`@temporalio/interceptors-opentelemetry`) as the next instrumentation layer.

## 7. Dead root `server/` tree

**State.** The legacy root-level `server/` tree still contains an old copy of
`telemetry.ts`. It is unused (the live server is
`services/api-server-ts/server/`) and harmless, but it confuses greps and code
review.

**Follow-up.** Delete the root `server/` tree in a cleanup wave after confirming
no build/deploy script references it.

## 8. Pre-existing Rust compile drift

**State.** tx-validator, ledger-bridge, and fluvio-consumer carried compile drift
before this round; it was preserved verbatim (no toolchain available to verify).
The new otel wiring was written to match the existing code shape but is likewise
uncompiled.

**Follow-up.** On the first build with a Rust toolchain: `cargo build` the
workspace, fix drift and any otel-common API mismatches together.

## 9. Go `go.mod` hand-edits

**State.** `services/shared/middleware/go.mod`, `services/gateway-service/go.mod`,
and `services/tigerbeetle-core/go.mod` were edited by hand
(`go.opentelemetry.io/otel v1.43.0`, `prometheus/client_golang v1.21.1`) without
a Go toolchain.

**Follow-up.** First build: run `go mod tidy` in each module; the `go` directive
may need a bump to 1.24+ to satisfy the otel dependency graph.

## 10. PromQL VERIFY comments

**State.** Alert expressions in `infra/observability/prometheus/rules/` carry
`VERIFY` comments where metric names depend on the deployed component versions:
collector `pos54` namespace prefixing (`pos54_up`, `pos54_calls_total`,
`pos54_duration_milliseconds_bucket`), kafkametrics lag metric name, redis /
postgresql receiver metric names, APISIX plugin metric names, OpenSearch
cluster-status metric name.

**Follow-up.** After the first live deploy, query Prometheus for each name,
update the rule files, and remove the VERIFY comments.

## 11. Dapr 1.11 Zipkin constraint

**State.** Dapr 1.11 supports only the Zipkin tracing exporter, so Dapr spans
reach the collector through its Zipkin receiver (`:9411`) and are converted to
OTLP there.

**Follow-up.** Upgrade Dapr to a version with native OTLP tracing support, then
repoint `infra/dapr/config.yaml` (and the HA config) directly at the OTLP
endpoint and retire the Zipkin bridge if nothing else uses it (Tempo's own
Zipkin receiver remains as a backup path).
