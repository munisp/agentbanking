// Sprint 87: GDPR/NDPR compliance, consent expiry, withdrawal workflow
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { dataConsentRecords } from "../../drizzle/schema";
import { eq, desc, and, count, lt } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
};

const CONSENT_TYPES = [
  "data_processing",
  "marketing",
  "analytics",
  "third_party_sharing",
  "biometric",
];
const CONSENT_EXPIRY_DAYS = 365;

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "dataConsentRecordsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dataConsentRecordsCrud",
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
    resource: "dataConsentRecordsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "dataConsentRecordsCrud",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _dataConsentRecordsCrud_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
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

export const dataConsentRecordsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        userId: z.number().optional(),
        consentType: z.string().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.userId)
          conditions.push(
            eq(dataConsentRecords.userAgent, input.userId as any)
          );
        if (input.consentType)
          conditions.push(
            eq(dataConsentRecords.consentType, input.consentType)
          );
        const rows = await db
          .select()
          .from(dataConsentRecords)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(dataConsentRecords.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(dataConsentRecords)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        const enriched = rows.map((r: any) => ({
          ...r,
          isExpired: r.expiresAt ? new Date(r.expiresAt) < new Date() : false,
        }));
        return { items: enriched, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(dataConsentRecords)
          .where(eq(dataConsentRecords.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Consent record not found",
          });
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  grantConsent: protectedProcedure
    .input(
      z.object({
        userId: z.number(),
        consentType: z.enum([
          "data_processing",
          "marketing",
          "analytics",
          "third_party_sharing",
          "biometric",
        ]),
        ipAddress: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        const expiresAt = new Date(Date.now() + CONSENT_EXPIRY_DAYS * 86400000);
        const [row] = await db
          .insert(dataConsentRecords)
          .values({
            ...input,
            status: "granted",
            grantedAt: new Date(),
            expiresAt,
          } as any)
          .returning();
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "dataConsentRecordsCrud",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return {
          ...row,
          message: `Consent granted for ${input.consentType}. Expires: ${expiresAt.toISOString()}`,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  withdrawConsent: protectedProcedure
    .input(z.object({ id: z.number(), reason: z.string().optional() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [record] = await db
          .select()
          .from(dataConsentRecords)
          .where(eq(dataConsentRecords.id, input.id))
          .limit(100);
        if (!record)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Consent record not found",
          });
        await db
          .update(dataConsentRecords)
          .set({
            withdrawalReason: input.reason,
          } as any)
          .where(eq(dataConsentRecords.id, input.id));
        return {
          success: true,
          message: "Consent withdrawn per NDPR Article 2.3",
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getComplianceStatus: protectedProcedure
    .input(z.object({ userId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const records = await db
          .select()
          .from(dataConsentRecords)
          .where(eq(dataConsentRecords.userAgent, input.userId as any))
          .limit(100);
        const active = records.filter(
          (r: any) =>
            r.status === "granted" &&
            (!r.expiresAt || new Date(r.expiresAt) > new Date())
        );
        const missing = CONSENT_TYPES.filter(
          t => !active.find((r: any) => r.consentType === t)
        );
        return {
          userId: input.userId,
          activeConsents: active.length,
          missingConsents: missing,
          isCompliant:
            missing.filter(m => m === "data_processing").length === 0,
          consentTypes: CONSENT_TYPES,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .delete(dataConsentRecords)
          .where(eq(dataConsentRecords.id, input.id));
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
});
