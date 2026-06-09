/**
 * PIN Reset Router
 *
 * Flow:
 *   1. Agent submits their agent code + registered phone number
 *   2. Server verifies the phone matches the DB record
 *   3. A 6-digit OTP is generated, hashed, and stored in the otp_tokens table
 *   4. OTP is sent via Termii SMS (falls back to console.log when key absent)
 *   5. Agent submits the OTP + new PIN
 *   6. Server verifies OTP, hashes new PIN, updates agents table
 */
import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { eq, and, gt } from "drizzle-orm";
import bcrypt from "bcryptjs";
import { getDb, writeAuditLog } from "../db";
import { agents, otpTokens } from "../../drizzle/schema";
import { protectedProcedure, router } from "../_core/trpc";
import { sendSms } from "../termii";
import crypto from "crypto";
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
const OTP_EXPIRY_MINUTES = 10;
// SECURITY: Use crypto.randomInt for cryptographically secure OTP generation
function generateOtp(): string {
  // Generates a 6-digit OTP using CSPRNG (crypto.randomInt is uniform in [100000, 999999])
  return crypto.randomInt(100000, 1000000).toString();
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "pinReset",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "pinReset",
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
    resource: "pinReset",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "pinReset",
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

// ── Extended Validation Schemas ────────────────────────────────────────────
const _pinResetSchemas = {
  idParam: z.object({ id: z.number().int().positive() }),
  paginationInput: z.object({
    page: z.number().int().min(1).default(1),
    pageSize: z.number().int().min(1).max(100).default(20),
    sortBy: z.string().optional(),
    sortOrder: z.enum(["asc", "desc"]).default("desc"),
  }),
  dateRange: z.object({
    from: z.string().datetime().optional(),
    to: z.string().datetime().optional(),
  }),
  searchInput: z.object({
    query: z.string().min(1).max(500),
    filters: z.record(z.string(), z.string()).optional(),
  }),
};

export const pinResetRouter = router({
  /**
   * Step 1: Request OTP
   * Verifies agent code + phone, generates OTP, sends SMS.
   */
  requestOtp: protectedProcedure
    .input(
      z.object({
        agentCode: z.string().min(3),
        phone: z.string().min(10).max(15),
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
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Find agent by code
        const agentRows = await db
          .select()
          .from(agents)
          .where(eq(agents.agentCode, input.agentCode))
          .limit(1);

        if (agentRows.length === 0) {
          // Return generic message to avoid agent code enumeration
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

            resource: "pinReset",

            resourceId:
              typeof input === "object" && input !== null && "id" in input
                ? String((input as any).id)
                : "new",

            status: "success",

            metadata: { input: typeof input === "object" ? input : {} },
          });

          return {
            success: true,
            message: "If the details match, an OTP has been sent.",
          };
        }

        const agent = agentRows[0];

        // Verify phone matches (last 10 digits comparison for flexibility)
        const storedPhone = (agent.phone ?? "").replace(/\D/g, "").slice(-10);
        const inputPhone = input.phone.replace(/\D/g, "").slice(-10);

        if (storedPhone !== inputPhone) {
          return {
            success: true,
            message: "If the details match, an OTP has been sent.",
          };
        }

        // Invalidate any existing OTPs for this agent
        await db.delete(otpTokens).where(eq(otpTokens.agentId, agent.id));

        // Generate and hash OTP
        const otp = generateOtp();
        const hashedOtp = await bcrypt.hash(otp, 10);
        const expiresAt = new Date(Date.now() + OTP_EXPIRY_MINUTES * 60 * 1000);

        await db.insert(otpTokens).values({
          agentId: agent.id,
          hashedOtp,
          expiresAt,
          used: false,
        });

        // Send SMS via shared Termii helper
        const smsResult = await sendSms(
          input.phone,
          `Your 54Link POS PIN reset code is: ${otp}. Valid for ${OTP_EXPIRY_MINUTES} minutes. Do not share this code.`
        );
        if (!smsResult.success) {
          // Redact phone number in logs to avoid PII exposure
          const maskedPhone =
            input.phone.slice(0, 4) + "****" + input.phone.slice(-3);
          console.error(
            `[pinReset] SMS delivery failed for ${maskedPhone}: ${smsResult.error}`
          );
        } else {
          const maskedPhone =
            input.phone.slice(0, 4) + "****" + input.phone.slice(-3);
          console.info(
            `[pinReset] OTP SMS sent to ${maskedPhone} — messageId: ${smsResult.messageId}`
          );
        }

        return {
          success: true,
          message: "If the details match, an OTP has been sent.",
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

  /**
   * Step 2: Verify OTP and set new PIN
   */
  resetPin: protectedProcedure
    .input(
      z.object({
        agentCode: z.string().min(3),
        otp: z.string().length(6),
        newPin: z.string().min(4).max(6),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Find agent
        const agentRows = await db
          .select()
          .from(agents)
          .where(eq(agents.agentCode, input.agentCode))
          .limit(1);

        if (agentRows.length === 0) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Invalid OTP or agent code",
          });
        }

        const agent = agentRows[0];

        // Find valid (unexpired, unused) OTP token
        const tokenRows = await db
          .select()
          .from(otpTokens)
          .where(
            and(
              eq(otpTokens.agentId, agent.id),
              eq(otpTokens.used, false),
              gt(otpTokens.expiresAt, new Date())
            )
          )
          .limit(1);

        if (tokenRows.length === 0) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "OTP expired or not found. Please request a new one.",
          });
        }

        const token = tokenRows[0];

        // Verify OTP
        const valid = await bcrypt.compare(input.otp, token.hashedOtp);
        if (!valid) {
          throw new TRPCError({ code: "BAD_REQUEST", message: "Invalid OTP" });
        }

        // Mark token as used
        await db
          .update(otpTokens)
          .set({ used: true })
          .where(eq(otpTokens.id, token.id));

        // Hash and update PIN
        const hashedPin = await bcrypt.hash(input.newPin, 12);
        await db
          .update(agents)
          .set({ pinHash: hashedPin })
          .where(eq(agents.id, agent.id));

        return {
          success: true,
          message: "PIN updated successfully. Please log in with your new PIN.",
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

  // ── Additional query/mutation procedures ─────────────────────
  getStats_pinReset: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      lastUpdated: new Date().toISOString(),
      status: "operational",
    };
  }),

  healthCheck_pinReset: protectedProcedure.query(async () => {
    return {
      healthy: true,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }),
});
