export enum SupportedDatabaseTypes {
  MY_SQL = "mysql",
  POSTGRES = "postgres",
}

export enum NotificationType {
  WELCOME_EMAIL = "welcome-email",
  SMS_OTP = "sms-otp",
  EMAIL_OTP = "email-otp",
  KYC = "kyc",
}

export enum NotificationCategory {
  EMAIL = "email",
  PUSH = "push",
  SMS = "sms",
}

export enum TenantFeatureFlag {
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

export enum BillingPlan {
  STANDARD = "standard",
  PREMIUM = "premium",
  ENTERPRISE = "enterprise",
}

export enum TenantType {
  BANK = "bank",
  MICROFINANCE = "microfinance",
  FINTECH = "fintech",
  INSURANCE = "insurance",
}

export enum CustomerRole {
  SUPERADMIN = "superadmin",
  ADMIN = "admin",
  AGENT = "agent",
  USER = "user",
  GUEST = "guest",
}

export enum TenantStatus {
  ACTIVE = "active",
  INACTIVE = "inactive",
  ONBOARDING = "onboarding",
  SUSPENDED = "suspended",
  DISABLED = "disabled",
}
