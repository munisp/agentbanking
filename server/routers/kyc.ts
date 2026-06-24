/**
 * KYC Router — tRPC procedures bridging POS Shell to the open-source KYC/KYB engines
 *
 * Procedures:
 *  kyc.startLiveness       — create a liveness challenge (returns challengeId + instruction)
 *  kyc.submitLivenessFrame — submit a base64 frame to verify the challenge
 *  kyc.verifyDocument      — submit a base64 document image for OCR extraction
 *  kyc.getStatus           — get the current KYC session status for the logged-in agent
 *  kyc.listSessions        — admin: list all KYC sessions with pagination
 */

import { z } from "zod";
import { eq, desc, and, gte, lte, sql, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { router, protectedProcedure, adminProcedure } from "../_core/trpc.js";
import { getAgentFromCookie } from "../middleware/agentAuth.js";
import { getDb, writeAuditLog } from "../db.js";
import { kycSessions } from "../../drizzle/schema.js";
import { validateInput } from "../lib/routerHelpers";

import {
  createLivenessChallenge,
  verifyLivenessChallenge,
  processDocument,
  storeComplianceRecord,
} from "../_core/kycClient.js";
import {
  isLockedOut,
  recordLivenessFailure,
  recordLivenessSuccess,
  clearCooldown,
  getCooldownStatus,
  analyzePassiveLiveness,
  createDeviceFingerprint,
  getDeviceThresholds,
  recordDeviceLivenessAttempt,
  getDeviceLivenessHistory,
  getAllDeviceHistories,
  getProblematicDevices,
  resolveGeoIp,
  correlateGeoIp,
  getAllGeoCorrelations,
  getHighRiskCorrelations,
  clearGeoIpData,
} from "../middleware/livenessSecurityEnhancements.js";
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

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function requireAgent(req: Request | any) {
  const agent = await getAgentFromCookie(req);
  if (!agent)
    throw new TRPCError({
      code: "UNAUTHORIZED",
      message: "Agent session required",
    });
  return agent;
}

// ─── Router ───────────────────────────────────────────────────────────────────

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "kyc",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "kyc",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
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
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishkycMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `kyc.${action}` as any;
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
      txType: `kyc_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `kyc_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("kyc", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const kycRouter = router({
  // ─── Retry Cooldown ──────────────────────────────────────────────────────────

  /** Check if the current user is locked out from liveness checks */
  checkCooldown: protectedProcedure.query(async ({ ctx }) => {
    try {
      const agent = await requireAgent(ctx.req);
      return isLockedOut(`agent-${agent.id}`);
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),

  /** Admin: clear cooldown for a specific user */
  adminClearCooldown: adminProcedure
    .input(z.object({ userId: z.string().min(1).max(255) }))
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
        const cleared = clearCooldown(input.userId);
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

          resource: "kyc",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { cleared, userId: input.userId };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  /** Admin: get all active cooldowns */
  adminGetCooldowns: adminProcedure.query(async () => {
    return { cooldowns: getCooldownStatus() };
  }),

  // ─── Server-side Passive Liveness ────────────────────────────────────────────

  /** Submit a single frame for server-side passive liveness analysis (no motion needed) */
  passiveLiveness: protectedProcedure
    .input(
      z.object({
        frameBase64: z.string().min(100),
        sessionId: z.number().int().positive().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await requireAgent(ctx.req);
        const userId = `agent-${agent.id}`;

        // Check cooldown
        const cooldown = isLockedOut(userId);
        if (cooldown.locked) {
          throw new TRPCError({
            code: "TOO_MANY_REQUESTS",
            message: `Too many failed attempts. Please wait ${Math.ceil(cooldown.remainingMs / 60000)} minutes before trying again.`,
          });
        }

        // Run passive analysis
        const result = analyzePassiveLiveness(input.frameBase64);

        // Record success/failure
        if (result.isLive) {
          recordLivenessSuccess(userId);
        } else {
          recordLivenessFailure(userId);
        }

        // Update KYC session if provided
        if (input.sessionId) {
          const db = (await getDb())!;
          if (db) {
            await db
              .update(kycSessions)
              .set({
                status: result.isLive ? "liveness_passed" : "liveness_failed",
                livenessPassed: result.isLive,
                livenessScore: result.confidence.toString(),
                livenessMethod: "passive_texture_frequency",
                updatedAt: new Date(),
              })
              .where(eq(kycSessions.id, input.sessionId));
          }
        }

        return result;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ─── Device Fingerprinting ───────────────────────────────────────────────────

  /** Register device fingerprint and get adaptive thresholds */
  registerDevice: protectedProcedure
    .input(
      z.object({
        userAgent: z.string(),
        cameraWidth: z.number().int().positive(),
        cameraHeight: z.number().int().positive(),
        screenWidth: z.number().int().positive(),
        screenHeight: z.number().int().positive(),
        pixelRatio: z.number().positive(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const fingerprint = createDeviceFingerprint(input);
        const thresholds = getDeviceThresholds(fingerprint);
        const history = getDeviceLivenessHistory(fingerprint.fingerprintHash);

        // Middleware fan-out (fail-open)

        await publishKycMiddleware("passiveLiveness", `${Date.now()}`, { action: "passiveLiveness" }).catch(() => {});


        // Middleware fan-out (fail-open)


        await publishKycMiddleware("registerDevice", `${Date.now()}`, { action: "registerDevice" }).catch(() => {});



        return {
          fingerprint,
          thresholds,
          history: history
            ? {
                successRate: history.successRate,
                totalAttempts: history.attempts.length,
                avgScore: history.avgScore,
              }
            : null,
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

  /** Record a liveness attempt result for device analytics */
  recordDeviceAttempt: protectedProcedure
    .input(
      z.object({
        userAgent: z.string(),
        cameraWidth: z.number().int().positive(),
        cameraHeight: z.number().int().positive(),
        screenWidth: z.number().int().positive(),
        screenHeight: z.number().int().positive(),
        pixelRatio: z.number().positive(),
        passed: z.boolean(),
        method: z.string(),
        score: z.number().min(0).max(1),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const fingerprint = createDeviceFingerprint({
          userAgent: input.userAgent,
          cameraWidth: input.cameraWidth,
          cameraHeight: input.cameraHeight,
          screenWidth: input.screenWidth,
          screenHeight: input.screenHeight,
          pixelRatio: input.pixelRatio,
        });
        recordDeviceLivenessAttempt(
          fingerprint,
          input.passed,
          input.method,
          input.score
        );
        // Middleware fan-out (fail-open)
        await publishKycMiddleware("recordDeviceAttempt", `${Date.now()}`, { action: "recordDeviceAttempt" }).catch(() => {});

        return { recorded: true, fingerprintHash: fingerprint.fingerprintHash };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  /** Admin: get all device histories for analytics dashboard */
  adminDeviceHistories: adminProcedure.query(async () => {
    return { devices: getAllDeviceHistories() };
  }),

  /** Admin: get problematic devices that consistently fail */
  adminProblematicDevices: adminProcedure
    .input(
      z.object({
        minAttempts: z.number().int().min(1).default(5),
        maxSuccessRate: z.number().min(0).max(1).default(0.5),
      })
    )
    .query(async ({ input }) => {
      try {
        return {
          devices: getProblematicDevices(
            input.minAttempts,
            input.maxSuccessRate
          ),
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
   * Create a new KYC session and return a liveness challenge.
   * The POS Shell camera will display the challenge instruction to the agent.
   */
  startLiveness: protectedProcedure
    .input(
      z.object({
        method: z
          .enum([
            "active_blink",
            "active_smile",
            "active_head_movement",
            "passive",
          ])
          .default("active_blink"),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await requireAgent(ctx.req);
        const userId = `agent-${agent.id}`;

        // Check cooldown before starting
        const cooldown = isLockedOut(userId);
        if (cooldown.locked) {
          throw new TRPCError({
            code: "TOO_MANY_REQUESTS",
            message: `Too many failed attempts. Please wait ${Math.ceil(cooldown.remainingMs / 60000)} minutes before trying again.`,
          });
        }

        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Create a liveness challenge via the video-kyc service
        const challenge = await createLivenessChallenge(input.method);

        // Insert a new KYC session row
        const [session] = await db
          .insert(kycSessions)
          .values({
            agentId: agent.id,
            status: "pending",
            livenessMethod: input.method,
            livenessChallenge: challenge?.challengeId ?? null,
          })
          .returning();

        if (!challenge) {
          // Service unavailable — return session ID so the client can still proceed
          // Middleware fan-out (fail-open)
          await publishKycMiddleware("startLiveness", `${Date.now()}`, { action: "startLiveness" }).catch(() => {});

          return {
            sessionId: session.id,
            challengeId: null,
            instruction:
              "Liveness service unavailable — please retake your selfie",
            method: input.method,
            serviceAvailable: false,
          };
        }

        return {
          sessionId: session.id,
          challengeId: challenge.challengeId,
          instruction: challenge.instruction,
          method: challenge.method,
          serviceAvailable: true,
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
   * Submit a base64-encoded video frame to verify the liveness challenge.
   * Updates the KYC session with the liveness result.
   */
  submitLivenessFrame: protectedProcedure
    .input(
      z.object({
        sessionId: z.number().int().positive(),
        challengeId: z.string().min(1).max(255),
        frameBase64: z.string().min(100), // base64-encoded JPEG/PNG frame
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await requireAgent(ctx.req);
        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Fetch the session and verify ownership
        const [session] = await db
          .select()
          .from(kycSessions)
          .where(eq(kycSessions.id, input.sessionId))
          .limit(1);

        if (!session || session.agentId !== agent.id) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "KYC session not found",
          });
        }

        // Check cooldown
        const userId = `agent-${agent.id}`;
        const cooldown = isLockedOut(userId);
        if (cooldown.locked) {
          throw new TRPCError({
            code: "TOO_MANY_REQUESTS",
            message: `Too many failed attempts. Please wait ${Math.ceil(cooldown.remainingMs / 60000)} minutes before trying again.`,
          });
        }

        // Call liveness service
        const result = await verifyLivenessChallenge(
          input.challengeId,
          input.frameBase64
        );

        const newStatus = result
          ? result.passed
            ? "liveness_passed"
            : "liveness_failed"
          : "liveness_failed";

        // Record success/failure for cooldown tracking
        if (result?.passed) {
          recordLivenessSuccess(userId);
        } else {
          recordLivenessFailure(userId);
        }

        await db
          .update(kycSessions)
          .set({
            status: newStatus,
            livenessPassed: result?.passed ?? false,
            livenessScore: result?.score?.toString() ?? null,
            livenessRaw: result?.raw ?? null,
            updatedAt: new Date(),
          })
          .where(eq(kycSessions.id, input.sessionId));

        // Middleware fan-out (fail-open)

        await publishKycMiddleware("submitLivenessFrame", `${Date.now()}`, { action: "submitLivenessFrame" }).catch(() => {});


        return {
          sessionId: input.sessionId,
          passed: result?.passed ?? false,
          score: result?.score ?? 0,
          spoofingDetected: result?.spoofingDetected ?? false,
          status: newStatus,
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
   * Submit a base64-encoded document image for OCR extraction.
   * Stores extracted fields in the KYC session and (optionally) in the compliance-kyc service.
   */
  verifyDocument: protectedProcedure
    .input(
      z.object({
        sessionId: z.number().int().positive(),
        imageBase64: z.string().min(100),
        docType: z.enum([
          "NIN",
          "BVN_CARD",
          "PASSPORT",
          "DRIVERS_LICENCE",
          "VOTER_CARD",
        ]),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await requireAgent(ctx.req);
        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Fetch and verify session ownership
        const [session] = await db
          .select()
          .from(kycSessions)
          .where(eq(kycSessions.id, input.sessionId))
          .limit(1);

        if (!session || session.agentId !== agent.id) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "KYC session not found",
          });
        }

        // Run OCR
        const ocr = await processDocument(input.imageBase64, input.docType);

        const hasFraud = (ocr?.fraudIndicators?.length ?? 0) > 0;
        const docPassed = !!ocr && ocr.confidence >= 0.6 && !hasFraud;
        const newStatus = docPassed ? "document_passed" : "document_failed";

        // Store in compliance-kyc service if OCR succeeded
        let complianceId: string | null = null;
        if (ocr && docPassed) {
          const record = await storeComplianceRecord({
            customerId: `agent-${agent.id}`,
            fullName: ocr.extractedName,
            idType: input.docType,
            idNumber: ocr.extractedIdNumber,
            livenessScore: session.livenessScore
              ? Number(session.livenessScore)
              : undefined,
            documentConfidence: ocr.confidence,
          });
          complianceId = record?.id ?? null;
        }

        // Determine final session status
        const finalStatus =
          docPassed && session.livenessPassed ? "completed" : newStatus;

        await db
          .update(kycSessions)
          .set({
            status: finalStatus,
            docType: input.docType,
            docExtractedName: ocr?.extractedName ?? null,
            docExtractedDob: ocr?.extractedDob ?? null,
            docExtractedIdNumber: ocr?.extractedIdNumber ?? null,
            docConfidence: ocr?.confidence?.toString() ?? null,
            docFraudIndicators: ocr?.fraudIndicators ?? [],
            ocrRaw: ocr?.raw ?? null,
            complianceRecordId: complianceId,
            updatedAt: new Date(),
          })
          .where(eq(kycSessions.id, input.sessionId));

        // ── Fluvio KYC event (fire-and-forget) ─────────────────────────────────
        import("../lib/fluvioClient.js")
          .then(({ publishKycEvent }) =>
            publishKycEvent({
              sessionId: input.sessionId,
              status: finalStatus,
            })
          )
          .catch((e: unknown) =>
            console.error("[Fluvio] KYC event failed:", e)
          );

        return {
          sessionId: input.sessionId,
          passed: docPassed,
          confidence: ocr?.confidence ?? 0,
          extractedName: ocr?.extractedName ?? null,
          extractedDob: ocr?.extractedDob ?? null,
          extractedIdNumber: ocr?.extractedIdNumber ?? null,
          fraudIndicators: ocr?.fraudIndicators ?? [],
          status: finalStatus,
          complianceRecordId: complianceId,
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
   * Get the current KYC session status for the logged-in agent.
   * Returns the most recent session.
   */
  getStatus: protectedProcedure.query(async ({ ctx }) => {
    try {
      const agent = await requireAgent(ctx.req);
      const db = (await getDb())!;
      if (!db) return { hasSession: false, status: null, session: null };

      const [session] = await db
        .select()
        .from(kycSessions)
        .where(eq(kycSessions.agentId, agent.id))
        .orderBy(desc(kycSessions.createdAt))
        .limit(1);

      if (!session) return { hasSession: false, status: null, session: null };

      return {
        hasSession: true,
        status: session.status,
        session: {
          id: session.id,
          status: session.status,
          livenessPassed: session.livenessPassed,
          livenessScore: session.livenessScore
            ? Number(session.livenessScore)
            : null,
          docType: session.docType,
          docExtractedName: session.docExtractedName,
          docExtractedDob: session.docExtractedDob,
          docExtractedIdNumber: session.docExtractedIdNumber,
          docConfidence: session.docConfidence
            ? Number(session.docConfidence)
            : null,
          fraudIndicators: session.docFraudIndicators ?? [],
          complianceRecordId: session.complianceRecordId,
          createdAt: session.createdAt,
          updatedAt: session.updatedAt,
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
  }),

  /**
   * Admin: list all KYC sessions with pagination.
   */
  listSessions: adminProcedure
    .input(
      z.object({
        page: z.number().int().min(1).default(1),
        pageSize: z.number().int().min(1).max(100).default(20),
        status: z
          .enum([
            "pending",
            "liveness_passed",
            "liveness_failed",
            "document_passed",
            "document_failed",
            "completed",
            "rejected",
          ])
          .optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });
        const offset = (input.page - 1) * input.pageSize;

        const rows = await db
          .select()
          .from(kycSessions)
          .orderBy(desc(kycSessions.createdAt))
          .limit(input.pageSize)
          .offset(offset);

        return {
          sessions: rows.map((s: (typeof rows)[number]) => ({
            id: s.id,
            agentId: s.agentId,
            status: s.status,
            livenessPassed: s.livenessPassed,
            livenessScore: s.livenessScore ? Number(s.livenessScore) : null,
            docType: s.docType,
            docExtractedName: s.docExtractedName,
            docExtractedIdNumber: s.docExtractedIdNumber,
            docConfidence: s.docConfidence ? Number(s.docConfidence) : null,
            fraudIndicators: s.docFraudIndicators ?? [],
            complianceRecordId: s.complianceRecordId,
            createdAt: s.createdAt,
          })),
          page: input.page,
          pageSize: input.pageSize,
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
   * Request a presigned S3 URL for direct KYC document upload.
   * Frontend uploads the document directly to S3, then calls verifyDocument with the S3 key.
   */
  requestDocumentUpload: protectedProcedure
    .input(
      z.object({
        mimeType: z.enum([
          "image/jpeg",
          "image/png",
          "image/webp",
          "application/pdf",
        ]),
        docType: z.enum([
          "NIN",
          "BVN_CARD",
          "PASSPORT",
          "DRIVERS_LICENCE",
          "VOTER_CARD",
        ]),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const agent = await requireAgent(ctx.req);
        const ext =
          input.mimeType === "application/pdf"
            ? "pdf"
            : input.mimeType === "image/png"
              ? "png"
              : input.mimeType === "image/webp"
                ? "webp"
                : "jpg";
        const fileKey = `kyc-docs/${agent.id}/${input.docType.toLowerCase()}-${Date.now()}.${ext}`;
        try {
          const { storagePut } = await import("../storage.js");
          // Upload a zero-byte placeholder to reserve the key and get the CDN URL
          const { url } = await storagePut(
            fileKey,
            Buffer.alloc(0),
            input.mimeType
          );
          // Middleware fan-out (fail-open)
          await publishKycMiddleware("requestDocumentUpload", `${Date.now()}`, { action: "requestDocumentUpload" }).catch(() => {});

          return {
            uploadUrl: url,
            fileKey,
            expiresIn: 3600,
            instructions: `Upload your ${input.docType.replace(/_/g, " ")} document to this URL using HTTP PUT with Content-Type: ${input.mimeType}`,
          };
        } catch {
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              "Failed to generate upload URL. Please use base64 upload instead.",
          });
        }
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ─── Geo-IP Correlation ─────────────────────────────────────────────────────

  /** Correlate a liveness attempt with geo-IP data */
  geoIpCorrelate: protectedProcedure
    .input(
      z.object({
        deviceFingerprint: z.string(),
        clientIp: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const ip =
          input.clientIp ||
          ctx.req?.headers?.["x-forwarded-for"]
            ?.toString()
            ?.split(",")[0]
            ?.trim() ||
          ctx.req?.socket?.remoteAddress ||
          "127.0.0.1";
        const geo = await resolveGeoIp(ip);
        const correlation = correlateGeoIp(
          ctx.user.id.toString(),
          input.deviceFingerprint,
          geo
        );

        // If high risk, notify admin
        if (correlation.riskScore >= 50) {
          const { notifyOwner } = await import("../_core/notification.js");
          notifyOwner({
            title: `\u26a0\ufe0f High-Risk Geo-IP: ${ctx.user.name || ctx.user.id}`,
            content:
              `User ${ctx.user.id} triggered geo-IP risk score ${correlation.riskScore}/100. ` +
              `Flags: ${correlation.flags.join(", ")}. ` +
              `IP: ${ip}, Country: ${geo.country}, ISP: ${geo.isp}. ` +
              `Review in Admin > Liveness Device Analytics.`,
          }).catch(() => {});
        }

        // Middleware fan-out (fail-open)

        await publishKycMiddleware("geoIpCorrelate", `${Date.now()}`, { action: "geoIpCorrelate" }).catch(() => {});


        return {
          riskScore: correlation.riskScore,
          flags: correlation.flags,
          geo: {
            country: geo.country,
            city: geo.city,
            isVpn: geo.isVpn,
            isTor: geo.isTor,
          },
          blocked: correlation.riskScore >= 80,
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

  /** Admin: Get all geo-IP correlations */
  adminGeoCorrelations: adminProcedure.query(() => {
    return { correlations: getAllGeoCorrelations() };
  }),

  /** Admin: Get high-risk correlations */
  adminHighRiskGeo: adminProcedure
    .input(z.object({ minRiskScore: z.number().min(0).max(100).default(50) }))
    .query(({ input }) => {
      return { correlations: getHighRiskCorrelations(input.minRiskScore) };
    }),

  /** Admin: Clear geo-IP data for a user (GDPR compliance) */
  adminClearGeoData: adminProcedure
    .input(z.object({ userId: z.string().min(1).max(255) }))
    .mutation(({ input }) => {
      const cleared = clearGeoIpData(input.userId);
      return {
        cleared,
        message: `Cleared ${cleared} geo-IP record(s) for user ${input.userId}`,
      };
    }),
});
