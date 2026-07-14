import React, { lazy, Suspense } from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import "./App.css";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import AgentHierarchy from "./pages/AgentHierarchy";
import BillPayment from "./pages/BillPayment";
import BusinessManagement from "./pages/BusinessManagement";
import CashIn from "./pages/CashIn";
import CashOut from "./pages/CashOut";
import ChartOfAccounts from "./pages/ChartOfAccounts";
import CommissionSettlement from "./pages/CommissionSettlement";
import Training from "./pages/Training";
import Performance from "./pages/Performance";
import Achievements from "./pages/Achievements";
import Communication from "./pages/Communication";
import CreateOrder from "./pages/CreateOrder";
import Dashboard from "./pages/Dashboard";
import Disputes from "./pages/Disputes";
import FloatManagement from "./pages/FloatManagement";
import Inventory from "./pages/Inventory";
import Loans from "./pages/Loans";
import Login from "./pages/Login";
import Loyalty from "./pages/Loyalty";
import NetworkPredictions from "./pages/NetworkPredictions";
import NetworkStatus from "./pages/NetworkStatus";
import NotFound from "./pages/NotFound";
import Onboarding from "./pages/Onboarding";
import OrderReceipt from "./pages/OrderReceipt";
import Orders from "./pages/Orders";
import POSDetails from "./pages/POSDetails";
import POSManagement from "./pages/POSManagement";
import POSOrder from "./pages/POSOrder";
import POSRequests from "./pages/POSRequests";
import Projections from "./pages/Projections";
import QRScanner from "./pages/QRScanner";
import Reconciliation from "./pages/Reconciliation";
import RemittanceVerification from "./pages/RemittanceVerification";
import SendRemittance from "./pages/SendRemittance";
import Services from "./pages/Services";
import SignUp from "./pages/SignUp";
import StoreMap from "./pages/StoreMap";
import Transactions from "./pages/Transactions";
import Transfer from "./pages/Transfer";

// New performance & gamification pages
import AgentPerformanceLeaderboardPage from "./pages/AgentPerformanceLeaderboardPage";
import AgentPerformanceScorecardPage from "./pages/AgentPerformanceScorecardPage";
import AgentPerformanceAnalytics from "./pages/AgentPerformanceAnalytics";
import AgentPerformanceIncentives from "./pages/AgentPerformanceIncentives";
import AgentPerformanceLeaderboard from "./pages/AgentPerformanceLeaderboard";
import AgentPerformanceScoring from "./pages/AgentPerformanceScoring";
// New reporting pages
import ReportSchedulerPage from "./pages/ReportSchedulerPage";
import ReportBuilderTemplatesPage from "./pages/ReportBuilderTemplatesPage";
import ReportComparison from "./pages/ReportComparison";
import ReportTemplateDesigner from "./pages/ReportTemplateDesigner";
import WeeklyReports from "./pages/WeeklyReports";

// New compliance pages
import RegulatoryCompliancePage from "./pages/RegulatoryCompliancePage";
import RegulatoryReportingPage from "./pages/RegulatoryReportingPage";
import RegulatoryFilingAutomation from "./pages/RegulatoryFilingAutomation";
import RegulatoryReportGenerator from "./pages/RegulatoryReportGenerator";

// New map & media pages
import TransactionMapVizPage from "./pages/TransactionMapVizPage";
import TransactionMapLoading from "./pages/TransactionMapLoading";
import VideoTutorials from "./pages/VideoTutorials";

// New payment channel pages
import NFCPayment from "./pages/NFCPayment";
import InsurancePayment from "./pages/InsurancePayment";
import NanoLoan from "./pages/NanoLoan";

// New savings & cards pages
import VirtualCards from "./pages/VirtualCards";
import SavingsGoals from "./pages/SavingsGoals";
import RateCalculator from "./pages/RateCalculator";

// New float & insurance pages
import FloatForecasting from "./pages/FloatForecasting";
import FloatInsuranceClaims from "./pages/FloatInsuranceClaims";
import MicroInsurance from "./pages/MicroInsurance";


import AgentDeviceFingerprint from "./pages/AgentDeviceFingerprint";

// Orphaned pages — wired into router
import AgentPerformance from "./pages/AgentPerformance";
import BeneficiaryManagement from "./pages/BeneficiaryManagement";
import Businesses from "./pages/Businesses";
import Customer360 from "./pages/Customer360";
import OfflineTransactionExample from "./pages/OfflineTransactionExample";
import Profile from "./pages/Profile";
import Receipts from "./pages/Receipts";
import ReportScheduler from "./pages/ReportScheduler";
import TerritoryHeatmap from "./pages/TerritoryHeatmap";
import TerritoryOptimizer from "./pages/TerritoryOptimizer";

// New customer pages
import CustomerFeedback from "./pages/CustomerFeedback";

// New security & AI pages
import AgentChurnPrediction from "./pages/AgentChurnPrediction";

// Migrated from NGApp
import AgentCommissionCalc from "./pages/AgentCommissionCalc";
import AgentLoanAdvance from "./pages/AgentLoanAdvance";
import AgentMicroInsurancePage from "./pages/AgentMicroInsurance";
import AgentInventoryMgmt from "./pages/AgentInventoryMgmt";
import AgentStoreSetup from "./pages/AgentStoreSetup";
import AgentGamification from "./pages/AgentGamification";
import AgentGamificationPage from "./pages/AgentGamificationPage";
import AgentScorecardPage from "./pages/AgentScorecardPage";
import PredictiveAgentChurn from "./pages/PredictiveAgentChurn";
import RealtimeTxMonitorPage from "./pages/RealtimeTxMonitorPage";
import RealtimePnlDashboard from "./pages/RealtimePnlDashboard";
import TransactionVelocityMonitor from "./pages/TransactionVelocityMonitor";
import FraudRealtimeVizPage from "./pages/FraudRealtimeVizPage";
import DailyPnlReportPage from "./pages/DailyPnlReportPage";
import DragDropReportBuilderPage from "./pages/DragDropReportBuilderPage";
import NlFinancialQuery from "./pages/NlFinancialQuery";
import MultiCurrencyExchange from "./pages/MultiCurrencyExchange";
import CrossBorderRemittanceHub from "./pages/CrossBorderRemittanceHub";
import PaymentGatewayRouter from "./pages/PaymentGatewayRouter";
import PaymentLinkGenerator from "./pages/PaymentLinkGenerator";
import DynamicQrPayment from "./pages/DynamicQrPayment";
import WearablePayments from "./pages/WearablePayments";
import NfcTapToPay from "./pages/NfcTapToPay";
import StablecoinRails from "./pages/StablecoinRails";
import CarbonCreditMarketplace from "./pages/CarbonCreditMarketplace";
import UssdGateway from "./pages/UssdGateway";
import UssdAnalyticsDashboard from "./pages/UssdAnalyticsDashboard";
import UssdSessionReplayPage from "./pages/UssdSessionReplayPage";
import UssdLocalizationPage from "./pages/UssdLocalizationPage";
import WhatsAppChannelPage from "./pages/WhatsAppChannelPage";
import SocialCommerceGatewayPage from "./pages/SocialCommerceGateway";
import EmbeddedFinanceAnaas from "./pages/EmbeddedFinanceAnaas";
import OpenBankingApi from "./pages/OpenBankingApi";
import EducationPayments from "./pages/EducationPayments";
import AgritechPayments from "./pages/AgritechPayments";
import PensionMicro from "./pages/PensionMicro";
import HealthInsuranceMicro from "./pages/HealthInsuranceMicro";
import BnplEngine from "./pages/BnplEngine";
import KycWorkflow from "./pages/KycWorkflow";
import BiometricAuthPage from "./pages/BiometricAuthPage";

// --- Lazy-loaded new pages ---
// Agent management & hierarchy
const AgentBenchmarking = lazy(() => import("./pages/AgentBenchmarking"));
const AgentClusterAnalytics = lazy(() => import("./pages/AgentClusterAnalytics"));
const AgentCommunicationHubPage = lazy(() => import("./pages/AgentCommunicationHubPage"));
const AgentFloatForecasting = lazy(() => import("./pages/AgentFloatForecasting"));
const AgentFloatInsuranceClaims = lazy(() => import("./pages/AgentFloatInsuranceClaims"));
const AgentGeoFencingPage = lazy(() => import("./pages/AgentGeoFencingPage"));
const AgentHierarchyPage = lazy(() => import("./pages/AgentHierarchyPage"));
const AgentHierarchyTerritory = lazy(() => import("./pages/AgentHierarchyTerritory"));
const AgentKycDocVault = lazy(() => import("./pages/AgentKycDocVault"));
const AgentKycPage = lazy(() => import("./pages/AgentKycPage"));
const AgentLoanFacilityPage = lazy(() => import("./pages/AgentLoanFacilityPage"));
const AgentLoanOrigination = lazy(() => import("./pages/AgentLoanOrigination"));
const AgentLoanOriginationV2 = lazy(() => import("./pages/AgentLoanOriginationV2"));
const AgentLogin = lazy(() => import("./pages/AgentLogin"));
const AgentManagementDashboard = lazy(() => import("./pages/AgentManagementDashboard"));
const AgentNetworkTopology = lazy(() => import("./pages/AgentNetworkTopology"));
const AgentOnboarding = lazy(() => import("./pages/AgentOnboarding"));
const AgentOnboardingWizardPage = lazy(() => import("./pages/AgentOnboardingWizardPage"));
const AgentOnboardingWorkflowPage = lazy(() => import("./pages/AgentOnboardingWorkflowPage"));
const AgentPortal = lazy(() => import("./pages/AgentPortal"));
const AgentRevenueAttribution = lazy(() => import("./pages/AgentRevenueAttribution"));
const AgentSuspensionWorkflowPage = lazy(() => import("./pages/AgentSuspensionWorkflowPage"));
const AgentTerritoryHeatmap = lazy(() => import("./pages/AgentTerritoryHeatmap"));
const AgentTerritoryOptimizer = lazy(() => import("./pages/AgentTerritoryOptimizer"));
const AgentTrainingAcademy = lazy(() => import("./pages/AgentTrainingAcademy"));
const AgentTrainingPage = lazy(() => import("./pages/AgentTrainingPage"));
const AgentTrainingPortal = lazy(() => import("./pages/AgentTrainingPortal"));

// Vending & analytics
const AirtimeVendingPage = lazy(() => import("./pages/AirtimeVendingPage"));
const AnalyticsDashboard = lazy(() => import("./pages/AnalyticsDashboard"));
const AdvancedBiReportingPage = lazy(() => import("./pages/AdvancedBiReportingPage"));
const AiCashFlowPredictor = lazy(() => import("./pages/AiCashFlowPredictor"));

// Payments & billing
const BillPaymentsPage = lazy(() => import("./pages/BillPaymentsPage"));
const BiometricAuthGateway = lazy(() => import("./pages/BiometricAuthGateway"));
const CardRequestPage = lazy(() => import("./pages/CardRequestPage"));

// Commission
const CommissionCalculatorPage = lazy(() => import("./pages/CommissionCalculatorPage"));
const CommissionClawbackPage = lazy(() => import("./pages/CommissionClawbackPage"));
const CommissionConfig = lazy(() => import("./pages/CommissionConfig"));
const CommissionEnginePage = lazy(() => import("./pages/CommissionEnginePage"));
const CommissionPayouts = lazy(() => import("./pages/CommissionPayouts"));

// Compliance
const ComplianceAutomationPage = lazy(() => import("./pages/ComplianceAutomationPage"));
const ComplianceCertManager = lazy(() => import("./pages/ComplianceCertManager"));
const ComplianceReporting = lazy(() => import("./pages/ComplianceReporting"));
const ComplianceTrainingPage = lazy(() => import("./pages/ComplianceTrainingPage"));
const ComplianceTrainingTracker = lazy(() => import("./pages/ComplianceTrainingTracker"));

// Network & connectivity
const ConnectionQualityPage = lazy(() => import("./pages/ConnectionQualityPage"));
const NetworkQualityHeatmap = lazy(() => import("./pages/NetworkQualityHeatmap"));

// Finance
const CurrencyHedging = lazy(() => import("./pages/CurrencyHedging"));
const FinancialReportingSuite = lazy(() => import("./pages/FinancialReportingSuite"));

// Float
const FloatManagementPage = lazy(() => import("./pages/FloatManagementPage"));
const FloatReconciliationPage = lazy(() => import("./pages/FloatReconciliationPage"));

// Insurance & savings
const InsuranceProductsPage = lazy(() => import("./pages/InsuranceProductsPage"));
const SavingsProductsPage = lazy(() => import("./pages/SavingsProductsPage"));

// KYC
const KycDocumentManagementPage = lazy(() => import("./pages/KycDocumentManagementPage"));
const KycVerificationWorkflow = lazy(() => import("./pages/KycVerificationWorkflow"));

// Loans
const LoanDisbursementPage = lazy(() => import("./pages/LoanDisbursementPage"));

// ML & scoring
const MLScoringDashboard = lazy(() => import("./pages/MLScoringDashboard"));

// Mobile money & remittance
const MobileMoneyPage = lazy(() => import("./pages/MobileMoneyPage"));
const RemittancePage = lazy(() => import("./pages/RemittancePage"));

// Offline
const OfflinePosMode = lazy(() => import("./pages/OfflinePosMode"));
const OfflineQueueDashboard = lazy(() => import("./pages/OfflineQueueDashboard"));
const OfflineSyncPage = lazy(() => import("./pages/OfflineSyncPage"));

// Payment outcomes
const PaymentCancel = lazy(() => import("./pages/PaymentCancel"));
const PaymentSuccess = lazy(() => import("./pages/PaymentSuccess"));
const Payments = lazy(() => import("./pages/Payments"));

// Pension & tax
const PensionCollectionPage = lazy(() => import("./pages/PensionCollectionPage"));
const TaxCollectionPage = lazy(() => import("./pages/TaxCollectionPage"));

// PnL & revenue
const PnlReportPage = lazy(() => import("./pages/PnlReportPage"));
const RevenueLeakageDetector = lazy(() => import("./pages/RevenueLeakageDetector"));
const RevenueForecastingEngine = lazy(() => import("./pages/RevenueForecastingEngine"));

// POS
const POSFirmwareOTA = lazy(() => import("./pages/POSFirmwareOTA"));
const POSShell = lazy(() => import("./pages/POSShell"));

// Reports
const ScheduledReports = lazy(() => import("./pages/ScheduledReports"));

// SIM & terminals
const SimOrchestratorDashboard = lazy(() => import("./pages/SimOrchestratorDashboard"));
const TerminalFleetPage = lazy(() => import("./pages/TerminalFleetPage"));

// Territory management
const TerritoryManagementPage = lazy(() => import("./pages/TerritoryManagementPage"));

// Transaction tools
const TransactionAnalytics = lazy(() => import("./pages/TransactionAnalytics"));
const TransactionCsvExport = lazy(() => import("./pages/TransactionCsvExport"));
const TransactionFeeCalc = lazy(() => import("./pages/TransactionFeeCalc"));
const TransactionGraphAnalyzer = lazy(() => import("./pages/TransactionGraphAnalyzer"));

const LazyFallback = (
  <div className="flex items-center justify-center h-screen">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
  </div>
);

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="businesses" element={<BusinessManagement />} />
            <Route path="chart-of-accounts" element={<ChartOfAccounts />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="transfer" element={<Transfer />} />
            <Route
              path="remittance-verification"
              element={<RemittanceVerification />}
            />
            <Route path="send-remittance" element={<SendRemittance />} />
            <Route path="cash-in" element={<CashIn />} />
            <Route path="cash-out" element={<CashOut />} />
            <Route path="loans" element={<Loans />} />
            <Route path="loyalty" element={<Loyalty />} />
            <Route path="bills" element={<BillPayment />} />
            <Route path="scanner" element={<QRScanner />} />
            {/* <Route path="reconciliation" element={<Reconciliation />} /> */}
            <Route path="disputes" element={<Disputes />} />
            <Route path="network-status" element={<NetworkStatus />} />
            <Route
              path="network-predictions"
              element={<NetworkPredictions />}
            />
            <Route path="projections" element={<Projections />} />
            <Route path="messages" element={<Communication />} />
            <Route path="pos" element={<POSManagement />} />
            <Route path="pos/requests" element={<POSRequests />} />
            <Route path="pos/order" element={<POSOrder />} />
            <Route path="pos/:terminalId" element={<POSDetails />} />
            <Route path="orders" element={<Orders />} />
            <Route path="orders/create" element={<CreateOrder />} />
            <Route path="orders/:orderId/receipt" element={<OrderReceipt />} />
            <Route path="hierarchy" element={<AgentHierarchy />} />
            <Route path="commission" element={<CommissionSettlement />} />
            {/* <Route path="services" element={<Services />} /> */}
            <Route path="float" element={<FloatManagement />} />
            <Route path="store-map" element={<StoreMap />} />
            <Route path="training" element={<Training />} />
            <Route path="performance" element={<Performance />} />
            <Route path="achievements" element={<Achievements />} />

            {/* Performance & Gamification */}
            <Route path="performance/leaderboard" element={<AgentPerformanceLeaderboardPage />} />
            <Route path="performance/scorecard" element={<AgentPerformanceScorecardPage />} />
            <Route path="performance/analytics" element={<AgentPerformanceAnalytics />} />
            <Route path="performance/incentives" element={<AgentPerformanceIncentives />} />
            <Route path="performance/ranking" element={<AgentPerformanceLeaderboard />} />
            <Route path="performance/scoring" element={<AgentPerformanceScoring />} />
            {/* Reports */}
            <Route path="reports/scheduler" element={<ReportSchedulerPage />} />
            <Route path="reports/templates" element={<ReportBuilderTemplatesPage />} />
            <Route path="reports/comparison" element={<ReportComparison />} />
            <Route path="reports/designer" element={<ReportTemplateDesigner />} />
            <Route path="reports/weekly" element={<WeeklyReports />} />

            {/* Regulatory Compliance */}
            <Route path="compliance" element={<RegulatoryCompliancePage />} />
            <Route path="compliance/reporting" element={<RegulatoryReportingPage />} />
            <Route path="compliance/filing" element={<RegulatoryFilingAutomation />} />
            <Route path="compliance/generator" element={<RegulatoryReportGenerator />} />

            {/* Map & Media */}
            <Route path="transaction-map" element={<TransactionMapVizPage />} />
            <Route path="transaction-map/loading" element={<TransactionMapLoading />} />
            <Route path="tutorials" element={<VideoTutorials />} />

            {/* New Payment Channels */}
            <Route path="nfc-payment" element={<NFCPayment />} />
            <Route path="insurance" element={<InsurancePayment />} />
            <Route path="nano-loan" element={<NanoLoan />} />

            {/* Savings & Cards */}
            <Route path="virtual-cards" element={<VirtualCards />} />
            <Route path="savings" element={<SavingsGoals />} />
            <Route path="calculator" element={<RateCalculator />} />

            {/* Float & Insurance */}
            <Route path="float-forecasting" element={<FloatForecasting />} />
            <Route path="float-insurance" element={<FloatInsuranceClaims />} />
            <Route path="micro-insurance" element={<MicroInsurance />} />

            <Route path="my-devices" element={<AgentDeviceFingerprint />} />

            {/* Customers */}
            <Route path="customer-feedback" element={<CustomerFeedback />} />

            {/* Security & AI */}
            <Route path="churn-prediction" element={<AgentChurnPrediction />} />

            {/* Agent Operations (NGApp) */}
            <Route path="agent-commission" element={<AgentCommissionCalc />} />
            <Route path="agent-loan-advance" element={<AgentLoanAdvance />} />
            <Route path="agent-micro-insurance-new" element={<AgentMicroInsurancePage />} />
            <Route path="agent-inventory-management" element={<AgentInventoryMgmt />} />
            <Route path="agent-store-setup" element={<AgentStoreSetup />} />
            <Route path="agent-gamification" element={<AgentGamification />} />
            <Route path="agent-gamification-overview" element={<AgentGamificationPage />} />
            <Route path="agent-scorecard" element={<AgentScorecardPage />} />
            <Route path="predictive-churn" element={<PredictiveAgentChurn />} />
            {/* Analytics (NGApp) */}
            <Route path="realtime-tx-monitor" element={<RealtimeTxMonitorPage />} />
            <Route path="realtime-pnl" element={<RealtimePnlDashboard />} />
            <Route path="transaction-velocity" element={<TransactionVelocityMonitor />} />
            <Route path="fraud-realtime-viz" element={<FraudRealtimeVizPage />} />
            <Route path="daily-pnl-report" element={<DailyPnlReportPage />} />
            <Route path="drag-drop-report-builder" element={<DragDropReportBuilderPage />} />
            <Route path="natural-language-query" element={<NlFinancialQuery />} />
            {/* Payments (NGApp) */}
            <Route path="multi-currency-exchange" element={<MultiCurrencyExchange />} />
            <Route path="cross-border-remittance" element={<CrossBorderRemittanceHub />} />
            <Route path="payment-gateway-router" element={<PaymentGatewayRouter />} />
            <Route path="payment-link-generator" element={<PaymentLinkGenerator />} />
            <Route path="dynamic-qr-payment" element={<DynamicQrPayment />} />
            <Route path="wearable-payments" element={<WearablePayments />} />
            <Route path="nfc-tap-to-pay" element={<NfcTapToPay />} />
            <Route path="stablecoin-rails" element={<StablecoinRails />} />
            <Route path="carbon-credits" element={<CarbonCreditMarketplace />} />
            {/* Channels (NGApp) */}
            <Route path="ussd-gateway" element={<UssdGateway />} />
            <Route path="ussd-analytics" element={<UssdAnalyticsDashboard />} />
            <Route path="ussd-session-replay" element={<UssdSessionReplayPage />} />
            <Route path="ussd-localization" element={<UssdLocalizationPage />} />
            <Route path="whatsapp-channel" element={<WhatsAppChannelPage />} />
            <Route path="social-commerce" element={<SocialCommerceGatewayPage />} />
            <Route path="embedded-finance" element={<EmbeddedFinanceAnaas />} />
            <Route path="open-banking" element={<OpenBankingApi />} />
            <Route path="education-payments" element={<EducationPayments />} />
            <Route path="agritech-payments" element={<AgritechPayments />} />
            <Route path="pension" element={<PensionMicro />} />
            <Route path="health-insurance-micro" element={<HealthInsuranceMicro />} />
            <Route path="bnpl" element={<BnplEngine />} />
            {/* Compliance (NGApp) */}
            <Route path="kyc-workflow" element={<KycWorkflow />} />
            <Route path="biometric-auth" element={<BiometricAuthPage />} />

            {/* Previously orphaned pages */}
            <Route path="profile" element={<Profile />} />
            <Route path="receipts" element={<Receipts />} />
            <Route path="beneficiaries" element={<BeneficiaryManagement />} />
            <Route path="customer-360" element={<Customer360 />} />
            <Route path="agent-performance-overview" element={<AgentPerformance />} />
            <Route path="business-directory" element={<Businesses />} />
            <Route path="territory-heatmap" element={<TerritoryHeatmap />} />
            <Route path="territory-optimizer" element={<TerritoryOptimizer />} />
            <Route path="reports/schedule" element={<ReportScheduler />} />
            <Route path="offline-transaction-demo" element={<OfflineTransactionExample />} />

            {/* New lazy-loaded pages */}
            <Route path="agent-benchmarking" element={<Suspense fallback={LazyFallback}><AgentBenchmarking /></Suspense>} />
            <Route path="agent-cluster-analytics" element={<Suspense fallback={LazyFallback}><AgentClusterAnalytics /></Suspense>} />
            <Route path="agent-communication-hub" element={<Suspense fallback={LazyFallback}><AgentCommunicationHubPage /></Suspense>} />
            <Route path="agent-float-forecasting" element={<Suspense fallback={LazyFallback}><AgentFloatForecasting /></Suspense>} />
            <Route path="agent-float-insurance-claims" element={<Suspense fallback={LazyFallback}><AgentFloatInsuranceClaims /></Suspense>} />
            <Route path="agent-geo-fencing" element={<Suspense fallback={LazyFallback}><AgentGeoFencingPage /></Suspense>} />
            <Route path="agent-hierarchy-page" element={<Suspense fallback={LazyFallback}><AgentHierarchyPage /></Suspense>} />
            <Route path="agent-hierarchy-territory" element={<Suspense fallback={LazyFallback}><AgentHierarchyTerritory /></Suspense>} />
            <Route path="agent-kyc-doc-vault" element={<Suspense fallback={LazyFallback}><AgentKycDocVault /></Suspense>} />
            <Route path="agent-kyc" element={<Suspense fallback={LazyFallback}><AgentKycPage /></Suspense>} />
            <Route path="agent-loan-facility" element={<Suspense fallback={LazyFallback}><AgentLoanFacilityPage /></Suspense>} />
            <Route path="agent-loan-origination" element={<Suspense fallback={LazyFallback}><AgentLoanOrigination /></Suspense>} />
            <Route path="agent-loan-origination-v2" element={<Suspense fallback={LazyFallback}><AgentLoanOriginationV2 /></Suspense>} />
            <Route path="agent-login" element={<Suspense fallback={LazyFallback}><AgentLogin /></Suspense>} />
            <Route path="agent-management" element={<Suspense fallback={LazyFallback}><AgentManagementDashboard /></Suspense>} />
            <Route path="agent-network-topology" element={<Suspense fallback={LazyFallback}><AgentNetworkTopology /></Suspense>} />
            <Route path="agent-onboarding" element={<Suspense fallback={LazyFallback}><AgentOnboarding /></Suspense>} />
            <Route path="agent-onboarding-wizard" element={<Suspense fallback={LazyFallback}><AgentOnboardingWizardPage /></Suspense>} />
            <Route path="agent-onboarding-workflow" element={<Suspense fallback={LazyFallback}><AgentOnboardingWorkflowPage /></Suspense>} />
            <Route path="agent-portal" element={<Suspense fallback={LazyFallback}><AgentPortal /></Suspense>} />
            <Route path="agent-revenue-attribution" element={<Suspense fallback={LazyFallback}><AgentRevenueAttribution /></Suspense>} />
            <Route path="agent-suspension-workflow" element={<Suspense fallback={LazyFallback}><AgentSuspensionWorkflowPage /></Suspense>} />
            <Route path="agent-territory-heatmap" element={<Suspense fallback={LazyFallback}><AgentTerritoryHeatmap /></Suspense>} />
            <Route path="agent-territory-optimizer" element={<Suspense fallback={LazyFallback}><AgentTerritoryOptimizer /></Suspense>} />
            <Route path="agent-training-academy" element={<Suspense fallback={LazyFallback}><AgentTrainingAcademy /></Suspense>} />
            <Route path="agent-training" element={<Suspense fallback={LazyFallback}><AgentTrainingPage /></Suspense>} />
            <Route path="agent-training-portal" element={<Suspense fallback={LazyFallback}><AgentTrainingPortal /></Suspense>} />
            <Route path="airtime-vending" element={<Suspense fallback={LazyFallback}><AirtimeVendingPage /></Suspense>} />
            <Route path="analytics" element={<Suspense fallback={LazyFallback}><AnalyticsDashboard /></Suspense>} />
            <Route path="advanced-bi-reporting" element={<Suspense fallback={LazyFallback}><AdvancedBiReportingPage /></Suspense>} />
            <Route path="ai-cash-flow-predictor" element={<Suspense fallback={LazyFallback}><AiCashFlowPredictor /></Suspense>} />
            <Route path="bill-payments" element={<Suspense fallback={LazyFallback}><BillPaymentsPage /></Suspense>} />
            <Route path="biometric-auth-gateway" element={<Suspense fallback={LazyFallback}><BiometricAuthGateway /></Suspense>} />
            <Route path="card-request" element={<Suspense fallback={LazyFallback}><CardRequestPage /></Suspense>} />
            <Route path="commission-calculator" element={<Suspense fallback={LazyFallback}><CommissionCalculatorPage /></Suspense>} />
            <Route path="commission-clawback" element={<Suspense fallback={LazyFallback}><CommissionClawbackPage /></Suspense>} />
            <Route path="commission-config" element={<Suspense fallback={LazyFallback}><CommissionConfig /></Suspense>} />
            <Route path="commission-engine" element={<Suspense fallback={LazyFallback}><CommissionEnginePage /></Suspense>} />
            <Route path="commission-payouts" element={<Suspense fallback={LazyFallback}><CommissionPayouts /></Suspense>} />
            <Route path="compliance-automation" element={<Suspense fallback={LazyFallback}><ComplianceAutomationPage /></Suspense>} />
            <Route path="compliance-cert-manager" element={<Suspense fallback={LazyFallback}><ComplianceCertManager /></Suspense>} />
            <Route path="compliance-reporting" element={<Suspense fallback={LazyFallback}><ComplianceReporting /></Suspense>} />
            <Route path="compliance-training" element={<Suspense fallback={LazyFallback}><ComplianceTrainingPage /></Suspense>} />
            <Route path="compliance-training-tracker" element={<Suspense fallback={LazyFallback}><ComplianceTrainingTracker /></Suspense>} />
            <Route path="connection-quality" element={<Suspense fallback={LazyFallback}><ConnectionQualityPage /></Suspense>} />
            <Route path="currency-hedging" element={<Suspense fallback={LazyFallback}><CurrencyHedging /></Suspense>} />
            <Route path="financial-reporting-suite" element={<Suspense fallback={LazyFallback}><FinancialReportingSuite /></Suspense>} />
            <Route path="float-management" element={<Suspense fallback={LazyFallback}><FloatManagementPage /></Suspense>} />
            <Route path="float-reconciliation" element={<Suspense fallback={LazyFallback}><FloatReconciliationPage /></Suspense>} />
            <Route path="insurance-products" element={<Suspense fallback={LazyFallback}><InsuranceProductsPage /></Suspense>} />
            <Route path="kyc-document-management" element={<Suspense fallback={LazyFallback}><KycDocumentManagementPage /></Suspense>} />
            <Route path="kyc-verification-workflow" element={<Suspense fallback={LazyFallback}><KycVerificationWorkflow /></Suspense>} />
            <Route path="loan-disbursement" element={<Suspense fallback={LazyFallback}><LoanDisbursementPage /></Suspense>} />
            <Route path="ml-scoring" element={<Suspense fallback={LazyFallback}><MLScoringDashboard /></Suspense>} />
            <Route path="mobile-money" element={<Suspense fallback={LazyFallback}><MobileMoneyPage /></Suspense>} />
            <Route path="network-quality-heatmap" element={<Suspense fallback={LazyFallback}><NetworkQualityHeatmap /></Suspense>} />
            <Route path="offline-pos" element={<Suspense fallback={LazyFallback}><OfflinePosMode /></Suspense>} />
            <Route path="offline-queue" element={<Suspense fallback={LazyFallback}><OfflineQueueDashboard /></Suspense>} />
            <Route path="offline-sync" element={<Suspense fallback={LazyFallback}><OfflineSyncPage /></Suspense>} />
            <Route path="payment-cancel" element={<Suspense fallback={LazyFallback}><PaymentCancel /></Suspense>} />
            <Route path="payment-success" element={<Suspense fallback={LazyFallback}><PaymentSuccess /></Suspense>} />
            <Route path="payments" element={<Suspense fallback={LazyFallback}><Payments /></Suspense>} />
            <Route path="pension-collection" element={<Suspense fallback={LazyFallback}><PensionCollectionPage /></Suspense>} />
            <Route path="pnl-report" element={<Suspense fallback={LazyFallback}><PnlReportPage /></Suspense>} />
            <Route path="pos-firmware-ota" element={<Suspense fallback={LazyFallback}><POSFirmwareOTA /></Suspense>} />
            <Route path="pos-shell" element={<Suspense fallback={LazyFallback}><POSShell /></Suspense>} />
            <Route path="remittance" element={<Suspense fallback={LazyFallback}><RemittancePage /></Suspense>} />
            <Route path="revenue-leakage-detector" element={<Suspense fallback={LazyFallback}><RevenueLeakageDetector /></Suspense>} />
            <Route path="revenue-forecasting" element={<Suspense fallback={LazyFallback}><RevenueForecastingEngine /></Suspense>} />
            <Route path="savings-products" element={<Suspense fallback={LazyFallback}><SavingsProductsPage /></Suspense>} />
            <Route path="scheduled-reports" element={<Suspense fallback={LazyFallback}><ScheduledReports /></Suspense>} />
            <Route path="sim-orchestrator" element={<Suspense fallback={LazyFallback}><SimOrchestratorDashboard /></Suspense>} />
            <Route path="tax-collection" element={<Suspense fallback={LazyFallback}><TaxCollectionPage /></Suspense>} />
            <Route path="territory-management" element={<Suspense fallback={LazyFallback}><TerritoryManagementPage /></Suspense>} />
            <Route path="terminal-fleet" element={<Suspense fallback={LazyFallback}><TerminalFleetPage /></Suspense>} />
            <Route path="transaction-analytics" element={<Suspense fallback={LazyFallback}><TransactionAnalytics /></Suspense>} />
            <Route path="transaction-csv-export" element={<Suspense fallback={LazyFallback}><TransactionCsvExport /></Suspense>} />
            <Route path="transaction-fee-calc" element={<Suspense fallback={LazyFallback}><TransactionFeeCalc /></Suspense>} />
            <Route path="transaction-graph-analyzer" element={<Suspense fallback={LazyFallback}><TransactionGraphAnalyzer /></Suspense>} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
