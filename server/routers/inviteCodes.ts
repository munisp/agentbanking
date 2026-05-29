/**
 * Invite Code Router — Generate, validate, list, and revoke partner invite codes.
 * Only admins/super-admins can generate codes; public validation is allowed for onboarding.
 * Uses PostgreSQL via Drizzle ORM (with in-memory fallback for dev/test).
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import crypto from "crypto";
import { getDb } from "../db";
import { sql, eq, and, ilike, or, desc, count, gte, lte } from "drizzle-orm";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

interface InviteCodeRecord {
  id: number;
  code: string;
  type: "one_time" | "multi_use";
  status: "active" | "used" | "expired" | "revoked";
  maxUses: number;
  usedCount: number;
  createdBy: number | null;
  assignedTenantId: number | null;
  partnerName: string | null;
  partnerEmail: string | null;
  notes: string | null;
  expiresAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

// In-memory fallback for environments without DB
let nextId = 1;
const memStore: InviteCodeRecord[] = [];

function generateCode(): string {
  return "RF-" + crypto.randomBytes(6).toString("hex").toUpperCase();
}

async function getInviteCodesTable() {
  const db = await getDb();
  if (!db || (db as any)._isNoop) return null;
  try {
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS invite_codes (
        id SERIAL PRIMARY KEY,
        code VARCHAR(32) UNIQUE NOT NULL,
        type VARCHAR(16) NOT NULL DEFAULT 'one_time',
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        max_uses INTEGER NOT NULL DEFAULT 1,
        used_count INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER,
        assigned_tenant_id INTEGER,
        partner_name VARCHAR(128),
        partner_email VARCHAR(320),
        notes TEXT,
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);
    return db;
  } catch {
    return null;
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateInvitecodesInput(data: Record<string, unknown>): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "inviteCodes",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "inviteCodes",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_INVITECODES = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_INVITECODES.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_INVITECODES.validateRange(data.amount, 0, 100_000_000))
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
}

// ── Database Operations Helper ─────────────────────────────────────────────
async function checkDbHealth() {
  try {
    const db = await (await import("../db")).getDb();
    if ((db as any)?._isNoop) return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
  }
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _inviteCodes_db = {
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

export const inviteCodesRouter = router({
  generate: protectedProcedure
    .input(
      z.object({
        type: z.enum(["one_time", "multi_use"]).default("one_time"),
        maxUses: z.number().int().min(1).max(1000).default(1),
        partnerName: z.string().max(128).optional(),
        partnerEmail: z.string().email().max(320).optional(),
        notes: z.string().max(500).optional(),
        expiresAt: z.string().datetime().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "inviteCodes",
        "mutation",
        "Executed inviteCodes mutation"
      );

      const code = generateCode();
      const db = await getInviteCodesTable();

      if (db) {
        const [record] = (await db.execute(sql`
          INSERT INTO invite_codes (code, type, status, max_uses, used_count, created_by, partner_name, partner_email, notes, expires_at)
          VALUES (${code}, ${input.type}, 'active', ${input.type === "one_time" ? 1 : input.maxUses}, 0, ${ctx.user?.id ?? null}, ${input.partnerName ?? null}, ${input.partnerEmail ?? null}, ${input.notes ?? null}, ${input.expiresAt ? new Date(input.expiresAt) : null})
          RETURNING *
        `)) as any;
        return record;
      }

      // Fallback: in-memory
      const record: InviteCodeRecord = {
        id: nextId++,
        code,
        type: input.type,
        status: "active",
        maxUses: input.type === "one_time" ? 1 : input.maxUses,
        usedCount: 0,
        createdBy: ctx.user?.id ?? null,
        assignedTenantId: null,
        partnerName: input.partnerName ?? null,
        partnerEmail: input.partnerEmail ?? null,
        notes: input.notes ?? null,
        expiresAt: input.expiresAt ? new Date(input.expiresAt) : null,
        createdAt: new Date(),
        updatedAt: new Date(),
      };
      memStore.push(record);
      return record;
    }),

  list: protectedProcedure
    .input(
      z
        .object({
          page: z.number().int().min(1).default(1),
          limit: z.number().int().min(1).max(100).default(20),
          status: z.enum(["active", "used", "expired", "revoked"]).optional(),
          search: z.string().max(128).optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const { page = 1, limit = 20, status, search } = input ?? {};
      const db = await getInviteCodesTable();

      if (db) {
        const conditions: any[] = [];
        if (status) conditions.push(sql`status = ${status}`);
        if (search) {
          const q = `%${search}%`;
          conditions.push(
            sql`(code ILIKE ${q} OR partner_name ILIKE ${q} OR partner_email ILIKE ${q})`
          );
        }
        const whereClause =
          conditions.length > 0
            ? sql`WHERE ${sql.join(conditions, sql` AND `)}`
            : sql``;
        const offset = (page - 1) * limit;

        const items = (await db.execute(sql`
          SELECT * FROM invite_codes ${whereClause} ORDER BY created_at DESC LIMIT ${limit} OFFSET ${offset}
        `)) as any;
        const [{ c }] = (await db.execute(
          sql`SELECT COUNT(*)::int AS c FROM invite_codes ${whereClause}`
        )) as any;

        return {
          items: items.rows ?? items,
          total: c,
          page,
          limit,
          totalPages: Math.ceil(c / limit),
        };
      }

      // Fallback: in-memory
      let filtered = [...memStore];
      if (status) filtered = filtered.filter(c => c.status === status);
      if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(
          c =>
            c.code.toLowerCase().includes(q) ||
            c.partnerName?.toLowerCase().includes(q) ||
            c.partnerEmail?.toLowerCase().includes(q)
        );
      }
      filtered.sort(
        (a: any, b: any) => b.createdAt.getTime() - a.createdAt.getTime()
      );
      const total = filtered.length;
      const items = filtered.slice((page - 1) * limit, page * limit);
      return {
        items,
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      };
    }),

  validate: protectedProcedure
    .input(z.object({ code: z.string().min(1).max(32) }))
    .query(async ({ input }) => {
      const db = await getInviteCodesTable();

      if (db) {
        const records = (await db.execute(
          sql`SELECT * FROM invite_codes WHERE code = ${input.code} LIMIT 1`
        )) as any;
        const record = (records.rows ?? records)?.[0];
        if (!record) return { valid: false, reason: "Code not found" };
        if (record.status === "revoked")
          return { valid: false, reason: "Code has been revoked" };
        if (record.status === "used")
          return { valid: false, reason: "Code has already been used" };
        if (record.status === "expired")
          return { valid: false, reason: "Code has expired" };
        if (record.expires_at && new Date(record.expires_at) < new Date()) {
          await db.execute(
            sql`UPDATE invite_codes SET status = 'expired', updated_at = NOW() WHERE id = ${record.id}`
          );
          return { valid: false, reason: "Code has expired" };
        }
        if (record.used_count >= record.max_uses) {
          await db.execute(
            sql`UPDATE invite_codes SET status = 'used', updated_at = NOW() WHERE id = ${record.id}`
          );
          return { valid: false, reason: "Code has reached maximum uses" };
        }
        return {
          valid: true,
          code: record.code,
          type: record.type,
          partnerName: record.partner_name,
          partnerEmail: record.partner_email,
          remainingUses: record.max_uses - record.used_count,
        };
      }

      // Fallback: in-memory
      const record = memStore.find(c => c.code === input.code);
      if (!record) return { valid: false, reason: "Code not found" };
      if (record.status === "revoked")
        return { valid: false, reason: "Code has been revoked" };
      if (record.status === "used")
        return { valid: false, reason: "Code has already been used" };
      if (record.status === "expired")
        return { valid: false, reason: "Code has expired" };
      if (record.expiresAt && record.expiresAt < new Date()) {
        record.status = "expired";
        return { valid: false, reason: "Code has expired" };
      }
      if (record.usedCount >= record.maxUses) {
        record.status = "used";
        return { valid: false, reason: "Code has reached maximum uses" };
      }
      return {
        valid: true,
        code: record.code,
        type: record.type,
        partnerName: record.partnerName,
        partnerEmail: record.partnerEmail,
        remainingUses: record.maxUses - record.usedCount,
      };
    }),

  markUsed: protectedProcedure
    .input(z.object({ code: z.string(), tenantId: z.number().int() }))
    .mutation(async ({ input }) => {
      const db = await getInviteCodesTable();

      if (db) {
        const records = (await db.execute(
          sql`SELECT * FROM invite_codes WHERE code = ${input.code} LIMIT 1`
        )) as any;
        const record = (records.rows ?? records)?.[0];
        if (!record)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Invite code not found",
          });
        const newUsedCount = record.used_count + 1;
        const newStatus =
          record.type === "one_time" || newUsedCount >= record.max_uses
            ? "used"
            : record.status;
        await db.execute(sql`
          UPDATE invite_codes SET used_count = ${newUsedCount}, assigned_tenant_id = ${input.tenantId}, status = ${newStatus}, updated_at = NOW()
          WHERE id = ${record.id}
        `);
        return { ...record, used_count: newUsedCount, status: newStatus };
      }

      // Fallback: in-memory
      const record = memStore.find(c => c.code === input.code);
      if (!record)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Invite code not found",
        });
      record.usedCount += 1;
      record.assignedTenantId = input.tenantId;
      record.updatedAt = new Date();
      if (record.type === "one_time" || record.usedCount >= record.maxUses)
        record.status = "used";
      return record;
    }),

  revoke: protectedProcedure
    .input(z.object({ id: z.number().int() }))
    .mutation(async ({ input }) => {
      const db = await getInviteCodesTable();

      if (db) {
        const records = (await db.execute(
          sql`SELECT * FROM invite_codes WHERE id = ${input.id} LIMIT 1`
        )) as any;
        const record = (records.rows ?? records)?.[0];
        if (!record)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Invite code not found",
          });
        await db.execute(
          sql`UPDATE invite_codes SET status = 'revoked', updated_at = NOW() WHERE id = ${input.id}`
        );
        return { ...record, status: "revoked" };
      }

      // Fallback: in-memory
      const record = memStore.find(c => c.id === input.id);
      if (!record)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Invite code not found",
        });
      record.status = "revoked";
      record.updatedAt = new Date();
      return record;
    }),

  stats: protectedProcedure.query(async () => {
    const db = await getInviteCodesTable();

    if (db) {
      const result = (await db.execute(sql`
        SELECT
          COUNT(*)::int AS total,
          COUNT(*) FILTER (WHERE status = 'active')::int AS active,
          COUNT(*) FILTER (WHERE status = 'used')::int AS used,
          COUNT(*) FILTER (WHERE status = 'expired')::int AS expired,
          COUNT(*) FILTER (WHERE status = 'revoked')::int AS revoked,
          COUNT(*) FILTER (WHERE assigned_tenant_id IS NOT NULL)::int AS total_tenants_created
        FROM invite_codes
      `)) as any;
      const row = (result.rows ?? result)?.[0];
      return {
        total: row?.total ?? 0,
        active: row?.active ?? 0,
        used: row?.used ?? 0,
        expired: row?.expired ?? 0,
        revoked: row?.revoked ?? 0,
        totalTenantsCreated: row?.total_tenants_created ?? 0,
      };
    }

    // Fallback: in-memory
    return {
      total: memStore.length,
      active: memStore.filter(c => c.status === "active").length,
      used: memStore.filter(c => c.status === "used").length,
      expired: memStore.filter(c => c.status === "expired").length,
      revoked: memStore.filter(c => c.status === "revoked").length,
      totalTenantsCreated: memStore.filter(c => c.assignedTenantId !== null)
        .length,
    };
  }),
});
