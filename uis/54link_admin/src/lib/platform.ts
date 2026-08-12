export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";
export type ExposureTrend = "up" | "down" | "flat";
export type SyncState = "healthy" | "warning" | "critical" | "unknown";
export type ContractState = "draft" | "active" | "review" | "matured" | "delinquent";
export type CustomerStatus = "Active" | "Pending" | "Review" | "Dormant";
export type CustomerSegment = string;
export type CustomerTier = string;
export type CustomerRisk = string;
export type WorkflowStage = string;
export type WorkflowStatus = string;
export type OperatorActionState = "Pending" | "In progress" | "Done";
export type OperatorRole = "branch" | "operations" | "treasury" | "compliance";
export type AuditSeverity = "info" | "warning" | "critical";
export type ExportStatus = "Ready" | "Queued" | "Failed";

export interface ProductSurface {
  key: string;
  title: string;
  category: "retail" | "operations" | "treasury" | "trade" | "partnerships";
  summary: string;
  route: string;
  status: HealthStatus;
  services: string[];
}

export interface ServiceHealth {
  name: string;
  route: string;
  status: HealthStatus;
  latencyMs?: number;
  description: string;
  dependencies: string[];
}

export interface PortfolioMetric {
  label: string;
  value: string;
  detail: string;
  trend: ExposureTrend;
}

export interface TellerSession {
  tellerId: string;
  tellerName: string;
  branch: string;
  tillAccountId: string;
  state: "open" | "balanced" | "under_review" | "closed";
  openingFloat: number;
  availableCash: number;
  pendingTransactions: number;
  imbalanceAmount: number;
  lastBalancedAt?: string;
}

export interface TellerTransaction {
  transactionId: string;
  tellerId?: string;
  customerName: string;
  transactionType: "cash_deposit" | "cash_withdrawal" | "vault_funding" | "vault_return" | "reversal_review";
  amount: number;
  currency: string;
  branch?: string;
  status: "processing" | "posted" | "review" | "failed";
  createdAt: string;
}

export interface ReconciliationSnapshot {
  snapshotId: string;
  state: SyncState;
  discrepancyCount: number;
  autoResolvedCount: number;
  manualReviewCount: number;
  lastRunAt: string;
  summary: string;
}

export interface ReconciliationDiscrepancy {
  discrepancyId: string;
  accountId: string;
  classification: string;
  severity: "low" | "medium" | "high" | "critical";
  tigerbeetleValue: number;
  postgresValue: number;
  delta: number;
  resolutionState: "open" | "acknowledged" | "repaired" | "suppressed";
}

export interface ERPNextSyncRecord {
  syncId: string;
  documentType: string;
  sourceEntity: string;
  sourceReference?: string;
  status: "queued" | "in_progress" | "succeeded" | "retrying" | "failed" | "degraded";
  idempotencyKey: string;
  lastAttemptAt?: string;
  lastWebhookAt?: string;
  errorDetail?: string;
  attemptCount?: number;
}

export interface ERPNextConfigSummary {
  enabled: boolean;
  baseUrl?: string;
  company?: string;
  mode: "sandbox" | "production" | "unknown";
  mappedDocuments: string[];
  callbackUrl?: string;
  maxAttempts?: number;
  syncTimeoutSeconds?: number;
}

export interface IslamicProduct {
  productId: string;
  name: string;
  contractType: "murabaha" | "ijara" | "mudarabah";
  state: ContractState;
  assetClass: string;
  approvedExposure: number;
  outstandingExposure: number;
  profitRateDescription: string;
  nextMilestone: string;
}

export interface IslamicPortfolioSummary {
  activeContracts: number;
  approvedExposure: number;
  outstandingExposure: number;
  delinquentContracts: number;
  takafulCoverageRate: number;
}

export interface OverviewResponse {
  asOf: string;
  products: ProductSurface[];
  serviceHealth: ServiceHealth[];
  metrics: PortfolioMetric[];
}

export interface LedgerOutcomeSummary {
  domain: string;
  source: string;
  connected: boolean;
  tigerBeetlePosting: string;
  middleware: string[];
  downstreamSinks: string[];
  recommendedPostingSeams: string[];
  detail: string;
}

export interface TellerOverviewResponse {
  asOf: string;
  sessions: TellerSession[];
  recentTransactions: TellerTransaction[];
  summary?: {
    sessionsUnderReview?: number;
    activeSessions?: number;
    cashOnTill?: number;
  };
  ledgerOutcome?: LedgerOutcomeSummary;
}

export interface ReconciliationResponse {
  asOf: string;
  latestSnapshot?: ReconciliationSnapshot;
  discrepancies: ReconciliationDiscrepancy[];
  ledgerOutcome?: LedgerOutcomeSummary;
}

export interface ERPNextResponse {
  asOf: string;
  config: ERPNextConfigSummary;
  syncHistory: ERPNextSyncRecord[];
  metrics?: Record<string, number>;
  ledgerOutcome?: LedgerOutcomeSummary;
}

export interface IslamicBankingResponse {
  asOf: string;
  summary: IslamicPortfolioSummary;
  contracts: IslamicProduct[];
  ledgerOutcome?: LedgerOutcomeSummary;
}

export interface ProductCatalogResponse {
  asOf: string;
  products: ProductSurface[];
}

export interface CustomerRecord {
  id: string;
  name: string;
  segment: CustomerSegment;
  tier: CustomerTier;
  location: string;
  relationshipManager: string;
  risk: CustomerRisk;
  status: CustomerStatus;
  bvn: string;
  phone: string;
  balance: number;
  lastTouchpoint: string;
}

export interface WorkflowCase {
  id: string;
  customer: string;
  product: string;
  stage: WorkflowStage;
  status: WorkflowStatus;
  channel: string;
  amount: number;
  nextAction: string;
  slaHours: number;
}

export interface OperatorAction {
  id: string;
  domainKey: string;
  title: string;
  detail: string;
  owner: string;
  due: string;
  route: string;
  status: OperatorActionState;
  roles?: OperatorRole[];
}

export interface SearchRecord {
  id: string;
  type: string;
  title: string;
  subtitle: string;
  meta: string;
  route?: string;
}

export interface RoleProfile {
  role: OperatorRole;
  title: string;
  description: string;
  defaultRoute: string;
  permissions: string[];
  visibleDomains: string[];
  exportScopes: string[];
}

export interface AuthContextResponse {
  asOf: string;
  tenantId: string;
  role: OperatorRole;
  actorId: string;
  issuer: string;
  authzEndpoint: string;
  gateway: string;
  permissions: string[];
  visibleDomains: string[];
  exportScopes: string[];
  defaultRoute: string;
}

export interface TenantFeatureFlagRecord {
  key: string;
  label: string;
  category: "onboarding" | "payments" | "cards" | "operations" | "compliance" | "platform";
  description: string;
  enabled: boolean;
  rolloutStage: "pilot" | "controlled" | "general";
  adminManaged: boolean;
  dependsOn?: string[];
}

export interface TenantWhiteLabelProfile {
  displayName: string;
  legalEntity: string;
  supportEmail: string;
  primaryColor: string;
  accentColor: string;
  logoUrl: string;
  loginHeadline: string;
  customDomain?: string;
}

export interface TenantConfiguration {
  tenantId: string;
  name: string;
  onboardingStatus: "draft" | "active" | "restricted";
  segment: "retail" | "operations" | "growth";
  region: string;
  featureFlags: TenantFeatureFlagRecord[];
  whiteLabel: TenantWhiteLabelProfile;
  enabledModules: string[];
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actorRole: OperatorRole;
  actorId: string;
  entityType: string;
  entityId: string;
  action: string;
  outcome: string;
  severity: AuditSeverity;
  route: string;
  middleware: string[];
  detail: string;
}

export interface AuditResponse {
  asOf: string;
  role: OperatorRole;
  items: AuditEntry[];
  total: number;
}

export interface ExportJob {
  id: string;
  domainKey: string;
  title: string;
  format: "csv" | "json" | "xlsx";
  status: ExportStatus;
  createdAt: string;
  requestedByRole: OperatorRole;
  route: string;
  rowCount: number;
  approvalState: "Signed" | "Pending review";
  approvalSignature: string;
  downloadUrl: string;
  retainedUntil?: string;
  reportVersion?: string;
  approvalChain?: string[];
  signedBy?: string[];
}

export interface ExportResponse {
  asOf: string;
  role: OperatorRole;
  items: ExportJob[];
  total: number;
}

export interface BillingAccountRecord {
  id: string;
  tenantId: string;
  accountName: string;
  billingModel: "subscription" | "usage" | "hybrid" | "revenue_share";
  currency: string;
  status: "draft" | "active" | "suspended" | "closed";
  contractStartAt: string;
  contractEndAt?: string;
  defaultRateCardId: string;
  minimumCommitAmount: number;
}

export interface BillingRateCardRecord {
  id: string;
  billingAccountId?: string;
  name: string;
  version: number;
  status: "draft" | "approved" | "active" | "retired";
  effectiveFrom: string;
  effectiveTo?: string;
  pricingCurrency: string;
  createdBy: string;
  approvalState: "pending" | "approved" | "rejected";
}

export interface BillingRateCardLineRecord {
  id: string;
  rateCardId: string;
  meterKey: string;
  productKey: string;
  chargeType: "flat" | "per_unit" | "tiered" | "minimum" | "percentage";
  unitPrice: number;
  includedUnits: number;
  minimumCharge?: number;
  maximumCharge?: number;
  settlementLedgerCode?: string;
}

export interface BillingUsageEventRecord {
  id: string;
  idempotencyKey: string;
  tenantId: string;
  billingAccountId: string;
  sourceService: string;
  sourceEventType: string;
  meterKey: string;
  productKey: string;
  quantity: number;
  unitAmount?: number;
  currency: string;
  eventTimestamp: string;
  ingestedAt: string;
  correlationId?: string;
  actorId?: string;
  resourceId?: string;
  payload: Record<string, unknown>;
  status: "pending" | "rated" | "ignored" | "failed";
}

export interface BillingRatedEventRecord {
  id: string;
  usageEventId: string;
  rateCardId: string;
  rateCardLineId: string;
  billingPeriodKey: string;
  quantityRated: number;
  billableUnits: number;
  amountAccrued: number;
  currency: string;
  ratingExplanation: Record<string, unknown>;
  ratedAt: string;
}

export interface BillingAccrualSnapshotRecord {
  id: string;
  tenantId: string;
  billingAccountId: string;
  billingPeriodKey: string;
  meterKey: string;
  productKey: string;
  ratedEventCount: number;
  usageQuantity: number;
  accruedAmount: number;
  unratedEventCount: number;
  lastUsageAt?: string;
  lastRatedAt?: string;
  snapshotStatus: "healthy" | "lagging" | "review";
}

export interface BillingContractOverrideRecord {
  id: string;
  billingAccountId: string;
  tenantId: string;
  overrideType: "unit_price" | "included_units" | "minimum_commit" | "billing_model" | "billing_period";
  meterKey?: string;
  productKey?: string;
  valueNumber?: number;
  valueText?: string;
  effectiveFrom: string;
  effectiveTo?: string;
  status: "draft" | "active" | "expired";
  createdBy: string;
  notes?: string;
}

export interface BillingDiscountRuleRecord {
  id: string;
  billingAccountId: string;
  tenantId: string;
  name: string;
  discountType: "percentage" | "fixed" | "threshold_percentage";
  meterKey?: string;
  productKey?: string;
  percentage?: number;
  fixedAmount?: number;
  thresholdAmount?: number;
  effectiveFrom: string;
  effectiveTo?: string;
  status: "draft" | "active" | "expired";
  createdBy: string;
}

export interface BillingRevenueShareRuleRecord {
  id: string;
  billingAccountId: string;
  tenantId: string;
  name: string;
  target: "platform" | "partner_bank" | "aggregator" | "reseller";
  percentage: number;
  beneficiaryName: string;
  settlementLedgerCode?: string;
  effectiveFrom: string;
  effectiveTo?: string;
  status: "draft" | "active" | "expired";
  createdBy: string;
}

export interface BillingInvoiceRecord {
  id: string;
  invoiceNumber: string;
  tenantId: string;
  billingAccountId: string;
  billingPeriodKey: string;
  billingPeriodType: "monthly" | "quarterly" | "semi_annual" | "annual" | "custom";
  periodStartAt: string;
  periodEndAt: string;
  currency: string;
  subtotalAmount: number;
  discountAmount: number;
  revenueShareAmount: number;
  minimumCommitAdjustment: number;
  taxAmount: number;
  totalAmount: number;
  status: "draft" | "pending_approval" | "approved" | "rejected" | "issued" | "paid" | "void";
  approvalStatus: "pending" | "approved" | "rejected" | "skipped";
  generatedAt: string;
  dueAt: string;
  approvalStepCount: number;
  issuedAt?: string;
}

export interface BillingInvoiceLineRecord {
  id: string;
  invoiceId: string;
  lineType: "usage" | "discount" | "revenue_share" | "minimum_commit" | "tax";
  meterKey?: string;
  productKey?: string;
  description: string;
  quantity: number;
  unitPrice: number;
  amount: number;
  metadata?: Record<string, unknown>;
}

export interface BillingInvoiceApprovalRecord {
  id: string;
  invoiceId: string;
  stageKey: string;
  actorRole: "operations" | "treasury" | "compliance" | "branch";
  status: "pending" | "approved" | "rejected" | "skipped";
  actedAt?: string;
  note?: string;
}

export interface BillingDashboardResponse {
  asOf: string;
  summary: {
    billingPeriodKey: string;
    currency: string;
    totalAccruedAmount: number;
    ratedEventCount: number;
    unratedEventCount: number;
    usageEventCount: number;
    draftInvoiceCount: number;
    pendingApprovalInvoiceCount: number;
    issuedInvoiceAmount: number;
    topMeters: Array<{
      meterKey: string;
      productKey: string;
      accruedAmount: number;
      usageQuantity: number;
    }>;
    thresholdAlerts: Array<{
      id: string;
      severity: "info" | "warning" | "critical";
      title: string;
      detail: string;
    }>;
    liveSeries: Array<{
      periodKey: string;
      accruedAmount: number;
      usageEventCount: number;
      invoiceAmount: number;
    }>;
    contractSummary: {
      overrideCount: number;
      discountRuleCount: number;
      revenueShareRuleCount: number;
    };
  };
  accounts: BillingAccountRecord[];
  rateCards: BillingRateCardRecord[];
  rateCardLines: BillingRateCardLineRecord[];
  usageEvents: BillingUsageEventRecord[];
  ratedEvents: BillingRatedEventRecord[];
  accruals: BillingAccrualSnapshotRecord[];
  invoices: BillingInvoiceRecord[];
  invoiceLines: BillingInvoiceLineRecord[];
  invoiceApprovals: BillingInvoiceApprovalRecord[];
  contractOverrides: BillingContractOverrideRecord[];
  discountRules: BillingDiscountRuleRecord[];
  revenueShareRules: BillingRevenueShareRuleRecord[];
  middleware: string[];
}

export interface MiddlewareSurface {
  key: string;
  title: string;
  status: HealthStatus;
  scope: string;
  languages: string[];
  directlyIntegrated: boolean;
  notes: string;
  services: string[];
}

export interface TigerBeetleIntegrationResponse {
  asOf: string;
  directIntegrationAssessment: {
    robust: boolean;
    universal: boolean;
    summary: string;
  };
  config: Record<string, Record<string, string>>;
  middleware: MiddlewareSurface[];
}

export interface CustomerCardProfile {
  id: string;
  customerId: string;
  type: "virtual" | "physical";
  brand: "visa" | "mastercard";
  lastFour: string;
  expiryDate: string;
  cardHolder: string;
  balance: number;
  isLocked: boolean;
  controls: {
    online: boolean;
    atm: boolean;
    international: boolean;
  };
  spendingLimits: {
    daily: number;
    atm: number;
    online: number;
  };
  colorTone: "blue" | "graphite";
  updatedAt: string;
}

export interface CustomerCardEvent {
  id: string;
  cardId: string;
  customerId: string;
  title: string;
  detail: string;
  severity: "info" | "warning" | "success";
  createdAt: string;
}

export interface CustomerBillPaymentRecord {
  id: string;
  customerId: string;
  category: "electricity" | "water" | "internet" | "school" | "airtime";
  provider: string;
  amount: number;
  status: "scheduled" | "paid" | "pending";
  paidAt: string;
  reference: string;
  billerId?: string;
  customerReference?: string;
  customerName?: string;
  scheduledFor?: string;
  evidenceStatus?: "verified" | "ready" | "scheduled";
  channel?: "self-service" | "saved-biller" | "operator-assisted";
}

export interface CustomerSavedBiller {
  id: string;
  customerId: string;
  category: CustomerBillPaymentRecord["category"];
  provider: string;
  billerId: string;
  customerReference: string;
  nickname: string;
  lastAmount: number;
  verifiedName?: string;
  lastPaidAt?: string;
  createdAt: string;
}

export interface CustomerStatementRecord {
  id: string;
  customerId: string;
  title: string;
  detail: string;
  amount: number;
  direction: "credit" | "debit";
  type: "transfer" | "bill_payment" | "workflow" | "deposit";
  status: "completed" | "pending" | "prepared";
  timestamp: string;
  reference?: string;
  category?: string;
}

export interface CustomerQrOverview {
  asOf: string;
  customerId: string;
  featureEnabled: boolean;
  serviceStatus: HealthStatus;
  settlementRoute: string;
  lastUsedAt?: string;
  supportedFlows: Array<{
    key: string;
    label: string;
    detail: string;
    route: string;
    status: "ready" | "gated" | "review";
  }>;
  complianceChecks: string[];
  recentAudit: AuditEntry[];
}

export interface CustomerTransferRecord {
  id: string;
  customerId: string;
  beneficiaryId?: string;
  beneficiaryName: string;
  amount: number;
  narration?: string;
  transferType: "bank" | "wallet" | "workflow";
  status: "draft" | "otp_pending" | "submitted" | "completed" | "failed";
  createdAt: string;
  bankCode?: string;
  bankName?: string;
  accountNumber?: string;
  accountName?: string;
  workflowId?: string;
  otpReference?: string;
  otpIssuedAt?: string;
  confirmedAt?: string;
  approvalState?: "not_required" | "pending_review" | "approved";
}

export interface CustomerTransferOtpRequest {
  transferId: string;
  otpReference: string;
  expiresAt: string;
  maskedDestination: string;
  previewCode?: string;
}

export interface CustomerTransferSubmission {
  customerId?: string;
  beneficiaryId?: string;
  beneficiaryName?: string;
  amount: number;
  narration?: string;
  transferType: CustomerTransferRecord["transferType"];
  bankCode?: string;
  bankName?: string;
  accountNumber?: string;
  accountName?: string;
  workflowId?: string;
}

export interface CustomerApprovalRequest {
  id: string;
  customerId: string;
  entityType: "card_control" | "scheduled_bill" | "statement_export";
  entityId: string;
  title: string;
  detail: string;
  route: string;
  state: "pending" | "approved" | "rejected";
  requestedAt: string;
  requestedByRole: OperatorRole | "customer";
  requestedById: string;
  approvalRole: OperatorRole;
  resolvedAt?: string;
  resolutionNote?: string;
}

export interface CustomerStatementExportRequest {
  customerId?: string;
  format?: "csv" | "xlsx";
  rowCount?: number;
  title?: string;
}

export interface CustomerStatementExportResponse {
  exportJob: ExportJob;
  approvalRequest?: CustomerApprovalRequest;
}

export interface StatementResponse {
  asOf: string;
  customerId: string;
  items: CustomerStatementRecord[];
  total: number;
}

export interface CustomerTransferResponse {
  asOf: string;
  customerId: string;
  items: CustomerTransferRecord[];
  total: number;
}

export interface CustomerApprovalResponse {
  asOf: string;
  customerId: string;
  items: CustomerApprovalRequest[];
  total: number;
}

export interface CustomerOtpConfirmation {
  otpReference: string;
  otpCode: string;
}

export interface CustomerBillApprovalPayload {
  approvalRole?: OperatorRole;
  resolutionNote?: string;
}

export interface CustomerCardApprovalPayload {
  approvalRole?: OperatorRole;
  resolutionNote?: string;
}

export interface CustomerTransferApprovalPayload {
  approvalRole?: OperatorRole;
  resolutionNote?: string;
}

export interface CustomerExportApprovalPayload {
  approvalRole?: OperatorRole;
  resolutionNote?: string;
}

export interface CustomerApprovalDecision {
  resolutionNote?: string;
}

export interface CustomerStatementExportListResponse {
  asOf: string;
  customerId: string;
  items: ExportJob[];
  total: number;
}

export interface CustomerStatementExportRequestListResponse {
  asOf: string;
  customerId: string;
  items: CustomerApprovalRequest[];
  total: number;
}

export interface CustomerServicingEnvelope<T> {
  asOf: string;
  customerId: string;
  items: T[];
  total: number;
}

export interface CustomerTransferOtpEnvelope {
  transfer: CustomerTransferRecord;
  otp: CustomerTransferOtpRequest;
}

export interface CustomerTransferConfirmationEnvelope {
  transfer: CustomerTransferRecord;
  statement: CustomerStatementRecord;
}

export interface CustomerApprovalDecisionEnvelope {
  approvalRequest: CustomerApprovalRequest;
}

export interface CustomerCardUpdateEnvelope {
  card: CustomerCardProfile;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerBillPaymentEnvelope {
  payment: CustomerBillPaymentRecord;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerStatementExportEnvelope {
  exportJob: ExportJob;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerTransferSubmissionEnvelope {
  transfer: CustomerTransferRecord;
}

export interface CustomerTransferOtpConfirmationEnvelope {
  transfer: CustomerTransferRecord;
  statement: CustomerStatementRecord;
}

export interface CustomerApprovalListEnvelope {
  asOf: string;
  customerId: string;
  items: CustomerApprovalRequest[];
  total: number;
}

export interface CustomerExportListEnvelope {
  asOf: string;
  customerId: string;
  items: ExportJob[];
  total: number;
}

export interface CustomerTransferListEnvelope {
  asOf: string;
  customerId: string;
  items: CustomerTransferRecord[];
  total: number;
}

export interface CustomerStatementListEnvelope {
  asOf: string;
  customerId: string;
  items: CustomerStatementRecord[];
  total: number;
}

export interface CustomerOtpEnvelope {
  transfer: CustomerTransferRecord;
  otp: CustomerTransferOtpRequest;
}

export interface CustomerDecisionEnvelope {
  approvalRequest: CustomerApprovalRequest;
}

export interface CustomerCardEnvelope {
  card: CustomerCardProfile;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerBillEnvelope {
  payment: CustomerBillPaymentRecord;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerExportEnvelope {
  exportJob: ExportJob;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerTransferEnvelope {
  transfer: CustomerTransferRecord;
}

export interface CustomerStatementEnvelope {
  statement: CustomerStatementRecord;
}

export interface CustomerOtpConfirmEnvelope {
  transfer: CustomerTransferRecord;
  statement: CustomerStatementRecord;
}

export interface CustomerApprovalEnvelope {
  approvalRequest: CustomerApprovalRequest;
}

export interface CustomerTransferQuery {
  customerId?: string;
}

export interface CustomerApprovalQuery {
  customerId?: string;
}

export interface CustomerStatementExportQuery {
  customerId?: string;
}

export interface CustomerStatementQuery {
  customerId?: string;
}

export interface CustomerCardQuery {
  customerId?: string;
}

export interface CustomerBillQuery {
  customerId?: string;
}

export interface CustomerBillerQuery {
  customerId?: string;
}

export interface CustomerCardEventQuery {
  customerId?: string;
}

export interface CustomerTransferOtpPayload {
  transferId: string;
}

export interface CustomerTransferCompletionPayload {
  otpReference: string;
  otpCode: string;
}

export interface CustomerApprovalResolvePayload {
  resolutionNote?: string;
}

export interface CustomerExportRequestPayload {
  customerId?: string;
  format?: "csv" | "xlsx";
  rowCount?: number;
  title?: string;
}

export interface CustomerTransferCreatePayload {
  customerId?: string;
  beneficiaryId?: string;
  beneficiaryName?: string;
  amount: number;
  narration?: string;
  transferType: CustomerTransferRecord["transferType"];
  bankCode?: string;
  bankName?: string;
  accountNumber?: string;
  accountName?: string;
  workflowId?: string;
}

export interface CustomerApprovalUpdatePayload {
  resolutionNote?: string;
}

export interface CustomerTransferRequestPayload extends CustomerTransferCreatePayload {}

export interface CustomerTransferConfirmationPayload {
  otpReference: string;
  otpCode: string;
}

export interface CustomerExportRequestApprovalPayload {
  resolutionNote?: string;
}

export interface CustomerSchedulingApprovalPayload {
  resolutionNote?: string;
}

export interface CustomerCardControlApprovalPayload {
  resolutionNote?: string;
}

export interface CustomerWorkflowApprovalPayload {
  resolutionNote?: string;
}

export interface CustomerTransferStatusEnvelope {
  transfer: CustomerTransferRecord;
}

export interface CustomerTransferHistoryResponse {
  asOf: string;
  customerId: string;
  items: CustomerTransferRecord[];
  total: number;
}

export interface CustomerApprovalHistoryResponse {
  asOf: string;
  customerId: string;
  items: CustomerApprovalRequest[];
  total: number;
}

export interface CustomerExportHistoryResponse {
  asOf: string;
  customerId: string;
  items: ExportJob[];
  total: number;
}

export interface CustomerStatementHistoryResponse {
  asOf: string;
  customerId: string;
  items: CustomerStatementRecord[];
  total: number;
}

export interface CustomerTransferOtpResponse {
  transfer: CustomerTransferRecord;
  otp: CustomerTransferOtpRequest;
}

export interface CustomerTransferConfirmResponse {
  transfer: CustomerTransferRecord;
  statement: CustomerStatementRecord;
}

export interface CustomerApprovalResolveResponse {
  approvalRequest: CustomerApprovalRequest;
}

export interface CustomerCardUpdateResponse {
  card: CustomerCardProfile;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerBillCreateResponse {
  payment: CustomerBillPaymentRecord;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerExportCreateResponse {
  exportJob: ExportJob;
  approvalRequest?: CustomerApprovalRequest;
}

export interface CustomerTransferCreateResponse {
  transfer: CustomerTransferRecord;
}

export interface CustomerServicingActionResponse {
  message?: string;
}

interface RequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | undefined>;
  role?: OperatorRole;
  actorId?: string;
  tenantId?: string;
}

const API_BASE_URL =
  (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "/api/platform";

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const base = path.startsWith("http") ? path : `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const url = new URL(base, window.location.origin);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
}

function buildRoleHeaders(role?: OperatorRole, actorId?: string, tenantId?: string) {
  return {
    ...(role ? { "X-Operator-Role": role } : {}),
    ...(actorId ? { "X-Actor-Id": actorId } : {}),
    ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
  };
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...buildRoleHeaders(options.role, options.actorId, options.tenantId),
    ...(options.headers ?? {}),
  };

  const response = await fetch(buildUrl(path, options.query), {
    ...options,
    headers,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getPlatformOverview(role?: OperatorRole): Promise<OverviewResponse> {
  return requestJson<OverviewResponse>("/overview", { role });
}

export async function getProductCatalog(): Promise<ProductCatalogResponse> {
  return requestJson<ProductCatalogResponse>("/products");
}

export async function getRoleProfiles() {
  return requestJson<{ asOf: string; items: RoleProfile[]; total: number }>("/roles");
}

export async function getAuthContext(role?: OperatorRole, actorId?: string, tenantId?: string) {
  return requestJson<AuthContextResponse>("/auth/context", { role, actorId, tenantId, query: { role, tenantId } });
}

export async function getTenantConfigurations() {
  return requestJson<{ asOf: string; items: TenantConfiguration[]; total: number }>("/tenants/configurations");
}

export async function getTigerBeetleIntegration() {
  return requestJson<TigerBeetleIntegrationResponse>("/integrations/tigerbeetle");
}

export async function getTellerOverview(): Promise<TellerOverviewResponse> {
  return requestJson<TellerOverviewResponse>("/teller/overview");
}

export async function getLedgerSyncOverview(): Promise<ReconciliationResponse> {
  return requestJson<ReconciliationResponse>("/reconciliation/overview");
}

export async function getERPNextOverview(): Promise<ERPNextResponse> {
  return requestJson<ERPNextResponse>("/erpnext/overview");
}

export interface DomainOverviewResponse {
  asOf: string;
  domain: ProductSurface | null;
  metrics: {
    openActions: number;
    pendingActions: number;
    signedExports: number;
    auditEvents: number;
  };
  actions: OperatorAction[];
  exports: ExportJob[];
  audits: AuditEntry[];
}

export async function getIslamicBankingOverview(): Promise<IslamicBankingResponse> {
  return requestJson<IslamicBankingResponse>("/islamic-banking/overview");
}

export async function getTradeFinanceOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/trade-finance/overview");
}

export async function getDisputesOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/disputes/overview");
}

export async function getAgriculturalInsuranceOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/agricultural-insurance/overview");
}

export async function getMortgageOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/mortgage/overview");
}

export async function getEducationLoansOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/education-loans/overview");
}

export async function getEsusuOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/esusu/overview");
}

export async function getVirtualAccountsOverview(): Promise<DomainOverviewResponse> {
  return requestJson<DomainOverviewResponse>("/virtual-accounts/overview");
}

export async function getCustomers(query?: { q?: string; segment?: string; status?: string }, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerRecord[]; total: number }>("/customers", { query, role });
}

export async function createCustomer(payload: Omit<CustomerRecord, "id" | "lastTouchpoint">, role?: OperatorRole) {
  return requestJson<CustomerRecord>("/customers", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function updateCustomer(customerId: string, payload: Partial<CustomerRecord>, role?: OperatorRole) {
  return requestJson<CustomerRecord>(`/customers/${customerId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    role,
  });
}

export async function deleteCustomer(customerId: string, role?: OperatorRole) {
  return requestJson<{ id: string; removed: boolean }>(`/customers/${customerId}`, {
    method: "DELETE",
    role,
  });
}

export interface CustomerBeneficiaryRecord {
  id: string;
  customerId: string;
  name: string;
  phone: string;
  location: string;
  addedAt: string;
  source: "customer" | "manual" | "workflow" | "transfer";
}

export interface CustomerNotificationRecord {
  id: string;
  customerId: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  read: boolean;
  createdAt: string;
  actionUrl?: string;
}

export interface CustomerSessionPreferenceRecord {
  actorId: string;
  actorRole: string;
  tenantId: string;
  activeCustomerId: string;
  createdAt: string;
  updatedAt: string;
}

export async function getCustomerSessionPreference(role?: OperatorRole, actorId?: string, tenantId?: string) {
  return requestJson<CustomerSessionPreferenceRecord | null>("/customer-servicing/session-preference", {
    role,
    actorId,
    tenantId,
    query: { tenantId },
  });
}

export async function updateCustomerSessionPreference(
  payload: Pick<CustomerSessionPreferenceRecord, "activeCustomerId">,
  role?: OperatorRole,
  actorId?: string,
  tenantId?: string,
) {
  return requestJson<CustomerSessionPreferenceRecord>("/customer-servicing/session-preference", {
    method: "PUT",
    body: JSON.stringify(payload),
    role,
    actorId,
    tenantId,
  });
}

export async function getCustomerBeneficiaries(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerBeneficiaryRecord[]; total: number }>("/customer-servicing/beneficiaries", {
    query: { customerId },
    role,
  });
}

export async function saveCustomerBeneficiary(payload: CustomerBeneficiaryRecord, role?: OperatorRole) {
  return requestJson<CustomerBeneficiaryRecord>("/customer-servicing/beneficiaries", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerNotifications(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerNotificationRecord[]; total: number }>("/customer-servicing/notifications", {
    query: { customerId },
    role,
  });
}

export async function updateCustomerNotification(notificationId: string, payload: Partial<CustomerNotificationRecord>, role?: OperatorRole) {
  return requestJson<CustomerNotificationRecord>(`/customer-servicing/notifications/${notificationId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    role,
  });
}

export async function createCustomerNotification(payload: CustomerNotificationRecord, role?: OperatorRole) {
  return requestJson<CustomerNotificationRecord>("/customer-servicing/notifications", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerCards(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerCardProfile[]; total: number }>("/customer-servicing/cards", {
    query: { customerId },
    role,
  });
}

export async function updateCustomerCard(cardId: string, payload: Partial<CustomerCardProfile>, role?: OperatorRole) {
  return requestJson<CustomerCardProfile>(`/customer-servicing/cards/${cardId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerCardEvents(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerCardEvent[]; total: number }>("/customer-servicing/card-events", {
    query: { customerId },
    role,
  });
}

export async function getSavedBillers(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerSavedBiller[]; total: number }>("/customer-servicing/billers", {
    query: { customerId },
    role,
  });
}

export async function saveCustomerBiller(payload: CustomerSavedBiller, role?: OperatorRole) {
  return requestJson<CustomerSavedBiller>("/customer-servicing/billers", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function deleteCustomerBiller(billerId: string, role?: OperatorRole) {
  return requestJson<{ id: string; removed: boolean }>(`/customer-servicing/billers/${billerId}`, {
    method: "DELETE",
    role,
  });
}

export async function getCustomerBillPayments(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerBillPaymentRecord[]; total: number }>("/customer-servicing/bills", {
    query: { customerId },
    role,
  });
}

export async function createCustomerBillPayment(payload: CustomerBillPaymentRecord, role?: OperatorRole) {
  return requestJson<CustomerBillPaymentRecord>("/customer-servicing/bills", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerStatements(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerStatementRecord[]; total: number }>("/customer-servicing/statements", {
    query: { customerId },
    role,
  });
}
export async function getCustomerQrOverview(customerId?: string, role?: OperatorRole) {
  return requestJson<CustomerQrOverview>("/customer-servicing/qr-overview", {
    query: { customerId },
    role,
  });
}
export async function getCustomerTransfers(customerId?: string, role?: OperatorRole) {

  return requestJson<{ asOf: string; items: CustomerTransferRecord[]; total: number }>("/customer-servicing/transfers", {
    query: { customerId },
    role,
  });
}

export async function createCustomerTransfer(payload: CustomerTransferCreatePayload, role?: OperatorRole) {
  return requestJson<CustomerTransferCreateResponse>("/customer-servicing/transfers", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function requestCustomerTransferOtp(transferId: string, role?: OperatorRole) {
  return requestJson<CustomerTransferOtpResponse>(`/customer-servicing/transfers/${transferId}/otp`, {
    method: "POST",
    body: JSON.stringify({ transferId }),
    role,
  });
}

export async function confirmCustomerTransferOtp(transferId: string, payload: CustomerTransferConfirmationPayload, role?: OperatorRole) {
  return requestJson<CustomerTransferConfirmResponse>(`/customer-servicing/transfers/${transferId}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerApprovalRequests(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: CustomerApprovalRequest[]; total: number }>("/customer-servicing/approvals", {
    query: { customerId },
    role,
  });
}

export async function approveCustomerApprovalRequest(approvalId: string, payload: CustomerApprovalResolvePayload = {}, role?: OperatorRole) {
  return requestJson<CustomerApprovalResolveResponse>(`/customer-servicing/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function rejectCustomerApprovalRequest(approvalId: string, payload: CustomerApprovalResolvePayload = {}, role?: OperatorRole) {
  return requestJson<CustomerApprovalResolveResponse>(`/customer-servicing/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function requestCustomerStatementExport(payload: CustomerExportRequestPayload, role?: OperatorRole) {
  return requestJson<CustomerExportCreateResponse>("/customer-servicing/statement-exports", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getCustomerStatementExports(customerId?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: ExportJob[]; total: number }>("/customer-servicing/statement-exports", {
    query: { customerId },
    role,
  });
}

export async function getWorkflowCases() {
  return requestJson<{ asOf: string; items: WorkflowCase[]; total: number }>("/workflows");
}

export async function advanceWorkflowCase(workflowId: string, role?: OperatorRole) {
  return requestJson<WorkflowCase>(`/workflows/${workflowId}/advance`, {
    method: "POST",
    body: JSON.stringify({}),
    role,
  });
}

export async function getOperatorActions(domainKey?: string, role?: OperatorRole) {
  return requestJson<{ asOf: string; items: OperatorAction[]; total: number }>("/actions", {
    query: { domainKey },
    role,
  });
}

export async function updateOperatorActionStatus(actionId: string, status?: OperatorActionState, role?: OperatorRole) {
  return requestJson<OperatorAction>(`/actions/${actionId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
    role,
  });
}

export async function getAuditEntries(role?: OperatorRole, domainKey?: string) {
  return requestJson<AuditResponse>("/audit", { role, query: { domainKey } });
}

export async function getExportJobs(role?: OperatorRole) {
  return requestJson<ExportResponse>("/exports", { role });
}

export async function createExportJob(
  payload: Pick<ExportJob, "domainKey" | "title" | "format" | "route"> &
    Partial<Pick<ExportJob, "rowCount" | "retainedUntil" | "reportVersion" | "approvalChain" | "signedBy">>,
  role?: OperatorRole,
) {
  return requestJson<ExportJob>("/exports", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getBillingDashboard() {
  return requestJson<BillingDashboardResponse>("/billing/dashboard");
}

export async function getBillingRateCards() {
  return requestJson<{ asOf: string; items: BillingRateCardRecord[]; total: number }>("/billing/rate-cards");
}

export async function createBillingRateCard(payload: {
  billingAccountId?: string;
  name: string;
  pricingCurrency?: string;
}) {
  return requestJson<BillingRateCardRecord>("/billing/rate-cards", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBillingUsageEvents() {
  return requestJson<{ asOf: string; items: BillingUsageEventRecord[]; total: number }>("/billing/usage-events");
}

export async function createBillingUsageEvent(payload: {
  idempotencyKey?: string;
  sourceService: string;
  sourceEventType: string;
  meterKey: string;
  productKey: string;
  quantity: number;
  unitAmount?: number;
  currency?: string;
  eventTimestamp?: string;
  correlationId?: string;
  resourceId?: string;
  payload?: Record<string, unknown>;
}) {
  return requestJson<BillingUsageEventRecord>("/billing/usage-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBillingAccruals() {
  return requestJson<{ asOf: string; items: BillingAccrualSnapshotRecord[]; total: number }>("/billing/accruals");
}

export async function getBillingInvoices() {
  return requestJson<{
    asOf: string;
    items: BillingInvoiceRecord[];
    lines: BillingInvoiceLineRecord[];
    approvals: BillingInvoiceApprovalRecord[];
    total: number;
  }>("/billing/invoices");
}

export async function generateBillingInvoices(payload: {
  billingAccountId?: string;
  periodType?: "monthly" | "quarterly" | "semi_annual" | "annual" | "custom";
}) {
  return requestJson<{
    asOf: string;
    invoices: BillingInvoiceRecord[];
    invoiceLines: BillingInvoiceLineRecord[];
    invoiceApprovals: BillingInvoiceApprovalRecord[];
    total: number;
  }>("/billing/invoices/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resolveBillingInvoiceApproval(
  invoiceId: string,
  approvalId: string,
  payload: { decision: "approve" | "reject"; note?: string },
  role: "operations" | "treasury" | "compliance" | "branch" = "operations",
) {
  return requestJson<BillingInvoiceRecord>(`/billing/invoices/${invoiceId}/approvals/${approvalId}`, {
    method: "POST",
    body: JSON.stringify(payload),
    role,
  });
}

export async function getBillingContractOverrides() {
  return requestJson<{ asOf: string; items: BillingContractOverrideRecord[]; total: number }>("/billing/contract-overrides");
}

export async function createBillingContractOverride(payload: {
  billingAccountId?: string;
  overrideType: "unit_price" | "included_units" | "minimum_commit" | "billing_model" | "billing_period";
  meterKey?: string;
  productKey?: string;
  valueNumber?: number;
  valueText?: string;
  effectiveFrom?: string;
  effectiveTo?: string;
  status?: "draft" | "active" | "expired";
  notes?: string;
}) {
  return requestJson<BillingContractOverrideRecord>("/billing/contract-overrides", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBillingDiscountRules() {
  return requestJson<{ asOf: string; items: BillingDiscountRuleRecord[]; total: number }>("/billing/discount-rules");
}

export async function createBillingDiscountRule(payload: {
  billingAccountId?: string;
  name: string;
  discountType: "percentage" | "fixed" | "threshold_percentage";
  meterKey?: string;
  productKey?: string;
  percentage?: number;
  fixedAmount?: number;
  thresholdAmount?: number;
  effectiveFrom?: string;
  effectiveTo?: string;
  status?: "draft" | "active" | "expired";
}) {
  return requestJson<BillingDiscountRuleRecord>("/billing/discount-rules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBillingRevenueShareRules() {
  return requestJson<{ asOf: string; items: BillingRevenueShareRuleRecord[]; total: number }>("/billing/revenue-share-rules");
}

export async function createBillingRevenueShareRule(payload: {
  billingAccountId?: string;
  name: string;
  target: "platform" | "partner_bank" | "aggregator" | "reseller";
  percentage: number;
  beneficiaryName: string;
  settlementLedgerCode?: string;
  effectiveFrom?: string;
  effectiveTo?: string;
  status?: "draft" | "active" | "expired";
}) {
  return requestJson<BillingRevenueShareRuleRecord>("/billing/revenue-share-rules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function searchPlatform(query: string) {
  return requestJson<{ asOf: string; items: SearchRecord[] }>("/search", {
    query: { q: query },
  });
}

export function formatCurrency(amount: number, currency = "NGN") {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatRelativeIso(iso?: string) {
  if (!iso) {
    return "Not yet recorded";
  }

  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) {
    return iso;
  }

  return value.toLocaleString("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export interface BillingApprovalMatrixRecord {
  id: string;
  tenantId: string;
  billingAccountId: string;
  name: string;
  status: "draft" | "active" | "retired";
  createdBy: string;
  createdAt: string;
  stages: Array<{
    stageKey: string;
    actorRole: "operations" | "treasury" | "compliance" | "branch";
    label: string;
    minimumAmount?: number;
    maximumAmount?: number;
    autoApprove?: boolean;
  }>;
}

export interface BillingInvoiceDisputeRecord {
  id: string;
  invoiceId: string;
  tenantId: string;
  status: "open" | "under_review" | "resolved" | "rejected";
  severity: "low" | "medium" | "high";
  reasonCode: "usage_dispute" | "pricing_dispute" | "tax_dispute" | "contract_dispute" | "duplicate_invoice";
  title: string;
  detail: string;
  openedBy: string;
  assignedRole: "operations" | "treasury" | "compliance" | "branch";
  openedAt: string;
  updatedAt: string;
  resolutionNote?: string;
}

export interface BillingErpPostingRecord {
  id: string;
  invoiceId: string;
  invoiceNumber: string;
  tenantId: string;
  status: "queued" | "posted" | "failed";
  erpSystem: "erpnext" | "lakehouse_finance";
  reference: string;
  payload: Record<string, unknown>;
  queuedAt: string;
  postedAt?: string;
  errorMessage?: string;
}

export interface BillingExtendedDashboardResponse extends BillingDashboardResponse {
  liveIngestion: {
    middleware: Array<"Kafka" | "Dapr" | "Redis" | "Fluvio" | "TigerBeetle" | "Lakehouse" | "APISIX" | "OpenAppSec">;
    lastIngestedAt?: string;
    serviceBreakdown: Array<{ sourceService: string; eventCount: number; quantity: number }>;
    meterBreakdown: Array<{ meterKey: string; productKey: string; eventCount: number; quantity: number }>;
  };
  disputes: BillingInvoiceDisputeRecord[];
  approvalMatrices: BillingApprovalMatrixRecord[];
  erpPostings: BillingErpPostingRecord[];
  controls: {
    overrideCount: number;
    discountRuleCount: number;
    revenueShareRuleCount: number;
    disputeCount: number;
    matrixCount: number;
    queuedErpPostings: number;
    issuedInvoices: number;
  };
}

export async function getBillingExtendedDashboard() {
  return requestJson<BillingExtendedDashboardResponse>("/billing/dashboard/extended");
}

export async function getBillingApprovalMatrices() {
  return requestJson<{ asOf: string; items: BillingApprovalMatrixRecord[]; total: number }>("/billing/approval-matrices");
}

export async function createBillingApprovalMatrix(payload: {
  tenantId?: string;
  billingAccountId?: string;
  name: string;
  status?: "draft" | "active" | "retired";
  stages: BillingApprovalMatrixRecord["stages"];
}) {
  return requestJson<BillingApprovalMatrixRecord>("/billing/approval-matrices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateBillingInvoicesAdvanced(payload: {
  billingAccountId?: string;
  periodType?: "monthly" | "quarterly" | "semi_annual" | "annual" | "custom";
}) {
  return requestJson<{
    asOf: string;
    invoices: BillingInvoiceRecord[];
    invoiceLines: BillingInvoiceLineRecord[];
    invoiceApprovals: BillingInvoiceApprovalRecord[];
    total: number;
  }>("/billing/invoices/generate-advanced", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBillingInvoiceExportUrl(invoiceId: string, format: "csv" | "json" | "html" = "json") {
  return `${API_BASE_URL}/billing/invoices/${invoiceId}/export?format=${format}`;
}

export async function getBillingErpPostings() {
  return requestJson<{ asOf: string; items: BillingErpPostingRecord[]; total: number }>("/billing/erp-postings");
}

export async function queueBillingInvoiceErpPost(invoiceId: string, payload?: { erpSystem?: "erpnext" | "lakehouse_finance" }) {
  return requestJson<BillingErpPostingRecord>(`/billing/invoices/${invoiceId}/erp-post`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export async function resolveBillingErpPosting(attemptId: string, payload: { status: "posted" | "failed"; errorMessage?: string }) {
  return requestJson<BillingErpPostingRecord>(`/billing/erp-postings/${attemptId}/resolve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBillingDisputes() {
  return requestJson<{ asOf: string; items: BillingInvoiceDisputeRecord[]; total: number }>("/billing/disputes");
}

export async function createBillingDispute(payload: {
  invoiceId: string;
  tenantId?: string;
  severity?: "low" | "medium" | "high";
  reasonCode?: "usage_dispute" | "pricing_dispute" | "tax_dispute" | "contract_dispute" | "duplicate_invoice";
  title: string;
  detail: string;
  assignedRole?: "operations" | "treasury" | "compliance" | "branch";
}) {
  return requestJson<BillingInvoiceDisputeRecord>("/billing/disputes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resolveBillingDispute(disputeId: string, payload: { status: "under_review" | "resolved" | "rejected"; resolutionNote?: string }) {
  return requestJson<BillingInvoiceDisputeRecord>(`/billing/disputes/${disputeId}/resolve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function ingestBillingUsageEvent(payload: {
  tenantId?: string;
  billingAccountId?: string;
  sourceService: string;
  sourceEventType: string;
  meterKey: string;
  productKey: string;
  quantity: number;
  currency?: string;
  actorId?: string;
  resourceId?: string;
  correlationId?: string;
  bridge?: "kafka" | "dapr" | "fluvio" | "tigerbeetle";
  payload?: Record<string, unknown>;
}) {
  return requestJson<BillingUsageEventRecord>("/billing/usage-events/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
