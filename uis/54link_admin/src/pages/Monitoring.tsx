import {
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  Search,
  Server,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTenantBranding } from "../contexts/TenantBrandingContext";
import { BACKEND_URL } from "../const";

interface ServiceHealth {
  appId: string;
  name: string;
  status: "healthy" | "unhealthy" | "checking";
  lastChecked?: Date;
  error?: string;
  category: string;
}

interface SmokeResult {
  service_name: string;
  status: "passed" | "failed" | "skipped";
  error_detail?: string;
  checked_at: string;
}

interface ServiceDef {
  appId: string;
  category: string;
  name?: string; // optional override; auto-derived from appId if omitted
}

const SMOKE_API = `${BACKEND_URL}/ops-dashboard/api/v1/ops/smoke-results`;

const toName = (appId: string) =>
  appId
    .replace(/-py$|-go$|-rs$/, "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

const smokeStatusToDisplay = (s: SmokeResult["status"]): ServiceHealth["status"] => {
  if (s === "passed") return "healthy";
  if (s === "failed") return "unhealthy";
  return "checking"; // skipped → status unknown
};

const SERVICES: ServiceDef[] = [
  // ── Core Platform ─────────────────────────────────────────────────────────
  { appId: "auth-service",              category: "Core Platform" },
  { appId: "admin-service",             category: "Core Platform" },
  { appId: "user-service",              category: "Core Platform" },
  { appId: "orchestrator-service",      category: "Core Platform" },
  { appId: "tenant-management",         category: "Core Platform" },
  { appId: "core-banking-go",           category: "Core Platform" },
  { appId: "billing",                   category: "Core Platform" },
  { appId: "it-admin-service",          category: "Core Platform" },
  { appId: "employee-service",          category: "Core Platform" },
  { appId: "notification-service",      category: "Core Platform" },
  { appId: "reporting-service",         category: "Core Platform" },
  { appId: "search-service",            category: "Core Platform" },
  // ── Banking Operations ────────────────────────────────────────────────────
  { appId: "account-service",           category: "Banking Operations" },
  { appId: "account-opening-go",        category: "Banking Operations" },
  { appId: "account-closure-go",        category: "Banking Operations" },
  { appId: "account-statement-go",      category: "Banking Operations" },
  { appId: "teller-service",            category: "Banking Operations" },
  { appId: "teller-operations-go",      category: "Banking Operations" },
  { appId: "branch-manager-service",    category: "Banking Operations" },
  { appId: "branch-operations-go",      category: "Banking Operations" },
  { appId: "treasury-service",          category: "Banking Operations" },
  { appId: "chart-of-accounts-service", category: "Banking Operations" },
  { appId: "virtual-account-service",   category: "Banking Operations" },
  { appId: "virtual-accounts-go",       category: "Banking Operations" },
  { appId: "cif-management-go",         category: "Banking Operations" },
  { appId: "finance-service",           category: "Banking Operations" },
  { appId: "gl-engine-go",              category: "Banking Operations" },
  { appId: "eod-processor-go",          category: "Banking Operations" },
  { appId: "reconciliation-service",    category: "Banking Operations" },
  { appId: "reconciliation-engine-rs",  category: "Banking Operations" },
  { appId: "ledger-reconciliation-rs",  category: "Banking Operations" },
  { appId: "transaction-ledger",        category: "Banking Operations" },
  { appId: "cash-pooling-go",           category: "Banking Operations" },
  { appId: "safe-deposit-go",           category: "Banking Operations" },
  { appId: "fixed-assets-go",           category: "Banking Operations" },
  { appId: "mandate-management-go",     category: "Banking Operations" },
  { appId: "locker-go",                 category: "Banking Operations" },
  { appId: "dormancy-management-rs",    category: "Banking Operations" },
  { appId: "banking-clearing-ops-rs",   category: "Banking Operations" },
  { appId: "multi-entity-go",           category: "Banking Operations" },
  { appId: "operations-control-gl-rs",  category: "Banking Operations" },
  { appId: "interest-accrual-engine-go",category: "Banking Operations" },
  { appId: "interest-computation-rs",   category: "Banking Operations" },
  { appId: "interest-rate-engine-go",   category: "Banking Operations" },
  { appId: "accounting-rules-rs",       category: "Banking Operations" },
  { appId: "gl-regulatory-pipeline-py", category: "Banking Operations" },
  // ── Payments & Transfers ──────────────────────────────────────────────────
  { appId: "payment-processing-service",category: "Payments & Transfers" },
  { appId: "payment-hub",               category: "Payments & Transfers" },
  { appId: "payment-investigation-go",  category: "Payments & Transfers" },
  { appId: "payment-rails-connectors",  category: "Payments & Transfers" },
  { appId: "bill-payment-service",      category: "Payments & Transfers" },
  { appId: "card-service",              category: "Payments & Transfers" },
  { appId: "card-management-go",        category: "Payments & Transfers" },
  { appId: "fx-service",                category: "Payments & Transfers" },
  { appId: "fx-rates-engine-rs",        category: "Payments & Transfers" },
  { appId: "qr-payments-go",            category: "Payments & Transfers" },
  { appId: "bulk-payments-rs",          category: "Payments & Transfers" },
  { appId: "standing-orders-go",        category: "Payments & Transfers" },
  { appId: "standing-charges-go",       category: "Payments & Transfers" },
  { appId: "remittance-go",             category: "Payments & Transfers" },
  { appId: "utility-payments-go",       category: "Payments & Transfers" },
  { appId: "atm-management-go",         category: "Payments & Transfers" },
  { appId: "cheque-clearing-go",        category: "Payments & Transfers" },
  { appId: "nibss-nip-engine-go",       category: "Payments & Transfers" },
  { appId: "nibss-direct-debit-go",     category: "Payments & Transfers" },
  { appId: "mojaloop-connector",        category: "Payments & Transfers" },
  { appId: "mojaloop-admin-go",         category: "Payments & Transfers" },
  { appId: "mojaloop-settlement-mgr-go",category: "Payments & Transfers" },
  { appId: "commission-settlement",     category: "Payments & Transfers" },
  { appId: "beneficiary-management-go", category: "Payments & Transfers" },
  { appId: "fee-management-go",         category: "Payments & Transfers" },
  { appId: "multicurrency-revaluation-rs",category: "Payments & Transfers"},
  { appId: "swift-messaging-go",        category: "Payments & Transfers" },
  { appId: "iso20022-hub-rs",           category: "Payments & Transfers" },
  { appId: "swift-iso20022-rs",         category: "Payments & Transfers" },
  { appId: "banking-domain-integration-go",category:"Payments & Transfers"},
  { appId: "interbank-lending-rs",      category: "Payments & Transfers" },
  { appId: "grid-token-card-go",        category: "Payments & Transfers" },
  // ── Loans & Credit ────────────────────────────────────────────────────────
  { appId: "loan-service",              category: "Loans & Credit" },
  { appId: "loan-origination-go",       category: "Loans & Credit" },
  { appId: "loan-calculator-go",        category: "Loans & Credit" },
  { appId: "lpo-service",               category: "Loans & Credit" },
  { appId: "education-loan-service",    category: "Loans & Credit" },
  { appId: "education-loans-py",        category: "Loans & Credit" },
  { appId: "mortgage-service",          category: "Loans & Credit" },
  { appId: "mortgage-servicing-rs",     category: "Loans & Credit" },
  { appId: "leasing-go",                category: "Loans & Credit" },
  { appId: "equipment-leasing-go",      category: "Loans & Credit" },
  { appId: "credit-facility-go",        category: "Loans & Credit" },
  { appId: "credit-bureau-rs",          category: "Loans & Credit" },
  { appId: "group-lending-go",          category: "Loans & Credit" },
  { appId: "factoring-go",              category: "Loans & Credit" },
  { appId: "bank-guarantees-go",        category: "Loans & Credit" },
  { appId: "syndicated-loans-go",       category: "Loans & Credit" },
  { appId: "acgsf-guarantee-go",        category: "Loans & Credit" },
  { appId: "nirsal-credit-guarantee-go",category: "Loans & Credit" },
  { appId: "debt-collection-go",        category: "Loans & Credit" },
  { appId: "collateral-valuation-rs",   category: "Loans & Credit" },
  { appId: "project-finance-go",        category: "Loans & Credit" },
  // ── Savings & Investments ─────────────────────────────────────────────────
  { appId: "savings-service",           category: "Savings & Investments" },
  { appId: "savings-products-go",       category: "Savings & Investments" },
  { appId: "savings-products-py",       category: "Savings & Investments" },
  { appId: "esusu-service",             category: "Savings & Investments" },
  { appId: "esusu-groups-go",           category: "Savings & Investments" },
  { appId: "escrow-service",            category: "Savings & Investments" },
  { appId: "escrow-go",                 category: "Savings & Investments" },
  { appId: "securities-trading-rs",     category: "Savings & Investments" },
  { appId: "portfolio-mgmt-rs",         category: "Savings & Investments" },
  { appId: "wealth-mgmt-py",            category: "Savings & Investments" },
  { appId: "pension-py",                category: "Savings & Investments" },
  { appId: "money-market-rs",           category: "Savings & Investments" },
  { appId: "etd-trading-rs",            category: "Savings & Investments" },
  { appId: "otc-derivatives-rs",        category: "Savings & Investments" },
  { appId: "trust-estate-rs",           category: "Savings & Investments" },
  { appId: "custody-service-go",        category: "Savings & Investments" },
  // ── Insurance ─────────────────────────────────────────────────────────────
  { appId: "insurance-service",         category: "Insurance" },
  { appId: "etherisc-service",          category: "Insurance" },
  { appId: "area-yield-index-insurance-py",category: "Insurance" },
  { appId: "livestock-insurance-rs",    category: "Insurance" },
  { appId: "multi-peril-crop-insurance-rs",category:"Insurance" },
  { appId: "insurance-portfolio-analytics-py",category:"Insurance" },
  { appId: "parametric-insurance-iot-rs",category: "Insurance" },
  // ── Risk, Fraud & AML ────────────────────────────────────────────────────
  { appId: "fraud-service",             category: "Risk, Fraud & AML" },
  { appId: "fraud-detection-rs",        category: "Risk, Fraud & AML" },
  { appId: "fraudfusion",               category: "Risk, Fraud & AML" },
  { appId: "fraudfusion-ensemble-rs",   category: "Risk, Fraud & AML" },
  { appId: "ai-fraud-scoring-rs",       category: "Risk, Fraud & AML" },
  { appId: "gnn-fraud-detection-py",    category: "Risk, Fraud & AML" },
  { appId: "risk-manager-service",      category: "Risk, Fraud & AML" },
  { appId: "risk-scoring-rs",           category: "Risk, Fraud & AML" },
  { appId: "risk-based-approach-py",    category: "Risk, Fraud & AML" },
  { appId: "mcmc-bayesian-risk-py",     category: "Risk, Fraud & AML" },
  { appId: "dispute-service",           category: "Risk, Fraud & AML" },
  { appId: "dispute-management-py",     category: "Risk, Fraud & AML" },
  { appId: "aml-engine-rs",             category: "Risk, Fraud & AML" },
  { appId: "aml-case-manager-go",       category: "Risk, Fraud & AML" },
  { appId: "aml-compliance-dashboard-py",category:"Risk, Fraud & AML" },
  { appId: "aml-risk-scoring-rs",       category: "Risk, Fraud & AML" },
  { appId: "aml-training-tracker-go",   category: "Risk, Fraud & AML" },
  { appId: "sanctions-screening-service",category:"Risk, Fraud & AML" },
  { appId: "sanctions-screening-rs",    category: "Risk, Fraud & AML" },
  { appId: "sanctions-engine-rs",       category: "Risk, Fraud & AML" },
  { appId: "sanctions-batch-rescreener-rs",category:"Risk, Fraud & AML"},
  { appId: "watchlist-manager-rs",      category: "Risk, Fraud & AML" },
  { appId: "wire-transfer-monitor-rs",  category: "Risk, Fraud & AML" },
  { appId: "anomaly-detector-py",       category: "Risk, Fraud & AML" },
  { appId: "typology-detector-rs",      category: "Risk, Fraud & AML" },
  { appId: "txn-monitoring-rules-rs",   category: "Risk, Fraud & AML" },
  { appId: "txn-pattern-analyzer-py",   category: "Risk, Fraud & AML" },
  { appId: "adverse-media-scanner-py",  category: "Risk, Fraud & AML" },
  { appId: "adverse-media-screening-py",category: "Risk, Fraud & AML" },
  { appId: "ctr-auto-filer-go",         category: "Risk, Fraud & AML" },
  { appId: "sar-filing-engine-go",      category: "Risk, Fraud & AML" },
  { appId: "goaml-integration-go",      category: "Risk, Fraud & AML" },
  { appId: "carbon-service",            category: "Risk, Fraud & AML" },
  // ── Audit & Compliance ────────────────────────────────────────────────────
  { appId: "audit-service",             category: "Audit & Compliance" },
  { appId: "compliance-service",        category: "Audit & Compliance" },
  { appId: "internal-auditor-service",  category: "Audit & Compliance" },
  { appId: "immutable-audit-rs",        category: "Audit & Compliance" },
  { appId: "corporate-monitoring-go",   category: "Audit & Compliance" },
  { appId: "cbn-service",               category: "Audit & Compliance" },
  { appId: "cbn-returns-py",            category: "Audit & Compliance" },
  { appId: "cbn-agsmeis-go",            category: "Audit & Compliance" },
  { appId: "cbn-anchor-borrowers-go",   category: "Audit & Compliance" },
  { appId: "cbn-compliance-checker-py", category: "Audit & Compliance" },
  { appId: "cbn-tiered-kyc-rs",         category: "Audit & Compliance" },
  { appId: "regulatory-reporting-go",   category: "Audit & Compliance" },
  { appId: "regulatory-reporting-py",   category: "Audit & Compliance" },
  { appId: "regulatory-automation-py",  category: "Audit & Compliance" },
  { appId: "regulatory-sandbox-go",     category: "Audit & Compliance" },
  { appId: "tax-reporting-py",          category: "Audit & Compliance" },
  { appId: "ndpr-compliance-py",        category: "Audit & Compliance" },
  { appId: "fatca-crs-rs",              category: "Audit & Compliance" },
  { appId: "nfiu-ctr-str-filing-py",    category: "Audit & Compliance" },
  { appId: "efass-kyc-returns-py",      category: "Audit & Compliance" },
  { appId: "efass-generator-rs",        category: "Audit & Compliance" },
  { appId: "ifrs9-engine-rs",           category: "Audit & Compliance" },
  { appId: "ifrs9-ecl-engine-rs",       category: "Audit & Compliance" },
  { appId: "lcr-nsfr-rs",               category: "Audit & Compliance" },
  { appId: "basel-engine-rs",           category: "Audit & Compliance" },
  { appId: "soc2-evidence-collector-py",category: "Audit & Compliance" },
  { appId: "pep-enhanced-dd-py",        category: "Audit & Compliance" },
  { appId: "beneficial-ownership-go",   category: "Audit & Compliance" },
  { appId: "ubo-service",               category: "Audit & Compliance" },
  { appId: "ubo-ownership-graph-rs",    category: "Audit & Compliance" },
  // ── KYC & Identity ───────────────────────────────────────────────────────
  { appId: "identity-verification-service",category:"KYC & Identity" },
  { appId: "identity-verification-go",  category: "KYC & Identity" },
  { appId: "kyb-service",               category: "KYC & Identity" },
  { appId: "kyb-engine-py",             category: "KYC & Identity" },
  { appId: "biometric-service",         category: "KYC & Identity" },
  { appId: "biometric-auth-rs",         category: "KYC & Identity" },
  { appId: "bvn-nin-verification-go",   category: "KYC & Identity" },
  { appId: "kyc-engine-py",             category: "KYC & Identity" },
  { appId: "kyc-aml-screening-py",      category: "KYC & Identity" },
  { appId: "kyc-analytics-dashboard-py",category: "KYC & Identity" },
  { appId: "kyc-data-quality-py",       category: "KYC & Identity" },
  { appId: "kyc-self-service-py",       category: "KYC & Identity" },
  { appId: "kyc-workflow-orchestration-py",category:"KYC & Identity" },
  { appId: "video-kyc-py",              category: "KYC & Identity" },
  { appId: "liveness-detection-rs",     category: "KYC & Identity" },
  { appId: "continuous-liveness-rs",    category: "KYC & Identity" },
  { appId: "face-match-rs",             category: "KYC & Identity" },
  { appId: "ocr-service",               category: "KYC & Identity" },
  { appId: "verification-service",      category: "KYC & Identity" },
  { appId: "address-verification-py",   category: "KYC & Identity" },
  { appId: "business-verification-service",category:"KYC & Identity" },
  { appId: "multi-bureau-verification-go",category:"KYC & Identity" },
  { appId: "cac-realtime-api-go",       category: "KYC & Identity" },
  { appId: "corporate-doc-verification-py",category:"KYC & Identity"},
  { appId: "customer-onboarding",       category: "KYC & Identity" },
  { appId: "agent-kyc-capture-go",      category: "KYC & Identity" },
  // ── Agricultural & Cooperative ────────────────────────────────────────────
  { appId: "agricultural-service",      category: "Agricultural & Cooperative" },
  { appId: "cooperative-management-go", category: "Agricultural & Cooperative" },
  { appId: "cooperative-meetings-go",   category: "Agricultural & Cooperative" },
  { appId: "cooperative-credit-scoring-py",category:"Agricultural & Cooperative"},
  { appId: "cooperative-financials-py", category: "Agricultural & Cooperative" },
  { appId: "agent-farmer-onboarding-go",category: "Agricultural & Cooperative" },
  { appId: "agent-banking-go",          category: "Agricultural & Cooperative" },
  { appId: "crop-yield-prediction-py",  category: "Agricultural & Cooperative" },
  { appId: "animal-id-traceability-rs", category: "Agricultural & Cooperative" },
  { appId: "livestock-management-rs",   category: "Agricultural & Cooperative" },
  { appId: "livestock-finance-rs",      category: "Agricultural & Cooperative" },
  { appId: "soil-analysis-py",          category: "Agricultural & Cooperative" },
  { appId: "satellite-crop-monitor-rs", category: "Agricultural & Cooperative" },
  { appId: "farm-boundary-mapping-rs",  category: "Agricultural & Cooperative" },
  { appId: "post-harvest-loss-tracker-go",category:"Agricultural & Cooperative"},
  { appId: "warehouse-management-go",   category: "Agricultural & Cooperative" },
  { appId: "quality-certification-go",  category: "Agricultural & Cooperative" },
  { appId: "fisheries-aquaculture-go",  category: "Agricultural & Cooperative" },
  { appId: "nirsal-agro-geocoop-go",    category: "Agricultural & Cooperative" },
  { appId: "cbn-agsmeis-go",            category: "Agricultural & Cooperative" },
  { appId: "inventory-py",              category: "Agricultural & Cooperative" },
  // ── Specialised Finance ───────────────────────────────────────────────────
  { appId: "islamic-banking-service",   category: "Specialised Finance" },
  { appId: "islamic-banking-py",        category: "Specialised Finance" },
  { appId: "microfinance-engine-go",    category: "Specialised Finance" },
  { appId: "microfinance-py",           category: "Specialised Finance" },
  { appId: "trade-finance-service",     category: "Specialised Finance" },
  { appId: "trade-finance-go",          category: "Specialised Finance" },
  { appId: "trade-finance-gl-go",       category: "Specialised Finance" },
  { appId: "supply-chain-service",      category: "Specialised Finance" },
  { appId: "supply-chain-finance-go",   category: "Specialised Finance" },
  { appId: "commodity-exchange-rs",     category: "Specialised Finance" },
  { appId: "commodity-price-intelligence-py",category:"Specialised Finance"},
  { appId: "diaspora-banking-py",       category: "Specialised Finance" },
  { appId: "enaira-cbdc-py",            category: "Specialised Finance" },
  { appId: "mojaloop-crossborder-py",   category: "Specialised Finance" },
  { appId: "realtime-pricing-rs",       category: "Specialised Finance" },
  // ── Customer & Engagement ────────────────────────────────────────────────
  { appId: "customer-360-py",           category: "Customer & Engagement" },
  { appId: "customer-360-dashboard-py", category: "Customer & Engagement" },
  { appId: "customer-insights-py",      category: "Customer & Engagement" },
  { appId: "customer-engagement-py",    category: "Customer & Engagement" },
  { appId: "customer-feedback-py",      category: "Customer & Engagement" },
  { appId: "relationship-manager-service",category:"Customer & Engagement"},
  { appId: "merchant-service",          category: "Customer & Engagement" },
  { appId: "communication-hub",         category: "Customer & Engagement" },
  { appId: "gamification-service",      category: "Customer & Engagement" },
  { appId: "salary-processing-go",      category: "Customer & Engagement" },
  { appId: "document-service",          category: "Customer & Engagement" },
  { appId: "document-management-py",    category: "Customer & Engagement" },
  { appId: "expense-mgmt-go",           category: "Customer & Engagement" },
  // ── Digital Channels ─────────────────────────────────────────────────────
  { appId: "ussd-service",              category: "Digital Channels" },
  { appId: "ussd-gateway-service",      category: "Digital Channels" },
  { appId: "ussd-banking-gateway-go",   category: "Digital Channels" },
  { appId: "ussd-multilingual-py",      category: "Digital Channels" },
  { appId: "ussd-transaction-engine-rs",category: "Digital Channels" },
  { appId: "chatbot-service",           category: "Digital Channels" },
  { appId: "chatbot-py",                category: "Digital Channels" },
  { appId: "sms-banking",               category: "Digital Channels" },
  { appId: "sms-notification-service",  category: "Digital Channels" },
  { appId: "sms-banking-gateway-go",    category: "Digital Channels" },
  { appId: "sms-email-gateway-go",      category: "Digital Channels" },
  { appId: "sms-service",               category: "Digital Channels" },
  { appId: "voice-banking-gateway-go",  category: "Digital Channels" },
  { appId: "voice-ivr-menu-go",         category: "Digital Channels" },
  { appId: "voice-nlu-banking-py",      category: "Digital Channels" },
  { appId: "voice-tts-nigerian-rs",     category: "Digital Channels" },
  { appId: "voice-asr-nigerian-py",     category: "Digital Channels" },
  { appId: "voice-agent-escalation-go", category: "Digital Channels" },
  { appId: "whatsapp-service",          category: "Digital Channels" },
  { appId: "whatsapp-cloud-api-go",     category: "Digital Channels" },
  { appId: "whatsapp-business-gateway-go",category:"Digital Channels" },
  { appId: "whatsapp-banking-flows-rs", category: "Digital Channels" },
  { appId: "whatsapp-payment-integration-go",category:"Digital Channels"},
  { appId: "telegram-service",          category: "Digital Channels" },
  { appId: "telegram-bot-gateway-go",   category: "Digital Channels" },
  { appId: "telegram-mini-app-go",      category: "Digital Channels" },
  { appId: "telegram-notification-py",  category: "Digital Channels" },
  { appId: "telegram-banking-commands-rs",category:"Digital Channels" },
  { appId: "pos-terminal-go",           category: "Digital Channels" },
  { appId: "mobile-bff",                category: "Digital Channels" },
  { appId: "mobile-sync-service",       category: "Digital Channels" },
  { appId: "mobile-offline-service",    category: "Digital Channels" },
  { appId: "stk-service",               category: "Digital Channels" },
  // ── AI & Analytics ───────────────────────────────────────────────────────
  { appId: "ml-service",                category: "AI & Analytics" },
  { appId: "analytics-engine-py",       category: "AI & Analytics" },
  { appId: "credit-scoring-py",         category: "AI & Analytics" },
  { appId: "kpi-engine-go",             category: "AI & Analytics" },
  { appId: "kpi-analytics-py",          category: "AI & Analytics" },
  { appId: "kpi-threshold-monitor-rs",  category: "AI & Analytics" },
  { appId: "opensearch-analytics-py",   category: "AI & Analytics" },
  { appId: "opensearch-indexer-py",     category: "AI & Analytics" },
  { appId: "opensearch-optimizer-py",   category: "AI & Analytics" },
  { appId: "ab-testing-py",             category: "AI & Analytics" },
  { appId: "data-intelligence",         category: "AI & Analytics" },
  { appId: "epr-kgqa-engine-py",        category: "AI & Analytics" },
  { appId: "cocoindex-pipeline-py",     category: "AI & Analytics" },
  { appId: "deepseek-local",            category: "AI & Analytics" },
  { appId: "ollama-inference-go",       category: "AI & Analytics" },
  { appId: "ml-security-service",       category: "AI & Analytics" },
  { appId: "docling-service",           category: "AI & Analytics" },
  // ── Developer Platform ───────────────────────────────────────────────────
  { appId: "developer-platform-service",category: "Developer Platform" },
  { appId: "developer-portal-go",       category: "Developer Platform" },
  { appId: "open-banking-go",           category: "Developer Platform" },
  { appId: "open-banking-baas-go",      category: "Developer Platform" },
  { appId: "api-analytics-py",          category: "Developer Platform" },
  { appId: "api-key-vault-go",          category: "Developer Platform" },
  { appId: "api-key-enforcer-go",       category: "Developer Platform" },
  { appId: "api-marketplace-go",        category: "Developer Platform" },
  { appId: "api-versioning-go",         category: "Developer Platform" },
  { appId: "api-metering",              category: "Developer Platform" },
  { appId: "graphql-gateway-go",        category: "Developer Platform" },
  { appId: "grpc-gateway-rs",           category: "Developer Platform" },
  { appId: "webhook-engine-go",         category: "Developer Platform" },
  { appId: "plugin-marketplace-py",     category: "Developer Platform" },
  { appId: "growth-features-go",        category: "Developer Platform" },
  { appId: "feature-entitlement-go",    category: "Developer Platform" },
  { appId: "feature-flag-engine-rs",    category: "Developer Platform" },
  { appId: "graduated-rollout-rs",      category: "Developer Platform" },
  // ── ERP & Integrations ───────────────────────────────────────────────────
  { appId: "erpnext-integration-service",category:"ERP & Integrations" },
  { appId: "erpnext-bridge-go",         category: "ERP & Integrations" },
  { appId: "erpnext-sync-py",           category: "ERP & Integrations" },
  { appId: "banking-operations-pipeline-py",category:"ERP & Integrations"},
  { appId: "aggregation-center-go",     category: "ERP & Integrations" },
  { appId: "batch-aggregator-go",       category: "ERP & Integrations" },
  { appId: "batch-processing-py",       category: "ERP & Integrations" },
  { appId: "event-bus-go",              category: "ERP & Integrations" },
  { appId: "event-streaming-go",        category: "ERP & Integrations" },
  { appId: "event-sourcing-go",         category: "ERP & Integrations" },
  { appId: "kafka-broker-go",           category: "ERP & Integrations" },
  { appId: "kafka-streaming-go",        category: "ERP & Integrations" },
  { appId: "kafka-schema-registry-go",  category: "ERP & Integrations" },
  { appId: "kafka-batch-producer-rs",   category: "ERP & Integrations" },
  { appId: "kafka-consumer-optimizer-go",category:"ERP & Integrations" },
  { appId: "kafka-lakehouse-connector", category: "ERP & Integrations" },
  { appId: "avro-schema-registry-go",   category: "ERP & Integrations" },
  { appId: "fluvio-streams-rs",         category: "ERP & Integrations" },
  { appId: "mojaloop-protocol-py",      category: "ERP & Integrations" },
  { appId: "mojaloop-tb-bridge-rs",     category: "ERP & Integrations" },
  { appId: "mojaloop-fspiop-callbacks-rs",category:"ERP & Integrations"},
  // ── Workflow & Operations ────────────────────────────────────────────────
  { appId: "approval-workflow-go",      category: "Workflow & Operations" },
  { appId: "maker-checker-go",          category: "Workflow & Operations" },
  { appId: "workflow-engine-py",        category: "Workflow & Operations" },
  { appId: "temporal-access-service",   category: "Workflow & Operations" },
  { appId: "temporal-orchestrator-py",  category: "Workflow & Operations" },
  { appId: "temporal-worker-go",        category: "Workflow & Operations" },
  { appId: "temporal-sagas-go",         category: "Workflow & Operations" },
  { appId: "saga-coordinator-py",       category: "Workflow & Operations" },
  { appId: "identity-channels-go",      category: "Workflow & Operations" },
  { appId: "mfa-orchestrator-go",       category: "Workflow & Operations" },
  { appId: "product-factory-rs",        category: "Workflow & Operations" },
  { appId: "notification-router-go",    category: "Workflow & Operations" },
  { appId: "notification-service-go",   category: "Workflow & Operations" },
  { appId: "realtime-notification-service",category:"Workflow & Operations"},
  { appId: "i18n-service-go",           category: "Workflow & Operations" },
  { appId: "exam-management-py",        category: "Workflow & Operations" },
  // ── Security ─────────────────────────────────────────────────────────────
  { appId: "security-service",          category: "Security" },
  { appId: "auth-enforcer-rs",          category: "Security" },
  { appId: "jwt-validator-rs",          category: "Security" },
  { appId: "keycloak-admin-go",         category: "Security" },
  { appId: "keycloak-enforcer-go",      category: "Security" },
  { appId: "keycloak-identity-py",      category: "Security" },
  { appId: "permify-authz-go",          category: "Security" },
  { appId: "otp-hardening-rs",          category: "Security" },
  { appId: "session-security-rs",       category: "Security" },
  { appId: "secrets-vault-go",          category: "Security" },
  { appId: "secrets-rotation-rs",       category: "Security" },
  { appId: "key-rotation-engine-go",    category: "Security" },
  { appId: "hsm-key-manager-rs",        category: "Security" },
  { appId: "vault-integration-rs",      category: "Security" },
  { appId: "cloud-kms-bridge-rs",       category: "Security" },
  { appId: "field-level-encryption-rs", category: "Security" },
  { appId: "pin-hasher-rs",             category: "Security" },
  { appId: "pin-block-engine-rs",       category: "Security" },
  { appId: "security-gateway-go",       category: "Security" },
  { appId: "security-hardening-go",     category: "Security" },
  { appId: "security-audit-logger-py",  category: "Security" },
  { appId: "platform-hardening-rs",     category: "Security" },
  { appId: "platform-security-infra-go",category: "Security" },
  { appId: "otel-collector-go",         category: "Security" },
  { appId: "incident-responder-go",     category: "Security" },
  { appId: "siem-exporter-py",          category: "Security" },
  { appId: "apm-sentry-py",             category: "Security" },
  { appId: "pci-scanner-rs",            category: "Security" },
  { appId: "ddos-protection-go",        category: "Security" },
  { appId: "ddos-shield-go",            category: "Security" },
  { appId: "openappsec-waf-rs",         category: "Security" },
  { appId: "waf-rules-engine-rs",       category: "Security" },
  { appId: "cors-gateway-go",           category: "Security" },
  { appId: "mtls-mesh-rs",              category: "Security" },
  { appId: "ip-allowlist-rs",           category: "Security" },
  { appId: "voice-biometric-auth-rs",   category: "Security" },
  { appId: "liveness-detection-rs",     category: "Security" },
  { appId: "signature-verification-rs", category: "Security" },
  { appId: "pkce-auth-flow-go",         category: "Security" },
  // ── Infrastructure ───────────────────────────────────────────────────────
  { appId: "tigerbeetle-adapter-rs",    category: "Infrastructure" },
  { appId: "tigerbeetle-ledger-rs",     category: "Infrastructure" },
  { appId: "tigerbeetle-batch-engine-rs",category:"Infrastructure" },
  { appId: "tigerbeetle-multicurrency-rs",category:"Infrastructure" },
  { appId: "tigerbeetle-protocol-rs",   category: "Infrastructure" },
  { appId: "tigerbeetle-sync-go",       category: "Infrastructure" },
  { appId: "tigerbeetle-postgres-sync", category: "Infrastructure" },
  { appId: "postgres-adapter-go",       category: "Infrastructure" },
  { appId: "redis-cache-rs",            category: "Infrastructure" },
  { appId: "redis-session-store-go",    category: "Infrastructure" },
  { appId: "hot-data-cache-rs",         category: "Infrastructure" },
  { appId: "bloom-filter-cache-rs",     category: "Infrastructure" },
  { appId: "cache-invalidation-rs",     category: "Infrastructure" },
  { appId: "lakehouse-rs",              category: "Infrastructure" },
  { appId: "lakehouse-etl-py",          category: "Infrastructure" },
  { appId: "data-export-rs",            category: "Infrastructure" },
  { appId: "dapr-sidecar-go",           category: "Infrastructure" },
  { appId: "backup-manager-py",         category: "Infrastructure" },
  { appId: "db-migration-manager-go",   category: "Infrastructure" },
  { appId: "connectivity-service",      category: "Infrastructure" },
  { appId: "idempotency-go",            category: "Infrastructure" },
];

type StatusFilter = "all" | "healthy" | "unhealthy" | "checking";

export default function Monitoring() {
  const { primaryColor, secondaryColor } = useTenantBranding();

  const [services, setServices] = useState<ServiceHealth[]>(
    SERVICES.map((s) => ({
      appId: s.appId,
      name: s.name ?? toName(s.appId),
      category: s.category,
      status: "checking" as const,
    })),
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filterStatus, setFilterStatus] = useState<StatusFilter>("all");
  const [filterCategory, setFilterCategory] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const categories = useMemo(
    () => Array.from(new Set(SERVICES.map((s) => s.category))),
    [],
  );

  const loadSmokeResults = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(SMOKE_API, { signal: AbortSignal.timeout(15000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: { results: SmokeResult[] } = await res.json();
      const byName: Record<string, SmokeResult> = {};
      for (const r of data.results ?? []) byName[r.service_name] = r;
      setServices(
        SERVICES.map((def) => {
          const r = byName[def.appId];
          return {
            appId: def.appId,
            name: def.name ?? toName(def.appId),
            category: def.category,
            status: r ? smokeStatusToDisplay(r.status) : "checking",
            lastChecked: r ? new Date(r.checked_at) : undefined,
            error: r?.status === "failed" ? r.error_detail : undefined,
          };
        }),
      );
    } catch {
      // keep existing state on error; spinner stops
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadSmokeResults();
    const interval = setInterval(loadSmokeResults, 300_000); // refresh every 5 min
    return () => clearInterval(interval);
  }, []);

  const healthyCount = services.filter((s) => s.status === "healthy").length;
  const unhealthyCount = services.filter((s) => s.status === "unhealthy").length;
  const checkingCount = services.filter((s) => s.status === "checking").length;
  const overallUptime =
    services.length > 0
      ? (((healthyCount + checkingCount) / services.length) * 100).toFixed(1)
      : "0.0";
  const allHealthy = unhealthyCount === 0 && checkingCount === 0;

  const filteredServices = useMemo(() => {
    return services.filter((s) => {
      const matchesStatus =
        filterStatus === "all" ||
        s.status === filterStatus;
      const matchesCategory =
        filterCategory === "all" || s.category === filterCategory;
      const matchesSearch =
        !searchTerm ||
        s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.appId.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesStatus && matchesCategory && matchesSearch;
    });
  }, [services, filterStatus, filterCategory, searchTerm]);

  const visibleCategories = useMemo(() => {
    const cats = new Set(filteredServices.map((s) => s.category));
    return categories.filter((c) => cats.has(c));
  }, [filteredServices, categories]);

  const getStatusColor = (status: ServiceHealth["status"]) => {
    if (status === "healthy") return "bg-green-500";
    if (status === "unhealthy") return "bg-red-500";
    return "bg-yellow-400";
  };

  const getStatusBadge = (status: ServiceHealth["status"]) => {
    if (status === "healthy")
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
    if (status === "unhealthy")
      return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
    return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300";
  };

  const statusFilterBtn = (val: StatusFilter, label: string, count: number) => {
    const active = filterStatus === val;
    return (
      <button
        onClick={() => setFilterStatus(val)}
        className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors border ${
          active
            ? "text-white border-transparent"
            : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"
        }`}
        style={active ? { backgroundColor: primaryColor, borderColor: primaryColor } : {}}
      >
        {label}
        <span
          className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${
            active ? "bg-white/25" : "bg-slate-100 dark:bg-slate-700"
          }`}
        >
          {count}
        </span>
      </button>
    );
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: `linear-gradient(to bottom right, ${primaryColor}12, ${secondaryColor}12)` }}
    >
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <Activity className="w-8 h-8" style={{ color: primaryColor }} />
            System Monitoring
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Daily smoke-test status for {services.length} deployed services
          </p>
        </div>
      </div>

      <div className="container py-8">
        {/* Overall status banner */}
        <div
          className={`rounded-xl shadow-lg p-6 mb-8 text-white ${
            unhealthyCount > 0 ? "bg-gradient-to-r from-red-500 to-red-600" : ""
          }`}
          style={
            allHealthy || checkingCount > 0
              ? { background: `linear-gradient(to right, ${secondaryColor}, ${primaryColor})` }
              : undefined
          }
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                {checkingCount > 0 ? (
                  <Loader2 className="w-8 h-8 animate-spin" />
                ) : allHealthy ? (
                  <CheckCircle className="w-8 h-8" />
                ) : (
                  <XCircle className="w-8 h-8" />
                )}
                <h2 className="text-2xl font-bold">
                  {checkingCount > 0
                    ? `Checking ${checkingCount} services…`
                    : allHealthy
                    ? "All Systems Operational"
                    : `${unhealthyCount} Service${unhealthyCount > 1 ? "s" : ""} Degraded`}
                </h2>
              </div>
              <p className="opacity-90">
                {healthyCount} healthy · {unhealthyCount} unhealthy · {checkingCount} checking
              </p>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold">{overallUptime}%</div>
              <div className="opacity-80 text-sm">availability</div>
              <button
                onClick={loadSmokeResults}
                disabled={isRefreshing}
                className="mt-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isRefreshing ? "Loading…" : "Refresh Now"}
              </button>
            </div>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Services", value: services.length, icon: Server, color: "purple" },
            { label: "Healthy",  value: healthyCount,   icon: CheckCircle, color: "green" },
            { label: "Unhealthy",value: unhealthyCount, icon: XCircle,     color: "red" },
            {
              label: "Last Run",
              value: (() => {
                const checked = services.filter((s) => s.lastChecked);
                if (checked.length === 0) return "—";
                const latest = checked.reduce((a, s) =>
                  s.lastChecked! > a.lastChecked! ? s : a
                );
                const d = latest.lastChecked!;
                return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
              })(),
              icon: Clock,
              color: "blue",
            },
          ].map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700"
            >
              <div className={`p-2 rounded-lg bg-${color}-100 dark:bg-${color}-900/30 w-fit mb-3`}>
                <Icon className={`w-5 h-5 text-${color}-600 dark:text-${color}-400`} />
              </div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white">{value}</div>
              <div className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search services…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2"
                style={{ "--tw-ring-color": primaryColor } as React.CSSProperties}
              />
            </div>

            {/* Status filter pills */}
            <div className="flex items-center gap-2 flex-wrap">
              {statusFilterBtn("all", "All", services.length)}
              {statusFilterBtn("healthy", "Healthy", healthyCount)}
              {statusFilterBtn("unhealthy", "Unhealthy", unhealthyCount)}
              {statusFilterBtn("checking", "Checking", checkingCount)}
            </div>

            {/* Category filter */}
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
            >
              <option value="all">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Result count */}
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
          Showing {filteredServices.length} of {services.length} services
        </p>

        {/* Service cards grouped by category */}
        {visibleCategories.map((category) => {
          const catServices = filteredServices.filter((s) => s.category === category);
          if (catServices.length === 0) return null;
          const catHealthy = catServices.filter((s) => s.status === "healthy").length;
          const catUnhealthy = catServices.filter((s) => s.status === "unhealthy").length;
          return (
            <div key={category} className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  <Server className="w-4 h-4" style={{ color: primaryColor }} />
                  {category}
                  <span className="text-xs font-normal text-slate-400 dark:text-slate-500">
                    ({catServices.length} services)
                  </span>
                </h2>
                <div className="flex items-center gap-2 text-xs">
                  {catHealthy > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 font-semibold">
                      {catHealthy} healthy
                    </span>
                  )}
                  {catUnhealthy > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 font-semibold">
                      {catUnhealthy} down
                    </span>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {catServices.map((service) => (
                  <div
                    key={service.appId}
                    className={`bg-white dark:bg-slate-800 rounded-xl p-4 border transition-shadow hover:shadow-md ${
                      service.status === "unhealthy"
                        ? "border-red-200 dark:border-red-900/50"
                        : "border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(service.status)} ${
                            service.status === "healthy" ? "animate-pulse" : ""
                          }`}
                        />
                        <h3 className="font-semibold text-slate-900 dark:text-white text-xs truncate">
                          {service.name}
                        </h3>
                      </div>
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ml-1 ${getStatusBadge(service.status)}`}>
                        {service.status === "checking" ? (
                          <span className="flex items-center gap-0.5">
                            <Loader2 className="w-2.5 h-2.5 animate-spin" />
                          </span>
                        ) : service.status}
                      </span>
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-400 dark:text-slate-500 mb-1.5">
                      <span>
                        {service.lastChecked
                          ? service.lastChecked.toLocaleDateString(undefined, { month: "short", day: "numeric" })
                          : "no data"}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 dark:text-slate-500 truncate">
                      {service.appId}
                    </div>
                    {service.error && (
                      <div className="mt-1.5 text-[10px] font-medium text-red-600 dark:text-red-400 truncate">
                        {service.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {filteredServices.length === 0 && (
          <div className="text-center py-20">
            <AlertCircle className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
            <p className="text-slate-500 dark:text-slate-400">No services match your filters.</p>
          </div>
        )}
      </div>
    </div>
  );
}
