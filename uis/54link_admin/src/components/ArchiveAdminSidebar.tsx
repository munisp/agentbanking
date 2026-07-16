// Design philosophy: extracted 54link-dev admin portal as canonical base.
// Sidebar organized into collapsible categories to manage 230+ pages.

import { useState } from "react";
import { Link, useLocation } from "wouter";
import { useFeatureFlags, SERVICE_CATALOG } from "@/hooks/useFeatureFlags";
import {
  Activity,
  Bell,
  Building2,
  CreditCard,
  FileBarChart,
  Calculator,
  Coins,
  FileText,
  Flag,
  Heart,
  LayoutDashboard,
  Link2,
  LogOut,
  MapPin,
  Menu,
  PiggyBank,
  Plus,
  Satellite,
  Settings,
  Shield,
  Tractor,
  TrendingUp,
  Users,
  Wheat,
  AlertTriangle,
  BarChart3,
  Handshake,
  X,
  Clock,
  Layers,
  UserPlus,
  BookOpen,
  Radio,
  GitBranch,
  Globe,
  Search,
  Database,
  Zap,
  Key,
  ArrowRightLeft,
  Landmark,
  Receipt,
  Send,
  AlertCircle,
  GitCompare,
  BellRing,
  Moon,
  Percent,
  Gauge,
  Lock,
  MessageSquare,
  ArrowLeftRight,
  Banknote,
  Package,
  PieChart,
  Mail,
  ShieldAlert,
  Download,
  Brain,
  Wallet,
  FileSearch,
  FolderOpen,
  Smartphone,
  Scale,
  Star,
  Sigma,
  ShieldCheck,
  QrCode,
  FileWarning,
  Fingerprint,
  Box,
  Building,
  Archive,
  FolderLock,
  ListChecks,
  ScrollText,
  PlayCircle,
  CheckSquare,
  DollarSign,
  BarChart2,
  ScanEye,
  ScanFace,
  Server,
  ToggleRight,
  Paintbrush,
  Rocket,
  MessageCircle,
  Factory,
  BarChart3 as BarChartIcon,
  Webhook,
  CheckCircle,
  Store,
  CircuitBoard,
  ShieldPlus,
  Cpu,
  ChevronDown,
  ChevronRight,
  WifiOff,
  Sparkles,
  Leaf,
  Code,
  Phone,
  Signal,
  RotateCcw,
  ArrowUpCircle,
  RefreshCw,
  LayoutGrid,
  Monitor,
  FileCheck,
  ArrowUpRight,
  Clipboard,
  Target,
  Upload,
  Network,
  Briefcase,
  GraduationCap,
  Crosshair,
  Award,
  BadgeCheck,
  Beaker,
  Bug,
  Calendar,
  CloudRain,
  Fish,
  Globe2,
  MapIcon,
  ScanLine,
  ShoppingCart,
  Ticket,
  Trash2,
  Truck,
  Umbrella,
  Warehouse,
  Hash,
  HeadphonesIcon,
  ListTree,
  Mic,
  Terminal,
  UserCheck,
  Volume2,
} from "lucide-react";

const Map = MapIcon;

type MenuItem = { path: string; label: string; icon: React.ElementType };

interface MenuCategory {
  category: string;
  icon: React.ElementType;
  items: MenuItem[];
}

const categorizedMenu: MenuCategory[] = [
  {
    category: "Overview",
    icon: LayoutDashboard,
    items: [
      { path: "/", label: "Dashboard", icon: LayoutDashboard },
      { path: "/control-center", label: "Control Center", icon: LayoutDashboard },
      { path: "/operations", label: "Operations Center", icon: Activity },
      { path: "/monitoring", label: "Monitoring", icon: Activity },
      { path: "/service-health", label: "Service Health", icon: Activity },
      { path: "/usage-analytics", label: "Usage Analytics", icon: BarChart3 },
      { path: "/analytics", label: "Analytics", icon: BarChart3 },
      { path: "/alerts", label: "Alerts", icon: Bell },
      { path: "/alert-settings", label: "Alert Settings", icon: Settings },
      { path: "/alert-rules", label: "Alert Rules", icon: Flag },
    ],
  },
  {
    category: "Core Banking",
    icon: Building2,
    items: [
      { path: "/banks", label: "Banks", icon: Building2 },
      { path: "/account-opening", label: "Account Opening", icon: UserPlus },
      { path: "/customer-360", label: "Customer 360", icon: Users },
      { path: "/customer-onboarding", label: "Onboarding", icon: UserPlus },
      { path: "/customer-segments", label: "Segments", icon: PieChart },
      { path: "/customer-engagement", label: "Engagement", icon: Heart },
      { path: "/customer-insights", label: "Insights", icon: Brain },
      { path: "/customer-feedback", label: "Feedback & NPS", icon: Star },
      { path: "/beneficiary-management", label: "Beneficiaries", icon: Users },
      { path: "/interest-rates", label: "Interest Rates", icon: TrendingUp },
      { path: "/interest-accrual", label: "Interest Accrual", icon: Percent },
      { path: "/fixed-deposits", label: "Fixed Deposits", icon: Landmark },
      { path: "/savings-products", label: "Savings Products", icon: PiggyBank },
      { path: "/product-catalog", label: "Product Catalog", icon: Package },
      { path: "/dormancy", label: "Dormancy", icon: Moon },
      { path: "/standing-orders", label: "Standing Orders", icon: Clock },
      { path: "/standing-instructions", label: "Standing Instructions", icon: Clock },
      { path: "/standing-charges", label: "Standing Charges", icon: ListChecks },
      { path: "/branch-operations", label: "Branch Ops", icon: Building2 },
      { path: "/teller", label: "Teller Ops", icon: Building2 },
      { path: "/atm-management", label: "ATM Management", icon: CreditCard },
      { path: "/pos-terminals", label: "POS Terminals", icon: Smartphone },
      { path: "/channel-management", label: "Channels", icon: Radio },
      { path: "/identity-channels", label: "Identity & Channels", icon: Settings },
    ],
  },
  {
    category: "Payments & Transfers",
    icon: ArrowRightLeft,
    items: [
      { path: "/payments-hub", label: "Payments Hub", icon: CreditCard },
      { path: "/payment-transactions", label: "Payment Txns", icon: ArrowRightLeft },
      { path: "/bulk-payments", label: "Bulk Payments", icon: Layers },
      { path: "/nibss-direct-debit", label: "NIBSS Direct Debit", icon: CreditCard },
      { path: "/cheque-clearing", label: "Cheque Clearing", icon: FileText },
      { path: "/cheque-imaging", label: "Cheque Imaging", icon: FileBarChart },
      { path: "/remittance", label: "Remittance", icon: Send },
      { path: "/utility-payments", label: "Utility Payments", icon: Zap },
      { path: "/qr-payments", label: "QR Payments", icon: QrCode },
      { path: "/salary-processing", label: "Salary Processing", icon: Wallet },
      { path: "/interbank-settlement", label: "Settlement", icon: ArrowLeftRight },
      { path: "/payment-investigation", label: "Payment Investigation", icon: Search },
      { path: "/swift-messages", label: "SWIFT Center", icon: Send },
      { path: "/iso20022-hub", label: "ISO 20022 Hub", icon: FileText },
      { path: "/batch-processing", label: "Batch Processing", icon: Layers },
      { path: "/mojaloop", label: "Mojaloop", icon: Globe },
      { path: "/swift-messaging", label: "SWIFT Messaging", icon: Send },
    ],
  },
  {
    category: "Cards & Digital",
    icon: CreditCard,
    items: [
      { path: "/card-management", label: "Card Management", icon: CreditCard },
      { path: "/card-management-v2", label: "Card Mgmt v2", icon: CreditCard },
      // { path: "/card-tokens", label: "Card Tokens", icon: Smartphone },
      { path: "/card-fraud-rules", label: "Card Fraud Rules", icon: ShieldAlert },
      { path: "/virtual-accounts", label: "Virtual Accounts", icon: Coins },
      { path: "/biometric-auth", label: "Biometric Auth", icon: Fingerprint },
      { path: "/signature-verification", label: "Signature Verification", icon: FileSearch },
      { path: "/open-banking", label: "Open Banking", icon: Globe },
      { path: "/api-marketplace", label: "API Marketplace", icon: Globe },
      { path: "/chatbot", label: "AI Chatbot", icon: MessageSquare },
      { path: "/growth-features", label: "Growth Features", icon: TrendingUp },
      { path: "/locker", label: "Digital Locker", icon: FolderLock },
    ],
  },
  {
    category: "Lending & Credit",
    icon: Landmark,
    items: [
      { path: "/loan-origination", label: "Loan Origination", icon: FileBarChart },
      { path: "/loan-products", label: "Loan Products", icon: Landmark },
      { path: "/loan-accounts", label: "Loan Accounts", icon: Receipt },
      { path: "/loan-calculator", label: "Loan Calculator", icon: Calculator },
      { path: "/credit-facilities", label: "Credit Facilities / ELCM", icon: CreditCard },
      { path: "/credit-risk", label: "Credit Risk", icon: AlertCircle },
      { path: "/credit-bureau", label: "Credit Bureau", icon: FileSearch },
      { path: "/collateral", label: "Collateral", icon: Lock },
      { path: "/collateral-valuation", label: "Collateral Valuation", icon: Scale },
      { path: "/group-lending", label: "Group Lending", icon: Users },
      { path: "/education-loans", label: "Education Loans", icon: FileText },
      { path: "/mortgage", label: "Mortgage Servicing", icon: Building2 },
      { path: "/microfinance", label: "Microfinance", icon: Heart },
      { path: "/esusu", label: "Esusu Groups", icon: Users },
      { path: "/syndicated-loans", label: "Syndicated Loans", icon: Users },
      { path: "/project-finance", label: "Project Finance", icon: Building2 },
      { path: "/leasing", label: "Leasing", icon: Package },
      { path: "/factoring", label: "Factoring", icon: Receipt },
      { path: "/mandate-management", label: "Mandate Management", icon: FileText },
    ],
  },
  {
    category: "Treasury & Markets",
    icon: TrendingUp,
    items: [
      { path: "/treasury", label: "Treasury & Liquidity", icon: TrendingUp },
      { path: "/treasury-liquidity", label: "Treasury Liquidity", icon: TrendingUp },
      { path: "/treasury-investments", label: "Treasury Investments", icon: Landmark },
      { path: "/fx-rates", label: "FX & Rates", icon: TrendingUp },
      { path: "/fx-dealing-room", label: "FX Dealing Room", icon: TrendingUp },
      { path: "/fx-positions", label: "FX Positions", icon: Coins },
      { path: "/fx-revaluation", label: "Multi-Currency Reval", icon: TrendingUp },
      { path: "/money-market", label: "Money Market", icon: Banknote },
      { path: "/securities-trading", label: "Securities Trading", icon: TrendingUp },
      { path: "/otc-derivatives", label: "OTC Derivatives", icon: Sigma },
      { path: "/etd-trading", label: "ETD Trading", icon: TrendingUp },
      { path: "/interbank-lending", label: "Interbank Lending", icon: ArrowLeftRight },
      { path: "/cash-management", label: "Cash & Liquidity", icon: Banknote },
      { path: "/cash-pooling", label: "Cash Pooling", icon: Layers },
      { path: "/correspondent-banking", label: "Correspondents", icon: Globe },
      { path: "/rate-cascade", label: "Rate Cascade Engine", icon: TrendingUp },
    ],
  },
  {
    category: "Trade & Structured Finance",
    icon: FileText,
    items: [
      { path: "/trade-finance", label: "Trade Finance", icon: FileText },
      { path: "/supply-chain-finance", label: "Supply Chain Finance", icon: Link2 },
      { path: "/bank-guarantees", label: "Bank Guarantees", icon: ShieldCheck },
      { path: "/contingent-liabilities", label: "Contingent Liabilities", icon: AlertTriangle },
      { path: "/lc-amendments", label: "LC Amendments", icon: FileText },
      { path: "/doc-collections", label: "Doc Collections", icon: FileText },
      { path: "/escrow", label: "Escrow", icon: Shield },
    ],
  },
  {
    category: "Wealth & Investment",
    icon: PieChart,
    items: [
      { path: "/wealth-mgmt", label: "Wealth Mgmt", icon: Landmark },
      { path: "/portfolio-mgmt", label: "Portfolio Mgmt", icon: PieChart },
      { path: "/custody-service", label: "Custody Services", icon: Lock },
      { path: "/trust-estate", label: "Trust & Estate", icon: ScrollText },
      { path: "/insurance", label: "Bancassurance", icon: ShieldCheck },
      { path: "/pension", label: "Pension", icon: Landmark },
      { path: "/safe-deposit", label: "Safe Deposit Box", icon: Box },
    ],
  },
  {
    category: "Accounting & GL",
    icon: BookOpen,
    items: [
      { path: "/ledger", label: "Ledger", icon: BookOpen },
      { path: "/gl-accounts", label: "General Ledger", icon: BookOpen },
      { path: "/chart-of-accounts", label: "Chart of Accounts", icon: BookOpen },
      { path: "/journal-entries", label: "Journal Entries", icon: FileText },
      { path: "/accounting-rules", label: "Accounting Rules", icon: BookOpen },
      { path: "/reconciliation", label: "Reconciliation", icon: GitCompare },
      { path: "/fee-schedules", label: "Fee Schedules", icon: Receipt },
      { path: "/ledger-sync", label: "Ledger Sync", icon: Link2 },
      { path: "/erpnext-sync", label: "ERPNext Sync", icon: FileBarChart },
      { path: "/fixed-assets", label: "Fixed Assets", icon: Building },
      { path: "/expense-mgmt", label: "Expense Mgmt", icon: Wallet },
      { path: "/inventory", label: "Inventory", icon: Archive },
      { path: "/eod-processor", label: "EOD/BOD Processing", icon: Clock },
      { path: "/account-statements", label: "Account Statements", icon: FileText },
      { path: "/statement-history", label: "Statement History", icon: FileBarChart },
      { path: "/statement-generator", label: "Statement Generator", icon: FileText },
      { path: "/gl-engine", label: "GL Engine", icon: BookOpen },
    ],
  },
  {
    category: "Risk & Compliance",
    icon: Shield,
    items: [
      { path: "/fraud-detection", label: "Fraud Detection", icon: Shield },
      { path: "/fraud-rules", label: "Fraud Rules", icon: Shield },
      { path: "/fraud-alerts", label: "Fraud Alerts", icon: AlertTriangle },
      { path: "/kyc-aml", label: "KYC/AML Screening", icon: Shield },
      { path: "/compliance-checks", label: "Compliance", icon: Shield },
      { path: "/regulatory-reporting", label: "CBN Reports", icon: FileText },
      { path: "/regulatory-calendar", label: "Reg Calendar", icon: Clock },
      { path: "/cbn-returns", label: "CBN Regulatory Returns", icon: FileText },
      { path: "/risk-scoring", label: "Risk Scoring", icon: ShieldAlert },
      { path: "/stress-testing", label: "Stress Testing", icon: Gauge },
      { path: "/watchlist-screening", label: "Watchlist Screening", icon: AlertTriangle },
      { path: "/sar-reports", label: "SAR Reports", icon: FileText },
      { path: "/pep-database", label: "PEP Database", icon: Shield },
      { path: "/fatca-crs", label: "FATCA/CRS", icon: FileWarning },
      { path: "/basel-engine", label: "Basel III/IV Engine", icon: Scale },
      { path: "/ifrs9-engine", label: "IFRS 9 Engine", icon: Calculator },
      { path: "/lcr-nsfr", label: "LCR / NSFR Calculator", icon: BarChart2 },
      { path: "/exam-management", label: "Regulatory Exams", icon: AlertTriangle },
      { path: "/audit-trail", label: "Audit Trail", icon: FileText },
      { path: "/disputes", label: "Disputes", icon: AlertTriangle },
      { path: "/complaints", label: "Complaints", icon: MessageSquare },
      { path: "/limit-management", label: "Limits", icon: Gauge },
      { path: "/security-hardening", label: "Security Hardening", icon: Shield },
      { path: "/ddos-protection", label: "DDoS Protection", icon: Shield },
      { path: "/pbac-engine", label: "PBAC Engine", icon: Shield },
      { path: "/regulatory-automation", label: "Regulatory Automation", icon: FileText },
    ],
  },
  {
    category: "KYC / KYB / Identity",
    icon: ScanEye,
    items: [
      { path: "/kyc-engine", label: "KYC Verification", icon: ScanEye },
      { path: "/kyb-engine", label: "KYB Company Verification", icon: Building2 },
      { path: "/liveness-detection", label: "Liveness Detection", icon: ShieldCheck },
      { path: "/face-match", label: "Face Match Engine", icon: ScanFace },
      { path: "/kyc-triggers", label: "KYC Admin Triggers", icon: PlayCircle },
      { path: "/kyb-triggers", label: "KYB Admin Triggers", icon: Building2 },
      { path: "/kyc-event-rules", label: "Event Rules", icon: Zap },
      { path: "/kyc-service-gates", label: "Service Gates", icon: ShieldCheck },
      { path: "/kyc-overrides", label: "Overrides", icon: ShieldAlert },
      { path: "/cif-management", label: "CIF / Address Mgmt", icon: Users },
      { path: "/kyc-tiered-dashboard", label: "CBN Tiered KYC", icon: ShieldCheck },
      { path: "/bvn-nin-verification", label: "BVN/NIN Verification", icon: ScanEye },
      { path: "/nfiu-ctr-str-filing", label: "NFIU CTR/STR Filing", icon: FileText },
      { path: "/sanctions-screening", label: "Sanctions Screening", icon: ShieldAlert },
      { path: "/cac-verification", label: "CAC Company Verify", icon: Building2 },
      { path: "/txn-monitoring-rules", label: "Transaction Monitoring", icon: Zap },
      { path: "/risk-based-approach", label: "Risk-Based Approach", icon: Shield },
      { path: "/pep-enhanced-dd", label: "PEP Enhanced DD", icon: Users },
      { path: "/ubo-ownership-graph", label: "UBO Ownership Graph", icon: Building2 },
      { path: "/multi-bureau-check", label: "Multi-Bureau Check", icon: FileText },
      { path: "/address-verification", label: "Address Verification", icon: MapPin },
      { path: "/corporate-doc-verify", label: "Corporate Doc Verify", icon: FileText },
      { path: "/kyc-analytics-dash", label: "KYC Analytics", icon: BarChart3 },
      { path: "/video-kyc", label: "Video KYC", icon: ScanEye },
      { path: "/continuous-liveness", label: "Continuous Liveness", icon: ShieldCheck },
      { path: "/kyc-workflow", label: "KYC Workflow Orchestration", icon: PlayCircle },
      { path: "/kyc-self-service", label: "Customer Self-Service", icon: Users },
      { path: "/agent-kyc-capture", label: "Agent KYC Capture", icon: MapPin },
      { path: "/adverse-media", label: "Adverse Media Screening", icon: FileText },
      { path: "/corporate-monitoring", label: "Corporate Monitoring", icon: Building2 },
      { path: "/kyc-data-quality", label: "KYC Data Quality", icon: Shield },
      { path: "/efass-kyc-returns", label: "CBN eFASS Returns", icon: FileText },
      { path: "/kyc-enhanced-summary", label: "KYC Enhanced Summary", icon: ScanEye },
    ],
  },
  {
    category: "Agent & Specialty Banking",
    icon: MapPin,
    items: [
      { path: "/agent-banking", label: "Agent Banking", icon: MapPin },
      { path: "/agent-banking-v2", label: "Agent Banking v2", icon: MapPin },
      { path: "/agent-performance", label: "Agent Performance", icon: Users },
      { path: "/diaspora-banking", label: "Diaspora Banking", icon: Globe },
      { path: "/islamic-banking", label: "Islamic Banking", icon: CreditCard },
      { path: "/murabaha-calculator", label: "Murabaha Calculator", icon: Calculator },
      { path: "/sukuk-management", label: "Sukuk Bonds", icon: Landmark },
      { path: "/takaful-management", label: "Takaful Insurance", icon: Heart },
      { path: "/wakala-investments", label: "Wakala Investments", icon: TrendingUp },
      { path: "/multi-entity", label: "Multi-Entity", icon: GitBranch },
      { path: "/branch-operations-2", label: "Branch Operations", icon: Building },
      { path: "/microfinance-engine", label: "Microfinance Engine", icon: Users },
    ],
  },
  {
    category: "Agriculture Banking",
    icon: Wheat,
    items: [
      { path: "/agriculture", label: "Agriculture", icon: Wheat },
      { path: "/agricultural-insurance", label: "Agri Insurance", icon: Wheat },
      { path: "/agriculture/farmers", label: "Farmers", icon: Users },
      { path: "/agriculture/loans", label: "Agri Loans", icon: Tractor },
      { path: "/agriculture/risk", label: "Risk Alerts", icon: AlertTriangle },
      { path: "/agriculture/agtech", label: "AgTech", icon: Satellite },
      { path: "/agriculture/value-chain", label: "Value Chain", icon: Link2 },
      { path: "/agriculture/regulatory", label: "Agri Compliance", icon: FileText },
      { path: "/agriculture/analytics", label: "Agri Analytics", icon: FileBarChart },
    ],
  },
  {
    category: "Billing & Revenue",
    icon: CircuitBoard,
    items: [
      { path: "/billing", label: "Billing", icon: CreditCard },
      { path: "/admin/billing-engine", label: "Billing Engine", icon: Coins },
      { path: "/pricing-model", label: "Pricing Model", icon: Calculator },
      { path: "/billing-orchestrator", label: "Billing Orchestrator", icon: CircuitBoard },
      { path: "/billing-rbac", label: "Billing RBAC", icon: ShieldPlus },
      { path: "/billing-event-processor", label: "Billing Events", icon: Cpu },
      { path: "/relationship-pricing", label: "Relationship Pricing", icon: DollarSign },
    ],
  },
  {
    category: "Multi-Tenant Platform",
    icon: Server,
    items: [
      { path: "/admin/onboarding", label: "Partner Onboarding", icon: Handshake },
      { path: "/service-catalog", label: "Service Catalog", icon: Package },
      { path: "/tenant-isolation", label: "Tenant Isolation", icon: Server },
      { path: "/feature-flag-engine", label: "Feature Flags", icon: ToggleRight },
      { path: "/features", label: "Feature Config", icon: Flag },
      { path: "/white-label-engine", label: "White Labeling", icon: Paintbrush },
      { path: "/white-label-config", label: "White Label Config", icon: Settings },
      { path: "/tenant-provisioning", label: "Tenant Provisioning", icon: Rocket },
      { path: "/branded-comms", label: "Branded Comms", icon: MessageCircle },
      { path: "/graduated-rollout", label: "Graduated Rollout", icon: Gauge },
      { path: "/custom-domains", label: "Custom Domains", icon: Globe },
      { path: "/tenant-metering", label: "Tenant Metering", icon: BarChartIcon },
      { path: "/webhook-engine", label: "Webhook Engine", icon: Webhook },
      { path: "/approval-workflows", label: "Approval Workflows", icon: CheckCircle },
      { path: "/plugin-marketplace", label: "Plugin Marketplace", icon: Store },
      { path: "/product-factory", label: "Product Factory", icon: Factory },
    ],
  },
  {
    category: "Infrastructure & Middleware",
    icon: Database,
    items: [
      { path: "/infra-postgres", label: "PostgreSQL", icon: Database },
      { path: "/infra-kafka", label: "Kafka Broker", icon: Activity },
      { path: "/infra-redis", label: "Redis Cache", icon: Zap },
      { path: "/infra-temporal", label: "Temporal Workflows", icon: GitBranch },
      { path: "/infra-opensearch", label: "OpenSearch", icon: Search },
      { path: "/infra-tigerbeetle", label: "TigerBeetle Ledger", icon: Shield },
      { path: "/infra-lakehouse", label: "Lakehouse ETL", icon: Database },
      { path: "/kafka-streaming", label: "Kafka Streaming", icon: Activity },
      { path: "/temporal-sagas", label: "Temporal Sagas", icon: GitBranch },
      { path: "/event-streaming", label: "Event Streaming", icon: Radio },
      { path: "/event-bus", label: "Event Bus", icon: Radio },
      { path: "/opensearch", label: "OpenSearch Analytics", icon: Search },
      { path: "/lakehouse", label: "Lakehouse", icon: Database },
      { path: "/fluvio-streams", label: "Fluvio Streams", icon: Zap },
      { path: "/dapr", label: "Dapr Mesh", icon: Layers },
      { path: "/permify", label: "Authorization (Permify)", icon: Shield },
      { path: "/keycloak", label: "Identity (Keycloak)", icon: Key },
      { path: "/db-admin", label: "Database Admin", icon: Database },
      { path: "/etl-pipelines", label: "ETL Pipelines", icon: Database },
      { path: "/offline-resilience", label: "Offline Resilience", icon: WifiOff },
    ],
  },
  {
    category: "Workflows & Operations",
    icon: GitBranch,
    items: [
      { path: "/workflow-engine", label: "Workflows", icon: GitBranch },
      { path: "/workflow-definitions", label: "Workflow Definitions", icon: GitBranch },
      { path: "/workflow-instances", label: "Workflow Instances", icon: PlayCircle },
      { path: "/maker-checker", label: "Maker-Checker Approvals", icon: CheckSquare },
      { path: "/notification-center", label: "Notifications", icon: Bell },
      { path: "/notification-preferences", label: "Notif Preferences", icon: BellRing },
      { path: "/messaging-gateway", label: "Messaging Gateway", icon: Mail },
      { path: "/webhook-subscriptions", label: "Webhooks", icon: Radio },
      { path: "/webhook-deliveries", label: "Webhook Deliveries", icon: Zap },
      { path: "/staff-management", label: "Staff", icon: Users },
      { path: "/document-management", label: "Documents", icon: FolderOpen },
      { path: "/data-export", label: "Data Export", icon: Download },
      { path: "/my-transactions", label: "My Transactions", icon: Receipt },
      { path: "/reporting", label: "Reports", icon: FileBarChart },
    ],
  },
  {
    category: "Dev & Testing",
    icon: Activity,
    items: [
      { path: "/integration-tests", label: "Integration Tests", icon: Activity },
      { path: "/seed-registry", label: "Seed Registry", icon: Database },
      { path: "/e2e-tests", label: "E2E Test Suite", icon: Activity },
      { path: "/load-testing", label: "Load Testing", icon: Gauge },
    ],
  },
  {
    category: "Production Infrastructure",
    icon: Server,
    items: [
      { path: "/database-persistence", label: "Database Persistence", icon: Database },
      { path: "/kafka-event-bus", label: "Kafka Event Bus", icon: Radio },
      { path: "/jwt-auth", label: "JWT Auth Enforcement", icon: Key },
      { path: "/tigerbeetle-ledger", label: "TigerBeetle Ledger", icon: Shield },
      { path: "/rate-limiting", label: "API Rate Limiting", icon: Gauge },
      { path: "/disaster-recovery", label: "Disaster Recovery", icon: ShieldCheck },
      { path: "/batch-eod", label: "Batch / EOD Engine", icon: Clock },
      { path: "/notifications-engine", label: "Notifications Engine", icon: Bell },
      { path: "/maker-checker", label: "Maker-Checker Engine", icon: CheckSquare },
      { path: "/report-generation", label: "Report Generation", icon: FileBarChart },
      { path: "/audit-trail", label: "Immutable Audit Trail", icon: FileText },
      { path: "/document-management", label: "Document Mgmt / OCR", icon: FolderOpen },
    ],
  },
  {
    category: "Innovation & Open Banking",
    icon: Sparkles,
    items: [
      { path: "/multi-currency-fx", label: "Multi-Currency FX", icon: DollarSign },
      { path: "/ai-fraud-detection", label: "AI Fraud Detection", icon: Brain },
      { path: "/open-banking", label: "Open Banking API", icon: Globe },
      { path: "/enaira-cbdc", label: "eNaira CBDC", icon: Banknote },
      { path: "/esg-banking", label: "ESG / Carbon Credits", icon: Leaf },
      { path: "/embedded-finance", label: "Embedded Finance SDK", icon: Code },
    ],
  },
  {
    category: "Security & Resilience",
    icon: ShieldAlert,
    items: [
      { path: "/ransomware-protection", label: "Ransomware Protection", icon: ShieldAlert },
      { path: "/resilience-dashboard", label: "Resilience Dashboard", icon: Activity },
      { path: "/ussd-banking", label: "USSD Banking", icon: Phone },
      { path: "/sms-banking", label: "SMS Banking", icon: MessageSquare },
      { path: "/offline-transactions", label: "Offline Transactions", icon: WifiOff },
      { path: "/bandwidth-adaptation", label: "Bandwidth Adaptation", icon: Signal },
    ],
  },
  {
    category: "Fault Tolerance & Error Handling",
    icon: ShieldCheck,
    items: [
      { path: "/circuit-breaker-dashboard", label: "Circuit Breaker Dashboard", icon: CircuitBoard },
      { path: "/idempotency-dashboard", label: "Idempotency Keys", icon: Fingerprint },
      { path: "/error-catalog", label: "Error Catalog", icon: AlertCircle },
      { path: "/notification-center", label: "Notification Center", icon: Bell },
      { path: "/retry-policies", label: "Retry Policies", icon: RotateCcw },
      { path: "/error-telemetry", label: "Error Telemetry", icon: BarChart3 },
    ],
  },
  {
    category: "Performance & Scalability",
    icon: Zap,
    items: [
      { path: "/performance-cache", label: "Cache Dashboard", icon: Database },
      { path: "/performance-metrics", label: "Performance Metrics", icon: Activity },
      { path: "/keda-autoscaling", label: "KEDA Autoscaling", icon: ArrowUpCircle },
      { path: "/keda-policies", label: "Scaling Policies", icon: Layers },
    ],
  },
  {
    category: "High Availability",
    icon: Server,
    items: [
      { path: "/ha-services", label: "HA Services", icon: Server },
      { path: "/ha-middleware", label: "HA Middleware", icon: Database },
      { path: "/ha-zones", label: "HA Zones", icon: Globe },
    ],
  },
  {
    category: "Lakehouse & Data Platform",
    icon: Database,
    items: [
      { path: "/lakehouse-domain-cdc", label: "Domain CDC Events", icon: Activity },
      { path: "/lakehouse-cdc-events", label: "CDC Event Stream", icon: Radio },
      { path: "/lakehouse-clients", label: "Shared Clients", icon: Code },
      { path: "/lakehouse-query-federation", label: "Query Federation", icon: Search },
      { path: "/lakehouse-materialized-views", label: "Materialized Views", icon: Layers },
      { path: "/lakehouse-lineage-nodes", label: "Lineage Nodes", icon: GitBranch },
      { path: "/lakehouse-lineage-edges", label: "Lineage Edges", icon: ArrowRightLeft },
    ],
  },
  {
    category: "Postgres Optimization",
    icon: Database,
    items: [
      { path: "/pg-query-profiles", label: "Query Profiles", icon: Database },
      { path: "/pg-index-advisory", label: "Index Advisory", icon: Zap },
      { path: "/pg-connection-pools", label: "Connection Pools", icon: Layers },
      { path: "/pg-slow-queries", label: "Slow Queries", icon: AlertTriangle },
      { path: "/pg-table-stats", label: "Table Statistics", icon: BarChart3 },
      { path: "/pg-tuning-params", label: "Tuning Parameters", icon: Settings },
    ],
  },
  {
    category: "APISIX Gateway",
    icon: Globe,
    items: [
      { path: "/apisix-routes", label: "Routes", icon: Globe },
      { path: "/apisix-upstreams", label: "Upstreams", icon: Satellite },
      { path: "/apisix-plugins", label: "Plugins", icon: Settings },
    ],
  },
  {
    category: "OpenAppSec WAF",
    icon: ShieldAlert,
    items: [
      { path: "/openappsec-rules", label: "WAF Rules", icon: Shield },
      { path: "/openappsec-events", label: "Security Events", icon: AlertTriangle },
    ],
  },
  {
    category: "Keycloak IAM",
    icon: Key,
    items: [
      { path: "/keycloak", label: "Overview", icon: Key },
      { path: "/keycloak-realms", label: "Realms", icon: Shield },
      { path: "/keycloak-clients", label: "Clients", icon: Key },
      { path: "/keycloak-roles", label: "Roles", icon: Users },
      { path: "/keycloak-identity-providers", label: "Identity Providers", icon: Link2 },
      { path: "/jwt-auth", label: "JWT Auth Enforcement", icon: Lock },
    ],
  },
  {
    category: "Service Mesh",
    icon: Satellite,
    items: [
      { path: "/service-registry", label: "Service Registry", icon: Satellite },
      { path: "/proxy-routes", label: "Proxy Routes", icon: ArrowRightLeft },
    ],
  },
  {
    category: "Observability",
    icon: Activity,
    items: [
      { path: "/otel-configs", label: "OpenTelemetry", icon: Activity },
      { path: "/prometheus-metrics", label: "Prometheus Metrics", icon: BarChart3 },
      { path: "/grafana-dashboards", label: "Grafana Dashboards", icon: LayoutDashboard },
      { path: "/alert-rules", label: "Alert Rules", icon: Bell },
    ],
  },
  {
    category: "Mojaloop Interoperability",
    icon: Globe,
    items: [
      { path: "/mojaloop", label: "Transfers", icon: Send },
      { path: "/mojaloop-callbacks", label: "FSPIOP Callbacks", icon: Phone },
      { path: "/mojaloop-callback-endpoints", label: "Callback Endpoints", icon: Link2 },
      { path: "/mojaloop-ilp-packets", label: "ILP Packets", icon: Shield },
      { path: "/mojaloop-settlement-windows", label: "Settlement Windows", icon: Clock },
      { path: "/mojaloop-settlement-models", label: "Settlement Models", icon: Layers },
      { path: "/mojaloop-admin-participants", label: "Admin — Participants", icon: Users },
      { path: "/mojaloop-admin-limits", label: "Admin — Limits", icon: Gauge },
      { path: "/mojaloop-corridors", label: "Cross-Border Corridors", icon: Globe },
      { path: "/mojaloop-tb-bridge-entries", label: "TB Bridge Entries", icon: ArrowRightLeft },
      { path: "/mojaloop-tb-bridge-configs", label: "TB Bridge Configs", icon: Settings },
    ],
  },
  {
    category: "TigerBeetle ↔ Postgres Sync",
    icon: RefreshCw,
    items: [
      { path: "/tb-pg-sync-configs", label: "Sync Pipelines", icon: RefreshCw },
      { path: "/tb-pg-sync-events", label: "Sync Events", icon: Activity },
      { path: "/tb-pg-reconciliation-runs", label: "Reconciliation Runs", icon: Scale },
      { path: "/tb-pg-reconciliation-rules", label: "Reconciliation Rules", icon: Shield },
      { path: "/tb-pg-balance-cache-configs", label: "Balance Cache", icon: Zap },
      { path: "/tb-pg-balance-cache-entries", label: "Cached Balances", icon: Database },
      { path: "/tb-pg-saga-definitions", label: "Saga Definitions", icon: GitBranch },
      { path: "/tb-pg-saga-executions", label: "Saga Executions", icon: PlayCircle },
    ],
  },
  {
    category: "AI / ML / GNN / CV",
    icon: Zap,
    items: [
      { path: "/gnn-fraud-detection", label: "GNN Fraud Detection", icon: Shield },
      { path: "/fraudfusion-ensemble", label: "FraudFusion Ensemble", icon: Layers },
      { path: "/mcmc-bayesian-risk", label: "MCMC Bayesian Risk", icon: TrendingUp },
      { path: "/cocoindex-pipeline", label: "CocoIndex Pipelines", icon: Database },
      { path: "/epr-kgqa", label: "EPR-KGQA (Knowledge QA)", icon: Search },
      { path: "/falkordb-graph", label: "FalkorDB Graph", icon: GitBranch },
      { path: "/ollama-llm", label: "Ollama Local LLM", icon: Zap },
      { path: "/art-adversarial", label: "ART Adversarial Defense", icon: Shield },
      { path: "/mojaloop-pisp", label: "Mojaloop PISP", icon: Globe },
      { path: "/tb-multicurrency", label: "TB Multi-Currency", icon: Coins },
      { path: "/kafka-governance", label: "Kafka Governance", icon: Radio },
    ],
  },
  {
    category: "Security Hardening",
    icon: Shield,
    items: [
      { path: "/cors-gateway", label: "CORS Gateway", icon: Globe },
      { path: "/auth-enforcer", label: "Auth Enforcer", icon: Lock },
      { path: "/request-validator", label: "Request Validator", icon: CheckCircle },
      { path: "/api-versioning", label: "API Versioning", icon: GitBranch },
      { path: "/apm-sentry", label: "APM & Sentry", icon: Activity },
      { path: "/secrets-rotation", label: "Secrets Rotation", icon: Key },
    ],
  },
  {
    category: "Data Management",
    icon: Database,
    items: [
      { path: "/db-migration-manager", label: "DB Migrations", icon: Database },
      { path: "/connection-pooler", label: "Connection Pooler", icon: Zap },
      { path: "/backup-manager", label: "Backup Manager", icon: Download },
    ],
  },
  {
    category: "Testing Suite",
    icon: CheckCircle,
    items: [
      { path: "/unit-test-runner", label: "Unit Tests", icon: CheckSquare },
      { path: "/e2e-orchestrator", label: "E2E Orchestrator", icon: PlayCircle },
      { path: "/contract-tests", label: "Contract Tests", icon: Scale },
      { path: "/load-test-runner", label: "Load Tests", icon: Gauge },
    ],
  },
  {
    category: "Extended Observability",
    icon: Radio,
    items: [
      { path: "/otel-collector", label: "OTel Collector", icon: Radio },
      { path: "/changelog-generator", label: "Changelog", icon: FileText },
      { path: "/helm-validator", label: "Helm Validator", icon: Shield },
    ],
  },
  {
    category: "Frontend Quality",
    icon: Code,
    items: [
      { path: "/accessibility-auditor", label: "Accessibility (WCAG)", icon: Shield },
      { path: "/i18n-service", label: "i18n Localization", icon: Globe },
    ],
  },
  {
    category: "Missing Banking Domains",
    icon: Building2,
    items: [
      { path: "/credit-scoring", label: "Credit Scoring", icon: TrendingUp },
      { path: "/debt-collection", label: "Debt Collection", icon: DollarSign },
      { path: "/account-closure", label: "Account Closure", icon: Shield },
      { path: "/dormancy-management", label: "Dormancy Management", icon: Clock },
      { path: "/interest-computation", label: "Interest Computation", icon: Calculator },
      { path: "/fee-management", label: "Fee Management", icon: Receipt },
      { path: "/tax-reporting", label: "Tax Reporting", icon: FileBarChart },
      { path: "/regulatory-sandbox", label: "Regulatory Sandbox", icon: Rocket },
      { path: "/api-analytics", label: "API Analytics", icon: BarChart3 },
      { path: "/developer-portal", label: "Developer Portal", icon: Code },
      { path: "/customer-360-dashboard", label: "Customer 360", icon: Users },
      { path: "/realtime-pricing", label: "Real-Time Pricing", icon: Zap },
    ],
  },
  {
    category: "Security Enhancement",
    icon: Shield,
    items: [
      { path: "/scratch-card-pins", label: "Scratch Card PINs", icon: CreditCard },
      { path: "/hsm-key-manager", label: "HSM Key Manager", icon: Key },
      { path: "/pin-block-engine", label: "PIN Block Engine", icon: Lock },
      { path: "/grid-token-cards", label: "Grid Token Cards", icon: LayoutGrid },
      { path: "/mfa-orchestrator", label: "MFA Orchestrator", icon: Fingerprint },
      { path: "/otp-hardening", label: "OTP Hardening", icon: Shield },
      { path: "/session-security", label: "Session Security", icon: Monitor },
      { path: "/api-key-vault", label: "API Key Vault", icon: Key },
      { path: "/adaptive-rate-limiter", label: "Rate Limiter", icon: Activity },
      { path: "/field-level-encryption", label: "Field Encryption", icon: Lock },
      { path: "/certificate-manager", label: "Certificate Manager", icon: FileCheck },
      { path: "/security-audit-logger", label: "Security Audit", icon: FileSearch },
    ],
  },
  {
    category: "Security Hardening",
    icon: Shield,
    items: [
      { path: "/jwt-validator", label: "JWT Validator", icon: Shield },
      { path: "/route-schema-enforcer", label: "Route Schema Enforcer", icon: FileCheck },
      { path: "/sql-parameterizer", label: "SQL Parameterizer", icon: Database },
      { path: "/secrets-vault", label: "Secrets Vault", icon: Lock },
      { path: "/pin-hasher", label: "PIN Hasher (Argon2)", icon: Key },
      { path: "/docker-hardener", label: "Docker Hardener", icon: Box },
      { path: "/pkce-auth-flow", label: "PKCE Auth Flow", icon: Shield },
      { path: "/token-rotation", label: "Token Rotation", icon: RefreshCw },
      { path: "/mtls-mesh", label: "mTLS Mesh", icon: Network },
      { path: "/body-limit-enforcer", label: "Body Limit Enforcer", icon: Shield },
      { path: "/cloud-kms-bridge", label: "Cloud KMS Bridge", icon: Key },
      { path: "/tls-terminator", label: "TLS Terminator", icon: Lock },
      { path: "/event-correlator", label: "Event Correlator", icon: Activity },
      { path: "/pci-scanner", label: "PCI-DSS Scanner", icon: FileSearch },
      { path: "/api-key-enforcer", label: "API Key Enforcer", icon: Key },
      { path: "/path-validator", label: "Path Validator", icon: Shield },
      { path: "/key-rotation-engine", label: "Key Rotation", icon: RefreshCw },
      { path: "/network-policy-manager", label: "Network Policy", icon: Network },
      { path: "/vault-integration", label: "Vault Integration", icon: Lock },
      { path: "/anomaly-detector", label: "Anomaly Detector", icon: AlertTriangle },
      { path: "/ndpr-compliance", label: "NDPR Compliance", icon: FileCheck },
      { path: "/output-encoder", label: "Output Encoder", icon: Code },
      { path: "/image-scanner", label: "Image Scanner", icon: Box },
      { path: "/waf-rules-engine", label: "WAF Rules Engine", icon: Shield },
      { path: "/ddos-shield", label: "DDoS Shield", icon: Zap },
      { path: "/ip-allowlist", label: "IP Allowlist", icon: Globe },
      { path: "/siem-exporter", label: "SIEM Exporter", icon: Upload },
      { path: "/cbn-compliance-checker", label: "CBN Compliance", icon: FileCheck },
      { path: "/egress-controller", label: "Egress Controller", icon: ArrowUpRight },
      { path: "/incident-responder", label: "Incident Responder", icon: AlertTriangle },
      { path: "/immutable-audit", label: "Immutable Audit", icon: Link2 },
      { path: "/soc2-evidence", label: "SOC 2 Evidence", icon: Clipboard },
      { path: "/pentest-orchestrator", label: "Pentest Orchestrator", icon: Target },
      { path: "/sri-validator", label: "SRI Validator", icon: CheckCircle },
      { path: "/csp-nonce-engine", label: "CSP Nonce Engine", icon: Shield },
      { path: "/clickjack-defender", label: "Clickjack Defender", icon: Shield },
      { path: "/browser-fingerprint", label: "Browser Fingerprint", icon: Fingerprint },
    ],
  },
  {
    category: "Performance Optimization",
    icon: Zap,
    items: [
      { path: "/redis-cache-middleware", label: "Redis Response Cache", icon: Database },
      { path: "/redis-session-store", label: "Redis Session Store", icon: Key },
      { path: "/cache-invalidation", label: "Cache Invalidation", icon: RefreshCw },
      { path: "/bloom-filter-cache", label: "Bloom Filter Cache", icon: Database },
      { path: "/sorted-set-ranking", label: "Sorted Set Rankings", icon: BarChart2 },
      { path: "/pgbouncer-manager", label: "PgBouncer Manager", icon: Database },
      { path: "/query-cache-engine", label: "Query Cache Engine", icon: Zap },
      { path: "/prepared-stmt-cache", label: "Prepared Statements", icon: Database },
      { path: "/table-partitioner", label: "Table Partitioner", icon: Layers },
      { path: "/materialized-view-engine", label: "Materialized Views", icon: Gauge },
      { path: "/hot-data-cache", label: "Hot Data Cache", icon: Zap },
      { path: "/batch-aggregator", label: "Batch Aggregator", icon: Package },
      { path: "/keepalive-tuner", label: "Keep-Alive Tuner", icon: Activity },
      { path: "/response-compressor", label: "Response Compressor", icon: ArrowUpRight },
      { path: "/grpc-hot-path", label: "gRPC Hot Path", icon: Zap },
      { path: "/route-trie-optimizer", label: "Route Trie Optimizer", icon: GitBranch },
      { path: "/stream-response", label: "Response Streamer", icon: ArrowUpRight },
      { path: "/http2-multiplexer", label: "HTTP/2 Multiplexer", icon: Globe },
      { path: "/request-coalescer", label: "Request Coalescer", icon: Layers },
      { path: "/fast-json-serializer", label: "Fast JSON Serializer", icon: Zap },
      { path: "/sw-api-cache", label: "SW API Cache", icon: Download },
      { path: "/virtual-scroll-engine", label: "Virtual Scroll Engine", icon: Layers },
      { path: "/component-memoizer", label: "Component Memoizer", icon: Cpu },
      { path: "/bundle-splitter", label: "Bundle Splitter", icon: Package },
      { path: "/optimistic-ui-engine", label: "Optimistic UI Engine", icon: Zap },
      { path: "/kafka-consumer-optimizer", label: "Kafka Consumer Optimizer", icon: Activity },
      { path: "/kafka-batch-producer", label: "Kafka Batch Producer", icon: ArrowUpRight },
      { path: "/avro-schema-registry", label: "Avro Schema Registry", icon: FileCheck },
      { path: "/fluvio-wasm-transform", label: "Fluvio WASM Transform", icon: Cpu },
      { path: "/event-dedup-engine", label: "Event Dedup Engine", icon: Shield },
      { path: "/distroless-builder", label: "Distroless Builder", icon: Box },
      { path: "/tigerbeetle-batch", label: "TigerBeetle Batch", icon: Zap },
      { path: "/hpa-autoscaler", label: "HPA Autoscaler", icon: TrendingUp },
      { path: "/cdn-edge-cache", label: "CDN Edge Cache", icon: Globe },
      { path: "/read-replica-router", label: "Read Replica Router", icon: Database },
      { path: "/keda-scaler", label: "KEDA Event Scaler", icon: TrendingUp },
      { path: "/prometheus-dashboard", label: "Prometheus Dashboard", icon: BarChart2 },
      { path: "/opensearch-optimizer", label: "OpenSearch Optimizer", icon: Search },
      { path: "/temporal-memoizer", label: "Temporal Memoizer", icon: Clock },
      { path: "/apisix-plugin-optimizer", label: "APISIX Plugin Optimizer", icon: Settings },
    ],
  },
  {
    category: "AML Enhancement",
    icon: Shield,
    items: [
      { path: "/aml-risk-scoring", label: "AML Risk Scoring", icon: Shield },
      { path: "/sar-filing", label: "SAR Filing Engine", icon: FileText },
      { path: "/ctr-auto-filer", label: "CTR Auto-Filing", icon: FileText },
      { path: "/aml-case-manager", label: "AML Case Management", icon: Briefcase },
      { path: "/watchlist-manager", label: "Global Watchlist Manager", icon: Globe },
      { path: "/adverse-media-scanner", label: "Adverse Media Scanner", icon: Search },
      { path: "/beneficial-ownership", label: "Beneficial Ownership", icon: Users },
      { path: "/txn-pattern-analyzer", label: "Transaction Patterns", icon: Activity },
      { path: "/goaml-integration", label: "goAML Integration", icon: FileText },
      { path: "/aml-compliance-dashboard", label: "AML Compliance Dashboard", icon: BarChart2 },
      { path: "/sanctions-batch-rescreener", label: "Batch Re-screener", icon: RefreshCw },
      { path: "/aml-training-tracker", label: "AML Training Tracker", icon: GraduationCap },
      { path: "/wire-transfer-monitor", label: "Wire Transfer Monitor", icon: ArrowUpRight },
      { path: "/aml-regulatory-reporting", label: "Regulatory Reporting", icon: FileText },
      { path: "/typology-detector", label: "Typology Detector", icon: Crosshair },
    ],
  },
  {
    category: "Agriculture Enhancement",
    icon: Wheat,
    items: [
      { label: "Cooperative Management", path: "/agriculture-enhancement/cooperative-management", icon: Users },
      { label: "Livestock Management", path: "/agriculture-enhancement/livestock-management", icon: Bug },
      { label: "Input Marketplace", path: "/agriculture-enhancement/agri-input-marketplace", icon: ShoppingCart },
      { label: "NIRSAL Credit Guarantee", path: "/agriculture-enhancement/nirsal-credit-guarantee", icon: Shield },
      { label: "CBN Anchor Borrowers", path: "/agriculture-enhancement/cbn-anchor-borrowers", icon: Landmark },
      { label: "USSD Agriculture", path: "/agriculture-enhancement/interactive-ussd-agri", icon: Smartphone },
      { label: "Savings Cycles", path: "/agriculture-enhancement/agri-savings-cycles", icon: PiggyBank },
      { label: "Livestock Finance", path: "/agriculture-enhancement/livestock-finance", icon: Banknote },
      { label: "Commodity Exchange", path: "/agriculture-enhancement/commodity-exchange", icon: ArrowLeftRight },
      { label: "Agri E-Voucher", path: "/agriculture-enhancement/agri-evoucher", icon: Ticket },
      { label: "Price Intelligence", path: "/agriculture-enhancement/commodity-price-intelligence", icon: TrendingUp },
      { label: "Satellite Monitor", path: "/agriculture-enhancement/satellite-crop-monitor", icon: Satellite },
      { label: "CoopScore", path: "/agriculture-enhancement/cooperative-credit-scoring", icon: BarChart3 },
      { label: "Fisheries Banking", path: "/agriculture-enhancement/fisheries-aquaculture", icon: Fish },
      { label: "Farm Mapping", path: "/agriculture-enhancement/farm-boundary-mapping", icon: Map },
      { label: "AYII Insurance", path: "/agriculture-enhancement/area-yield-index-insurance", icon: CloudRain },
      { label: "Warehouse Mgmt", path: "/agriculture-enhancement/warehouse-management", icon: Warehouse },
      { label: "Agent Onboarding", path: "/agriculture-enhancement/agent-farmer-onboarding", icon: UserPlus },
      { label: "Livestock Insurance", path: "/agriculture-enhancement/livestock-insurance", icon: ShieldCheck },
      { label: "Equipment Leasing", path: "/agriculture-enhancement/equipment-leasing", icon: Tractor },
      { label: "Yield Prediction", path: "/agriculture-enhancement/crop-yield-prediction", icon: Brain },
      { label: "MPCI Insurance", path: "/agriculture-enhancement/multi-peril-crop-insurance", icon: Umbrella },
      { label: "Agri Logistics", path: "/agriculture-enhancement/agri-logistics", icon: Truck },
      { label: "CBN Agri Returns", path: "/agriculture-enhancement/cbn-agri-returns", icon: FileText },
      { label: "Animal Traceability", path: "/agriculture-enhancement/animal-id-traceability", icon: ScanLine },
      { label: "NIRSAL Geo-Coop", path: "/agriculture-enhancement/nirsal-agro-geocoop", icon: Globe },
      { label: "IoT Sensors", path: "/agriculture-enhancement/agri-iot-sensor", icon: Cpu },
      { label: "Agri Reinsurance", path: "/agriculture-enhancement/agri-reinsurance", icon: Layers },
      { label: "Quality Grading", path: "/agriculture-enhancement/quality-certification", icon: Award },
      { label: "ESG Impact", path: "/agriculture-enhancement/agri-esg-impact", icon: Leaf },
      { label: "Cross-Border Trade", path: "/agriculture-enhancement/crossborder-agri-trade", icon: Globe2 },
      { label: "Coop Meetings", path: "/agriculture-enhancement/cooperative-meetings", icon: Calendar },
      { label: "Coop Financials", path: "/agriculture-enhancement/cooperative-financials", icon: Receipt },
      { label: "Soil Analysis", path: "/agriculture-enhancement/soil-analysis", icon: Beaker },
      { label: "Insurance Analytics", path: "/agriculture-enhancement/insurance-portfolio-analytics", icon: PieChart },
      { label: "Parametric Insurance", path: "/agriculture-enhancement/parametric-insurance-iot", icon: Zap },
      { label: "Post-Harvest Loss", path: "/agriculture-enhancement/post-harvest-loss-tracker", icon: Trash2 },
      { label: "Aggregation Center", path: "/agriculture-enhancement/aggregation-center", icon: Building },
      { label: "CBN AGSMEIS", path: "/agriculture-enhancement/cbn-agsmeis", icon: Landmark },
      { label: "ACGSF Guarantee", path: "/agriculture-enhancement/acgsf-guarantee", icon: BadgeCheck },
    ],
  },
  {
    category: "Channel Banking",
    icon: Phone,
    items: [
      { label: "Voice Banking Gateway", path: "/channel-banking/voice-banking-gateway", icon: Phone },
      { label: "Nigerian Voice TTS", path: "/channel-banking/voice-tts-nigerian", icon: Volume2 },
      { label: "Nigerian Voice ASR", path: "/channel-banking/voice-asr-nigerian", icon: Mic },
      { label: "Voice NLU Banking", path: "/channel-banking/voice-nlu-banking", icon: Brain },
      { label: "Voice Biometric Auth", path: "/channel-banking/voice-biometric-auth", icon: Fingerprint },
      { label: "IVR Menu Engine", path: "/channel-banking/voice-ivr-menu", icon: ListTree },
      { label: "Voice Call Analytics", path: "/channel-banking/voice-call-analytics", icon: BarChart3 },
      { label: "Voice Agent Escalation", path: "/channel-banking/voice-agent-escalation", icon: HeadphonesIcon },
      { label: "Telegram Bot Gateway", path: "/channel-banking/telegram-bot-gateway", icon: Send },
      { label: "Telegram Banking Commands", path: "/channel-banking/telegram-banking-commands", icon: Terminal },
      { label: "Telegram Notifications", path: "/channel-banking/telegram-notification", icon: Bell },
      { label: "Telegram Mini App", path: "/channel-banking/telegram-mini-app", icon: Smartphone },
      { label: "Telegram KYC Bot", path: "/channel-banking/telegram-kyc-bot", icon: UserCheck },
      { label: "WhatsApp Business Gateway", path: "/channel-banking/whatsapp-business-gateway", icon: MessageSquare },
      { label: "WhatsApp Banking Flows", path: "/channel-banking/whatsapp-banking-flows", icon: GitBranch },
      { label: "WhatsApp Payment", path: "/channel-banking/whatsapp-payment-integration", icon: CreditCard },
      { label: "WhatsApp Notifications", path: "/channel-banking/whatsapp-notification", icon: BellRing },
      { label: "WhatsApp Documents", path: "/channel-banking/whatsapp-document-service", icon: FileText },
      { label: "USSD Banking Gateway", path: "/channel-banking/ussd-banking-gateway", icon: Hash },
      { label: "USSD Transaction Engine", path: "/channel-banking/ussd-transaction-engine", icon: Zap },
      { label: "USSD Multilingual", path: "/channel-banking/ussd-multilingual", icon: Globe },
      { label: "USSD SIM Toolkit", path: "/channel-banking/ussd-sim-toolkit", icon: Cpu },
      { label: "SMS Banking Gateway", path: "/channel-banking/sms-banking-gateway", icon: Mail },
      { label: "SMS OTP Service", path: "/channel-banking/sms-otp-service", icon: Key },
      { label: "SMS Alert Notification", path: "/channel-banking/sms-alert-notification", icon: AlertCircle },
    ],
  },
];

function CategorySection({
  cat,
  isOpen,
  onToggle,
  location,
  onItemClick,
  isEnabled,
}: {
  cat: MenuCategory;
  isOpen: boolean;
  onToggle: () => void;
  location: string;
  onItemClick: () => void;
  isEnabled: (flag: string) => boolean;
}) {
  const CatIcon = cat.icon;

  // Filter items based on feature flags — items without a flag mapping are always visible
  const visibleItems = cat.items.filter((item) => {
    const flagKey = SERVICE_CATALOG[item.path];
    return !flagKey || isEnabled(flagKey);
  });

  // Hide entire category if no items are visible
  if (visibleItems.length === 0) return null;

  const hasActive = visibleItems.some((item) => item.path === location);

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={onToggle}
        className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
          hasActive
            ? "bg-blue-50 text-blue-700"
            : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
        }`}
      >
        <CatIcon size={14} />
        <span className="flex-1 text-left">{cat.category}</span>
        <span className="text-xs font-normal text-slate-400 mr-1">{visibleItems.length}</span>
        <span className="text-slate-400">
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>
      {isOpen && (
        <div className="ml-2 mt-0.5 space-y-0.5 border-l border-slate-200 pl-2">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const active = location === item.path;
            return (
              <Link
                key={item.path}
                href={item.path}
                onClick={onItemClick}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  active
                    ? "bg-blue-50 font-medium text-blue-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <Icon size={14} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ArchiveAdminSidebar() {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isEnabled } = useFeatureFlags();

  // Auto-expand the category that contains the active route
  const activeCategory = categorizedMenu.findIndex((cat) =>
    cat.items.some((item) => item.path === location),
  );
  const [openCategories, setOpenCategories] = useState<Set<number>>(() => {
    const initial = new Set<number>();
    // Always open Overview
    initial.add(0);
    if (activeCategory >= 0) initial.add(activeCategory);
    return initial;
  });

  const toggleCategory = (idx: number) => {
    setOpenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const navigationItems = (
    <div className="space-y-0.5">
      {categorizedMenu.map((cat, idx) => (
        <CategorySection
          key={cat.category}
          cat={cat}
          isOpen={openCategories.has(idx)}
          onToggle={() => toggleCategory(idx)}
          location={location}
          onItemClick={() => setMobileOpen(false)}
          isEnabled={isEnabled}
        />
      ))}
    </div>
  );

  return (
    <>
      <div className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-blue-600">54link-dev</h1>
            <p className="truncate text-xs text-slate-500">Super Admin Console</p>
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-2xl bg-slate-100 px-4 py-3 text-xs text-slate-500">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          {categorizedMenu.length} categories &middot; {categorizedMenu.reduce((s, c) => s + c.items.length, 0)} pages
        </div>
        {mobileOpen ? (
          <div className="mt-3 max-h-[70vh] overflow-y-auto rounded-3xl border border-slate-200 bg-white shadow-2xl">
            <div className="border-b border-slate-200 px-4 py-4">
              <Link
                href="/admin/onboarding"
                onClick={() => setMobileOpen(false)}
                className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(37,99,235,0.18)]"
              >
                <Plus size={18} />
                Review Partners
              </Link>
            </div>
            <nav className="px-4 py-4">{navigationItems}</nav>
            <div className="border-t border-slate-200 px-4 py-4">
              <div className="flex items-center gap-3 rounded-xl px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
                  SA
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">Super Admin</p>
                  <p className="truncate text-xs text-slate-500">admin@54link-dev.com</p>
                </div>
              </div>
              <Link
                href="/login"
                onClick={() => setMobileOpen(false)}
                className="mt-2 flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
              >
                <LogOut size={18} />
                Logout
              </Link>
            </div>
          </div>
        ) : null}
      </div>

      <aside className="hidden min-h-screen w-72 shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col">
        <div className="border-b border-slate-200 px-6 py-6">
          <h1 className="text-2xl font-bold text-blue-600">54link-dev</h1>
          <p className="mt-1 text-xs text-slate-500">Super Admin Console</p>
          <div className="mt-5 flex items-center gap-2 rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-500">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            {categorizedMenu.length} categories &middot; {categorizedMenu.reduce((s, c) => s + c.items.length, 0)} pages
          </div>
        </div>

        <div className="border-b border-slate-200 px-4 py-4">
          <Link
            href="/admin/onboarding"
            className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(37,99,235,0.18)]"
          >
            <Plus size={18} />
            Review Partners
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-4">{navigationItems}</nav>

        <div className="border-t border-slate-200 px-4 py-4">
          <div className="flex items-center gap-3 rounded-xl px-4 py-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
              SA
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900">Super Admin</p>
              <p className="truncate text-xs text-slate-500">admin@54link-dev.com</p>
            </div>
          </div>
          <Link
            href="/login"
            className="mt-2 flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
          >
            <LogOut size={18} />
            Logout
          </Link>
        </div>
      </aside>
    </>
  );
}
