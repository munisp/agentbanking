import {
  Activity,
  ArrowLeftRight,
  Bell,
  Building2,
  ClipboardList,
  Clock,
  Code2,
  CreditCard,
  Flag,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Settings,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "wouter";
import { PERMISSION_MAP, usePermissions } from "../_core/hooks/usePermissions";
import { useTenantBranding } from "../contexts/TenantBrandingContext";
import GlobalSearch from "./GlobalSearch";
import Notifications from "./Notifications";
import { AppTour, useTour } from "./AppTour";

interface MenuItem {
  path: string;
  label: string;
  icon: any;
  tourId?: string;
  permission?: { resourceType: string; permission: string } | null;
}

interface Section {
  label: string;
  items: MenuItem[];
}

const sections: Section[] = [
  {
    label: "Overview",
    items: [
      { path: "/", label: "Dashboard", icon: LayoutDashboard, tourId: "nav-dashboard", permission: PERMISSION_MAP.DASHBOARD },
    ],
  },
  {
    label: "Administration",
    items: [
      { path: "/admin/admins",        label: "Admin Management",    icon: UserCog,        tourId: "nav-admins",       permission: PERMISSION_MAP.MANAGE_EMPLOYEES },
      { path: "/business-management", label: "Business Management", icon: ShieldCheck,    tourId: "nav-business",     permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/tenants",             label: "Tenants",             icon: Building2,      tourId: "nav-tenants",      permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/transactions",        label: "Transactions",        icon: ArrowLeftRight, tourId: "nav-transactions", permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/features",            label: "Features",            icon: Flag,           tourId: "nav-features",     permission: PERMISSION_MAP.VIEW_ALL_DATA },
    ],
  },
  {
    label: "Billing",
    items: [
      { path: "/billing", label: "Billing Accounts", icon: CreditCard, tourId: "nav-billing", permission: PERMISSION_MAP.VIEW_ALL_DATA },
    ],
  },
  {
    label: "Audit & Compliance",
    items: [
      { path: "/admin/audit-logs",      label: "Audit Logs",      icon: ClipboardList, tourId: "nav-audit-logs",       permission: PERMISSION_MAP.VIEW_AUDIT_LOGS },
      { path: "/admin/temporal-access", label: "Temporal Access", icon: Clock,         tourId: "nav-temporal-access",  permission: PERMISSION_MAP.TEMPORAL_ACCESS },
      { path: "/my-access",             label: "My Permissions",  icon: ShieldCheck,   tourId: "nav-my-access",        permission: PERMISSION_MAP.MY_PERMISSIONS },
    ],
  },
  {
    label: "Monitoring & Alerts",
    items: [
      { path: "/monitoring",     label: "Monitoring",     icon: Activity, tourId: "nav-monitoring",     permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/alerts",         label: "Alerts",         icon: Bell,     tourId: "nav-alerts",         permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/alert-settings", label: "Alert Settings", icon: Settings, tourId: "nav-alert-settings", permission: PERMISSION_MAP.VIEW_ALL_DATA },
      { path: "/alert-rules",    label: "Alert Rules",    icon: Flag,     tourId: "nav-alert-rules",    permission: PERMISSION_MAP.VIEW_ALL_DATA },
    ],
  },
  {
    label: "Developer",
    items: [
      { path: "/developer-platform", label: "Developer Platform", icon: Code2, tourId: "nav-developer", featureFlag: "developer_platform", permission: PERMISSION_MAP.DEVELOPER_PLATFORM },
    ],
  },
];

export default function Sidebar() {
  const [location] = useLocation();
  const { name, logoUrl, primaryColor } = useTenantBranding();
  const { hasPermission, initialLoading, permissionCache } = usePermissions();
  const [accessLevel, setAccessLevel] = useState<string | null>(null);
  const [userInfo, setUserInfo] = useState<{ name: string; email: string } | null>(null);
  const { run: tourRun, startTour, stopTour } = useTour();

  useEffect(() => {
    const updateAccessLevel = () => {
      let level = localStorage.getItem("platform_role");
      let uName = "";
      let uEmail = "";

      const adminDataStr =
        localStorage.getItem("admin_data") ||
        localStorage.getItem("auth_user");
      if (adminDataStr) {
        try {
          const adminUser = JSON.parse(adminDataStr);
          if (!level) {
            level = adminUser.access_level || adminUser.user_role || adminUser.role || null;
          }
          uName = [adminUser.first_name, adminUser.last_name].filter(Boolean).join(" ") || adminUser.email || "";
          uEmail = adminUser.email || "";

          const tenantConfigStr = localStorage.getItem("tenant_config");
          if (tenantConfigStr && adminUser.email) {
            try {
              const tenantConfig = JSON.parse(tenantConfigStr);
              if (tenantConfig?.contact?.email === adminUser.email) level = "super_admin";
            } catch {}
          }
        } catch {
          if (!level) level = null;
        }
      }

      setAccessLevel(level || "support_agent");
      if (uName || uEmail) setUserInfo({ name: uName, email: uEmail });
    };

    updateAccessLevel();
    const handleStorageChange = (e: StorageEvent) => {
      if (["admin_data", "auth_user", "tenant_config", "platform_role"].includes(e.key || "")) {
        updateAccessLevel();
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  const filteredSections = useMemo(() => {
    return sections
      .map((section) => ({
        ...section,
        items: section.items.filter((item) => {
          if (item.permission === null) return true;
          if (item.permission) return hasPermission(item.permission.resourceType, item.permission.permission);
          return true;
        }),
      }))
      .filter((section) => section.items.length > 0);
  }, [hasPermission, permissionCache]);

  const roleLabel = (accessLevel || "support_agent")
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return (
    <>
      <div className="w-64 bg-white dark:bg-slate-900 border-r border-gray-100 dark:border-slate-800 min-h-screen flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 border-b border-gray-100 dark:border-slate-800">
          <div className="flex items-center gap-3 mb-1">
            {logoUrl && (
              <img src={logoUrl} alt={`${name} logo`} className="w-7 h-7 rounded-lg" />
            )}
            <h1 className="text-xl font-bold tracking-tight" style={{ color: primaryColor }}>
              {name}
            </h1>
          </div>
          <p className="text-[11px] font-medium text-gray-400 dark:text-slate-500 uppercase tracking-wider">
            Super Admin Console
          </p>
          <div className="flex items-center gap-2 mt-4">
            <div className="flex-1">
              <GlobalSearch />
            </div>
            <Notifications />
          </div>
        </div>

        {/* Sectioned Navigation */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          {initialLoading ? (
            <div className="animate-pulse space-y-5">
              {[3, 4, 2, 3].map((count, i) => (
                <div key={i}>
                  <div className="h-2 w-20 bg-gray-200 dark:bg-slate-700 rounded mx-3 mb-2" />
                  <div className="space-y-0.5">
                    {Array.from({ length: count }).map((_, j) => (
                      <div key={j} className="h-9 bg-gray-100 dark:bg-slate-800 rounded-lg mx-0.5" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            filteredSections.map((section) => (
              <div key={section.label} className="mb-4">
                <p
                  data-tour={`section-${section.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                  className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-slate-500"
                >
                  {section.label}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location === item.path;
                    return (
                      <Link key={item.path} href={item.path}>
                        <a
                          data-tour={item.tourId}
                          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm ${
                            isActive
                              ? "font-semibold"
                              : "text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 font-medium"
                          }`}
                          style={isActive ? { backgroundColor: `${primaryColor}12`, color: primaryColor } : {}}
                        >
                          <Icon className="h-4 w-4 flex-shrink-0" />
                          <span className="truncate tracking-tight">{item.label}</span>
                        </a>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </nav>

        {/* User Section */}
        <div className="px-3 py-4 border-t border-gray-100 dark:border-slate-800">
          {userInfo && (
            <div className="flex items-center gap-3 px-3 py-2.5 mb-1 rounded-lg bg-gray-50 dark:bg-slate-800/60">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs flex-shrink-0"
                style={{ backgroundColor: primaryColor }}
              >
                {userInfo.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2) || "SA"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-gray-900 dark:text-slate-100 truncate tracking-tight">
                  {userInfo.name || "Admin"}
                </p>
                <p className="text-[10px] font-medium truncate uppercase tracking-wider" style={{ color: primaryColor }}>
                  {roleLabel}
                </p>
              </div>
            </div>
          )}
          <Link href="/change-password">
            <div className="flex items-center gap-3 px-3 py-2.5 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-lg transition-colors w-full text-sm font-medium cursor-pointer">
              <KeyRound className="h-4 w-4 flex-shrink-0" />
              <span>Change Password</span>
            </div>
          </Link>
          <div className="flex items-center gap-1">
            <button
              data-tour="tour-help"
              onClick={startTour}
              title="Start guide tour"
              className="flex items-center gap-2 px-3 py-2.5 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-lg transition-colors text-sm font-medium"
            >
              <span className="h-4 w-4 flex items-center justify-center rounded-full border border-current text-xs font-bold flex-shrink-0">?</span>
              <span>Guide Tour</span>
            </button>
            <button
              onClick={() => {
                Object.keys(localStorage)
                  .filter((k) => k.startsWith("permify_cache:"))
                  .forEach((k) => localStorage.removeItem(k));
                localStorage.removeItem("54link-dev_auth");
                localStorage.removeItem("tenant_config");
                localStorage.removeItem("auth_user");
                localStorage.removeItem("admin_data");
                localStorage.removeItem("platform_role");
                localStorage.removeItem("access_token");
                localStorage.removeItem("keycloak_id");
                window.location.href = "/login";
              }}
              className="flex items-center gap-3 px-3 py-2.5 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-lg transition-colors text-sm font-medium ml-auto"
            >
              <LogOut className="h-4 w-4 flex-shrink-0" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </div>

      <AppTour run={tourRun} onFinish={stopTour} />
    </>
  );
}
