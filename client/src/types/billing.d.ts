// Global type declarations for billing pages
// These provide type safety across all billing-related pages

export interface BillingEntry {
  id: number;
  tenantId: string;
  transactionId: number;
  amount: string;
  currency: string;
  billingModelType: string;
  platformShare: string;
  clientShare: string;
  status: string;
  createdAt: Date;
}

export interface BillingAuditLog {
  id: number;
  userId: string;
  action: string;
  entityType: string;
  entityId: string;
  changes: Record<string, unknown>;
  ipAddress: string;
  createdAt: Date;
}

export interface TenantBillingConfig {
  id: number;
  tenantId: string;
  billingModel: string;
  revenueSharePercentage: string;
  subscriptionTier: string;
  monthlyFee: string;
  isActive: boolean;
  provisionedAt: Date;
}

export interface Invoice {
  id: number;
  tenantId: string;
  invoiceNumber: string;
  amount: string;
  currency: string;
  status: string;
  dueDate: Date;
  paidAt: Date | null;
  stripeInvoiceId: string | null;
}

export interface BillingPermission {
  userId: string;
  role: string;
  permissions: string[];
  tenantId: string;
}

export interface RevenueMetrics {
  totalRevenue: number;
  mrrGrowth: number;
  churnRate: number;
  ltv: number;
  arpu: number;
}

export interface CohortAnalytics {
  cohortId: string;
  month: string;
  retention: number;
  revenue: number;
  customers: number;
}

export interface DunningConfig {
  maxRetries: number;
  retryIntervalDays: number;
  gracePeriodDays: number;
  escalationEmail: string;
}

export interface BillingAlert {
  id: number;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  tenantId: string;
  acknowledged: boolean;
  createdAt: Date;
}
