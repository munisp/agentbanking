import { lazy, Suspense, useEffect } from "react";
import { Route, Switch, useLocation } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import Sidebar from "./components/Sidebar";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { ProgressProvider } from "./contexts/ProgressContext";
import { TenantBrandingProvider } from "./contexts/TenantBrandingContext";
import { ThemeProvider } from "./contexts/ThemeContext";
const AgentBanking = lazy(() => import("./pages/AgentBanking"));
const AlertRules = lazy(() => import("./pages/AlertRules"));
const AlertSettings = lazy(() => import("./pages/AlertSettings"));
const Alerts = lazy(() => import("./pages/Alerts"));
const AuditTrails = lazy(() => import("./pages/AuditTrails"));
const BankManagement = lazy(() => import("./pages/BankManagement"));
const BankOnboarding = lazy(() => import("./pages/BankOnboarding"));
const Billing = lazy(() => import("./pages/Billing"));
const Curriculum = lazy(() => import("./pages/Curriculum"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Disputes = lazy(() => import("./pages/Disputes"));
const FeatureFlags = lazy(() => import("./pages/FeatureFlags"));
const GroupLending = lazy(() => import("./pages/GroupLending"));
const Home = lazy(() => import("./pages/Home"));
const Infrastructure = lazy(() => import("./pages/Infrastructure"));
const BNPL = lazy(() => import("./pages/BNPL"));
const LPO = lazy(() => import("./pages/LPO"));
const Labs = lazy(() => import("./pages/Labs"));
const Loans = lazy(() => import("./pages/Loans"));
const ChangePassword = lazy(() => import("./pages/ChangePassword"));
const Login = lazy(() => import("./pages/Login"));
const Monitoring = lazy(() => import("./pages/Monitoring"));
const NotFound = lazy(() => import("./pages/NotFound"));
const QuickReference = lazy(() => import("./pages/QuickReference"));
const RegulatoryReporting = lazy(() => import("./pages/RegulatoryReporting"));
const Resources = lazy(() => import("./pages/Resources"));
const Savings = lazy(() => import("./pages/Savings"));
const Transactions = lazy(() => import("./pages/Transactions"));
const UsageAnalytics = lazy(() => import("./pages/UsageAnalytics"));
const AdminManagement = lazy(() => import("./pages/admin/admins"));
const AdminAnalytics = lazy(() => import("./pages/admin/analytics"));
const AuditLogs = lazy(() => import("./pages/admin/audit-logs"));
const AdminCards = lazy(() => import("./pages/admin/cards"));
const AdminFeatureFlagsPage = lazy(() =>
  import("./pages/AdminModulePages").then((m) => ({ default: m.AdminFeatureFlagsPage }))
);
const AdminSecurityPage = lazy(() =>
  import("./pages/AdminModulePages").then((m) => ({ default: m.AdminSecurityPage }))
);
const AdminBankingOpsPage = lazy(() =>
  import("./pages/AdminModulePages").then((m) => ({ default: m.AdminBankingOpsPage }))
);
const AdminAnalyticsPage = lazy(() =>
  import("./pages/AdminModulePages").then((m) => ({ default: m.AdminAnalyticsPage }))
);
const AdminUsersPage = lazy(() =>
  import("./pages/AdminModulePages").then((m) => ({ default: m.AdminUsersPage }))
);
// Role-based dashboards
const AuditorDashboard = lazy(() => import("./pages/dashboard/AuditorDashboard"));
const BankAdminDashboard = lazy(() => import("./pages/dashboard/BankAdminDashboard"));
const ComplianceOfficerDashboard = lazy(() => import("./pages/dashboard/ComplianceOfficerDashboard"));
const CustomerSupportDashboard = lazy(() => import("./pages/dashboard/CustomerSupportDashboard"));
const OperationsOfficerDashboard = lazy(() => import("./pages/dashboard/OperationsOfficerDashboard"));
const SuperAdminDashboard = lazy(() => import("./pages/dashboard/SuperAdminDashboard"));
const TechnicalAdminDashboard = lazy(() => import("./pages/dashboard/TechnicalAdminDashboard"));
// COMMENTED OUT: Onboarding removed - app is only for 54link
// // COMMENTED OUT: Onboarding removed - app is only for 54link
// import AdminOnboarding from './pages/AdminOnboarding';
const BiometricAuthWorkspace = lazy(() => import("./pages/BiometricAuthWorkspace"));
const BusinessManagement = lazy(() => import("./pages/BusinessManagement"));
const KYC = lazy(() => import("./pages/KYC"));
const KYBEngineWorkspace = lazy(() => import("./pages/KYBEngineWorkspace"));
const KYBTriggersWorkspace = lazy(() => import("./pages/KYBTriggersWorkspace"));
const KYBVerification = lazy(() => import("./pages/KYBVerification"));
const CbnAgsmeisWorkspace = lazy(() => import("./pages/CbnAgsmeisWorkspace"));
const CbnAnchorBorrowersWorkspace = lazy(() => import("./pages/CbnAnchorBorrowersWorkspace"));
const CBNReturnsWorkspace = lazy(() => import("./pages/CBNReturnsWorkspace"));
const CbnAgriReturnsWorkspace = lazy(() => import("./pages/CbnAgriReturnsWorkspace"));
const CBNComplianceCheckerWorkspace = lazy(() => import("./pages/CBNComplianceCheckerWorkspace"));
// Developer Platform
import { useTemporalAccessPolling } from "./_core/hooks/useTemporalAccess";
const Analytics = lazy(() => import("./pages/Analytics"));
const ApiExplorer = lazy(() => import("./pages/ApiExplorer"));
const AppReview = lazy(() => import("./pages/AppReview"));
const DeveloperManagement = lazy(() =>
  import("./pages/DeveloperManagement").then((m) => ({ default: m.DeveloperManagement }))
);
const DeveloperPlatform = lazy(() => import("./pages/DeveloperPlatform"));
const MyAccess = lazy(() => import("./pages/MyAccess"));
const Organizations = lazy(() => import("./pages/Organizations"));
const Security = lazy(() => import("./pages/Security"));
const TemporalAccess = lazy(() => import("./pages/TemporalAccess"));
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
        <Suspense
          fallback={
            <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
              Loading…
            </div>
          }
        >
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
          <Route path="/api-explorer" component={ApiExplorer} />

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
        </Suspense>
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
