export enum SupportedDatabaseTypes {
  MY_SQL = "mysql",
  POSTGRES = "postgres",
}

export enum BillingPlan {
  STANDARD = "standard",
  PREMIUM = "premium",
  ENTERPRISE = "enterprise",
}

export enum BillingStatus {
  ACTIVE = "ACTIVE",
  PAST_DUE = "PAST_DUE",
  SUSPENDED = "SUSPENDED",
}

export enum BillingCycleStatus {
  PAID = "PAID",
  RUNNING = "RUNNING",
  PENDING_PAYMENT = "PENDING_PAYMENT",
  PAST_DUE = "PAST_DUE",
}

export enum BillingModel {
  REVENUE_SHARE = "revenue_share",
  SUBSCRIPTION = "subscription",
  HYBRID = "hybrid",
}

export enum BillingRole {
  PLATFORM_ADMIN = "platform_admin",
  BILLING_ADMIN = "billing_admin",
  BILLING_ANALYST = "billing_analyst",
  BILLING_VIEWER = "billing_viewer",
}

export enum BillingAuditAction {
  PERMISSION_GRANTED = "permission_granted",
  PERMISSION_REVOKED = "permission_revoked",
  SPLIT_RECORDED = "split_recorded",
  CONFIG_CREATED = "config_created",
  CONFIG_UPDATED = "config_updated",
  CONFIG_DELETED = "config_deleted",
  RECONCILIATION_RUN = "reconciliation_run",
  GRACE_PERIOD_APPLIED = "grace_period_applied",
  DISPUTE_CREATED = "dispute_created",
  EXPORT_GENERATED = "export_generated",
  BILLING_MODEL_CHANGED = "billing_model_changed",
  TENANT_BILLING_PROVISIONED = "tenant_billing_provisioned",
  CONTRACT_RENEWED = "contract_renewed",
  BILLING_SUSPENDED = "billing_suspended",
  BILLING_REACTIVATED = "billing_reactivated",
  CONTRACT_TERMINATED = "contract_terminated",
  PLAN_MIGRATED = "plan_migrated",
  CREDIT_TOP_UP = "credit_top_up",
}

export enum ReconciliationStatus {
  PENDING = "pending",
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  FAILED = "failed",
}
