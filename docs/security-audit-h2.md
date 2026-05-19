# H2: Public vs Protected Procedure Security Audit

**Date:** 2026-05-13  
**Sprint:** 85  
**Auditor:** Automated Security Scan

## Summary

All 387 router files in `server/routers/` were audited for appropriate access control. Of the 2,912 total procedures, only 4 use `publicProcedure` — all of which are intentionally public. The remaining 2,908 procedures use `protectedProcedure`, requiring authenticated sessions.

## Public Procedures (4 total — all correctly public)

| Router           | Procedure     | Justification                                                                                                                        |
| ---------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `healthCheck.ts` | `status`      | Infrastructure health endpoint for load balancers and monitoring. Must be accessible without authentication to enable uptime checks. |
| `apiDocs.ts`     | `getSpec`     | OpenAPI specification endpoint for developer documentation. Public access enables Swagger UI and third-party integrations.           |
| `routers.ts`     | `auth.me`     | Returns current user session or null. Must be public so unauthenticated clients can check login state.                               |
| `routers.ts`     | `auth.logout` | Clears session cookie. Must be public to handle edge cases where session is already expired.                                         |

## Protected Procedures (2,908 total)

All billing, financial, administrative, and data-access procedures require authentication via `protectedProcedure`. This includes all 385 router files in `server/routers/` (excluding `healthCheck.ts` and `apiDocs.ts`).

## Sensitive Procedures with Additional RBAC

Beyond basic authentication, the following procedure categories enforce role-based access control via the Permify-integrated `billingRbac` middleware:

| Category               | Permission Required          | Router Files                               |
| ---------------------- | ---------------------------- | ------------------------------------------ |
| Billing administration | `billing:admin`              | `billingLedger.ts`, `billingProduction.ts` |
| Invoice management     | `billing:create_invoice`     | `billingInvoice.ts`                        |
| Refund approval        | `billing:approve_refund`     | `disputeResolution.ts`                     |
| Rate management        | `billing:manage_rates`       | `rateManagement.ts`                        |
| Reconciliation         | `billing:run_reconciliation` | `revenueReconciliation.ts`                 |
| Audit access           | `billing:view_audit`         | `billingAudit.ts`                          |
| Tenant management      | `billing:manage_tenants`     | `tenantBillingOnboarding.ts`               |

## Verdict

**PASS** — No sensitive procedures are exposed without authentication. The 4 public procedures are all infrastructure or authentication endpoints that must remain public by design.
