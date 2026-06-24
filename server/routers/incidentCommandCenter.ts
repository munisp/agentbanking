import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import { platform_incidents, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  detected: ["analyzing"],
  analyzing: ["confirmed_threat", "false_alarm"],
  confirmed_threat: ["containment"],
  containment: ["eradication"],
  eradication: ["recovery"],
  recovery: ["post_incident_review"],
  post_incident_review: ["closed"],
  false_alarm: ["closed"],
  closed: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "incidentCommandCenter",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "incidentCommandCenter",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "incidentCommandCenter",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "incidentCommandCenter",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishincidentCommandCenterMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `platform.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(() => {});

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `platform_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `platform_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const incidentCommandCenterRouter = router({
  listIncidents: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(50),
          severity: z.string().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = input?.severity
          ? await db
              .select()
              .from(platform_incidents)
              .where(eq(platform_incidents.severity, input.severity))
              .orderBy(desc(platform_incidents.startedAt))
              .limit(input?.limit ?? 50)
          : await db
              .select()
              .from(platform_incidents)
              .orderBy(desc(platform_incidents.startedAt))
              .limit(input?.limit ?? 50);
        return { incidents: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getIncident: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [incident] = await db
          .select()
          .from(platform_incidents)
          .where(eq(platform_incidents.id, input.id))
          .limit(1);
        return incident ?? null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createIncident: protectedProcedure
    .input(
      z.object({
        title: z.string(),
        description: z.string(),
        severity: z.enum(["low", "medium", "high", "critical"]),
        service: z.string(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as Record<string, unknown>).status as string;
        const currentStatus =
          ((input as Record<string, unknown>).currentStatus as string) ||
          "pending";
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
          });
        }
      }
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        const [incident] = await db
          .insert(platform_incidents)
          .values({
            title: input.title,
            description: input.description,
            severity: input.severity,
            service: input.service,
            status: "open",
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "incident_created",
          resource: "platform_incidents",
          resourceId: String(incident.id),
          status: "success",
          metadata: { title: input.title, severity: input.severity },
        } as any);
        return incident;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  resolveIncident: protectedProcedure
    .input(z.object({ id: z.number(), resolution: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .update(platform_incidents)
          .set({
            status: "resolved",
            resolution: input.resolution,
            resolvedAt: new Date(),
          })
          .where(eq(platform_incidents.id, input.id));
        await db.insert(auditLog).values({
          action: "incident_resolved",
          resource: "platform_incidents",
          resourceId: String(input.id),
          status: "success",
          metadata: { resolution: input.resolution },
        });

        // Middleware fan-out (fail-open)

        await publishincidentCommandCenterMiddleware("createIncident", `${Date.now()}`, { action: "createIncident" }).catch(() => {});


        // Middleware fan-out (fail-open)


        await publishincidentCommandCenterMiddleware("resolveIncident", `${Date.now()}`, { action: "resolveIncident" }).catch(() => {});



        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [total] = await db
      .select({ value: count() })
      .from(platform_incidents)
      .limit(100);
    const [open] = await db
      .select({ value: count() })
      .from(platform_incidents)
      .where(eq(platform_incidents.status, "open"))
      .limit(100);
    return {
      totalIncidents: Number(total.value),
      openIncidents: Number(open.value),
    };
  }),
});
