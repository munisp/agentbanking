/**
 * Feature Flag Hook — Tenant-aware feature flag system.
 * Fetches the active tenant's enabled feature flags from the backend
 * and exposes helpers to check flag state for sidebar/route gating.
 */

import { useCallback, useEffect, useState } from "react";

export interface FeatureFlag {
  key: string;
  label: string;
  enabled: boolean;
  rolloutPct: number;
  category: string;
  tenantId: string;
}

interface FeatureFlagState {
  flags: FeatureFlag[];
  loading: boolean;
  tenantId: string;
  isEnabled: (flagKey: string) => boolean;
  refresh: () => void;
}

// Service catalog — maps sidebar paths to feature flag keys.
// If a path is NOT listed here, it is always visible (e.g. Dashboard, Settings).
export const SERVICE_CATALOG: Record<string, string> = {
  // Core Banking
  "/account-opening": "core_banking",
  "/customer-360": "core_banking",
  "/customer-onboarding": "core_banking",
  "/customer-segments": "core_banking",
  "/customer-engagement": "core_banking",
  "/customer-insights": "core_banking",
  "/customer-feedback": "core_banking",
  "/beneficiary-management": "core_banking",
  "/interest-rates": "core_banking",
  "/interest-accrual": "core_banking",
  "/fixed-deposits": "core_banking",
  "/savings-products": "core_banking",
  "/product-catalog": "core_banking",
  "/dormancy": "core_banking",
  "/standing-orders": "core_banking",
  "/standing-instructions": "core_banking",
  "/standing-charges": "core_banking",
  "/branch-operations": "core_banking",
  "/teller": "core_banking",
  "/atm-management": "core_banking",
  "/pos-terminals": "core_banking",
  "/channel-management": "core_banking",

  // Payments & Transfers
  "/transfers": "payments",
  "/payment-processing": "payments",
  "/payment-investigation": "payments",
  "/bulk-payments": "payments",
  "/utility-payments": "payments",
  "/bill-payments": "payments",
  "/direct-debit": "payments",
  "/mandate-management": "payments",
  "/collections": "payments",
  "/disbursements": "payments",
  "/nipss": "payments",

  // Cards & Digital
  "/cards": "cards_digital",
  "/card-management": "cards_digital",
  "/card-issuance": "cards_digital",
  "/virtual-cards": "cards_digital",
  "/mobile-money": "mobile_money",
  "/ussd-banking": "mobile_money",
  "/qr-payments": "cards_digital",
  "/wallet": "cards_digital",

  // Lending & Credit
  "/loan-management": "lending",
  "/loan-origination": "lending",
  "/loan-calculator": "lending",
  "/loan-recovery": "lending",
  "/credit-scoring": "lending",
  "/credit-bureau": "lending",
  "/collateral-management": "lending",
  "/education-loans": "lending",
  "/group-lending": "lending",
  "/leasing": "lending",
  "/mortgage-servicing": "lending",

  // Treasury & Markets
  "/treasury": "treasury",
  "/treasury-liquidity": "treasury",
  "/fx-rates": "treasury",
  "/fx-trading": "treasury",
  "/money-market": "treasury",
  "/otc-derivatives": "treasury",
  "/securities-trading": "treasury",
  "/cash-pooling": "treasury",

  // Trade & Structured Finance
  "/trade-finance": "trade_finance",
  "/letters-of-credit": "trade_finance",
  "/bank-guarantees": "trade_finance",
  "/trade-document-management": "trade_finance",
  "/project-finance": "trade_finance",
  "/swift-messaging": "trade_finance",
  "/iso20022": "trade_finance",
  "/escrow": "trade_finance",

  // Wealth & Investment
  "/wealth-management": "wealth_management",
  "/portfolio-management": "wealth_management",
  "/pension-management": "wealth_management",
  "/insurance": "wealth_management",

  // Accounting & GL
  "/general-ledger": "accounting",
  "/gl-engine": "accounting",
  "/chart-of-accounts": "accounting",
  "/accounting-rules": "accounting",
  "/account-statements": "accounting",
  "/eod-processing": "accounting",
  "/multicurrency-revaluation": "accounting",
  "/reconciliation": "accounting",
  "/statement-generator": "accounting",

  // Risk & Compliance
  "/risk-management": "risk_compliance",
  "/compliance-dashboard": "risk_compliance",
  "/regulatory-reporting": "risk_compliance",
  "/regulatory-automation": "risk_compliance",
  "/aml-screening": "risk_compliance",
  "/kyc-engine": "risk_compliance",
  "/kyb-engine": "risk_compliance",
  "/fraud-detection": "risk_compliance",
  "/sanctions-screening": "risk_compliance",
  "/suspicious-transaction-reporting": "risk_compliance",
  "/ifrs9-engine": "risk_compliance",
  "/lcr-nsfr": "risk_compliance",
  "/basel-engine": "risk_compliance",
  "/exam-management": "risk_compliance",

  // Agent & Specialty Banking
  "/agent-banking": "agent_banking",
  "/agent-banking-v2": "agent_banking",
  "/microfinance": "microfinance",
  "/microfinance-engine": "microfinance",
  "/islamic-banking": "islamic_banking",
  "/diaspora-banking": "diaspora_banking",
  "/esusu-groups": "cooperative_banking",

  // Agriculture Banking
  "/agricultural-loans": "agriculture_banking",
  "/crop-insurance": "agriculture_banking",
  "/agricultural-insurance": "agriculture_banking",
  "/farm-management": "agriculture_banking",
  "/cooperative-management": "agriculture_banking",
  "/commodity-trading": "agriculture_banking",
  "/warehouse-receipts": "agriculture_banking",
  "/farmer-registry": "agriculture_banking",
  "/harvest-financing": "agriculture_banking",
  "/livestock-management": "agriculture_banking",
  "/weather-data": "agriculture_banking",

  // Billing & Revenue
  "/billing-engine": "billing",
  "/billing-orchestrator": "billing",
  "/billing-rbac": "billing",
  "/billing-events": "billing",
  "/pricing-model": "billing",
  "/relationship-pricing": "billing",
  "/revenue-analysis": "billing",

  // Multi-Tenant Platform
  "/tenant-isolation": "multi_tenant",
  "/feature-flag-engine": "multi_tenant",
  "/white-label-engine": "multi_tenant",
  "/tenant-provisioning": "multi_tenant",
  "/graduated-rollout": "multi_tenant",
  "/custom-domains": "multi_tenant",
  "/metering": "multi_tenant",
  "/webhooks-engine": "multi_tenant",
  "/approval-workflows": "multi_tenant",
  "/plugin-marketplace": "multi_tenant",
  "/ab-testing": "multi_tenant",
};

// All available feature flag categories with display info
export const FLAG_CATEGORIES = [
  { key: "core_banking", label: "Core Banking", description: "Account opening, customer 360, deposits, branches, teller, ATM, POS" },
  { key: "payments", label: "Payments & Transfers", description: "Transfers, bulk payments, direct debit, collections, NIP/SS" },
  { key: "cards_digital", label: "Cards & Digital", description: "Card issuance, virtual cards, QR payments, wallets" },
  { key: "mobile_money", label: "Mobile Money & USSD", description: "Mobile money, USSD banking channels" },
  { key: "lending", label: "Lending & Credit", description: "Loans, credit scoring, collateral, group lending, leasing" },
  { key: "treasury", label: "Treasury & Markets", description: "FX, money market, securities, OTC derivatives, cash pooling" },
  { key: "trade_finance", label: "Trade & Structured Finance", description: "LC, bank guarantees, SWIFT, ISO 20022, escrow" },
  { key: "wealth_management", label: "Wealth & Investment", description: "Portfolio management, pension, insurance" },
  { key: "accounting", label: "Accounting & GL", description: "General ledger, chart of accounts, EOD, reconciliation" },
  { key: "risk_compliance", label: "Risk & Compliance", description: "AML, KYC, fraud, regulatory reporting, Basel, IFRS9" },
  { key: "agent_banking", label: "Agent Banking", description: "Agent network management, super agents, sub-agents" },
  { key: "microfinance", label: "Microfinance", description: "Microfinance groups, savings cycles, solidarity lending" },
  { key: "islamic_banking", label: "Islamic Banking", description: "Sharia-compliant products, murabaha, musharakah" },
  { key: "diaspora_banking", label: "Diaspora Banking", description: "Cross-border remittances, diaspora accounts" },
  { key: "cooperative_banking", label: "Cooperative Banking", description: "Esusu groups, cooperative societies, thrift savings" },
  { key: "agriculture_banking", label: "Agriculture Banking", description: "Farm loans, crop insurance, warehouse receipts, commodity trading" },
  { key: "billing", label: "Billing & Revenue", description: "Billing engine, pricing models, revenue sharing" },
  { key: "multi_tenant", label: "Multi-Tenant Platform", description: "Tenant management, feature flags, white labeling, plugins" },
] as const;

export function useFeatureFlags(): FeatureFlagState {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [tenantId, setTenantId] = useState("TEN-PLATFORM-ADMIN");

  const fetchFlags = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/feature-flag-engine/v1/tenant-flags");
      if (res.ok) {
        const data = await res.json();
        if (data.items) {
          setFlags(data.items);
          if (data.tenantId) setTenantId(data.tenantId);
        }
      } else {
        // Fallback: all flags enabled for platform admin
        setFlags(FLAG_CATEGORIES.map((cat) => ({
          key: cat.key,
          label: cat.label,
          enabled: true,
          rolloutPct: 100,
          category: cat.key,
          tenantId: "TEN-PLATFORM-ADMIN",
        })));
      }
    } catch {
      // Offline or unavailable: enable all for admin
      setFlags(FLAG_CATEGORIES.map((cat) => ({
        key: cat.key,
        label: cat.label,
        enabled: true,
        rolloutPct: 100,
        category: cat.key,
        tenantId: "TEN-PLATFORM-ADMIN",
      })));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchFlags();
  }, [fetchFlags]);

  const isEnabled = useCallback(
    (flagKey: string) => {
      // Platform admin always has all flags enabled
      if (tenantId === "TEN-PLATFORM-ADMIN") return true;
      const flag = flags.find((f) => f.key === flagKey);
      return flag ? flag.enabled : false;
    },
    [flags, tenantId],
  );

  return { flags, loading, tenantId, isEnabled, refresh: fetchFlags };
}
