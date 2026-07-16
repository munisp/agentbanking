import { lazy, Suspense, useEffect, useState } from "react";
import {
    Route,
    BrowserRouter as Router,
    Routes,
    useLocation,
    useNavigate,
} from "react-router-dom";
import "./App.css";
import { KYCVerificationModal } from "./components/KYCVerificationModal";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./hooks/useAuth";
import Accounts from "./pages/Accounts";
import Communication from "./pages/Communication";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Onboarding from "./pages/Onboarding";
import Profile from "./pages/Profile";
import SignUp from "./pages/SignUp";
import Storefront from "./pages/Storefront";
import StoreMap from "./pages/StoreMap";
import Transactions from "./pages/Transactions";
import { STORAGE } from "./utils/api";

// New feature pages (eager — already existed before this batch)
import CustomerWallet from "./pages/CustomerWallet";
import CustomerFeedbackNps from "./pages/CustomerFeedbackNps";
import CustomerSurveys from "./pages/CustomerSurveys";
import CustomerDisputePortal from "./pages/CustomerDisputePortal";
import LoyaltyProgramPage from "./pages/LoyaltyProgramPage";
import ReferralProgramPage from "./pages/ReferralProgramPage";
import SavingsProductsPage from "./pages/SavingsProductsPage";

// New Onboarding Flow Components
import AccountTypeScreen from "./pages/onboarding/AccountTypeScreen";
import AddressVerificationScreen from "./pages/onboarding/AddressVerificationScreen";
import BvnVerificationScreen from "./pages/onboarding/BvnVerificationScreen";
import OnboardingCompletionScreen from "./pages/onboarding/OnboardingCompletionScreen";
import OnboardingStartScreen from "./pages/onboarding/OnboardingStartScreen";

// ─── Lazy-loaded new feature pages ────────────────────────────────────────────
const AccountOpeningPage = lazy(() => import("./pages/AccountOpeningPage"));
const CustomerOnboardingPipeline = lazy(() => import("./pages/CustomerOnboardingPipeline"));
const OnboardingWizard = lazy(() => import("./pages/OnboardingWizard"));
const CustomerWalletSystem = lazy(() => import("./pages/CustomerWalletSystem"));
const DynamicQrPayment = lazy(() => import("./pages/DynamicQrPayment"));
const MobileMoneyPage = lazy(() => import("./pages/MobileMoneyPage"));
const Payments = lazy(() => import("./pages/Payments"));
const PaymentCancel = lazy(() => import("./pages/PaymentCancel"));
const PaymentSuccess = lazy(() => import("./pages/PaymentSuccess"));
const PaymentLinkGenerator = lazy(() => import("./pages/PaymentLinkGenerator"));
const BillPaymentsPage = lazy(() => import("./pages/BillPaymentsPage"));
const AirtimeVendingPage = lazy(() => import("./pages/AirtimeVendingPage"));
const CardRequestPage = lazy(() => import("./pages/CardRequestPage"));
const RemittancePage = lazy(() => import("./pages/RemittancePage"));
const CrossBorderRemittanceHub = lazy(() => import("./pages/CrossBorderRemittanceHub"));
const CurrencyHedging = lazy(() => import("./pages/CurrencyHedging"));
const MultiCurrencyExchange = lazy(() => import("./pages/MultiCurrencyExchange"));
const TaxCollectionPage = lazy(() => import("./pages/TaxCollectionPage"));
const PensionCollectionPage = lazy(() => import("./pages/PensionCollectionPage"));
const InsuranceProductsPage = lazy(() => import("./pages/InsuranceProductsPage"));
const SavingsProductsPageLazy = lazy(() => import("./pages/SavingsProductsPage"));
const LoanDisbursementPage = lazy(() => import("./pages/LoanDisbursementPage"));
const Customer360Page = lazy(() => import("./pages/Customer360Page"));
const Customer360View = lazy(() => import("./pages/Customer360View"));
const CustomerJourneyAnalyticsPage = lazy(() => import("./pages/CustomerJourneyAnalyticsPage"));
const CustomerJourneyMapper = lazy(() => import("./pages/CustomerJourneyMapper"));
const CustomerSegmentationEngine = lazy(() => import("./pages/CustomerSegmentationEngine"));
const CustomerDatabasePage = lazy(() => import("./pages/CustomerDatabasePage"));
const DisputeResolutionPage = lazy(() => import("./pages/DisputeResolutionPage"));
const CustomerDisputePortalLazy = lazy(() => import("./pages/CustomerDisputePortal"));
const NotificationPreferences = lazy(() => import("./pages/NotificationPreferences"));
const NotificationInbox = lazy(() => import("./pages/NotificationInbox"));
const AlertNotificationPreferences = lazy(() => import("./pages/AlertNotificationPreferences"));
const UserNotifSettings = lazy(() => import("./pages/UserNotifSettings"));
const UserQuietHours = lazy(() => import("./pages/UserQuietHours"));
const LoyaltySystem = lazy(() => import("./pages/LoyaltySystem"));
const LoyaltyProgramPageLazy = lazy(() => import("./pages/LoyaltyProgramPage"));
const ReferralProgram = lazy(() => import("./pages/ReferralProgram"));
const ReferralProgramPageLazy = lazy(() => import("./pages/ReferralProgramPage"));
const WeeklyReports = lazy(() => import("./pages/WeeklyReports"));
const ScheduledReports = lazy(() => import("./pages/ScheduledReports"));
const ReportSchedulerPage = lazy(() => import("./pages/ReportSchedulerPage"));
const TransactionCsvExport = lazy(() => import("./pages/TransactionCsvExport"));
const TransactionAnalytics = lazy(() => import("./pages/TransactionAnalytics"));
const KycWorkflow = lazy(() => import("./pages/KycWorkflow"));
const KycVerificationWorkflow = lazy(() => import("./pages/KycVerificationWorkflow"));
const BiometricAuthPage = lazy(() => import("./pages/BiometricAuthPage"));
const PrivacyPolicy = lazy(() => import("./pages/PrivacyPolicy"));
const GdprDashboard = lazy(() => import("./pages/GdprDashboard"));
const HelpDeskPage = lazy(() => import("./pages/HelpDeskPage"));
const VideoTutorials = lazy(() => import("./pages/VideoTutorials"));
const UserGuide = lazy(() => import("./pages/UserGuide"));

/** Inner component — lives inside Router so it can use useLocation / useNavigate */
function AppContent() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showKYCModal, setShowKYCModal] = useState(false);
  const [kycUrl, setKycUrl] = useState(null);
  // Persisted in sessionStorage so Login.jsx and App.jsx share the same flag.
  // Reset is automatic on tab close or explicit logout.
  const [kycAcknowledged, setKycAcknowledged] = useState(
    () => sessionStorage.getItem("kyc_acknowledged") === "true",
  );

  // Public routes that should never trigger the KYC gate
  const isPublicPage =
    location.pathname === "/login" ||
    location.pathname === "/signup" ||
    location.pathname.startsWith("/onboarding");

  // Check KYC status on every navigation while authenticated
  useEffect(() => {
    if (isAuthenticated && !isPublicPage && !kycAcknowledged) {
      try {
        const stored = localStorage.getItem(STORAGE.USER);
        if (stored) {
          const u = JSON.parse(stored);
          if (u.kycStatus && u.kycStatus !== "verified") {
            setKycUrl(u.kycVerificationUrl || null);
            setShowKYCModal(true);
          } else {
            setShowKYCModal(false);
          }
        }
      } catch {
        // ignore parse errors
      }
    } else {
      setShowKYCModal(false);
    }
  }, [isAuthenticated, isPublicPage, kycAcknowledged, location.pathname, user]);

  const handleKycComplete = () => {
    sessionStorage.setItem("kyc_acknowledged", "true");
    setKycAcknowledged(true);
    setShowKYCModal(false);
  };

  const handleKycLogout = async () => {
    sessionStorage.removeItem("kyc_acknowledged");
    setKycAcknowledged(false); // reset so next login shows the modal again if still unverified
    await logout();
    setShowKYCModal(false);
    navigate("/login");
  };

  return (
    <>
      {/* Global KYC gate — blocks all protected content when status is not 'verified' */}
      <KYCVerificationModal
        open={showKYCModal}
        kycUrl={kycUrl}
        onComplete={handleKycComplete}
        onLogout={handleKycLogout}
      />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />

        {/* Legacy onboarding (kept for backward compatibility) */}
        <Route path="/onboarding" element={<Onboarding />} />

        {/* New Multi-Step Onboarding Flow */}
        <Route path="/onboarding/start" element={<OnboardingStartScreen />} />
        <Route
          path="/onboarding/account-type"
          element={<AccountTypeScreen />}
        />
        <Route
          path="/onboarding/bvn-verification"
          element={<BvnVerificationScreen />}
        />
        <Route
          path="/onboarding/address-verification"
          element={<AddressVerificationScreen />}
        />
        <Route
          path="/onboarding/completion"
          element={<OnboardingCompletionScreen />}
        />

        {/* Public legal / help pages (no auth required) */}
        <Route path="/privacy-policy" element={<Suspense fallback={null}><PrivacyPolicy /></Suspense>} />

        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Layout />}>
            {/* ── Existing production routes (must not be removed) ── */}
            <Route index element={<Dashboard />} />
            <Route path="accounts" element={<Accounts />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="storefront" element={<Storefront />} />
            <Route path="store-map" element={<StoreMap />} />
            <Route path="communication" element={<Communication />} />
            <Route path="profile" element={<Profile />} />
            <Route path="wallet" element={<CustomerWallet />} />
            <Route path="feedback" element={<CustomerFeedbackNps />} />
            <Route path="surveys" element={<CustomerSurveys />} />
            <Route path="disputes" element={<CustomerDisputePortal />} />
            <Route path="loyalty" element={<LoyaltyProgramPage />} />
            <Route path="referrals" element={<ReferralProgramPage />} />
            <Route path="savings-products" element={<SavingsProductsPage />} />

            {/* ── New routes (lazy-loaded, wrapped in Suspense) ── */}
            <Route
              path="account-opening"
              element={<Suspense fallback={null}><AccountOpeningPage /></Suspense>}
            />
            <Route
              path="onboarding-pipeline"
              element={<Suspense fallback={null}><CustomerOnboardingPipeline /></Suspense>}
            />
            <Route
              path="onboarding-wizard"
              element={<Suspense fallback={null}><OnboardingWizard /></Suspense>}
            />

            {/* Wallet & Payments */}
            <Route
              path="wallet-system"
              element={<Suspense fallback={null}><CustomerWalletSystem /></Suspense>}
            />
            <Route
              path="qr-payment"
              element={<Suspense fallback={null}><DynamicQrPayment /></Suspense>}
            />
            <Route
              path="mobile-money"
              element={<Suspense fallback={null}><MobileMoneyPage /></Suspense>}
            />
            <Route
              path="payments"
              element={<Suspense fallback={null}><Payments /></Suspense>}
            />
            <Route
              path="payment-cancel"
              element={<Suspense fallback={null}><PaymentCancel /></Suspense>}
            />
            <Route
              path="payment-success"
              element={<Suspense fallback={null}><PaymentSuccess /></Suspense>}
            />
            <Route
              path="payment-link"
              element={<Suspense fallback={null}><PaymentLinkGenerator /></Suspense>}
            />
            <Route
              path="bill-payments"
              element={<Suspense fallback={null}><BillPaymentsPage /></Suspense>}
            />
            <Route
              path="airtime-vending"
              element={<Suspense fallback={null}><AirtimeVendingPage /></Suspense>}
            />
            <Route
              path="card-requests"
              element={<Suspense fallback={null}><CardRequestPage /></Suspense>}
            />

            {/* Remittance & FX */}
            <Route
              path="remittance"
              element={<Suspense fallback={null}><RemittancePage /></Suspense>}
            />
            <Route
              path="remittance/cross-border"
              element={<Suspense fallback={null}><CrossBorderRemittanceHub /></Suspense>}
            />
            <Route
              path="currency-hedging"
              element={<Suspense fallback={null}><CurrencyHedging /></Suspense>}
            />
            <Route
              path="multi-currency-exchange"
              element={<Suspense fallback={null}><MultiCurrencyExchange /></Suspense>}
            />

            {/* Collections & Financial Products */}
            <Route
              path="tax-collection"
              element={<Suspense fallback={null}><TaxCollectionPage /></Suspense>}
            />
            <Route
              path="pension-collection"
              element={<Suspense fallback={null}><PensionCollectionPage /></Suspense>}
            />
            <Route
              path="insurance-products"
              element={<Suspense fallback={null}><InsuranceProductsPage /></Suspense>}
            />
            <Route
              path="savings"
              element={<Suspense fallback={null}><SavingsProductsPageLazy /></Suspense>}
            />
            <Route
              path="loan-disbursement"
              element={<Suspense fallback={null}><LoanDisbursementPage /></Suspense>}
            />

            {/* Customer 360 & Analytics */}
            <Route
              path="customer-360"
              element={<Suspense fallback={null}><Customer360Page /></Suspense>}
            />
            <Route
              path="customer-360-view"
              element={<Suspense fallback={null}><Customer360View /></Suspense>}
            />
            <Route
              path="customer-journey-analytics"
              element={<Suspense fallback={null}><CustomerJourneyAnalyticsPage /></Suspense>}
            />
            <Route
              path="customer-journey-mapper"
              element={<Suspense fallback={null}><CustomerJourneyMapper /></Suspense>}
            />
            <Route
              path="customer-segmentation"
              element={<Suspense fallback={null}><CustomerSegmentationEngine /></Suspense>}
            />
            <Route
              path="customer-database"
              element={<Suspense fallback={null}><CustomerDatabasePage /></Suspense>}
            />

            {/* Disputes */}
            <Route
              path="dispute-resolution"
              element={<Suspense fallback={null}><DisputeResolutionPage /></Suspense>}
            />
            <Route
              path="dispute-portal"
              element={<Suspense fallback={null}><CustomerDisputePortalLazy /></Suspense>}
            />

            {/* Notifications */}
            <Route
              path="notifications/preferences"
              element={<Suspense fallback={null}><NotificationPreferences /></Suspense>}
            />
            <Route
              path="notifications/inbox"
              element={<Suspense fallback={null}><NotificationInbox /></Suspense>}
            />
            <Route
              path="notifications/alert-preferences"
              element={<Suspense fallback={null}><AlertNotificationPreferences /></Suspense>}
            />
            <Route
              path="notifications/settings"
              element={<Suspense fallback={null}><UserNotifSettings /></Suspense>}
            />
            <Route
              path="notifications/quiet-hours"
              element={<Suspense fallback={null}><UserQuietHours /></Suspense>}
            />

            {/* Loyalty & Referrals */}
            <Route
              path="loyalty-system"
              element={<Suspense fallback={null}><LoyaltySystem /></Suspense>}
            />
            <Route
              path="loyalty-program"
              element={<Suspense fallback={null}><LoyaltyProgramPageLazy /></Suspense>}
            />
            <Route
              path="referral-program"
              element={<Suspense fallback={null}><ReferralProgram /></Suspense>}
            />
            <Route
              path="referral"
              element={<Suspense fallback={null}><ReferralProgramPageLazy /></Suspense>}
            />

            {/* Reports */}
            <Route
              path="weekly-reports"
              element={<Suspense fallback={null}><WeeklyReports /></Suspense>}
            />
            <Route
              path="scheduled-reports"
              element={<Suspense fallback={null}><ScheduledReports /></Suspense>}
            />
            <Route
              path="report-scheduler"
              element={<Suspense fallback={null}><ReportSchedulerPage /></Suspense>}
            />
            <Route
              path="transaction-csv-export"
              element={<Suspense fallback={null}><TransactionCsvExport /></Suspense>}
            />
            <Route
              path="transaction-analytics"
              element={<Suspense fallback={null}><TransactionAnalytics /></Suspense>}
            />

            {/* KYC & Security */}
            <Route
              path="kyc-workflow"
              element={<Suspense fallback={null}><KycWorkflow /></Suspense>}
            />
            <Route
              path="kyc-verification"
              element={<Suspense fallback={null}><KycVerificationWorkflow /></Suspense>}
            />
            <Route
              path="biometric-auth"
              element={<Suspense fallback={null}><BiometricAuthPage /></Suspense>}
            />

            {/* Compliance & Privacy */}
            <Route
              path="gdpr"
              element={<Suspense fallback={null}><GdprDashboard /></Suspense>}
            />

            {/* Help & Support */}
            <Route
              path="help"
              element={<Suspense fallback={null}><HelpDeskPage /></Suspense>}
            />
            <Route
              path="video-tutorials"
              element={<Suspense fallback={null}><VideoTutorials /></Suspense>}
            />
            <Route
              path="user-guide"
              element={<Suspense fallback={null}><UserGuide /></Suspense>}
            />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
