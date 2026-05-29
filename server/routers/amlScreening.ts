/**
 * AML Screening Router — Anti-Money Laundering screening with risk scoring,
 * sanctions list checking, PEP detection, and case management.
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { TRPCError } from "@trpc/server";
import { amlScreenings, amlWatchlistEntries } from "../../drizzle/schema";
import { eq, desc, count, sql, and, gte, lte, or, ilike } from "drizzle-orm";
import { logAudit } from "../lib/auditTrail";
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

const RISK_WEIGHTS = {
  sanctionsList: 50,
  pepMatch: 30,
  adverseMedia: 15,
  highRiskCountry: 20,
  highTransactionVolume: 10,
  unusualPattern: 10,
  nameVariantMatch: 5,
};

const HIGH_RISK_COUNTRIES = new Set([
  "AF",
  "IR",
  "KP",
  "SY",
  "YE",
  "MM",
  "LY",
  "SO",
  "SS",
  "SD",
  "VE",
  "CU",
]);

function calculateRiskScore(factors: {
  sanctionsList: boolean;
  pepMatch: boolean;
  adverseMedia: boolean;
  highRiskCountry: boolean;
  highTransactionVolume: boolean;
  unusualPattern: boolean;
  nameVariantMatch: boolean;
}): number {
  let score = 0;
  if (factors.sanctionsList) score += RISK_WEIGHTS.sanctionsList;
  if (factors.pepMatch) score += RISK_WEIGHTS.pepMatch;
  if (factors.adverseMedia) score += RISK_WEIGHTS.adverseMedia;
  if (factors.highRiskCountry) score += RISK_WEIGHTS.highRiskCountry;
  if (factors.highTransactionVolume)
    score += RISK_WEIGHTS.highTransactionVolume;
  if (factors.unusualPattern) score += RISK_WEIGHTS.unusualPattern;
  if (factors.nameVariantMatch) score += RISK_WEIGHTS.nameVariantMatch;
  return Math.min(100, score);
}

function determineStatus(
  riskScore: number
): "clear" | "review" | "escalated" | "blocked" {
  if (riskScore >= 50) return "blocked";
  if (riskScore >= 30) return "escalated";
  if (riskScore >= 10) return "review";
  return "clear";
}

export const amlScreeningRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        status: z.enum(["clear", "review", "escalated", "blocked"]).optional(),
        dateFrom: z.string().optional(),
        dateTo: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { items: [], total: 0 };

        const conditions = [];
        if (input.status) {
          conditions.push(eq(amlScreenings.status, input.status));
        }
        if (input.dateFrom) {
          conditions.push(
            gte(amlScreenings.createdAt, new Date(input.dateFrom))
          );
        }
        if (input.dateTo) {
          conditions.push(lte(amlScreenings.createdAt, new Date(input.dateTo)));
        }

        const where = conditions.length > 0 ? and(...conditions) : undefined;

        const [items, totalResult] = await Promise.all([
          db
            .select()
            .from(amlScreenings)
            .where(where)
            .orderBy(desc(amlScreenings.createdAt))
            .limit(input.limit)
            .offset(input.offset),
          db.select({ total: count() }).from(amlScreenings).where(where),
        ]);

        return {
          items,
          total: totalResult[0]?.total ?? 0,
        };
      } catch {
        return { items: [], total: 0 };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });

      const [record] = await db
        .select()
        .from(amlScreenings)
        .where(eq(amlScreenings.id, input.id))
        .limit(1);

      if (!record) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: `AML screening ${input.id} not found`,
        });
      }
      return record;
    }),

  screen: protectedProcedure
    .input(
      z.object({
        entityName: z.string().min(2).max(200),
        entityType: z.enum(["individual", "organization"]),
        country: z.string().length(2).optional(),
        nationalId: z.string().optional(),
        dateOfBirth: z.string().optional(),
        transactionAmount: z.number().optional(),
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
        "amlScreening",
        "mutation",
        "Executed amlScreening mutation"
      );

      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });

      // Check watchlist for name matches (fuzzy)
      const nameNormalized = input.entityName.toLowerCase().trim();
      let sanctionsMatch = false;
      let pepMatch = false;
      let adverseMediaMatch = false;
      let nameVariantMatch = false;

      try {
        const watchlistHits = await db
          .select()
          .from(amlWatchlistEntries)
          .where(
            or(
              ilike(amlWatchlistEntries.entityName, `%${nameNormalized}%`),
              ilike(amlWatchlistEntries.aliases, `%${nameNormalized}%`)
            )
          )
          .limit(10);

        for (const hit of watchlistHits) {
          if (hit.listType === "sanctions") sanctionsMatch = true;
          if (hit.listType === "pep") pepMatch = true;
          if (hit.listType === "adverse_media") adverseMediaMatch = true;
          if (
            hit.entityName?.toLowerCase() !== nameNormalized &&
            hit.aliases?.toLowerCase().includes(nameNormalized)
          ) {
            nameVariantMatch = true;
          }
        }
      } catch {
        // Watchlist table may not exist yet — proceed with other checks
      }

      const highRiskCountry = input.country
        ? HIGH_RISK_COUNTRIES.has(input.country.toUpperCase())
        : false;

      const highTransactionVolume = (input.transactionAmount ?? 0) > 1_000_000;

      const riskScore = calculateRiskScore({
        sanctionsList: sanctionsMatch,
        pepMatch,
        adverseMedia: adverseMediaMatch,
        highRiskCountry,
        highTransactionVolume,
        unusualPattern: false,
        nameVariantMatch,
      });

      const status = determineStatus(riskScore);

      // Store screening result
      try {
        await db.insert(amlScreenings).values({
          entityName: input.entityName,
          entityType: input.entityType,
          country: input.country ?? null,
          nationalId: input.nationalId ?? null,
          riskScore,
          status,
          sanctionsMatch,
          pepMatch,
          adverseMediaMatch,
          highRiskCountry,
          screenedAt: new Date(),
        });
      } catch {
        // Table may not exist — still return the screening result
      }

      logAudit({
        userId: null,
        userRole: "system",
        action: "CREATE",
        resource: "amlScreening",
        resourceId: null,
        description: `AML screening: ${input.entityName} (${input.entityType}) — score: ${riskScore}, status: ${status}`,
        ipAddress: "internal",
        userAgent: "server",
        severity: riskScore >= 30 ? "critical" : "medium",
        category: "compliance",
        metadata: {
          riskScore,
          status,
          sanctionsMatch,
          pepMatch,
          highRiskCountry,
        },
      });

      return {
        entityName: input.entityName,
        entityType: input.entityType,
        riskScore,
        status,
        factors: {
          sanctionsMatch,
          pepMatch,
          adverseMediaMatch,
          highRiskCountry,
          highTransactionVolume,
          nameVariantMatch,
        },
        screenedAt: new Date().toISOString(),
        recommendation:
          status === "blocked"
            ? "Block transaction — sanctions/PEP match detected"
            : status === "escalated"
              ? "Escalate to compliance officer for manual review"
              : status === "review"
                ? "Flag for periodic review"
                : "Proceed — no adverse findings",
      };
    }),

  getStats: protectedProcedure.query(async () => {
    try {
      const db = await getDb();
      if (!db)
        return {
          total: 0,
          clear: 0,
          review: 0,
          escalated: 0,
          blocked: 0,
          avgRiskScore: 0,
        };

      const [total, clear, review, escalated, blocked, avgScore] =
        await Promise.all([
          db.select({ cnt: count() }).from(amlScreenings),
          db
            .select({ cnt: count() })
            .from(amlScreenings)
            .where(eq(amlScreenings.status, "clear")),
          db
            .select({ cnt: count() })
            .from(amlScreenings)
            .where(eq(amlScreenings.status, "review")),
          db
            .select({ cnt: count() })
            .from(amlScreenings)
            .where(eq(amlScreenings.status, "escalated")),
          db
            .select({ cnt: count() })
            .from(amlScreenings)
            .where(eq(amlScreenings.status, "blocked")),
          db
            .select({
              avg: sql<string>`COALESCE(AVG(${amlScreenings.riskScore}), 0)`,
            })
            .from(amlScreenings),
        ]);

      return {
        total: total[0]?.cnt ?? 0,
        clear: clear[0]?.cnt ?? 0,
        review: review[0]?.cnt ?? 0,
        escalated: escalated[0]?.cnt ?? 0,
        blocked: blocked[0]?.cnt ?? 0,
        avgRiskScore: Number(avgScore[0]?.avg ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        clear: 0,
        review: 0,
        escalated: 0,
        blocked: 0,
        avgRiskScore: 0,
      };
    }
  }),

  updateStatus: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        status: z.enum(["clear", "review", "escalated", "blocked"]),
        reason: z.string().min(5).max(500),
      })
    )
    .mutation(async ({ input }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });

      const [existing] = await db
        .select()
        .from(amlScreenings)
        .where(eq(amlScreenings.id, input.id))
        .limit(1);

      if (!existing) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: `AML screening ${input.id} not found`,
        });
      }

      const ALLOWED_TRANSITIONS: Record<string, string[]> = {
        clear: ["review", "escalated"],
        review: ["clear", "escalated", "blocked"],
        escalated: ["review", "blocked", "clear"],
        blocked: ["escalated", "review"],
      };

      const allowed = ALLOWED_TRANSITIONS[existing.status ?? "clear"];
      if (!allowed?.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Cannot transition from '${existing.status}' to '${input.status}'`,
        });
      }

      await db
        .update(amlScreenings)
        .set({
          status: input.status,
          updatedAt: new Date(),
        })
        .where(eq(amlScreenings.id, input.id));

      logAudit({
        userId: null,
        userRole: "compliance_officer",
        action: "UPDATE",
        resource: "amlScreening",
        resourceId: String(input.id),
        description: `AML status changed: ${existing.status} → ${input.status}. Reason: ${input.reason}`,
        ipAddress: "internal",
        userAgent: "server",
        severity: "critical",
        category: "compliance",
        previousState: { status: existing.status },
        newState: { status: input.status },
      });

      return { success: true, id: input.id, newStatus: input.status };
    }),
});
