/**
 * Micro-Insurance Products — embedded insurance for agents and customers
 *
 * Products:
 * - Device Protection: POS terminal coverage (theft, damage, malfunction)
 * - Health Micro: Basic health coverage for agents (outpatient, emergency)
 * - Crop Insurance: Weather-indexed crop insurance for agri-banking
 * - Personal Accident: Coverage for agents during work
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { checkDailyLimit } from "../lib/cbnLimits";
import { agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, count, sum } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import { validateInput } from "../lib/routerHelpers";

interface InsuranceProduct {
  id: string;
  name: string;
  category: string;
  description: string;
  monthlyPremium: number;
  coverageAmount: number;
  waitingPeriodDays: number;
  maxClaimPerYear: number;
  features: string[];
}

const PRODUCTS: InsuranceProduct[] = [
  {
    id: "device_basic",
    name: "POS Shield Basic",
    category: "device_protection",
    description:
      "Basic POS terminal protection against theft and accidental damage",
    monthlyPremium: 500,
    coverageAmount: 150_000,
    waitingPeriodDays: 7,
    maxClaimPerYear: 2,
    features: [
      "Theft protection",
      "Accidental damage",
      "Free replacement terminal",
      "24-hour claim processing",
    ],
  },
  {
    id: "device_premium",
    name: "POS Shield Premium",
    category: "device_protection",
    description:
      "Comprehensive POS terminal protection including malfunction and loss",
    monthlyPremium: 1200,
    coverageAmount: 350_000,
    waitingPeriodDays: 3,
    maxClaimPerYear: 4,
    features: [
      "All Basic features",
      "Malfunction coverage",
      "Loss coverage",
      "Express replacement (same day)",
      "Accessory coverage (charger, battery)",
    ],
  },
  {
    id: "health_micro",
    name: "Agent Health Cover",
    category: "health",
    description: "Basic health coverage for agents — outpatient and emergency",
    monthlyPremium: 2000,
    coverageAmount: 500_000,
    waitingPeriodDays: 30,
    maxClaimPerYear: 6,
    features: [
      "Outpatient treatment up to NGN 50,000",
      "Emergency hospitalization up to NGN 200,000",
      "Prescription drugs coverage",
      "Telemedicine consultations",
      "Annual health check",
    ],
  },
  {
    id: "crop_basic",
    name: "Crop Guard",
    category: "crop_insurance",
    description: "Weather-indexed crop insurance for farming agents",
    monthlyPremium: 1500,
    coverageAmount: 1_000_000,
    waitingPeriodDays: 0,
    maxClaimPerYear: 1,
    features: [
      "Drought protection",
      "Flood coverage",
      "Pest infestation (major outbreaks)",
      "Automatic payout based on weather data",
      "Satellite-verified claims",
    ],
  },
  {
    id: "personal_accident",
    name: "Agent Safety Net",
    category: "personal_accident",
    description: "Personal accident coverage for agents during work hours",
    monthlyPremium: 800,
    coverageAmount: 2_000_000,
    waitingPeriodDays: 0,
    maxClaimPerYear: 1,
    features: [
      "Accidental death benefit: NGN 2,000,000",
      "Permanent disability: up to NGN 2,000,000",
      "Temporary disability: NGN 5,000/day (max 90 days)",
      "Medical expenses: up to NGN 200,000",
      "24/7 coverage during work activities",
    ],
  },
];

export const microInsuranceRouter = router({
  listProducts: protectedProcedure
    .input(
      z
        .object({
          category: z.string().max(50).optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      let products = PRODUCTS;
      if (input?.category) {
        products = products.filter(p => p.category === input.category);
      }
      return {
        products,
        categories: [
          {
            id: "device_protection",
            name: "Device Protection",
            icon: "smartphone",
          },
          { id: "health", name: "Health Cover", icon: "heart" },
          { id: "crop_insurance", name: "Crop Insurance", icon: "cloud-rain" },
          {
            id: "personal_accident",
            name: "Personal Accident",
            icon: "shield",
          },
        ],
      };
    }),

  getProduct: protectedProcedure
    .input(z.object({ productId: z.string().min(1).max(50) }))
    .query(async ({ input }) => {
      const product = PRODUCTS.find(p => p.id === input.productId);
      if (!product)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Product not found",
        });
      return product;
    }),

  enroll: protectedProcedure
    .input(
      z.object({
        productId: z.string().min(1).max(50),
        beneficiaryName: z.string().min(2).max(100),
        beneficiaryPhone: z.string().min(10).max(15),
        startDate: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const product = PRODUCTS.find(p => p.id === input.productId);
      if (!product)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Product not found",
        });

      const policyRef = `INS-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;

      // Calculate risk-adjusted premium based on product category
      const basePremium = product.monthlyPremium;
      const riskMultiplier = product.category === "health" ? 1.15 : 1.0;
      const adjustedPremium = Math.round(basePremium * riskMultiplier);
      const startDate =
        input.startDate || new Date().toISOString().split("T")[0];
      const waitingEnds = new Date(
        Date.now() + product.waitingPeriodDays * 86_400_000
      )
        .toISOString()
        .split("T")[0];

      // Persist policy enrollment to DB
      await db.execute(
        sql`INSERT INTO "insurance_policies" (policy_number, agent_id, product_id, product_name, category, monthly_premium, coverage_amount, status, beneficiary_name, beneficiary_phone, start_date, waiting_period_ends, created_at) VALUES (${policyRef}, ${session.id}, ${input.productId}, ${product.name}, ${product.category}, ${adjustedPremium}, ${product.coverageAmount}, 'active', ${input.beneficiaryName}, ${input.beneficiaryPhone}, ${startDate}, ${waitingEnds}, NOW())`
      );

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "INSURANCE_ENROLLMENT",
        resource: "micro_insurance",
        resourceId: policyRef,
        status: "success",
        metadata: {
          productId: input.productId,
          monthlyPremium: adjustedPremium,
          coverageAmount: product.coverageAmount,
          beneficiary: input.beneficiaryName,
        },
      });

      return {
        policyNumber: policyRef,
        productId: input.productId,
        productName: product.name,
        status: "active",
        monthlyPremium: adjustedPremium,
        coverageAmount: product.coverageAmount,
        startDate,
        waitingPeriodEnds: waitingEnds,
        beneficiaryName: input.beneficiaryName,
        beneficiaryPhone: input.beneficiaryPhone,
        createdAt: new Date().toISOString(),
      };
    }),

  fileClaim: protectedProcedure
    .input(
      z.object({
        policyNumber: z.string().min(1).max(50),
        claimType: z.string().min(1).max(100),
        description: z.string().min(10).max(2000),
        amount: z.number().min(1),
        evidenceUrls: z.array(z.string().url()).max(10).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const claimRef = `CLM-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;

      // Validate policy exists and is claimable
      const policyResult = await db.execute(
        sql`SELECT coverage_amount, status, waiting_period_ends FROM "insurance_policies" WHERE policy_number = ${input.policyNumber} AND agent_id = ${session.id}`
      );
      const policyRow = (policyResult as any).rows?.[0];
      if (!policyRow || policyRow.status !== "active") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Policy not found or not active",
        });
      }
      if (
        policyRow.waiting_period_ends &&
        new Date(policyRow.waiting_period_ends) > new Date()
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Policy is still in waiting period",
        });
      }
      if (input.amount > (policyRow.coverage_amount ?? 0)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Claim amount exceeds coverage limit",
        });
      }

      // Persist claim to DB
      await db.execute(
        sql`INSERT INTO "insurance_claims" (claim_number, policy_number, agent_id, claim_type, description, amount, status, evidence_urls, created_at) VALUES (${claimRef}, ${input.policyNumber}, ${session.id}, ${input.claimType}, ${input.description}, ${input.amount}, 'submitted', ${JSON.stringify(input.evidenceUrls || [])}, NOW())`
      );

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "INSURANCE_CLAIM_FILED",
        resource: "micro_insurance",
        resourceId: claimRef,
        status: "success",
        metadata: {
          policyNumber: input.policyNumber,
          claimType: input.claimType,
          amount: input.amount,
        },
      });

      return {
        claimNumber: claimRef,
        policyNumber: input.policyNumber,
        status: "submitted",
        estimatedProcessingDays: 5,
        createdAt: new Date().toISOString(),
      };
    }),

  adjudicateClaim: protectedProcedure
    .input(
      z.object({
        claimNumber: z.string(),
        decision: z.enum(["approved", "rejected", "needs_more_info"]),
        notes: z.string().optional(),
        approvedAmount: z.number().optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      // Look up claim
      const claimResult = await db.execute(
        sql`SELECT id, claim_number, policy_number, amount, status FROM "insurance_claims" WHERE claim_number = ${input.claimNumber}`,
      );
      const claim = (claimResult as any).rows?.[0];
      if (!claim) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Claim not found",
        });
      }
      if (claim.status !== "submitted" && claim.status !== "under_review") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Claim already ${claim.status}`,
        });
      }

      const newStatus =
        input.decision === "approved"
          ? "approved"
          : input.decision === "rejected"
            ? "rejected"
            : "under_review";

      const approvedAmount =
        input.decision === "approved"
          ? input.approvedAmount ?? claim.amount
          : null;

      await db.execute(
        sql`UPDATE "insurance_claims" SET status = ${newStatus}, adjudication_notes = ${input.notes ?? ""}, resolved_at = ${input.decision !== "needs_more_info" ? new Date().toISOString() : null} WHERE claim_number = ${input.claimNumber}`,
      );

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "INSURANCE_CLAIM_ADJUDICATED",
        resource: "micro_insurance",
        resourceId: input.claimNumber,
        status: "success",
        metadata: {
          decision: input.decision,
          approvedAmount,
          notes: input.notes,
        },
      });

      return {
        claimNumber: input.claimNumber,
        decision: input.decision,
        newStatus,
        approvedAmount,
        adjudicatedAt: new Date().toISOString(),
      };
    }),

  listClaims: protectedProcedure.query(async ({ ctx }) => {
    const db = (await getDb())!;
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    const result = await db.execute(
      sql`SELECT claim_number, policy_number, claim_type, amount, status, created_at FROM "insurance_claims" WHERE agent_id = ${session.id} ORDER BY created_at DESC LIMIT 50`,
    );
    return { claims: (result as any).rows ?? [] };
  }),

  listPolicies: protectedProcedure.query(async ({ ctx }) => {
    const db = (await getDb())!;
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    const result = await db.execute(
      sql`SELECT policy_number, product_name, category, monthly_premium, coverage_amount, status, start_date, waiting_period_ends FROM "insurance_policies" WHERE agent_id = ${session.id} ORDER BY created_at DESC LIMIT 50`,
    );
    return { policies: (result as any).rows ?? [] };
  }),

  stats: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    return {
      totalProducts: PRODUCTS.length,
      categories: 4,
      avgMonthlyPremium: Math.round(
        PRODUCTS.reduce((s, p) => s + p.monthlyPremium, 0) / PRODUCTS.length,
      ),
      avgCoverage: Math.round(
        PRODUCTS.reduce((s, p) => s + p.coverageAmount, 0) / PRODUCTS.length,
      ),
    };
  }),
});
