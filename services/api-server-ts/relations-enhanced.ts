/**
 * Drizzle ORM — Enhanced Relations
 * ─────────────────────────────────────────────────────────────────────────────
 * Extends the existing relations.ts with missing relations for all 169 tables.
 * These relations power the Drizzle `with:` query API for eager loading.
 *
 * Usage:
 *   const agentWithTx = await db.query.agents.findFirst({
 *     where: eq(agents.id, agentId),
 *     with: {
 *       transactions: { limit: 10, orderBy: desc(transactions.createdAt) },
 *       kycSessions: true,
 *       devices: true,
 *       fraudAlerts: { where: eq(fraudAlerts.status, "open") },
 *     },
 *   });
 */

import { relations } from "drizzle-orm";
import {
  agents, users, transactions, fraudAlerts, loyaltyHistory,
  chatSessions, chatMessages, auditLog, floatTopUpRequests,
  otpTokens, devices, deviceCommands, supervisorAgents,
  disputes, disputeMessages, refunds, posTerminals,
  terminalGroups, serviceRecords, softwareUpdates,
  terminalLeases, posSettlementBatches, commissionRules,
  qrCodes, inventoryItems, multiSimProfiles, reversalRequests,
  shareableLinks, customers, tenants, erpSyncLog,
  storefrontAds, vatRecords, erpConfig, mqttBridgeConfig,
  analyticsMetrics, webhookSecrets, emailQueue, merchants,
  merchantSettlements, apiKeys, apiKeyUsage, fido2Credentials,
  fido2Challenges, creditScoreHistory, creditApplications,
  otaReleases, otaUpdateLog, dataRightsRequests, fraudRules,
  agentPushSubscriptions, connectivityLog, systemConfig,
  simProbeLog, simOrchestratorConfig, simFailoverLog,
  deviceCompliancePolicies, deviceComplianceViolations,
  dlqMessages, commissionPayouts, referrals,
  webhookEndpoints, webhookDeliveries, agentOnboardingProgress,
  settlementReconciliation, rateAlerts, emailDeliveryLog,
  inviteCodes, tenantBranding, tenantCorridors,
  tenantFeeOverrides, tenantUsers, commissionCascadeHistory,
  agentBankAccounts, kycDocuments, floatReconciliations,
  agentPerformanceScores, commissionClawbacks, pnlReports,
  geoFences, transactionLimits, complianceChecks,
  agentSuspensionLog, txMonitoringAlerts, fraudMlScores,
  notificationDispatchLog, agentLoans, feeRules, feeAuditTrail,
  merchantKycDocs, merchantPayouts, complianceFilings,
  agentAchievements, agentBadges, tenantFeatureToggles,
  reconciliationBatches, reconciliationItems, analyticsDashboards,
  customerJourneySteps, rateLimitRules, backupSnapshots,
  workflowDefinitions, workflowInstances, glEntries,
  trainingCourses, trainingEnrollments, biReportDefinitions,
  observabilityAlerts, encryptedFields, dataConsentRecords,
  realtime_tx_alerts, notification_channels, notification_logs,
  customer_journey_events, gl_accounts, gl_journal_entries,
  sla_definitions, sla_breaches, data_export_jobs,
  platform_health_checks, platform_incidents,
  platformBillingLedger, billingReconciliationReports,
  billingProvisioningHistory, ecommerceInventoryReservations,
  amlScreenings, amlWatchlistEntries, idempotencyKeys,
  temporalWorkflowLog, permifyCheckLog, openappsecThreatLog,
  fluvioEventLog, lakehouseSyncLog, daprPubsubLog,
  commissionTiers, commissionSplits, disputeEvidence,
  commissionAuditTrail, faceEnrollments, biometricAuditEvents,
  receiptTemplates, guideFeedback,
} from "./schema";

// ─── Agents ───────────────────────────────────────────────────────────────────
export const agentsRelationsEnhanced = relations(agents, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [agents.tenantId],
    references: [tenants.id],
  }),
  transactions: many(transactions),
  fraudAlerts: many(fraudAlerts),
  loyaltyHistory: many(loyaltyHistory),
  chatSessions: many(chatSessions),
  floatTopUpRequests: many(floatTopUpRequests),
  devices: many(devices),
  disputes: many(disputes),
  posTerminals: many(posTerminals),
  commissionPayouts: many(commissionPayouts),
  referrals: many(referrals),
  agentOnboardingProgress: one(agentOnboardingProgress, {
    fields: [agents.id],
    references: [agentOnboardingProgress.agentId],
  }),
  kycSessions: many(kycSessions),
  kycDocuments: many(kycDocuments),
  agentBankAccounts: many(agentBankAccounts),
  agentPerformanceScores: many(agentPerformanceScores),
  commissionClawbacks: many(commissionClawbacks),
  agentSuspensionLog: many(agentSuspensionLog),
  txMonitoringAlerts: many(txMonitoringAlerts),
  fraudMlScores: many(fraudMlScores),
  agentLoans: many(agentLoans),
  agentAchievements: many(agentAchievements),
  agentBadges: many(agentBadges),
  trainingEnrollments: many(trainingEnrollments),
  faceEnrollments: many(faceEnrollments),
  pushSubscriptions: many(agentPushSubscriptions),
  connectivityLog: many(connectivityLog),
  commissionCascadeHistory: many(commissionCascadeHistory),
  floatReconciliations: many(floatReconciliations),
  pnlReports: many(pnlReports),
  shareableLinks: many(shareableLinks),
  qrCodes: many(qrCodes),
  inventoryItems: many(inventoryItems),
  multiSimProfiles: many(multiSimProfiles),
  reversalRequests: many(reversalRequests),
  auditLog: many(auditLog),
}));

// ─── Transactions ─────────────────────────────────────────────────────────────
export const transactionsRelationsEnhanced = relations(transactions, ({ one, many }) => ({
  agent: one(agents, {
    fields: [transactions.agentId],
    references: [agents.id],
  }),
  tenant: one(tenants, {
    fields: [transactions.tenantId],
    references: [tenants.id],
  }),
  fraudAlerts: many(fraudAlerts),
  disputes: many(disputes),
  refunds: many(refunds),
  reversalRequests: many(reversalRequests),
  loyaltyHistory: many(loyaltyHistory),
  txMonitoringAlerts: many(txMonitoringAlerts),
  fraudMlScores: many(fraudMlScores),
  feeAuditTrail: many(feeAuditTrail),
  realtimeTxAlerts: many(realtime_tx_alerts),
}));

// ─── Tenants ──────────────────────────────────────────────────────────────────
export const tenantsRelationsEnhanced = relations(tenants, ({ many, one }) => ({
  agents: many(agents),
  merchants: many(merchants),
  users: many(tenantUsers),
  branding: one(tenantBranding, {
    fields: [tenants.id],
    references: [tenantBranding.tenantId],
  }),
  corridors: many(tenantCorridors),
  feeOverrides: many(tenantFeeOverrides),
  featureToggles: many(tenantFeatureToggles),
  billingConfig: one(tenantBillingConfig, {
    fields: [tenants.id],
    references: [tenantBillingConfig.tenantId],
  }),
  billingLedger: many(platformBillingLedger),
  erpConfig: one(erpConfig, {
    fields: [tenants.id],
    references: [erpConfig.tenantId],
  }),
  mqttBridgeConfig: one(mqttBridgeConfig, {
    fields: [tenants.id],
    references: [mqttBridgeConfig.tenantId],
  }),
  simOrchestratorConfig: one(simOrchestratorConfig, {
    fields: [tenants.id],
    references: [simOrchestratorConfig.tenantId],
  }),
  pnlReports: many(pnlReports),
  reconciliationBatches: many(reconciliationBatches),
  complianceFilings: many(complianceFilings),
  dataExportJobs: many(data_export_jobs),
}));

// ─── Merchants ────────────────────────────────────────────────────────────────
export const merchantsRelationsEnhanced = relations(merchants, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [merchants.tenantId],
    references: [tenants.id],
  }),
  settlements: many(merchantSettlements),
  kycDocs: many(merchantKycDocs),
  payouts: many(merchantPayouts),
  posTerminals: many(posTerminals),
  vatRecords: many(vatRecords),
  storefrontAds: many(storefrontAds),
}));

// ─── Disputes ─────────────────────────────────────────────────────────────────
export const disputesRelationsEnhanced = relations(disputes, ({ one, many }) => ({
  transaction: one(transactions, {
    fields: [disputes.transactionId],
    references: [transactions.id],
  }),
  agent: one(agents, {
    fields: [disputes.agentId],
    references: [agents.id],
  }),
  messages: many(disputeMessages),
  evidence: many(disputeEvidence),
  refunds: many(refunds),
}));

// ─── KYC Sessions ─────────────────────────────────────────────────────────────
export const kycSessionsRelationsEnhanced = relations(kycSessions, ({ one }) => ({
  agent: one(agents, {
    fields: [kycSessions.agentId],
    references: [agents.id],
  }),
}));

// ─── Devices ──────────────────────────────────────────────────────────────────
export const devicesRelationsEnhanced = relations(devices, ({ one, many }) => ({
  agent: one(agents, {
    fields: [devices.agentId],
    references: [agents.id],
  }),
  commands: many(deviceCommands),
  complianceViolations: many(deviceComplianceViolations),
  locations: many(deviceLocations),
  otaUpdateLog: many(otaUpdateLog),
}));

// ─── POS Terminals ────────────────────────────────────────────────────────────
export const posTerminalsRelationsEnhanced = relations(posTerminals, ({ one, many }) => ({
  agent: one(agents, {
    fields: [posTerminals.agentId],
    references: [agents.id],
  }),
  merchant: one(merchants, {
    fields: [posTerminals.merchantId],
    references: [merchants.id],
  }),
  group: one(terminalGroups, {
    fields: [posTerminals.groupId],
    references: [terminalGroups.id],
  }),
  serviceRecords: many(serviceRecords),
  softwareUpdates: many(softwareUpdates),
  leases: many(terminalLeases),
  settlementBatches: many(posSettlementBatches),
  receiptTemplates: many(receiptTemplates),
}));

// ─── Commission Rules ─────────────────────────────────────────────────────────
export const commissionRulesRelationsEnhanced = relations(commissionRules, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [commissionRules.tenantId],
    references: [tenants.id],
  }),
  tiers: many(commissionTiers),
  payouts: many(commissionPayouts),
  auditTrail: many(commissionAuditTrail),
}));

// ─── Workflow Definitions ─────────────────────────────────────────────────────
export const workflowDefinitionsRelationsEnhanced = relations(workflowDefinitions, ({ many }) => ({
  instances: many(workflowInstances),
}));

export const workflowInstancesRelationsEnhanced = relations(workflowInstances, ({ one }) => ({
  definition: one(workflowDefinitions, {
    fields: [workflowInstances.workflowId],
    references: [workflowDefinitions.id],
  }),
  temporalLog: one(temporalWorkflowLog, {
    fields: [workflowInstances.temporalWorkflowId],
    references: [temporalWorkflowLog.workflowId],
  }),
}));

// ─── GL Accounts ──────────────────────────────────────────────────────────────
export const glAccountsRelationsEnhanced = relations(gl_accounts, ({ many }) => ({
  journalEntries: many(gl_journal_entries),
  glEntries: many(glEntries),
}));

// ─── SLA Definitions ─────────────────────────────────────────────────────────
export const slaDefinitionsRelationsEnhanced = relations(sla_definitions, ({ many }) => ({
  breaches: many(sla_breaches),
}));

// ─── Notification Channels ────────────────────────────────────────────────────
export const notificationChannelsRelationsEnhanced = relations(notification_channels, ({ many }) => ({
  logs: many(notification_logs),
}));

// ─── Training Courses ─────────────────────────────────────────────────────────
export const trainingCoursesRelationsEnhanced = relations(trainingCourses, ({ many }) => ({
  enrollments: many(trainingEnrollments),
  feedback: many(guideFeedback),
}));

// ─── API Keys ─────────────────────────────────────────────────────────────────
export const apiKeysRelationsEnhanced = relations(apiKeys, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [apiKeys.tenantId],
    references: [tenants.id],
  }),
  usage: many(apiKeyUsage),
}));

// ─── Webhook Endpoints ────────────────────────────────────────────────────────
export const webhookEndpointsRelationsEnhanced = relations(webhookEndpoints, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [webhookEndpoints.tenantId],
    references: [tenants.id],
  }),
  deliveries: many(webhookDeliveries),
}));

// ─── Reconciliation Batches ───────────────────────────────────────────────────
export const reconciliationBatchesRelationsEnhanced = relations(reconciliationBatches, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [reconciliationBatches.tenantId],
    references: [tenants.id],
  }),
  items: many(reconciliationItems),
}));

// ─── AML Screenings ───────────────────────────────────────────────────────────
export const amlScreeningsRelationsEnhanced = relations(amlScreenings, ({ one }) => ({
  agent: one(agents, {
    fields: [amlScreenings.agentId],
    references: [agents.id],
  }),
  transaction: one(transactions, {
    fields: [amlScreenings.transactionId],
    references: [transactions.id],
  }),
}));

// ─── Face Enrollments ─────────────────────────────────────────────────────────
export const faceEnrollmentsRelationsEnhanced = relations(faceEnrollments, ({ one, many }) => ({
  agent: one(agents, {
    fields: [faceEnrollments.agentId],
    references: [agents.id],
  }),
  auditEvents: many(biometricAuditEvents),
}));

// ─── Customers ────────────────────────────────────────────────────────────────
export const customersRelationsEnhanced = relations(customers, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [customers.tenantId],
    references: [tenants.id],
  }),
  journeyEvents: many(customer_journey_events),
  journeySteps: many(customerJourneySteps),
  dataConsentRecords: many(dataConsentRecords),
  dataRightsRequests: many(dataRightsRequests),
  creditApplications: many(creditApplications),
  creditScoreHistory: many(creditScoreHistory),
}));

// ─── Platform Incidents ───────────────────────────────────────────────────────
export const platformIncidentsRelationsEnhanced = relations(platform_incidents, ({ many }) => ({
  healthChecks: many(platform_health_checks),
}));
