import { Flag, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTenantBranding } from "../contexts/TenantBrandingContext";
import { GLOBAL_FEATURE_CATALOG, tenantService } from "../services/tenant/tenantService";

// Category and tier metadata per feature (mirrors backend GLOBAL_FEATURES groupings)
const FEATURE_META: Record<string, { category: string; tier: "Standard" | "Premium" }> = {
  // Core
  auth:                  { category: "Core",                   tier: "Standard" },
  user_management:       { category: "Core",                   tier: "Standard" },
  accounts:              { category: "Core",                   tier: "Standard" },
  payments:              { category: "Core",                   tier: "Standard" },
  reporting:             { category: "Core",                   tier: "Standard" },
  notifications:         { category: "Core",                   tier: "Standard" },
  kyc_kyb:               { category: "Core",                   tier: "Standard" },
  compliance:            { category: "Core",                   tier: "Standard" },
  audit:                 { category: "Core",                   tier: "Standard" },
  // Banking Channels
  mobile_banking:        { category: "Banking Channels",       tier: "Standard" },
  ussd_banking:          { category: "Banking Channels",       tier: "Standard" },
  whatsapp_banking:      { category: "Banking Channels",       tier: "Premium"  },
  agent_banking:         { category: "Banking Channels",       tier: "Standard" },
  chatbot:               { category: "Banking Channels",       tier: "Premium"  },
  pos_terminal:          { category: "Banking Channels",       tier: "Standard" },
  // Payments & Transfers
  bill_payments:         { category: "Payments & Transfers",   tier: "Standard" },
  qr_payments:           { category: "Payments & Transfers",   tier: "Standard" },
  bulk_payments:         { category: "Payments & Transfers",   tier: "Standard" },
  standing_orders:       { category: "Payments & Transfers",   tier: "Standard" },
  remittance:            { category: "Payments & Transfers",   tier: "Premium"  },
  atm_management:        { category: "Payments & Transfers",   tier: "Standard" },
  // Cards & Accounts
  teller:                { category: "Cards & Accounts",       tier: "Standard" },
  card_management:       { category: "Cards & Accounts",       tier: "Standard" },
  virtual_accounts:      { category: "Cards & Accounts",       tier: "Standard" },
  fx:                    { category: "Cards & Accounts",       tier: "Premium"  },
  // Lending & Credit
  loans:                 { category: "Lending & Credit",       tier: "Standard" },
  education_loans:       { category: "Lending & Credit",       tier: "Premium"  },
  mortgage:              { category: "Lending & Credit",       tier: "Premium"  },
  lpo:                   { category: "Lending & Credit",       tier: "Premium"  },
  bnpl:                  { category: "Lending & Credit",       tier: "Premium"  },
  // Savings & Investments
  savings:               { category: "Savings & Investments",  tier: "Standard" },
  smart_savings:         { category: "Savings & Investments",  tier: "Premium"  },
  esusu:                 { category: "Savings & Investments",  tier: "Standard" },
  escrow:                { category: "Savings & Investments",  tier: "Premium"  },
  investment:            { category: "Savings & Investments",  tier: "Premium"  },
  // Risk & Compliance
  fraud_detection:       { category: "Risk & Compliance",      tier: "Standard" },
  risk_management:       { category: "Risk & Compliance",      tier: "Standard" },
  dispute:               { category: "Risk & Compliance",      tier: "Standard" },
  aml_compliance:        { category: "Risk & Compliance",      tier: "Premium"  },
  sanctions_screening:   { category: "Risk & Compliance",      tier: "Premium"  },
  regulatory_reporting:  { category: "Risk & Compliance",      tier: "Standard" },
  // Insurance
  insurance:             { category: "Insurance",              tier: "Premium"  },
  etherisc:              { category: "Insurance",              tier: "Premium"  },
  // Treasury & Finance
  treasury:              { category: "Treasury & Finance",     tier: "Premium"  },
  chart_of_accounts:     { category: "Treasury & Finance",     tier: "Standard" },
  reconciliation:        { category: "Treasury & Finance",     tier: "Standard" },
  finance:               { category: "Treasury & Finance",     tier: "Standard" },
  // Specialised Finance
  islamic_banking:       { category: "Specialised Finance",    tier: "Premium"  },
  agriculture_finance:   { category: "Specialised Finance",    tier: "Premium"  },
  supply_chain_finance:  { category: "Specialised Finance",    tier: "Premium"  },
  trade_finance:         { category: "Specialised Finance",    tier: "Premium"  },
  carbon_credits:        { category: "Specialised Finance",    tier: "Premium"  },
  cooperative_management:{ category: "Specialised Finance",    tier: "Standard" },
  diaspora_banking:      { category: "Specialised Finance",    tier: "Premium"  },
  microfinance:          { category: "Specialised Finance",    tier: "Standard" },
  // Wealth & Capital Markets
  wealth_management:     { category: "Wealth & Capital Markets", tier: "Premium" },
  pension:               { category: "Wealth & Capital Markets", tier: "Premium" },
  leasing:               { category: "Wealth & Capital Markets", tier: "Premium" },
  securities_trading:    { category: "Wealth & Capital Markets", tier: "Premium" },
  // Operations & Workflow
  employee_management:   { category: "Operations & Workflow",  tier: "Standard" },
  relationship_manager:  { category: "Operations & Workflow",  tier: "Standard" },
  document_management:   { category: "Operations & Workflow",  tier: "Standard" },
  communication_hub:     { category: "Operations & Workflow",  tier: "Standard" },
  merchant_management:   { category: "Operations & Workflow",  tier: "Premium"  },
  salary_processing:     { category: "Operations & Workflow",  tier: "Standard" },
  maker_checker:         { category: "Operations & Workflow",  tier: "Standard" },
  product_factory:       { category: "Operations & Workflow",  tier: "Premium"  },
  gamification:          { category: "Operations & Workflow",  tier: "Premium"  },
  // Platform & Integration
  open_banking:          { category: "Platform & Integration", tier: "Premium"  },
  biometric_auth:        { category: "Platform & Integration", tier: "Premium"  },
  developer_platform:    { category: "Platform & Integration", tier: "Premium"  },
  erp_integration:       { category: "Platform & Integration", tier: "Premium"  },
  temporal_access:       { category: "Platform & Integration", tier: "Standard" },
};

export default function FeatureFlags() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [filterTier, setFilterTier] = useState("all");
  const [tenantCount, setTenantCount] = useState(0);
  const [adoptionMap, setAdoptionMap] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    tenantService.getAllTenants().then(({ tenants }) => {
      setTenantCount(tenants.length);
      const counts: Record<string, number> = {};
      for (const tenant of tenants) {
        for (const flag of tenant.feature_flags ?? []) {
          if (flag.is_enabled) counts[flag.name] = (counts[flag.name] ?? 0) + 1;
        }
      }
      setAdoptionMap(counts);
    }).finally(() => setIsLoading(false));
  }, []);

  const features = useMemo(
    () =>
      GLOBAL_FEATURE_CATALOG.map((f) => ({
        name: f.name,
        label: f.label,
        category: FEATURE_META[f.name]?.category ?? "Other",
        tier: FEATURE_META[f.name]?.tier ?? "Standard",
        enabled: adoptionMap[f.name] ?? 0,
      })),
    [adoptionMap],
  );

  const CATEGORIES = useMemo(
    () => Array.from(new Set(features.map((f) => f.category))),
    [features],
  );

  const filteredFeatures = useMemo(
    () =>
      features.filter((f) => {
        const matchesSearch =
          f.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
          f.name.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesCategory = filterCategory === "all" || f.category === filterCategory;
        const matchesTier = filterTier === "all" || f.tier === filterTier;
        return matchesSearch && matchesCategory && matchesTier;
      }),
    [features, searchTerm, filterCategory, filterTier],
  );

  const totalFeatures = features.length;
  const premiumCount = features.filter((f) => f.tier === "Premium").length;
  const avgAdoption =
    tenantCount > 0
      ? Math.round(
          features.reduce((acc, f) => acc + (f.enabled / tenantCount) * 100, 0) /
            totalFeatures,
        )
      : 0;

  const getTierColor = (tier: string) =>
    tier === "Premium"
      ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
      : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300";

  return (
    <div
      className="min-h-screen dark:from-slate-900 dark:via-slate-900 dark:to-slate-900"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`,
      }}
    >
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <Flag className="w-8 h-8" style={{ color: primaryColor }} />
            Feature Flags Management
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Control platform features across all banks
          </p>
        </div>
      </div>

      <div className="container py-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-3xl font-bold text-slate-900 dark:text-white">{totalFeatures}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Total Features</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {totalFeatures - premiumCount}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Standard Features</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">{premiumCount}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Premium Features</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            {isLoading ? (
              <div className="h-9 w-16 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
            ) : (
              <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">{avgAdoption}%</div>
            )}
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Avg Adoption{tenantCount > 0 ? ` (${tenantCount} banks)` : ""}
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search features..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:border-transparent"
                style={{ "--tw-ring-color": primaryColor } as React.CSSProperties}
              />
            </div>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
            >
              <option value="all">All Categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select
              value={filterTier}
              onChange={(e) => setFilterTier(e.target.value)}
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
            >
              <option value="all">All Tiers</option>
              <option value="Standard">Standard</option>
              <option value="Premium">Premium</option>
            </select>
          </div>
        </div>

        {/* Features Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 animate-pulse"
              >
                <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-2/3 mb-2" />
                <div className="h-3 bg-slate-100 dark:bg-slate-600 rounded w-1/3 mb-4" />
                <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredFeatures.map((feature) => {
              const adoption = tenantCount > 0 ? Math.round((feature.enabled / tenantCount) * 100) : 0;
              return (
                <div
                  key={feature.name}
                  className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0 pr-3">
                      <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">
                        {feature.label}
                      </h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                        {feature.category}
                      </p>
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold flex-shrink-0 ${getTierColor(feature.tier)}`}>
                      {feature.tier}
                    </span>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-center justify-between text-sm mb-1.5">
                      <span className="text-slate-600 dark:text-slate-400">Adoption Rate</span>
                      <span className="font-semibold text-slate-900 dark:text-white">{adoption}%</span>
                    </div>
                    <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                      <div
                        className="h-2 rounded-full transition-all duration-500"
                        style={{
                          width: `${adoption}%`,
                          background: `linear-gradient(to right, ${primaryColor}, ${secondaryColor})`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="text-sm text-slate-500 dark:text-slate-400">
                    <span className="font-semibold text-slate-900 dark:text-white">{feature.enabled}</span>
                    {" / "}{tenantCount} banks using
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!isLoading && filteredFeatures.length === 0 && (
          <div className="text-center py-16 text-slate-500 dark:text-slate-400">
            No features match your filters.
          </div>
        )}
      </div>
    </div>
  );
}
