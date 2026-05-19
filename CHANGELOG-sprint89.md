# Sprint 89 — Change Manifest

**Sprint**: 89
**Date**: 2026-05-13
**Theme**: Stripe Checkout, PBAC Admin Dashboard, Fluvio→OpenSearch Pipeline

---

## Summary

Sprint 89 delivers three major capabilities: (1) production-grade Stripe checkout flow with user-linked subscriptions and webhook handling, (2) role-gated admin dashboard with PBAC enforcement via Permify, and (3) a Fluvio→OpenSearch real-time analytics pipeline with Rust consumer and Python indexer services.

---

## Changes by Category

### Stripe Checkout Flow (S89-01 to S89-06)

| ID     | Description                                                                                             | Files                                                                 |
| ------ | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| S89-01 | Added `stripe_customer_id`, `stripe_subscription_id`, `stripe_plan_id` to users schema                  | `drizzle/schema.ts`                                                   |
| S89-02 | Registered `/api/stripe/webhook` route with `express.raw()` before `express.json()`                     | `server/_core/index.ts`                                               |
| S89-03 | Upgraded stripeRouter with `protectedProcedure`, user linking, Stripe customer creation                 | `server/stripe/stripeRouter.ts`                                       |
| S89-04 | Enhanced webhookHandler: test event detection (`evt_test_`), checkout→user linking, subscription events | `server/stripe/webhookHandler.ts`                                     |
| S89-05 | Rebuilt Payments.tsx with subscription plans, one-time products, payment history, billing portal        | `client/src/pages/Payments.tsx`                                       |
| S89-06 | Created PaymentSuccess and PaymentCancel callback pages, wired routes                                   | `client/src/pages/PaymentSuccess.tsx`, `PaymentCancel.tsx`, `App.tsx` |

### Role-Based Admin Dashboard (S89-07 to S89-12)

| ID     | Description                                                                                                                          | Files                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| S89-07 | adminProcedure already existed with role=admin + Permify `admin_access` check                                                        | `server/_core/trpc.ts` (existing)          |
| S89-08 | Created adminDashboard tRPC router: getSystemStats, listUsers, updateUserRole, getAuditLog, getBillingLedgerSummary, getSystemHealth | `server/routers/adminDashboard.ts`         |
| S89-09 | Created AdminDashboard page with stats grid, user table, health panel, audit log                                                     | `client/src/pages/AdminDashboard.tsx`      |
| S89-10 | Created AdminUserManagement page with search, filter, role toggle                                                                    | `client/src/pages/AdminUserManagement.tsx` |
| S89-11 | Created AdminSystemHealth page with memory, uptime, pipeline health                                                                  | `client/src/pages/AdminSystemHealth.tsx`   |
| S89-12 | Wired admin routes in App.tsx: `/admin-dashboard`, `/admin/users`, `/admin/health`, `/transaction-analytics`                         | `client/src/App.tsx`                       |

### Fluvio→OpenSearch Pipeline (S89-13 to S89-18)

| ID     | Description                                                                                      | Files                                       |
| ------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| S89-13 | Created Fluvio consumer Rust service: batch buffering, retry logic, health endpoint              | `services/rust/fluvio-consumer/`            |
| S89-14 | Created OpenSearch indexer Python service: bulk indexing, search proxy, metrics                  | `services/python/opensearch-indexer/`       |
| S89-15 | Created analyticsQuery tRPC router: getTransactionMetrics, searchTransactions, getPipelineHealth | `server/routers/analyticsQuery.ts`          |
| S89-16 | Created TransactionAnalytics dashboard: volume metrics, time-series bars, search, pipeline info  | `client/src/pages/TransactionAnalytics.tsx` |
| S89-17 | Pipeline health endpoint in analyticsQuery router (OpenSearch cluster health check)              | `server/routers/analyticsQuery.ts`          |
| S89-18 | Docker Compose for analytics stack: OpenSearch, Dashboards, Indexer, Consumer                    | `services/docker-compose.analytics.yml`     |

### Tests (S89-T)

| Test Suite                | Tests  | Status         |
| ------------------------- | ------ | -------------- |
| webhookHandler unit tests | 7      | All pass       |
| adminDashboard RBAC tests | 5      | All pass       |
| analyticsQuery auth tests | 3      | All pass       |
| **Total**                 | **15** | **15/15 pass** |

---

## New Files

```
server/routers/adminDashboard.ts
server/routers/analyticsQuery.ts
server/sprint89.test.ts
client/src/pages/PaymentSuccess.tsx
client/src/pages/PaymentCancel.tsx
client/src/pages/AdminDashboard.tsx
client/src/pages/AdminUserManagement.tsx
client/src/pages/AdminSystemHealth.tsx
client/src/pages/TransactionAnalytics.tsx
services/rust/fluvio-consumer/Cargo.toml
services/rust/fluvio-consumer/Dockerfile
services/rust/fluvio-consumer/src/main.rs
services/python/opensearch-indexer/main.py
services/python/opensearch-indexer/requirements.txt
services/python/opensearch-indexer/Dockerfile
services/docker-compose.analytics.yml
CHANGELOG-sprint89.md
```

## Modified Files

```
drizzle/schema.ts (stripe fields on users)
server/_core/index.ts (webhook route registration)
server/stripe/stripeRouter.ts (protectedProcedure, user linking)
server/stripe/webhookHandler.ts (test events, user linking, subscription events)
server/routers.ts (adminDashboard + analyticsQuery wiring)
client/src/App.tsx (new routes + imports)
client/src/pages/Payments.tsx (full rebuild)
todo.md (Sprint 89 items marked complete)
```

---

## Architecture Notes

- **Stripe webhook handler** now detects test events (`evt_test_*`) and returns `{ verified: true }` for sandbox verification
- **User linking**: checkout.session.completed, subscription.created/updated/deleted events update user's Stripe fields in DB
- **Admin dashboard** uses `adminProcedure` which chains: JWT auth → role=admin check → Permify `admin_access` permission
- **Analytics pipeline**: Fluvio (Rust) → HTTP POST → OpenSearch Indexer (Python) → OpenSearch; tRPC router falls back to DB when OpenSearch is unavailable
- **Docker Compose** (`services/docker-compose.analytics.yml`) orchestrates the full analytics stack
