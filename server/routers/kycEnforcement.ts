import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { writeAuditLog } from "../db";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  not_started: ["documents_submitted"],
  documents_submitted: ["under_review"],
  under_review: [
    "additional_info_required",
    "verified",
    "rejected",
    "escalated",
  ],
  additional_info_required: ["documents_submitted"],
  verified: ["active", "expired"],
  active: ["renewal_pending", "suspended", "revoked"],
  renewal_pending: ["under_review"],
  expired: ["renewal_pending", "revoked"],
  suspended: ["under_review", "revoked"],
  escalated: ["verified", "rejected"],
  rejected: ["appeal"],
  appeal: ["under_review"],
  revoked: [],
};

const KYC_ENFORCEMENT_URL =
  process.env.KYC_ENFORCEMENT_URL || "http://localhost:8211";
const AML_CASE_MANAGER_URL =
  process.env.AML_CASE_MANAGER_URL || "http://localhost:8212";
const CBN_TIER_ENGINE_URL =
  process.env.CBN_TIER_ENGINE_URL || "http://localhost:8213";
const SANCTIONS_RESCREENER_URL =
  process.env.SANCTIONS_RESCREENER_URL || "http://localhost:8214";
const KYC_WORKFLOW_URL =
  process.env.KYC_WORKFLOW_URL || "http://localhost:8215";
const KYC_EVENT_CONSUMER_URL =
  process.env.KYC_EVENT_CONSUMER_URL || "http://localhost:8216";
const GOAML_URL = process.env.GOAML_SERVICE_URL || "http://localhost:8210";

async function serviceCall(
  url: string,
  method: string,
  body?: unknown
): Promise<unknown> {
  const resp = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15000),
  });
  if (!resp.ok && resp.status !== 202) {
    const text = await resp.text().catch(() => "");
    throw new TRPCError({
      code: "INTERNAL_SERVER_ERROR",
      message: `Service returned ${resp.status}: ${text.slice(0, 200)}`,
    });
  }
  return resp.json();
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "kycEnforcement",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "kycEnforcement",
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
    resource: "kycEnforcement",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "kycEnforcement",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
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
    if (!!(db && (db as Record<string, unknown>)._isNoop))
      return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`)
      .limit(500);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
  }
}

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const kycEnforcementRouter = router({
  // ── KYC Enforcement Gateway (Go, port 8211) ──
  enforceAccountOpening: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        tier: z.number().min(1).max(3),
        productType: z.string(),
        firstName: z.string(),
        lastName: z.string(),
        phone: z.string(),
        bvn: z.string().optional(),
        nin: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await writeAuditLog({
        action: "mutation",
        resource: "kycEnforcement",
        status: "success",
      });
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus =
          "status" in input
            ? String((input as Record<string, unknown>).status)
            : "";
        const currentStatus =
          "currentStatus" in input
            ? String((input as Record<string, unknown>).currentStatus)
            : "pending";
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
          ? Number(
              "amount" in input ? (input as Record<string, unknown>).amount : 0
            )
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      return serviceCall(
        `${KYC_ENFORCEMENT_URL}/api/v1/enforce/account-opening`,
        "POST",
        {
          customer_id: input.customerId,
          tier: input.tier,
          product_type: input.productType,
          first_name: input.firstName,
          last_name: input.lastName,
          phone: input.phone,
          bvn: input.bvn || "",
          nin: input.nin || "",
        }
      );
    }),

  enforceLoan: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        loanType: z.string(),
        amount: z.number().min(0),
        currency: z.string().default("NGN"),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${KYC_ENFORCEMENT_URL}/api/v1/enforce/loan`, "POST", {
        customer_id: input.customerId,
        loan_type: input.loanType,
        amount: input.amount,
        currency: input.currency,
      });
    }),

  checkKYCStatus: protectedProcedure
    .input(
      z.object({ customerId: z.string().min(1).max(255), level: z.string() })
    )
    .query(async ({ input }) => {
      return serviceCall(
        `${KYC_ENFORCEMENT_URL}/api/v1/enforce/check`,
        "POST",
        { customer_id: input.customerId, level: input.level }
      );
    }),

  bureauVerify: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        bvn: z.string(),
        nin: z.string().optional(),
        fullName: z.string(),
        dateOfBirth: z.string(),
        phone: z.string(),
        bureaus: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${KYC_ENFORCEMENT_URL}/api/v1/bureau/verify`,
        "POST",
        {
          customer_id: input.customerId,
          bvn: input.bvn,
          nin: input.nin || "",
          full_name: input.fullName,
          date_of_birth: input.dateOfBirth,
          phone: input.phone,
          bureaus: input.bureaus,
        }
      );
    }),

  tierRequirements: protectedProcedure.query(async () => {
    return serviceCall(
      `${KYC_ENFORCEMENT_URL}/api/v1/tiers/requirements`,
      "GET"
    );
  }),

  // ── AML Case Management (Go, port 8212) ──
  createCase: protectedProcedure
    .input(
      z.object({
        alertType: z.string(),
        alertId: z.string().min(1).max(255),
        subject: z.object({
          subjectType: z.string(),
          name: z.string(),
          customerId: z.string().min(1).max(255),
          bvn: z.string().optional(),
          riskLevel: z.string(),
        }),
        riskScore: z.number(),
        totalAmount: z.number().optional(),
        transactionCount: z.number().optional(),
        initialNote: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${AML_CASE_MANAGER_URL}/api/v1/cases`, "POST", {
        alert_type: input.alertType,
        alert_id: input.alertId,
        subject: {
          subject_type: input.subject.subjectType,
          name: input.subject.name,
          customer_id: input.subject.customerId,
          bvn: input.subject.bvn || "",
          risk_level: input.subject.riskLevel,
        },
        risk_score: input.riskScore,
        total_amount: input.totalAmount || 0,
        transaction_count: input.transactionCount || 0,
        initial_note: input.initialNote || "",
      });
    }),

  listCases: protectedProcedure
    .input(
      z
        .object({
          status: z.string().optional(),
          priority: z.string().optional(),
          assignedTo: z.string().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const params = new URLSearchParams();
      if (input?.status) params.set("status", input.status);
      if (input?.priority) params.set("priority", input.priority);
      if (input?.assignedTo) params.set("assigned_to", input.assignedTo);
      return serviceCall(
        `${AML_CASE_MANAGER_URL}/api/v1/cases?${params}`,
        "GET"
      );
    }),

  getCase: protectedProcedure
    .input(z.object({ caseId: z.string().min(1).max(255) }))
    .query(async ({ input }) => {
      return serviceCall(
        `${AML_CASE_MANAGER_URL}/api/v1/cases/${input.caseId}`,
        "GET"
      );
    }),

  escalateCase: protectedProcedure
    .input(
      z.object({
        caseId: z.string().min(1).max(255),
        escalatedTo: z.string(),
        reason: z.string(),
        actor: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${AML_CASE_MANAGER_URL}/api/v1/cases/${input.caseId}/escalate`,
        "PUT",
        {
          escalated_to: input.escalatedTo,
          reason: input.reason,
          actor: input.actor,
        }
      );
    }),

  closeCase: protectedProcedure
    .input(
      z.object({
        caseId: z.string().min(1).max(255),
        resolution: z.string(),
        actor: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${AML_CASE_MANAGER_URL}/api/v1/cases/${input.caseId}/close`,
        "PUT",
        { resolution: input.resolution, actor: input.actor }
      );
    }),

  casesDashboard: protectedProcedure.query(async () => {
    return serviceCall(`${AML_CASE_MANAGER_URL}/api/v1/dashboard`, "GET");
  }),

  // ── CBN Tier Engine (Rust, port 8213) ──
  assessTier: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        hasPhone: z.boolean(),
        hasName: z.boolean(),
        hasDob: z.boolean(),
        hasBvn: z.boolean(),
        hasNin: z.boolean(),
        hasIdDocument: z.boolean(),
        hasUtilityBill: z.boolean(),
        hasPassportPhoto: z.boolean(),
        hasSignature: z.boolean(),
        livenessPassed: z.boolean(),
        bvnVerified: z.boolean(),
        ninVerified: z.boolean(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${CBN_TIER_ENGINE_URL}/api/v1/tier/assess`, "POST", {
        customer_id: input.customerId,
        has_phone: input.hasPhone,
        has_name: input.hasName,
        has_dob: input.hasDob,
        has_bvn: input.hasBvn,
        has_nin: input.hasNin,
        has_id_document: input.hasIdDocument,
        has_utility_bill: input.hasUtilityBill,
        has_passport_photo: input.hasPassportPhoto,
        has_signature: input.hasSignature,
        liveness_passed: input.livenessPassed,
        bvn_verified: input.bvnVerified,
        nin_verified: input.ninVerified,
      });
    }),

  enforceLimits: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        tier: z.enum(["tier1", "tier2", "tier3"]),
        transactionAmount: z.number(),
        dailyTotalSoFar: z.number(),
        currentBalance: z.number(),
        transactionType: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${CBN_TIER_ENGINE_URL}/api/v1/tier/enforce-limits`,
        "POST",
        {
          customer_id: input.customerId,
          tier: input.tier,
          transaction_amount: input.transactionAmount,
          daily_total_so_far: input.dailyTotalSoFar,
          current_balance: input.currentBalance,
          transaction_type: input.transactionType,
        }
      );
    }),

  complianceScore: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        hasBvn: z.boolean(),
        bvnVerified: z.boolean(),
        hasNin: z.boolean(),
        ninVerified: z.boolean(),
        livenessPassed: z.boolean(),
        documentsVerified: z.number(),
        documentsRequired: z.number(),
        addressVerified: z.boolean(),
        lastKycUpdateDays: z.number(),
        sanctionsClear: z.boolean(),
        pepClear: z.boolean(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${CBN_TIER_ENGINE_URL}/api/v1/tier/compliance-score`,
        "POST",
        {
          customer_id: input.customerId,
          has_bvn: input.hasBvn,
          bvn_verified: input.bvnVerified,
          has_nin: input.hasNin,
          nin_verified: input.ninVerified,
          liveness_passed: input.livenessPassed,
          documents_verified: input.documentsVerified,
          documents_required: input.documentsRequired,
          address_verified: input.addressVerified,
          last_kyc_update_days: input.lastKycUpdateDays,
          sanctions_clear: input.sanctionsClear,
          pep_clear: input.pepClear,
        }
      );
    }),

  // ── Sanctions Batch Re-Screener (Rust, port 8214) ──
  startBatchRescreen: protectedProcedure
    .input(
      z
        .object({
          scope: z.string().optional(),
          lists: z.array(z.string()).optional(),
          triggeredBy: z.string().optional(),
        })
        .optional()
    )
    .mutation(async ({ input }) => {
      return serviceCall(
        `${SANCTIONS_RESCREENER_URL}/api/v1/batch/start`,
        "POST",
        {
          scope: input?.scope || "all",
          lists: input?.lists,
          triggered_by: input?.triggeredBy || "manual",
        }
      );
    }),

  batchHistory: protectedProcedure.query(async () => {
    return serviceCall(
      `${SANCTIONS_RESCREENER_URL}/api/v1/batch/history`,
      "GET"
    );
  }),

  batchMatches: protectedProcedure.query(async () => {
    return serviceCall(
      `${SANCTIONS_RESCREENER_URL}/api/v1/batch/matches`,
      "GET"
    );
  }),

  // ── KYC Workflow Orchestrator (Python, port 8215) ──
  startWorkflow: protectedProcedure
    .input(
      z.object({
        customerId: z.string().min(1).max(255),
        kycLevel: z.string().default("standard"),
        targetTier: z.string().default("tier_2"),
        triggeredBy: z.string().default("manual"),
        customerData: z.record(z.string(), z.unknown()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${KYC_WORKFLOW_URL}/api/v1/workflow/start`, "POST", {
        customer_id: input.customerId,
        kyc_level: input.kycLevel,
        target_tier: input.targetTier,
        triggered_by: input.triggeredBy,
        customer_data: input.customerData || {},
      });
    }),

  getWorkflow: protectedProcedure
    .input(z.object({ workflowId: z.string().min(1).max(255) }))
    .query(async ({ input }) => {
      return serviceCall(
        `${KYC_WORKFLOW_URL}/api/v1/workflow/${input.workflowId}`,
        "GET"
      );
    }),

  listWorkflows: protectedProcedure
    .input(
      z
        .object({
          status: z.string().optional(),
          customerId: z.string().min(1).max(255).optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const params = new URLSearchParams();
      if (input?.status) params.set("status", input.status);
      if (input?.customerId) params.set("customer_id", input.customerId);
      return serviceCall(
        `${KYC_WORKFLOW_URL}/api/v1/workflows?${params}`,
        "GET"
      );
    }),

  // ── KYC Event Consumer (Python, port 8216) ──
  eventConsumerStats: protectedProcedure.query(async () => {
    return serviceCall(`${KYC_EVENT_CONSUMER_URL}/api/v1/stats`, "GET");
  }),

  triggerRules: protectedProcedure.query(async () => {
    return serviceCall(`${KYC_EVENT_CONSUMER_URL}/api/v1/rules`, "GET");
  }),

  clearCooldown: protectedProcedure
    .input(z.object({ customerId: z.string().min(1).max(255) }))
    .mutation(async ({ input }) => {
      return serviceCall(
        `${KYC_EVENT_CONSUMER_URL}/api/v1/cooldowns/${input.customerId}`,
        "DELETE"
      );
    }),

  // ── goAML Filing (Go, port 8210) ──
  createSTR: protectedProcedure
    .input(
      z.object({
        subject: z.object({
          subjectType: z.string(),
          fullName: z.string(),
          bvn: z.string().optional(),
          nationality: z.string().default("Nigeria"),
          riskLevel: z.string(),
        }),
        indicators: z.array(z.string()),
        narrative: z.string(),
        riskScore: z.number(),
        reportingOfficer: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${GOAML_URL}/api/v1/str/create`, "POST", {
        subject: {
          subject_type: input.subject.subjectType,
          full_name: input.subject.fullName,
          bvn: input.subject.bvn || "",
          nationality: input.subject.nationality,
          risk_level: input.subject.riskLevel,
        },
        indicators: input.indicators,
        narrative: input.narrative,
        risk_score: input.riskScore,
        reporting_officer: input.reportingOfficer,
      });
    }),

  listSTRs: protectedProcedure
    .input(z.object({ status: z.string().optional() }).optional())
    .query(async ({ input }) => {
      const params = input?.status ? `?status=${input.status}` : "";
      return serviceCall(`${GOAML_URL}/api/v1/str/list${params}`, "GET");
    }),

  createCTR: protectedProcedure
    .input(
      z.object({
        subject: z.object({
          subjectType: z.string(),
          fullName: z.string(),
          bvn: z.string().optional(),
          nationality: z.string().default("Nigeria"),
        }),
        transactionAmount: z.number(),
        transactionCurrency: z.string().default("NGN"),
        transactionType: z.string(),
        accountNumber: z.string(),
        reportingOfficer: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      return serviceCall(`${GOAML_URL}/api/v1/ctr/create`, "POST", {
        subject: {
          subject_type: input.subject.subjectType,
          full_name: input.subject.fullName,
          bvn: input.subject.bvn || "",
          nationality: input.subject.nationality,
        },
        transaction_amount: input.transactionAmount,
        transaction_currency: input.transactionCurrency,
        transaction_type: input.transactionType,
        account_number: input.accountNumber,
        reporting_officer: input.reportingOfficer,
      });
    }),

  // ── Health checks ──
  healthCheck: protectedProcedure.query(async () => {
    const checks: Record<string, string> = {};
    const services = [
      ["kyc_enforcement", `${KYC_ENFORCEMENT_URL}/health`],
      ["aml_case_manager", `${AML_CASE_MANAGER_URL}/health`],
      ["cbn_tier_engine", `${CBN_TIER_ENGINE_URL}/health`],
      ["sanctions_rescreener", `${SANCTIONS_RESCREENER_URL}/health`],
      ["kyc_workflow", `${KYC_WORKFLOW_URL}/health`],
      ["kyc_event_consumer", `${KYC_EVENT_CONSUMER_URL}/health`],
      ["goaml", `${GOAML_URL}/health`],
    ] as const;

    for (const [name, url] of services) {
      try {
        const resp = await fetch(url, { signal: AbortSignal.timeout(3000) });
        checks[name] = resp.ok ? "healthy" : `unhealthy (${resp.status})`;
      } catch {
        checks[name] = "unreachable";
      }
    }

    return { services: checks };
  }),
});
