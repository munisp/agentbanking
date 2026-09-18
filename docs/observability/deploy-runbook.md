# Observability Stack — Deploy Runbook (Round 5)

**Scope:** first deploy of the round-4 observability stack (`infra/observability/`, `docker-compose.observability.yml`) onto the externally provisioned infrastructure. This runbook contains no runtime claims — every step has a verification command; do not mark a step done unless its check passes.

## 0. Prerequisites
- Docker network `54link-network` exists (`docker network ls | grep 54link`).
- `alertmanager.env` created from `infra/observability/alertmanager/alertmanager.env.template` with real values (never commit it).
- Ports free on host: 19090 (Prometheus), 13000 (Grafana), 13200 (Tempo), 19093 (Alertmanager), 13100 (Loki), 18080 (ntfy).
- CI gate `observability-build-gate` green on the commit being deployed.

## 1. Deploy
```bash
docker compose -f docker-compose.observability.yml up -d
docker compose -f docker-compose.observability.yml ps   # all services Up/healthy
```

## 2. Smoke checks (run all; stop on first failure)
| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | Collector up | `curl -s localhost:13133/` (health) or `docker logs otel-collector` | no pipeline errors |
| 2 | Collector self-metrics | `curl -s localhost:8888/metrics \| head` | `otelcol_*` series |
| 3 | Prometheus scrape of collector exporter | `curl -s localhost:8889/metrics \| grep -c calls_total` | > 0 |
| 4 | Prometheus targets | `curl -s localhost:19090/api/v1/targets?state=active` | all jobs `health=up` (mojaloop/opensearch/minio/fluvio/spark + otel-collector) |
| 5 | Rules loaded | `curl -s localhost:19090/api/v1/rules` | 34 rules across funds-flow/middleware/platform groups |
| 6 | Alertmanager config | `curl -s localhost:19093/api/v2/status` | cluster `status=ready`, route tree present |
| 7 | ntfy | `curl -s localhost:18080/v1/health` | `{"healthy":true}` |
| 8 | Tempo | `curl -s localhost:13200/status/version` | JSON version |
| 9 | Loki | `curl -s localhost:13100/ready` | `ready` |
| 10 | Grafana datasources | Grafana UI → Connections | Prometheus/Tempo/Loki/Alertmanager all green |

## 3. End-to-end trace check
1. Call any instrumented service with a tenant header:
   `curl -H "x-tenant-id: smoke-tenant-1" http://<api-server>/api/health`
2. Grafana → Explore → Tempo → search `service.name=<service>` → confirm span has `tenant.id=smoke-tenant-1`.
3. Prometheus → query `calls_total{tenant_id="smoke-tenant-1"}` (or `pos54_calls_total` if the namespace prefix is active — see checklist) → count ≥ 1.
4. If the span is missing, check in order: service OTEL env vars → collector logs (`docker logs otel-collector`) → Tempo logs.

## 4. Alert delivery check
```bash
# fire a synthetic test alert
curl -X POST localhost:19093/api/v1/alerts -H 'Content-Type: application/json' -d '[{
  "labels": {"alertname":"SmokeTestAlert","severity":"warning","team":"ops","tenant_id":"smoke-tenant-1"},
  "annotations": {"summary":"deploy smoke test"}}]'
```
Confirm the notification arrives on the ntfy `ops` topic. Then resolve by waiting for the repeat interval or restarting Alertmanager.

## 5. First-scrape validation
Run every item in `first-scrape-validation-checklist.md` — it maps each `# VERIFY` marker in the rule files to the exact PromQL existence query.

## 6. Rotating secrets
1. Generate new ntfy tokens / SMTP password.
2. Update `alertmanager.env`, then `docker compose -f docker-compose.observability.yml up -d alertmanager` (config is re-rendered at start).
3. Verify with the step-4 synthetic alert.

## 7. Rollback
The stack is additive (no changes to data-plane services beyond instrumentation). Rollback = `docker compose -f docker-compose.observability.yml down` and, if needed, revert service env vars `OTEL_*` to unset (all instrumentation is env-gated no-op when unset).
