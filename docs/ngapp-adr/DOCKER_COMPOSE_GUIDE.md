# Docker Compose File Guide

> ⚠️ **2026-08 correction (@ `505705ac`):** this guide previously described `docker-compose.production.yml` as the production compose file. That file **does not exist in the repository** (verified against the git tree at commit `505705ac`). `Makefile.production` still references it (`COMPOSE_PROD` variable) and will fail until the file is created or the Makefile is updated.

## Which file to use?

| File                          | Purpose                                            | When to use                                 |
| ----------------------------- | -------------------------------------------------- | ------------------------------------------- |
| **`docker-compose.yml`**      | **Full stack** — app + infra (30+ services, some profiles) | Current primary compose file for all environments |
| `docker-compose.production.yml` | PRODUCTION — full stack with profiles            | ⚠️ **Not present in the repo** (see note above) |

## Deployment (current state)

```bash
# Copy and configure environment
cp .env.production.example .env.production
# Edit .env.production with production values

# Start everything
docker compose -f docker-compose.yml --env-file .env.production up -d
```

`docker-compose.yml` defines a small number of `profiles:` entries; most services start by default. A dedicated production compose file with the full `infra` / `app` / `gateway` / `observability` profile split described in earlier revisions of this guide has not been committed yet.

## Local Development

```bash
# Quick start (app + postgres + redis)
docker compose up -d
```

## Legacy / Sprint-Specific Files (DO NOT USE IN PRODUCTION)

The following files are sprint-specific or experimental configurations kept for reference (verified present @ `505705ac`):

- `docker-compose.integration-test.yml`
- `docker-compose.optimized.yml`
- `docker-compose.sprint42.yml`, `docker-compose.sprint46.yml`, `docker-compose.sprint50.yml`, `docker-compose.sprint76.yml`

(`docker-compose.override.yml`, `docker-compose.final.yml`, and `docker-compose.unified.yml` were referenced by earlier revisions of this guide but are **not present** in the repository.)

**Until `docker-compose.production.yml` is (re)added, use `docker-compose.yml` for all environments.**
