// TypeScript enabled — Sprint 96 security audit
/**
 * 54agent Temporal Client
 * Provides a Temporal client for scheduling and triggering workflows.
 *
 * Workflows:
 *   SettlementWorkflow — daily settlement at 17:00 WAT
 *     Activities: aggregateSettlement → notifyAgents → archiveSettlement
 *
 * Audit: All workflow starts and completions are logged to the
 * temporal_workflow_log PostgreSQL table (migration 0047).
 *
 * Usage:
 *   import { triggerSettlement, getTemporalClient } from "./temporal";
 *   await triggerSettlement({ date: "2025-01-15" });
 */
import {
  Connection,
  Client,
  WorkflowExecutionAlreadyStartedError,
} from "@temporalio/client";
import logger from "./_core/logger";

const TEMPORAL_ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";
const TEMPORAL_NAMESPACE = process.env.TEMPORAL_NAMESPACE ?? "default";
const SETTLEMENT_TASK_QUEUE = "settlement-queue";

let _client: Client | null = null;

/**
 * Get (or create) the shared Temporal client.
 * Returns null if Temporal is unavailable — callers must handle gracefully.
 */
export async function getTemporalClient(): Promise<Client | null> {
  if (_client) return _client;

  try {
    const connection = await Connection.connect({
      address: TEMPORAL_ADDRESS,
    });
    _client = new Client({
      connection,
      namespace: TEMPORAL_NAMESPACE,
    });
    logger.info(
      `[Temporal] Connected to ${TEMPORAL_ADDRESS} (namespace: ${TEMPORAL_NAMESPACE})`
    );
    return _client;
  } catch (err) {
    logger.warn(
      { err },
      "[Temporal] Connection failed — workflow scheduling unavailable"
    );
    return null;
  }
}

/**
 * Persist a workflow start event to the temporal_workflow_log table.
 * Fire-and-forget — never blocks the workflow trigger path.
 */
async function logWorkflowStart(opts: {
  workflowId: string;
  workflowType: string;
  runId?: string;
  taskQueue: string;
  namespace: string;
  inputPayload?: Record<string, unknown>;
  triggeredBy?: string;
  agentCode?: string;
  tenantId?: number;
}): Promise<void> {
  try {
    const { getDb } = await import("./db");
    const { temporalWorkflowLog } = await import("../drizzle/schema");
    const db = await getDb();
    if (!db) return;
    await db.insert(temporalWorkflowLog).values({
      workflowId: opts.workflowId,
      workflowType: opts.workflowType,
      runId: opts.runId,
      taskQueue: opts.taskQueue,
      namespace: opts.namespace,
      status: "running",
      inputPayload: opts.inputPayload,
      triggeredBy: opts.triggeredBy,
      agentCode: opts.agentCode,
      tenantId: opts.tenantId,
    });
  } catch {
    // Persistence failure must never break the workflow trigger path
  }
}

export interface SettlementInput {
  date: string; // ISO date string e.g. "2025-01-15"
  triggeredBy?: string; // "cron" | "manual" | agentCode
}

export interface SettlementResult {
  agentsProcessed: number;
  totalVolume: number;
  totalCommission: number;
  smsCount: number;
  errors: string[];
  completedAt: string;
}

/**
 * Trigger the SettlementWorkflow for a given date.
 * Uses workflowId = `settlement-{date}` to prevent duplicate runs.
 */
export async function triggerSettlement(
  input: SettlementInput
): Promise<string | null> {
  const client = await getTemporalClient();
  if (!client) {
    logger.warn("[Temporal] Cannot trigger settlement — Temporal unavailable");
    return null;
  }

  const workflowId = `settlement-${input.date}`;

  try {
    const handle = await client.workflow.start("SettlementWorkflow", {
      taskQueue: SETTLEMENT_TASK_QUEUE,
      workflowId,
      args: [input],
    });
    logger.info(
      `[Temporal] Settlement workflow started: ${workflowId} (runId: ${handle.firstExecutionRunId})`
    );
    // Persist workflow start to audit log
    void logWorkflowStart({
      workflowId,
      workflowType: "SettlementWorkflow",
      runId: handle.firstExecutionRunId,
      taskQueue: SETTLEMENT_TASK_QUEUE,
      namespace: TEMPORAL_NAMESPACE,
      inputPayload: input as unknown as Record<string, unknown>,
      triggeredBy: input.triggeredBy ?? "manual",
    });
    return handle.firstExecutionRunId;
  } catch (err) {
    if (err instanceof WorkflowExecutionAlreadyStartedError) {
      logger.warn(`[Temporal] Settlement for ${input.date} already running`);
      return null;
    }
    logger.error({ err }, "[Temporal] Failed to start settlement workflow");
    return null;
  }
}

/**
 * Trigger any named workflow and log it to the audit table.
 */
export async function triggerWorkflow(opts: {
  workflowType: string;
  workflowId: string;
  taskQueue?: string;
  args?: unknown[];
  triggeredBy?: string;
  agentCode?: string;
  tenantId?: number;
}): Promise<string | null> {
  const client = await getTemporalClient();
  if (!client) {
    logger.warn(`[Temporal] Cannot trigger ${opts.workflowType} — Temporal unavailable`);
    return null;
  }

  const taskQueue = opts.taskQueue ?? SETTLEMENT_TASK_QUEUE;

  try {
    const handle = await client.workflow.start(opts.workflowType, {
      taskQueue,
      workflowId: opts.workflowId,
      args: opts.args ?? [],
    });
    logger.info(
      `[Temporal] ${opts.workflowType} started: ${opts.workflowId} (runId: ${handle.firstExecutionRunId})`
    );
    void logWorkflowStart({
      workflowId: opts.workflowId,
      workflowType: opts.workflowType,
      runId: handle.firstExecutionRunId,
      taskQueue,
      namespace: TEMPORAL_NAMESPACE,
      inputPayload: (opts.args?.[0] ?? {}) as Record<string, unknown>,
      triggeredBy: opts.triggeredBy,
      agentCode: opts.agentCode,
      tenantId: opts.tenantId,
    });
    return handle.firstExecutionRunId;
  } catch (err) {
    if (err instanceof WorkflowExecutionAlreadyStartedError) {
      logger.warn(`[Temporal] ${opts.workflowType} ${opts.workflowId} already running`);
      return null;
    }
    logger.error({ err }, `[Temporal] Failed to start ${opts.workflowType}`);
    return null;
  }
}

/**
 * Schedule a daily settlement cron via Temporal.
 * This replaces the node-cron schedule when Temporal is available.
 * Cron: "0 17 * * *" = 17:00 UTC daily (adjust for WAT = UTC+1)
 */
export async function scheduleSettlementCron(): Promise<void> {
  const client = await getTemporalClient();
  if (!client) {
    logger.info(
      "[Temporal] Skipping cron schedule — Temporal unavailable (node-cron will be used)"
    );
    return;
  }

  const scheduleId = "daily-settlement-cron";

  try {
    await client.schedule.create({
      scheduleId,
      spec: {
        cronExpressions: ["0 16 * * *"], // 16:00 UTC = 17:00 WAT
      },
      action: {
        type: "startWorkflow",
        workflowType: "SettlementWorkflow",
        taskQueue: SETTLEMENT_TASK_QUEUE,
        args: [{ triggeredBy: "cron" }],
      },
    });
    logger.info(
      `[Temporal] Daily settlement cron scheduled (scheduleId: ${scheduleId})`
    );
  } catch (err: unknown) {
    // Schedule already exists — that's fine
    if (err instanceof Error && err.message?.includes("already exists")) {
      logger.debug("[Temporal] Settlement cron schedule already exists");
    } else {
      logger.warn(
        { err },
        "[Temporal] Failed to create settlement cron schedule"
      );
    }
  }
}

/**
 * Get the status of a settlement workflow by date.
 */
export async function getSettlementStatus(date: string): Promise<{
  status: string;
  result?: SettlementResult;
} | null> {
  const client = await getTemporalClient();
  if (!client) return null;

  const workflowId = `settlement-${date}`;
  try {
    const handle = client.workflow.getHandle(workflowId);
    const desc = await handle.describe();
    return { status: desc.status.name };
  } catch {
    return null;
  }
}

export default {
  getTemporalClient,
  triggerSettlement,
  triggerWorkflow,
  scheduleSettlementCron,
  getSettlementStatus,
};
