# 54agent Production Runbook

## Table of Contents

1. [Service Architecture](#service-architecture)
2. [Incident Response](#incident-response)
3. [Common Issues & Resolution](#common-issues--resolution)
4. [Deployment Procedures](#deployment-procedures)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Escalation Matrix](#escalation-matrix)

---

## Service Architecture

### Core Services

| Service                   | Language   | Port | Health Endpoint   |
| ------------------------- | ---------- | ---- | ----------------- |
| 54agent API                | TypeScript | 3001 | `GET /api/health` |
| goAML Integration         | Go         | 8210 | `GET /health`     |
| KYC Enforcement Gateway   | Go         | 8211 | `GET /health`     |
| AML Case Manager          | Go         | 8212 | `GET /health`     |
| CBN Tiered KYC Engine     | Rust       | 8213 | `GET /health`     |
| Sanctions Re-Screener     | Rust       | 8214 | `GET /health`     |
| KYC Workflow Orchestrator | Python     | 8215 | `GET /health`     |
| KYC Event Consumer        | Python     | 8216 | `GET /health`     |
| Agent Store Service       | Go         | 8220 | `GET /health`     |
| Payment Split Engine      | Rust       | 8221 | `GET /health`     |
| Store Analytics Engine    | Python     | 8222 | `GET /health`     |

### Infrastructure Dependencies

| Dependency  | Default Port | Purpose                               |
| ----------- | ------------ | ------------------------------------- |
| PostgreSQL  | 5432         | Primary database                      |
| Redis       | 6379         | Caching, rate limiting, session store |
| Kafka       | 9092         | Event streaming                       |
| Keycloak    | 8080         | Identity & access management          |
| Temporal    | 7233         | Workflow orchestration (SLA timers)   |
| TigerBeetle | 3001         | Double-entry ledger                   |

---

## Incident Response

### Severity Levels

| Level     | Description                             | Response Time     | Escalation                           |
| --------- | --------------------------------------- | ----------------- | ------------------------------------ |
| **SEV-1** | Platform down, all transactions failing | 5 min             | Immediate: On-call + Team Lead + CTO |
| **SEV-2** | Major feature degraded, >5% tx failures | 15 min            | On-call + Team Lead                  |
| **SEV-3** | Minor feature broken, <1% impact        | 1 hour            | On-call engineer                     |
| **SEV-4** | Cosmetic/non-urgent                     | Next business day | Backlog                              |

### Incident Response Steps

#### 1. Detect & Triage (0-5 min)

```bash
# Check overall platform health
curl -s http://localhost:3001/api/health | jq .

# Check all services
for port in 8210 8211 8212 8213 8214 8215 8216 8220 8221 8222; do
  echo "Port $port: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:$port/health)"
done

# Check database connectivity
psql $DATABASE_URL -c "SELECT 1;"

# Check Redis
redis-cli ping

# Check Kafka
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

#### 2. Contain (5-15 min)

- Enable maintenance mode: `curl -X POST http://localhost:3001/api/admin/maintenance-mode`
- If a specific service is causing cascading failures, disable its circuit breaker:
  ```bash
  curl -X POST http://localhost:3001/api/admin/circuit-breaker/open \
    -H "Content-Type: application/json" \
    -d '{"service": "<service-name>"}'
  ```

#### 3. Diagnose

```bash
# Recent error logs
docker logs --tail 500 54agent-api 2>&1 | grep -i error

# Database slow queries
psql $DATABASE_URL -c "
  SELECT pid, now() - pg_stat_activity.query_start AS duration, query
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY duration DESC
  LIMIT 10;"

# Connection pool status
psql $DATABASE_URL -c "
  SELECT count(*) AS total,
    count(*) FILTER (WHERE state = 'active') AS active,
    count(*) FILTER (WHERE state = 'idle') AS idle
  FROM pg_stat_activity;"

# Kafka consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --all-groups
```

#### 4. Resolve & Recover

- Restart specific service: `docker restart <service-name>`
- Full platform restart: `docker compose -f docker-compose.production.yml restart`
- Database connection reset: Restart API server (pool is recreated on startup)
- Clear Redis cache: `redis-cli FLUSHDB` (use with caution)

#### 5. Post-Incident

- Write incident report within 24 hours
- Update this runbook with new failure modes
- Create tickets for preventive measures

---

## Common Issues & Resolution

### Transaction Processing Failures

**Symptoms**: Transactions returning 500, settlement delays

```bash
# Check transaction queue
curl http://localhost:3001/api/admin/tx-queue-depth

# Check TigerBeetle health
curl http://localhost:3001/api/admin/tigerbeetle-health

# Check for stuck transactions
psql $DATABASE_URL -c "
  SELECT status, count(*)
  FROM transactions
  WHERE created_at > now() - interval '1 hour'
  GROUP BY status;"
```

### Keycloak Authentication Failures

**Symptoms**: Users can't log in, 401 errors across services

```bash
# Check Keycloak is responsive
curl -s http://localhost:8080/auth/realms/54agent/.well-known/openid-configuration | jq .issuer

# Check JWT validation
curl -s http://localhost:3001/api/auth/me \
  -H "Authorization: Bearer <token>" | jq .

# Restart Keycloak if unresponsive
docker restart keycloak
```

### High Memory Usage

**Symptoms**: OOM kills, slow responses

```bash
# Check process memory
docker stats --no-stream

# Check Node.js heap
curl http://localhost:3001/api/admin/heap-stats | jq .

# Force garbage collection (development only)
kill -USR2 $(pgrep -f "node.*server")
```

### Kafka Consumer Lag

**Symptoms**: Delayed notifications, stale data

```bash
# Check lag per consumer group
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group 54agent-kyc-consumer

# Reset consumer offset (CAUTION: may cause reprocessing)
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group 54agent-kyc-consumer \
  --topic kyc-events \
  --reset-offsets --to-latest --execute
```

---

## Deployment Procedures

### Pre-Deployment Checklist

- [ ] All CI checks passing (Lint, TypeCheck, Tests, Security Scans)
- [ ] Database migrations reviewed and tested on staging
- [ ] Feature flags configured for gradual rollout
- [ ] Monitoring alerts reviewed and updated
- [ ] Rollback plan documented

### Deploy Steps

```bash
# 1. Build and tag
docker build -t 54agent/api:$(git rev-parse --short HEAD) .
docker push 54agent/api:$(git rev-parse --short HEAD)

# 2. Deploy with Helm (blue-green)
helm upgrade 54agent ./helm/54agent \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set deployment.strategy=blue-green \
  --namespace production

# 3. Verify health
kubectl rollout status deployment/54agent-api -n production

# 4. Run smoke tests
npm run test:smoke -- --env=production
```

### Rollback

```bash
# Immediate rollback via Helm
helm rollback 54agent 0 --namespace production

# Or revert to specific revision
helm rollback 54agent <REVISION> --namespace production
```

---

## Monitoring & Alerts

### Dashboards

- **Platform Overview**: Grafana → 54agent Platform Overview
- **Transaction Metrics**: Grafana → 54agent Transactions
- **Service Health**: Grafana → 54agent Service Health

### Key Metrics

| Metric              | Healthy Range | Alert Threshold     |
| ------------------- | ------------- | ------------------- |
| API Error Rate      | < 0.1%        | > 5% for 5 min      |
| P95 Latency         | < 500ms       | > 2s for 5 min      |
| DB Pool Usage       | < 50%         | > 85% for 3 min     |
| Transaction Failure | < 0.5%        | > 2% for 5 min      |
| Kafka Consumer Lag  | < 100         | > 10,000 for 10 min |
| Memory Usage        | < 70%         | > 90% for 5 min     |

---

## Escalation Matrix

| Time    | Action                                                    |
| ------- | --------------------------------------------------------- |
| 0 min   | On-call receives alert via PagerDuty                      |
| 5 min   | Acknowledge alert, begin triage                           |
| 15 min  | If SEV-1/SEV-2: escalate to Team Lead                     |
| 30 min  | If unresolved: escalate to CTO                            |
| 1 hour  | If unresolved: war room with full team                    |
| 4 hours | If unresolved: engage vendor support (AWS/Kafka/Keycloak) |

### Contacts

Configure in PagerDuty/OpsGenie:

- On-call rotation: Platform Engineering team
- Team Lead: Engineering Manager
- Escalation: CTO
