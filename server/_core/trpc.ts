import { NOT_ADMIN_ERR_MSG, UNAUTHED_ERR_MSG } from "@shared/const";
import { initTRPC, TRPCError } from "@trpc/server";
import superjson from "superjson";
import type { TrpcContext } from "./context";
import { permifyCheck } from "../_core/permify";
import { createObservabilityMiddleware } from "../middleware/observabilityMiddleware";
import { createSidecarMiddleware } from "../middleware/sidecarIntegration";
import { createTrpcCacheMiddleware } from "../middleware/trpcCacheMiddleware";
import { createProductionHardeningMiddleware } from "../middleware/productionHardeningMiddleware";

const t = initTRPC.context<TrpcContext>().create({
  transformer: superjson,
});

export const router = t.router;
export const middleware = t.middleware;

// ── Observability middleware: instruments ALL procedures with Kafka, Redis,
//    Fluvio, TigerBeetle (fire-and-forget, fail-open) ────────────────────────
const observability = createObservabilityMiddleware(t);
const sidecarMiddleware = createSidecarMiddleware(t);
const trpcCache = createTrpcCacheMiddleware(t);
const productionHardening = createProductionHardeningMiddleware(t);

// ── Input Sanitization middleware: XSS/injection detection on all inputs ──────
function containsMaliciousPatterns(input: unknown): boolean {
  if (typeof input === "string") {
    if (
      /<script[\s>]/i.test(input) ||
      /javascript:/i.test(input) ||
      /on\w+\s*=/i.test(input)
    )
      return true;
    if (
      /(\b(DROP|DELETE|INSERT|UPDATE|ALTER)\b.*;\s*(DROP|DELETE|INSERT|UPDATE|ALTER))/i.test(
        input
      )
    )
      return true;
    return false;
  }
  if (Array.isArray(input)) return input.some(containsMaliciousPatterns);
  if (input !== null && typeof input === "object") {
    return Object.values(input as Record<string, unknown>).some(
      containsMaliciousPatterns
    );
  }
  return false;
}

const inputSanitization = t.middleware(async opts => {
  const { next, getRawInput } = opts;
  const rawInput = await getRawInput();
  if (rawInput !== undefined && containsMaliciousPatterns(rawInput)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: "Input contains potentially malicious content",
    });
  }
  return next();
});

// Base: t.procedure.use(observability) applied to all procedure levels
export const publicProcedure = t.procedure
  .use(inputSanitization)
  .use(observability)
  .use(sidecarMiddleware)
  .use(trpcCache)
  .use(productionHardening);

// ── requireUser: verify JWT session ──────────────────────────────────────────
const requireUser = t.middleware(async opts => {
  const { ctx, next } = opts;

  if (!ctx.user) {
    throw new TRPCError({ code: "UNAUTHORIZED", message: UNAUTHED_ERR_MSG });
  }

  return next({
    ctx: {
      ...ctx,
      user: ctx.user,
    },
  });
});

// ── requirePermify: enforce Permify "can_access" check for authenticated users
// Falls back gracefully when Permify is unavailable (returns true = allow).
const requirePermify = t.middleware(async opts => {
  const { ctx, next } = opts;

  if (!ctx.user) {
    throw new TRPCError({ code: "UNAUTHORIZED", message: UNAUTHED_ERR_MSG });
  }

  // Permify check: user:<userId> can "access" system:pos-shell
  // This is the base access gate — resource-level checks are done per-procedure.
  const allowed = await permifyCheck({
    subjectType: "user",
    subjectId: String(ctx.user.id),
    entityType: "system",
    entityId: "pos-shell",
    permission: "access",
  });

  if (!allowed) {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Access denied by authorization policy",
    });
  }

  return next({
    ctx: {
      ...ctx,
      user: ctx.user,
    },
  });
});

// ── protectedProcedure: JWT auth + Permify base access check ─────────────────
// Chain: protectedProcedure = t.procedure.use(observability).use(requireUser).use(requirePermify)
export const protectedProcedure = t.procedure
  .use(inputSanitization)
  .use(observability)
  .use(sidecarMiddleware)
  .use(trpcCache)
  .use(productionHardening)
  .use(requireUser)
  .use(requirePermify);

// ── adminProcedure: JWT auth + role=admin + Permify admin check ───────────────
// Chain: adminProcedure = t.procedure.use(observability).use(requireUser).use(requireAdmin)
export const adminProcedure = t.procedure
  .use(inputSanitization)
  .use(observability)
  .use(sidecarMiddleware)
  .use(
    t.middleware(async opts => {
      const { ctx, next } = opts;

      if (!ctx.user) {
        throw new TRPCError({
          code: "UNAUTHORIZED",
          message: UNAUTHED_ERR_MSG,
        });
      }

      if (ctx.user.role !== "admin") {
        throw new TRPCError({ code: "FORBIDDEN", message: NOT_ADMIN_ERR_MSG });
      }

      // Permify check: user:<userId> can "admin_access" system:pos-shell
      const allowed = await permifyCheck({
        subjectType: "user",
        subjectId: String(ctx.user.id),
        entityType: "system",
        entityId: "pos-shell",
        permission: "admin_access",
      });

      if (!allowed) {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "Admin access denied by authorization policy",
        });
      }

      return next({
        ctx: {
          ...ctx,
          user: ctx.user,
        },
      });
    })
  );
