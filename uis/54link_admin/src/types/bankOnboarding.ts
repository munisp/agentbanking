export type BankTier = 'Basic' | 'Pro' | 'Enterprise';

export type BankFeature =
  // Core
  | 'auth' | 'user_management' | 'accounts' | 'payments' | 'reporting'
  | 'notifications' | 'kyc_kyb' | 'compliance' | 'audit'
  // Banking Channels
  | 'mobile_banking' | 'ussd_banking' | 'whatsapp_banking' | 'agent_banking'
  | 'chatbot' | 'pos_terminal'
  // Payments & Transfers
  | 'bill_payments' | 'qr_payments' | 'bulk_payments' | 'standing_orders'
  | 'remittance' | 'atm_management'
  // Cards & Accounts
  | 'teller' | 'card_management' | 'virtual_accounts' | 'fx'
  // Lending & Credit
  | 'loans' | 'education_loans' | 'mortgage' | 'lpo' | 'bnpl'
  // Savings & Investments
  | 'savings' | 'smart_savings' | 'esusu' | 'escrow' | 'investment'
  // Risk, Fraud & Compliance
  | 'fraud_detection' | 'risk_management' | 'dispute'
  | 'aml_compliance' | 'sanctions_screening' | 'regulatory_reporting'
  // Insurance
  | 'insurance' | 'etherisc'
  // Treasury & Finance
  | 'treasury' | 'chart_of_accounts' | 'reconciliation' | 'finance'
  // Specialised Finance
  | 'islamic_banking' | 'agriculture_finance' | 'supply_chain_finance'
  | 'trade_finance' | 'carbon_credits' | 'cooperative_management'
  | 'diaspora_banking' | 'microfinance'
  // Wealth & Capital Markets
  | 'wealth_management' | 'pension' | 'leasing' | 'securities_trading'
  // Operations & Workflow
  | 'employee_management' | 'relationship_manager' | 'document_management'
  | 'communication_hub' | 'merchant_management' | 'salary_processing'
  | 'maker_checker' | 'product_factory' | 'gamification'
  // Platform & Integration
  | 'open_banking' | 'biometric_auth' | 'developer_platform'
  | 'erp_integration' | 'temporal_access';

export interface BankOnboardingPayload {
  bankName: string;
  bankCode: string;
  tier: BankTier;
  contactEmail: string;
  contactPhone: string;
  cacDocument?: File | string | null;
  cbnLicense?: File | string | null;
  webhookUrl: string;
  callbackUrl: string;
  features?: BankFeature[];
}

export interface BankOnboardingRequest {
  bankName: string;
  bankCode: string;
  tier: BankTier;
  contactEmail: string;
  contactPhone: string;
  cacDocument?: string | null;
  cbnLicense?: string | null;
  webhookUrl: string;
  callbackUrl: string;
  features?: BankFeature[];
}

export interface BankOnboardingFormData {
  bankName: string;
  bankCode: string;
  tier: BankTier;
  contactEmail: string;
  contactPhone: string;
  cacDocument: File | null;
  cbnLicense: File | null;
  webhookUrl: string;
  callbackUrl: string;
  features: BankFeature[];
}

export interface BankOnboardingResponse {
  success: boolean;
  message: string;
  data: {
    bankId: string;
    apiKey: string;
    secretKey: string;
    bankName: string;
    bankCode: string;
    tier: BankTier;
    contactEmail: string;
    webhookUrl: string;
    callbackUrl: string;
    features: BankFeature[];
    createdAt: string;
    status: 'active' | 'pending' | 'suspended';
  };
}

export interface TierPricing {
  Basic: { monthlyFee: number; currency: string };
  Pro: { monthlyFee: number; currency: string };
  Enterprise: { monthlyFee: number; currency: string };
}

export const BANK_ONBOARDING_CONFIG = {
  tiers: ['Basic', 'Pro', 'Enterprise'] as const,
  defaultTier: 'Basic' as BankTier,

  tierPricing: {
    Basic: { monthlyFee: 500000, currency: 'NGN' },
    Pro: { monthlyFee: 2000000, currency: 'NGN' },
    Enterprise: { monthlyFee: 5000000, currency: 'NGN' },
  } as TierPricing,

  /** Features always included in all tiers */
  requiredFeatures: [
    'auth', 'user_management', 'accounts', 'payments', 'reporting',
    'notifications', 'kyc_kyb', 'compliance', 'audit', 'maker_checker',
  ] as BankFeature[],
} as const;

export function isBankTier(value: string): value is BankTier {
  return BANK_ONBOARDING_CONFIG.tiers.includes(value as BankTier);
}
