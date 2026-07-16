import { useEffect } from "react";
import { Route, Switch, useLocation } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import Sidebar from "./components/Sidebar";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { ProgressProvider } from "./contexts/ProgressContext";
import { TenantBrandingProvider } from "./contexts/TenantBrandingContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import AgentBanking from "./pages/AgentBanking";
import AlertRules from "./pages/AlertRules";
import AlertSettings from "./pages/AlertSettings";
import Alerts from "./pages/Alerts";
import AuditTrails from "./pages/AuditTrails";
import BankManagement from "./pages/BankManagement";
import BankOnboarding from "./pages/BankOnboarding";
import Billing from "./pages/Billing";
import Curriculum from "./pages/Curriculum";
import Dashboard from "./pages/Dashboard";
import Disputes from "./pages/Disputes";
import FeatureFlags from "./pages/FeatureFlags";
import GroupLending from "./pages/GroupLending";
import Home from "./pages/Home";
import Infrastructure from "./pages/Infrastructure";
import BNPL from "./pages/BNPL";
import LPO from "./pages/LPO";
import Labs from "./pages/Labs";
import Loans from "./pages/Loans";
import ChangePassword from "./pages/ChangePassword";
import Login from "./pages/Login";
import Monitoring from "./pages/Monitoring";
import NotFound from "./pages/NotFound";
import QuickReference from "./pages/QuickReference";
import RegulatoryReporting from "./pages/RegulatoryReporting";
import Resources from "./pages/Resources";
import Savings from "./pages/Savings";
import Transactions from "./pages/Transactions";
import UsageAnalytics from "./pages/UsageAnalytics";
import AdminManagement from "./pages/admin/admins";
import AdminAnalytics from "./pages/admin/analytics";
import AuditLogs from "./pages/admin/audit-logs";
import AdminCards from "./pages/admin/cards";
import {
  AdminFeatureFlagsPage,
  AdminSecurityPage,
  AdminBankingOpsPage,
  AdminAnalyticsPage,
  AdminUsersPage,
} from "./pages/AdminModulePages";
// Role-based dashboards
import AuditorDashboard from "./pages/dashboard/AuditorDashboard";
import BankAdminDashboard from "./pages/dashboard/BankAdminDashboard";
import ComplianceOfficerDashboard from "./pages/dashboard/ComplianceOfficerDashboard";
import CustomerSupportDashboard from "./pages/dashboard/CustomerSupportDashboard";
import OperationsOfficerDashboard from "./pages/dashboard/OperationsOfficerDashboard";
import SuperAdminDashboard from "./pages/dashboard/SuperAdminDashboard";
import TechnicalAdminDashboard from "./pages/dashboard/TechnicalAdminDashboard";
// COMMENTED OUT: Onboarding removed - app is only for 54link
// // COMMENTED OUT: Onboarding removed - app is only for 54link
// import AdminOnboarding from './pages/AdminOnboarding';
import BiometricAuthWorkspace from "./pages/BiometricAuthWorkspace";
import BusinessManagement from "./pages/BusinessManagement";
import KYC from "./pages/KYC";
import KYBEngineWorkspace from "./pages/KYBEngineWorkspace";
import KYBTriggersWorkspace from "./pages/KYBTriggersWorkspace";
import KYBVerification from "./pages/KYBVerification";
import CbnAgsmeisWorkspace from "./pages/CbnAgsmeisWorkspace";
import CbnAnchorBorrowersWorkspace from "./pages/CbnAnchorBorrowersWorkspace";
import CBNReturnsWorkspace from "./pages/CBNReturnsWorkspace";
import CbnAgriReturnsWorkspace from "./pages/CbnAgriReturnsWorkspace";
import CBNComplianceCheckerWorkspace from "./pages/CBNComplianceCheckerWorkspace";
// Developer Platform
import { useTemporalAccessPolling } from "./_core/hooks/useTemporalAccess";
import Analytics from "./pages/Analytics";
import AppReview from "./pages/AppReview";
import { DeveloperManagement } from "./pages/DeveloperManagement";
import DeveloperPlatform from "./pages/DeveloperPlatform";
import MyAccess from "./pages/MyAccess";
import Organizations from "./pages/Organizations";
import Security from "./pages/Security";
import TemporalAccess from "./pages/TemporalAccess";
import { tenantService } from "./services/tenant";
// TODO: STEP 5 — Feature Realignment
// COMMENTED OUT: Onboarding removed - app is only for 54link
// import { onboardingService } from "./services/onboarding";

function Router() {
  const [location, setLocation] = useLocation();
  const isLoginPage = location === "/login";
  // TODO: STEP 5 — Feature Realignment
  // COMMENTED OUT: Onboarding removed - app is only for 54link
  // const isOnboardingPage = location === '/admin/onboarding';
  // TODO: STEP 5 — Feature Realignment
  // COMMENTED OUT: KYC page check removed - not needed
  // const isKYCPage = location === '/kyc';
  const token = localStorage.getItem("auth_token");
  const isAuthenticated = token !== null && token !== "";

  // Keep temporal access grants in sync while authenticated
  useTemporalAccessPolling(isAuthenticated && !isLoginPage);

  // Fetch tenant data on page load if authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoginPage) {
      const fetchTenantData = async () => {
        try {
          const existingConfig = tenantService.getTenantConfig();
          if (!existingConfig) {
            await tenantService.getTenant();
            console.log('Tenant config loaded and stored in localStorage');
          }
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          console.error('Error fetching tenant data:', errorMessage);
        }
      };

      fetchTenantData();
    }
  }, [isAuthenticated, isLoginPage]);

  // TODO: STEP 5 — Feature Realignment
  // COMMENTED OUT: Onboarding check removed - app is only for 54link
  // Check onboarding status and redirect if needed
  // useEffect(() => {
  //   if (isAuthenticated && !isLoginPage && !isOnboardingPage && !isKYCPage) {
  //     const isOnboardingComplete = onboardingService.isOnboardingComplete();
  //     if (!isOnboardingComplete) {
  //       setLocation('/admin/onboarding');
  //     }
  //   }
  // }, [isAuthenticated, isLoginPage, isOnboardingPage, isKYCPage, setLocation]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated && !isLoginPage) {
      setLocation("/login");
    }
  }, [isAuthenticated, isLoginPage, setLocation]);

  if (!isAuthenticated && !isLoginPage) {
    return null;
  }

  // Dashboard route by platform role.
  // Priority: platform_role in localStorage (set from admin API during login), then JWT payload fields.
  let platformRole = localStorage.getItem("platform_role") || "";
  if (!platformRole && token) {
    try {
      const parts = token.split(".");
      if (parts.length === 3) {
        const payload = JSON.parse(atob(parts[1]));
        platformRole = payload.access_level || payload.role || "";
      }
    } catch {
      platformRole = "";
    }
  }
  if (!platformRole) platformRole = "support_agent";

  // Map v2.perm platform roles to dashboard components
  const dashboardByRole: Record<string, React.ComponentType> = {
    support_agent: CustomerSupportDashboard,
    relationship_manager: CustomerSupportDashboard,
    operations_manager: OperationsOfficerDashboard,
    risk_manager: ComplianceOfficerDashboard,
    internal_auditor: AuditorDashboard,
    compliance_officer: ComplianceOfficerDashboard,
    it_admin: TechnicalAdminDashboard,
    tenant_manager: BankAdminDashboard,
    super_admin: SuperAdminDashboard,
  };
  const DashboardComponent = dashboardByRole[platformRole] ?? Dashboard;

  return (
    <div className="flex">
      {!isLoginPage && <Sidebar />}
      <div className="flex-1">
        <Switch>
          <Route path="/" component={DashboardComponent} />
          <Route path="/tenants" component={BankManagement} />
          <Route path="/transactions" component={Transactions} />
          <Route path="/loans" component={Loans} />
          <Route path="/bnpl" component={BNPL} />
          <Route path="/lpo" component={LPO} />
          <Route path="/disputes" component={Disputes} />
          <Route path="/savings" component={Savings} />
          {/* <Route path="/tenant-management" component={TenantManagement} /> */}
          <Route path="/features" component={FeatureFlags} />
          <Route path="/billing" component={Billing} />
          <Route path="/monitoring" component={Monitoring} />
          <Route path="/usage-analytics" component={UsageAnalytics} />
          <Route path="/alert-settings" component={AlertSettings} />
          <Route path="/alerts" component={Alerts} />
          <Route path="/alert-rules" component={AlertRules} />
          <Route path="/group-lending" component={GroupLending} />
          <Route path="/agent-banking" component={AgentBanking} />
          <Route path="/regulatory-reporting" component={RegulatoryReporting} />
          <Route path="/onboarding" component={BankOnboarding} />

          {/* Admin Routes */}
          <Route path="/admin/analytics" component={AdminAnalytics} />
          <Route path="/admin/cards" component={AdminCards} />
          <Route path="/admin/admins" component={AdminManagement} />
          <Route path="/admin/audit-logs" component={AuditLogs} />
          <Route path="/admin/temporal-access" component={TemporalAccess} />
          <Route path="/my-access" component={MyAccess} />
          <Route path="/audit-trails" component={AuditTrails} />
          {/* COMMENTED OUT: Onboarding removed - app is only for 54link */}
          {/* <Route path="/admin/onboarding" component={AdminOnboarding} /> */}

          {/* Admin Module Pages */}
          <Route path="/admin/feature-flags" component={AdminFeatureFlagsPage} />
          <Route path="/admin/security" component={AdminSecurityPage} />
          <Route path="/admin/banking-ops" component={AdminBankingOpsPage} />
          <Route path="/admin/analytics" component={AdminAnalyticsPage} />
          <Route path="/admin/users" component={AdminUsersPage} />

          {/* KYC & Onboarding */}
          <Route path="/biometric-auth" component={BiometricAuthWorkspace} />
          <Route path="/kyc" component={KYC} />
          <Route path="/kyb-engine" component={KYBEngineWorkspace} />
          <Route path="/kyb-triggers" component={KYBTriggersWorkspace} />
          <Route path="/kyb-verification" component={KYBVerification} />
          <Route path="/business-management" component={BusinessManagement} />

          {/* CBN Workspaces */}
          <Route path="/cbn-compliance-checker" component={CBNComplianceCheckerWorkspace} />
          <Route path="/cbn-returns" component={CBNReturnsWorkspace} />
          <Route path="/cbn-agri-returns" component={CbnAgriReturnsWorkspace} />
          <Route path="/cbn-agsmeis" component={CbnAgsmeisWorkspace} />
          <Route path="/cbn-anchor-borrowers" component={CbnAnchorBorrowersWorkspace} />

          {/* Developer Platform */}
          <Route path="/developer-platform" component={DeveloperPlatform} />
          <Route
            path="/developer-platform/developers"
            component={DeveloperManagement}
          />

          <Route
            path="/developer-platform/organizations"
            component={Organizations}
          />
          <Route path="/developer-platform/security" component={Security} />
          <Route path="/developer-platform/analytics" component={Analytics} />
          <Route path="/developer-platform/apps" component={AppReview} />

          {/* Auth & Utility */}
          <Route path="/login" component={Login} />
          <Route path="/change-password" component={ChangePassword} />
          <Route path="/home" component={Home} />
          <Route path="/curriculum" component={Curriculum} />
          <Route path="/infrastructure" component={Infrastructure} />
          <Route path="/resources" component={Resources} />
          <Route path="/quick-reference" component={QuickReference} />
          <Route path="/labs" component={Labs} />
          <Route path="/404" component={NotFound} />
          {/* Final fallback route */}
          <Route component={NotFound} />
        </Switch>
      </div>
    </div>
  );
}

// NOTE: About Theme
// - First choose a default theme according to your design style (dark or light bg), than change color palette in index.css
//   to keep consistent foreground/background color across components
// - If you want to make theme switchable, pass `switchable` ThemeProvider and use `useTheme` hook

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="light" switchable>
        <TenantBrandingProvider>
          <ProgressProvider>
            <TooltipProvider>
              <Toaster />
              <Router />
            </TooltipProvider>
          </ProgressProvider>
        </TenantBrandingProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
