/**
 * schema-stakeholder-tables.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Dedicated first-class tables for every stakeholder workflow that previously
 * relied on aliased/shared tables.  Each table is production-ready with:
 *   • Proper primary keys (UUID)
 *   • Tenant isolation (tenantId FK)
 *   • Audit columns (createdAt / updatedAt with $onUpdate)
 *   • Appropriate indexes
 *   • Exported TypeScript types ($inferSelect / $inferInsert)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import {
  pgTable,
  uuid,
  text,
  numeric,
  integer,
  boolean,
  timestamp,
  jsonb,
  pgEnum,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

// ─── Shared helpers ───────────────────────────────────────────────────────────
const now = () => sql`now()`;
const pkId = () => uuid("id").primaryKey().defaultRandom();
const tenantId = () => uuid("tenant_id").notNull();
const createdAt = () => timestamp("created_at").notNull().defaultNow();
const updatedAt = () =>
  timestamp("updated_at")
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date());

// ═══════════════════════════════════════════════════════════════════════════════
// 1. ROLES  (RBAC — platform-level roles)
// ═══════════════════════════════════════════════════════════════════════════════
export const roleTypeEnum = pgEnum("role_type", [
  "super_admin",
  "tenant_owner",
  "tenant_admin",
  "supervisor",
  "agent",
  "customer",
  "merchant",
  "developer",
  "regulator",
  "compliance_officer",
  "auditor",
  "support",
]);

export const roles = pgTable(
  "roles",
  {
    id: pkId(),
    tenantId: tenantId(),
    name: text("name").notNull(),
    type: roleTypeEnum("type").notNull(),
    description: text("description"),
    permissions: jsonb("permissions").notNull().default(sql`'[]'::jsonb`),
    isSystem: boolean("is_system").notNull().default(false),
    isActive: boolean("is_active").notNull().default(true),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("roles_tenant_idx").on(t.tenantId),
    nameIdx: uniqueIndex("roles_tenant_name_uidx").on(t.tenantId, t.name),
  })
);

export type Role = typeof roles.$inferSelect;
export type NewRole = typeof roles.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 2. AGENT FLOAT ACCOUNTS  (dedicated ledger per agent)
// ═══════════════════════════════════════════════════════════════════════════════
export const floatAccountStatusEnum = pgEnum("float_account_status", [
  "active",
  "suspended",
  "closed",
  "overdrawn",
]);

export const agentFloatAccounts = pgTable(
  "agent_float_accounts",
  {
    id: pkId(),
    tenantId: tenantId(),
    agentId: uuid("agent_id").notNull(),
    currency: text("currency").notNull().default("NGN"),
    balance: numeric("balance", { precision: 20, scale: 4 }).notNull().default("0"),
    reservedBalance: numeric("reserved_balance", { precision: 20, scale: 4 }).notNull().default("0"),
    creditLimit: numeric("credit_limit", { precision: 20, scale: 4 }).notNull().default("0"),
    status: floatAccountStatusEnum("status").notNull().default("active"),
    tbAccountId: text("tb_account_id"),          // TigerBeetle account ID
    lastReconciledAt: timestamp("last_reconciled_at"),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("afa_tenant_idx").on(t.tenantId),
    agentIdx: index("afa_agent_idx").on(t.agentId),
    agentTenantUidx: uniqueIndex("afa_agent_tenant_currency_uidx").on(t.agentId, t.tenantId, t.currency),
  })
);

export type AgentFloatAccount = typeof agentFloatAccounts.$inferSelect;
export type NewAgentFloatAccount = typeof agentFloatAccounts.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 3. AGENT FLOAT INSURANCE CLAIMS
// ═══════════════════════════════════════════════════════════════════════════════
export const floatInsuranceClaimStatusEnum = pgEnum("float_insurance_claim_status", [
  "submitted",
  "under_review",
  "approved",
  "rejected",
  "paid",
]);

export const agentFloatInsuranceClaims = pgTable(
  "agent_float_insurance_claims",
  {
    id: pkId(),
    tenantId: tenantId(),
    agentId: uuid("agent_id").notNull(),
    floatAccountId: uuid("float_account_id").notNull(),
    claimAmount: numeric("claim_amount", { precision: 20, scale: 4 }).notNull(),
    approvedAmount: numeric("approved_amount", { precision: 20, scale: 4 }),
    status: floatInsuranceClaimStatusEnum("status").notNull().default("submitted"),
    incidentDate: timestamp("incident_date").notNull(),
    description: text("description").notNull(),
    evidenceUrls: jsonb("evidence_urls").default(sql`'[]'::jsonb`),
    reviewedBy: uuid("reviewed_by"),
    reviewNotes: text("review_notes"),
    paidAt: timestamp("paid_at"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("afic_tenant_idx").on(t.tenantId),
    agentIdx: index("afic_agent_idx").on(t.agentId),
    statusIdx: index("afic_status_idx").on(t.status),
  })
);

export type AgentFloatInsuranceClaim = typeof agentFloatInsuranceClaims.$inferSelect;
export type NewAgentFloatInsuranceClaim = typeof agentFloatInsuranceClaims.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 4. AGENT CLUSTERS  (supervisor groupings)
// ═══════════════════════════════════════════════════════════════════════════════
export const agentClusters = pgTable(
  "agent_clusters",
  {
    id: pkId(),
    tenantId: tenantId(),
    supervisorId: uuid("supervisor_id").notNull(),
    name: text("name").notNull(),
    description: text("description"),
    region: text("region"),
    state: text("state"),
    lga: text("lga"),
    targetTransactionVolume: numeric("target_tx_volume", { precision: 20, scale: 4 }),
    targetAgentCount: integer("target_agent_count"),
    isActive: boolean("is_active").notNull().default(true),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("ac_tenant_idx").on(t.tenantId),
    supervisorIdx: index("ac_supervisor_idx").on(t.supervisorId),
  })
);

export type AgentCluster = typeof agentClusters.$inferSelect;
export type NewAgentCluster = typeof agentClusters.$inferInsert;

export const agentClusterMembers = pgTable(
  "agent_cluster_members",
  {
    id: pkId(),
    clusterId: uuid("cluster_id").notNull(),
    agentId: uuid("agent_id").notNull(),
    joinedAt: createdAt(),
    isActive: boolean("is_active").notNull().default(true),
  },
  (t) => ({
    clusterIdx: index("acm_cluster_idx").on(t.clusterId),
    agentIdx: index("acm_agent_idx").on(t.agentId),
    uniqueMember: uniqueIndex("acm_unique_uidx").on(t.clusterId, t.agentId),
  })
);

// ═══════════════════════════════════════════════════════════════════════════════
// 5. AGENT GAMIFICATION  (points, levels, streaks)
// ═══════════════════════════════════════════════════════════════════════════════
export const agentGamification = pgTable(
  "agent_gamification",
  {
    id: pkId(),
    tenantId: tenantId(),
    agentId: uuid("agent_id").notNull(),
    totalPoints: integer("total_points").notNull().default(0),
    level: integer("level").notNull().default(1),
    levelName: text("level_name").notNull().default("Bronze"),
    currentStreak: integer("current_streak").notNull().default(0),
    longestStreak: integer("longest_streak").notNull().default(0),
    lastActivityDate: timestamp("last_activity_date"),
    monthlyPoints: integer("monthly_points").notNull().default(0),
    weeklyPoints: integer("weekly_points").notNull().default(0),
    leaderboardRank: integer("leaderboard_rank"),
    badges: jsonb("badges").notNull().default(sql`'[]'::jsonb`),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("ag_tenant_idx").on(t.tenantId),
    agentUidx: uniqueIndex("ag_agent_tenant_uidx").on(t.agentId, t.tenantId),
    pointsIdx: index("ag_points_idx").on(t.totalPoints),
  })
);

export type AgentGamificationRecord = typeof agentGamification.$inferSelect;
export type NewAgentGamificationRecord = typeof agentGamification.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 6. AGENT HIERARCHY  (multi-level agent tree)
// ═══════════════════════════════════════════════════════════════════════════════
export const agentHierarchy = pgTable(
  "agent_hierarchy",
  {
    id: pkId(),
    tenantId: tenantId(),
    agentId: uuid("agent_id").notNull(),
    parentAgentId: uuid("parent_agent_id"),
    supervisorId: uuid("supervisor_id"),
    clusterId: uuid("cluster_id"),
    depth: integer("depth").notNull().default(0),
    path: text("path").notNull().default(""),   // materialized path e.g. "root/uuid1/uuid2"
    isActive: boolean("is_active").notNull().default(true),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("ah_tenant_idx").on(t.tenantId),
    agentUidx: uniqueIndex("ah_agent_tenant_uidx").on(t.agentId, t.tenantId),
    parentIdx: index("ah_parent_idx").on(t.parentAgentId),
    supervisorIdx: index("ah_supervisor_idx").on(t.supervisorId),
  })
);

export type AgentHierarchyRecord = typeof agentHierarchy.$inferSelect;
export type NewAgentHierarchyRecord = typeof agentHierarchy.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 7. TIGERBEETLE ACCOUNTS  (TB ledger account mapping)
// ═══════════════════════════════════════════════════════════════════════════════
export const tbAccountTypeEnum = pgEnum("tb_account_type", [
  "agent_float",
  "customer_wallet",
  "merchant_settlement",
  "fee_collection",
  "suspense",
  "nostro",
  "vostro",
]);

export const tbAccounts = pgTable(
  "tb_accounts",
  {
    id: pkId(),
    tenantId: tenantId(),
    tbAccountId: text("tb_account_id").notNull(),   // TigerBeetle uint128 as hex string
    ledger: integer("ledger").notNull(),             // TB ledger (currency code)
    code: integer("code").notNull(),                 // TB account code
    accountType: tbAccountTypeEnum("account_type").notNull(),
    ownerId: uuid("owner_id").notNull(),             // agent/customer/merchant UUID
    ownerType: text("owner_type").notNull(),         // "agent" | "customer" | "merchant"
    currency: text("currency").notNull().default("NGN"),
    creditsPending: numeric("credits_pending", { precision: 20, scale: 4 }).notNull().default("0"),
    creditsPosted: numeric("credits_posted", { precision: 20, scale: 4 }).notNull().default("0"),
    debitsPending: numeric("debits_pending", { precision: 20, scale: 4 }).notNull().default("0"),
    debitsPosted: numeric("debits_posted", { precision: 20, scale: 4 }).notNull().default("0"),
    flags: integer("flags").notNull().default(0),
    isActive: boolean("is_active").notNull().default(true),
    lastSyncedAt: timestamp("last_synced_at"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("tba_tenant_idx").on(t.tenantId),
    tbIdUidx: uniqueIndex("tba_tb_id_uidx").on(t.tbAccountId),
    ownerIdx: index("tba_owner_idx").on(t.ownerId, t.ownerType),
  })
);

export type TbAccount = typeof tbAccounts.$inferSelect;
export type NewTbAccount = typeof tbAccounts.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 8. BNPL TRANSACTIONS  (Buy-Now-Pay-Later dedicated table)
// ═══════════════════════════════════════════════════════════════════════════════
export const bnplStatusEnum = pgEnum("bnpl_status", [
  "initiated",
  "approved",
  "active",
  "partially_repaid",
  "fully_repaid",
  "overdue",
  "defaulted",
  "cancelled",
]);

export const bnplTransactions = pgTable(
  "bnpl_transactions",
  {
    id: pkId(),
    tenantId: tenantId(),
    customerId: uuid("customer_id").notNull(),
    merchantId: uuid("merchant_id").notNull(),
    originalTransactionId: uuid("original_transaction_id"),
    principalAmount: numeric("principal_amount", { precision: 20, scale: 4 }).notNull(),
    totalRepayableAmount: numeric("total_repayable_amount", { precision: 20, scale: 4 }).notNull(),
    outstandingBalance: numeric("outstanding_balance", { precision: 20, scale: 4 }).notNull(),
    interestRate: numeric("interest_rate", { precision: 8, scale: 4 }).notNull().default("0"),
    tenorDays: integer("tenor_days").notNull(),
    installmentCount: integer("installment_count").notNull().default(1),
    installmentAmount: numeric("installment_amount", { precision: 20, scale: 4 }).notNull(),
    status: bnplStatusEnum("status").notNull().default("initiated"),
    approvedAt: timestamp("approved_at"),
    firstInstallmentDueDate: timestamp("first_installment_due_date"),
    lastInstallmentDueDate: timestamp("last_installment_due_date"),
    defaultedAt: timestamp("defaulted_at"),
    tbDebitAccountId: text("tb_debit_account_id"),
    tbCreditAccountId: text("tb_credit_account_id"),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("bnpl_tenant_idx").on(t.tenantId),
    customerIdx: index("bnpl_customer_idx").on(t.customerId),
    merchantIdx: index("bnpl_merchant_idx").on(t.merchantId),
    statusIdx: index("bnpl_status_idx").on(t.status),
  })
);

export type BnplTransaction = typeof bnplTransactions.$inferSelect;
export type NewBnplTransaction = typeof bnplTransactions.$inferInsert;

export const bnplRepayments = pgTable(
  "bnpl_repayments",
  {
    id: pkId(),
    bnplTransactionId: uuid("bnpl_transaction_id").notNull(),
    installmentNumber: integer("installment_number").notNull(),
    dueDate: timestamp("due_date").notNull(),
    dueAmount: numeric("due_amount", { precision: 20, scale: 4 }).notNull(),
    paidAmount: numeric("paid_amount", { precision: 20, scale: 4 }).notNull().default("0"),
    paidAt: timestamp("paid_at"),
    isPaid: boolean("is_paid").notNull().default(false),
    penaltyAmount: numeric("penalty_amount", { precision: 20, scale: 4 }).notNull().default("0"),
    transactionRef: text("transaction_ref"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    bnplIdx: index("bnplr_bnpl_idx").on(t.bnplTransactionId),
    dueDateIdx: index("bnplr_due_date_idx").on(t.dueDate),
  })
);

// ═══════════════════════════════════════════════════════════════════════════════
// 9. LOAN APPLICATIONS  (customer & agent loan applications)
// ═══════════════════════════════════════════════════════════════════════════════
export const loanApplicationStatusEnum = pgEnum("loan_application_status", [
  "draft",
  "submitted",
  "under_review",
  "credit_check",
  "approved",
  "rejected",
  "disbursed",
  "cancelled",
]);

export const loanApplications = pgTable(
  "loan_applications",
  {
    id: pkId(),
    tenantId: tenantId(),
    applicantId: uuid("applicant_id").notNull(),
    applicantType: text("applicant_type").notNull().default("customer"), // customer | agent
    requestedAmount: numeric("requested_amount", { precision: 20, scale: 4 }).notNull(),
    approvedAmount: numeric("approved_amount", { precision: 20, scale: 4 }),
    currency: text("currency").notNull().default("NGN"),
    purpose: text("purpose").notNull(),
    tenorMonths: integer("tenor_months").notNull(),
    interestRate: numeric("interest_rate", { precision: 8, scale: 4 }),
    status: loanApplicationStatusEnum("status").notNull().default("draft"),
    creditScore: integer("credit_score"),
    creditScoreSource: text("credit_score_source"),
    collateralDescription: text("collateral_description"),
    collateralValue: numeric("collateral_value", { precision: 20, scale: 4 }),
    reviewedBy: uuid("reviewed_by"),
    reviewNotes: text("review_notes"),
    rejectionReason: text("rejection_reason"),
    submittedAt: timestamp("submitted_at"),
    approvedAt: timestamp("approved_at"),
    disbursedAt: timestamp("disbursed_at"),
    disbursementTransactionId: uuid("disbursement_transaction_id"),
    documents: jsonb("documents").default(sql`'[]'::jsonb`),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("la_tenant_idx").on(t.tenantId),
    applicantIdx: index("la_applicant_idx").on(t.applicantId),
    statusIdx: index("la_status_idx").on(t.status),
  })
);

export type LoanApplication = typeof loanApplications.$inferSelect;
export type NewLoanApplication = typeof loanApplications.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 10. SETTLEMENTS  (dedicated settlement table)
// ═══════════════════════════════════════════════════════════════════════════════
export const settlementStatusEnum = pgEnum("settlement_status", [
  "pending",
  "processing",
  "completed",
  "failed",
  "reversed",
]);

export const settlements = pgTable(
  "settlements",
  {
    id: pkId(),
    tenantId: tenantId(),
    batchId: text("batch_id").notNull(),
    settlementType: text("settlement_type").notNull(), // agent | merchant | partner
    recipientId: uuid("recipient_id").notNull(),
    recipientType: text("recipient_type").notNull(),
    grossAmount: numeric("gross_amount", { precision: 20, scale: 4 }).notNull(),
    feeAmount: numeric("fee_amount", { precision: 20, scale: 4 }).notNull().default("0"),
    taxAmount: numeric("tax_amount", { precision: 20, scale: 4 }).notNull().default("0"),
    netAmount: numeric("net_amount", { precision: 20, scale: 4 }).notNull(),
    currency: text("currency").notNull().default("NGN"),
    status: settlementStatusEnum("status").notNull().default("pending"),
    bankAccountNumber: text("bank_account_number"),
    bankCode: text("bank_code"),
    bankName: text("bank_name"),
    paymentReference: text("payment_reference"),
    settlementDate: timestamp("settlement_date"),
    processedAt: timestamp("processed_at"),
    failureReason: text("failure_reason"),
    tbTransferId: text("tb_transfer_id"),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("s_tenant_idx").on(t.tenantId),
    batchIdx: index("s_batch_idx").on(t.batchId),
    recipientIdx: index("s_recipient_idx").on(t.recipientId),
    statusIdx: index("s_status_idx").on(t.status),
    dateIdx: index("s_date_idx").on(t.settlementDate),
  })
);

export type Settlement = typeof settlements.$inferSelect;
export type NewSettlement = typeof settlements.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 11. AML SCREENING RESULTS  (dedicated AML results table)
// ═══════════════════════════════════════════════════════════════════════════════
export const amlRiskLevelEnum = pgEnum("aml_risk_level", [
  "low",
  "medium",
  "high",
  "critical",
]);

export const amlScreeningResults = pgTable(
  "aml_screening_results",
  {
    id: pkId(),
    tenantId: tenantId(),
    screeningId: uuid("screening_id").notNull(),  // FK to amlScreenings
    entityId: uuid("entity_id").notNull(),
    entityType: text("entity_type").notNull(),    // customer | agent | merchant | transaction
    riskLevel: amlRiskLevelEnum("risk_level").notNull(),
    riskScore: numeric("risk_score", { precision: 5, scale: 2 }).notNull(),
    matchedWatchlists: jsonb("matched_watchlists").default(sql`'[]'::jsonb`),
    matchedPatterns: jsonb("matched_patterns").default(sql`'[]'::jsonb`),
    sanctionsHit: boolean("sanctions_hit").notNull().default(false),
    pepHit: boolean("pep_hit").notNull().default(false),
    adverseMediaHit: boolean("adverse_media_hit").notNull().default(false),
    requiresManualReview: boolean("requires_manual_review").notNull().default(false),
    reviewedBy: uuid("reviewed_by"),
    reviewDecision: text("review_decision"),   // cleared | escalated | blocked
    reviewNotes: text("review_notes"),
    reviewedAt: timestamp("reviewed_at"),
    rawResponse: jsonb("raw_response").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("asr_tenant_idx").on(t.tenantId),
    entityIdx: index("asr_entity_idx").on(t.entityId, t.entityType),
    riskIdx: index("asr_risk_idx").on(t.riskLevel),
    sanctionsIdx: index("asr_sanctions_idx").on(t.sanctionsHit),
  })
);

export type AmlScreeningResult = typeof amlScreeningResults.$inferSelect;
export type NewAmlScreeningResult = typeof amlScreeningResults.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 12. COMMISSION STRUCTURES  (top-level commission configuration)
// ═══════════════════════════════════════════════════════════════════════════════
export const commissionStructures = pgTable(
  "commission_structures",
  {
    id: pkId(),
    tenantId: tenantId(),
    name: text("name").notNull(),
    description: text("description"),
    transactionType: text("transaction_type").notNull(),
    agentShare: numeric("agent_share", { precision: 8, scale: 4 }).notNull(),
    supervisorShare: numeric("supervisor_share", { precision: 8, scale: 4 }).notNull().default("0"),
    tenantShare: numeric("tenant_share", { precision: 8, scale: 4 }).notNull().default("0"),
    platformShare: numeric("platform_share", { precision: 8, scale: 4 }).notNull().default("0"),
    minTransactionAmount: numeric("min_transaction_amount", { precision: 20, scale: 4 }),
    maxTransactionAmount: numeric("max_transaction_amount", { precision: 20, scale: 4 }),
    effectiveFrom: timestamp("effective_from").notNull().defaultNow(),
    effectiveTo: timestamp("effective_to"),
    isActive: boolean("is_active").notNull().default(true),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("cs_tenant_idx").on(t.tenantId),
    txTypeIdx: index("cs_tx_type_idx").on(t.transactionType),
    activeIdx: index("cs_active_idx").on(t.isActive),
  })
);

export type CommissionStructure = typeof commissionStructures.$inferSelect;
export type NewCommissionStructure = typeof commissionStructures.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 13. USER NOTIFICATION PREFERENCES
// ═══════════════════════════════════════════════════════════════════════════════
export const userNotifPreferences = pgTable(
  "user_notif_preferences",
  {
    id: pkId(),
    tenantId: tenantId(),
    userId: uuid("user_id").notNull(),
    emailEnabled: boolean("email_enabled").notNull().default(true),
    smsEnabled: boolean("sms_enabled").notNull().default(true),
    pushEnabled: boolean("push_enabled").notNull().default(true),
    inAppEnabled: boolean("in_app_enabled").notNull().default(true),
    whatsappEnabled: boolean("whatsapp_enabled").notNull().default(false),
    transactionAlerts: boolean("transaction_alerts").notNull().default(true),
    securityAlerts: boolean("security_alerts").notNull().default(true),
    marketingMessages: boolean("marketing_messages").notNull().default(false),
    reportDigests: boolean("report_digests").notNull().default(true),
    quietHoursStart: text("quiet_hours_start"),   // "22:00"
    quietHoursEnd: text("quiet_hours_end"),        // "07:00"
    timezone: text("timezone").notNull().default("Africa/Lagos"),
    language: text("language").notNull().default("en"),
    customPreferences: jsonb("custom_preferences").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("unp_tenant_idx").on(t.tenantId),
    userUidx: uniqueIndex("unp_user_tenant_uidx").on(t.userId, t.tenantId),
  })
);

export type UserNotifPreference = typeof userNotifPreferences.$inferSelect;
export type NewUserNotifPreference = typeof userNotifPreferences.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 14. NOTIFICATION INBOX  (per-user in-app inbox)
// ═══════════════════════════════════════════════════════════════════════════════
export const notifInboxStatusEnum = pgEnum("notif_inbox_status", [
  "unread",
  "read",
  "archived",
  "deleted",
]);

export const notificationInbox = pgTable(
  "notification_inbox",
  {
    id: pkId(),
    tenantId: tenantId(),
    userId: uuid("user_id").notNull(),
    title: text("title").notNull(),
    body: text("body").notNull(),
    category: text("category").notNull().default("general"),
    actionUrl: text("action_url"),
    iconUrl: text("icon_url"),
    status: notifInboxStatusEnum("status").notNull().default("unread"),
    readAt: timestamp("read_at"),
    archivedAt: timestamp("archived_at"),
    expiresAt: timestamp("expires_at"),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("ni_tenant_idx").on(t.tenantId),
    userIdx: index("ni_user_idx").on(t.userId),
    statusIdx: index("ni_status_idx").on(t.status),
    userStatusIdx: index("ni_user_status_idx").on(t.userId, t.status),
  })
);

export type NotificationInboxItem = typeof notificationInbox.$inferSelect;
export type NewNotificationInboxItem = typeof notificationInbox.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 15. SYSTEM SETTINGS  (platform-wide configuration key-value store)
// ═══════════════════════════════════════════════════════════════════════════════
export const systemSettings = pgTable(
  "system_settings",
  {
    id: pkId(),
    key: text("key").notNull(),
    value: jsonb("value").notNull(),
    description: text("description"),
    isSecret: boolean("is_secret").notNull().default(false),
    isEditable: boolean("is_editable").notNull().default(true),
    category: text("category").notNull().default("general"),
    lastModifiedBy: uuid("last_modified_by"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    keyUidx: uniqueIndex("ss_key_uidx").on(t.key),
    categoryIdx: index("ss_category_idx").on(t.category),
  })
);

export type SystemSetting = typeof systemSettings.$inferSelect;
export type NewSystemSetting = typeof systemSettings.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 16. TENANT SETTINGS  (per-tenant configuration)
// ═══════════════════════════════════════════════════════════════════════════════
export const tenantSettings = pgTable(
  "tenant_settings",
  {
    id: pkId(),
    tenantId: tenantId(),
    key: text("key").notNull(),
    value: jsonb("value").notNull(),
    description: text("description"),
    isSecret: boolean("is_secret").notNull().default(false),
    category: text("category").notNull().default("general"),
    lastModifiedBy: uuid("last_modified_by"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => ({
    tenantIdx: index("ts_tenant_idx").on(t.tenantId),
    keyUidx: uniqueIndex("ts_tenant_key_uidx").on(t.tenantId, t.key),
  })
);

export type TenantSetting = typeof tenantSettings.$inferSelect;
export type NewTenantSetting = typeof tenantSettings.$inferInsert;

// ═══════════════════════════════════════════════════════════════════════════════
// 17. AUDIT LOGS  (canonical audit log with full context)
// ═══════════════════════════════════════════════════════════════════════════════
export const auditLogs = pgTable(
  "audit_logs",
  {
    id: pkId(),
    tenantId: tenantId(),
    actorId: uuid("actor_id"),
    actorType: text("actor_type"),   // user | agent | system | api_key
    action: text("action").notNull(),
    resource: text("resource").notNull(),
    resourceId: text("resource_id"),
    outcome: text("outcome").notNull().default("success"),  // success | failure | partial
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    requestId: text("request_id"),
    sessionId: text("session_id"),
    before: jsonb("before"),
    after: jsonb("after"),
    diff: jsonb("diff"),
    metadata: jsonb("metadata").default(sql`'{}'::jsonb`),
    createdAt: createdAt(),
  },
  (t) => ({
    tenantIdx: index("al_tenant_idx").on(t.tenantId),
    actorIdx: index("al_actor_idx").on(t.actorId),
    resourceIdx: index("al_resource_idx").on(t.resource, t.resourceId),
    actionIdx: index("al_action_idx").on(t.action),
    createdAtIdx: index("al_created_at_idx").on(t.createdAt),
  })
);

export type AuditLog = typeof auditLogs.$inferSelect;
export type NewAuditLog = typeof auditLogs.$inferInsert;
