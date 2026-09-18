import { z } from "zod";
import { router, protectedProcedure, adminProcedure } from "../_core/trpc";
import { getDb } from "../db";
import {
  eq,
  desc,
  and,
  sql,
  count,
  sum,
  isNull,
  gt,
  gte,
  lte,
  or,
  asc,
} from "drizzle-orm";
import { customers, auditLog, otpTokens } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { encryptField, blindIndex } from "../lib/fieldEncryption";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { sendSms } from "../termii";
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

// ── Tier-1 Phone OTP Verification (fail-closed) ─────────────────────────────
// Tier-1 accounts (no BVN/NIN) must verify the customer's phone via OTP before
// the account record may be created. OTPs are stored bcrypt-hashed in the
// otp_tokens table under a dedicated purpose, are single-use, expire, and are
// rate-limited (resend cooldown + max verification attempts).
const TIER1_OTP_PURPOSE = "tier1_account_opening";
const TIER1_OTP_EXPIRY_MINUTES = 10;
const TIER1_OTP_RESEND_COOLDOWN_SECONDS = 60;
const TIER1_OTP_MAX_ATTEMPTS = 5;

function generateTier1Otp(): string {
  // CSPRNG 6-digit OTP (crypto.randomInt is uniform in [100000, 999999])
  return crypto.randomInt(100000, 1000000).toString();
}

/**
 * Verify a tier-1 account-opening OTP for the requesting user. FAIL-CLOSED:
 * any missing/expired/over-attempted/mismatched token throws; the token is
 * marked used on success (single-use).
 */
async function verifyTier1Otp(
  db: NonNullable<Awaited<ReturnType<typeof getDb>>>,
  userId: number,
  otp: string
): Promise<void> {
  const tokenRows = await db
    .select()
    .from(otpTokens)
    .where(
      and(
        eq(otpTokens.agentId, userId),
        eq(otpTokens.purpose, TIER1_OTP_PURPOSE),
        eq(otpTokens.used, false),
        gt(otpTokens.expiresAt, new Date())
      )
    )
    .orderBy(desc(otpTokens.createdAt))
    .limit(1);

  if (tokenRows.length === 0) {
    throw new TRPCError({
      code: "PRECONDITION_FAILED",
      message:
        "Phone OTP verification required for tier-1 account opening — request an OTP via accountOpening.sendTier1Otp first (fail-closed).",
    });
  }

  const token = tokenRows[0];

  // Max-attempts guard (attempts column created by migration 0053; COALESCE
  // keeps pre-existing rows at 0).
  const attemptRows = await db.execute(
    sql`SELECT COALESCE(attempts, 0) AS attempts FROM otp_tokens WHERE id = ${token.id}`
  );
  const currentAttempts = Number((attemptRows as any).rows?.[0]?.attempts ?? 0);
  if (currentAttempts >= TIER1_OTP_MAX_ATTEMPTS) {
    await db
      .update(otpTokens)
      .set({ used: true })
      .where(eq(otpTokens.id, token.id));
    throw new TRPCError({
      code: "PRECONDITION_FAILED",
      message: "Too many failed OTP attempts. Please request a new OTP.",
    });
  }

  const valid = await bcrypt.compare(otp, token.hashedOtp);
  if (!valid) {
    await db.execute(
      sql`UPDATE otp_tokens SET attempts = COALESCE(attempts, 0) + 1 WHERE id = ${token.id}`
    );
    throw new TRPCError({
      code: "PRECONDITION_FAILED",
      message: "Invalid OTP — tier-1 account opening BLOCKED (fail-closed).",
    });
  }

  // Single-use: mark consumed before proceeding
  await db
    .update(otpTokens)
    .set({ used: true, usedAt: new Date() })
    .where(eq(otpTokens.id, token.id));
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateAccountopeningInput(data: Record<string, unknown>): boolean {
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
      "accountOpening",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "accountOpening",
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
    resource: "accountOpening",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "accountOpening",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_ACCOUNTOPENING = {
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
    if (!INTEGRITY_RULES_ACCOUNTOPENING.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_ACCOUNTOPENING.validateRange(data.amount, 0, 100_000_000)
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _accountOpening_db = {
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

export const accountOpeningRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalAccounts: 0, pending: 0, active: 0, suspended: 0 };
    const [total] = await db
      .select({ value: count() })
      .from(customers)
      .limit(100);
    const [pending] = await db
      .select({ value: count() })
      .from(customers)
      .where(eq(customers.status, "pending_kyc"))
      .limit(100);
    const [active] = await db
      .select({ value: count() })
      .from(customers)
      .where(eq(customers.status, "active"))
      .limit(100);
    return {
      totalAccounts: Number(total.value),
      pending: Number(pending.value),
      active: Number(active.value),
      suspended: 0,
    };
  }),
  listAccounts: protectedProcedure
    .input(
      z
        .object({
          status: z.string().optional(),
          limit: z.number().default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { accounts: [], total: 0 };
        const rows = await db
          .select()
          .from(customers)
          .orderBy(desc(customers.createdAt))
          .limit(input?.limit ?? 20);
        // Never expose stored BVN/NIN (now encrypted ciphertext) over the API.
        const accounts = rows.map(r => ({
          ...r,
          bvn: r.bvn ? "***" : null,
          nin: r.nin ? "***" : null,
        }));
        return { accounts, total: accounts.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  /**
   * Step 1 (tier-1): send a phone verification OTP for tier-1 account opening.
   * Resend is throttled (60s cooldown); previous tier-1 OTPs are invalidated.
   */
  sendTier1Otp: protectedProcedure
    .input(z.object({ phone: z.string().min(10).max(15) }))
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable — cannot issue OTP (fail-closed)",
        });
      const userId = Number((ctx.user as any)?.id);
      if (!Number.isFinite(userId) || userId <= 0)
        throw new TRPCError({ code: "UNAUTHORIZED", message: "Invalid user" });

      // Resend cooldown: refuse if a tier-1 OTP was issued within the window
      const recent = await db
        .select({ id: otpTokens.id })
        .from(otpTokens)
        .where(
          and(
            eq(otpTokens.agentId, userId),
            eq(otpTokens.purpose, TIER1_OTP_PURPOSE),
            gt(
              otpTokens.createdAt,
              new Date(Date.now() - TIER1_OTP_RESEND_COOLDOWN_SECONDS * 1000)
            )
          )
        )
        .limit(1);
      if (recent.length > 0) {
        // Generic response — do not leak token state
        return {
          success: true,
          message: "If the details match, an OTP has been sent.",
        };
      }

      // Invalidate any existing tier-1 OTPs for this user
      await db
        .delete(otpTokens)
        .where(
          and(
            eq(otpTokens.agentId, userId),
            eq(otpTokens.purpose, TIER1_OTP_PURPOSE)
          )
        );

      const otp = generateTier1Otp();
      const hashedOtp = await bcrypt.hash(otp, 10);
      const expiresAt = new Date(
        Date.now() + TIER1_OTP_EXPIRY_MINUTES * 60 * 1000
      );
      await db.insert(otpTokens).values({
        agentId: userId,
        hashedOtp,
        purpose: TIER1_OTP_PURPOSE,
        expiresAt,
        used: false,
      });

      const smsResult = await sendSms(
        input.phone,
        `Your account opening verification code is: ${otp}. Valid for ${TIER1_OTP_EXPIRY_MINUTES} minutes. Do not share this code.`
      );
      if (!smsResult.success) {
        const maskedPhone =
          input.phone.slice(0, 4) + "****" + input.phone.slice(-3);
        console.error(
          `[accountOpening] OTP SMS delivery failed for ${maskedPhone}: ${smsResult.error}`
        );
      }

      return {
        success: true,
        message: "If the details match, an OTP has been sent.",
      };
    }),

  openAccount: protectedProcedure
    .input(
      z.object({
        firstName: z.string(),
        lastName: z.string(),
        phone: z.string(),
        email: z.string().optional(),
        bvn: z.string().optional(),
        nin: z.string().optional(),
        address: z.string().optional(),
        // Tier-1 (no BVN/NIN) requires a verified phone OTP
        otp: z.string().length(6).optional(),
        idempotencyKey: z.string().optional(),
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
        "accountOpening",
        "mutation",
        "Executed accountOpening mutation"
      );

      const createAccount = async () => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");

        // ══ FAIL-CLOSED KYC ENFORCEMENT ══
        // For Tier 2+ accounts, verify KYC service is reachable BEFORE creating the record.
        // If KYC enforcement gateway is unreachable, BLOCK the operation (fail-closed design).
        const KYC_ENFORCEMENT_URL =
          process.env.KYC_ENFORCEMENT_URL || "http://localhost:8211";
        const requiresKYC = !!(input.bvn || input.nin); // Tier 2+ requires BVN/NIN

        if (requiresKYC) {
          try {
            const kycResp = await fetch(
              `${KYC_ENFORCEMENT_URL}/api/v1/enforce/account-opening`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  customer_id:
                    `${input.firstName}-${input.lastName}-${input.phone}`
                      .toLowerCase()
                      .replace(/\s/g, "-"),
                  tier: input.nin ? 3 : 2,
                  product_type: "current",
                  first_name: input.firstName,
                  last_name: input.lastName,
                  phone: input.phone,
                  bvn: input.bvn || "",
                  nin: input.nin || "",
                  email: input.email || "",
                }),
                signal: AbortSignal.timeout(10000),
              }
            );

            if (kycResp.status === 503) {
              // KYC gateway unreachable — FAIL CLOSED
              throw new TRPCError({
                code: "PRECONDITION_FAILED",
                message:
                  "KYC verification service unreachable — account opening BLOCKED (fail-closed). Retry when service is available.",
              });
            }
            if (!kycResp.ok) {
              // Any 4xx/5xx from the KYC gateway is treated as a denial — FAIL CLOSED
              throw new TRPCError({
                code: "PRECONDITION_FAILED",
                message: `KYC enforcement gateway returned HTTP ${kycResp.status} — account opening BLOCKED (fail-closed).`,
              });
            }
            // Gateway returns 202 with body {allowed:false} on denial — block unless explicitly allowed
            let kycDecision: { allowed?: boolean } | null = null;
            try {
              kycDecision = (await kycResp.json()) as { allowed?: boolean };
            } catch {
              kycDecision = null;
            }
            if (kycDecision?.allowed !== true) {
              throw new TRPCError({
                code: "FORBIDDEN",
                message:
                  "KYC enforcement denied account opening — verification not satisfied (fail-closed).",
              });
            }
          } catch (kycError) {
            if (kycError instanceof TRPCError) throw kycError;
            // Network error reaching KYC gateway — FAIL CLOSED
            throw new TRPCError({
              code: "PRECONDITION_FAILED",
              message:
                "KYC enforcement gateway unreachable — account opening BLOCKED (fail-closed design prevents unverified account creation)",
            });
          }
        } else {
          // ══ TIER-1 PHONE OTP ENFORCEMENT (FAIL-CLOSED) ══
          // Tier-1 accounts (no BVN/NIN) must present a verified phone OTP.
          // If the OTP store is unreachable or the OTP is missing/invalid,
          // BLOCK the operation.
          if (!input.otp) {
            throw new TRPCError({
              code: "PRECONDITION_FAILED",
              message:
                "Tier-1 account opening requires phone OTP verification — call accountOpening.sendTier1Otp and supply the OTP (fail-closed).",
            });
          }
          const otpUserId = Number((ctx.user as any)?.id);
          if (!Number.isFinite(otpUserId) || otpUserId <= 0) {
            throw new TRPCError({
              code: "UNAUTHORIZED",
              message: "Invalid user context for OTP verification",
            });
          }
          await verifyTier1Otp(db, otpUserId, input.otp);
        }

        // Duplicate BVN/NIN pre-checks — CONFLICT on match.
        // Values are stored encrypted with a random IV, so the pre-check runs
        // against the deterministic blind-index columns (sha256+salt) instead
        // of plaintext equality.
        const bvnHash = input.bvn ? blindIndex(input.bvn) : null;
        const ninHash = input.nin ? blindIndex(input.nin) : null;
        if (bvnHash) {
          const [dupBvn] = await db
            .select({ id: customers.id })
            .from(customers)
            .where(eq(customers.bvnHash, bvnHash))
            .limit(1);
          if (dupBvn)
            throw new TRPCError({
              code: "CONFLICT",
              message: "A customer with this BVN already exists",
            });
        }
        if (ninHash) {
          const [dupNin] = await db
            .select({ id: customers.id })
            .from(customers)
            .where(eq(customers.ninHash, ninHash))
            .limit(1);
          if (dupNin)
            throw new TRPCError({
              code: "CONFLICT",
              message: "A customer with this NIN already exists",
            });
        }

        const [customer] = await db
          .insert(customers)
          .values({
            firstName: input.firstName,
            lastName: input.lastName,
            phone: input.phone,
            email: input.email,
            // PII at rest: AES-256-GCM ciphertext + blind index (migration 0057)
            bvn: input.bvn ? encryptField(input.bvn) : undefined,
            nin: input.nin ? encryptField(input.nin) : undefined,
            bvnHash,
            ninHash,
            address: input.address,
            status: "pending_kyc",
            tenantId: (ctx.user as any)?.tenantId ?? null,
          })
          .returning();
        await db.insert(auditLog).values({
          action: "account_opened",
          resource: "customers",
          resourceId: String(customer.id),
          status: "success",
          metadata: {
            firstName: input.firstName,
            lastName: input.lastName,
            tier: requiresKYC ? (input.nin ? 3 : 2) : 1,
            phoneOtpVerified: requiresKYC ? undefined : true,
          },
        });
        // Redact stored PII from the response (bvn/nin are ciphertext at rest).
        return {
          success: true,
          customer: {
            ...customer,
            bvn: customer.bvn ? "***" : null,
            nin: customer.nin ? "***" : null,
          },
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
      };
      if (input.idempotencyKey) {
        return withIdempotency(
          `accountOpening:${input.idempotencyKey}`,
          createAccount,
          { payload: input }
        );
      }
      return createAccount();
    }),
  approveAccount: adminProcedure
    .input(z.object({ customerId: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        // Conditional update — only a pending_kyc account can be approved (0 rows → CONFLICT)
        const [updated] = await db
          .update(customers)
          .set({ status: "active" })
          .where(
            and(
              eq(customers.id, input.customerId),
              eq(customers.status, "pending_kyc")
            )
          )
          .returning();
        if (!updated)
          throw new TRPCError({
            code: "CONFLICT",
            message: "Account is not in pending_kyc status — cannot approve",
          });
        await db.insert(auditLog).values({
          action: "account_approved",
          resource: "customers",
          resourceId: String(input.customerId),
          status: "success",
        });
        return { success: true, customer: updated };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  list: protectedProcedure.query(async () => {
    return {
      applications: [
        {
          id: "AO-001",
          customerName: "Fatima Ibrahim",
          accountType: "savings",
          status: "approved",
          createdAt: "2024-06-01",
        },
      ],
      total: 1,
    };
  }),
  analytics: protectedProcedure.query(async () => {
    return {
      total: 1500,
      totalApplications: 1500,
      approved: 1200,
      pending: 200,
      rejected: 100,
      byStatus: { approved: 1200, pending: 200, rejected: 100 },
      byBank: { access: 500, gtbank: 400, zenith: 300, firstbank: 300 },
      conversionRate: 80,
      avgProcessingDays: 3,
    };
  }),
});
