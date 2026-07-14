/**
 * Drizzle ORM — Complete TypeScript Type Exports
 * ─────────────────────────────────────────────────────────────────────────────
 * Exports $inferSelect and $inferInsert types for all 169 tables.
 * The 105 types already in schema.ts are re-exported here for a single
 * import point. The 64 missing types are added below.
 *
 * Usage:
 *   import type { Agent, InsertAgent, Transaction, ... } from "@/drizzle/schema-types";
 */

// ── Re-export all existing types from schema.ts ───────────────────────────────
export type {
  User, InsertUser,
  Agent, InsertAgent,
  Transaction, InsertTransaction,
  FraudAlert, InsertFraudAlert,
  LoyaltyHistory,
  ChatSession,
  ChatMessage,
  AuditLog,
  FloatTopUpRequest,
  OtpToken,
  Device, InsertDevice,
  DeviceCommand,
  SupervisorAgent,
  Dispute,
  DisputeMessage,
  Refund,
  PlatformSetting,
  VelocityLimit,
  ComplianceReport,
  GeofenceZone,
  AgentGeofenceZone,
  DeviceLocation,
  KycSession,
  PosTerminal,
  TerminalGroup,
  ServiceRecord,
  SoftwareUpdate,
  TerminalLease,
  PosSettlementBatch,
  CommissionRule,
  QrCode,
  InventoryItem,
  MultiSimProfile,
  ReversalRequest,
  ShareableLink,
  Customer,
  Tenant,
  ErpSyncLog,
  StorefrontAd,
  VatRecord,
  ErpConfig,
  MqttBridgeConfig,
  AnalyticsMetric,
  WebhookSecret,
  EmailQueue,
  Merchant,
  MerchantSettlement,
  ApiKey,
  ApiKeyUsage,
  Fido2Credential,
  Fido2Challenge,
  CreditScoreHistory,
  CreditApplication,
  OtaRelease,
  OtaUpdateLog,
  DataRightsRequest,
  FraudRule,
  AgentPushSubscription,
  ConnectivityLog,
  SystemConfig,
  SimProbeLog,
  SimOrchestratorConfig,
  SimFailoverLog,
  DlqMessage,
  CommissionPayout,
  Referral,
  WebhookEndpoint,
  WebhookDelivery,
  AgentOnboardingProgress,
  SettlementReconciliation,
  RateAlert,
  EmailDeliveryLog,
  InviteCode,
  TenantBranding,
  TenantCorridor,
  TenantFeeOverride,
  TenantUser,
  AgentBankAccount,
  KycDocument,
  FloatReconciliation,
  AgentPerformanceScore,
  CommissionClawback,
  PnlReport,
  TransactionLimit,
  ComplianceCheck,
  AgentSuspensionLog,
  TxMonitoringAlert,
  FraudMlScore,
  AgentLoan,
  FeeRule,
  FeeAuditTrail,
  MerchantKycDoc,
  MerchantPayout,
  ComplianceFiling,
  AgentAchievement,
  AgentBadge,
  TenantFeatureToggle,
  ReconciliationBatch,
  ReconciliationItem,
  AnalyticsDashboard,
  CustomerJourneyStep,
  RateLimitRule,
  BackupSnapshot,
  WorkflowDefinition,
  WorkflowInstance,
  GlEntry,
  TrainingCourse,
  TrainingEnrollment,
  BiReportDefinition,
  ObservabilityAlert,
  EncryptedField,
  DataConsentRecord,
} from "./schema";

// ── Import tables for the 64 missing type definitions ────────────────────────
import {
  deviceCompliancePolicies,
  deviceComplianceViolations,
  mdmGeofenceViolations,
  commissionPayouts,
  referrals,
  webhookEndpoints,
  webhookDeliveries,
  agentOnboardingProgress,
  settlementReconciliation,
  commissionCascadeHistory,
  agentBankAccounts,
  kycDocuments,
  floatReconciliations,
  agentPerformanceScores,
  commissionClawbacks,
  pnlReports,
  geoFences,
  transactionLimits,
  complianceChecks,
  agentSuspensionLog,
  txMonitoringAlerts,
  fraudMlScores,
  notificationDispatchLog,
  agentLoans,
  feeRules,
  feeAuditTrail,
  merchantKycDocs,
  merchantPayouts,
  complianceFilings,
  agentAchievements,
  agentBadges,
  tenantFeatureToggles,
  reconciliationBatches,
  reconciliationItems,
  analyticsDashboards,
  customerJourneySteps,
  rateLimitRules,
  backupSnapshots,
  workflowDefinitions,
  workflowInstances,
  glEntries,
  trainingCourses,
  trainingEnrollments,
  biReportDefinitions,
  observabilityAlerts,
  encryptedFields,
  dataConsentRecords,
  realtime_tx_alerts,
  notification_channels,
  notification_logs,
  customer_journey_events,
  gl_accounts,
  gl_journal_entries,
  sla_definitions,
  sla_breaches,
  data_export_jobs,
  platform_health_checks,
  platform_incidents,
  platformBillingLedger,
  billingRevenuePeriods,
  billingReconciliationReports,
  billingRoleAssignments,
  billingAuditLog,
  tenantBillingConfig,
  billingProvisioningHistory,
  ecommerceInventoryReservations,
  amlScreenings,
  amlWatchlistEntries,
  idempotencyKeys,
  temporalWorkflowLog,
  permifyCheckLog,
  openappsecThreatLog,
  fluvioEventLog,
  lakehouseSyncLog,
  daprPubsubLog,
  commissionTiers,
  commissionSplits,
  disputeEvidence,
  commissionAuditTrail,
  loadTestRuns,
  faceEnrollments,
  biometricAuditEvents,
  receiptTemplates,
  guideFeedback,
} from "./schema";

// ── 64 Missing Select Types ───────────────────────────────────────────────────
export type DeviceCompliancePolicy      = typeof deviceCompliancePolicies.$inferSelect;
export type InsertDeviceCompliancePolicy = typeof deviceCompliancePolicies.$inferInsert;

export type DeviceComplianceViolation   = typeof deviceComplianceViolations.$inferSelect;
export type InsertDeviceComplianceViolation = typeof deviceComplianceViolations.$inferInsert;

export type MdmGeofenceViolation        = typeof mdmGeofenceViolations.$inferSelect;
export type InsertMdmGeofenceViolation  = typeof mdmGeofenceViolations.$inferInsert;

export type CommissionPayout            = typeof commissionPayouts.$inferSelect;
export type InsertCommissionPayout      = typeof commissionPayouts.$inferInsert;

export type Referral                    = typeof referrals.$inferSelect;
export type InsertReferral              = typeof referrals.$inferInsert;

export type WebhookEndpoint             = typeof webhookEndpoints.$inferSelect;
export type InsertWebhookEndpoint       = typeof webhookEndpoints.$inferInsert;

export type WebhookDelivery             = typeof webhookDeliveries.$inferSelect;
export type InsertWebhookDelivery       = typeof webhookDeliveries.$inferInsert;

export type AgentOnboardingProgress     = typeof agentOnboardingProgress.$inferSelect;
export type InsertAgentOnboardingProgress = typeof agentOnboardingProgress.$inferInsert;

export type SettlementReconciliation    = typeof settlementReconciliation.$inferSelect;
export type InsertSettlementReconciliation = typeof settlementReconciliation.$inferInsert;

export type CommissionCascadeHistory    = typeof commissionCascadeHistory.$inferSelect;
export type InsertCommissionCascadeHistory = typeof commissionCascadeHistory.$inferInsert;

export type AgentBankAccount            = typeof agentBankAccounts.$inferSelect;
export type InsertAgentBankAccount      = typeof agentBankAccounts.$inferInsert;

export type KycDocument                 = typeof kycDocuments.$inferSelect;
export type InsertKycDocument           = typeof kycDocuments.$inferInsert;

export type FloatReconciliation         = typeof floatReconciliations.$inferSelect;
export type InsertFloatReconciliation   = typeof floatReconciliations.$inferInsert;

export type AgentPerformanceScore       = typeof agentPerformanceScores.$inferSelect;
export type InsertAgentPerformanceScore = typeof agentPerformanceScores.$inferInsert;

export type CommissionClawback          = typeof commissionClawbacks.$inferSelect;
export type InsertCommissionClawback    = typeof commissionClawbacks.$inferInsert;

export type PnlReport                   = typeof pnlReports.$inferSelect;
export type InsertPnlReport             = typeof pnlReports.$inferInsert;

export type GeoFence                    = typeof geoFences.$inferSelect;
export type InsertGeoFence              = typeof geoFences.$inferInsert;

export type TransactionLimit            = typeof transactionLimits.$inferSelect;
export type InsertTransactionLimit      = typeof transactionLimits.$inferInsert;

export type ComplianceCheck             = typeof complianceChecks.$inferSelect;
export type InsertComplianceCheck       = typeof complianceChecks.$inferInsert;

export type AgentSuspensionLog          = typeof agentSuspensionLog.$inferSelect;
export type InsertAgentSuspensionLog    = typeof agentSuspensionLog.$inferInsert;

export type TxMonitoringAlert           = typeof txMonitoringAlerts.$inferSelect;
export type InsertTxMonitoringAlert     = typeof txMonitoringAlerts.$inferInsert;

export type FraudMlScore                = typeof fraudMlScores.$inferSelect;
export type InsertFraudMlScore          = typeof fraudMlScores.$inferInsert;

export type NotificationDispatchLog     = typeof notificationDispatchLog.$inferSelect;
export type InsertNotificationDispatchLog = typeof notificationDispatchLog.$inferInsert;

export type AgentLoan                   = typeof agentLoans.$inferSelect;
export type InsertAgentLoan             = typeof agentLoans.$inferInsert;

export type FeeRule                     = typeof feeRules.$inferSelect;
export type InsertFeeRule               = typeof feeRules.$inferInsert;

export type FeeAuditTrail               = typeof feeAuditTrail.$inferSelect;
export type InsertFeeAuditTrail         = typeof feeAuditTrail.$inferInsert;

export type MerchantKycDoc              = typeof merchantKycDocs.$inferSelect;
export type InsertMerchantKycDoc        = typeof merchantKycDocs.$inferInsert;

export type MerchantPayout              = typeof merchantPayouts.$inferSelect;
export type InsertMerchantPayout        = typeof merchantPayouts.$inferInsert;

export type ComplianceFiling            = typeof complianceFilings.$inferSelect;
export type InsertComplianceFiling      = typeof complianceFilings.$inferInsert;

export type AgentAchievement            = typeof agentAchievements.$inferSelect;
export type InsertAgentAchievement      = typeof agentAchievements.$inferInsert;

export type AgentBadge                  = typeof agentBadges.$inferSelect;
export type InsertAgentBadge            = typeof agentBadges.$inferInsert;

export type TenantFeatureToggle         = typeof tenantFeatureToggles.$inferSelect;
export type InsertTenantFeatureToggle   = typeof tenantFeatureToggles.$inferInsert;

export type ReconciliationBatch         = typeof reconciliationBatches.$inferSelect;
export type InsertReconciliationBatch   = typeof reconciliationBatches.$inferInsert;

export type ReconciliationItem          = typeof reconciliationItems.$inferSelect;
export type InsertReconciliationItem    = typeof reconciliationItems.$inferInsert;

export type AnalyticsDashboard          = typeof analyticsDashboards.$inferSelect;
export type InsertAnalyticsDashboard    = typeof analyticsDashboards.$inferInsert;

export type CustomerJourneyStep         = typeof customerJourneySteps.$inferSelect;
export type InsertCustomerJourneyStep   = typeof customerJourneySteps.$inferInsert;

export type RateLimitRule               = typeof rateLimitRules.$inferSelect;
export type InsertRateLimitRule         = typeof rateLimitRules.$inferInsert;

export type BackupSnapshot              = typeof backupSnapshots.$inferSelect;
export type InsertBackupSnapshot        = typeof backupSnapshots.$inferInsert;

export type WorkflowDefinition          = typeof workflowDefinitions.$inferSelect;
export type InsertWorkflowDefinition    = typeof workflowDefinitions.$inferInsert;

export type WorkflowInstance            = typeof workflowInstances.$inferSelect;
export type InsertWorkflowInstance      = typeof workflowInstances.$inferInsert;

export type GlEntry                     = typeof glEntries.$inferSelect;
export type InsertGlEntry               = typeof glEntries.$inferInsert;

export type TrainingCourse              = typeof trainingCourses.$inferSelect;
export type InsertTrainingCourse        = typeof trainingCourses.$inferInsert;

export type TrainingEnrollment          = typeof trainingEnrollments.$inferSelect;
export type InsertTrainingEnrollment    = typeof trainingEnrollments.$inferInsert;

export type BiReportDefinition          = typeof biReportDefinitions.$inferSelect;
export type InsertBiReportDefinition    = typeof biReportDefinitions.$inferInsert;

export type ObservabilityAlert          = typeof observabilityAlerts.$inferSelect;
export type InsertObservabilityAlert    = typeof observabilityAlerts.$inferInsert;

export type EncryptedField              = typeof encryptedFields.$inferSelect;
export type InsertEncryptedField        = typeof encryptedFields.$inferInsert;

export type DataConsentRecord           = typeof dataConsentRecords.$inferSelect;
export type InsertDataConsentRecord     = typeof dataConsentRecords.$inferInsert;

export type RealtimeTxAlert             = typeof realtime_tx_alerts.$inferSelect;
export type InsertRealtimeTxAlert       = typeof realtime_tx_alerts.$inferInsert;

export type NotificationChannel         = typeof notification_channels.$inferSelect;
export type InsertNotificationChannel   = typeof notification_channels.$inferInsert;

export type NotificationLog             = typeof notification_logs.$inferSelect;
export type InsertNotificationLog       = typeof notification_logs.$inferInsert;

export type CustomerJourneyEvent        = typeof customer_journey_events.$inferSelect;
export type InsertCustomerJourneyEvent  = typeof customer_journey_events.$inferInsert;

export type GlAccount                   = typeof gl_accounts.$inferSelect;
export type InsertGlAccount             = typeof gl_accounts.$inferInsert;

export type GlJournalEntry              = typeof gl_journal_entries.$inferSelect;
export type InsertGlJournalEntry        = typeof gl_journal_entries.$inferInsert;

export type SlaDefinition               = typeof sla_definitions.$inferSelect;
export type InsertSlaDefinition         = typeof sla_definitions.$inferInsert;

export type SlaBreach                   = typeof sla_breaches.$inferSelect;
export type InsertSlaBreach             = typeof sla_breaches.$inferInsert;

export type DataExportJob               = typeof data_export_jobs.$inferSelect;
export type InsertDataExportJob         = typeof data_export_jobs.$inferInsert;

export type PlatformHealthCheck         = typeof platform_health_checks.$inferSelect;
export type InsertPlatformHealthCheck   = typeof platform_health_checks.$inferInsert;

export type PlatformIncident            = typeof platform_incidents.$inferSelect;
export type InsertPlatformIncident      = typeof platform_incidents.$inferInsert;

export type PlatformBillingLedger       = typeof platformBillingLedger.$inferSelect;
export type InsertPlatformBillingLedger = typeof platformBillingLedger.$inferInsert;

export type BillingRevenuePeriod        = typeof billingRevenuePeriods.$inferSelect;
export type InsertBillingRevenuePeriod  = typeof billingRevenuePeriods.$inferInsert;

export type BillingReconciliationReport = typeof billingReconciliationReports.$inferSelect;
export type InsertBillingReconciliationReport = typeof billingReconciliationReports.$inferInsert;

export type BillingRoleAssignment       = typeof billingRoleAssignments.$inferSelect;
export type InsertBillingRoleAssignment = typeof billingRoleAssignments.$inferInsert;

export type BillingAuditLog             = typeof billingAuditLog.$inferSelect;
export type InsertBillingAuditLog       = typeof billingAuditLog.$inferInsert;

export type TenantBillingConfig         = typeof tenantBillingConfig.$inferSelect;
export type InsertTenantBillingConfig   = typeof tenantBillingConfig.$inferInsert;

export type BillingProvisioningHistory  = typeof billingProvisioningHistory.$inferSelect;
export type InsertBillingProvisioningHistory = typeof billingProvisioningHistory.$inferInsert;

export type EcommerceInventoryReservation = typeof ecommerceInventoryReservations.$inferSelect;
export type InsertEcommerceInventoryReservation = typeof ecommerceInventoryReservations.$inferInsert;

export type AmlScreening                = typeof amlScreenings.$inferSelect;
export type InsertAmlScreening          = typeof amlScreenings.$inferInsert;

export type AmlWatchlistEntry           = typeof amlWatchlistEntries.$inferSelect;
export type InsertAmlWatchlistEntry     = typeof amlWatchlistEntries.$inferInsert;

export type IdempotencyKey              = typeof idempotencyKeys.$inferSelect;
export type InsertIdempotencyKey        = typeof idempotencyKeys.$inferInsert;

// ── Middleware Integration Log Types ─────────────────────────────────────────
export type TemporalWorkflowLog         = typeof temporalWorkflowLog.$inferSelect;
export type InsertTemporalWorkflowLog   = typeof temporalWorkflowLog.$inferInsert;

export type PermifyCheckLog             = typeof permifyCheckLog.$inferSelect;
export type InsertPermifyCheckLog       = typeof permifyCheckLog.$inferInsert;

export type OpenappsecThreatLog         = typeof openappsecThreatLog.$inferSelect;
export type InsertOpenappsecThreatLog   = typeof openappsecThreatLog.$inferInsert;

export type FluvioEventLog              = typeof fluvioEventLog.$inferSelect;
export type InsertFluvioEventLog        = typeof fluvioEventLog.$inferInsert;

export type LakehouseSyncLog            = typeof lakehouseSyncLog.$inferSelect;
export type InsertLakehouseSyncLog      = typeof lakehouseSyncLog.$inferInsert;

export type DaprPubsubLog               = typeof daprPubsubLog.$inferSelect;
export type InsertDaprPubsubLog         = typeof daprPubsubLog.$inferInsert;

// ── Commission & Gamification Types ──────────────────────────────────────────
export type CommissionTier              = typeof commissionTiers.$inferSelect;
export type InsertCommissionTier        = typeof commissionTiers.$inferInsert;

export type CommissionSplit             = typeof commissionSplits.$inferSelect;
export type InsertCommissionSplit       = typeof commissionSplits.$inferInsert;

export type DisputeEvidence             = typeof disputeEvidence.$inferSelect;
export type InsertDisputeEvidence       = typeof disputeEvidence.$inferInsert;

export type CommissionAuditTrail        = typeof commissionAuditTrail.$inferSelect;
export type InsertCommissionAuditTrail  = typeof commissionAuditTrail.$inferInsert;

export type LoadTestRun                 = typeof loadTestRuns.$inferSelect;
export type InsertLoadTestRun           = typeof loadTestRuns.$inferInsert;

export type FaceEnrollment              = typeof faceEnrollments.$inferSelect;
export type InsertFaceEnrollment        = typeof faceEnrollments.$inferInsert;

export type BiometricAuditEvent         = typeof biometricAuditEvents.$inferSelect;
export type InsertBiometricAuditEvent   = typeof biometricAuditEvents.$inferInsert;

export type ReceiptTemplate             = typeof receiptTemplates.$inferSelect;
export type InsertReceiptTemplate       = typeof receiptTemplates.$inferInsert;

export type GuideFeedback               = typeof guideFeedback.$inferSelect;
export type InsertGuideFeedback         = typeof guideFeedback.$inferInsert;
