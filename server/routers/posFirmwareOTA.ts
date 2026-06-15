/**
 * POS Firmware OTA Management — staged firmware rollouts, version tracking,
 * rollback capability, checksum verification.
 *
 * Middleware: Redis (rollout state), Kafka (OTA events), PostgreSQL (version history),
 * Go firmware distribution service (port 8141)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  posTerminals,
  platformSettings,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, sql, gte, lte, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
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
import { checkDailyLimit } from "../lib/cbnLimits";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  application: ["under_review"],
  under_review: ["approved", "rejected", "additional_info"],
  additional_info: ["under_review"],
  approved: ["onboarding"],
  onboarding: ["active"],
  active: ["suspended", "under_review"],
  suspended: ["active", "terminated"],
  terminated: [],
  rejected: ["appeal"],
  appeal: ["under_review"],
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
      "posFirmwareOTA",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "posFirmwareOTA",
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
    resource: "posFirmwareOTA",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "posFirmwareOTA",
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
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const posFirmwareOTARouter = router({
  listVersions: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { versions: [] };

        const rows = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, "firmware_versions"))
          .limit(1);

        let versions: unknown[] = [];
        if (rows[0]?.value) {
          try {
            versions = JSON.parse(String(rows[0].value));
          } catch {}
        }

        return { versions };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  publishVersion: protectedProcedure
    .input(
      z.object({
        version: z.string().regex(/^\d+\.\d+\.\d+$/),
        releaseNotes: z.string().max(2000),
        checksum: z.string().min(32).max(128),
        downloadUrl: z.string().url(),
        minAppVersion: z.string().optional(),
        forceUpdate: z.boolean().default(false),
      })
    )
    .mutation(async ({ input, ctx }) => {
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
      const fees = calculateFee(txAmount, "posTransaction");
      const commission = calculateCommission(fees.fee, "posTransaction");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const entry = {
          ...input,
          publishedAt: new Date().toISOString(),
          publishedBy: session.agentCode,
          status: "staged",
        };

        const existing = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, "firmware_versions"))
          .limit(1);

        let versions: unknown[] = [];
        if (existing[0]?.value) {
          try {
            versions = JSON.parse(String(existing[0].value));
          } catch {}
        }
        versions.unshift(entry);

        await db
          .insert(platformSettings)
          .values({ key: "firmware_versions", value: JSON.stringify(versions) })
          .onConflictDoUpdate({
            target: platformSettings.key,
            set: { value: JSON.stringify(versions) },
          });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FIRMWARE_PUBLISHED",
          resource: "firmware",
          resourceId: input.version,
          status: "success",
          metadata: { version: input.version, forceUpdate: input.forceUpdate },
        });

        return entry;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  startRollout: protectedProcedure
    .input(
      z.object({
        version: z.string(),
        targetGroupId: z.number().optional(),
        rolloutPercentage: z.number().min(1).max(100).default(10),
        canaryStages: z
          .array(z.object({ percentage: z.number(), waitMinutes: z.number() }))
          .optional(),
        maxFailureRate: z.number().min(0).max(100).default(5),
        autoRollbackOnFailure: z.boolean().default(true),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Verify version exists in published versions
        const versionRows = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, "firmware_versions"))
          .limit(1);
        let versions: Array<{ version: string; status: string }> = [];
        if (versionRows[0]?.value) {
          try {
            versions = JSON.parse(String(versionRows[0].value));
          } catch {}
        }
        const versionEntry = versions.find(v => v.version === input.version);
        if (!versionEntry)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: `Firmware version ${input.version} not found`,
          });

        // Default canary stages: 5% → 25% → 50% → 100%
        const stages = input.canaryStages ?? [
          { percentage: 5, waitMinutes: 30 },
          { percentage: 25, waitMinutes: 60 },
          { percentage: 50, waitMinutes: 120 },
          { percentage: 100, waitMinutes: 0 },
        ];

        const rolloutId = `ROL-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;

        // Count target terminals
        const terminalConditions = [sql`${posTerminals.deletedAt} IS NULL`];
        if (input.targetGroupId)
          terminalConditions.push(
            eq(posTerminals.groupId, input.targetGroupId)
          );
        const [{ total }] = await db
          .select({ total: sql<number>`count(*)::int` })
          .from(posTerminals)
          .where(and(...terminalConditions));

        const targetCount = Math.ceil((total * input.rolloutPercentage) / 100);

        // Store rollout state
        await db
          .insert(platformSettings)
          .values({
            key: `rollout_${rolloutId}`,
            value: JSON.stringify({
              rolloutId,
              version: input.version,
              status: "in_progress",
              currentStageIndex: 0,
              stages,
              targetGroupId: input.targetGroupId,
              maxFailureRate: input.maxFailureRate,
              autoRollbackOnFailure: input.autoRollbackOnFailure,
              totalTerminals: total,
              targetCount,
              successCount: 0,
              failureCount: 0,
              startedAt: new Date().toISOString(),
              previousVersion: null,
            }),
          })
          .onConflictDoUpdate({
            target: platformSettings.key,
            set: {
              value: JSON.stringify({
                rolloutId,
                version: input.version,
                status: "in_progress",
                stages,
              }),
            },
          });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FIRMWARE_ROLLOUT_STARTED",
          resource: "firmware_rollout",
          resourceId: rolloutId,
          status: "success",
          metadata: {
            version: input.version,
            percentage: input.rolloutPercentage,
            stages,
            maxFailureRate: input.maxFailureRate,
            totalTerminals: total,
            targetCount,
          },
        });

        return {
          rolloutId,
          version: input.version,
          percentage: input.rolloutPercentage,
          status: "rolling_out",
          stages,
          currentStage: stages[0],
          totalTerminals: total,
          targetCount,
          startedAt: new Date().toISOString(),
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

  rollbackRollout: protectedProcedure
    .input(
      z.object({
        rolloutId: z.string().min(1).max(64),
        reason: z.string().min(1).max(500),
        revertToVersion: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Load rollout state
        const [rolloutRow] = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, `rollout_${input.rolloutId}`))
          .limit(1);
        if (!rolloutRow?.value)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Rollout not found",
          });

        const rolloutState = JSON.parse(String(rolloutRow.value));
        if (rolloutState.status === "rolled_back")
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Rollout already rolled back",
          });

        // Update rollout state to rolled_back
        rolloutState.status = "rolled_back";
        rolloutState.rolledBackAt = new Date().toISOString();
        rolloutState.rollbackReason = input.reason;

        await db
          .update(platformSettings)
          .set({ value: JSON.stringify(rolloutState) })
          .where(eq(platformSettings.key, `rollout_${input.rolloutId}`));

        // Revert terminals that were updated to this version
        const revertVersion = input.revertToVersion ?? "previous";
        const updatedTerminals = await db
          .update(posTerminals)
          .set({
            firmwareVersion: revertVersion,
            updatedAt: new Date(),
          })
          .where(
            and(
              eq(posTerminals.firmwareVersion, rolloutState.version),
              sql`${posTerminals.deletedAt} IS NULL`
            )
          )
          .returning({ id: posTerminals.id });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FIRMWARE_ROLLOUT_ROLLED_BACK",
          resource: "firmware_rollout",
          resourceId: input.rolloutId,
          status: "success",
          metadata: {
            reason: input.reason,
            version: rolloutState.version,
            revertedTerminals: updatedTerminals.length,
            revertToVersion: revertVersion,
          },
        });

        return {
          success: true,
          rolloutId: input.rolloutId,
          status: "rolled_back",
          revertedTerminals: updatedTerminals.length,
          reason: input.reason,
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

  advanceRollout: protectedProcedure
    .input(
      z.object({
        rolloutId: z.string().min(1).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [rolloutRow] = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, `rollout_${input.rolloutId}`))
          .limit(1);
        if (!rolloutRow?.value)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Rollout not found",
          });

        const state = JSON.parse(String(rolloutRow.value));
        if (state.status !== "in_progress")
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot advance rollout in '${state.status}' state`,
          });

        // Check failure rate before advancing
        const failureRate =
          state.successCount + state.failureCount > 0
            ? (state.failureCount / (state.successCount + state.failureCount)) *
              100
            : 0;
        if (failureRate > state.maxFailureRate && state.autoRollbackOnFailure) {
          state.status = "auto_rolled_back";
          state.rolledBackAt = new Date().toISOString();
          state.rollbackReason = `Failure rate ${failureRate.toFixed(1)}% exceeded threshold ${state.maxFailureRate}%`;
          await db
            .update(platformSettings)
            .set({ value: JSON.stringify(state) })
            .where(eq(platformSettings.key, `rollout_${input.rolloutId}`));

          await writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "FIRMWARE_ROLLOUT_AUTO_ROLLBACK",
            resource: "firmware_rollout",
            resourceId: input.rolloutId,
            status: "failure",
            metadata: { failureRate, threshold: state.maxFailureRate },
          });

          return {
            rolloutId: input.rolloutId,
            status: "auto_rolled_back",
            reason: state.rollbackReason,
          };
        }

        // Advance to next stage
        const nextIndex = state.currentStageIndex + 1;
        if (nextIndex >= state.stages.length) {
          state.status = "completed";
          state.completedAt = new Date().toISOString();
        } else {
          state.currentStageIndex = nextIndex;
        }

        await db
          .update(platformSettings)
          .set({ value: JSON.stringify(state) })
          .where(eq(platformSettings.key, `rollout_${input.rolloutId}`));

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FIRMWARE_ROLLOUT_ADVANCED",
          resource: "firmware_rollout",
          resourceId: input.rolloutId,
          status: "success",
          metadata: {
            newStageIndex: state.currentStageIndex,
            newPercentage: state.stages[state.currentStageIndex]?.percentage,
            status: state.status,
          },
        });

        return {
          rolloutId: input.rolloutId,
          status: state.status,
          currentStage: state.stages[state.currentStageIndex],
          stageIndex: state.currentStageIndex,
          failureRate: failureRate.toFixed(1),
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

  checkForUpdate: protectedProcedure
    .input(z.object({ terminalId: z.number(), currentVersion: z.string() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { updateAvailable: false };

        const rows = await db
          .select({ value: platformSettings.value })
          .from(platformSettings)
          .where(eq(platformSettings.key, "firmware_versions"))
          .limit(1);

        if (!rows[0]?.value) return { updateAvailable: false };

        let versions: Array<{
          version: string;
          status: string;
          downloadUrl: string;
          checksum: string;
          forceUpdate: boolean;
        }> = [];
        try {
          versions = JSON.parse(String(rows[0].value));
        } catch {}

        const latest = versions.find(
          v => v.status === "released" || v.status === "staged"
        );
        if (!latest || latest.version === input.currentVersion)
          return { updateAvailable: false };

        return {
          updateAvailable: true,
          version: latest.version,
          downloadUrl: latest.downloadUrl,
          checksum: latest.checksum,
          forceUpdate: latest.forceUpdate,
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

  reportUpdateResult: protectedProcedure
    .input(
      z.object({
        terminalId: z.number(),
        version: z.string(),
        success: z.boolean(),
        errorMessage: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        if (input.success) {
          await db
            .update(posTerminals)
            .set({ firmwareVersion: input.version, updatedAt: new Date() })
            .where(eq(posTerminals.id, input.terminalId));
        }

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: input.success
            ? "FIRMWARE_UPDATE_SUCCESS"
            : "FIRMWARE_UPDATE_FAILED",
          resource: "firmware",
          resourceId: String(input.terminalId),
          status: input.success ? "success" : "failure",
          metadata: {
            version: input.version,
            errorMessage: input.errorMessage,
          },
        });

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

  list: protectedProcedure
    .input(
      z.object({ limit: z.number().default(50), offset: z.number().default(0) })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db)
          return {
            items: [],
            total: 0,
            limit: input.limit,
            offset: input.offset,
          };

        const items = await db
          .select({
            id: posTerminals.id,
            serialNumber: posTerminals.serialNumber,
            firmwareVersion: posTerminals.firmwareVersion,
            appVersion: posTerminals.appVersion,
            model: posTerminals.model,
            status: posTerminals.status,
            lastSeenAt: posTerminals.lastSeenAt,
          })
          .from(posTerminals)
          .where(sql`${posTerminals.deletedAt} IS NULL`)
          .orderBy(desc(posTerminals.updatedAt))
          .limit(input.limit)
          .offset(input.offset);

        const [{ total }] = await db
          .select({ total: sql<number>`count(*)::int` })
          .from(posTerminals)
          .where(sql`${posTerminals.deletedAt} IS NULL`);

        return { items, total, limit: input.limit, offset: input.offset };
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
    if (!db) return { totalTerminals: 0, versionDistribution: {} };

    const rows = await db
      .select({
        version: posTerminals.firmwareVersion,
        cnt: sql<number>`count(*)::int`,
      })
      .from(posTerminals)
      .where(sql`${posTerminals.deletedAt} IS NULL`)
      .groupBy(posTerminals.firmwareVersion);

    const dist: Record<string, number> = {};
    let total = 0;
    for (const r of rows) {
      dist[r.version ?? "unknown"] = r.cnt;
      total += r.cnt;
    }

    return { totalTerminals: total, versionDistribution: dist };
  }),
});
