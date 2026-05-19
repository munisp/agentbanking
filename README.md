# 54Link Agency Banking Platform

**Enterprise-grade POS Agent Banking Platform for Nigerian Financial Services**

A comprehensive agency banking platform built for managing POS terminal networks, agent operations, transaction processing, fraud detection, KYC verification, and regulatory compliance (CBN). Designed for the Nigerian financial services market with multi-language support (English, French, Nigerian Pidgin, Hausa, Yoruba, Igbo).

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Features](#features)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Security](#security)
- [Testing](#testing)
- [Contributing](#contributing)

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                        Client (React 19)                        │
│  POS Shell │ Dashboard │ Reports │ Agent Mgmt │ Fraud │ KYC   │
│                     tRPC Client (Superjson)                      │
└───────────────────────────────┬───────────────────────────────┘
                              │ HTTPS / WebSocket
┌───────────────────────────────┼───────────────────────────────┐
│                Express + tRPC Server (70+ routers)               │
│  Auth │ CRUD │ Fraud Engine │ Settlement │ KYC │ Reports     │
│  Middleware: Rate Limit │ Tracing │ CSP │ CORS │ Validation  │
└───────────────────────────────┬───────────────────────────────┘
                              │
┌───────────────────────────────┼───────────────────────────────┐
│  PostgreSQL │ Redis │ S3 Storage │ TigerBeetle (Ledger)       │
└───────────────────────────────────────────────────────────────┘
```

| Layer      | Technology                                      |
| ---------- | ----------------------------------------------- |
| Frontend   | React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| State      | TanStack React Query, tRPC React hooks          |
| Backend    | Express 4, tRPC 11, Node.js 22                  |
| Database   | PostgreSQL (Drizzle ORM), 71 tables             |
| Auth       | Manus OAuth, JWT sessions                       |
| Payments   | Stripe (subscriptions + one-time)               |
| Real-time  | Socket.IO notifications                         |
| Storage    | AWS S3                                          |
| AI/LLM     | Built-in LLM helper for chat support            |
| Monitoring | Prometheus, Grafana (4 dashboards)              |
| Infra      | Docker Compose, Kubernetes, Terraform           |
| CI/CD      | GitHub Actions                                  |
| Testing    | Vitest (1,200+), Playwright E2E, k6 load        |

---

## Getting Started

### Prerequisites

- Node.js 22+ and pnpm 9+
- PostgreSQL 15+
- Redis 7+ (optional)

### Installation

```bash
git clone <repo-url> && cd pos-shell-demo
pnpm install
cp .env.example .env   # Edit with your credentials
pnpm db:push           # Push database schema
node scripts/seed-production.mjs  # Seed demo data
pnpm dev               # Start development server
```

### Docker

```bash
docker compose up -d                    # Development
docker compose -f docker-compose.yml \  # Production
  -f docker-compose.production.yml up -d
```

---

## Features

### Core Banking

- POS Terminal Shell (cash-in, cash-out, transfers, bill payments)
- Transaction lifecycle with real-time status tracking
- Float management with auto-alerts
- Settlement engine with batch reconciliation
- Tiered commission calculator

### Agent Management

- Multi-step onboarding with document upload
- 4-tier system (Basic, Standard, Premium, Enterprise)
- KPI-based performance scoring
- Territory and geographic coverage

### Compliance & Security

- KYC document verification workflow
- Rule-based fraud detection with risk scoring
- CBN regulatory reporting (daily/weekly/monthly/quarterly)
- Complete audit trail with export
- Security score: 100/100 EXCELLENT

### Analytics & Reporting

- Real-time dashboard with transaction volume and revenue
- Automated weekly reports with comparison
- Configurable metric thresholds and alerts
- CSV/PDF data export

### User Experience

- 6 languages: English, French, Nigerian Pidgin, Hausa, Yoruba, Igbo
- Real-time notification center with WebSocket
- AI-powered live chat with proactive help
- Video tutorials for 5 complex features
- Searchable user guide with feedback ratings

### Infrastructure

- Docker Compose (16 services)
- Kubernetes (Helm chart with HPA, PDB, Ingress)
- 4 Grafana dashboards, 8 Prometheus alert rules
- GitHub Actions CI/CD pipeline
- Terraform IaC definitions

---

## API Documentation

OpenAPI 3.0 spec: `docs/openapi.json`

| Router       | Key Procedures                     |
| ------------ | ---------------------------------- |
| auth         | me, logout                         |
| transactions | list, create, get, update, reverse |
| agents       | list, create, get, update, onboard |
| fraud        | alerts, rules, score, resolve      |
| kyc          | submit, review, approve, reject    |
| settlement   | batches, process, reconcile        |
| reports      | weekly, comparison, custom         |
| stripe       | checkout, portal, history          |

---

## Database Schema

71 tables: users, agents, customers, terminals, transactions, transaction_fees, reversals, kyc_documents, kyc_reviews, fraud_alerts, fraud_rules, settlement_batches, commissions, float_ledger, audit_logs, cbn_reports, notifications, webhooks, rate_limits, api_keys, and more.

---

## Testing

```bash
pnpm test                              # All 1,200+ vitest tests
node scripts/smoke-test.mjs            # 25 smoke tests
node scripts/security-audit-v2.mjs     # Security audit
npx playwright test                    # E2E tests
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Phase 161 — Full Production Finalization (April 2026)

This phase completed all production finalization gaps:

### New Infrastructure

- **docker-compose.production.yml**: Added `mdm-compliance-engine`, `mdm-geofence-service`, `fluvio`, `dapr`, and `minio` services
- **infra/fluvio/**: Fluvio SmartModule directory with deploy script (`transaction-filter`, `fraud-enricher`, `mdm-heartbeat-parser`)
- **infra/apisix/bootstrap.sh**: APISix Admin API bootstrap script seeding all microservice routes
- **infra/tigerbeetle/provision.sh**: Full TigerBeetle account provisioning (float, commission, settlement, CBN reserve, suspense)
- **infra/minio/lifecycle/**: Bucket lifecycle policies (screenshots 30d, firmware 365d, lakehouse Bronze/Silver/Gold tiering)
- **scripts/bootstrap-production.sh**: One-command production bootstrap script

### OTA Service

- **server/ota-service/main.go**: Fixed placeholder download URL to real AWS S3 presigned URL generation (15-minute expiry, MinIO-compatible)

### CBN Reporting Engine

- **services/python/cbn-reporting-engine/scheduler.py**: APScheduler cron scheduler (daily 23:00 WAT, monthly 1st 01:00 WAT, weekly Sunday 02:00 WAT, quarterly 03:00 WAT)

### Monitoring

- **monitoring/prometheus/alerts/mdm.rules.yml**: MDM fleet alert rules (offline devices, compliance violations, OTA failures, battery critical, geofence spikes)
- **monitoring/prometheus/alerts/cbn.rules.yml**: CBN compliance alert rules (report failures, submission overdue, transaction limits, KYC compliance, suspicious transactions)
- **monitoring/grafana/dashboards/mdm-fleet.json**: MDM Fleet Overview Grafana dashboard
- **monitoring/grafana/dashboards/cbn-compliance.json**: CBN Compliance Grafana dashboard

### Testing

- **e2e/06-mdm-device-management.spec.ts**: Playwright E2E tests for MDM device management
- **e2e/07-cbn-compliance-reporting.spec.ts**: Playwright E2E tests for CBN compliance reporting
- **k6/mdm-ota-update.js**: k6 load test simulating 200 POS devices polling for OTA firmware updates

### CI/CD

- **.github/workflows/ci.yml**: Three new CI jobs — Playwright E2E, k6 OTA load test (main branch), Prometheus alert rule validation

### Makefile

- **Makefile.production**: Added Phase 161 targets — `up-mdm`, `up-fluvio`, `up-minio`, `minio-lifecycle`, `tigerbeetle-provision`, `apisix-bootstrap`, `ota-build`, `cbn-report-now`, `test-go-mdm`, `test-python`, `prometheus-lint`, `health-mdm`, `health-cbn`, `k6-ota`, `bootstrap-production`

### Documentation

- **PRODUCTION_READINESS_FINAL.md**: Comprehensive production readiness report with full architecture reference, deployment checklist, security checklist, CBN compliance matrix, and operational runbook
