# Docker Compose File Guide

## Which file to use?

| File | Purpose | When to use |
|------|---------|-------------|
| **`docker-compose.production.yml`** | **PRODUCTION** — full stack with profiles | Production & staging deployments |
| `docker-compose.yml` | Local development — app + basic infra | `docker compose up` for quick local dev |
| `docker-compose.override.yml` | Dev overrides (volumes, debug ports) | Auto-applied when using `docker-compose.yml` |

## Production Deployment

```bash
# Copy and configure environment
cp .env.production.example .env.production
# Edit .env.production with production values

# Start everything
docker compose -f docker-compose.production.yml --env-file .env.production up -d

# Or start specific profiles:
docker compose -f docker-compose.production.yml --env-file .env.production \
  --profile infra --profile app --profile gateway --profile observability up -d
```

### Profiles
| Profile | Services |
|---------|----------|
| `infra` | PostgreSQL, Redis, Kafka, Keycloak, Temporal, TigerBeetle, Permify, Vault |
| `app` | 54Link API + all Go/Rust/Python microservices |
| `gateway` | Nginx reverse proxy with TLS |
| `observability` | Prometheus, Grafana, Loki, Promtail, Alertmanager |

## Local Development

```bash
# Quick start (app + postgres + redis)
docker compose up -d

# With all infrastructure
docker compose --profile infra up -d
```

## Legacy Files (DO NOT USE IN PRODUCTION)
The following files are sprint-specific configurations kept for reference:
- `docker-compose.sprint10.yml` through `docker-compose.sprint76.yml`
- `docker-compose.final.yml`
- `docker-compose.unified.yml`

**Always use `docker-compose.production.yml` for production.**
