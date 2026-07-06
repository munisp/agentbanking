export enum SupportedDatabaseTypes {
  MY_SQL = "mysql",
  POSTGRES = "postgres",
}

export enum TenantStatus {
  ACTIVE = "active",
  INACTIVE = "inactive",
  ONBOARDING = "onboarding",
  SUSPENDED = "suspended",
  DISABLED = "disabled",
}

export enum FeatureFlag {
  AUTH = "auth",
  USER_MANAGEMENT = "user_management",
  ACCOUNTS = "accounts",
  PAYMENTS = "payments",
  REPORTING = "reporting",
  NOTIFICATIONS = "notifications",
  LOANS = "loans",
  INSURANCE = "insurance",
  LPO = "lpo",
  CARBON_CREDITS = "carbon_credits",
  DISPUTE = "dispute",
  KYC_KYB = "kyc_kyb",
  EDUCATION_LOANS = "education_loans",
  ESUSU = "esusu",
  ESCROW = "escrow",
  MORTGAGE = "mortgage",
  SUPPLY_CHAIN_FINANCE = "supply_chain_finance",
  ETHERISC = "etherisc",
  AGRICULTURE_FINANCE = "agriculture_finance",
  FINANCE = "finance",
  COMPLIANCE = "compliance",
  SAVINGS = "savings",
  ISLAMIC_BANKING = "islamic_banking",
}

export enum OnboardingWorkflowStatus {
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum TenantType {
  BANK = "bank",
  MICROFINANCE = "microfinance",
  FINTECH = "fintech",
  INSURANCE = "insurance",
}

export enum BillingPlan {
  STANDARD = "standard",
  PREMIUM = "premium",
  ENTERPRISE = "enterprise",
}

export enum BillingPeriod {
  MONTHLY = "monthly",
  ANNUAL = "annual",
}

