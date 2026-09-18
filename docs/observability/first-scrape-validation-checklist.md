# First-Scrape Validation Checklist (Round 5)

Every `# VERIFY` marker left in the round-4 rule files is listed below with the exact existence query to run against Prometheus (`localhost:19090`) after the first live scrape. Tick an item only when the query returns series; if it returns nothing, fix the rule to the metric name actually emitted by the deployed component version, and remove the `# VERIFY` comment.

Query pattern: `curl -s 'localhost:19090/api/v1/query?query=<EXPR>'` → `data.result` must be non-empty.

## middleware.rules.yml

| # | Line | VERIFY item | Existence query |
|---|------|-------------|-----------------|
| 1 | 9 | Collector prometheus exporter namespace prefix on metric names | `count({__name__=~"pos54_.+"})` — if 0, names are unprefixed; adjust all pos54_* rules |
| 2 | 13 | kafka/postgres/redis series present via collector receivers | `count({__name__=~"kafka.+"})`, `count({__name__=~"pg.+\|postgresql.+"})`, `count({__name__=~"redis.+"})` |
| 3 | 24 | `kafka_brokers` present (else alert on absence) | `kafka_brokers` |
| 4 | 38 | postgres up-signal job name (`postgresql` receiver vs `postgres-exporter`) | `up{job=~"postgres.*"}`, `pg_up` |
| 5 | 50 | redis up-signal (`redis_up` vs `up{job="redis"}`) | `redis_up`, `up{job="redis"}` |
| 6 | 195 | Collector self-telemetry names for collector 0.129.0 | `otelcol_receiver_accepted_spans`, `otelcol_exporter_sent_spans` |
| 7 | 206 | redis receiver metric names (version-dependent) | `redis_db_keys`, `redis_memory_used_bytes` (or `redis_memory_used_rss_bytes`) |
| 8 | 218 | `pg_stat_activity_count` from postgresql receiver | `pg_stat_activity_count` |
| 9 | 231 | `pg_stat_database_deadlocks` from postgresql receiver | `pg_stat_database_deadlocks` |
| 10 | 242 | APISIX prometheus plugin 5xx series | `apisix_http_status{code=~"5.."}` |
| 11 | 253 | OpenSearch cluster status metric name via `_prometheus/metrics` plugin | `opensearch_cluster_status`, or `opensearch_cluster_health_status` |
| 12 | 266 | MinIO disk metrics names | `minio_cluster_disk_free_total`, `minio_cluster_disk_total` |

## platform.rules.yml

| # | Line | VERIFY item | Existence query |
|---|------|-------------|-----------------|
| 13 | 6 | spanmetrics calls_total namespaced as `pos54_calls_total` | `calls_total`, `pos54_calls_total` — use whichever exists |
| 14 | 33 | per-tenant label present on spanmetrics | `count by (tenant_id) (calls_total)` or `pos54_calls_total` |
| 15 | 48 | duration histogram name | `duration_milliseconds_bucket` or `pos54_duration_milliseconds_bucket` |
| 16 | 76 | exporter queue metrics | `otelcol_exporter_queue_size`, `otelcol_exporter_queue_capacity` |

## Non-PromQL verifications

| # | Item | Check |
|---|------|-------|
| 17 | APISIX `collector.address` scheme in `plugin_attr.opentelemetry` | APISIX 3.9/3.11 expects `http://otel-collector:4318` (scheme required); confirm spans arrive in Tempo after one gateway request |
| 18 | Temporal metrics port | `curl -s <temporal-host>:9090/metrics \| head` (NOT 7233) |
| 19 | Keycloak telemetry | Keycloak logs show `telemetry enabled`; traces visible in Tempo with `service.name=keycloak` |
| 20 | Dapr zipkin bridge | Tempo search `service.name` containing daprd app ids after one pub/sub call |
| 21 | Loki mount path | `docker compose` resolves `../loki/loki-config.yaml` relative to the compose file location — confirm the file exists at that relative path on the deploy host |

## Sign-off
All 21 items checked by: ____________  Date: ______  Remaining VERIFY markers after remediation: ____
