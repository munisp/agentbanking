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

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "INSURANCE_ENROLLMENT",
        resource: "micro_insurance",
        resourceId: policyRef,
        status: "success",
        metadata: {
          productId: input.productId,
          monthlyPremium: product.monthlyPremium,
          coverageAmount: product.coverageAmount,
          beneficiary: input.beneficiaryName,
        },
      });

      return {
        policyNumber: policyRef,
        productId: input.productId,
        productName: product.name,
        status: "active",
        monthlyPremium: product.monthlyPremium,
        coverageAmount: product.coverageAmount,
        startDate: input.startDate || new Date().toISOString().split("T")[0],
        waitingPeriodEnds: new Date(
          Date.now() + product.waitingPeriodDays * 86_400_000
        )
          .toISOString()
          .split("T")[0],
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

  stats: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    return {
      totalProducts: PRODUCTS.length,
      categories: 4,
      avgMonthlyPremium: Math.round(
        PRODUCTS.reduce((s, p) => s + p.monthlyPremium, 0) / PRODUCTS.length
      ),
      avgCoverage: Math.round(
        PRODUCTS.reduce((s, p) => s + p.coverageAmount, 0) / PRODUCTS.length
      ),
    };
  }),
});
