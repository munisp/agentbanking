import {
    AlertCircle,
    Bell,
    ChevronDown,
    ClipboardList,
    CreditCard,
    Gift,
    Home,
    LogOut,
    MapPin,
    Menu,
    MessageSquare,
    PiggyBank,
    Receipt,
    ShoppingBag,
    Star,
    User,
    Users,
    Wallet,
    X,
} from "lucide-react";
import React, { useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import { useAuth } from "../hooks/useAuth";

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState({});
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const toggleSection = (title) =>
    setCollapsedSections(prev => ({ ...prev, [title]: !prev[title] }));

  const navigationSections = [
    {
      title: "HOME",
      items: [
        { name: "Dashboard", href: "/", icon: Home },
      ],
    },
    {
      title: "FINANCE",
      items: [
        { name: "Accounts", href: "/accounts", icon: Wallet },
        { name: "Transactions", href: "/transactions", icon: Receipt },
        { name: "Wallet", href: "/wallet", icon: CreditCard },
        { name: "Savings", href: "/savings-products", icon: PiggyBank },
      ],
    },
    {
      title: "REWARDS",
      items: [
        { name: "Loyalty", href: "/loyalty", icon: Gift },
        { name: "Referrals", href: "/referrals", icon: Users },
      ],
    },
    {
      title: "COMMERCE",
      items: [
        { name: "Storefront", href: "/storefront", icon: ShoppingBag },
        { name: "Find Stores", href: "/store-map", icon: MapPin },
      ],
    },
    {
      title: "SUPPORT",
      items: [
        { name: "Disputes", href: "/disputes", icon: AlertCircle },
        { name: "Messages", href: "/communication", icon: MessageSquare },
        { name: "Feedback", href: "/feedback", icon: Star },
        { name: "Surveys", href: "/surveys", icon: ClipboardList },
      ],
    },
    {
      title: "ACCOUNT",
      items: [
        { name: "Profile", href: "/profile", icon: User },
      ],
    },
  ];

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-gradient-to-b from-green-900 via-green-800 to-emerald-900 shadow-2xl transform transition-transform duration-300 ease-in-out lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-green-700 bg-green-800/50">
          <div className="flex items-center min-w-0 flex-1">
            <img
              src={logo}
              alt="Area Konnect by Fidelity"
              className="h-8 w-auto object-contain flex-shrink-0"
            />
            <h1 className="ml-2 text-base font-bold text-white truncate">
              Customer Portal
            </h1>
          </div>
          <button
            className="lg:hidden ml-2 flex-shrink-0 hover:bg-green-700 rounded-lg p-1 transition-all"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-6 h-6 text-white" />
          </button>
        </div>

        <nav className="mt-4 px-3 pb-24 overflow-y-auto" style={{ maxHeight: "calc(100vh - 180px)" }}>
          {navigationSections.map((section) => {
            const isCollapsed = !!collapsedSections[section.title];
            return (
              <div key={section.title} className="mb-3">
                <button
                  onClick={() => toggleSection(section.title)}
                  className="w-full flex items-center justify-between px-2 py-0.5 mb-1 rounded-md hover:bg-green-700/30 transition-colors text-green-300/60"
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
                      const isActive = location.pathname === item.href ||
                        (item.href !== "/" && location.pathname.startsWith(item.href + "/"));
                      const IconComponent = item.icon;
                      return (
                        <Link
                          key={item.name}
                          to={item.href}
                          className={`group flex items-center px-2.5 py-2 text-sm font-medium rounded-lg transition-all duration-150 ${
                            isActive
                              ? "bg-gradient-to-r from-green-600 to-emerald-600 text-white shadow-md"
                              : "text-green-100 hover:bg-green-700/50 hover:text-white"
                          }`}
                          onClick={() => setSidebarOpen(false)}
                        >
                          <IconComponent
                            className={`mr-2.5 h-4 w-4 shrink-0 ${isActive ? "text-white" : "text-green-300 group-hover:text-white"}`}
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
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-green-700 bg-green-800/50">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center min-w-0 flex-1">
              <div className="h-10 w-10 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg">
                <span className="text-white font-medium text-sm">
                  {user?.name
                    ?.split(" ")
                    .map((n) => n[0])
                    .join("") || "U"}
                </span>
              </div>
              <div className="ml-3 min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate">
                  {user?.name || "Customer"}
                </p>
                <p className="text-xs text-green-200 truncate">
                  {user?.email || ""}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-green-200 hover:text-white flex-shrink-0 hover:bg-green-700 p-2 rounded-lg transition-all"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-h-screen ml-0 lg:ml-64">
        {/* Top navigation */}
        <header className="bg-white shadow-sm border-b border-gray-200 flex-shrink-0">
          <div className="flex items-center justify-between h-16 px-6">
            <button className="lg:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-6 h-6 text-gray-400" />
            </button>
            <div className="flex items-center space-x-4 ml-auto">
              <button className="relative p-2 text-gray-400 hover:text-gray-500">
                <Bell className="w-6 h-6" />
                <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-white" />
              </button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
