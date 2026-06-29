import {
    AlertCircle,
    ArrowDownLeft,
    ArrowUpRight,
    Award,
    BarChart3,
    Bell,
    BookOpen,
    Trophy,
    Building2,
    Calculator,
    Calendar,
    ChevronDown,
    CreditCard,
    Droplets,
    FileCheck,
    FileText,
    Globe,
    LayoutDashboard,
    LayoutGrid,
    LogOut,
    Map,
    MapPin,
    Menu,
    MessageSquare,
    MonitorSmartphone,
    Network,
    Nfc,
    Package,
    PiggyBank,
    PlayCircle,
    QrCode,
    Receipt,
    Send,
    Shield,
    ShieldCheck,
    Smartphone,
    Star,
    Store,
    Target,
    TrendingDown,
    TrendingUp,
    User,
    Users,
    Wifi,
    X,
    Zap,
} from "lucide-react";
import React, { useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import { useTenant } from "../contexts/TenantContext";
import { useAgentLocationTracking } from "../hooks/useAgentLocationTracking";
import { useAuth } from "../hooks/useAuth";
import LocationTrackingIndicator from "./LocationTrackingIndicator";
import { AppTour, useTour } from "./AppTour";
import LanguageSelector from "./LanguageSelector";

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState({});
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { logoUrl, name: tenantName } = useTenant();
  const agentRole = (user?.agentRole || "agent").toLowerCase();
  const { run: tourRun, startTour, stopTour } = useTour();

  const trackingStatus = useAgentLocationTracking();

  const toggleSection = (title) =>
    setCollapsedSections(prev => ({ ...prev, [title]: !prev[title] }));

  const navigationSections = [
    {
      title: "OVERVIEW",
      items: [
        { name: "Dashboard", href: "/", icon: LayoutDashboard, tourId: "nav-dashboard" },
      ],
    },
    {
      title: "FINANCE",
      items: [
        { name: "Cash In", href: "/cash-in", icon: ArrowDownLeft, tourId: "nav-cash-in" },
        { name: "Cash Out", href: "/cash-out", icon: ArrowUpRight, tourId: "nav-cash-out" },
        { name: "Float Requests", href: "/float", icon: Droplets, tourId: "nav-float" },
        { name: "Commission", href: "/commission", icon: Award, tourId: "nav-commission" },
        { name: "Loyalty", href: "/loyalty", icon: BookOpen, tourId: "nav-loyalty" },
        { name: "Chart of Accounts", href: "/chart-of-accounts", icon: Building2 },
      ],
    },
    {
      title: "BUSINESS",
      items: [
        { name: "My Businesses", href: "/businesses", icon: Store },
        ...(agentRole === "super_agent" ? [{ name: "Agent Network", href: "/hierarchy", icon: Network }] : []),
        { name: "Store Map", href: "/store-map", icon: MapPin },
      ],
    },
    {
      title: "POS & OPERATIONS",
      items: [
        { name: "POS Terminals", href: "/pos", icon: MonitorSmartphone, tourId: "nav-pos" },
        { name: "POS Requests", href: "/pos/requests", icon: FileText },
        { name: "QR Scanner", href: "/scanner", icon: QrCode },
        { name: "Orders", href: "/orders", icon: FileText },
        { name: "Inventory", href: "/inventory", icon: Package },
        { name: "Receipts", href: "/receipts", icon: Receipt },
      ],
    },
    {
      title: "TRANSACTIONS",
      items: [
        { name: "Transactions", href: "/transactions", icon: Receipt, tourId: "nav-transactions" },
        { name: "Transfer", href: "/transfer", icon: Send, tourId: "nav-transfer" },
        { name: "Beneficiaries", href: "/beneficiaries", icon: Users },
        { name: "Send Remittance", href: "/send-remittance", icon: Globe },
        { name: "Remittance Verification", href: "/remittance-verification", icon: Shield },
        { name: "Bill Payment & VAT", href: "/bills", icon: CreditCard, tourId: "nav-bills" },
        { name: "Insurance", href: "/insurance", icon: ShieldCheck },
      ],
    },
    {
      title: "SAVINGS",
      items: [
        { name: "Savings Goals", href: "/savings", icon: PiggyBank },
        { name: "Rate Calculator", href: "/calculator", icon: Calculator },
      ],
    },
    {
      title: "GROWTH",
      items: [
        { name: "Training Academy", href: "/training", icon: BookOpen, tourId: "nav-training" },
        { name: "Achievements", href: "/achievements", icon: Trophy, tourId: "nav-achievements" },
        { name: "My Performance", href: "/performance", icon: BarChart3, tourId: "nav-performance" },
        { name: "Performance Overview", href: "/agent-performance-overview", icon: Target },
        { name: "Leaderboard", href: "/performance/leaderboard", icon: Users },
        { name: "Scorecard", href: "/performance/scorecard", icon: Star },
        { name: "Video Tutorials", href: "/tutorials", icon: PlayCircle },
      ],
    },
    {
      title: "INSIGHTS",
      items: [
        { name: "Projections", href: "/projections", icon: TrendingUp },
        { name: "Transaction Map", href: "/transaction-map", icon: Map },
        { name: "Weekly Reports", href: "/reports/weekly", icon: Calendar },
        { name: "Float Forecasting", href: "/float-forecasting", icon: TrendingUp },
        { name: "Float Insurance", href: "/float-insurance", icon: Shield },
        { name: "Micro-Insurance", href: "/micro-insurance", icon: ShieldCheck },
      ],
    },
    {
      title: "CUSTOMERS",
      items: [
        { name: "Customer Feedback", href: "/customer-feedback", icon: MessageSquare },
        { name: "Customer 360", href: "/customer-360", icon: User },
      ],
    },
    {
      title: "SUPPORT",
      items: [
        { name: "Compliance", href: "/compliance", icon: FileCheck },
        { name: "Messages", href: "/messages", icon: MessageSquare },
        { name: "Disputes", href: "/disputes", icon: AlertCircle },
        { name: "Network Status", href: "/network-status", icon: Wifi },
      ],
    },
    {
      title: "ACCOUNT",
      items: [
        { name: "My Devices", href: "/my-devices", icon: Smartphone },
        { name: "Profile", href: "/profile", icon: User },
        { name: "Churn Insights", href: "/churn-prediction", icon: TrendingDown },
      ],
    },
  ];

  // Keep flat list for active-state detection (child-route logic)
  const navigation = navigationSections.flatMap(s => s.items);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-gray-50 to-gray-100 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 shadow-2xl transform transition-transform duration-300 ease-in-out lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
        style={{
          background: "linear-gradient(to bottom, var(--tenant-primary-color,#004F71), color-mix(in srgb, var(--tenant-primary-color,#004F71) 60%, black))",
        }}
      >
        <div
          className="flex items-center justify-between h-16 px-4 border-b bg-black/20"
          style={{ borderColor: "rgba(255,255,255,0.1)" }}
        >
          <div className="flex items-center min-w-0 flex-1">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={tenantName}
                className="h-8 w-auto object-contain shrink-0"
              />
            ) : (
              <div className="h-8 w-8 rounded-lg bg-white/20 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {tenantName.slice(0, 2).toUpperCase()}
              </div>
            )}
            <h1 className="ml-2 text-base font-bold text-white truncate">
              {tenantName}
            </h1>
          </div>
          <button
            className="lg:hidden ml-2 shrink-0 rounded-lg p-1 transition-all"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.1)" }}
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-6 h-6 text-white" />
          </button>
        </div>

        <nav
          className="mt-4 px-3 pb-24 overflow-y-auto"
          style={{ maxHeight: "calc(100vh - 180px)" }}
        >
          {navigationSections.map((section) => {
            const isCollapsed = !!collapsedSections[section.title];
            return (
              <div key={section.title} className="mb-3">
                <button
                  onClick={() => toggleSection(section.title)}
                  className="w-full flex items-center justify-between px-2 py-0.5 mb-1 rounded-md transition-colors"
                  style={{ color: "rgba(255,255,255,0.35)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                >
                  <span className="text-[10px] font-bold tracking-widest uppercase">
                    {section.title}
                  </span>
                  <ChevronDown
                    className="h-3 w-3 flex-shrink-0 transition-transform duration-200"
                    style={{ transform: isCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}
                  />
                </button>
                {!isCollapsed && (
                  <div className="space-y-0.5">
                    {section.items.map((item) => {
                      const hasChildRoute = navigation.some(
                        (navItem) => navItem.href !== item.href && navItem.href.startsWith(item.href + "/"),
                      );
                      let isActive;
                      if (item.href === "/") {
                        isActive = location.pathname === "/";
                      } else if (hasChildRoute) {
                        isActive = location.pathname === item.href;
                      } else {
                        isActive = location.pathname === item.href || location.pathname.startsWith(item.href + "/");
                      }
                      const IconComponent = item.icon;
                      return (
                        <Link
                          key={item.name}
                          to={item.href}
                          data-tour={item.tourId}
                          className="group flex items-center px-2.5 py-2 text-sm font-medium rounded-lg transition-all duration-150"
                          style={
                            isActive
                              ? { backgroundColor: "var(--tenant-secondary-color,#69BC5E)", color: "#1F2937" }
                              : { color: "rgba(255,255,255,0.8)" }
                          }
                          onMouseEnter={(e) => {
                            if (!isActive) {
                              e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.1)";
                              e.currentTarget.style.color = "#ffffff";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) {
                              e.currentTarget.style.backgroundColor = "transparent";
                              e.currentTarget.style.color = "rgba(255,255,255,0.8)";
                            }
                          }}
                          onClick={() => setSidebarOpen(false)}
                        >
                          <IconComponent
                            className="mr-2.5 h-4 w-4 shrink-0"
                            style={{ color: isActive ? "#1F2937" : "rgba(255,255,255,0.7)" }}
                          />
                          <span className="truncate">{item.name}</span>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* User Info */}
        <div
          className="absolute bottom-0 left-0 right-0 p-4 border-t bg-black/20"
          style={{ borderColor: "rgba(255,255,255,0.1)" }}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center min-w-0 flex-1">
              <div
                className="h-10 w-10 rounded-full flex items-center justify-center shrink-0 shadow-lg"
                style={{ backgroundColor: "var(--tenant-secondary-color,#69BC5E)" }}
              >
                <span
                  className="font-medium text-sm"
                  style={{ color: "#1F2937" }}
                >
                  {user?.name
                    ?.split(" ")
                    .map((n) => n[0])
                    .join("") || "A"}
                </span>
              </div>
              <div className="ml-3 min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate">
                  {user?.name || "Agent"}
                </p>
                <p
                  className="text-xs truncate"
                  style={{ color: "rgba(255, 255, 255, 0.7)" }}
                >
                  {user?.agentCode || ""}
                </p>
              </div>
            </div>
            <button
              data-tour="tour-help"
              onClick={startTour}
              className="shrink-0 p-2 rounded-lg transition-all"
              style={{ color: "var(--tenant-secondary-color,#6CC049)" }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.15)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
              title="Start guide tour"
            >
              <span style={{ fontSize: 16, fontWeight: 700 }}>?</span>
            </button>
            <button
              onClick={handleLogout}
              className="shrink-0 p-2 rounded-lg transition-all"
              style={{ color: "rgba(255, 255, 255, 0.8)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor =
                  "rgba(255, 255, 255, 0.1)";
                e.currentTarget.style.color = "#ffffff";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.color = "rgba(255, 255, 255, 0.8)";
              }}
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col min-h-screen ml-0 lg:ml-64">
        {/* Top navigation */}
        <header className="bg-white shadow-sm border-b border-gray-200 shrink-0">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <button className="lg:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-6 h-6 text-gray-400" />
            </button>
            <div className="flex items-center space-x-2 ml-auto">
              <LocationTrackingIndicator status={trackingStatus} />
              <LanguageSelector />
              <button className="relative p-2 text-gray-400 hover:text-gray-500">
                <Bell className="w-6 h-6" />
                <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-white" />
              </button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 min-w-0 p-3 sm:p-4 lg:p-6 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      <AppTour run={tourRun} onFinish={stopTour} />
    </div>
  );
};

export default Layout;
