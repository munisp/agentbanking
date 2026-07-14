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

const defaultProducts: ProductSurface[] = [
  {
    key: "customer-operations",
    title: "Customer operations",
    category: "operations",
    summary: "Customer onboarding, workflow progression, and relationship servicing across banking lines.",
    route: "/",
    status: "healthy",
    services: ["customer-service", "kyc-service", "search-service"],
  },
  {
    key: "teller-operations",
    title: "Teller operations",
    category: "operations",
    summary: "Branch sessions, till balancing, vault funding, and over-the-counter cash processing.",
    route: "/teller",
    status: "degraded",
    services: ["teller-service", "ledger-service", "reconciliation-service"],
  },
  {
    key: "islamic-banking",
    title: "Islamic banking",
    category: "retail",
    summary: "Murabaha, Ijara, and Mudarabah products with Sharia-compliant schedules and portfolio controls.",
    route: "/islamic-banking",
    status: "degraded",
    services: ["islamic-banking-service", "finance-service", "insurance-service"],
  },
  {
    key: "trade-finance",
    title: "Trade finance",
    category: "trade",
    summary: "Letters of credit, warehouse receipts, FX approval flows, and partner settlement readiness.",
    route: "/trade-finance",
    status: "healthy",
    services: ["trade-finance-service", "fx-service", "compliance-service"],
  },
  {
    key: "agricultural-insurance",
    title: "Agricultural insurance",
    category: "retail",
    summary: "Parametric crop cover, claims readiness, and rural risk controls across weather-linked programs.",
    route: "/agricultural-insurance",
    status: "degraded",
    services: ["agricultural-insurance-service", "insurance-service", "compliance-service"],
  },
  {
    key: "dispute-management",
    title: "Dispute management",
    category: "operations",
    summary: "Case intake, evidence review, reversal posture, and customer-remediation controls.",
    route: "/disputes",
    status: "degraded",
    services: ["dispute-service", "transfer-service", "merchant-service"],
  },
  {
    key: "erpnext-sync",
    title: "ERPNext sync",
    category: "partnerships",
    summary: "Accounting document mapping, outbound sync monitoring, and retry governance.",
    route: "/erpnext-sync",
    status: "degraded",
    services: ["erpnext-integration", "billing-service", "finance-service"],
  },
  {
    key: "ledger-reconciliation",
    title: "Ledger reconciliation",
    category: "treasury",
    summary: "TigerBeetle to PostgreSQL parity checks, discrepancy triage, and repair controls.",
    route: "/ledger-sync",
    status: "healthy",
    services: ["ledger-service", "reconciliation-service", "lakehouse-api"],
  },
];

const defaultRoleProfiles: RoleProfile[] = [
  {
    role: "branch",
    title: "Branch operations",
    description: "Frontline account servicing, teller balancing, and assisted onboarding.",
    defaultRoute: "/",
    permissions: ["customer.read", "customer.write", "workflow.advance", "teller.session.review"],
    visibleDomains: ["customer-operations", "teller-operations", "islamic-banking"],
    exportScopes: ["customers", "teller-sessions"],
  },
  {
    role: "operations",
    title: "Central operations",
    description: "Workflow management, dispute handling, ERPNext retries, and service coordination.",
    defaultRoute: "/",
    permissions: ["customer.read", "customer.write", "workflow.advance", "dispute.manage", "erpnext.retry"],
    visibleDomains: ["customer-operations", "dispute-management", "erpnext-sync", "trade-finance"],
    exportScopes: ["customers", "workflows", "actions", "disputes"],
  },
  {
    role: "treasury",
    title: "Treasury and ledger control",
    description: "TigerBeetle oversight, reconciliation, and settlement governance.",
    defaultRoute: "/ledger-sync",
    permissions: ["ledger.read", "ledger.reconcile", "settlement.review", "trade.approve"],
    visibleDomains: ["ledger-reconciliation", "trade-finance", "erpnext-sync"],
    exportScopes: ["ledger", "reconciliation", "trade-finance"],
  },
  {
    role: "compliance",
    title: "Compliance and risk",
    description: "KYC review, policy exceptions, insurance controls, and regulatory evidence trails.",
    defaultRoute: "/disputes",
    permissions: ["compliance.review", "workflow.block", "export.audit", "insurance.review", "customer.read"],
    visibleDomains: ["customer-operations", "agricultural-insurance", "dispute-management", "islamic-banking"],
    exportScopes: ["audit", "compliance", "insurance", "disputes"],
  },
];

const defaultTenantConfigurations: TenantConfiguration[] = [
  {
    tenantId: "54-retail",
    name: "Main Retail Bank",
    onboardingStatus: "active",
    segment: "retail",
    region: "Nigeria",
    enabledModules: ["customer-operations", "customer-servicing", "cards", "kyc", "payments", "disputes"],
    featureFlags: [
      {
        key: "digital_onboarding",
        label: "Digital onboarding",
        category: "onboarding",
        description: "Allow self-service onboarding journeys with risk and KYC review steps.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
        dependsOn: ["kyc_review", "tenant_branding"],
      },
      {
        key: "merchant_settlement",
        label: "Merchant settlement",
        category: "payments",
        description: "Enable merchant settlement routing and reconciliation workflows for this tenant.",
        enabled: true,
        rolloutStage: "controlled",
        adminManaged: true,
        dependsOn: ["ledger_sync"],
      },
      {
        key: "virtual_cards",
        label: "Virtual cards",
        category: "cards",
        description: "Expose instant virtual card issuance during onboarding and servicing.",
        enabled: true,
        rolloutStage: "controlled",
        adminManaged: true,
      },
      {
        key: "tenant_branding",
        label: "White-label branding",
        category: "platform",
        description: "Apply tenant-specific theme, logo, and custom domain settings across operator and customer surfaces.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
      },
      {
        key: "kyc_review",
        label: "KYC review queue",
        category: "compliance",
        description: "Route onboarding decisions through compliance review and evidence export controls.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
      },
    ],
    whiteLabel: {
      displayName: "54 Retail",
      legalEntity: "54link-dev Retail Operations Ltd.",
      supportEmail: "retail-ops@54link-dev.app",
      primaryColor: "#0f766e",
      accentColor: "#f59e0b",
      logoUrl: "https://assets.54link-dev.app/logos/54link-dev-retail.png",
      loginHeadline: "Retail banking experiences, branded per tenant.",
      customDomain: "retail.54link-dev.app",
    },
  },
  {
    tenantId: "54-ops",
    name: "Operations & Settlement Bank",
    onboardingStatus: "restricted",
    segment: "operations",
    region: "Pan-African operations",
    enabledModules: ["ledger-sync", "reconciliation", "erpnext-sync", "workflow-ops", "notifications"],
    featureFlags: [
      {
        key: "ops_onboarding",
        label: "Operations onboarding pack",
        category: "onboarding",
        description: "Enable operator-led onboarding packs for settlement and internal control teams.",
        enabled: true,
        rolloutStage: "controlled",
        adminManaged: true,
      },
      {
        key: "reconciliation_console",
        label: "Reconciliation console",
        category: "operations",
        description: "Provide tenant-specific reconciliation dashboards, workflows, and discrepancy actions.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
        dependsOn: ["ops_onboarding"],
      },
      {
        key: "erpnext_sync",
        label: "ERPNext sync",
        category: "platform",
        description: "Connect this tenant to accounting sync and retry governance surfaces.",
        enabled: true,
        rolloutStage: "controlled",
        adminManaged: true,
      },
      {
        key: "tenant_branding",
        label: "White-label branding",
        category: "platform",
        description: "Expose operator-shell branding, logo, and domain controls for the tenant.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
      },
    ],
    whiteLabel: {
      displayName: "54 Operations",
      legalEntity: "54link-dev Settlement Services Ltd.",
      supportEmail: "ops-control@54link-dev.app",
      primaryColor: "#1d4ed8",
      accentColor: "#22c55e",
      logoUrl: "https://assets.54link-dev.app/logos/54link-dev-ops.png",
      loginHeadline: "Settlement, treasury, and control workflows in one tenant shell.",
      customDomain: "ops.54link-dev.app",
    },
  },
  {
    tenantId: "54-growth",
    name: "Growth & Onboarding Programs",
    onboardingStatus: "draft",
    segment: "growth",
    region: "Expansion programs",
    enabledModules: ["onboarding", "campaigns", "kyc", "customer-operations"],
    featureFlags: [
      {
        key: "campaign_onboarding",
        label: "Campaign onboarding",
        category: "onboarding",
        description: "Allow growth teams to enable guided onboarding programs for partner channels.",
        enabled: true,
        rolloutStage: "pilot",
        adminManaged: true,
      },
      {
        key: "partner_referrals",
        label: "Partner referrals",
        category: "platform",
        description: "Enable referral and partner intake routes during onboarding.",
        enabled: false,
        rolloutStage: "pilot",
        adminManaged: true,
        dependsOn: ["campaign_onboarding"],
      },
      {
        key: "tenant_branding",
        label: "White-label branding",
        category: "platform",
        description: "Apply partner-specific branding, theme, and launch messaging.",
        enabled: true,
        rolloutStage: "controlled",
        adminManaged: true,
      },
      {
        key: "manual_review_gate",
        label: "Manual review gate",
        category: "compliance",
        description: "Require compliance approval before customers move from onboarding to active banking.",
        enabled: true,
        rolloutStage: "general",
        adminManaged: true,
      },
    ],
    whiteLabel: {
      displayName: "54 Growth",
      legalEntity: "54link-dev Growth Programs Ltd.",
      supportEmail: "growth-launch@54link-dev.app",
      primaryColor: "#7c3aed",
      accentColor: "#fb7185",
      logoUrl: "https://assets.54link-dev.app/logos/54link-dev-growth.png",
      loginHeadline: "Partner-led acquisition journeys with tenant-specific launch controls.",
      customDomain: "growth.54link-dev.app",
    },
  },
];

const defaultAuthContext: AuthContextResponse = {
  asOf: new Date().toISOString(),
  tenantId: defaultTenantConfigurations[0].tenantId,
  role: "operations",
  actorId: "operations.default",
  issuer: "http://keycloak:8080/realms/54link-dev",
  authzEndpoint: "http://permify:3476",
  gateway: "https://api.54link-dev.internal/gateway",
  permissions: defaultRoleProfiles[1].permissions,
  visibleDomains: defaultRoleProfiles[1].visibleDomains,
  exportScopes: defaultRoleProfiles[1].exportScopes,
  defaultRoute: defaultRoleProfiles[1].defaultRoute,
};

const fallbackTigerBeetle: TigerBeetleIntegrationResponse = {
  asOf: new Date().toISOString(),
  directIntegrationAssessment: {
    robust: true,
    universal: false,
    summary:
      "TigerBeetle is treated as a real ledger dependency for core money-movement and reconciliation domains, but not every service integrates directly with it.",
  },
  config: {
    tigerbeetle: { addresses: "tigerbeetle:3000", clusterId: "00000000000000000000000000000000" },
    kafka: { brokers: "kafka:9092" },
    temporal: { hostPort: "temporal-frontend:7233" },
    keycloak: { issuer: "http://keycloak:8080/realms/54link-dev" },
    permify: { endpoint: "http://permify:3476" },
    redis: { url: "redis://redis-master:6379/0" },
    apisix: { publicGatewayUrl: "https://api.54link-dev.internal/gateway" },
    mojaloop: { endpoint: "http://mojaloop-switch.default.svc.cluster.local:4000" },
    postgres: { url: "postgresql://app_user:54link-dev-postgres-secret@postgres-primary:5432/app_db?sslmode=require" },
    lakehouse: { endpoint: "http://lakehouse-query.default.svc.cluster.local:8000" },
    fluvio: { endpoint: "fluvio-sc-public:9003" },
    dapr: { httpPort: "3500" },
  },
  middleware: [
    {
      key: "tigerbeetle",
      title: "TigerBeetle ledger plane",
      status: "healthy",
      scope: "System of record for selected financial posting domains rather than every service.",
      languages: ["Go", "Python", "Rust-adjacent validators"],
      directlyIntegrated: true,
      notes: "Direct implementation is concentrated in ledger, reconciliation, billing, virtual accounts, mortgage, and education-loan flows.",
      services: ["ledger-service", "reconciliation-service", "virtual-account-service", "billing", "mortgage-service", "education-loan-service"],
    },
    {
      key: "kafka",
      title: "Kafka event backbone",
      status: "healthy",
      scope: "Ledger-adjacent domain events and downstream analytics fan-out.",
      languages: ["Go", "Python"],
      directlyIntegrated: true,
      notes: "Kafka should receive posting outcomes after TigerBeetle or reconciliation decisions.",
      services: ["payment-service", "customer-onboarding", "education-loan-service"],
    },
    {
      key: "temporal",
      title: "Temporal workflow plane",
      status: "healthy",
      scope: "Workflow orchestration for onboarding, payments, mortgage, and remediation.",
      languages: ["Go", "Python"],
      directlyIntegrated: false,
      notes: "Workflow activities should carry explicit ledger state instead of assuming success.",
      services: ["customer-onboarding", "payment-service", "mortgage-service", "workflows"],
    },
  ],
};

const fallbackAudit: AuditResponse = {
  asOf: new Date().toISOString(),
  role: "operations",
  total: 5,
  items: [
    {
      id: "AUD-955",
      timestamp: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
      actorRole: "compliance",
      actorId: "aml.engine",
      entityType: "aml_screening",
      entityId: "SCR-4891",
      action: "escalated",
      outcome: "High-risk PEP match flagged for enhanced due diligence — Alhaji Musa Danjuma, Kano State.",
      severity: "warning",
      route: "/aml-enhancement/sanctions-screening",
      middleware: ["OpenSearch", "Kafka", "Postgres", "Redis"],
      detail: "Automated sanctions screening matched a politically exposed person against the CBN watchlist. Case escalated to the AML compliance desk for manual review.",
    },
    {
      id: "AUD-954",
      timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      actorRole: "treasury",
      actorId: "treasury.lead",
      entityType: "fx_settlement",
      entityId: "FX-TXN-7823",
      action: "completed",
      outcome: "NGN/USD spot settlement completed — ₦1.2B @ ₦1,580/$ for Dangote Industries.",
      severity: "info",
      route: "/treasury/fx-deals",
      middleware: ["TigerBeetle", "Kafka", "Postgres", "Mojaloop"],
      detail: "Foreign exchange spot deal settled through the interbank market. TigerBeetle double-entry posted and Mojaloop corridor confirmation received.",
    },
    {
      id: "AUD-953",
      timestamp: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
      actorRole: "operations",
      actorId: "ops.supervisor",
      entityType: "loan_disbursement",
      entityId: "LOAN-DIS-3345",
      action: "approved",
      outcome: "Agricultural anchor borrower loan disbursed — ₦45M to Oyo Cooperative Farmers Union.",
      severity: "info",
      route: "/agriculture-banking/agri-loans",
      middleware: ["Temporal", "Postgres", "Kafka", "TigerBeetle"],
      detail: "CBN Anchor Borrowers Programme loan approved and disbursed via NIRSAL credit guarantee (75% CRG). Funds released to 120 cooperative members.",
    },
    {
      id: "AUD-952",
      timestamp: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
      actorRole: "compliance",
      actorId: "soc.analyst",
      entityType: "fraud_alert",
      entityId: "FRD-ALT-892",
      action: "blocked",
      outcome: "Suspicious card-not-present transaction blocked — ₦8.5M attempted from flagged IP (Lagos).",
      severity: "critical",
      route: "/risk-compliance/fraud-detection",
      middleware: ["Redis", "OpenAppSec", "APISIX", "Kafka"],
      detail: "Real-time fraud detection identified velocity anomaly — 12 transactions in 3 minutes from same card. Card frozen and customer notified via SMS.",
    },
    {
      id: "AUD-951",
      timestamp: new Date(Date.now() - 1000 * 60 * 48).toISOString(),
      actorRole: "operations",
      actorId: "kyc.processor",
      entityType: "kyc_verification",
      entityId: "KYC-VER-5567",
      action: "completed",
      outcome: "Tier 3 KYC upgrade completed for Sterling Microfinance Bank — BVN, NIN, CAC verified.",
      severity: "info",
      route: "/kyc-kyb/verification-queue",
      middleware: ["Keycloak", "Postgres", "Kafka", "OpenSearch"],
      detail: "Corporate KYB verification completed with BVN validation, NIN cross-check, and CAC registration. UBO chain verified to 3 levels. Risk score: Low.",
    },
  ],
};

const fallbackExports: ExportResponse = {
  asOf: new Date().toISOString(),
  role: "operations",
  total: 2,
  items: [
    {
      id: "EXP-201",
      domainKey: "ledger-reconciliation",
      title: "Ledger variance summary",
      format: "csv",
      status: "Ready",
      createdAt: new Date(Date.now() - 1000 * 60 * 70).toISOString(),
      requestedByRole: "treasury",
      route: "/ledger-sync",
      rowCount: 42,
      approvalState: "Signed",
      approvalSignature: "TREASURY-OPS-SIGNOFF",
      downloadUrl: "/api/platform/exports/EXP-201/download",
    },
    {
      id: "EXP-202",
      domainKey: "dispute-management",
      title: "Dispute case review pack",
      format: "json",
      status: "Ready",
      createdAt: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
      requestedByRole: "compliance",
      route: "/disputes",
      rowCount: 18,
      approvalState: "Signed",
      approvalSignature: "COMPLIANCE-LEGAL-SIGNOFF",
      downloadUrl: "/api/platform/exports/EXP-202/download",
    },
  ],
};

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

function fallbackOverview(): OverviewResponse {
  return {
    asOf: new Date().toISOString(),
    products: defaultProducts,
    metrics: [
      { label: "Active services", value: "18", detail: "Core banking, treasury, and operations domains observed", trend: "up" },
      { label: "Open control items", value: "7", detail: "Restoration work remaining across teller, ERPNext, and Islamic domains", trend: "down" },
      { label: "Ledger sync state", value: "Healthy with reviews", detail: "TigerBeetle reconciliation is live but still requires operator-driven healing", trend: "flat" },
      { label: "UI surface breadth", value: "Expanded", detail: "Broader products can now be routed from a unified shell instead of a single legacy homepage shell", trend: "up" },
    ],
    serviceHealth: [
      {
        name: "Customer service",
        route: "/",
        status: "healthy",
        latencyMs: 92,
        description: "Customer profile, workflow, note, and segment endpoints are reachable.",
        dependencies: ["PostgreSQL", "KYC service", "Search service"],
      },
      {
        name: "Teller service",
        route: "/teller",
        status: "degraded",
        latencyMs: 145,
        description: "Branch cash operations are being restored into a dedicated teller domain.",
        dependencies: ["Ledger service", "Account service", "Reconciliation service"],
      },
      {
        name: "ERPNext integration",
        route: "/erpnext-sync",
        status: "degraded",
        description: "Outbound accounting sync is under active restoration and validation.",
        dependencies: ["Billing service", "Finance service", "ERPNext tenant endpoint"],
      },
      {
        name: "Islamic banking service",
        route: "/islamic-banking",
        status: "degraded",
        description: "Murabaha, Ijara, and Mudarabah portfolio surfaces are being restored.",
        dependencies: ["Finance service", "Insurance service", "Compliance service"],
      },
      {
        name: "Reconciliation service",
        route: "/ledger-sync",
        status: "healthy",
        latencyMs: 108,
        description: "Sync snapshots, mismatch tracking, and reconciliation classification are available.",
        dependencies: ["TigerBeetle", "PostgreSQL", "Lakehouse API"],
      },
    ],
  };
}

function fallbackLedgerOutcome(domain: string): LedgerOutcomeSummary {
  const recommendedPostingSeams: Record<string, string[]> = {
    teller: ["cash transaction posting", "vault funding", "session balancing"],
    "islamic-banking": ["contract review", "approved exposure adjustment"],
    "ledger-sync": ["reconciliation repair", "discrepancy acknowledgement"],
    "erpnext-sync": ["post-reconciliation accounting confirmation"],
  };

  return {
    domain,
    source: "fallback",
    connected: false,
    tigerBeetlePosting: "not_connected",
    middleware: ["Postgres"],
    downstreamSinks: ["Postgres"],
    recommendedPostingSeams: recommendedPostingSeams[domain] ?? ["workflow confirmation", "final settlement boundary"],
    detail: `${domain} is currently using fallback posture until the upstream middleware path is available.`,
  };
}


function fallbackTeller(): TellerOverviewResponse {
  return {
    asOf: new Date().toISOString(),
    sessions: [],
    recentTransactions: [],
    summary: { sessionsUnderReview: 0, activeSessions: 0, cashOnTill: 0 },
    ledgerOutcome: fallbackLedgerOutcome("teller"),
  };
}

function fallbackReconciliation(): ReconciliationResponse {
  return {
    asOf: new Date().toISOString(),
    latestSnapshot: undefined,
    discrepancies: [],
    ledgerOutcome: fallbackLedgerOutcome("ledger-sync"),
  };
}

function fallbackERPNext(): ERPNextResponse {
  return {
    asOf: new Date().toISOString(),
    config: {
      enabled: false,
      mode: "unknown",
      mappedDocuments: [],
    },
    syncHistory: [],
    metrics: {},
    ledgerOutcome: fallbackLedgerOutcome("erpnext-sync"),
  };
}

function fallbackIslamic(): IslamicBankingResponse {
  return {
    asOf: new Date().toISOString(),
    summary: {
      activeContracts: 0,
      approvedExposure: 0,
      outstandingExposure: 0,
      delinquentContracts: 0,
      takafulCoverageRate: 0,
    },
    contracts: [],
    ledgerOutcome: fallbackLedgerOutcome("islamic-banking"),
  };
}

export async function getPlatformOverview(role?: OperatorRole): Promise<OverviewResponse> {
  try {
    return await requestJson<OverviewResponse>("/overview", { role });
  } catch {
    return fallbackOverview();
  }
}

export async function getProductCatalog(): Promise<ProductCatalogResponse> {
  try {
    return await requestJson<ProductCatalogResponse>("/products");
  } catch {
    return { asOf: new Date().toISOString(), products: defaultProducts };
  }
}

export async function getRoleProfiles() {
  try {
    return await requestJson<{ asOf: string; items: RoleProfile[]; total: number }>("/roles");
  } catch {
    return { asOf: new Date().toISOString(), items: defaultRoleProfiles, total: defaultRoleProfiles.length };
  }
}

export async function getAuthContext(role?: OperatorRole, actorId?: string, tenantId?: string) {
  try {
    return await requestJson<AuthContextResponse>("/auth/context", { role, actorId, tenantId, query: { role, tenantId } });
  } catch {
    const resolvedTenantId = tenantId || defaultAuthContext.tenantId;
    return {
      ...defaultAuthContext,
      asOf: new Date().toISOString(),
      tenantId: resolvedTenantId,
      role: role || defaultAuthContext.role,
      actorId: actorId || `${role || defaultAuthContext.role}.default`,
      permissions: defaultRoleProfiles.find((profile) => profile.role === (role || defaultAuthContext.role))?.permissions || defaultAuthContext.permissions,
      visibleDomains: defaultRoleProfiles.find((profile) => profile.role === (role || defaultAuthContext.role))?.visibleDomains || defaultAuthContext.visibleDomains,
      exportScopes: defaultRoleProfiles.find((profile) => profile.role === (role || defaultAuthContext.role))?.exportScopes || defaultAuthContext.exportScopes,
      defaultRoute: defaultRoleProfiles.find((profile) => profile.role === (role || defaultAuthContext.role))?.defaultRoute || defaultAuthContext.defaultRoute,
    };
  }
}

export async function getTenantConfigurations() {
  try {
    return await requestJson<{ asOf: string; items: TenantConfiguration[]; total: number }>("/tenants/configurations");
  } catch {
    return { asOf: new Date().toISOString(), items: defaultTenantConfigurations, total: defaultTenantConfigurations.length };
  }
}

export async function getTigerBeetleIntegration() {
  try {
    return await requestJson<TigerBeetleIntegrationResponse>("/integrations/tigerbeetle");
  } catch {
    return fallbackTigerBeetle;
  }
}

export async function getTellerOverview(): Promise<TellerOverviewResponse> {
  try {
    return await requestJson<TellerOverviewResponse>("/teller/overview");
  } catch {
    return fallbackTeller();
  }
}

export async function getLedgerSyncOverview(): Promise<ReconciliationResponse> {
  try {
    return await requestJson<ReconciliationResponse>("/reconciliation/overview");
  } catch {
    return fallbackReconciliation();
  }
}

export async function getERPNextOverview(): Promise<ERPNextResponse> {
  try {
    return await requestJson<ERPNextResponse>("/erpnext/overview");
  } catch {
    return fallbackERPNext();
  }
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
  try {
    return await requestJson<IslamicBankingResponse>("/islamic-banking/overview");
  } catch {
    return fallbackIslamic();
  }
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
  try {
    return await requestJson<AuditResponse>("/audit", { role, query: { domainKey } });
  } catch {
    return { ...fallbackAudit, role: role || fallbackAudit.role };
  }
}

export async function getExportJobs(role?: OperatorRole) {
  try {
    return await requestJson<ExportResponse>("/exports", { role });
  } catch {
    return { ...fallbackExports, role: role || fallbackExports.role };
  }
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
