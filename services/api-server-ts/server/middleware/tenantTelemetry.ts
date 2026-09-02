/**
 * tenantTelemetry.ts — Tenant context propagation for the POS Shell
 *
 * Express middleware that:
 *  - reads the tenant id from the `x-tenant-id` request header
 *    (defaults to "unknown" when absent),
 *  - stores it as OpenTelemetry baggage entry `tenant.id` on the active
 *    context so it propagates to downstream services (W3C Baggage),
 *  - stamps `tenant.id` as an attribute on the active span when one exists.
 *
 * This mirrors the Go shared middleware contract
 * (services/shared/middleware/otel.go: TenantIDFromRequest,
 * ContextWithTenant, TenantIDFromContext).
 */

import { context, propagation, trace } from "@opentelemetry/api";
import type { NextFunction, Request, Response } from "express";

export const TENANT_ID_BAGGAGE_KEY = "tenant.id";
export const TENANT_ID_HEADER = "x-tenant-id";
export const TENANT_ID_UNKNOWN = "unknown";

/**
 * tenantTelemetryMiddleware attaches tenant.id baggage + span attribute to
 * every incoming request, then runs the rest of the middleware chain inside
 * the enriched context so downstream code (and outgoing HTTP calls) inherit
 * the tenant baggage automatically.
 */
export function tenantTelemetryMiddleware(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  const raw = req.headers[TENANT_ID_HEADER];
  const tenantId =
    (Array.isArray(raw) ? raw[0] : raw)?.trim() || TENANT_ID_UNKNOWN;

  const bag = propagation.createBaggage({
    [TENANT_ID_BAGGAGE_KEY]: { value: tenantId },
  });
  const ctx = propagation.setBaggage(context.active(), bag);

  const span = trace.getActiveSpan();
  if (span) {
    span.setAttribute(TENANT_ID_BAGGAGE_KEY, tenantId);
  }

  context.with(ctx, () => next());
}

/**
 * getTenantIdFromContext returns the tenant id carried on the active OTel
 * context via baggage, or "unknown" when no tenant context is present
 * (e.g. background crons).
 */
export function getTenantIdFromContext(): string {
  const bag = propagation.getBaggage(context.active());
  return bag?.getEntry(TENANT_ID_BAGGAGE_KEY)?.value ?? TENANT_ID_UNKNOWN;
}
