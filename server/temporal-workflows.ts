// @ts-nocheck
/**
 * 54Link POS — Temporal Workflow Definitions
 * These run inside the Temporal sandbox (no direct I/O).
 * All I/O is delegated to activities.
 */
import {
  proxyActivities,
  defineSignal,
  defineQuery,
  setHandler,
  condition,
  sleep,
  log,
  workflowInfo,
} from "@temporalio/workflow";
import type * as activities from "./temporal-activities";

// ── Activity proxies ──────────────────────────────────────────────────────────
const {
  fetchUnsettledTransactions,
  groupTransactionsByAgent,
  calculateAgentSettlements,
  validateSettlementAmounts,
  executeSettlementTransfers,
  markTransactionsAsSettled,
  generateSettlementReport,
  notifyAgentsOfSettlement,
  archiveSettlementBatch,
} = proxyActivities<typeof activities>({
  startToCloseTimeout: "5 minutes",
  retry: {
    maximumAttempts: 3,
    initialInterval: "1s",
    backoffCoefficient: 2,
    maximumInterval: "30s",
  },
});

// ── Signals & Queries ─────────────────────────────────────────────────────────
export const pauseSettlementSignal =
  defineSignal<[{ reason: string }]>("pauseSettlement");
export const resumeSettlementSignal = defineSignal("resumeSettlement");
export const cancelSettlementSignal =
  defineSignal<[{ reason: string }]>("cancelSettlement");
export const getSettlementStatusQuery = defineQuery<SettlementStatus>(
  "getSettlementStatus"
);

export interface SettlementStatus {
  phase: string;
  agentsProcessed: number;
  totalAgents: number;
  totalAmountSettled: number;
  paused: boolean;
  cancelled: boolean;
  errors: string[];
}

// ── Settlement Workflow ───────────────────────────────────────────────────────
export interface SettlementWorkflowInput {
  settlementDate: string; // ISO date string e.g. "2026-04-09"
  batchId: string;
  currency: string;
  dryRun?: boolean;
}

export async function SettlementWorkflow(
  input: SettlementWorkflowInput
): Promise<{ success: boolean; batchId: string; report: string }> {
  const { workflowId } = workflowInfo();
  let paused = false;
  let cancelled = false;
  let cancelReason = "";
  const status: SettlementStatus = {
    phase: "initializing",
    agentsProcessed: 0,
    totalAgents: 0,
    totalAmountSettled: 0,
    paused: false,
    cancelled: false,
    errors: [],
  };

  // Register signal handlers
  setHandler(pauseSettlementSignal, ({ reason }) => {
    log.info("Settlement paused", { reason, workflowId });
    paused = true;
    status.paused = true;
    status.phase = "paused";
  });

  setHandler(resumeSettlementSignal, () => {
    log.info("Settlement resumed", { workflowId });
    paused = false;
    status.paused = false;
    status.phase = "resuming";
  });

  setHandler(cancelSettlementSignal, ({ reason }) => {
    log.warn("Settlement cancelled", { reason, workflowId });
    cancelled = true;
    cancelReason = reason;
    status.cancelled = true;
    status.phase = "cancelled";
  });

  setHandler(getSettlementStatusQuery, () => ({ ...status }));

  try {
    // Phase 1: Fetch unsettled transactions
    status.phase = "fetching_transactions";
    log.info("Fetching unsettled transactions", {
      date: input.settlementDate,
      batchId: input.batchId,
    });
    const transactions = await fetchUnsettledTransactions({
      date: input.settlementDate,
      currency: input.currency,
    });

    if (cancelled) {
      return {
        success: false,
        batchId: input.batchId,
        report: `Cancelled: ${cancelReason}`,
      };
    }

    // Phase 2: Group by agent
    status.phase = "grouping_by_agent";
    const agentGroups = await groupTransactionsByAgent(transactions);
    status.totalAgents = agentGroups.length;

    // Phase 3: Calculate settlements
    status.phase = "calculating_settlements";
    const settlements = await calculateAgentSettlements(agentGroups);

    // Phase 4: Validate amounts
    status.phase = "validating_amounts";
    const validationResult = await validateSettlementAmounts(settlements);
    if (!validationResult.valid) {
      status.errors.push(...validationResult.errors);
      throw new Error(
        `Settlement validation failed: ${validationResult.errors.join(", ")}`
      );
    }

    if (input.dryRun) {
      log.info("Dry run complete — no transfers executed", { workflowId });
      const report = await generateSettlementReport({
        batchId: input.batchId,
        settlements,
        dryRun: true,
      });
      return { success: true, batchId: input.batchId, report };
    }

    // Phase 5: Execute transfers (with pause support)
    status.phase = "executing_transfers";
    for (let i = 0; i < settlements.length; i++) {
      // Wait if paused
      if (paused) {
        await condition(() => !paused, "1 hour");
      }
      if (cancelled) {
        break;
      }

      await executeSettlementTransfers([settlements[i]]);
      status.agentsProcessed = i + 1;
      status.totalAmountSettled += settlements[i].amount;
    }

    if (cancelled) {
      return {
        success: false,
        batchId: input.batchId,
        report: `Cancelled after ${status.agentsProcessed} agents`,
      };
    }

    // Phase 6: Mark transactions as settled
    status.phase = "marking_settled";
    await markTransactionsAsSettled({
      batchId: input.batchId,
      transactionIds: transactions.map((t: any) => t.id),
    });

    // Phase 7: Generate report
    status.phase = "generating_report";
    const report = await generateSettlementReport({
      batchId: input.batchId,
      settlements,
      dryRun: false,
    });

    // Phase 8: Notify agents
    status.phase = "notifying_agents";
    await notifyAgentsOfSettlement({
      settlements,
      reportUrl: `https://app.54link.ng/settlements/${input.batchId}`,
    });

    // Phase 9: Archive
    status.phase = "archiving";
    await archiveSettlementBatch({
      batchId: input.batchId,
      report,
      date: input.settlementDate,
    });

    status.phase = "completed";
    log.info("Settlement workflow completed", {
      workflowId,
      batchId: input.batchId,
      agentsSettled: status.agentsProcessed,
      totalAmount: status.totalAmountSettled,
    });

    return { success: true, batchId: input.batchId, report };
  } catch (err: any) {
    status.phase = "failed";
    status.errors.push(err.message);
    log.error("Settlement workflow failed", { workflowId, error: err.message });
    throw err;
  }
}

// ── Float Replenishment Workflow ──────────────────────────────────────────────
export interface FloatReplenishmentInput {
  agentId: number;
  requestedAmount: number;
  currency: string;
  requestId: string;
}

const {
  checkAgentFloatBalance,
  approveFloatReplenishment,
  executeFloatTransfer,
  notifyAgentOfFloat,
} = proxyActivities<typeof activities>({
  startToCloseTimeout: "2 minutes",
  retry: { maximumAttempts: 3 },
});

export async function FloatReplenishmentWorkflow(
  input: FloatReplenishmentInput
): Promise<{ approved: boolean; transferRef: string }> {
  const balance = await checkAgentFloatBalance(input.agentId);

  if (balance.pendingRequests > 0) {
    log.warn("Agent has pending float requests", {
      agentId: input.agentId,
      pending: balance.pendingRequests,
    });
  }

  // Auto-approve if below 20% threshold
  const autoApprove = balance.currentBalance < balance.minBalance * 0.2;
  const approved = autoApprove
    ? true
    : await approveFloatReplenishment({
        agentId: input.agentId,
        requestId: input.requestId,
        amount: input.requestedAmount,
        currentBalance: balance.currentBalance,
      });

  if (!approved) {
    return { approved: false, transferRef: "" };
  }

  const transferRef = await executeFloatTransfer({
    agentId: input.agentId,
    amount: input.requestedAmount,
    currency: input.currency,
    requestId: input.requestId,
  });

  await notifyAgentOfFloat({
    agentId: input.agentId,
    amount: input.requestedAmount,
    currency: input.currency,
    transferRef,
  });

  return { approved: true, transferRef };
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sprint 82: Billing Provisioning Workflow
// 7-step workflow with rollback on failure
// ═══════════════════════════════════════════════════════════════════════════════

const billingActivities = proxyActivities<typeof activities>({
  startToCloseTimeout: "60s",
  retry: { maximumAttempts: 3, initialInterval: "2s", backoffCoefficient: 2 },
});

export interface BillingProvisioningInput {
  tenantId: number;
  tenantName: string;
  billingModel: "revenue_share" | "subscription" | "hybrid";
  customConfig?: any;
  provisionedBy: number;
  region: string;
  currency: string;
}

export interface BillingProvisioningResult {
  success: boolean;
  tenantId: number;
  steps: Array<{ step: string; status: string; details?: any; error?: string }>;
  configId: number;
  rollbackPerformed: boolean;
  duration: string;
}

const cancelBillingProvisioningSignal = defineSignal(
  "cancelBillingProvisioning"
);
const billingProvisioningStepQuery = defineQuery<string>(
  "billingProvisioningStep"
);

/**
 * BillingProvisioningWorkflow — provisions billing infrastructure for a new tenant.
 * 7 sequential steps with full rollback on failure.
 */
export async function BillingProvisioningWorkflow(
  input: BillingProvisioningInput
): Promise<BillingProvisioningResult> {
  const startTime = Date.now();
  let cancelled = false;
  let currentStep = "initializing";
  const completedSteps: string[] = [];
  const stepResults: Array<{
    step: string;
    status: string;
    details?: any;
    error?: string;
  }> = [];

  setHandler(cancelBillingProvisioningSignal, () => {
    cancelled = true;
    log.info("Billing provisioning cancellation requested", {
      tenantId: input.tenantId,
    });
  });
  setHandler(billingProvisioningStepQuery, () => currentStep);

  const steps = [
    {
      name: "validate_tenant",
      fn: () =>
        billingActivities.validateTenantForBilling({
          tenantId: input.tenantId,
          tenantName: input.tenantName,
        }),
    },
    {
      name: "create_billing_config",
      fn: () =>
        billingActivities.createBillingConfig({
          tenantId: input.tenantId,
          billingModel: input.billingModel,
          customConfig: input.customConfig,
          provisionedBy: input.provisionedBy,
          currency: input.currency,
        }),
    },
    {
      name: "create_tigerbeetle_accounts",
      fn: () =>
        billingActivities.createTigerBeetleAccounts({
          tenantId: input.tenantId,
        }),
    },
    {
      name: "provision_kafka_topics",
      fn: () =>
        billingActivities.provisionKafkaTopics({ tenantId: input.tenantId }),
    },
    {
      name: "assign_billing_roles",
      fn: () =>
        billingActivities.assignBillingRoles({
          tenantId: input.tenantId,
          provisionedBy: input.provisionedBy,
        }),
    },
    {
      name: "configure_reconciliation",
      fn: () =>
        billingActivities.configureReconciliation({
          tenantId: input.tenantId,
          region: input.region,
        }),
    },
    {
      name: "activate_billing",
      fn: () =>
        billingActivities.activateBilling({
          tenantId: input.tenantId,
          provisionedBy: input.provisionedBy,
        }),
    },
  ];

  let configId = 0;

  for (const step of steps) {
    if (cancelled) {
      log.warn("Billing provisioning cancelled", {
        step: step.name,
        tenantId: input.tenantId,
      });
      break;
    }
    currentStep = step.name;
    log.info("Executing billing provisioning step", {
      step: step.name,
      tenantId: input.tenantId,
    });

    try {
      const result = await step.fn();
      completedSteps.push(step.name);
      stepResults.push({
        step: step.name,
        status: "completed",
        details: result,
      });
      if (step.name === "create_billing_config" && result?.configId) {
        configId = result.configId;
      }
    } catch (error) {
      const errMsg = (error as Error).message || "Unknown error";
      stepResults.push({ step: step.name, status: "failed", error: errMsg });
      log.error("Billing step failed — initiating rollback", {
        step: step.name,
        error: errMsg,
        tenantId: input.tenantId,
      });

      // Rollback in reverse order
      for (let i = completedSteps.length - 1; i >= 0; i--) {
        currentStep = `rollback_${completedSteps[i]}`;
        log.info("Rolling back billing step", {
          step: completedSteps[i],
          tenantId: input.tenantId,
        });
        try {
          await billingActivities.rollbackBillingStep({
            tenantId: input.tenantId,
            step: completedSteps[i],
          });
        } catch (rbErr) {
          log.error("Rollback failed (manual intervention required)", {
            step: completedSteps[i],
            error: (rbErr as Error).message,
          });
        }
      }

      return {
        success: false,
        tenantId: input.tenantId,
        steps: stepResults,
        configId,
        rollbackPerformed: true,
        duration: `${Date.now() - startTime}ms`,
      };
    }
  }

  return {
    success: !cancelled,
    tenantId: input.tenantId,
    steps: stepResults,
    configId,
    rollbackPerformed: false,
    duration: `${Date.now() - startTime}ms`,
  };
}

// ── Dispute Resolution Workflow ─────────────────────────────────────────────
export interface DisputeWorkflowInput {
  disputeId: string;
  txRef: string;
  agentCode: string;
  amount: number;
  reason: string;
  evidence?: string[];
}

const disputeActivities = proxyActivities<{
  createDisputeRecord: (input: DisputeWorkflowInput) => Promise<{ id: string }>;
  notifyCounterparty: (disputeId: string) => Promise<void>;
  collectEvidence: (
    disputeId: string,
    txRef: string
  ) => Promise<{ evidence: any[] }>;
  assignInvestigator: (
    disputeId: string
  ) => Promise<{ investigatorId: string }>;
  makeDecision: (
    disputeId: string,
    evidence: any[]
  ) => Promise<{ decision: string; refundAmount: number }>;
  executeRefund: (
    disputeId: string,
    amount: number
  ) => Promise<{ refundRef: string }>;
  closeDispute: (disputeId: string, outcome: string) => Promise<void>;
}>({
  startToCloseTimeout: "10 minutes",
  retry: {
    maximumAttempts: 3,
    initialInterval: "2s",
    backoffCoefficient: 2,
    maximumInterval: "1m",
  },
});

export const getDisputeStatusQuery = defineQuery<{
  phase: string;
  decision?: string;
}>("getDisputeStatus");

export async function DisputeResolutionWorkflow(
  input: DisputeWorkflowInput
): Promise<{ success: boolean; outcome: string; refundRef?: string }> {
  let phase = "filing";
  let decision = "";
  setHandler(getDisputeStatusQuery, () => ({ phase, decision }));

  // Step 1: Create dispute record
  phase = "creating_record";
  const record = await disputeActivities.createDisputeRecord(input);

  // Step 2: Notify counterparty
  phase = "notifying_counterparty";
  await disputeActivities.notifyCounterparty(record.id);

  // Step 3: Collect evidence (auto-fetch from transaction logs)
  phase = "collecting_evidence";
  const { evidence } = await disputeActivities.collectEvidence(
    record.id,
    input.txRef
  );

  // Step 4: Wait for investigation (with timeout)
  phase = "investigating";
  const { investigatorId } = await disputeActivities.assignInvestigator(
    record.id
  );
  log.info("Investigator assigned", { disputeId: record.id, investigatorId });

  // Step 5: Make decision
  phase = "deciding";
  const result = await disputeActivities.makeDecision(record.id, evidence);
  decision = result.decision;

  // Step 6: Execute refund if decision is in favor
  let refundRef: string | undefined;
  if (result.decision === "refund" && result.refundAmount > 0) {
    phase = "refunding";
    const refund = await disputeActivities.executeRefund(
      record.id,
      result.refundAmount
    );
    refundRef = refund.refundRef;
  }

  // Step 7: Close dispute
  phase = "closing";
  await disputeActivities.closeDispute(record.id, result.decision);

  return { success: true, outcome: result.decision, refundRef };
}

// ── KYC Approval Workflow ───────────────────────────────────────────────────
export interface KYCWorkflowInput {
  agentCode: string;
  documentType: string;
  documentId: string;
  tier: number;
  submittedBy: string;
}

const kycActivities = proxyActivities<{
  validateDocument: (
    docId: string,
    docType: string
  ) => Promise<{ valid: boolean; confidence: number; issues?: string[] }>;
  runPEPCheck: (name: string) => Promise<{ result: string; risk: number }>;
  runSanctionsCheck: (
    name: string
  ) => Promise<{ result: string; risk: number }>;
  runLivenessCheck: (agentCode: string) => Promise<{ passed: boolean }>;
  assignReviewer: (
    docId: string,
    tier: number
  ) => Promise<{ reviewerId: string }>;
  awaitReviewDecision: (
    docId: string
  ) => Promise<{ approved: boolean; notes?: string }>;
  updateKYCTier: (agentCode: string, newTier: number) => Promise<void>;
  notifyAgent: (
    agentCode: string,
    status: string,
    notes?: string
  ) => Promise<void>;
}>({
  startToCloseTimeout: "30 minutes",
  retry: {
    maximumAttempts: 3,
    initialInterval: "5s",
    backoffCoefficient: 2,
    maximumInterval: "2m",
  },
});

export async function KYCApprovalWorkflow(
  input: KYCWorkflowInput
): Promise<{ approved: boolean; tier: number; notes?: string }> {
  log.info("KYC approval started", {
    agentCode: input.agentCode,
    tier: input.tier,
  });

  // Step 1: Document validation (OCR + authenticity)
  const docResult = await kycActivities.validateDocument(
    input.documentId,
    input.documentType
  );
  if (!docResult.valid) {
    await kycActivities.notifyAgent(
      input.agentCode,
      "document_rejected",
      docResult.issues?.join("; ")
    );
    return {
      approved: false,
      tier: input.tier,
      notes: "Document validation failed",
    };
  }

  // Step 2: PEP + Sanctions screening (parallel)
  const [pepResult, sanctionsResult] = await Promise.all([
    kycActivities.runPEPCheck(input.agentCode),
    kycActivities.runSanctionsCheck(input.agentCode),
  ]);
  if (sanctionsResult.result === "hit") {
    await kycActivities.notifyAgent(input.agentCode, "sanctions_block");
    return { approved: false, tier: input.tier, notes: "Sanctions list match" };
  }

  // Step 3: Liveness check (biometric) for tier 2+
  if (input.tier >= 2) {
    const liveness = await kycActivities.runLivenessCheck(input.agentCode);
    if (!liveness.passed) {
      await kycActivities.notifyAgent(input.agentCode, "liveness_failed");
      return {
        approved: false,
        tier: input.tier,
        notes: "Liveness check failed",
      };
    }
  }

  // Step 4: Manual review for tier 3+ or PEP hits
  if (input.tier >= 3 || pepResult.result === "hit") {
    const { reviewerId } = await kycActivities.assignReviewer(
      input.documentId,
      input.tier
    );
    log.info("Manual review assigned", { reviewerId, docId: input.documentId });
    const review = await kycActivities.awaitReviewDecision(input.documentId);
    if (!review.approved) {
      await kycActivities.notifyAgent(
        input.agentCode,
        "review_rejected",
        review.notes
      );
      return { approved: false, tier: input.tier, notes: review.notes };
    }
  }

  // Step 5: Upgrade tier
  await kycActivities.updateKYCTier(input.agentCode, input.tier);
  await kycActivities.notifyAgent(input.agentCode, "approved");

  return { approved: true, tier: input.tier };
}

// ── Agent Onboarding Workflow ───────────────────────────────────────────────
export interface OnboardingWorkflowInput {
  agentCode: string;
  agentName: string;
  businessType: string;
  region: string;
  supervisorCode: string;
}

const onboardingActivities = proxyActivities<{
  createAgentProfile: (
    input: OnboardingWorkflowInput
  ) => Promise<{ agentId: string }>;
  assignTerritory: (agentCode: string, region: string) => Promise<void>;
  provisionFloat: (
    agentCode: string,
    initialAmount: number
  ) => Promise<{ floatRef: string }>;
  assignTerminal: (agentCode: string) => Promise<{ terminalId: string }>;
  scheduleTraining: (agentCode: string) => Promise<{ trainingId: string }>;
  enableTransactions: (agentCode: string) => Promise<void>;
  sendWelcomeKit: (agentCode: string, agentName: string) => Promise<void>;
}>({
  startToCloseTimeout: "5 minutes",
  retry: {
    maximumAttempts: 3,
    initialInterval: "1s",
    backoffCoefficient: 2,
    maximumInterval: "30s",
  },
});

export async function AgentOnboardingWorkflow(
  input: OnboardingWorkflowInput
): Promise<{ success: boolean; agentId: string; terminalId?: string }> {
  log.info("Agent onboarding started", { agentCode: input.agentCode });

  // Step 1: Create profile
  const { agentId } = await onboardingActivities.createAgentProfile(input);

  // Step 2: Assign territory
  await onboardingActivities.assignTerritory(input.agentCode, input.region);

  // Step 3: Provision initial float
  await onboardingActivities.provisionFloat(input.agentCode, 50000);

  // Step 4: Assign POS terminal
  let terminalId: string | undefined;
  try {
    const terminal = await onboardingActivities.assignTerminal(input.agentCode);
    terminalId = terminal.terminalId;
  } catch {
    log.warn("No available terminals for assignment", {
      agentCode: input.agentCode,
    });
  }

  // Step 5: Schedule training
  await onboardingActivities.scheduleTraining(input.agentCode);

  // Step 6: Enable transactions
  await onboardingActivities.enableTransactions(input.agentCode);

  // Step 7: Send welcome kit
  await onboardingActivities.sendWelcomeKit(input.agentCode, input.agentName);

  return { success: true, agentId, terminalId };
}

// ── Commission Payout Workflow ──────────────────────────────────────────────
export interface CommissionWorkflowInput {
  period: string;
  agentCodes?: string[];
  currency: string;
}

const commissionActivities = proxyActivities<{
  calculateCommissions: (
    period: string,
    agentCodes?: string[]
  ) => Promise<Array<{ agentCode: string; amount: number; txCount: number }>>;
  validatePayouts: (
    payouts: Array<{ agentCode: string; amount: number }>
  ) => Promise<{ valid: boolean; issues?: string[] }>;
  executePayouts: (
    payouts: Array<{ agentCode: string; amount: number }>,
    currency: string
  ) => Promise<Array<{ agentCode: string; ref: string; status: string }>>;
  generateCommissionReport: (period: string, results: any[]) => Promise<string>;
  notifyAgentsOfPayout: (
    results: Array<{ agentCode: string; amount: number; ref: string }>
  ) => Promise<void>;
}>({
  startToCloseTimeout: "15 minutes",
  retry: {
    maximumAttempts: 3,
    initialInterval: "2s",
    backoffCoefficient: 2,
    maximumInterval: "1m",
  },
});

export async function CommissionPayoutWorkflow(
  input: CommissionWorkflowInput
): Promise<{ success: boolean; totalPaid: number; agentCount: number }> {
  log.info("Commission payout started", { period: input.period });

  // Step 1: Calculate commissions for period
  const commissions = await commissionActivities.calculateCommissions(
    input.period,
    input.agentCodes
  );
  if (commissions.length === 0) {
    return { success: true, totalPaid: 0, agentCount: 0 };
  }

  // Step 2: Validate payouts
  const validation = await commissionActivities.validatePayouts(commissions);
  if (!validation.valid) {
    log.error("Commission validation failed", { issues: validation.issues });
    return { success: false, totalPaid: 0, agentCount: 0 };
  }

  // Step 3: Execute payouts
  const results = await commissionActivities.executePayouts(
    commissions,
    input.currency
  );
  const successful = results.filter(r => r.status === "completed");

  // Step 4: Generate report
  await commissionActivities.generateCommissionReport(input.period, results);

  // Step 5: Notify agents
  const notifications = successful.map(r => ({
    agentCode: r.agentCode,
    amount: commissions.find(c => c.agentCode === r.agentCode)?.amount ?? 0,
    ref: r.ref,
  }));
  await commissionActivities.notifyAgentsOfPayout(notifications);

  const totalPaid = notifications.reduce((sum, n) => sum + n.amount, 0);
  return { success: true, totalPaid, agentCount: successful.length };
}
