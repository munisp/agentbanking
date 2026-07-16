import "leaflet/dist/leaflet.css";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Award,
  BarChart3,
  Trophy,
  Bell,
  BookOpen,
  Building2,
  ChevronDown,
  Cpu,
  CreditCard,
  Eye,
  FileText,
  LayoutDashboard,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Menu,
  MessageSquare,
  MonitorSmartphone,
  Network,
  Package,
  Settings,
  Shield,
  Smartphone,
  Star,
  Store,
  TrendingUp,
  User,
  UserCheck,
  Users,
  Wifi,
  X,
  Gauge,
  Layers,
  GitBranch,
  Radio,
  Database,
  Server,
  FlaskConical,
  ShoppingBag,
  Leaf,
  Globe,
  HeadphonesIcon,
  MessageCircle,
  Wallet,
  Zap,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

// Import logo
import logo from "./assets/logo.png";

// Import contexts
import {
  TenantBrandingProvider,
  useTenantBranding,
} from "./contexts/TenantBrandingContext";

// Import permissions hook
import { PERMISSION_MAP, usePermissions } from "./hooks/usePermissions";

// Import services
import { tenantService } from "./services/tenant/tenantService";

// Import pages
import Loans from "./pages/Loans";
import MDM from "./pages/MDM";
import QRCodePage from "./pages/QRCode";
import Transactions from "./pages/Transactions";
import Transfer from "./pages/Transfer";
import ErpNextPage from "./pages/erpnext/ErpNextPage";
import FraudEnginePage from "./pages/fraud-engine/FraudEnginePage";
import LoyaltyPage from "./pages/loyalty/LoyaltyPage";
import NigeriaVatPage from "./pages/nigeria-vat/NigeriaVatPage";
import StorefrontAdvertisingPage from "./pages/storefront-advertising/StorefrontAdvertisingPage";

// Billing pages
import BillingDashboardPage from "./pages/billing/BillingDashboardPage";
import InvoiceManagementPage from "./pages/billing/InvoiceManagementPage";
import BillingLedgerPage from "./pages/billing/BillingLedgerPage";
import CreditsPaymentsPage from "./pages/billing/CreditsPaymentsPage";

// Import components
import AdminManagement from "./components/Admins/AdminManagement";
import AgentManagement from "./components/Agents/AgentManagement";
import AuditLogs from "./components/Audit/AuditLogs";
import ChartOfAccounts from "./components/ChartOfAccounts/ChartOfAccounts";
import CommissionSettlement from "./components/Commission/CommissionSettlement";
import CommunicationManagement from "./components/Communication/CommunicationManagement";
import ComplianceMonitoring from "./components/Compliance/ComplianceMonitoring";
import Dashboard from "./components/Dashboard/Dashboard";
import AdminDisputeManagement from "./components/Disputes/AdminDisputeManagement";
import HierarchyManagement from "./components/Hierarchy/HierarchyManagement";
import PerformanceMonitoring from "./components/Monitoring/PerformanceMonitoring";
import NetworkStatusMonitor from "./components/NetworkStatus/NetworkStatusMonitor.tsx";
import NotificationCenter from "./components/Notifications/NotificationCenter";
import DeviceCatalog from "./components/POSManagement/DeviceCatalog";
import GeofenceViolationsMonitor from "./components/POSManagement/GeofenceViolationsMonitor";
import POSHardwareInventory from "./components/POSManagement/POSHardwareInventory";
import POSManagement from "./components/POSManagement/POSManagement";
import POSRequestManagement from "./components/POSManagement/POSRequestManagement";
import ProjectionsAnalytics from "./components/Projections/ProjectionsAnalytics";
import AgentBusinessReports from "./components/Reports/AgentBusinessReports";
import ReportsAnalytics from "./components/Reports/ReportsAnalytics";
import SecurityCenter from "./components/Security/SecurityCenter";
import SystemSettings from "./components/Settings/SystemSettings";
import StoresList from "./components/Stores/StoresList";
// import StorefrontManagement from "./components/Storefront/StorefrontManagement";
import TransactionManagement from "./components/Transactions/TransactionManagement";
import UserManagement from "./components/Users/UserManagement";
import NetworkOperations from "./pages/NetworkOperations";
import ServiceIntegrations from "./pages/ServiceIntegrations";
import SettlementReconciliation from "./pages/settlement/SettlementReconciliation";
import SettlementBatchProcessor from "./pages/settlement/SettlementBatchProcessor";
import ChargebackManagement from "./pages/disputes/ChargebackManagement";
import DisputeArbitration from "./pages/disputes/DisputeArbitration";
import DisputeResolutionPage from "./pages/disputes/DisputeResolutionPage";
import CustomerDisputePortal from "./pages/disputes/CustomerDisputePortal";
import DisputeMediationAI from "./pages/disputes/DisputeMediationAI";
import DisputeAutoRules from "./pages/disputes/DisputeAutoRules";
import AgentGamificationPage from "./pages/agents-gamification/AgentGamificationPage";
import AgentGamification from "./pages/agents-gamification/AgentGamification";
import AgentTrainingPage from "./pages/agent-training/AgentTrainingPage";
import AgentTrainingAcademy from "./pages/agent-training/AgentTrainingAcademy";
import AgentTrainingPortal from "./pages/agent-training/AgentTrainingPortal";
import AgentPerformanceLeaderboardPage from "./pages/agent-performance/AgentPerformanceLeaderboardPage";
import AgentPerformance from "./pages/agent-performance/AgentPerformance";
import AgentPerformanceAnalytics from "./pages/agent-performance/AgentPerformanceAnalytics";
import AgentPerformanceIncentives from "./pages/agent-performance/AgentPerformanceIncentives";
import AgentPerformanceLeaderboard from "./pages/agent-performance/AgentPerformanceLeaderboard";
import AgentPerformanceScorecardPage from "./pages/agent-performance/AgentPerformanceScorecardPage";
import AgentPerformanceScoring from "./pages/agent-performance/AgentPerformanceScoring";
import ComplianceAutomationPage from "./pages/compliance/ComplianceAutomationPage";
import ComplianceCertManager from "./pages/compliance/ComplianceCertManager";
import ComplianceChatbotPage from "./pages/compliance/ComplianceChatbotPage";
import ComplianceFilingPage from "./pages/compliance/ComplianceFilingPage";
import ComplianceReporting from "./pages/compliance/ComplianceReporting";
import ComplianceScheduling from "./pages/compliance/ComplianceScheduling";
import ComplianceTrainingPage from "./pages/compliance/ComplianceTrainingPage";
import ComplianceTrainingTracker from "./pages/compliance/ComplianceTrainingTracker";
import GDPRModule from "./pages/compliance/GDPRModule";
import CBNScheduledReports from "./pages/compliance/CBNScheduledReports";
import NFIUReporting from "./pages/compliance/NFIUReporting";
import RegulatorySandbox from "./pages/compliance/RegulatorySandbox";
import DeveloperPortal from "./pages/developer/DeveloperPortal";
import ApiKeyManagement from "./pages/developer/ApiKeyManagement";
import WebhookManagement from "./pages/developer/WebhookManagement";
import RevenueLeakage from "./pages/finance/RevenueLeakage";
import NettingEngine from "./pages/finance/NettingEngine";
import CommissionClawback from "./pages/finance/CommissionClawback";
import CreditRatingSystem from "./pages/finance/CreditRatingSystem";
import IncidentManagement from "./pages/ops/IncidentManagement";
import ABTesting from "./pages/ops/ABTesting";
import CanaryRelease from "./pages/ops/CanaryRelease";
import TerritoryAnalytics from "./pages/ops/TerritoryAnalytics";
import { AppTour, useTour } from "./components/AppTour";

// Developer & API Tooling
import APIAnalyticsDashboard from "./pages/developer/APIAnalyticsDashboard";
import APIRateLimiterDashboard from "./pages/developer/APIRateLimiterDashboard";
import APIVersioningPage from "./pages/developer/APIVersioningPage";
import IntegrationMarketplace from "./pages/developer/IntegrationMarketplace";
import PublishReadinessChecker from "./pages/developer/PublishReadinessChecker";
import ProductionReadinessChecklist from "./pages/developer/ProductionReadinessChecklist";

// Advanced Operations Dashboards
import ChaosEngineeringConsole from "./pages/operations/ChaosEngineeringConsole";
import LoadTestDashboard from "./pages/operations/LoadTestDashboard";
import ServiceMeshDashboard from "./pages/operations/ServiceMeshDashboard";
import MQTTBridgeDashboard from "./pages/operations/MQTTBridgeDashboard";
import SIMOrchestratorDashboard from "./pages/operations/SIMOrchestratorDashboard";
import CarrierManagement from "./pages/operations/CarrierManagement";
import NetworkTelemetry from "./pages/operations/NetworkTelemetry";
import ConnectionQualityMonitor from "./pages/operations/ConnectionQualityMonitor";
import ConnectionPoolMonitor from "./pages/operations/ConnectionPoolMonitor";
import CacheManagementDashboard from "./pages/operations/CacheManagementDashboard";
import RetryQueueViewer from "./pages/operations/RetryQueueViewer";
import ArchivalAdmin from "./pages/operations/ArchivalAdmin";
import DatabaseSchemaVisualization from "./pages/operations/DatabaseSchemaVisualization";
import OpenTelemetryConfig from "./pages/operations/OpenTelemetryConfig";

// Advanced Compliance
import DataRetentionPolicy from "./pages/compliance/DataRetentionPolicy";
import LiveChatSupport from "./pages/compliance/LiveChatSupport";
import HelpDesk from "./pages/compliance/HelpDesk";


// Other Notable Additions
import SocialCommerceGateway from "./pages/SocialCommerceGateway";
import ESGCarbonTracker from "./pages/ESGCarbonTracker";
// NGApp migrations - Compliance
import RegulatorySandboxPage from "./pages/compliance/RegulatorySandboxPage";
import RegulatorySandboxTester from "./pages/compliance/RegulatorySandboxTester";
import AutoComplianceWorkflow from "./pages/compliance/AutoComplianceWorkflow";
import GdprDashboard from "./pages/compliance/GdprDashboard";
import BlockchainAuditTrail from "./pages/compliance/BlockchainAuditTrail";
// NGApp migrations - Merchant
import MerchantPortal from "./pages/merchant/MerchantPortal";
import MerchantAnalyticsDash from "./pages/merchant/MerchantAnalyticsDash";
import MerchantRiskScoring from "./pages/merchant/MerchantRiskScoring";
import MerchantSettlementDashboard from "./pages/merchant/MerchantSettlementDashboard";
import MerchantKycOnboardingPage from "./pages/merchant/MerchantKycOnboardingPage";
// NGApp migrations - Customer
import Customer360Page from "./pages/customers/Customer360Page";
import CustomerSegmentationEngine from "./pages/customers/CustomerSegmentationEngine";
import CustomerJourneyAnalyticsPage from "./pages/customers/CustomerJourneyAnalyticsPage";
import CustomerOnboardingPipeline from "./pages/customers/CustomerOnboardingPipeline";
// NGApp migrations - Disputes & Fraud
import DisputeWorkflowEngine from "./pages/disputes/DisputeWorkflowEngine";
import FraudCaseManagementPage from "./pages/operations/FraudCaseManagementPage";
import FraudMlScoringPage from "./pages/operations/FraudMlScoringPage";
import FraudRealtimeVizPage from "./pages/operations/FraudRealtimeVizPage";
import MultiChannelPaymentOrchestration from "./pages/MultiChannelPaymentOrchestration";
import RevenueForecastingEngine from "./pages/RevenueForecastingEngine";

// ── Remaining pages from NGApp ───────────────────────────────────────────────
import AirtimeVendingPage from "./pages/AirtimeVendingPage";
import ApacheAirflowPage from "./pages/ApacheAirflowPage";
import ApacheNifiPage from "./pages/ApacheNifiPage";
import ApiAnalyticsPage from "./pages/ApiAnalyticsPage";
import ApiRateLimiterDash from "./pages/ApiRateLimiterDash";
import ApiVersioningPage from "./pages/ApiVersioningPage";
import AutomatedTestingFrameworkPage from "./pages/AutomatedTestingFrameworkPage";
import CardBinLookup from "./pages/CardBinLookup";
import CardRequestPage from "./pages/CardRequestPage";
import CarrierCostDashboard from "./pages/CarrierCostDashboard";
import CarrierLivePricingPage from "./pages/CarrierLivePricingPage";
import CarrierSlaDashboard from "./pages/CarrierSlaDashboard";
import CdnCacheManager from "./pages/CdnCacheManager";
import ChargebackManagementPage from "./pages/ChargebackManagementPage";
import CommissionClawbackPage from "./pages/CommissionClawbackPage";
import ConnectionQualityPage from "./pages/ConnectionQualityPage";
import DeviceFleetManager from "./pages/DeviceFleetManager";
import DisputeArbitrationPage from "./pages/DisputeArbitrationPage";
import EsgCarbonTracker from "./pages/ESGCarbonTracker";
import FraudReportPage from "./pages/FraudReportPage";
import GeoFencingPage from "./pages/GeoFencingPage";
import HelpDeskPage from "./pages/HelpDeskPage";
import LoadTestComparison from "./pages/LoadTestComparison";
import OpenTelemetryPage from "./pages/OpenTelemetryPage";
import RevenueLeakageDetector from "./pages/RevenueLeakageDetector";
import ReversalApprovalPage from "./pages/ReversalApprovalPage";
import TransactionMapLoading from "./pages/TransactionMapLoading";
import WebSocketServicePage from "./pages/WebSocketServicePage";

// ── Agent Management (new) ──────────────────────────────────────────────────
import AgentCommissionCalc from "./pages/agent-management-new/AgentCommissionCalc";
import AgentDeviceFingerprint from "./pages/agent-management-new/AgentDeviceFingerprint";
import AgentFloatInsuranceClaims from "./pages/agent-management-new/AgentFloatInsuranceClaims";
import AgentGeoFencingPage from "./pages/agent-management-new/AgentGeoFencingPage";
import AgentHierarchyPage from "./pages/agent-management-new/AgentHierarchyPage";
import AgentInventoryMgmt from "./pages/agent-management-new/AgentInventoryMgmt";
import AgentKycPage from "./pages/agent-management-new/AgentKycPage";
import AgentLoanAdvance from "./pages/agent-management-new/AgentLoanAdvance";
import AgentLoanOriginationV2 from "./pages/agent-management-new/AgentLoanOriginationV2";
import AgentManagementDashboard from "./pages/agent-management-new/AgentManagementDashboard";
import AgentMicroInsurance from "./pages/agent-management-new/AgentMicroInsurance";
import AgentOnboarding from "./pages/agent-management-new/AgentOnboarding";
import AgentOnboardingWizardPage from "./pages/agent-management-new/AgentOnboardingWizardPage";
import AgentOnboardingWorkflowPage from "./pages/agent-management-new/AgentOnboardingWorkflowPage";
import AgentPortal from "./pages/agent-management-new/AgentPortal";
import AgentScorecardPage from "./pages/agent-management-new/AgentScorecardPage";
import AgentStoreSetup from "./pages/agent-management-new/AgentStoreSetup";
import AgentBenchmarking from "./pages/agent-management-new/AgentBenchmarking";
import AgentClusterAnalytics from "./pages/agent-management-new/AgentClusterAnalytics";

// ── Analytics & Reports ──────────────────────────────────────────────────────
import AdvancedBiReportingPage from "./pages/analytics/AdvancedBiReportingPage";
import AnalyticsDashboard from "./pages/analytics/AnalyticsDashboard";
import DragDropReportBuilderPage from "./pages/analytics/DragDropReportBuilderPage";
import ReportBuilderTemplatesPage from "./pages/analytics/ReportBuilderTemplatesPage";
import ReportSchedulerPage from "./pages/analytics/ReportSchedulerPage";
import ReportTemplateDesigner from "./pages/analytics/ReportTemplateDesigner";
import ReportScheduler from "./pages/analytics/ReportScheduler";
import ReportComparison from "./pages/analytics/ReportComparison";
import NLAnalyticsQueryPage from "./pages/analytics/NLAnalyticsQueryPage";
import NlFinancialQuery from "./pages/analytics/NlFinancialQuery";
import LakehouseAiDashboard from "./pages/analytics/LakehouseAiDashboard";
import LakehouseAnalytics from "./pages/analytics/LakehouseAnalytics";
import MLScoringDashboard from "./pages/analytics/MLScoringDashboard";
import TransactionAnalytics from "./pages/analytics/TransactionAnalytics";
import WeeklyReports from "./pages/analytics/WeeklyReports";
import DataExportCenter from "./pages/analytics/DataExportCenter";
import DataExportHubPage from "./pages/analytics/DataExportHubPage";
import DataExportImportPage from "./pages/analytics/DataExportImportPage";
import DataQualityPage from "./pages/analytics/DataQualityPage";

// ── Finance ──────────────────────────────────────────────────────────────────
import CommissionCalculatorPage from "./pages/finance/CommissionCalculatorPage";
import CommissionConfig from "./pages/finance/CommissionConfig";
import CommissionEnginePage from "./pages/finance/CommissionEnginePage";
import CommissionPayouts from "./pages/finance/CommissionPayouts";
import DailyPnlReportPage from "./pages/finance/DailyPnlReportPage";
import PnlReportPage from "./pages/finance/PnlReportPage";
import RealtimePnlDashboard from "./pages/finance/RealtimePnlDashboard";
import GeneralLedgerPage from "./pages/finance/GeneralLedgerPage";
import TigerBeetleLedger from "./pages/finance/TigerBeetleLedger";
import FloatManagementPage from "./pages/finance/FloatManagementPage";
import FloatReconciliationPage from "./pages/finance/FloatReconciliationPage";
import FinancialReconciliationPage from "./pages/finance/FinancialReconciliationPage";
import FinancialReportingSuite from "./pages/finance/FinancialReportingSuite";
import TaxCollectionPage from "./pages/finance/TaxCollectionPage";
import BulkDisbursementEngine from "./pages/finance/BulkDisbursementEngine";
import PayrollDisbursement from "./pages/finance/PayrollDisbursement";
import MultiCurrency from "./pages/finance/MultiCurrency";
import MultiCurrencyExchange from "./pages/finance/MultiCurrencyExchange";
import MultiCurrencyPage from "./pages/finance/MultiCurrencyPage";

// ── Payments & Transactions ──────────────────────────────────────────────────
import Payments from "./pages/payments/Payments";
import PaymentGatewayRouter from "./pages/payments/PaymentGatewayRouter";
import PaymentReconciliation from "./pages/payments/PaymentReconciliation";
import PaymentDisputeArbitration from "./pages/payments/PaymentDisputeArbitration";
import PaymentTokenVault from "./pages/payments/PaymentTokenVault";
import PaymentLinkGenerator from "./pages/payments/PaymentLinkGenerator";
import PaymentNotificationSystem from "./pages/payments/PaymentNotificationSystem";
import DynamicFeeCalculator from "./pages/payments/DynamicFeeCalculator";
import DynamicFeeEnginePage from "./pages/payments/DynamicFeeEnginePage";
import TransactionFeeCalc from "./pages/payments/TransactionFeeCalc";
import BulkPaymentProcessor from "./pages/payments/BulkPaymentProcessor";
import BulkTransactionProcessing from "./pages/payments/BulkTransactionProcessing";
import BulkTransactionProcessor from "./pages/payments/BulkTransactionProcessor";
import BulkOperationsPage from "./pages/payments/BulkOperationsPage";
import BatchProcessingPage from "./pages/payments/BatchProcessingPage";
import MultiChannelPaymentOrchNew from "./pages/payments/MultiChannelPaymentOrch";
import RateLimitDashboard from "./pages/payments/RateLimitDashboard";
import RateLimitEnginePage from "./pages/payments/RateLimitEnginePage";
import AdvancedRateLimiterPage from "./pages/payments/AdvancedRateLimiterPage";
import AutomatedSettlementScheduler from "./pages/payments/AutomatedSettlementScheduler";
import TransactionCsvExport from "./pages/payments/TransactionCsvExport";
import TransactionDisputeResolutionPage from "./pages/payments/TransactionDisputeResolutionPage";
import TransactionEnrichmentService from "./pages/payments/TransactionEnrichmentService";
import TransactionExportEngine from "./pages/payments/TransactionExportEngine";
import TransactionGraphAnalyzer from "./pages/payments/TransactionGraphAnalyzer";
import TransactionLimitsEnginePage from "./pages/payments/TransactionLimitsEnginePage";
import TransactionMapVizPage from "./pages/payments/TransactionMapVizPage";
import TransactionReceiptGenerator from "./pages/payments/TransactionReceiptGenerator";
import TransactionReconciliationPage from "./pages/payments/TransactionReconciliationPage";
import TransactionReversalManager from "./pages/payments/TransactionReversalManager";
import TransactionReversalWorkflowPage from "./pages/payments/TransactionReversalWorkflowPage";
import TransactionVelocityMonitor from "./pages/payments/TransactionVelocityMonitor";
import TxMonitorPage from "./pages/payments/TxMonitorPage";
import TxVelocityMonitor from "./pages/payments/TxVelocityMonitor";
import RealtimeTxMonitorPage from "./pages/payments/RealtimeTxMonitorPage";
import RealtimeDashboardWidgetsPage from "./pages/payments/RealtimeDashboardWidgetsPage";
import RealtimeWebSocketFeeds from "./pages/payments/RealtimeWebSocketFeeds";
import ReconciliationEnginePage from "./pages/payments/ReconciliationEnginePage";

// ── Notifications ────────────────────────────────────────────────────────────
import NotificationCenterPage from "./pages/notifications/NotificationCenterPage";
import NotificationInbox from "./pages/notifications/NotificationInbox";
import NotificationOrchestratorPage from "./pages/notifications/NotificationOrchestratorPage";
import NotificationPreferenceMatrix from "./pages/notifications/NotificationPreferenceMatrix";
import NotificationPreferences from "./pages/notifications/NotificationPreferences";
import NotificationTemplateManager from "./pages/notifications/NotificationTemplateManager";
import MultiChannelNotificationHub from "./pages/notifications/MultiChannelNotificationHub";
import BroadcastManager from "./pages/notifications/BroadcastManager";
import WhatsAppChannelPage from "./pages/notifications/WhatsAppChannelPage";
import BulkNotifSender from "./pages/notifications/BulkNotifSender";
import PushNotificationConfig from "./pages/notifications/PushNotificationConfig";
import RealtimeNotificationsPage from "./pages/notifications/RealtimeNotificationsPage";
import NotificationAnalytics from "./pages/notifications/NotificationAnalytics";
import AlertNotificationPreferences from "./pages/notifications/AlertNotificationPreferences";

// ── Platform & Infrastructure ────────────────────────────────────────────────
import PlatformHub from "./pages/platform/PlatformHub";
import PlatformHealthPage from "./pages/platform/PlatformHealthPage";
import PlatformChangelogPage from "./pages/platform/PlatformChangelogPage";
import InfrastructureDashboard from "./pages/platform/InfrastructureDashboard";
import BackupDRPage from "./pages/platform/BackupDRPage";
import BackupDisasterRecoveryPage from "./pages/platform/BackupDisasterRecoveryPage";
import ConfigManagementPage from "./pages/platform/ConfigManagementPage";
import SystemConfigManager from "./pages/platform/SystemConfigManager";
import SystemHealth from "./pages/platform/SystemHealth";
import SystemHealthDashboard from "./pages/platform/SystemHealthDashboard";
import SystemHealthDashboardPage from "./pages/platform/SystemHealthDashboardPage";
import SystemStatus from "./pages/platform/SystemStatus";
import CapacityPlanningPage from "./pages/platform/CapacityPlanningPage";
import FeatureFlagsPage from "./pages/platform/FeatureFlagsPage";
import NetworkQualityHeatmap from "./pages/platform/NetworkQualityHeatmap";
import NetworkStatusDashboard from "./pages/platform/NetworkStatusDashboard";
import NetworkDiagnosticPage from "./pages/platform/NetworkDiagnosticPage";
import TemporalWorkflowMonitor from "./pages/platform/TemporalWorkflowMonitor";
import ResilienceMonitor from "./pages/platform/ResilienceMonitor";
import MiddlewareServiceManager from "./pages/platform/MiddlewareServiceManager";
import MigrationToolsPage from "./pages/platform/MigrationToolsPage";
import VaultSecretsManager from "./pages/platform/VaultSecretsManager";
import SimOrchestratorDashboardNew from "./pages/platform/SimOrchestratorDashboard";
import DistributedTracingDash from "./pages/platform/DistributedTracingDash";
import EventDrivenArchPage from "./pages/platform/EventDrivenArchPage";

// ── Fraud & Incidents ────────────────────────────────────────────────────────
import FraudDashboard from "./pages/fraud/FraudDashboard";
import RansomwareAlertDashboard from "./pages/fraud/RansomwareAlertDashboard";
import IncidentCommandCenter from "./pages/fraud/IncidentCommandCenter";
import IncidentPlaybook from "./pages/fraud/IncidentPlaybook";
import IncidentManagementPage from "./pages/fraud/IncidentManagementPage";

// ── KYC & Regulatory ────────────────────────────────────────────────────────
import KycDocumentManagementPage from "./pages/kyc/KycDocumentManagementPage";
import KycVerificationWorkflow from "./pages/kyc/KycVerificationWorkflow";
import KycWorkflow from "./pages/kyc/KycWorkflow";
import CbnReportingDashboard from "./pages/kyc/CbnReportingDashboard";
import RegulatoryReportGenerator from "./pages/kyc/RegulatoryReportGenerator";
import RegulatoryCompliancePage from "./pages/kyc/RegulatoryCompliancePage";
import RegulatoryFilingAutomation from "./pages/kyc/RegulatoryFilingAutomation";
import RegulatoryReportingPage from "./pages/kyc/RegulatoryReportingPage";
import AutomatedComplianceChecker from "./pages/kyc/AutomatedComplianceChecker";

// ── Merchant (extended) ──────────────────────────────────────────────────────
import MerchantAcquirerGateway from "./pages/merchant/MerchantAcquirerGateway";
import MerchantOnboardingPortal from "./pages/merchant/MerchantOnboardingPortal";
import MerchantPaymentsPage from "./pages/merchant/MerchantPaymentsPage";
import MerchantPayoutSettlementPage from "./pages/merchant/MerchantPayoutSettlementPage";

// ── Customer (extended) ──────────────────────────────────────────────────────
import Customer360View from "./pages/customers/Customer360View";
import CustomerDatabasePage from "./pages/customers/CustomerDatabasePage";
import CustomerFeedbackNps from "./pages/customers/CustomerFeedbackNps";
import CustomerJourneyMapper from "./pages/customers/CustomerJourneyMapper";
import CustomerPortal from "./pages/customers/CustomerPortal";
import CustomerSurveys from "./pages/customers/CustomerSurveys";
import CustomerWallet from "./pages/customers/CustomerWallet";
import CustomerWalletSystem from "./pages/customers/CustomerWalletSystem";

// ── Webhooks & Developer (extended) ─────────────────────────────────────────
import ApiDocs from "./pages/webhooks/ApiDocs";
import ApiGatewayPage from "./pages/webhooks/ApiGatewayPage";
import GraphqlFederationPage from "./pages/webhooks/GraphqlFederationPage";
import GraphqlSubscriptionGateway from "./pages/webhooks/GraphqlSubscriptionGateway";
import WebhookConfig from "./pages/webhooks/WebhookConfig";
import WebhookDeliveryMonitor from "./pages/webhooks/WebhookDeliveryMonitor";
import WebhookDeliverySystem from "./pages/webhooks/WebhookDeliverySystem";
import WebhookDeliveryViewer from "./pages/webhooks/WebhookDeliveryViewer";
import WebhookManagementPage from "./pages/webhooks/WebhookManagementPage";
import WebhookManager from "./pages/webhooks/WebhookManager";
import WebhookMgmtConsole from "./pages/webhooks/WebhookMgmtConsole";

// ── Security ─────────────────────────────────────────────────────────────────
import BiometricAuthGateway from "./pages/security/BiometricAuthGateway";
import BiometricAuthPage from "./pages/security/BiometricAuthPage";
import MfaManager from "./pages/security/MfaManager";
import SessionManager from "./pages/security/SessionManager";
import PBACManagement from "./pages/security/PBACManagement";
import DecentralizedIdentityManager from "./pages/security/DecentralizedIdentityManager";
import DigitalIdentityLayer from "./pages/security/DigitalIdentityLayer";

// ── Emerging & Niche ─────────────────────────────────────────────────────────
import CbdcIntegrationGateway from "./pages/emerging/CbdcIntegrationGateway";
import StablecoinRails from "./pages/emerging/StablecoinRails";
import TokenizedAssets from "./pages/emerging/TokenizedAssets";
import SmartContractPayment from "./pages/emerging/SmartContractPayment";
import CarbonCreditMarketplace from "./pages/emerging/CarbonCreditMarketplace";
import HealthInsuranceMicro from "./pages/emerging/HealthInsuranceMicro";
import EducationPayments from "./pages/emerging/EducationPayments";
import AgritechPayments from "./pages/emerging/AgritechPayments";
import WearablePayments from "./pages/emerging/WearablePayments";
import NfcTapToPay from "./pages/emerging/NfcTapToPay";
import OpenBankingApi from "./pages/emerging/OpenBankingApi";
import SatelliteConnectivity from "./pages/emerging/SatelliteConnectivity";
import IotSmartPos from "./pages/emerging/IotSmartPos";
import DigitalTwinSimulator from "./pages/emerging/DigitalTwinSimulator";
import OfflinePosMode from "./pages/emerging/OfflinePosMode";
import VoiceCommandPos from "./pages/emerging/VoiceCommandPos";
import POSFirmwareOTA from "./pages/emerging/POSFirmwareOTA";
import POSShell from "./pages/emerging/POSShell";

// ── Lazy-loaded pages (new additions) ────────────────────────────────────────
const FraudDashboardLazy = React.lazy(() => import("./pages/FraudDashboard"));
const AdminPanel = React.lazy(() => import("./pages/AdminPanel"));
const SupervisorDashboard = React.lazy(() => import("./pages/SupervisorDashboard"));
const ManagementPortal = React.lazy(() => import("./pages/ManagementPortal"));
const AgentPortalNew = React.lazy(() => import("./pages/AgentPortal"));
const CustomerPortalNew = React.lazy(() => import("./pages/CustomerPortal"));
const SuperAdminPortal = React.lazy(() => import("./pages/SuperAdminPortal"));
const PlatformHubNew = React.lazy(() => import("./pages/PlatformHub"));
const AnalyticsDashboardNew = React.lazy(() => import("./pages/AnalyticsDashboard"));
const MerchantPortalNew = React.lazy(() => import("./pages/MerchantPortal"));
const SystemHealthNew = React.lazy(() => import("./pages/SystemHealth"));
const SystemHealthDashboardNew = React.lazy(() => import("./pages/SystemHealthDashboard"));
const LakehouseAnalyticsNew = React.lazy(() => import("./pages/LakehouseAnalytics"));
const WebhookManagerNew = React.lazy(() => import("./pages/WebhookManager"));
const CommissionPayoutsNew = React.lazy(() => import("./pages/CommissionPayouts"));
const AgentOnboardingNew = React.lazy(() => import("./pages/AgentOnboarding"));
const SettlementReconciliationNew = React.lazy(() => import("./pages/SettlementReconciliation"));
const ReferralProgram = React.lazy(() => import("./pages/ReferralProgram"));
const AuditLogViewerNew = React.lazy(() => import("./pages/AuditLogViewer"));
const InfrastructureDashboardNew = React.lazy(() => import("./pages/InfrastructureDashboard"));
const LoyaltySystem = React.lazy(() => import("./pages/LoyaltySystem"));
const LiveChatSupportNew = React.lazy(() => import("./pages/LiveChatSupport"));
const AgentPerformanceNew = React.lazy(() => import("./pages/AgentPerformance"));
const CustomerWalletNew = React.lazy(() => import("./pages/CustomerWallet"));
const NotificationPreferencesNew = React.lazy(() => import("./pages/NotificationPreferences"));
const MultiCurrencyNew = React.lazy(() => import("./pages/MultiCurrency"));
const ComplianceSchedulingNew = React.lazy(() => import("./pages/ComplianceScheduling"));
const AuditExportNew = React.lazy(() => import("./pages/AuditExport"));
const WebhookDeliveryViewerNew = React.lazy(() => import("./pages/WebhookDeliveryViewer"));
const GeofenceZoneEditor = React.lazy(() => import("./pages/GeofenceZoneEditor"));
const ApiKeyManagementNew = React.lazy(() => import("./pages/ApiKeyManagement"));
const KycWorkflowNew = React.lazy(() => import("./pages/KycWorkflow"));
const OnboardingWizard = React.lazy(() => import("./pages/OnboardingWizard"));
const CommissionConfigNew = React.lazy(() => import("./pages/CommissionConfig"));
const RateAlerts = React.lazy(() => import("./pages/RateAlerts"));
const NotificationInboxNew = React.lazy(() => import("./pages/NotificationInbox"));
const NotificationPreferenceMatrixNew = React.lazy(() => import("./pages/NotificationPreferenceMatrix"));
const WebhookConfigNew = React.lazy(() => import("./pages/WebhookConfig"));
const BatchOperations = React.lazy(() => import("./pages/BatchOperations"));
const AdminAnalyticsDashboard = React.lazy(() => import("./pages/AdminAnalyticsDashboard"));
const BroadcastManagerNew = React.lazy(() => import("./pages/BroadcastManager"));
const ScheduledReports = React.lazy(() => import("./pages/ScheduledReports"));
const UserNotifSettings = React.lazy(() => import("./pages/UserNotifSettings"));
const DataThresholdAlerts = React.lazy(() => import("./pages/DataThresholdAlerts"));
const SharedLayoutGallery = React.lazy(() => import("./pages/SharedLayoutGallery"));
const ReportTemplateDesignerNew = React.lazy(() => import("./pages/ReportTemplateDesigner"));
const EscalationChains = React.lazy(() => import("./pages/EscalationChains"));
const NotificationAnalyticsNew = React.lazy(() => import("./pages/NotificationAnalytics"));
const UserQuietHours = React.lazy(() => import("./pages/UserQuietHours"));
const NotificationTemplateManagerNew = React.lazy(() => import("./pages/NotificationTemplateManager"));
const SystemConfigManagerNew = React.lazy(() => import("./pages/SystemConfigManager"));
const PaymentNotificationSystemNew = React.lazy(() => import("./pages/PaymentNotificationSystem"));
const DatabaseVisualization = React.lazy(() => import("./pages/DatabaseVisualization"));
const MiddlewareServiceManagerNew = React.lazy(() => import("./pages/MiddlewareServiceManager"));
const SkillCreatorIntegration = React.lazy(() => import("./pages/SkillCreatorIntegration"));
const PaymentReconciliationNew = React.lazy(() => import("./pages/PaymentReconciliation"));
const AgentPerformanceAnalyticsNew = React.lazy(() => import("./pages/AgentPerformanceAnalytics"));
const ComplianceReportingNew = React.lazy(() => import("./pages/ComplianceReporting"));
const CustomerFeedbackNpsNew = React.lazy(() => import("./pages/CustomerFeedbackNps"));
const MultiCurrencyExchangeNew = React.lazy(() => import("./pages/MultiCurrencyExchange"));
const DisputeWorkflowEngineNew = React.lazy(() => import("./pages/DisputeWorkflowEngine"));
const BulkPaymentProcessorNew = React.lazy(() => import("./pages/BulkPaymentProcessor"));
const AgentHierarchyTerritory = React.lazy(() => import("./pages/AgentHierarchyTerritory"));
const FinancialReportingSuiteNew = React.lazy(() => import("./pages/FinancialReportingSuite"));
const WebhookDeliverySystemNew = React.lazy(() => import("./pages/WebhookDeliverySystem"));
const PlatformConfigCenter = React.lazy(() => import("./pages/PlatformConfigCenter"));
const BankAccountManagementPage = React.lazy(() => import("./pages/BankAccountManagementPage"));
const KycDocumentManagementPageNew = React.lazy(() => import("./pages/KycDocumentManagementPage"));
const FloatReconciliationPageNew = React.lazy(() => import("./pages/FloatReconciliationPage"));
const CustomerDatabasePageNew = React.lazy(() => import("./pages/CustomerDatabasePage"));
const ReversalApprovalPageNew = React.lazy(() => import("./pages/ReversalApprovalPage"));
const CommissionClawbackPageNew = React.lazy(() => import("./pages/CommissionClawbackPage"));
const PnlReportPageNew = React.lazy(() => import("./pages/PnlReportPage"));
const TransactionLimitsEnginePageNew = React.lazy(() => import("./pages/TransactionLimitsEnginePage"));
const RegulatoryCompliancePageNew = React.lazy(() => import("./pages/RegulatoryCompliancePage"));
const SystemHealthDashboardPageNew = React.lazy(() => import("./pages/SystemHealthDashboardPage"));
const AgentSuspensionWorkflowPage = React.lazy(() => import("./pages/AgentSuspensionWorkflowPage"));
const SessionManagerNew = React.lazy(() => import("./pages/SessionManager"));
const DataExportCenterNew = React.lazy(() => import("./pages/DataExportCenter"));
const PlatformChangelog = React.lazy(() => import("./pages/PlatformChangelog"));
const BulkNotifSenderNew = React.lazy(() => import("./pages/BulkNotifSender"));
const RetryQueueViewerNew = React.lazy(() => import("./pages/RetryQueueViewer"));
const RateLimitDashboardNew = React.lazy(() => import("./pages/RateLimitDashboard"));
const ServiceHealthAggregator = React.lazy(() => import("./pages/ServiceHealthAggregator"));
const CacheManagement = React.lazy(() => import("./pages/CacheManagement"));
const PartnerOnboarding = React.lazy(() => import("./pages/PartnerOnboarding"));
const TenantAdminDashboard = React.lazy(() => import("./pages/TenantAdminDashboard"));
const InviteCodeManager = React.lazy(() => import("./pages/InviteCodeManager"));
const GdprDashboardNew = React.lazy(() => import("./pages/GdprDashboard"));
const TigerBeetleLedgerNew = React.lazy(() => import("./pages/TigerBeetleLedger"));
const TemporalWorkflowMonitorNew = React.lazy(() => import("./pages/TemporalWorkflowMonitor"));
const VaultSecretsManagerNew = React.lazy(() => import("./pages/VaultSecretsManager"));
const ResilienceMonitorNew = React.lazy(() => import("./pages/ResilienceMonitor"));
const SimOrchestratorDashboard = React.lazy(() => import("./pages/SimOrchestratorDashboard"));
const MqttBridgeDashboard = React.lazy(() => import("./pages/MqttBridgeDashboard"));
const PushNotificationConfigNew = React.lazy(() => import("./pages/PushNotificationConfig"));
const AgentManagementDashboardNew = React.lazy(() => import("./pages/AgentManagementDashboard"));
const BusinessRulesDashboard = React.lazy(() => import("./pages/BusinessRulesDashboard"));
const AnnouncementReactions = React.lazy(() => import("./pages/AnnouncementReactions"));
const WeeklyReportsNew = React.lazy(() => import("./pages/WeeklyReports"));
const ReportComparisonNew = React.lazy(() => import("./pages/ReportComparison"));
const ThresholdManager = React.lazy(() => import("./pages/ThresholdManager"));
const EndpointRateLimits = React.lazy(() => import("./pages/EndpointRateLimits"));
const WebhookDeliveryMonitorNew = React.lazy(() => import("./pages/WebhookDeliveryMonitor"));
const AgentPerformanceScoringNew = React.lazy(() => import("./pages/AgentPerformanceScoring"));
const DisputeAutoRulesNew = React.lazy(() => import("./pages/DisputeAutoRules"));
const KycVerificationWorkflowNew = React.lazy(() => import("./pages/KycVerificationWorkflow"));
const ProductionReadinessChecklistNew = React.lazy(() => import("./pages/ProductionReadinessChecklist"));
const ScheduledEmailDelivery = React.lazy(() => import("./pages/ScheduledEmailDelivery"));
const GlobalSearchPage = React.lazy(() => import("./pages/GlobalSearchPage"));
const UserGuide = React.lazy(() => import("./pages/UserGuide"));
const PaymentsNew = React.lazy(() => import("./pages/Payments"));
const PaymentSuccess = React.lazy(() => import("./pages/PaymentSuccess"));
const PaymentCancel = React.lazy(() => import("./pages/PaymentCancel"));
const AdminDashboardPage = React.lazy(() => import("./pages/AdminDashboard"));
const AdminUserManagement = React.lazy(() => import("./pages/AdminUserManagement"));
const AdminSystemHealth = React.lazy(() => import("./pages/AdminSystemHealth"));
const AdminLivenessDeviceAnalytics = React.lazy(() => import("./pages/AdminLivenessDeviceAnalytics"));
const TransactionAnalyticsNew = React.lazy(() => import("./pages/TransactionAnalytics"));
const OfflineQueueDashboard = React.lazy(() => import("./pages/OfflineQueueDashboard"));
const RansomwareAlertDashboardNew = React.lazy(() => import("./pages/RansomwareAlertDashboard"));
const PBACManagementNew = React.lazy(() => import("./pages/PBACManagement"));
const AlertNotificationPreferencesNew = React.lazy(() => import("./pages/AlertNotificationPreferences"));
const NetworkQualityHeatmapNew = React.lazy(() => import("./pages/NetworkQualityHeatmap"));
const VideoTutorials = React.lazy(() => import("./pages/VideoTutorials"));
const FeedbackAnalytics = React.lazy(() => import("./pages/FeedbackAnalytics"));
const ApiDocsNew = React.lazy(() => import("./pages/ApiDocs"));
const SystemStatusNew = React.lazy(() => import("./pages/SystemStatus"));
const AuditTrailPage = React.lazy(() => import("./pages/AuditTrailPage"));
const UssdGateway = React.lazy(() => import("./pages/UssdGateway"));
const MobileMoneyPage = React.lazy(() => import("./pages/MobileMoneyPage"));
const AgentHierarchyPageNew = React.lazy(() => import("./pages/AgentHierarchyPage"));
const CommissionEnginePageNew = React.lazy(() => import("./pages/CommissionEnginePage"));
const BulkOperationsPageNew = React.lazy(() => import("./pages/BulkOperationsPage"));
const GeoFencingPageNew = React.lazy(() => import("./pages/GeoFencingPage"));
const BiometricAuthPageNew = React.lazy(() => import("./pages/BiometricAuthPage"));
const OfflineSyncPage = React.lazy(() => import("./pages/OfflineSyncPage"));
const WhatsAppChannelPageNew = React.lazy(() => import("./pages/WhatsAppChannelPage"));
const MerchantPaymentsPageNew = React.lazy(() => import("./pages/MerchantPaymentsPage"));
const BillPaymentsPage = React.lazy(() => import("./pages/BillPaymentsPage"));
const AirtimeVendingPageNew = React.lazy(() => import("./pages/AirtimeVendingPage"));
const LoanDisbursementPage = React.lazy(() => import("./pages/LoanDisbursementPage"));
const InsuranceProductsPage = React.lazy(() => import("./pages/InsuranceProductsPage"));
const SavingsProductsPage = React.lazy(() => import("./pages/SavingsProductsPage"));
const ReferralProgramPage = React.lazy(() => import("./pages/ReferralProgramPage"));
const CardRequestPageNew = React.lazy(() => import("./pages/CardRequestPage"));
const AccountOpeningPage = React.lazy(() => import("./pages/AccountOpeningPage"));
const TaxCollectionPageNew = React.lazy(() => import("./pages/TaxCollectionPage"));
const PensionCollectionPage = React.lazy(() => import("./pages/PensionCollectionPage"));
const RemittancePage = React.lazy(() => import("./pages/RemittancePage"));
const QdrantVectorSearchPage = React.lazy(() => import("./pages/QdrantVectorSearchPage"));
const FalkorDBGraphPage = React.lazy(() => import("./pages/FalkorDBGraphPage"));
const CocoIndexPipelinePage = React.lazy(() => import("./pages/CocoIndexPipelinePage"));
const OllamaLLMPage = React.lazy(() => import("./pages/OllamaLLMPage"));
const ARTRobustnessPage = React.lazy(() => import("./pages/ARTRobustnessPage"));
const LakehouseAiDashboardNew = React.lazy(() => import("./pages/LakehouseAiDashboard"));
const MLScoringDashboardNew = React.lazy(() => import("./pages/MLScoringDashboard"));
const AIMonitoringDashboard = React.lazy(() => import("./pages/AIMonitoringDashboard"));
const FraudReportPageNew = React.lazy(() => import("./pages/FraudReportPage"));
const ComplianceChatbotPageNew = React.lazy(() => import("./pages/ComplianceChatbotPage"));
const ApacheNifiPageNew = React.lazy(() => import("./pages/ApacheNifiPage"));
const DbtIntegrationPage = React.lazy(() => import("./pages/DbtIntegrationPage"));
const ApacheAirflowPageNew = React.lazy(() => import("./pages/ApacheAirflowPage"));
const WebSocketServicePageNew = React.lazy(() => import("./pages/WebSocketServicePage"));
const ReportSchedulerPageNew = React.lazy(() => import("./pages/ReportSchedulerPage"));
const EventDrivenArchPageNew = React.lazy(() => import("./pages/EventDrivenArchPage"));
const AdvancedNotificationsPage = React.lazy(() => import("./pages/AdvancedNotificationsPage"));
const SecurityDashboardPage = React.lazy(() => import("./pages/SecurityDashboardPage"));
const FraudRealtimeVizPageNew = React.lazy(() => import("./pages/FraudRealtimeVizPage"));
const PipelineMonitoringPage = React.lazy(() => import("./pages/PipelineMonitoringPage"));
const ApiGatewayPageNew = React.lazy(() => import("./pages/ApiGatewayPage"));
const BackupDRPageNew = React.lazy(() => import("./pages/BackupDRPage"));
const PerformanceProfilerPage = React.lazy(() => import("./pages/PerformanceProfilerPage"));
const MultiTenancyPage = React.lazy(() => import("./pages/MultiTenancyPage"));
const WebhookManagementPageNew = React.lazy(() => import("./pages/WebhookManagementPage"));
const DataExportImportPageNew = React.lazy(() => import("./pages/DataExportImportPage"));
const SlaManagementPage = React.lazy(() => import("./pages/SlaManagementPage"));
const CapacityPlanningPageNew = React.lazy(() => import("./pages/CapacityPlanningPage"));
const IncidentManagementPageNew = React.lazy(() => import("./pages/IncidentManagementPage"));
const FeatureFlagsPageNew = React.lazy(() => import("./pages/FeatureFlagsPage"));
const OpenTelemetryPageNew = React.lazy(() => import("./pages/OpenTelemetryPage"));
const AdvancedBiReportingPageNew = React.lazy(() => import("./pages/AdvancedBiReportingPage"));
const WorkflowAutomationPage = React.lazy(() => import("./pages/WorkflowAutomationPage"));
const NotificationCenterPageNew = React.lazy(() => import("./pages/NotificationCenterPage"));
const HelpDeskPageNew = React.lazy(() => import("./pages/HelpDeskPage"));
const DataQualityPageNew = React.lazy(() => import("./pages/DataQualityPage"));
const ConfigManagementPageNew = React.lazy(() => import("./pages/ConfigManagementPage"));
const ServiceMeshPage = React.lazy(() => import("./pages/ServiceMeshPage"));
const ComplianceAutomationPageNew = React.lazy(() => import("./pages/ComplianceAutomationPage"));
const Customer360PageNew = React.lazy(() => import("./pages/Customer360Page"));
const RealtimeNotificationsPageNew = React.lazy(() => import("./pages/RealtimeNotificationsPage"));
const DragDropReportBuilderPageNew = React.lazy(() => import("./pages/DragDropReportBuilderPage"));
const GraphqlFederationPageNew = React.lazy(() => import("./pages/GraphqlFederationPage"));
const ApiVersioningPageNew = React.lazy(() => import("./pages/ApiVersioningPage"));
const AdvancedRateLimiterPageNew = React.lazy(() => import("./pages/AdvancedRateLimiterPage"));
const RealtimeDashboardWidgetsPageNew = React.lazy(() => import("./pages/RealtimeDashboardWidgetsPage"));
const AgentScorecardPageNew = React.lazy(() => import("./pages/AgentScorecardPage"));
const DisputeResolutionPageNew = React.lazy(() => import("./pages/DisputeResolutionPage"));
const RegulatorySandboxPageNew = React.lazy(() => import("./pages/RegulatorySandboxPage"));
const MultiCurrencyPageNew = React.lazy(() => import("./pages/MultiCurrencyPage"));
const DocumentManagementPage = React.lazy(() => import("./pages/DocumentManagementPage"));
const AgentTrainingPageNew = React.lazy(() => import("./pages/AgentTrainingPage"));
const RevenueAnalyticsPage = React.lazy(() => import("./pages/RevenueAnalyticsPage"));
const PlatformHealthPageNew = React.lazy(() => import("./pages/PlatformHealthPage"));
const BatchProcessingPageNew = React.lazy(() => import("./pages/BatchProcessingPage"));
const IntegrationMarketplacePage = React.lazy(() => import("./pages/IntegrationMarketplacePage"));
const MobileApiLayerPage = React.lazy(() => import("./pages/MobileApiLayerPage"));
const AutomatedTestingFrameworkPageNew = React.lazy(() => import("./pages/AutomatedTestingFrameworkPage"));
const TransactionMapVizPageNew = React.lazy(() => import("./pages/TransactionMapVizPage"));
const ReportBuilderTemplatesPageNew = React.lazy(() => import("./pages/ReportBuilderTemplatesPage"));
const NLAnalyticsQueryPageNew = React.lazy(() => import("./pages/NLAnalyticsQueryPage"));
const BankingWorkflowPatternsPage = React.lazy(() => import("./pages/BankingWorkflowPatternsPage"));
const AgentOnboardingWizardPageNew = React.lazy(() => import("./pages/AgentOnboardingWizardPage"));
const TransactionReconciliationPageNew = React.lazy(() => import("./pages/TransactionReconciliationPage"));
const ChargebackManagementPageNew = React.lazy(() => import("./pages/ChargebackManagementPage"));
const RegulatoryReportingPageNew = React.lazy(() => import("./pages/RegulatoryReportingPage"));
const TerritoryManagementPage = React.lazy(() => import("./pages/TerritoryManagementPage"));
const DynamicPricingPage = React.lazy(() => import("./pages/DynamicPricingPage"));
const LoyaltyProgramPage = React.lazy(() => import("./pages/LoyaltyProgramPage"));
const FraudCaseManagementPageNew = React.lazy(() => import("./pages/FraudCaseManagementPage"));
const TerminalFleetPage = React.lazy(() => import("./pages/TerminalFleetPage"));
const FinancialReconciliationPageNew = React.lazy(() => import("./pages/FinancialReconciliationPage"));
const ApiAnalyticsPageNew = React.lazy(() => import("./pages/ApiAnalyticsPage"));
const AgentCommunicationHubPage = React.lazy(() => import("./pages/AgentCommunicationHubPage"));
const DisputeArbitrationPageNew = React.lazy(() => import("./pages/DisputeArbitrationPage"));
const ComplianceTrainingPageNew = React.lazy(() => import("./pages/ComplianceTrainingPage"));
const MigrationToolsPageNew = React.lazy(() => import("./pages/MigrationToolsPage"));
const AuditLogViewerPageNew = React.lazy(() => import("./pages/AuditLogViewerPage"));
const TransactionCsvExportNew = React.lazy(() => import("./pages/TransactionCsvExport"));
const TransactionMapLoadingNew = React.lazy(() => import("./pages/TransactionMapLoading"));
const NlFinancialQueryNew = React.lazy(() => import("./pages/NlFinancialQuery"));
const WhiteLabelOnboarding = React.lazy(() => import("./pages/WhiteLabelOnboarding"));
const WhiteLabelBranding = React.lazy(() => import("./pages/WhiteLabelBranding"));
const WhiteLabelApproval = React.lazy(() => import("./pages/WhiteLabelApproval"));
const PartnerSelfService = React.lazy(() => import("./pages/PartnerSelfService"));
const TransactionExportEngineNew = React.lazy(() => import("./pages/TransactionExportEngine"));
const AdvancedLoadingStates = React.lazy(() => import("./pages/AdvancedLoadingStates"));
const FinancialNlEngine = React.lazy(() => import("./pages/FinancialNlEngine"));
const PartnerRevenueSharing = React.lazy(() => import("./pages/PartnerRevenueSharing"));
const AgentGamificationNew = React.lazy(() => import("./pages/AgentGamification"));
const BulkTransactionProcessingNew = React.lazy(() => import("./pages/BulkTransactionProcessing"));
const Customer360ViewNew = React.lazy(() => import("./pages/Customer360View"));
const WebhookMgmtConsoleNew = React.lazy(() => import("./pages/WebhookMgmtConsole"));
const PlatformFeatureFlags = React.lazy(() => import("./pages/PlatformFeatureFlags"));
const SlaMonitoringDash = React.lazy(() => import("./pages/SlaMonitoringDash"));
const DataRetentionPolicyNew = React.lazy(() => import("./pages/DataRetentionPolicy"));
const AdvancedSearchFiltering = React.lazy(() => import("./pages/AdvancedSearchFiltering"));
const E2ETestFramework = React.lazy(() => import("./pages/E2ETestFramework"));
const DbSchemaPush = React.lazy(() => import("./pages/DbSchemaPush"));
const AgentCommissionCalcNew = React.lazy(() => import("./pages/AgentCommissionCalc"));
const MccManager = React.lazy(() => import("./pages/MccManager"));
const SettlementBatchProcessorNew = React.lazy(() => import("./pages/SettlementBatchProcessor"));
const CardBinLookupNew = React.lazy(() => import("./pages/CardBinLookup"));
const TransactionVelocityMonitorNew = React.lazy(() => import("./pages/TransactionVelocityMonitor"));
const MerchantRiskScoringNew = React.lazy(() => import("./pages/MerchantRiskScoring"));
const PaymentGatewayRouterNew = React.lazy(() => import("./pages/PaymentGatewayRouter"));
const AgentFloatForecasting = React.lazy(() => import("./pages/AgentFloatForecasting"));
const MultiTenantIsolation = React.lazy(() => import("./pages/MultiTenantIsolation"));
const PlatformHealthDash = React.lazy(() => import("./pages/PlatformHealthDash"));
const AutomatedComplianceCheckerNew = React.lazy(() => import("./pages/AutomatedComplianceChecker"));
const TransactionFeeCalcNew = React.lazy(() => import("./pages/TransactionFeeCalc"));
const AgentNetworkTopology = React.lazy(() => import("./pages/AgentNetworkTopology"));
const CustomerDisputePortalNew = React.lazy(() => import("./pages/CustomerDisputePortal"));
const RevenueLeakageDetectorNew = React.lazy(() => import("./pages/RevenueLeakageDetector"));
const ApiRateLimiterDashNew = React.lazy(() => import("./pages/ApiRateLimiterDash"));
const OperationalRunbook = React.lazy(() => import("./pages/OperationalRunbook"));
const PlatformMetricsExporter = React.lazy(() => import("./pages/PlatformMetricsExporter"));
const RealtimeWebSocketFeedsNew = React.lazy(() => import("./pages/RealtimeWebSocketFeeds"));
const MerchantOnboardingPortalNew = React.lazy(() => import("./pages/MerchantOnboardingPortal"));
const PaymentLinkGeneratorNew = React.lazy(() => import("./pages/PaymentLinkGenerator"));
const DisputeMediationAINew = React.lazy(() => import("./pages/DisputeMediationAI"));
const AgentPerformanceLeaderboardNew = React.lazy(() => import("./pages/AgentPerformanceLeaderboard"));
const AutomatedSettlementSchedulerNew = React.lazy(() => import("./pages/AutomatedSettlementScheduler"));
const CustomerWalletSystemNew = React.lazy(() => import("./pages/CustomerWalletSystem"));
const MerchantAnalyticsDashNew = React.lazy(() => import("./pages/MerchantAnalyticsDash"));
const POSFirmwareOTANew = React.lazy(() => import("./pages/POSFirmwareOTA"));
const TransactionReceiptGeneratorNew = React.lazy(() => import("./pages/TransactionReceiptGenerator"));
const AgentLoanAdvanceNew = React.lazy(() => import("./pages/AgentLoanAdvance"));
const RegulatoryFilingAutomationNew = React.lazy(() => import("./pages/RegulatoryFilingAutomation"));
const CustomerSegmentationEngineNew = React.lazy(() => import("./pages/CustomerSegmentationEngine"));
const IncidentCommandCenterNew = React.lazy(() => import("./pages/IncidentCommandCenter"));
const PlatformABTesting = React.lazy(() => import("./pages/PlatformABTesting"));
const TransactionEnrichmentServiceNew = React.lazy(() => import("./pages/TransactionEnrichmentService"));
const AgentInventoryMgmtNew = React.lazy(() => import("./pages/AgentInventoryMgmt"));
const RevenueForecastingEngineNew = React.lazy(() => import("./pages/RevenueForecastingEngine"));
const PlatformRecommendations = React.lazy(() => import("./pages/PlatformRecommendations"));
const PublishReadinessCheckerNew = React.lazy(() => import("./pages/PublishReadinessChecker"));
const DbSchemaMigrationManager = React.lazy(() => import("./pages/DbSchemaMigrationManager"));
const GraphqlSubscriptionGatewayNew = React.lazy(() => import("./pages/GraphqlSubscriptionGateway"));
const AiCashFlowPredictor = React.lazy(() => import("./pages/AiCashFlowPredictor"));
const BlockchainAuditTrailNew = React.lazy(() => import("./pages/BlockchainAuditTrail"));
const VoiceCommandPosNew = React.lazy(() => import("./pages/VoiceCommandPos"));
const SocialCommerceGatewayNew = React.lazy(() => import("./pages/SocialCommerceGateway"));
const EsgCarbonTrackerNew = React.lazy(() => import("./pages/ESGCarbonTracker"));
const DistributedTracingDashNew = React.lazy(() => import("./pages/DistributedTracingDash"));
const CanaryReleaseManager = React.lazy(() => import("./pages/CanaryReleaseManager"));
const ChaosEngineeringConsoleNew = React.lazy(() => import("./pages/ChaosEngineeringConsole"));
const ConnectionPoolMonitorNew = React.lazy(() => import("./pages/ConnectionPoolMonitor"));
const CqrsEventStore = React.lazy(() => import("./pages/CqrsEventStore"));
const DigitalTwinSimulatorNew = React.lazy(() => import("./pages/DigitalTwinSimulator"));
const CbdcIntegrationGatewayNew = React.lazy(() => import("./pages/CbdcIntegrationGateway"));
const DecentralizedIdentityManagerNew = React.lazy(() => import("./pages/DecentralizedIdentityManager"));
const PlatformMaturityScorecard = React.lazy(() => import("./pages/PlatformMaturityScorecard"));
const SmartContractPaymentNew = React.lazy(() => import("./pages/SmartContractPayment"));
const PredictiveAgentChurn = React.lazy(() => import("./pages/PredictiveAgentChurn"));
const CurrencyHedging = React.lazy(() => import("./pages/CurrencyHedging"));
const AgentClusterAnalyticsNew = React.lazy(() => import("./pages/AgentClusterAnalytics"));
const AutoComplianceWorkflowNew = React.lazy(() => import("./pages/AutoComplianceWorkflow"));
const PaymentTokenVaultNew = React.lazy(() => import("./pages/PaymentTokenVault"));
const DynamicQrPayment = React.lazy(() => import("./pages/DynamicQrPayment"));
const AgentRevenueAttribution = React.lazy(() => import("./pages/AgentRevenueAttribution"));
const PlatformCostAllocator = React.lazy(() => import("./pages/PlatformCostAllocator"));
const IntelligentRoutingEngine = React.lazy(() => import("./pages/IntelligentRoutingEngine"));
const RegulatorySandboxTesterNew = React.lazy(() => import("./pages/RegulatorySandboxTester"));
const AgentDeviceFingerprintNew = React.lazy(() => import("./pages/AgentDeviceFingerprint"));
const SettlementNettingEngine = React.lazy(() => import("./pages/SettlementNettingEngine"));
const PlatformCapacityPlanner = React.lazy(() => import("./pages/PlatformCapacityPlanner"));
const MerchantAcquirerGatewayNew = React.lazy(() => import("./pages/MerchantAcquirerGateway"));
const AgentMicroInsuranceNew = React.lazy(() => import("./pages/AgentMicroInsurance"));
const TransactionGraphAnalyzerNew = React.lazy(() => import("./pages/TransactionGraphAnalyzer"));
const PlatformRevenueOptimizer = React.lazy(() => import("./pages/PlatformRevenueOptimizer"));
const CrossBorderRemittanceHub = React.lazy(() => import("./pages/CrossBorderRemittanceHub"));
const OperationalCommandBridge = React.lazy(() => import("./pages/OperationalCommandBridge"));
const AgentKycDocVault = React.lazy(() => import("./pages/AgentKycDocVault"));
const RealtimePnlDashboardNew = React.lazy(() => import("./pages/RealtimePnlDashboard"));
const AutoReconciliationEngine = React.lazy(() => import("./pages/AutoReconciliationEngine"));
const AgentTerritoryOptimizer = React.lazy(() => import("./pages/AgentTerritoryOptimizer"));
const RegulatoryReportGeneratorNew = React.lazy(() => import("./pages/RegulatoryReportGenerator"));
const AgentTrainingAcademyNew = React.lazy(() => import("./pages/AgentTrainingAcademy"));
const DynamicFeeCalculatorNew = React.lazy(() => import("./pages/DynamicFeeCalculator"));
const CustomerOnboardingPipelineNew = React.lazy(() => import("./pages/CustomerOnboardingPipeline"));
const MerchantSettlementDashboardNew = React.lazy(() => import("./pages/MerchantSettlementDashboard"));
const AgentFloatInsuranceClaimsNew = React.lazy(() => import("./pages/AgentFloatInsuranceClaims"));
const PlatformSlaMonitor = React.lazy(() => import("./pages/PlatformSlaMonitor"));
const BulkDisbursementEngineNew = React.lazy(() => import("./pages/BulkDisbursementEngine"));
const TransactionReversalManagerNew = React.lazy(() => import("./pages/TransactionReversalManager"));
const AgentLoanOrigination = React.lazy(() => import("./pages/AgentLoanOrigination"));
const MultiChannelNotificationHubNew = React.lazy(() => import("./pages/MultiChannelNotificationHub"));
const PlatformMigrationToolkit = React.lazy(() => import("./pages/PlatformMigrationToolkit"));
const AgentPerformanceIncentivesNew = React.lazy(() => import("./pages/AgentPerformanceIncentives"));
const ExecutiveCommandCenter = React.lazy(() => import("./pages/ExecutiveCommandCenter"));
const DisputeNotifications = React.lazy(() => import("./pages/DisputeNotifications"));
const DisputeAnalyticsDashboard = React.lazy(() => import("./pages/DisputeAnalyticsDashboard"));
const AgentBenchmarkingNew = React.lazy(() => import("./pages/AgentBenchmarking"));
const TxVelocityMonitorNew = React.lazy(() => import("./pages/TxVelocityMonitor"));
const CustomerSurveysNew = React.lazy(() => import("./pages/CustomerSurveys"));
const AgentTerritoryHeatmap = React.lazy(() => import("./pages/AgentTerritoryHeatmap"));
const ReportSchedulerNew = React.lazy(() => import("./pages/ReportScheduler"));
const GatewayHealthMonitor = React.lazy(() => import("./pages/GatewayHealthMonitor"));
const AgentLoanOriginationV2New = React.lazy(() => import("./pages/AgentLoanOriginationV2"));
const MfaManagerNew = React.lazy(() => import("./pages/MfaManager"));
const IncidentPlaybookNew = React.lazy(() => import("./pages/IncidentPlaybook"));
const DeviceFleetManagerNew = React.lazy(() => import("./pages/DeviceFleetManager"));
const CustomerJourneyMapperNew = React.lazy(() => import("./pages/CustomerJourneyMapper"));
const ComplianceCertManagerNew = React.lazy(() => import("./pages/ComplianceCertManager"));
const PlatformHealthScorecard = React.lazy(() => import("./pages/PlatformHealthScorecard"));
const TrainingCertification = React.lazy(() => import("./pages/TrainingCertification"));
const BulkTransactionProcessorNew = React.lazy(() => import("./pages/BulkTransactionProcessor"));
const RealtimeTxMonitorPageNew = React.lazy(() => import("./pages/RealtimeTxMonitorPage"));
const FraudMlScoringPageNew = React.lazy(() => import("./pages/FraudMlScoringPage"));
const NotificationOrchestratorPageNew = React.lazy(() => import("./pages/NotificationOrchestratorPage"));
const AgentLoanFacilityPage = React.lazy(() => import("./pages/AgentLoanFacilityPage"));
const DynamicFeeEnginePageNew = React.lazy(() => import("./pages/DynamicFeeEnginePage"));
const MerchantKycOnboardingPageNew = React.lazy(() => import("./pages/MerchantKycOnboardingPage"));
const MerchantPayoutSettlementPageNew = React.lazy(() => import("./pages/MerchantPayoutSettlementPage"));
const ComplianceFilingPageNew = React.lazy(() => import("./pages/ComplianceFilingPage"));
const TenantFeatureTogglePage = React.lazy(() => import("./pages/TenantFeatureTogglePage"));
const ReconciliationEnginePageNew = React.lazy(() => import("./pages/ReconciliationEnginePage"));
const CustomerJourneyAnalyticsPageNew = React.lazy(() => import("./pages/CustomerJourneyAnalyticsPage"));
const BackupDisasterRecoveryPageNew = React.lazy(() => import("./pages/BackupDisasterRecoveryPage"));
const WorkflowEnginePage = React.lazy(() => import("./pages/WorkflowEnginePage"));
const GeneralLedgerPageNew = React.lazy(() => import("./pages/GeneralLedgerPage"));
const DataExportHubPageNew = React.lazy(() => import("./pages/DataExportHubPage"));
const SlaMonitoringPage = React.lazy(() => import("./pages/SlaMonitoringPage"));
const RateLimitEnginePageNew = React.lazy(() => import("./pages/RateLimitEnginePage"));
const AgentGamificationPageNew = React.lazy(() => import("./pages/AgentGamificationPage"));
const ExecutiveCommandCenterPage = React.lazy(() => import("./pages/ExecutiveCommandCenterPage"));
const ActivityAuditLogPage = React.lazy(() => import("./pages/ActivityAuditLogPage"));
const SystemSettingsPage = React.lazy(() => import("./pages/SystemSettingsPage"));
const AgentPerformanceLeaderboardPageNew = React.lazy(() => import("./pages/AgentPerformanceLeaderboardPage"));
const FloatManagementPageNew = React.lazy(() => import("./pages/FloatManagementPage"));
const ArchivalAdminNew = React.lazy(() => import("./pages/ArchivalAdmin"));
const LoadTestDashboardNew = React.lazy(() => import("./pages/LoadTestDashboard"));
const LoadTestComparisonNew = React.lazy(() => import("./pages/LoadTestComparison"));
const AdminSupportInbox = React.lazy(() => import("./pages/AdminSupportInbox"));
const NetworkStatusDashboardNew = React.lazy(() => import("./pages/NetworkStatusDashboard"));
const SecurityAuditDashboard = React.lazy(() => import("./pages/SecurityAuditDashboard"));
const CarrierCostDashboardNew = React.lazy(() => import("./pages/CarrierCostDashboard"));
const CarrierSlaDashboardNew = React.lazy(() => import("./pages/CarrierSlaDashboard"));
const UssdAnalyticsDashboard = React.lazy(() => import("./pages/UssdAnalyticsDashboard"));
const UssdLocalizationPage = React.lazy(() => import("./pages/UssdLocalizationPage"));
const NetworkDiagnosticPageNew = React.lazy(() => import("./pages/NetworkDiagnosticPage"));
const ConnectionQualityPageNew = React.lazy(() => import("./pages/ConnectionQualityPage"));
const UssdSessionReplayPage = React.lazy(() => import("./pages/UssdSessionReplayPage"));
const AgentKycPageNew = React.lazy(() => import("./pages/AgentKycPage"));
const TxMonitorPageNew = React.lazy(() => import("./pages/TxMonitorPage"));
const CommissionCalculatorPageNew = React.lazy(() => import("./pages/CommissionCalculatorPage"));
const CarrierLivePricingPageNew = React.lazy(() => import("./pages/CarrierLivePricingPage"));
const AgentGeoFencingPageNew = React.lazy(() => import("./pages/AgentGeoFencingPage"));
const AgentOnboardingWorkflowPageNew = React.lazy(() => import("./pages/AgentOnboardingWorkflowPage"));
const AuditExportPage = React.lazy(() => import("./pages/AuditExportPage"));
const AuditTrailExportPage = React.lazy(() => import("./pages/AuditTrailExportPage"));
const DailyPnlReportPageNew = React.lazy(() => import("./pages/DailyPnlReportPage"));
const TransactionDisputeResolutionPageNew = React.lazy(() => import("./pages/TransactionDisputeResolutionPage"));
const TransactionReversalWorkflowPageNew = React.lazy(() => import("./pages/TransactionReversalWorkflowPage"));
const BillingDashboardPageNew = React.lazy(() => import("./pages/BillingDashboardPage"));
const RealTimeDashboard = React.lazy(() => import("./pages/RealTimeDashboard"));
const InvoiceManagementPageNew = React.lazy(() => import("./pages/InvoiceManagementPage"));
const TenantBillingOnboardingPage = React.lazy(() => import("./pages/TenantBillingOnboardingPage"));
const TenantBillingPortalPage = React.lazy(() => import("./pages/TenantBillingPortalPage"));
const BillingAnalyticsDashboardPage = React.lazy(() => import("./pages/BillingAnalyticsDashboardPage"));
const PrivacyPolicy = React.lazy(() => import("./pages/PrivacyPolicy"));
const NetworkStatusDashboardPage = React.lazy(() => import("./pages/NetworkStatusDashboard"));
const AgentOnboardingNew2 = React.lazy(() => import("./pages/agent-management-new/AgentOnboarding"));
const AgentPortalMgmt = React.lazy(() => import("./pages/agent-management-new/AgentPortal"));
const AgentHierarchyPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentHierarchyPage"));
const AgentGeoFencingPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentGeoFencingPage"));
const AgentInventoryMgmtMgmt = React.lazy(() => import("./pages/agent-management-new/AgentInventoryMgmt"));
const AgentKycPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentKycPage"));
const AgentLoanOriginationV2Mgmt = React.lazy(() => import("./pages/agent-management-new/AgentLoanOriginationV2"));
const AgentMicroInsuranceMgmt = React.lazy(() => import("./pages/agent-management-new/AgentMicroInsurance"));
const AgentCommissionCalcMgmt = React.lazy(() => import("./pages/agent-management-new/AgentCommissionCalc"));
const AgentScorecardPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentScorecardPage"));
const AgentBenchmarkingMgmt = React.lazy(() => import("./pages/agent-management-new/AgentBenchmarking"));
const AgentClusterAnalyticsMgmt = React.lazy(() => import("./pages/agent-management-new/AgentClusterAnalytics"));
const AgentManagementDashboardMgmt = React.lazy(() => import("./pages/agent-management-new/AgentManagementDashboard"));
const AgentOnboardingWizardPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentOnboardingWizardPage"));
const AgentOnboardingWorkflowPageMgmt = React.lazy(() => import("./pages/agent-management-new/AgentOnboardingWorkflowPage"));
const AgentDeviceFingerprintMgmt = React.lazy(() => import("./pages/agent-management-new/AgentDeviceFingerprint"));
const AgentFloatInsuranceClaimsMgmt = React.lazy(() => import("./pages/agent-management-new/AgentFloatInsuranceClaims"));
const AgentLoanAdvanceMgmt = React.lazy(() => import("./pages/agent-management-new/AgentLoanAdvance"));

// Login Page
const BASE_URL = import.meta.env.VITE_API_URL || "https://54agent.upi.dev";
const DEFAULT_TENANT_ID = import.meta.env.VITE_TENANT_ID || "54agent";
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const LoginPage = () => {
  const navigate = useNavigate();
  const { name: tenantName, logoUrl } = useTenantBranding();
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Initialize tenant config on mount
  useEffect(() => {
    const initializeTenant = async () => {
      const tenantId = DEFAULT_TENANT_ID;
      try {
        // Fetch tenant config
        await tenantService.getTenant(tenantId);
        console.log("Tenant configuration loaded successfully");
      } catch (error) {
        console.warn(
          "Failed to load tenant configuration, will use defaults:",
          error,
        );
      }
    };

    initializeTenant();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsLoading(true);

    const tenantId = DEFAULT_TENANT_ID;

    try {
      // First, fetch tenant configuration
      try {
        await tenantService.getTenant(tenantId);
      } catch (error) {
        console.warn(
          "Failed to fetch tenant config, continuing with defaults:",
          error,
        );
      }

      // Demo mode: Skip authentication
      if (DEMO_MODE) {
        localStorage.setItem("auth_token", "demo-token");
        // Demo session expires in 8 hours
        localStorage.setItem("auth_token_expires_at", String(Date.now() + 8 * 60 * 60 * 1000));
        localStorage.setItem("userName", "Demo Admin");
        localStorage.setItem("tenantId", tenantId);
        localStorage.setItem("keycloakId", "demo-user-id");
        navigate("/dashboard");
        return;
      }

      // Use authApi which automatically includes tenant headers from config
      const { authApi } = await import("./utils/api");
      const data = await authApi.login(
        formData.email,
        formData.password,
        tenantId,
      );

      // Store auth data
      // Accept only user key for compatibility
      const rawUser = data && data.user ? data.user : data;
      const keycloakId =
        rawUser.keycloak_id ?? data.keycloak_id ?? formData.email;
      const accessToken = data.access_token;

      localStorage.setItem("auth_token", accessToken ?? "authenticated");
      // Store token expiry from expires_in or JWT exp claim
      const expiresIn = (data as any).expires_in;
      if (expiresIn) {
        localStorage.setItem("auth_token_expires_at", String(Date.now() + expiresIn * 1000));
      } else if (accessToken) {
        try {
          const payload = JSON.parse(atob(accessToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          if (payload.exp) localStorage.setItem("auth_token_expires_at", String(payload.exp * 1000));
        } catch {}
      }
      localStorage.setItem(
        "userName",
        (rawUser as any).name ??
          (rawUser as any).first_name ??
          formData.email.split("@")[0],
      );
      localStorage.setItem("tenantId", tenantId);
      localStorage.setItem("keycloakId", keycloakId);
      // Store admin role (v2.perm tenant role) — distinct from agent roles
      localStorage.setItem(
        "adminRole",
        (rawUser as any).access_level ?? (rawUser as any).role ?? "support_agent",
      );
      if (data.refresh_token)
        localStorage.setItem("refreshToken", data.refresh_token);

      navigate("/dashboard");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Login failed. Please try again.";
      setLoginError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-primary-900 to-gray-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute w-96 h-96 bg-primary/20 rounded-full blur-3xl -top-48 -left-48 animate-pulse"></div>
        <div className="absolute w-96 h-96 bg-secondary/20 rounded-full blur-3xl -bottom-48 -right-48 animate-pulse delay-1000"></div>
      </div>

      <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-md p-8 relative z-10 border border-white/20">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={tenantName}
                className="h-16 w-auto object-contain"
              />
            ) : (
              <div
                className="h-16 w-16 rounded-2xl flex items-center justify-center text-white text-2xl font-bold"
                style={{ backgroundColor: "var(--tenant-primary-color, #002082)" }}
              >
                {tenantName.slice(0, 2).toUpperCase()}
              </div>
            )}
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
            {tenantName}
          </h1>
          <p className="text-gray-600 mt-2">Agent Banking Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                type="email"
                required
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="admin@54agent.com"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                type="password"
                required
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-primary text-white py-3 rounded-xl hover:bg-primary-700 transition-all font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>
        {loginError && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm text-center">
            {loginError}
          </div>
        )}

        {/* <div className="mt-6 text-center">
          <Link
            to="/register"
            className="text-primary hover:text-primary-700 hover:underline text-sm font-medium transition-colors"
          >
            Don't have an account? Register
          </Link>
        </div> */}
      </div>
    </div>
  );
};

// Register Page
const RegisterPage = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    uin: "",
    password: "",
    confirmPassword: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      setRegisterError("Passwords do not match!");
      return;
    }
    setRegisterError(null);
    setIsLoading(true);
    try {
      const tenantId = DEFAULT_TENANT_ID;

      // Use api which automatically includes tenant headers from config
      const { api } = await import("./utils/api");
      await api.createAdmin({
        firstName: formData.firstName,
        lastName: formData.lastName,
        email: formData.email,
        phone: formData.phone,
        uin: formData.uin,
        password: formData.password,
      });

      navigate("/login");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed.";
      setRegisterError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary to-primary-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Create Account</h1>
          <p className="text-gray-600 mt-2">Join 54agent Admin Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {registerError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {registerError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                First Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  required
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                  placeholder="John"
                  value={formData.firstName}
                  onChange={(e) =>
                    setFormData({ ...formData, firstName: e.target.value })
                  }
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Last Name
              </label>
              <input
                type="text"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="Doe"
                value={formData.lastName}
                onChange={(e) =>
                  setFormData({ ...formData, lastName: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                type="email"
                required
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="admin@54agent.com"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Phone
            </label>
            <input
              type="tel"
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="+2348000000000"
              value={formData.phone}
              onChange={(e) =>
                setFormData({ ...formData, phone: e.target.value })
              }
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              NIN / BVN (UIN)
            </label>
            <input
              type="text"
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="Enter NIN or BVN"
              value={formData.uin}
              onChange={(e) =>
                setFormData({ ...formData, uin: e.target.value })
              }
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                type="password"
                required
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                type="password"
                required
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="••••••••"
                value={formData.confirmPassword}
                onChange={(e) =>
                  setFormData({ ...formData, confirmPassword: e.target.value })
                }
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-700 transition-colors font-medium disabled:opacity-60"
          >
            {isLoading ? "Creating Account..." : "Create Account"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <Link to="/login" className="text-primary hover:underline text-sm">
            Already have an account? Sign in
          </Link>
        </div>
      </div>
    </div>
  );
};

// Protected Route Wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem("auth_token");
  const expiresAt = localStorage.getItem("auth_token_expires_at");
  const expired = expiresAt ? Date.now() > Number(expiresAt) : false;
  if (!token || expired) {
    if (expired) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_token_expires_at");
      localStorage.removeItem("refreshToken");
    }
    return <Navigate to="/login" />;
  }
  return <>{children}</>;
};

// Main Layout with Sidebar
const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const toggleSection = (title: string) =>
    setCollapsedSections(prev => ({ ...prev, [title]: !prev[title] }));
  const userName = localStorage.getItem("userName") || "Admin";
  // adminRole is a v2.perm tenant role — used only for display, NOT for filtering
  const adminRole = localStorage.getItem("adminRole") || "support_agent";
  const { hasPermission, clearCache } = usePermissions();
  const { name: tenantName, logoUrl, primaryColor } = useTenantBranding();
  const { run: tourRun, startTour, stopTour } = useTour();

  const handleLogout = async () => {
    const refreshToken = localStorage.getItem("refreshToken");
    if (refreshToken) {
      try {
        // Use authApi which automatically includes tenant headers
        const { authApi } = await import("./utils/api");
        await authApi.logout(refreshToken);
      } catch {
        /* ignore */
      }
    }
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_token_expires_at");
    localStorage.removeItem("userName");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("keycloakId");
    localStorage.removeItem("adminRole");
    clearCache();
    // Clear tenant config on logout
    tenantService.clearTenantData();
    navigate("/login");
  };

  // Visibility is driven by Permify (v2.perm `tenants` entity).
  // permission: null = visible to all authenticated admin users.
  // Admin roles are v2.perm tenant roles — NOT agent roles (agent/super_agent/aggregator).
type MenuItem = {
  icon: React.ElementType;
  label: string;
  path: string;
  permission: any;
};

type MenuSection = {
  title: string;
  items: MenuItem[];
};

const menuSections = [
  {
    title: "OVERVIEW",
    items: [
      { icon: LayoutDashboard, label: "Dashboard", path: "/dashboard", permission: PERMISSION_MAP.DASHBOARD, tourId: "nav-dashboard" },
      { icon: Activity, label: "Monitoring", path: "/monitoring", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Settings, label: "Settings", path: "/settings", permission: PERMISSION_MAP.MANAGE_EMPLOYEES, tourId: "nav-settings" },
    ],
  },

  {
    title: "PEOPLE",
    items: [
      { icon: Users, label: "Customers", path: "/customers", permission: PERMISSION_MAP.MANAGE_CUSTOMERS, tourId: "nav-customers" },
      { icon: UserCheck, label: "Agents", path: "/agents", permission: PERMISSION_MAP.MANAGE_EMPLOYEES, tourId: "nav-agents" },
      { icon: Store, label: "Businesses", path: "/businesses", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Shield, label: "Admins", path: "/admins", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
    ],
  },

  {
    title: "POS & FIELD",
    items: [
      { icon: MonitorSmartphone, label: "POS Terminals", path: "/pos", permission: PERMISSION_MAP.ERP, tourId: "nav-pos" },
      { icon: Cpu, label: "POS Hardware", path: "/pos-hardware", permission: PERMISSION_MAP.ERP },
      { icon: Package, label: "POS Requests", path: "/pos-requests", permission: PERMISSION_MAP.ERP },
      { icon: BookOpen, label: "Device Catalog", path: "/device-catalog", permission: PERMISSION_MAP.ERP },
      { icon: Smartphone, label: "MDM", path: "/mdm", permission: PERMISSION_MAP.ERP },
      { icon: Star, label: "Loyalty", path: "/loyalty", permission: PERMISSION_MAP.MANAGE_CUSTOMERS, tourId: "nav-loyalty" },
      { icon: AlertTriangle, label: "Geofence Violations", path: "/geofence-violations", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: Wifi, label: "Network Status", path: "/network-operations", permission: PERMISSION_MAP.ERP },
    ],
  },

  {
    title: "FINANCE & TRANSACTIONS",
    items: [
      { icon: CreditCard, label: "Transactions", path: "/transactions", permission: PERMISSION_MAP.ERP, tourId: "nav-transactions" },
      { icon: Award, label: "Commission", path: "/commission", permission: PERMISSION_MAP.BILLING, tourId: "nav-commission" },
      { icon: TrendingUp, label: "Float Loans", path: "/loans", permission: PERMISSION_MAP.APPLICATIONS, tourId: "nav-float-loans" },
      { icon: Building2, label: "Chart of Accounts", path: "/chart-of-accounts", permission: PERMISSION_MAP.CHART_OF_ACCOUNTS },
      { icon: CreditCard, label: "Settlement Reconciliation", path: "/settlement-reconciliation", permission: PERMISSION_MAP.VIEW_ANALYTICS, tourId: "nav-reconciliation" },
      { icon: BarChart3, label: "Settlement Batches", path: "/settlement-batch-processor", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: TrendingUp, label: "Revenue Leakage", path: "/finance/revenue-leakage", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Netting Engine", path: "/finance/netting-engine", permission: PERMISSION_MAP.BILLING },
      { icon: Award, label: "Commission Clawback", path: "/finance/commission-clawback", permission: PERMISSION_MAP.BILLING },
      { icon: Star, label: "Credit Ratings", path: "/finance/credit-ratings", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },

  {
    title: "BILLING ENGINE",
    items: [
      { icon: CreditCard, label: "Billing Dashboard", path: "/billing", permission: PERMISSION_MAP.BILLING, tourId: "nav-billing" },
      { icon: Wallet, label: "Credits & Payments", path: "/billing/credits", permission: PERMISSION_MAP.BILLING },
      { icon: FileText, label: "Invoices", path: "/billing/invoices", permission: PERMISSION_MAP.BILLING },
    ],
  },

  {
    title: "AGENT DEVELOPMENT",
    items: [
      { icon: Trophy, label: "Gamification", path: "/agent-gamification", permission: PERMISSION_MAP.VIEW_ANALYTICS, tourId: "nav-gamification" },
      { icon: BookOpen, label: "Training Academy", path: "/agent-training", permission: PERMISSION_MAP.VIEW_ANALYTICS, tourId: "nav-training" },
      { icon: BookOpen, label: "Training Portal", path: "/agent-training/portal", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: TrendingUp, label: "Performance Leaderboard", path: "/agent-performance", permission: PERMISSION_MAP.VIEW_ANALYTICS, tourId: "nav-performance" },
      { icon: BarChart3, label: "Performance Analytics", path: "/agent-performance/analytics", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Award, label: "Performance Incentives", path: "/agent-performance/incentives", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Star, label: "Performance Scorecard", path: "/agent-performance/scorecard", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },

  {
    title: "DISPUTES & RISK",
    items: [
      { icon: AlertCircle, label: "Dispute Resolution", path: "/dispute-resolution", permission: PERMISSION_MAP.DISPUTES, tourId: "nav-disputes" },
      { icon: AlertTriangle, label: "Chargebacks", path: "/chargeback-management", permission: PERMISSION_MAP.DISPUTES },
      { icon: Shield, label: "Arbitration", path: "/dispute-arbitration", permission: PERMISSION_MAP.DISPUTES },
      { icon: Users, label: "Customer Portal", path: "/customer-dispute-portal", permission: PERMISSION_MAP.DISPUTES },
      { icon: Cpu, label: "Mediation AI", path: "/dispute-mediation-ai", permission: PERMISSION_MAP.DISPUTES },
      { icon: Settings, label: "Dispute Auto Rules", path: "/dispute-auto-rules", permission: PERMISSION_MAP.DISPUTES },
    ],
  },

  {
    title: "COMPLIANCE & REGULATORY",
    items: [
      { icon: FileText, label: "Compliance", path: "/compliance", permission: PERMISSION_MAP.VERIFY_KYC, tourId: "nav-compliance" },
      { icon: FileText, label: "Compliance Automation", path: "/compliance/automation", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: Shield, label: "Compliance Certs", path: "/compliance/certificates", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "Compliance Reporting", path: "/compliance/reporting", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "Compliance Filing", path: "/compliance/filing", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: BookOpen, label: "Compliance Training", path: "/compliance/training", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: Shield, label: "GDPR / Data Privacy", path: "/compliance/gdpr", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "CBN Reports", path: "/compliance/cbn-reports", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: AlertTriangle, label: "NFIU Reporting", path: "/compliance/nfiu", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: Eye, label: "Regulatory Sandbox", path: "/compliance/sandbox", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "Data Retention Policy", path: "/compliance/data-retention", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: Eye, label: "Audit Logs", path: "/audit", permission: PERMISSION_MAP.AUDIT_LOGS },
    ],
  },

  {
    title: "REPORTS & ANALYTICS",
    items: [
      { icon: BarChart3, label: "Reports", path: "/reports", permission: PERMISSION_MAP.VIEW_ANALYTICS, tourId: "nav-reports" },
      { icon: TrendingUp, label: "Agent Business Reports", path: "/agent-business-reports", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: TrendingUp, label: "Projections", path: "/projections", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: TrendingUp, label: "Revenue Forecasting", path: "/revenue-forecasting", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Leaf, label: "ESG & Carbon Tracker", path: "/esg", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },

  {
    title: "COMMUNICATION & SUPPORT",
    items: [
      { icon: MessageSquare, label: "Communication", path: "/communication", permission: PERMISSION_MAP.COMMUNICATION },
      { icon: Bell, label: "Notifications", path: "/notifications", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: MessageCircle, label: "Live Chat Support", path: "/compliance/live-chat", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: HeadphonesIcon, label: "Help Desk", path: "/compliance/help-desk", permission: PERMISSION_MAP.VIEW_ALL },
    ],
  },

  {
    title: "INTEGRATIONS",
    items: [
      { icon: Building2, label: "ERPNext", path: "/service-integrations/erpnext", permission: PERMISSION_MAP.ERP },
      { icon: Shield, label: "Fraud Engine", path: "/service-integrations/fraud-engine", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: FileText, label: "Nigeria VAT", path: "/nigeria-vat", permission: PERMISSION_MAP.BILLING },
      { icon: Store, label: "Storefront Ads", path: "/service-integrations/storefront-advertising", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: ShoppingBag, label: "Social Commerce", path: "/social-commerce", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    ],
  },

  {
    title: "DEVELOPER & API",
    items: [
      { icon: Network, label: "Developer Portal", path: "/developer", permission: PERMISSION_MAP.ERP, tourId: "nav-developer" },
      { icon: Lock, label: "API Keys", path: "/developer/api-keys", permission: PERMISSION_MAP.ERP },
      { icon: Bell, label: "Webhooks", path: "/developer/webhooks", permission: PERMISSION_MAP.ERP },
      { icon: BarChart3, label: "API Analytics", path: "/developer/api-analytics", permission: PERMISSION_MAP.ERP },
      { icon: Gauge, label: "Rate Limiter", path: "/developer/rate-limiter", permission: PERMISSION_MAP.ERP },
      { icon: Layers, label: "API Versioning", path: "/developer/versioning", permission: PERMISSION_MAP.ERP },
      { icon: GitBranch, label: "Integration Marketplace", path: "/developer/integrations", permission: PERMISSION_MAP.ERP },
      { icon: FileText, label: "Publish Readiness", path: "/developer/publish-readiness", permission: PERMISSION_MAP.ERP },
      { icon: Shield, label: "Production Checklist", path: "/developer/production-checklist", permission: PERMISSION_MAP.ERP },
    ],
  },

  {
    title: "OPERATIONS",
    items: [
      { icon: AlertCircle, label: "Incident Management", path: "/ops/incidents", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: BarChart3, label: "A/B Testing", path: "/ops/ab-testing", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Network, label: "Canary Releases", path: "/ops/canary", permission: PERMISSION_MAP.ERP },
      { icon: MapPin, label: "Territory Analytics", path: "/ops/territory", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },


  {
    title: "AGENT TOOLS",
    items: [
      { icon: Users, label: "Agent Management", path: "/agent-management", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { icon: UserCheck, label: "Agent Portal", path: "/agent/portal", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { icon: Users, label: "Agent Hierarchy", path: "/agent/hierarchy", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { icon: MapPin, label: "Geo-Fencing", path: "/agent/geo-fencing", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { icon: Package, label: "Inventory", path: "/agent/inventory", permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { icon: Shield, label: "Agent KYC", path: "/agent/kyc", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: TrendingUp, label: "Loan Origination", path: "/agent/loan-origination", permission: PERMISSION_MAP.APPLICATIONS },
      { icon: Award, label: "Micro-Insurance", path: "/agent/micro-insurance", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Award, label: "Commission Calc", path: "/agent/commission-calc", permission: PERMISSION_MAP.BILLING },
      { icon: Star, label: "Agent Scorecard", path: "/agent/scorecard", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: BarChart3, label: "Benchmarking", path: "/agent/benchmarking", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Store, label: "Store Setup", path: "/agent/store-setup", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    ],
  },

  {
    title: "ANALYTICS & REPORTS",
    items: [
      { icon: BarChart3, label: "Analytics Dashboard", path: "/analytics", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: BarChart3, label: "BI Reporting", path: "/analytics/bi-reporting", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: FileText, label: "Report Builder", path: "/analytics/drag-drop-reports", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: FileText, label: "Report Templates", path: "/analytics/report-templates", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: FileText, label: "Report Scheduler", path: "/analytics/report-scheduler", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Cpu, label: "ML Scoring", path: "/analytics/ml-scoring", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Activity, label: "Transaction Analytics", path: "/analytics/transactions", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: FileText, label: "Data Export", path: "/analytics/data-export", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Database, label: "Data Quality", path: "/analytics/data-quality", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },

  {
    title: "FINANCE TOOLS",
    items: [
      { icon: Award, label: "Commission Payouts", path: "/finance/commission-payouts", permission: PERMISSION_MAP.BILLING },
      { icon: Award, label: "Commission Engine", path: "/finance/commission-engine", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Daily P&L", path: "/finance/daily-pnl", permission: PERMISSION_MAP.BILLING },
      { icon: TrendingUp, label: "Realtime P&L", path: "/finance/realtime-pnl", permission: PERMISSION_MAP.BILLING },
      { icon: Wallet, label: "Float Management", path: "/finance/float-management", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Float Reconciliation", path: "/finance/float-reconciliation", permission: PERMISSION_MAP.BILLING },
      { icon: FileText, label: "Financial Reconciliation", path: "/finance/reconciliation", permission: PERMISSION_MAP.BILLING },
      { icon: FileText, label: "Financial Reports", path: "/finance/reporting-suite", permission: PERMISSION_MAP.BILLING },
      { icon: FileText, label: "Tax Collection", path: "/finance/tax-collection", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Multi-Currency", path: "/finance/multi-currency", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Payroll", path: "/finance/payroll", permission: PERMISSION_MAP.BILLING },
    ],
  },

  {
    title: "PAYMENTS ENGINE",
    items: [
      { icon: CreditCard, label: "Payments", path: "/payments", permission: PERMISSION_MAP.ERP },
      { icon: Network, label: "Gateway Router", path: "/payments/gateway-router", permission: PERMISSION_MAP.ERP },
      { icon: CreditCard, label: "Payment Reconciliation", path: "/payments/reconciliation", permission: PERMISSION_MAP.ERP },
      { icon: CreditCard, label: "Token Vault", path: "/payments/token-vault", permission: PERMISSION_MAP.ERP },
      { icon: CreditCard, label: "Dynamic Fee Calculator", path: "/payments/dynamic-fee-calculator", permission: PERMISSION_MAP.BILLING },
      { icon: CreditCard, label: "Bulk Payments", path: "/payments/bulk-payment-processor", permission: PERMISSION_MAP.ERP },
      { icon: CreditCard, label: "Settlement Scheduler", path: "/payments/settlement-scheduler", permission: PERMISSION_MAP.ERP },
      { icon: Activity, label: "TX Velocity Monitor", path: "/payments/velocity-monitor", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Activity, label: "Realtime TX Monitor", path: "/payments/realtime-tx-monitor", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: CreditCard, label: "Reversal Workflow", path: "/payments/reversal-workflow", permission: PERMISSION_MAP.ERP },
      { icon: BarChart3, label: "Transaction Graph", path: "/payments/graph-analyzer", permission: PERMISSION_MAP.VIEW_ANALYTICS },
    ],
  },

  {
    title: "NOTIFICATIONS HUB",
    items: [
      { icon: Bell, label: "Notification Center", path: "/notifications/center", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: Bell, label: "Notification Inbox", path: "/notifications/inbox", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: Bell, label: "Template Manager", path: "/notifications/template-manager", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: MessageCircle, label: "WhatsApp Channel", path: "/notifications/whatsapp", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: Bell, label: "Broadcast Manager", path: "/notifications/broadcast-manager", permission: PERMISSION_MAP.NOTIFICATIONS },
      { icon: Bell, label: "Multi-Channel Hub", path: "/notifications/multi-channel", permission: PERMISSION_MAP.NOTIFICATIONS },
    ],
  },

  {
    title: "PLATFORM OPS",
    items: [
      { icon: Server, label: "Platform Hub", path: "/platform", permission: PERMISSION_MAP.ERP },
      { icon: Activity, label: "System Health", path: "/platform/system-health", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Activity, label: "System Status", path: "/platform/system-status", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Settings, label: "Config Management", path: "/platform/config-management", permission: PERMISSION_MAP.ERP },
      { icon: Settings, label: "Feature Flags", path: "/platform/feature-flags", permission: PERMISSION_MAP.ERP },
      { icon: Database, label: "Capacity Planning", path: "/platform/capacity-planning", permission: PERMISSION_MAP.ERP },
      { icon: Activity, label: "Resilience Monitor", path: "/platform/resilience-monitor", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Wifi, label: "Network Quality Heatmap", path: "/platform/network-quality-heatmap", permission: PERMISSION_MAP.VIEW_ALL },
      { icon: Database, label: "Backup & DR", path: "/platform/backup-dr", permission: PERMISSION_MAP.ERP },
    ],
  },

  {
    title: "FRAUD & SECURITY",
    items: [
      { icon: Shield, label: "Fraud Dashboard", path: "/fraud/dashboard", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: AlertTriangle, label: "Ransomware Alerts", path: "/fraud/ransomware-alerts", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: AlertCircle, label: "Incident Command", path: "/fraud/incident-command", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: FileText, label: "Incident Playbook", path: "/fraud/incident-playbook", permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
      { icon: Shield, label: "Biometric Gateway", path: "/security/biometric-gateway", permission: PERMISSION_MAP.ERP },
      { icon: Lock, label: "MFA Manager", path: "/security/mfa-manager", permission: PERMISSION_MAP.ERP },
      { icon: Lock, label: "Session Manager", path: "/security/session-manager", permission: PERMISSION_MAP.ERP },
      { icon: Shield, label: "PBAC Management", path: "/security/pbac", permission: PERMISSION_MAP.ERP },
      { icon: Shield, label: "Digital Identity", path: "/security/digital-identity", permission: PERMISSION_MAP.ERP },
    ],
  },

  {
    title: "KYC & REGULATORY",
    items: [
      { icon: FileText, label: "KYC Document Mgmt", path: "/kyc/document-management", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "KYC Workflow", path: "/kyc/workflow", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "CBN Reporting", path: "/kyc/cbn-reporting", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "Regulatory Reports", path: "/kyc/regulatory-reporting", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: FileText, label: "Regulatory Filing", path: "/kyc/regulatory-filing", permission: PERMISSION_MAP.VERIFY_KYC },
      { icon: Shield, label: "Compliance Checker", path: "/kyc/automated-compliance", permission: PERMISSION_MAP.VERIFY_KYC },
    ],
  },

  {
    title: "MERCHANT TOOLS",
    items: [
      { icon: Store, label: "Acquirer Gateway", path: "/merchant/acquirer-gateway", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Store, label: "Merchant Onboarding", path: "/merchant/onboarding", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: CreditCard, label: "Merchant Payments", path: "/merchant/payments", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: CreditCard, label: "Payout Settlement", path: "/merchant/payout-settlement", permission: PERMISSION_MAP.BILLING },
    ],
  },

  {
    title: "CUSTOMER TOOLS",
    items: [
      { icon: Users, label: "Customer Portal", path: "/customer/portal", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Users, label: "Customer 360 View", path: "/customer/360-view", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Users, label: "Customer Database", path: "/customer/database", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: MessageSquare, label: "Feedback & NPS", path: "/customer/feedback-nps", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Wallet, label: "Customer Wallet", path: "/customer/wallet", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    ],
  },

  {
    title: "WEBHOOKS & API+",
    items: [
      { icon: Network, label: "API Docs", path: "/developer/api-docs", permission: PERMISSION_MAP.ERP },
      { icon: Bell, label: "Webhook Monitor", path: "/developer/webhook-delivery-monitor", permission: PERMISSION_MAP.ERP },
      { icon: Bell, label: "Webhook Manager", path: "/developer/webhook-manager", permission: PERMISSION_MAP.ERP },
      { icon: Bell, label: "Webhook Console", path: "/developer/webhook-console", permission: PERMISSION_MAP.ERP },
    ],
  },

  {
    title: "EMERGING TECH",
    items: [
      { icon: Globe, label: "Open Banking", path: "/emerging/open-banking", permission: PERMISSION_MAP.ERP },
      { icon: Leaf, label: "Carbon Marketplace", path: "/emerging/carbon-marketplace", permission: PERMISSION_MAP.VIEW_ANALYTICS },
      { icon: Globe, label: "Health Insurance", path: "/emerging/health-insurance", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: ShoppingBag, label: "Education Payments", path: "/emerging/education-payments", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
      { icon: Leaf, label: "AgriTech Payments", path: "/emerging/agritech", permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    ],
  },
];

const filteredSections = menuSections
  .map((section) => ({
    ...section,
    items: section.items.filter((item) => {
      if (!item.permission) return true;
      // return hasPermission(
      //   item.permission.resourceType,
      //   item.permission.permission
      // );
      return true
    }),
  }))
  .filter((section) => section.items.length > 0);
  const allMenuItems: MenuItem[] = [
    // 1. Overview
    { icon: LayoutDashboard, label: "Dashboard",            path: "/dashboard",                                    permission: PERMISSION_MAP.DASHBOARD },

    // 2. People & Structure
    { icon: Users,           label: "Customers",            path: "/customers",                                    permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    { icon: UserCheck,       label: "Agents",               path: "/agents",                                       permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
    { icon: Store,           label: "Businesses",           path: "/businesses",                                   permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    { icon: Shield,          label: "Admins",               path: "/admins",                                       permission: PERMISSION_MAP.MANAGE_EMPLOYEES },

    // 3. POS & Field Operations
    { icon: Cpu,             label: "POS Hardware",         path: "/pos-hardware",                                 permission: PERMISSION_MAP.ERP },
    { icon: Package,         label: "POS Requests",         path: "/pos-requests",                                 permission: PERMISSION_MAP.ERP },
    { icon: MonitorSmartphone,label: "POS Terminals",       path: "/pos",                                          permission: PERMISSION_MAP.ERP },
    { icon: BookOpen,        label: "Device Catalog",       path: "/device-catalog",                               permission: PERMISSION_MAP.ERP },
    { icon: Smartphone,      label: "MDM",                  path: "/mdm",                                          permission: PERMISSION_MAP.ERP },
    { icon: Star,            label: "Loyalty",              path: "/loyalty",                                      permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    { icon: Building2,       label: "ERPNext",              path: "/service-integrations/erpnext",                 permission: PERMISSION_MAP.ERP },
    { icon: Shield,          label: "Fraud Engine",         path: "/service-integrations/fraud-engine",            permission: PERMISSION_MAP.FLAG_SUSPICIOUS },
    { icon: FileText,        label: "Nigeria VAT",          path: "/nigeria-vat",                                  permission: PERMISSION_MAP.BILLING },
    { icon: Store,           label: "Storefront Ads",       path: "/service-integrations/storefront-advertising",  permission: PERMISSION_MAP.MANAGE_CUSTOMERS },
    { icon: AlertTriangle,   label: "Geofence Violations",  path: "/geofence-violations",                          permission: PERMISSION_MAP.FLAG_SUSPICIOUS },

    // 4. Transactions & Finance
    { icon: CreditCard,      label: "Transactions",         path: "/transactions",                                 permission: PERMISSION_MAP.TRANSACTIONS },
    { icon: Award,           label: "Commission",           path: "/commission",                                   permission: PERMISSION_MAP.BILLING },
    { icon: TrendingUp,      label: "Float Loans",          path: "/loans",                                        permission: PERMISSION_MAP.APPLICATIONS },
    { icon: Building2,       label: "Chart of Accounts",    path: "/chart-of-accounts",                            permission: PERMISSION_MAP.CHART_OF_ACCOUNTS },

    // 5. Reports & Insights
    { icon: BarChart3,       label: "Reports",              path: "/reports",                                      permission: PERMISSION_MAP.VIEW_ANALYTICS },
    { icon: TrendingUp,      label: "Agent Business Reports",path: "/agent-business-reports",                      permission: PERMISSION_MAP.VIEW_ANALYTICS },
    { icon: TrendingUp,      label: "Projections",          path: "/projections",                                  permission: PERMISSION_MAP.VIEW_ANALYTICS },

    // 6. Risk, Compliance & Oversight
    { icon: AlertCircle,     label: "Dispute Resolution",   path: "/dispute-resolution",                           permission: PERMISSION_MAP.DISPUTES },
    { icon: AlertTriangle,   label: "Chargebacks",          path: "/chargeback-management",                        permission: PERMISSION_MAP.DISPUTES },
    { icon: Shield,          label: "Arbitration",          path: "/dispute-arbitration",                          permission: PERMISSION_MAP.DISPUTES },
    { icon: Users,           label: "Customer Portal",      path: "/customer-dispute-portal",                      permission: PERMISSION_MAP.DISPUTES },
    { icon: Cpu,             label: "Mediation AI",         path: "/dispute-mediation-ai",                         permission: PERMISSION_MAP.DISPUTES },
    { icon: Settings,        label: "Dispute Auto Rules",   path: "/dispute-auto-rules",                           permission: PERMISSION_MAP.DISPUTES },
    { icon: FileText,        label: "Compliance",           path: "/compliance",                                   permission: PERMISSION_MAP.VERIFY_KYC },
    { icon: Eye,             label: "Audit Logs",           path: "/audit",                                        permission: PERMISSION_MAP.AUDIT_LOGS },

    // Settlement
    { icon: CreditCard,      label: "Settlement Reconciliation", path: "/settlement-reconciliation",               permission: PERMISSION_MAP.VIEW_ANALYTICS },
    { icon: BarChart3,       label: "Settlement Batches",   path: "/settlement-batch-processor",                   permission: PERMISSION_MAP.VIEW_ANALYTICS },

    // 7. Communication & Monitoring
    { icon: MessageSquare,   label: "Communication",        path: "/communication",                                permission: PERMISSION_MAP.COMMUNICATION },
    { icon: Bell,            label: "Notifications",        path: "/notifications",                                permission: PERMISSION_MAP.NOTIFICATIONS },
    { icon: Wifi,            label: "Network Status",       path: "/network-operations",                           permission: PERMISSION_MAP.ERP },
    { icon: Activity,        label: "Monitoring",           path: "/monitoring",                                   permission: PERMISSION_MAP.VIEW_ALL },

    // 8. Platform Configuration
    { icon: Settings,        label: "Settings",             path: "/settings",                                     permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
  ];

  const menuItems = allMenuItems.filter((item) => {
    if (item.permission === null) return true;
    // if (item.permission) return hasPermission(item.permission.resourceType, item.permission.permission);
    return true;
  });

  return (
    <div className="flex h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "w-64" : "w-20"
        } text-white transition-all duration-300 flex flex-col shadow-2xl overflow-hidden`}
        style={{
          background: `linear-gradient(to bottom, var(--tenant-primary-color, #002082), color-mix(in srgb, var(--tenant-primary-color, #002082) 70%, black))`,
        }}
      >
        {/* Logo */}
        <div
          className="p-4 flex items-center justify-between border-b"
          style={{
            borderColor: "rgba(255,255,255,0.1)",
            backgroundColor: "rgba(0, 0, 0, 0.2)",
          }}
        >
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              {logoUrl ? (
                <img
                  src={logoUrl}
                  alt={tenantName}
                  className="h-8 w-auto object-contain"
                />
              ) : (
                <div className="h-8 w-8 rounded-lg bg-white/20 flex items-center justify-center text-white text-xs font-bold">
                  {tenantName.slice(0, 2).toUpperCase()}
                </div>
              )}
              <h1 className="text-xl font-bold text-white truncate">
                {tenantName}
              </h1>
            </div>
          )}
          {!sidebarOpen && (
            logoUrl ? (
              <img
                src={logoUrl}
                alt={tenantName}
                className="h-8 w-auto object-contain mx-auto"
              />
            ) : (
              <div className="h-8 w-8 rounded-lg bg-white/20 flex items-center justify-center text-white text-xs font-bold mx-auto">
                {tenantName.slice(0, 2).toUpperCase()}
              </div>
            )
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg transition-all"
            style={{ backgroundColor: "transparent" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor =
                "rgba(255, 255, 255, 0.1)";
              e.currentTarget.style.transform = "scale(1.1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.transform = "scale(1)";
            }}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 overflow-y-auto" data-tour="sidebar-nav">
  {filteredSections.map((section) => {
    const isCollapsed = sidebarOpen && !!collapsedSections[section.title];
    return (
      <div key={section.title} className="mb-3">
        {/* SECTION HEADER */}
        {sidebarOpen ? (
          <button
            onClick={() => toggleSection(section.title)}
            className="w-full flex items-center justify-between px-2 py-1 mb-1 rounded-md hover:bg-white/5 transition-colors"
          >
            <span className="text-[10px] font-bold text-white/40 tracking-widest uppercase">
              {section.title}
            </span>
            <ChevronDown
              size={11}
              className="text-white/40 flex-shrink-0 transition-transform duration-200"
              style={{ transform: isCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}
            />
          </button>
        ) : (
          <div className="h-px bg-white/10 my-2 mx-1" />
        )}

        {/* ITEMS */}
        {!isCollapsed && (
          <div className="space-y-0.5">
            {section.items.map((item: any) => {
              const isActive = pathname === item.path || pathname.startsWith(item.path + "/");
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-tour={item.tourId}
                  title={!sidebarOpen ? item.label : undefined}
                  className="relative flex items-center gap-3 px-2.5 py-2 rounded-lg transition-all duration-150"
                  style={{
                    backgroundColor: isActive ? "var(--tenant-secondary-color, #6CC049)" : "transparent",
                    color: isActive ? "#1F2937" : "rgba(255,255,255,0.8)",
                    fontWeight: isActive ? 600 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.1)";
                      e.currentTarget.style.color = "rgba(255,255,255,1)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "rgba(255,255,255,0.8)";
                    }
                  }}
                >
                  <item.icon size={17} className="flex-shrink-0" />
                  {sidebarOpen && <span className="text-sm truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    );
  })}
</nav>

        {/* User Profile */}
        <div
          className="p-4 border-t"
          style={{
            borderColor: "rgba(255,255,255,0.1)",
            backgroundColor: "rgba(0, 0, 0, 0.2)",
          }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center shadow-lg"
              style={{ backgroundColor: "var(--tenant-secondary-color, #6CC049)" }}
            >
              <User size={20} style={{ color: "#1F2937" }} />
            </div>
            {sidebarOpen && (
              <div className="flex-1">
                <p className="font-semibold" style={{ color: "white" }}>
                  {userName}
                </p>
                <p className="text-sm" style={{ color: "#9CA3AF" }}>
                  {adminRole.replace(/_/g, " ")}
                </p>
              </div>
            )}
          </div>
          <button
            data-tour="tour-help"
            onClick={startTour}
            title="Start platform guide"
            className="w-full mt-2 flex items-center justify-center gap-2 p-2.5 rounded-lg transition-all font-medium"
            style={{ background: "rgba(255,255,255,0.1)", color: "var(--tenant-secondary-color, #6CC049)", border: "1px solid rgba(255,255,255,0.2)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.2)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
          >
            <span style={{ fontSize: 16 }}>?</span>
            {sidebarOpen && <span>Platform Guide</span>}
          </button>

          <button
            onClick={handleLogout}
            className="w-full mt-2 flex items-center justify-center gap-2 p-2.5 rounded-lg transition-all font-medium shadow-lg"
            style={{
              background: "linear-gradient(to right, #DC2626, #B91C1C)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background =
                "linear-gradient(to right, #B91C1C, #991B1B)";
              e.currentTarget.style.boxShadow =
                "0 10px 15px -3px rgba(0, 0, 0, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background =
                "linear-gradient(to right, #DC2626, #B91C1C)";
              e.currentTarget.style.boxShadow =
                "0 4px 6px -1px rgba(0, 0, 0, 0.1)";
            }}
          >
            <LogOut size={18} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">{children}</main>

      <AppTour run={tourRun} onFinish={stopTour} />
    </div>
  );
};

// Main App Component
function App() {
  return (
    <TenantBrandingProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected Routes */}
          <Route
            path="/mdm"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <MDM />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/loyalty"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <LoyaltyPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/service-integrations"
            element={<Navigate to="/service-integrations/erpnext" replace />}
          />
          <Route
            path="/service-integrations/erpnext"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ErpNextPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/service-integrations/fraud-engine"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <FraudEnginePage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/nigeria-vat"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <NigeriaVatPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/service-integrations/nigeria-vat"
            element={<Navigate to="/nigeria-vat" replace />}
          />
          <Route
            path="/service-integrations/stablecoin"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ServiceIntegrations initialTab="stablecoin" />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/service-integrations/storefront-advertising"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <StorefrontAdvertisingPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <Dashboard />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/customers"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <UserManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agents"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/businesses"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <StoresList />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admins"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AdminManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/pos-hardware"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <POSHardwareInventory />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/device-catalog"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DeviceCatalog />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/pos"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <POSManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/pos-requests"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <POSRequestManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/geofence-violations"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <GeofenceViolationsMonitor />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/commission"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <CommissionSettlement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/transactions"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <TransactionManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ReportsAnalytics />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-business-reports"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentBusinessReports />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceMonitoring />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/security"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SecurityCenter />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <NotificationCenter />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AuditLogs />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/monitoring"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <PerformanceMonitoring />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SystemSettings />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/inventory"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <StoresList />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          {/* <Route
            path="/storefront"
            element={
              <ProtectedRoute>
                <MainLayout><StorefrontManagement /> </MainLayout>
              </ProtectedRoute>
            }
          /> */}
          <Route
            path="/communication"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <CommunicationManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/projections"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ProjectionsAnalytics />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/hierarchy"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <HierarchyManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/chart-of-accounts"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ChartOfAccounts />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/disputes"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AdminDisputeManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dispute-resolution"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DisputeResolutionPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/chargeback-management"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ChargebackManagement />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dispute-arbitration"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DisputeArbitration />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/customer-dispute-portal"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <CustomerDisputePortal />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dispute-mediation-ai"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DisputeMediationAI />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dispute-auto-rules"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DisputeAutoRules />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settlement-reconciliation"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SettlementReconciliation />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settlement-batch-processor"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SettlementBatchProcessor />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/network-operations"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <NetworkStatusMonitor />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/network-transactions"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <NetworkOperations />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/core-transactions"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <Transactions />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/transfer"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <Transfer />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/loans"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <Loans />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/qrcode"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <QRCodePage />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/agent-gamification"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentGamificationPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-training"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentTrainingPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceLeaderboardPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/overview"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformance />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/analytics"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceAnalytics />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/incentives"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceIncentives />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/ranking"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceLeaderboard />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/scorecard"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceScorecardPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-performance/scoring"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentPerformanceScoring />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/agent-training/academy"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentTrainingAcademy />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-training/portal"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentTrainingPortal />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/agent-gamification/overview"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AgentGamification />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/compliance/automation"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceAutomationPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/certificates"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceCertManager />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/chatbot"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceChatbotPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/filing"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceFilingPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/reporting"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceReporting />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/scheduling"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceScheduling />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/training"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceTrainingPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance/training-tracker"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ComplianceTrainingTracker />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          {/* Developer Portal */}
          <Route path="/developer" element={<ProtectedRoute><MainLayout><DeveloperPortal /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/api-keys" element={<ProtectedRoute><MainLayout><ApiKeyManagement /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhooks" element={<ProtectedRoute><MainLayout><WebhookManagement /></MainLayout></ProtectedRoute>} />

          {/* Finance & Recovery */}
          <Route path="/finance/revenue-leakage" element={<ProtectedRoute><MainLayout><RevenueLeakage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/netting-engine" element={<ProtectedRoute><MainLayout><NettingEngine /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/commission-clawback" element={<ProtectedRoute><MainLayout><CommissionClawback /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/credit-ratings" element={<ProtectedRoute><MainLayout><CreditRatingSystem /></MainLayout></ProtectedRoute>} />

          {/* GDPR & Regulatory */}
          <Route path="/compliance/gdpr" element={<ProtectedRoute><MainLayout><GDPRModule /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/cbn-reports" element={<ProtectedRoute><MainLayout><CBNScheduledReports /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/nfiu" element={<ProtectedRoute><MainLayout><NFIUReporting /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/sandbox" element={<ProtectedRoute><MainLayout><RegulatorySandbox /></MainLayout></ProtectedRoute>} />

          {/* Operations & Engineering */}
          <Route path="/ops/incidents" element={<ProtectedRoute><MainLayout><IncidentManagement /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/ab-testing" element={<ProtectedRoute><MainLayout><ABTesting /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/canary" element={<ProtectedRoute><MainLayout><CanaryRelease /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/territory" element={<ProtectedRoute><MainLayout><TerritoryAnalytics /></MainLayout></ProtectedRoute>} />

          {/* Developer & API Tooling */}
          <Route path="/developer/api-analytics" element={<ProtectedRoute><MainLayout><APIAnalyticsDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/rate-limiter" element={<ProtectedRoute><MainLayout><APIRateLimiterDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/versioning" element={<ProtectedRoute><MainLayout><APIVersioningPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/integrations" element={<ProtectedRoute><MainLayout><IntegrationMarketplace /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/publish-readiness" element={<ProtectedRoute><MainLayout><PublishReadinessChecker /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/production-checklist" element={<ProtectedRoute><MainLayout><ProductionReadinessChecklist /></MainLayout></ProtectedRoute>} />

          {/* Advanced Operations Dashboards */}
          <Route path="/ops/chaos-engineering" element={<ProtectedRoute><MainLayout><ChaosEngineeringConsole /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/load-testing" element={<ProtectedRoute><MainLayout><LoadTestDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/service-mesh" element={<ProtectedRoute><MainLayout><ServiceMeshDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/mqtt-bridge" element={<ProtectedRoute><MainLayout><MQTTBridgeDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/sim-orchestrator" element={<ProtectedRoute><MainLayout><SIMOrchestratorDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/carrier-management" element={<ProtectedRoute><MainLayout><CarrierManagement /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/network-telemetry" element={<ProtectedRoute><MainLayout><NetworkTelemetry /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/connection-quality" element={<ProtectedRoute><MainLayout><ConnectionQualityMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/connection-pool" element={<ProtectedRoute><MainLayout><ConnectionPoolMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/cache-management" element={<ProtectedRoute><MainLayout><CacheManagementDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/retry-queue" element={<ProtectedRoute><MainLayout><RetryQueueViewer /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/archival" element={<ProtectedRoute><MainLayout><ArchivalAdmin /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/db-schema" element={<ProtectedRoute><MainLayout><DatabaseSchemaVisualization /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/opentelemetry" element={<ProtectedRoute><MainLayout><OpenTelemetryConfig /></MainLayout></ProtectedRoute>} />

          {/* Advanced Compliance */}
          <Route path="/compliance/data-retention" element={<ProtectedRoute><MainLayout><DataRetentionPolicy /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/live-chat" element={<ProtectedRoute><MainLayout><LiveChatSupport /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/help-desk" element={<ProtectedRoute><MainLayout><HelpDesk /></MainLayout></ProtectedRoute>} />

{/* Other Notable Additions */}
          <Route path="/social-commerce" element={<ProtectedRoute><MainLayout><SocialCommerceGateway /></MainLayout></ProtectedRoute>} />
          <Route path="/esg" element={<ProtectedRoute><MainLayout><ESGCarbonTracker /></MainLayout></ProtectedRoute>} />
          <Route path="/payment-orchestration" element={<ProtectedRoute><MainLayout><MultiChannelPaymentOrchestration /></MainLayout></ProtectedRoute>} />
          <Route path="/revenue-forecasting" element={<ProtectedRoute><MainLayout><RevenueForecastingEngine /></MainLayout></ProtectedRoute>} />

          {/* Billing Engine */}
          <Route path="/billing" element={<ProtectedRoute><MainLayout><BillingDashboardPage /></MainLayout></ProtectedRoute>} />
          <Route path="/billing/credits" element={<ProtectedRoute><MainLayout><CreditsPaymentsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/billing/invoices" element={<ProtectedRoute><MainLayout><InvoiceManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/billing/ledger" element={<ProtectedRoute><MainLayout><BillingLedgerPage /></MainLayout></ProtectedRoute>} />

          {/* Compliance (NGApp additions) */}
          <Route path="/compliance/regulatory-sandbox" element={<ProtectedRoute><MainLayout><RegulatorySandboxPage /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/regulatory-sandbox-tester" element={<ProtectedRoute><MainLayout><RegulatorySandboxTester /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/auto-workflow" element={<ProtectedRoute><MainLayout><AutoComplianceWorkflow /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/gdpr" element={<ProtectedRoute><MainLayout><GdprDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/compliance/blockchain-audit" element={<ProtectedRoute><MainLayout><BlockchainAuditTrail /></MainLayout></ProtectedRoute>} />
          {/* Merchant Management (NGApp) */}
          <Route path="/merchant-portal" element={<ProtectedRoute><MainLayout><MerchantPortal /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-analytics" element={<ProtectedRoute><MainLayout><MerchantAnalyticsDash /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-risk-scoring" element={<ProtectedRoute><MainLayout><MerchantRiskScoring /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-settlement" element={<ProtectedRoute><MainLayout><MerchantSettlementDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-kyc-onboarding" element={<ProtectedRoute><MainLayout><MerchantKycOnboardingPage /></MainLayout></ProtectedRoute>} />
          {/* Customer Management (NGApp) */}
          <Route path="/customer-360" element={<ProtectedRoute><MainLayout><Customer360Page /></MainLayout></ProtectedRoute>} />
          <Route path="/customer-segmentation" element={<ProtectedRoute><MainLayout><CustomerSegmentationEngine /></MainLayout></ProtectedRoute>} />
          <Route path="/customer-journey-analytics" element={<ProtectedRoute><MainLayout><CustomerJourneyAnalyticsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/customer-onboarding-pipeline" element={<ProtectedRoute><MainLayout><CustomerOnboardingPipeline /></MainLayout></ProtectedRoute>} />
          {/* Fraud & Disputes (NGApp) */}
          <Route path="/dispute-workflow-engine" element={<ProtectedRoute><MainLayout><DisputeWorkflowEngine /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud-case-management" element={<ProtectedRoute><MainLayout><FraudCaseManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud-ml-scoring" element={<ProtectedRoute><MainLayout><FraudMlScoringPage /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud-realtime-viz" element={<ProtectedRoute><MainLayout><FraudRealtimeVizPage /></MainLayout></ProtectedRoute>} />

          {/* ── Agent Management ─────────────────────────────────────────── */}
          <Route path="/agent-management" element={<ProtectedRoute><MainLayout><AgentManagementDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/portal" element={<ProtectedRoute><MainLayout><AgentPortal /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/onboarding" element={<ProtectedRoute><MainLayout><AgentOnboarding /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/onboarding/wizard" element={<ProtectedRoute><MainLayout><AgentOnboardingWizardPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/onboarding/workflow" element={<ProtectedRoute><MainLayout><AgentOnboardingWorkflowPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/store-setup" element={<ProtectedRoute><MainLayout><AgentStoreSetup /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/hierarchy" element={<ProtectedRoute><MainLayout><AgentHierarchyPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/geo-fencing" element={<ProtectedRoute><MainLayout><AgentGeoFencingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/inventory" element={<ProtectedRoute><MainLayout><AgentInventoryMgmt /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/kyc" element={<ProtectedRoute><MainLayout><AgentKycPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/loan-advance" element={<ProtectedRoute><MainLayout><AgentLoanAdvance /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/loan-origination" element={<ProtectedRoute><MainLayout><AgentLoanOriginationV2 /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/micro-insurance" element={<ProtectedRoute><MainLayout><AgentMicroInsurance /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/float-insurance-claims" element={<ProtectedRoute><MainLayout><AgentFloatInsuranceClaims /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/device-fingerprint" element={<ProtectedRoute><MainLayout><AgentDeviceFingerprint /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/commission-calc" element={<ProtectedRoute><MainLayout><AgentCommissionCalc /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/scorecard" element={<ProtectedRoute><MainLayout><AgentScorecardPage /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/benchmarking" element={<ProtectedRoute><MainLayout><AgentBenchmarking /></MainLayout></ProtectedRoute>} />
          <Route path="/agent/cluster-analytics" element={<ProtectedRoute><MainLayout><AgentClusterAnalytics /></MainLayout></ProtectedRoute>} />

          {/* ── Analytics & Reports ─────────────────────────────────────── */}
          <Route path="/analytics" element={<ProtectedRoute><MainLayout><AnalyticsDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/bi-reporting" element={<ProtectedRoute><MainLayout><AdvancedBiReportingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/drag-drop-reports" element={<ProtectedRoute><MainLayout><DragDropReportBuilderPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/report-templates" element={<ProtectedRoute><MainLayout><ReportBuilderTemplatesPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/report-scheduler" element={<ProtectedRoute><MainLayout><ReportSchedulerPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/report-template-designer" element={<ProtectedRoute><MainLayout><ReportTemplateDesigner /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/scheduled-reports" element={<ProtectedRoute><MainLayout><ReportScheduler /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/report-comparison" element={<ProtectedRoute><MainLayout><ReportComparison /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/nl-query" element={<ProtectedRoute><MainLayout><NLAnalyticsQueryPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/nl-financial-query" element={<ProtectedRoute><MainLayout><NlFinancialQuery /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/lakehouse-ai" element={<ProtectedRoute><MainLayout><LakehouseAiDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/lakehouse" element={<ProtectedRoute><MainLayout><LakehouseAnalytics /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/ml-scoring" element={<ProtectedRoute><MainLayout><MLScoringDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/transactions" element={<ProtectedRoute><MainLayout><TransactionAnalytics /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/weekly-reports" element={<ProtectedRoute><MainLayout><WeeklyReports /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/data-export" element={<ProtectedRoute><MainLayout><DataExportCenter /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/data-export-hub" element={<ProtectedRoute><MainLayout><DataExportHubPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/data-export-import" element={<ProtectedRoute><MainLayout><DataExportImportPage /></MainLayout></ProtectedRoute>} />
          <Route path="/analytics/data-quality" element={<ProtectedRoute><MainLayout><DataQualityPage /></MainLayout></ProtectedRoute>} />

          {/* ── Finance ────────────────────────────────────────────────── */}
          <Route path="/finance/commission-calculator" element={<ProtectedRoute><MainLayout><CommissionCalculatorPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/commission-config" element={<ProtectedRoute><MainLayout><CommissionConfig /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/commission-engine" element={<ProtectedRoute><MainLayout><CommissionEnginePage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/commission-payouts" element={<ProtectedRoute><MainLayout><CommissionPayouts /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/daily-pnl" element={<ProtectedRoute><MainLayout><DailyPnlReportPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/pnl-report" element={<ProtectedRoute><MainLayout><PnlReportPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/realtime-pnl" element={<ProtectedRoute><MainLayout><RealtimePnlDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/general-ledger" element={<ProtectedRoute><MainLayout><GeneralLedgerPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/tigerbeetle-ledger" element={<ProtectedRoute><MainLayout><TigerBeetleLedger /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/float-management" element={<ProtectedRoute><MainLayout><FloatManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/float-reconciliation" element={<ProtectedRoute><MainLayout><FloatReconciliationPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/reconciliation" element={<ProtectedRoute><MainLayout><FinancialReconciliationPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/reporting-suite" element={<ProtectedRoute><MainLayout><FinancialReportingSuite /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/tax-collection" element={<ProtectedRoute><MainLayout><TaxCollectionPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/bulk-disbursement" element={<ProtectedRoute><MainLayout><BulkDisbursementEngine /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/payroll" element={<ProtectedRoute><MainLayout><PayrollDisbursement /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/multi-currency" element={<ProtectedRoute><MainLayout><MultiCurrency /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/currency-exchange" element={<ProtectedRoute><MainLayout><MultiCurrencyExchange /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/multi-currency-page" element={<ProtectedRoute><MainLayout><MultiCurrencyPage /></MainLayout></ProtectedRoute>} />

          {/* ── Payments & Transactions ─────────────────────────────────── */}
          <Route path="/payments" element={<ProtectedRoute><MainLayout><Payments /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/gateway-router" element={<ProtectedRoute><MainLayout><PaymentGatewayRouter /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/reconciliation" element={<ProtectedRoute><MainLayout><PaymentReconciliation /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/dispute-arbitration" element={<ProtectedRoute><MainLayout><PaymentDisputeArbitration /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/token-vault" element={<ProtectedRoute><MainLayout><PaymentTokenVault /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/link-generator" element={<ProtectedRoute><MainLayout><PaymentLinkGenerator /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/notification-system" element={<ProtectedRoute><MainLayout><PaymentNotificationSystem /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/dynamic-fee-calculator" element={<ProtectedRoute><MainLayout><DynamicFeeCalculator /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/dynamic-fee-engine" element={<ProtectedRoute><MainLayout><DynamicFeeEnginePage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/transaction-fee-calc" element={<ProtectedRoute><MainLayout><TransactionFeeCalc /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/bulk-payment-processor" element={<ProtectedRoute><MainLayout><BulkPaymentProcessor /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/bulk-transaction" element={<ProtectedRoute><MainLayout><BulkTransactionProcessing /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/bulk-transaction-processor" element={<ProtectedRoute><MainLayout><BulkTransactionProcessor /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/bulk-operations" element={<ProtectedRoute><MainLayout><BulkOperationsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/batch-processing" element={<ProtectedRoute><MainLayout><BatchProcessingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/multi-channel" element={<ProtectedRoute><MainLayout><MultiChannelPaymentOrchNew /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/rate-limit-dashboard" element={<ProtectedRoute><MainLayout><RateLimitDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/rate-limit-engine" element={<ProtectedRoute><MainLayout><RateLimitEnginePage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/advanced-rate-limiter" element={<ProtectedRoute><MainLayout><AdvancedRateLimiterPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/settlement-scheduler" element={<ProtectedRoute><MainLayout><AutomatedSettlementScheduler /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/csv-export" element={<ProtectedRoute><MainLayout><TransactionCsvExport /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/dispute-resolution" element={<ProtectedRoute><MainLayout><TransactionDisputeResolutionPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/enrichment" element={<ProtectedRoute><MainLayout><TransactionEnrichmentService /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/export-engine" element={<ProtectedRoute><MainLayout><TransactionExportEngine /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/graph-analyzer" element={<ProtectedRoute><MainLayout><TransactionGraphAnalyzer /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/limits-engine" element={<ProtectedRoute><MainLayout><TransactionLimitsEnginePage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/map-viz" element={<ProtectedRoute><MainLayout><TransactionMapVizPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/receipt-generator" element={<ProtectedRoute><MainLayout><TransactionReceiptGenerator /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/tx-reconciliation" element={<ProtectedRoute><MainLayout><TransactionReconciliationPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/reversal-manager" element={<ProtectedRoute><MainLayout><TransactionReversalManager /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/reversal-workflow" element={<ProtectedRoute><MainLayout><TransactionReversalWorkflowPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/velocity-monitor" element={<ProtectedRoute><MainLayout><TransactionVelocityMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/tx-monitor" element={<ProtectedRoute><MainLayout><TxMonitorPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/tx-velocity-monitor" element={<ProtectedRoute><MainLayout><TxVelocityMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/realtime-tx-monitor" element={<ProtectedRoute><MainLayout><RealtimeTxMonitorPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/realtime-dashboard-widgets" element={<ProtectedRoute><MainLayout><RealtimeDashboardWidgetsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/realtime-websocket-feeds" element={<ProtectedRoute><MainLayout><RealtimeWebSocketFeeds /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/reconciliation-engine" element={<ProtectedRoute><MainLayout><ReconciliationEnginePage /></MainLayout></ProtectedRoute>} />

          {/* ── Notifications ───────────────────────────────────────────── */}
          <Route path="/notifications/center" element={<ProtectedRoute><MainLayout><NotificationCenterPage /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/inbox" element={<ProtectedRoute><MainLayout><NotificationInbox /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/orchestrator" element={<ProtectedRoute><MainLayout><NotificationOrchestratorPage /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/preference-matrix" element={<ProtectedRoute><MainLayout><NotificationPreferenceMatrix /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/preferences" element={<ProtectedRoute><MainLayout><NotificationPreferences /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/template-manager" element={<ProtectedRoute><MainLayout><NotificationTemplateManager /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/multi-channel" element={<ProtectedRoute><MainLayout><MultiChannelNotificationHub /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/broadcast-manager" element={<ProtectedRoute><MainLayout><BroadcastManager /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/whatsapp" element={<ProtectedRoute><MainLayout><WhatsAppChannelPage /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/bulk-sender" element={<ProtectedRoute><MainLayout><BulkNotifSender /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/push-config" element={<ProtectedRoute><MainLayout><PushNotificationConfig /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/realtime" element={<ProtectedRoute><MainLayout><RealtimeNotificationsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/analytics" element={<ProtectedRoute><MainLayout><NotificationAnalytics /></MainLayout></ProtectedRoute>} />
          <Route path="/notifications/alert-preferences" element={<ProtectedRoute><MainLayout><AlertNotificationPreferences /></MainLayout></ProtectedRoute>} />

          {/* ── Platform & Infrastructure ───────────────────────────────── */}
          <Route path="/platform" element={<ProtectedRoute><MainLayout><PlatformHub /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/health" element={<ProtectedRoute><MainLayout><PlatformHealthPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/changelog" element={<ProtectedRoute><MainLayout><PlatformChangelogPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/infrastructure" element={<ProtectedRoute><MainLayout><InfrastructureDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/backup-dr" element={<ProtectedRoute><MainLayout><BackupDRPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/backup-disaster-recovery" element={<ProtectedRoute><MainLayout><BackupDisasterRecoveryPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/config-management" element={<ProtectedRoute><MainLayout><ConfigManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/system-config" element={<ProtectedRoute><MainLayout><SystemConfigManager /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/system-health" element={<ProtectedRoute><MainLayout><SystemHealth /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/system-health-dashboard" element={<ProtectedRoute><MainLayout><SystemHealthDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/system-health-page" element={<ProtectedRoute><MainLayout><SystemHealthDashboardPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/system-status" element={<ProtectedRoute><MainLayout><SystemStatus /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/capacity-planning" element={<ProtectedRoute><MainLayout><CapacityPlanningPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/feature-flags" element={<ProtectedRoute><MainLayout><FeatureFlagsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/network-quality-heatmap" element={<ProtectedRoute><MainLayout><NetworkQualityHeatmap /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/network-status" element={<ProtectedRoute><MainLayout><NetworkStatusDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/network-diagnostic" element={<ProtectedRoute><MainLayout><NetworkDiagnosticPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/temporal-workflow" element={<ProtectedRoute><MainLayout><TemporalWorkflowMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/resilience-monitor" element={<ProtectedRoute><MainLayout><ResilienceMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/middleware" element={<ProtectedRoute><MainLayout><MiddlewareServiceManager /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/migration-tools" element={<ProtectedRoute><MainLayout><MigrationToolsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/vault-secrets" element={<ProtectedRoute><MainLayout><VaultSecretsManager /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/sim-orchestrator" element={<ProtectedRoute><MainLayout><SimOrchestratorDashboardNew /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/distributed-tracing" element={<ProtectedRoute><MainLayout><DistributedTracingDash /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/event-driven-arch" element={<ProtectedRoute><MainLayout><EventDrivenArchPage /></MainLayout></ProtectedRoute>} />

          {/* ── Fraud & Incidents ────────────────────────────────────────── */}
          <Route path="/fraud/dashboard" element={<ProtectedRoute><MainLayout><FraudDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud/ransomware-alerts" element={<ProtectedRoute><MainLayout><RansomwareAlertDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud/incident-command" element={<ProtectedRoute><MainLayout><IncidentCommandCenter /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud/incident-playbook" element={<ProtectedRoute><MainLayout><IncidentPlaybook /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud/incident-management" element={<ProtectedRoute><MainLayout><IncidentManagementPage /></MainLayout></ProtectedRoute>} />

          {/* ── KYC & Regulatory ────────────────────────────────────────── */}
          <Route path="/kyc/document-management" element={<ProtectedRoute><MainLayout><KycDocumentManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/verification-workflow" element={<ProtectedRoute><MainLayout><KycVerificationWorkflow /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/workflow" element={<ProtectedRoute><MainLayout><KycWorkflow /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/cbn-reporting" element={<ProtectedRoute><MainLayout><CbnReportingDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/regulatory-report-generator" element={<ProtectedRoute><MainLayout><RegulatoryReportGenerator /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/regulatory-compliance" element={<ProtectedRoute><MainLayout><RegulatoryCompliancePage /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/regulatory-filing" element={<ProtectedRoute><MainLayout><RegulatoryFilingAutomation /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/regulatory-reporting" element={<ProtectedRoute><MainLayout><RegulatoryReportingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/kyc/automated-compliance" element={<ProtectedRoute><MainLayout><AutomatedComplianceChecker /></MainLayout></ProtectedRoute>} />

          {/* ── Merchant (extended) ──────────────────────────────────────── */}
          <Route path="/merchant/acquirer-gateway" element={<ProtectedRoute><MainLayout><MerchantAcquirerGateway /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant/onboarding" element={<ProtectedRoute><MainLayout><MerchantOnboardingPortal /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant/payments" element={<ProtectedRoute><MainLayout><MerchantPaymentsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/merchant/payout-settlement" element={<ProtectedRoute><MainLayout><MerchantPayoutSettlementPage /></MainLayout></ProtectedRoute>} />

          {/* ── Customer (extended) ──────────────────────────────────────── */}
          <Route path="/customer/360-view" element={<ProtectedRoute><MainLayout><Customer360View /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/database" element={<ProtectedRoute><MainLayout><CustomerDatabasePage /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/feedback-nps" element={<ProtectedRoute><MainLayout><CustomerFeedbackNps /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/journey-mapper" element={<ProtectedRoute><MainLayout><CustomerJourneyMapper /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/portal" element={<ProtectedRoute><MainLayout><CustomerPortal /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/surveys" element={<ProtectedRoute><MainLayout><CustomerSurveys /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/wallet" element={<ProtectedRoute><MainLayout><CustomerWallet /></MainLayout></ProtectedRoute>} />
          <Route path="/customer/wallet-system" element={<ProtectedRoute><MainLayout><CustomerWalletSystem /></MainLayout></ProtectedRoute>} />

          {/* ── Webhooks & Developer (extended) ─────────────────────────── */}
          <Route path="/developer/api-docs" element={<ProtectedRoute><MainLayout><ApiDocs /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/api-gateway" element={<ProtectedRoute><MainLayout><ApiGatewayPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/graphql-federation" element={<ProtectedRoute><MainLayout><GraphqlFederationPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/graphql-subscriptions" element={<ProtectedRoute><MainLayout><GraphqlSubscriptionGateway /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-config" element={<ProtectedRoute><MainLayout><WebhookConfig /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-delivery-monitor" element={<ProtectedRoute><MainLayout><WebhookDeliveryMonitor /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-delivery-system" element={<ProtectedRoute><MainLayout><WebhookDeliverySystem /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-delivery-viewer" element={<ProtectedRoute><MainLayout><WebhookDeliveryViewer /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-management" element={<ProtectedRoute><MainLayout><WebhookManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-manager" element={<ProtectedRoute><MainLayout><WebhookManager /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/webhook-console" element={<ProtectedRoute><MainLayout><WebhookMgmtConsole /></MainLayout></ProtectedRoute>} />

          {/* ── Security ────────────────────────────────────────────────── */}
          <Route path="/security/biometric-gateway" element={<ProtectedRoute><MainLayout><BiometricAuthGateway /></MainLayout></ProtectedRoute>} />
          <Route path="/security/biometric-auth" element={<ProtectedRoute><MainLayout><BiometricAuthPage /></MainLayout></ProtectedRoute>} />
          <Route path="/security/mfa-manager" element={<ProtectedRoute><MainLayout><MfaManager /></MainLayout></ProtectedRoute>} />
          <Route path="/security/session-manager" element={<ProtectedRoute><MainLayout><SessionManager /></MainLayout></ProtectedRoute>} />
          <Route path="/security/pbac" element={<ProtectedRoute><MainLayout><PBACManagement /></MainLayout></ProtectedRoute>} />
          <Route path="/security/decentralized-identity" element={<ProtectedRoute><MainLayout><DecentralizedIdentityManager /></MainLayout></ProtectedRoute>} />
          <Route path="/security/digital-identity" element={<ProtectedRoute><MainLayout><DigitalIdentityLayer /></MainLayout></ProtectedRoute>} />

          {/* ── Emerging & Niche ────────────────────────────────────────── */}
          <Route path="/emerging/cbdc" element={<ProtectedRoute><MainLayout><CbdcIntegrationGateway /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/stablecoin" element={<ProtectedRoute><MainLayout><StablecoinRails /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/tokenized-assets" element={<ProtectedRoute><MainLayout><TokenizedAssets /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/smart-contract" element={<ProtectedRoute><MainLayout><SmartContractPayment /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/carbon-marketplace" element={<ProtectedRoute><MainLayout><CarbonCreditMarketplace /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/health-insurance" element={<ProtectedRoute><MainLayout><HealthInsuranceMicro /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/education-payments" element={<ProtectedRoute><MainLayout><EducationPayments /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/agritech" element={<ProtectedRoute><MainLayout><AgritechPayments /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/wearable-payments" element={<ProtectedRoute><MainLayout><WearablePayments /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/nfc-tap-to-pay" element={<ProtectedRoute><MainLayout><NfcTapToPay /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/open-banking" element={<ProtectedRoute><MainLayout><OpenBankingApi /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/satellite" element={<ProtectedRoute><MainLayout><SatelliteConnectivity /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/iot-smart-pos" element={<ProtectedRoute><MainLayout><IotSmartPos /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/digital-twin" element={<ProtectedRoute><MainLayout><DigitalTwinSimulator /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/offline-pos" element={<ProtectedRoute><MainLayout><OfflinePosMode /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/voice-pos" element={<ProtectedRoute><MainLayout><VoiceCommandPos /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/pos-firmware-ota" element={<ProtectedRoute><MainLayout><POSFirmwareOTA /></MainLayout></ProtectedRoute>} />
          <Route path="/emerging/pos-shell" element={<ProtectedRoute><MainLayout><POSShell /></MainLayout></ProtectedRoute>} />

          {/* ── Remaining NGApp pages ─────────────────────────────────── */}
          <Route path="/airtime-vending" element={<ProtectedRoute><MainLayout><AirtimeVendingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/apache-airflow" element={<ProtectedRoute><MainLayout><ApacheAirflowPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/apache-nifi" element={<ProtectedRoute><MainLayout><ApacheNifiPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/api-analytics-dash" element={<ProtectedRoute><MainLayout><ApiAnalyticsPage /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/api-rate-limiter-dash" element={<ProtectedRoute><MainLayout><ApiRateLimiterDash /></MainLayout></ProtectedRoute>} />
          <Route path="/developer/api-versioning" element={<ProtectedRoute><MainLayout><ApiVersioningPage /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/e2e-testing" element={<ProtectedRoute><MainLayout><AutomatedTestingFrameworkPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/card-bin-lookup" element={<ProtectedRoute><MainLayout><CardBinLookup /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/card-request" element={<ProtectedRoute><MainLayout><CardRequestPage /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/carrier-cost" element={<ProtectedRoute><MainLayout><CarrierCostDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/carrier-live-pricing" element={<ProtectedRoute><MainLayout><CarrierLivePricingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/carrier-sla" element={<ProtectedRoute><MainLayout><CarrierSlaDashboard /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/cdn-cache-manager" element={<ProtectedRoute><MainLayout><CdnCacheManager /></MainLayout></ProtectedRoute>} />
          <Route path="/disputes/chargeback-management-page" element={<ProtectedRoute><MainLayout><ChargebackManagementPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/commission-clawback-page" element={<ProtectedRoute><MainLayout><CommissionClawbackPage /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/connection-quality-page" element={<ProtectedRoute><MainLayout><ConnectionQualityPage /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/device-fleet-manager" element={<ProtectedRoute><MainLayout><DeviceFleetManager /></MainLayout></ProtectedRoute>} />
          <Route path="/disputes/arbitration-page" element={<ProtectedRoute><MainLayout><DisputeArbitrationPage /></MainLayout></ProtectedRoute>} />
          <Route path="/esg-carbon-tracker" element={<ProtectedRoute><MainLayout><EsgCarbonTracker /></MainLayout></ProtectedRoute>} />
          <Route path="/fraud/report" element={<ProtectedRoute><MainLayout><FraudReportPage /></MainLayout></ProtectedRoute>} />
          <Route path="/geo-fencing" element={<ProtectedRoute><MainLayout><GeoFencingPage /></MainLayout></ProtectedRoute>} />
          <Route path="/help-desk" element={<ProtectedRoute><MainLayout><HelpDeskPage /></MainLayout></ProtectedRoute>} />
          <Route path="/ops/load-test-comparison" element={<ProtectedRoute><MainLayout><LoadTestComparison /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/opentelemetry" element={<ProtectedRoute><MainLayout><OpenTelemetryPage /></MainLayout></ProtectedRoute>} />
          <Route path="/finance/revenue-leakage-detector" element={<ProtectedRoute><MainLayout><RevenueLeakageDetector /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/reversal-approval" element={<ProtectedRoute><MainLayout><ReversalApprovalPage /></MainLayout></ProtectedRoute>} />
          <Route path="/payments/transaction-map-loading" element={<ProtectedRoute><MainLayout><TransactionMapLoading /></MainLayout></ProtectedRoute>} />
          <Route path="/platform/websocket-service" element={<ProtectedRoute><MainLayout><WebSocketServicePage /></MainLayout></ProtectedRoute>} />

          {/* ── NEW ROUTES (lazy-loaded additions) ────────────────────────── */}
          <Route path="/hub" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformHubNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminPanel /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminDashboardPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/fraud" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FraudDashboardLazy /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminAnalyticsDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/audit" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditLogViewerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/tenant" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TenantAdminDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/invite-codes" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><InviteCodeManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminUserManagement /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/health" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminSystemHealth /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin/liveness-devices" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminLivenessDeviceAnalytics /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/admin-support-inbox" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminSupportInbox /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/supervisor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SupervisorDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ManagementPortal /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/management/:section" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ManagementPortal /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPortalNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerPortalNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/super-admin" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SuperAdminPortal /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/super-admin/:section" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SuperAdminPortal /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/developer/:section" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DeveloperPortal /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant/:section" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantPortalNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/privacy" element={<React.Suspense fallback={null}><PrivacyPolicy /></React.Suspense>} />
          <Route path="/system-health" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemHealthNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-health-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemHealthDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-health-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemHealthDashboardPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-config" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemConfigManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-config-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemConfigManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-settings" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemSettingsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/system-status" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SystemStatusNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/lakehouse" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LakehouseAnalyticsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/lakehouse-ai" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LakehouseAiDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhooks" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/commission-payouts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CommissionPayoutsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-onboarding" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentOnboardingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/referral-program" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReferralProgram /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/referral-program-v2" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReferralProgramPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/infrastructure" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><InfrastructureDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/live-chat" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LiveChatSupportNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-wallet" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerWalletNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-preferences" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationPreferencesNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-currency" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiCurrencyNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-currency-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiCurrencyPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-currency-exchange" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiCurrencyExchangeNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-scheduling" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceSchedulingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/audit-export" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditExportNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/audit-export-page" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditExportPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/audit-trail-export" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditTrailExportPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/audit-trail" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditTrailPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/audit-log-viewer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AuditLogViewerPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-deliveries" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookDeliveryViewerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-delivery" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookDeliverySystemNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-delivery-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookDeliveryMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-mgmt-console" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookMgmtConsoleNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/webhook-config" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebhookConfigNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/geofence-editor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GeofenceZoneEditor /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-keys" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiKeyManagementNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-key-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiKeyManagementNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/kyc-workflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><KycWorkflowNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/kyc-verification" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><KycVerificationWorkflowNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/kyc-documents" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><KycDocumentManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/onboarding-wizard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OnboardingWizard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/commission-config" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CommissionConfigNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/commission-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CommissionEnginePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/commission-clawback" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CommissionClawbackPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/commission-calculator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CommissionCalculatorPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/rate-alerts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RateAlerts /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-inbox" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationInboxNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-preference-matrix" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationPreferenceMatrixNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-templates" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationTemplateManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-settings" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UserNotifSettings /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-center" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationCenterPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationAnalyticsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-orchestrator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NotificationOrchestratorPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/notification-hub" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiChannelNotificationHubNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/realtime-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealtimeNotificationsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/batch-operations" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BatchOperations /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdminAnalyticsDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/broadcast-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BroadcastManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/scheduled-reports" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ScheduledReports /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/threshold-alerts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataThresholdAlerts /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/shared-layouts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SharedLayoutGallery /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/report-designer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReportTemplateDesignerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/partner/onboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PartnerOnboarding /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/escalation-chains" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><EscalationChains /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/quiet-hours" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UserQuietHours /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/data-export" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataExportCenterNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/data-export-hub" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataExportHubPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/data-export-import" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataExportImportPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/data-quality" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataQualityPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/data-retention-policy" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DataRetentionPolicyNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/changelog" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformChangelog /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-changelog" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformChangelogPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkNotifSenderNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/retry-queue" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RetryQueueViewerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/rate-limit-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RateLimitDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/rate-limit-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RateLimitEnginePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/service-health" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ServiceHealthAggregator /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cache-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CacheManagement /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/gdpr" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GdprDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cbn-reporting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CbnReportingDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tigerbeetle" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TigerBeetleLedgerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/temporal" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TemporalWorkflowMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/vault" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><VaultSecretsManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/resilience" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ResilienceMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/sim-orchestrator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SimOrchestratorDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/mqtt-bridge" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MqttBridgeDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/push-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PushNotificationConfigNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/business-rules" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BusinessRulesDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/announcement-reactions" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AnnouncementReactions /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/weekly-reports" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WeeklyReportsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/report-comparison" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReportComparisonNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/threshold-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ThresholdManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/endpoint-rate-limits" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><EndpointRateLimits /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-performance-scoring" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPerformanceScoringNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/production-readiness" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ProductionReadinessChecklistNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/publish-readiness" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PublishReadinessCheckerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/scheduled-email-delivery" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ScheduledEmailDelivery /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/global-search" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GlobalSearchPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/user-guide" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UserGuide /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/video-tutorials" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><VideoTutorials /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-success" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentSuccess /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-cancel" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentCancel /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentNotificationSystemNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-gateway-router" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentGatewayRouterNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-reconciliation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentReconciliationNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-link-generator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentLinkGeneratorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/payment-token-vault" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PaymentTokenVaultNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/feedback-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FeedbackAnalytics /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-docs" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiDocsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-gateway" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiGatewayPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiAnalyticsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-rate-limiter-dash" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiRateLimiterDashNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/api-versioning" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApiVersioningPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ussd-gateway" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UssdGateway /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/mobile-money" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MobileMoneyPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-hierarchy" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentHierarchyPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-hierarchy-territory" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentHierarchyTerritory /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-operations" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkOperationsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/biometric-auth" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BiometricAuthPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/offline-sync" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OfflineSyncPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/whatsapp-channel" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WhatsAppChannelPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-payments" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantPaymentsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bill-payments" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BillPaymentsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/loan-disbursement" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LoanDisbursementPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/insurance-products" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><InsuranceProductsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/savings-products" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SavingsProductsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/card-requests" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CardRequestPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/account-opening" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AccountOpeningPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tax-collection" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TaxCollectionPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/pension-collection" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PensionCollectionPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/remittance" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RemittancePage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/qdrant-vector-search" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><QdrantVectorSearchPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/falkordb-graph" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FalkorDBGraphPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cocoindex-pipeline" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CocoIndexPipelinePage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ollama-llm" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OllamaLLMPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/art-robustness" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ARTRobustnessPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ml-scoring" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MLScoringDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ai-monitoring" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AIMonitoringDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/fraud-reports" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FraudReportPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-chatbot" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceChatbotPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/apache-nifi" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApacheNifiPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dbt-integration" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DbtIntegrationPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/apache-airflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ApacheAirflowPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/websocket-service" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WebSocketServicePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/report-scheduler" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReportSchedulerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/event-driven-arch" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><EventDrivenArchPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/advanced-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdvancedNotificationsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/security-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SecurityDashboardPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/pipeline-monitoring" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PipelineMonitoringPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/backup-dr" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BackupDRPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/backup-disaster-recovery" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BackupDisasterRecoveryPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/performance-profiler" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PerformanceProfilerPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-tenancy" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiTenancyPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-tenant-isolation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiTenantIsolation /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/sla-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SlaManagementPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/sla-monitoring" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SlaMonitoringDash /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/sla-monitoring-v2" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SlaMonitoringPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/sla-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformSlaMonitor /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/capacity-planning" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CapacityPlanningPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/capacity-planner" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformCapacityPlanner /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/incident-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><IncidentManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/incident-command-center" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><IncidentCommandCenterNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/incident-playbook" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><IncidentPlaybookNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/feature-flags" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FeatureFlagsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-feature-flags" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformFeatureFlags /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/open-telemetry" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OpenTelemetryPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/advanced-bi-reporting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdvancedBiReportingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/workflow-automation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WorkflowAutomationPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/workflow-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WorkflowEnginePage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/config-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ConfigManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/service-mesh" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ServiceMeshPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-automation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceAutomationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-reporting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceReportingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-training" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceTrainingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-cert-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceCertManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/compliance-filing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ComplianceFilingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-360-view" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><Customer360ViewNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-database" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerDatabasePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-feedback" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerFeedbackNpsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-journey-mapper" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerJourneyMapperNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-onboarding" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerOnboardingPipelineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-segmentation-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerSegmentationEngineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-surveys" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerSurveysNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/customer-wallet-system" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CustomerWalletSystemNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/report-builder" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DragDropReportBuilderPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/report-builder-templates" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReportBuilderTemplatesPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/nl-analytics-query" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NLAnalyticsQueryPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/nl-financial-query" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NlFinancialQueryNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/banking-workflows" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BankingWorkflowPatternsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-onboarding-wizard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentOnboardingWizardPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-onboarding-workflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentOnboardingWorkflowPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-reconciliation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionReconciliationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-reporting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatoryReportingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-reports" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatoryReportGeneratorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-compliance" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatoryCompliancePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-sandbox" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatorySandboxPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-sandbox-tester" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatorySandboxTesterNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/regulatory-filing-automation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RegulatoryFilingAutomationNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/territory-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TerritoryManagementPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/territory-optimizer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentTerritoryOptimizer /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dynamic-pricing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DynamicPricingPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/loyalty-program" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LoyaltyProgramPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/terminal-fleet" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TerminalFleetPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/financial-reconciliation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FinancialReconciliationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/financial-reporting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FinancialReportingSuiteNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/financial-nl-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FinancialNlEngine /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-communication-hub" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentCommunicationHubPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dispute-workflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DisputeWorkflowEngineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dispute-notifications" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DisputeNotifications /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dispute-analytics-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DisputeAnalyticsDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/migration-tools" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MigrationToolsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/migration-toolkit" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformMigrationToolkit /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-csv-export" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionCsvExportNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-map-loading" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionMapLoadingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-map-viz" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionMapVizPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-fee-calc" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionFeeCalcNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-graph" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionGraphAnalyzerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-limits" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionLimitsEnginePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-velocity-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionVelocityMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-receipt-generator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionReceiptGeneratorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-enrichment-service" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionEnrichmentServiceNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-export-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionExportEngineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/transaction-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionAnalyticsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tx-dispute-resolution" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionDisputeResolutionPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tx-reversal-workflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionReversalWorkflowPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tx-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TxMonitorPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tx-velocity-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TxVelocityMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/realtime-tx-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealtimeTxMonitorPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/realtime-pnl" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealtimePnlDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/realtime-websocket-feeds" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealtimeWebSocketFeedsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/real-time-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealTimeDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dashboard-widgets" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RealtimeDashboardWidgetsPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/white-label-onboarding" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WhiteLabelOnboarding /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/white-label-branding" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WhiteLabelBranding /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/white-label-approval" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><WhiteLabelApproval /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/partner-self-service" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PartnerSelfService /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/partner-revenue-sharing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PartnerRevenueSharing /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/advanced-loading-states" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdvancedLoadingStates /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/advanced-search" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdvancedSearchFiltering /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/advanced-rate-limiter" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AdvancedRateLimiterPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-gamification-v2" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentGamificationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-benchmarking" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentBenchmarkingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-cluster-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentClusterAnalyticsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-commission-calc" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentCommissionCalcNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-device-fingerprint" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentDeviceFingerprintNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-float-forecasting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentFloatForecasting /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-geo-fencing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentGeoFencingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-inventory-mgmt" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentInventoryMgmtNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-kyc" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentKycPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-kyc-vault" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentKycDocVault /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-leaderboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPerformanceLeaderboardPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-loan-advance" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentLoanAdvanceNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-loan-facility" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentLoanFacilityPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-loan-origination-v2" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentLoanOriginationV2New /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-micro-insurance" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentMicroInsuranceNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-network-topology" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentNetworkTopology /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-performance-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPerformanceAnalyticsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-performance-leaderboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPerformanceLeaderboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-revenue-attribution" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentRevenueAttribution /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-scorecard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentScorecardPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-suspension" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentSuspensionWorkflowPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/agent-territory-heatmap" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentTerritoryHeatmap /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/loan-origination" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentLoanOrigination /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/training-academy" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentTrainingAcademyNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/training-certification" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TrainingCertification /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/fee-calculator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DynamicFeeCalculatorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-disbursement" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkDisbursementEngineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-payments" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkPaymentProcessorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-transaction-processing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkTransactionProcessingNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bulk-transaction-processor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BulkTransactionProcessorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/reversal-approval" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReversalApprovalPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/reversal-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TransactionReversalManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/bank-accounts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BankAccountManagementPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/float-reconciliation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FloatReconciliationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/float-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><FloatManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/pnl-reports" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PnlReportPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/daily-pnl-report" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DailyPnlReportPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/general-ledger" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GeneralLedgerPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/database-visualization" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DatabaseVisualization /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/middleware-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MiddlewareServiceManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/skill-creator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SkillCreatorIntegration /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-health" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformHealthPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-health-dash" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformHealthDash /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-health-scorecard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformHealthScorecard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-config" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformConfigCenter /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-cost-allocator" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformCostAllocator /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-metrics-exporter" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformMetricsExporter /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-recommendations" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformRecommendations /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/platform-ab-testing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformABTesting /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/maturity-scorecard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformMaturityScorecard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/integration-marketplace" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><IntegrationMarketplacePage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/mobile-api" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MobileApiLayerPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/automated-testing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AutomatedTestingFrameworkPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/document-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DocumentManagementPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/revenue-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RevenueAnalyticsPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/revenue-forecasting-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RevenueForecastingEngineNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/revenue-leakage-detector" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RevenueLeakageDetectorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/revenue-optimizer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PlatformRevenueOptimizer /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/intelligent-routing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><IntelligentRoutingEngine /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cross-border-remittance" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CrossBorderRemittanceHub /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/operational-command-bridge" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OperationalCommandBridge /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/operational-runbook" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OperationalRunbook /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-analytics-dash" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantAnalyticsDashNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-onboarding-portal" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantOnboardingPortalNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-acquirer" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantAcquirerGatewayNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/merchant-payout-settlement" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MerchantPayoutSettlementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/mcc-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MccManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/mfa-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MfaManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/pbac-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PBACManagementNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/session-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SessionManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/alert-preferences" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AlertNotificationPreferencesNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/network-heatmap" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NetworkQualityHeatmapNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/network-status" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NetworkStatusDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/network-diagnostic" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><NetworkDiagnosticPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/connection-quality" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ConnectionQualityPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/connection-pools" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ConnectionPoolMonitorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/distributed-tracing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DistributedTracingDashNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/canary-releases" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CanaryReleaseManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/chaos-engineering" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ChaosEngineeringConsoleNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cdn-cache" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CdnCacheManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cqrs-events" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CqrsEventStore /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/digital-twin" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DigitalTwinSimulatorNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/cbdc-gateway" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CbdcIntegrationGatewayNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/did-manager" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DecentralizedIdentityManagerNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/smart-contract-payment" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SmartContractPaymentNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/predictive-agent-churn" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><PredictiveAgentChurn /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/currency-hedging" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CurrencyHedging /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/auto-compliance-workflow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AutoComplianceWorkflowNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dynamic-qr-payment" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DynamicQrPayment /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/dynamic-fee-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DynamicFeeEnginePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/settlement-netting" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SettlementNettingEngine /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/insurance-claims" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentFloatInsuranceClaimsNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/performance-incentives" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AgentPerformanceIncentivesNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/executive-command" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ExecutiveCommandCenter /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/executive-command-center" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ExecutiveCommandCenterPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/activity-audit-log" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ActivityAuditLogPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/gateway-health-monitor" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GatewayHealthMonitor /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/auto-reconciliation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AutoReconciliationEngine /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/multi-channel-payment-orch" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><MultiChannelPaymentOrchNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ai-cash-flow" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><AiCashFlowPredictor /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/blockchain-audit" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BlockchainAuditTrailNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/voice-command-pos" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><VoiceCommandPosNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/e2e-test-framework" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><E2ETestFramework /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/db-schema-push" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DbSchemaPush /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/db-schema-migration" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><DbSchemaMigrationManager /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/graphql-federation" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GraphqlFederationPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/graphql-subscriptions" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><GraphqlSubscriptionGatewayNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/card-bin-lookup" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CardBinLookupNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/offline-pos-mode" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OfflinePosMode /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/pos-firmware-ota" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><POSFirmwareOTANew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/archival-admin" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ArchivalAdminNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/load-test-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LoadTestDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/load-test-comparison" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><LoadTestComparisonNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/security-audit" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><SecurityAuditDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/security-alerts" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><RansomwareAlertDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/carrier-costs" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CarrierCostDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/carrier-sla" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CarrierSlaDashboardNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/carrier-live-pricing" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><CarrierLivePricingPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ussd-analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UssdAnalyticsDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ussd-localization" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UssdLocalizationPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/ussd-session-replay" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><UssdSessionReplayPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/offline-queue" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><OfflineQueueDashboard /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tenant-feature-toggle" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TenantFeatureTogglePage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/reconciliation-engine" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><ReconciliationEnginePageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/billing-dashboard" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BillingDashboardPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/invoice-management" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><InvoiceManagementPageNew /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/tenant-billing-onboarding" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TenantBillingOnboardingPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/billing/portal" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><TenantBillingPortalPage /></React.Suspense></MainLayout></ProtectedRoute>} />
          <Route path="/billing/analytics" element={<ProtectedRoute><MainLayout><React.Suspense fallback={null}><BillingAnalyticsDashboardPage /></React.Suspense></MainLayout></ProtectedRoute>} />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/login" />} />
        </Routes>
      </Router>
    </TenantBrandingProvider>
  );
}

export default App;
