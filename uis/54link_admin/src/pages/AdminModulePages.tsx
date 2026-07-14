// Design philosophy: faithful recovery of the extracted 54link-dev admin information architecture.
// These pages restore the archive's main-bank modules rather than blending in non-admin mobile continuity routes.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "wouter";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  Download,
  Lock,
  Search,
  Shield,
  ToggleLeft,
  TrendingUp,
  UserCog,
  Users,
  WalletCards,
} from "lucide-react";

import AdminWorkspaceLayout from "@/components/AdminWorkspaceLayout";
import {
  approveCustomerApprovalRequest,
  formatCurrency,
  formatRelativeIso,
  getAuditEntries,
  getAuthContext,
  getCustomerApprovalRequests,
  getCustomers,
  getExportJobs,
  getOperatorActions,
  getPlatformOverview,
  getProductCatalog,
  getRoleProfiles,
  getTenantConfigurations,
  rejectCustomerApprovalRequest,
  type AuditEntry,
  type AuthContextResponse,
  type CustomerApprovalRequest,
  type CustomerRecord,
  type ExportJob,
  type OperatorAction,
  type ProductSurface,
  type RoleProfile,
  type ServiceHealth,
  type TenantConfiguration,
  type TenantFeatureFlagRecord,
} from "@/lib/platform";

interface AdminDataState {
  authContext: AuthContextResponse | null;
  roles: RoleProfile[];
  audits: AuditEntry[];
  exports: ExportJob[];
  products: ProductSurface[];
  services: ServiceHealth[];
  customers: CustomerRecord[];
  actions: OperatorAction[];
  tenants: TenantConfiguration[];
}

const initialState: AdminDataState = {
  authContext: null,
  roles: [],
  audits: [],
  exports: [],
  products: [],
  services: [],
  customers: [],
  actions: [],
  tenants: [],
};

function useAdminData() {
  const [state, setState] = useState<AdminDataState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      const [overviewResult, authContextResult, rolesResult, auditsResult, exportsResult, productsResult, customersResult, actionsResult, tenantsResult] = await Promise.allSettled([
        getPlatformOverview("operations"),
        getAuthContext("operations"),
        getRoleProfiles(),
        getAuditEntries("operations"),
        getExportJobs("operations"),
        getProductCatalog(),
        getCustomers(undefined, "operations"),
        getOperatorActions(undefined, "operations"),
        getTenantConfigurations(),
      ]);

      if (!active) return;

      const overview = overviewResult.status === "fulfilled" ? overviewResult.value : null;
      const products = productsResult.status === "fulfilled" ? productsResult.value.products : [];

      setState({
        authContext: authContextResult.status === "fulfilled" ? authContextResult.value : null,
        roles: rolesResult.status === "fulfilled" ? rolesResult.value.items : [],
        audits: auditsResult.status === "fulfilled" ? auditsResult.value.items : [],
        exports: exportsResult.status === "fulfilled" ? exportsResult.value.items : [],
        products: products.length ? products : overview?.products ?? [],
        services: overview?.serviceHealth ?? [],
        customers: customersResult.status === "fulfilled" ? customersResult.value.items : [],
        actions: actionsResult.status === "fulfilled" ? actionsResult.value.items : [],
        tenants: tenantsResult.status === "fulfilled" ? tenantsResult.value.items : [],
      });

      const failures = [
        overviewResult,
        authContextResult,
        rolesResult,
        auditsResult,
        exportsResult,
        productsResult,
        customersResult,
        actionsResult,
        tenantsResult,
      ].filter((result) => result.status === "rejected");

      setError(
        failures.length
          ? "Some admin data sources are unavailable in the current static preview, so this page is rendering with partial platform data."
          : null,
      );
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, []);

  return { ...state, loading, error };
}

function statusTone(status: string) {
  switch (status) {
    case "healthy":
    case "Ready":
    case "Active":
    case "active":
    case "Done":
    case "completed":
      return "bg-emerald-100 text-emerald-700";
    case "degraded":
    case "Pending":
    case "Queued":
    case "In progress":
    case "Review":
    case "recovered":
      return "bg-amber-100 text-amber-700";
    case "Failed":
    case "down":
    case "Dormant":
      return "bg-rose-100 text-rose-700";
    default:
      return "bg-stone-200 text-stone-700";
  }
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[1.8rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)] sm:p-6">
      <div>
        <h2 className="text-2xl font-semibold text-stone-900">{title}</h2>
        <p className="mt-2 text-sm leading-7 text-stone-500">{description}</p>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function AdminFeatureFlagsPage() {
  const { products, services, actions, tenants, loading, error } = useAdminData();
  const [query, setQuery] = useState("");
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [tenantFlags, setTenantFlags] = useState<Record<string, Record<string, boolean>>>({});
  const [brandingDrafts, setBrandingDrafts] = useState<Record<string, { displayName: string; primaryColor: string; accentColor: string; customDomain: string }>>({});
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedTenantId && tenants.length) {
      setSelectedTenantId(tenants[0].tenantId);
    }
  }, [selectedTenantId, tenants]);

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.tenantId === selectedTenantId) ?? tenants[0] ?? null,
    [selectedTenantId, tenants],
  );

  useEffect(() => {
    if (!selectedTenant) return;
    setTenantFlags((current) => ({
      ...current,
      [selectedTenant.tenantId]: current[selectedTenant.tenantId] ?? Object.fromEntries(selectedTenant.featureFlags.map((flag) => [flag.key, flag.enabled])),
    }));
    setBrandingDrafts((current) => ({
      ...current,
      [selectedTenant.tenantId]: current[selectedTenant.tenantId] ?? {
        displayName: selectedTenant.whiteLabel.displayName,
        primaryColor: selectedTenant.whiteLabel.primaryColor,
        accentColor: selectedTenant.whiteLabel.accentColor,
        customDomain: selectedTenant.whiteLabel.customDomain ?? "",
      },
    }));
  }, [selectedTenant]);

  const currentFlagState = selectedTenant ? tenantFlags[selectedTenant.tenantId] ?? {} : {};
  const currentBranding = selectedTenant ? brandingDrafts[selectedTenant.tenantId] : null;

  const flagRecords = useMemo(() => {
    if (!selectedTenant) return [] as Array<TenantFeatureFlagRecord & { source: string }>;

    const baseFlags = selectedTenant.featureFlags.map((flag) => ({
      ...flag,
      enabled: currentFlagState[flag.key] ?? flag.enabled,
      source: `Tenant ${selectedTenant.name}`,
    }));

    const productFlags = products
      .filter((product) => selectedTenant.enabledModules.includes(product.key) || product.category === selectedTenant.segment)
      .map((product) => ({
        key: product.key,
        label: product.title,
        category: "platform" as const,
        description: product.summary,
        enabled: currentFlagState[product.key] ?? product.status !== "down",
        rolloutStage: "controlled" as const,
        adminManaged: true,
        dependsOn: product.services,
        source: `Product route ${product.route}`,
      }));

    const serviceFlags = services
      .filter((service) => selectedTenant.enabledModules.some((module) => service.route.includes(module.replace(/_/g, "-")) || service.name.toLowerCase().includes(module.split("-")[0])))
      .slice(0, 6)
      .map((service) => ({
        key: service.name,
        label: service.name,
        category: "platform" as const,
        description: service.description,
        enabled: currentFlagState[service.name] ?? service.status === "healthy",
        rolloutStage: service.status === "healthy" ? "general" as const : "controlled" as const,
        adminManaged: true,
        dependsOn: service.dependencies,
        source: `Service route ${service.route}`,
      }));

    return [...baseFlags, ...productFlags, ...serviceFlags].filter((record) => {
      const haystack = `${record.label} ${record.description} ${record.category} ${record.source}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    });
  }, [currentFlagState, products, query, selectedTenant, services]);

  async function syncFeatureFlag(tenantId: string, flagKey: string, enabled: boolean) {
    try {
      setSyncStatus(`Syncing ${flagKey} to recovered tenant governance…`);
      const response = await fetch(`/api/db/tenant-feature-flags/${encodeURIComponent(flagKey)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, rolloutPct: enabled ? 100 : 0 }),
      });
      if (!response.ok) {
        throw new Error(`Feature sync failed with status ${response.status}`);
      }
      setSyncStatus(`Recovered backend saved ${flagKey} for ${tenantId}.`);
    } catch {
      setSyncStatus(`Unable to persist ${flagKey} to the backend for ${tenantId}. Refresh before assuming the change is saved.`);
    }
  }

  async function syncBranding(
    tenantId: string,
    draft: { displayName: string; primaryColor: string; accentColor: string; customDomain: string },
  ) {
    try {
      setSyncStatus(`Syncing white-label branding for ${tenantId}…`);
      const response = await fetch(`/api/db/tenants/${encodeURIComponent(tenantId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!response.ok) {
        throw new Error(`Branding sync failed with status ${response.status}`);
      }
      setSyncStatus(`Recovered backend saved branding for ${tenantId}.`);
    } catch {
      setSyncStatus(`Unable to persist branding to the backend for ${tenantId}. Refresh before assuming the change is saved.`);
    }
  }

  function updateFlag(flagKey: string) {
    if (!selectedTenant) return;
    const nextEnabled = !(tenantFlags[selectedTenant.tenantId]?.[flagKey] ?? selectedTenant.featureFlags.find((flag) => flag.key === flagKey)?.enabled ?? false);
      setTenantFlags((current) => {
        const nextTenantFlags = {
          ...(current[selectedTenant.tenantId] ?? Object.fromEntries(selectedTenant.featureFlags.map((flag) => [flag.key, flag.enabled]))),
          [flagKey]: nextEnabled,
        };
        return { ...current, [selectedTenant.tenantId]: nextTenantFlags };
      });
    void syncFeatureFlag(selectedTenant.tenantId, flagKey, nextEnabled);
  }

  function updateBranding(field: "displayName" | "primaryColor" | "accentColor" | "customDomain", value: string) {
    if (!selectedTenant) return;
    const next = {
      ...(brandingDrafts[selectedTenant.tenantId] ?? {
        displayName: selectedTenant.whiteLabel.displayName,
        primaryColor: selectedTenant.whiteLabel.primaryColor,
        accentColor: selectedTenant.whiteLabel.accentColor,
        customDomain: selectedTenant.whiteLabel.customDomain ?? "",
      }),
      [field]: value,
    };
    setBrandingDrafts((current) => ({ ...current, [selectedTenant.tenantId]: next }));
    void syncBranding(selectedTenant.tenantId, next);
  }

  const onboardingMetrics = selectedTenant
    ? [
        { label: "Onboarding status", value: selectedTenant.onboardingStatus, detail: `${selectedTenant.segment} tenant in ${selectedTenant.region}` },
        { label: "Admin-managed flags", value: String(selectedTenant.featureFlags.filter((flag) => flag.adminManaged).length), detail: "Available for onboarding-time enablement" },
        { label: "Enabled modules", value: String(selectedTenant.enabledModules.length), detail: selectedTenant.enabledModules.join(" · ") },
      ]
    : [];

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered admin module"
      title="Feature flags, tenant controls, and white-label rollout"
      description="This upgraded workspace makes feature governance tenant-aware, links onboarding presets to admin-managed controls, and exposes white-label settings that can be changed without leaving the admin shell."
      actions={
        <Link href="/admin/security" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          Review security posture <ArrowRight size={16} />
        </Link>
      }
    >
      <SectionCard
        title="Tenant-scoped rollout selection"
        description="Feature flags now resolve against a selected tenant so admins can decide what turns on during onboarding, which modules stay tenant-specific, and which branding envelope is active."
      >
        {syncStatus ? <p className="mb-4 rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{syncStatus}</p> : null}
        <div className="grid gap-4 lg:grid-cols-[1.1fr_1.9fr]">
          <div className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Tenant selector</p>
            <div className="mt-3 space-y-3">
              {tenants.map((tenant) => (
                <button
                  key={tenant.tenantId}
                  type="button"
                  onClick={() => setSelectedTenantId(tenant.tenantId)}
                  className={`w-full rounded-[1.2rem] border px-4 py-4 text-left transition ${selectedTenant?.tenantId === tenant.tenantId ? "border-emerald-300 bg-emerald-50" : "border-stone-200 bg-white hover:border-stone-300"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-stone-900">{tenant.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-stone-400">{tenant.tenantId} · {tenant.segment}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(tenant.onboardingStatus)}`}>{tenant.onboardingStatus}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {onboardingMetrics.map((metric) => (
              <article key={metric.label} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <p className="text-xs uppercase tracking-[0.16em] text-stone-400">{metric.label}</p>
                <p className="mt-2 text-2xl font-semibold text-stone-900">{metric.value}</p>
                <p className="mt-2 text-sm leading-6 text-stone-500">{metric.detail}</p>
              </article>
            ))}
            {!onboardingMetrics.length && (
              <article className="md:col-span-3 rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
                {loading ? "Loading tenant controls…" : error ?? "No tenant configuration records are available in the current preview."}
              </article>
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Managed rollout surface"
        description="The feature-governance model now combines tenant presets, module enablement, and service dependencies so administrators can decide what to activate during onboarding with clearer blast-radius context."
      >
        <div className="mb-4 flex items-center gap-3 rounded-[1.2rem] border border-stone-100 bg-stone-50 px-4 py-3">
          <Search size={16} className="text-stone-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search tenant feature switches"
            className="w-full bg-transparent text-sm text-stone-700 outline-none placeholder:text-stone-400"
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {flagRecords.map((record) => (
            <article key={`${selectedTenant?.tenantId ?? "tenant"}-${record.key}`} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-semibold text-stone-900">{record.label}</h3>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(record.enabled ? "active" : "down")}`}>
                      {record.enabled ? "Enabled" : "Disabled"}
                    </span>
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-stone-600">{record.rolloutStage}</span>
                  </div>
                  <p className="mt-2 text-sm leading-7 text-stone-500">{record.description}</p>
                  <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-stone-400">{record.category} · {record.source}</p>
                  {record.dependsOn?.length ? <p className="mt-2 text-xs text-stone-500">Depends on: {record.dependsOn.join(", ")}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={() => updateFlag(record.key)}
                  className={`inline-flex h-11 w-20 items-center rounded-full px-2 transition ${record.enabled ? "justify-end bg-emerald-600" : "justify-start bg-stone-300"}`}
                >
                  <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white text-stone-700 shadow-sm">
                    <ToggleLeft size={16} />
                  </span>
                </button>
              </div>
            </article>
          ))}
          {!flagRecords.length && (
            <article className="lg:col-span-2 rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
              {loading ? "Loading feature controls…" : error ?? "No feature-control records matched the current search."}
            </article>
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="White-label configuration and launch posture"
        description="Tenant branding is now treated as an operational control rather than a static mock-up, with editable defaults and a live preview tied to the selected tenant."
      >
        {selectedTenant && currentBranding ? (
          <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="rounded-[1.2rem] border border-stone-100 bg-stone-50 p-4 text-sm text-stone-600">
                Display name
                <input value={currentBranding.displayName} onChange={(event) => updateBranding("displayName", event.target.value)} className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-stone-900 outline-none" />
              </label>
              <label className="rounded-[1.2rem] border border-stone-100 bg-stone-50 p-4 text-sm text-stone-600">
                Custom domain
                <input value={currentBranding.customDomain} onChange={(event) => updateBranding("customDomain", event.target.value)} className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-stone-900 outline-none" />
              </label>
              <label className="rounded-[1.2rem] border border-stone-100 bg-stone-50 p-4 text-sm text-stone-600">
                Primary color
                <input value={currentBranding.primaryColor} onChange={(event) => updateBranding("primaryColor", event.target.value)} className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-stone-900 outline-none" />
              </label>
              <label className="rounded-[1.2rem] border border-stone-100 bg-stone-50 p-4 text-sm text-stone-600">
                Accent color
                <input value={currentBranding.accentColor} onChange={(event) => updateBranding("accentColor", event.target.value)} className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-stone-900 outline-none" />
              </label>
            </div>
            <article className="rounded-[1.5rem] border border-stone-100 p-6 text-white shadow-[0_18px_60px_rgba(15,23,42,0.08)]" style={{ background: `linear-gradient(135deg, ${currentBranding.primaryColor}, ${currentBranding.accentColor})` }}>
              <div className="flex items-center gap-4">
                <img src={selectedTenant.whiteLabel.logoUrl} alt={currentBranding.displayName} className="h-16 w-16 rounded-2xl bg-white/15 object-contain p-2" />
                <div>
                  <p className="text-sm uppercase tracking-[0.2em] text-white/70">White-label preview</p>
                  <h3 className="mt-2 text-2xl font-semibold">{currentBranding.displayName}</h3>
                </div>
              </div>
              <p className="mt-4 text-sm leading-7 text-white/85">{selectedTenant.whiteLabel.loginHeadline}</p>
              <div className="mt-5 grid gap-3 text-sm text-white/80">
                <div className="rounded-2xl bg-black/10 px-4 py-3">Legal entity: {selectedTenant.whiteLabel.legalEntity}</div>
                <div className="rounded-2xl bg-black/10 px-4 py-3">Support: {selectedTenant.whiteLabel.supportEmail}</div>
                <div className="rounded-2xl bg-black/10 px-4 py-3">Domain: {currentBranding.customDomain || "Not yet assigned"}</div>
              </div>
            </article>
          </div>
        ) : (
          <div className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">Tenant branding data is loading.</div>
        )}
      </SectionCard>

      <SectionCard
        title="Operator actions linked to rollout governance"
        description="Pending operational actions still anchor rollout decisions, but they now sit beside tenant-scoped governance rather than a single global switch list."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {actions.slice(0, 6).map((action) => (
            <article key={action.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-stone-900">{action.title}</p>
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(action.status)}`}>{action.status}</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-stone-500">{action.detail}</p>
              <p className="mt-3 text-xs uppercase tracking-[0.16em] text-stone-400">{action.domainKey}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </AdminWorkspaceLayout>
  );
}

export function AdminSecurityPage() {
  const { services, audits, authContext, loading, error } = useAdminData();

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered admin module"
      title="Security and control assurance"
      description="This page restores the extracted security dashboard concept using live service health, audit evidence, and operator-identity context from the current platform."
      actions={
        <Link href="/admin/banking" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          Open banking operations <ArrowRight size={16} />
        </Link>
      }
    >
      <SectionCard
        title="Platform control posture"
        description="The current static view combines service health and admin identity visibility to approximate the recovered archive’s security posture board."
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Issuer</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{authContext?.issuer ?? "54link-dev"}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Role: {authContext?.role ?? "operations"}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Healthy services</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{services.filter((service) => service.status === "healthy").length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Core systems reporting a healthy state.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Recent audit records</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{audits.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Available activity and governance evidence.</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="Service assurance"
        description="Recovered security review is anchored to the current platform’s service health registry."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {services.slice(0, 8).map((service) => (
            <article key={service.name} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                    <Shield size={18} />
                  </span>
                  <div>
                    <h3 className="text-lg font-semibold text-stone-900">{service.name}</h3>
                    <p className="text-sm text-stone-500">{service.route}</p>
                  </div>
                </div>
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(service.status)}`}>{service.status}</span>
              </div>
              <p className="mt-3 text-sm leading-7 text-stone-500">{service.description}</p>
            </article>
          ))}
          {!services.length && (
            <article className="lg:col-span-2 rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
              {loading ? "Loading security posture…" : error ?? "No service-assurance records are currently available."}
            </article>
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Recent audit evidence"
        description="This section preserves the archive’s operator-assurance intent by surfacing the latest admin audit activity."
      >
        <div className="space-y-4">
          {audits.slice(0, 6).map((entry) => (
            <article key={entry.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-stone-900 text-white">
                    <Lock size={16} />
                  </span>
                  <div>
                    <h3 className="text-base font-semibold text-stone-900">{entry.action}</h3>
                    <p className="text-sm text-stone-500">{entry.actorRole} · {entry.actorId}</p>
                  </div>
                </div>
                <span className="text-xs uppercase tracking-[0.16em] text-stone-400">{formatRelativeIso(entry.timestamp)}</span>
              </div>
              <p className="mt-3 text-sm leading-6 text-stone-500">{entry.detail}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </AdminWorkspaceLayout>
  );
}

export function AdminBankingOpsPage() {
  const { customers, actions, products, loading, error } = useAdminData();
  const [approvalQueue, setApprovalQueue] = useState<CustomerApprovalRequest[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueMessage, setQueueMessage] = useState<string | null>(null);
  const [busyApprovalId, setBusyApprovalId] = useState<string | null>(null);

  const activeCustomers = customers.filter((customer) => customer.status === "Active");
  const totalBalance = activeCustomers.reduce((sum, customer) => sum + customer.balance, 0);
  const lendingExposure = activeCustomers.reduce((sum, customer) => sum + customer.balance * 0.22, 0);
  const pendingActions = actions.filter((action) => action.status !== "Done");
  const customerNameById = useMemo(
    () => Object.fromEntries(customers.map((customer) => [customer.id, customer.name])),
    [customers],
  );
  const pendingApprovals = useMemo(
    () => approvalQueue.filter((approval) => approval.state === "pending"),
    [approvalQueue],
  );
  const exportApprovals = useMemo(
    () => pendingApprovals.filter((approval) => approval.entityType === "statement_export"),
    [pendingApprovals],
  );
  const workboardItems = useMemo(() => {
    const now = Date.now();
    return pendingApprovals
      .map((approval) => {
        const ageHours = Math.max(1, Math.round((now - new Date(approval.requestedAt).getTime()) / 36e5));
        const transferLike = approval.route.includes("/transfers") || approval.title.toLowerCase().includes("transfer");
        const owner = approval.entityType === "statement_export"
          ? "Reporting desk"
          : transferLike
            ? "Branch operations"
            : approval.entityType === "scheduled_bill"
              ? "Payments desk"
              : approval.entityType === "card_control"
                ? "Card controls"
                : "Customer servicing";
        const severity = ageHours >= 48 ? "critical" : ageHours >= 24 ? "warning" : "healthy";
        const escalation = severity !== "healthy" || transferLike;
        return {
          ...approval,
          ageHours,
          owner,
          severity,
          escalation,
          dueLabel: ageHours >= 48 ? "Past preferred SLA" : ageHours >= 24 ? "Approaching SLA threshold" : "Within preferred SLA",
        };
      })
      .sort((left, right) => right.ageHours - left.ageHours);
  }, [pendingApprovals]);
  const breachedWorkboardItems = useMemo(
    () => workboardItems.filter((item) => item.ageHours >= 24),
    [workboardItems],
  );
  const escalatedWorkboardItems = useMemo(
    () => workboardItems.filter((item) => item.escalation),
    [workboardItems],
  );
  const ownershipGroups = useMemo(() => {
    const groups = new Map<string, number>();
    for (const item of workboardItems) {
      groups.set(item.owner, (groups.get(item.owner) ?? 0) + 1);
    }
    return Array.from(groups.entries())
      .map(([owner, count]) => ({ owner, count }))
      .sort((left, right) => right.count - left.count);
  }, [workboardItems]);
  const queueMix = useMemo(() => {
    const groups = new Map<string, number>();
    for (const item of pendingApprovals) {
      const label = item.entityType.replaceAll("_", " ");
      groups.set(label, (groups.get(label) ?? 0) + 1);
    }
    return Array.from(groups.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count);
  }, [pendingApprovals]);

  useEffect(() => {
    let active = true;

    void (async () => {
      if (!customers.length) {
        if (active) {
          setApprovalQueue([]);
          setQueueLoading(false);
        }
        return;
      }

      setQueueLoading(true);
      try {
        const responses = await Promise.all(
          customers.slice(0, 8).map((customer) => getCustomerApprovalRequests(customer.id, "branch")),
        );
        if (!active) return;
        const deduped = new Map<string, CustomerApprovalRequest>();
        for (const response of responses) {
          for (const item of response.items) {
            deduped.set(item.id, item);
          }
        }
        setApprovalQueue(
          Array.from(deduped.values()).sort(
            (left, right) => new Date(right.requestedAt).getTime() - new Date(left.requestedAt).getTime(),
          ),
        );
        setQueueMessage(null);
      } catch {
        if (!active) return;
        setQueueMessage("Approval queue data is partially unavailable right now.");
      } finally {
        if (active) {
          setQueueLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [customers]);

  async function resolveApproval(approvalId: string, decision: "approve" | "reject") {
    setBusyApprovalId(approvalId);
    try {
      const response = decision === "approve"
        ? await approveCustomerApprovalRequest(approvalId, { resolutionNote: "Resolved from the Banking Operations queue." }, "branch")
        : await rejectCustomerApprovalRequest(approvalId, { resolutionNote: "Returned for manual correction from the Banking Operations queue." }, "branch");
      setApprovalQueue((current) => current.map((item) => (item.id === approvalId ? response.approvalRequest : item)));
      setQueueMessage(decision === "approve" ? "Approval request resolved successfully." : "Approval request rejected and returned for follow-up.");
    } catch {
      setQueueMessage("Unable to update that approval right now.");
    } finally {
      setBusyApprovalId(null);
    }
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered admin module"
      title="Banking operations"
      description="This restores the extracted BankingOps page as a first-class administrative route focused on customer accounts, lending exposure, and active operating queues."
      actions={
        <Link href="/operations" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          Open operator workspace <ArrowRight size={16} />
        </Link>
      }
    >
      <SectionCard
        title="Operational headline metrics"
        description="The active platform does not expose the exact extracted tRPC endpoints in static mode, so this restored BankingOps view uses current customer and workflow records to represent the same administrative domain."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Managed customers</p>
              <Users className="h-5 w-5 text-emerald-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{customers.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">{activeCustomers.length} currently active across the visible platform scope.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Deposit base</p>
              <WalletCards className="h-5 w-5 text-sky-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{formatCurrency(totalBalance)}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Approximate balance from active managed-customer records.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Lending exposure</p>
              <TrendingUp className="h-5 w-5 text-amber-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{formatCurrency(lendingExposure)}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Outstanding loans from the currently visible managed portfolio.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Pending actions</p>
              <CheckCircle2 className="h-5 w-5 text-violet-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{pendingActions.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Open operational work items still awaiting completion.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Pending approvals</p>
              <Shield className="h-5 w-5 text-rose-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{queueLoading ? "…" : pendingApprovals.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Customer-servicing requests currently awaiting branch decision.</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Export sign-offs</p>
              <Download className="h-5 w-5 text-sky-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{queueLoading ? "…" : exportApprovals.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Statement-export requests currently waiting for operator approval.</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="Customer and account supervision"
        description="This table restores the archive’s account-operations intent through the active customer ledger view available in the current platform."
      >
        <div className="space-y-4">
          {customers.slice(0, 8).map((customer) => (
            <article key={customer.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-semibold text-stone-900">{customer.name}</h3>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(customer.status)}`}>{customer.status}</span>
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-stone-600">{customer.segment}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-stone-500">{customer.location} · {customer.phone}</p>
                  <p className="mt-2 text-sm leading-6 text-stone-500">Relationship manager: {customer.relationshipManager}</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[360px]">
                  <div className="rounded-[1.1rem] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-stone-400">Balance</p>
                    <p className="mt-2 text-base font-semibold text-stone-900">{formatCurrency(customer.balance)}</p>
                  </div>
                  <div className="rounded-[1.1rem] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-stone-400">Estimated lending</p>
                    <p className="mt-2 text-base font-semibold text-stone-900">{formatCurrency(customer.balance * 0.22)}</p>
                  </div>
                  <div className="rounded-[1.1rem] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-stone-400">Last activity</p>
                    <p className="mt-2 text-base font-semibold text-stone-900">{formatRelativeIso(customer.lastTouchpoint)}</p>
                  </div>
                </div>
              </div>
            </article>
          ))}
          {!customers.length && (
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
              {loading ? "Loading customer operations…" : error ?? "No managed-customer records are currently available."}
            </article>
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Operator assignment and SLA workboard"
        description="The active approval rail now doubles as an operator workboard, showing queue ownership, aging, escalation pressure, and the next branch desk expected to act."
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
          <div>
            <div className="grid gap-4 md:grid-cols-3">
              <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <p className="text-sm font-medium text-stone-500">Assignments in branch queue</p>
                <p className="mt-4 text-3xl font-semibold text-stone-900">{queueLoading ? "…" : workboardItems.length}</p>
                <p className="mt-2 text-sm leading-6 text-stone-500">Requests that still require an operator owner, decision, or follow-through step.</p>
              </article>
              <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <p className="text-sm font-medium text-stone-500">Aging beyond 24h</p>
                <p className="mt-4 text-3xl font-semibold text-stone-900">{queueLoading ? "…" : breachedWorkboardItems.length}</p>
                <p className="mt-2 text-sm leading-6 text-stone-500">Queue items now outside the preferred same-day servicing window.</p>
              </article>
              <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <p className="text-sm font-medium text-stone-500">Escalation candidates</p>
                <p className="mt-4 text-3xl font-semibold text-stone-900">{queueLoading ? "…" : escalatedWorkboardItems.length}</p>
                <p className="mt-2 text-sm leading-6 text-stone-500">Requests that should stay visible to supervisors because of age, transfer risk, or export sensitivity.</p>
              </article>
            </div>
            <div className="mt-4 space-y-4">
              {workboardItems.length ? (
                workboardItems.slice(0, 6).map((item) => (
                  <article key={`workboard-${item.id}`} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-3">
                          <h3 className="text-lg font-semibold text-stone-900">{item.title}</h3>
                          <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(item.state)}`}>{item.state}</span>
                          <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(item.severity)}`}>{item.dueLabel}</span>
                        </div>
                        <p className="mt-2 text-sm leading-7 text-stone-500">{item.detail}</p>
                        <div className="mt-3 flex flex-wrap gap-3 text-[11px] uppercase tracking-[0.16em] text-stone-400">
                          <span>Owner: {item.owner}</span>
                          <span>Customer: {customerNameById[item.customerId] ?? item.customerId}</span>
                          <span>{item.ageHours}h open</span>
                          <span>Route: {item.route}</span>
                        </div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[250px]">
                        <div className="rounded-[1.1rem] bg-white px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-stone-400">Queue type</p>
                          <p className="mt-2 text-sm font-semibold text-stone-900">{item.entityType.replaceAll("_", " ")}</p>
                        </div>
                        <div className="rounded-[1.1rem] bg-white px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-stone-400">Approval role</p>
                          <p className="mt-2 text-sm font-semibold text-stone-900">{item.approvalRole}</p>
                        </div>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
                  {queueLoading ? "Loading operator workboard…" : "No pending operator assignments are currently visible in the branch queue."}
                </article>
              )}
            </div>
          </div>
          <div className="space-y-4">
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <h3 className="text-lg font-semibold text-stone-900">Queue ownership mix</h3>
              <p className="mt-2 text-sm leading-7 text-stone-500">These desk assignments turn the approval rail into a visible operations workboard instead of a flat action list.</p>
              <div className="mt-4 space-y-3">
                {ownershipGroups.length ? ownershipGroups.map((group) => (
                  <div key={group.owner} className="rounded-[1.1rem] bg-white px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-stone-900">{group.owner}</p>
                      <span className="rounded-full bg-stone-100 px-3 py-1 text-[11px] font-semibold text-stone-700">{group.count}</span>
                    </div>
                  </div>
                )) : <div className="rounded-[1.1rem] bg-white px-4 py-3 text-sm text-stone-500">No assignment ownership groups are visible yet.</div>}
              </div>
            </article>
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <h3 className="text-lg font-semibold text-stone-900">Request mix</h3>
              <p className="mt-2 text-sm leading-7 text-stone-500">This highlights which servicing actions are creating the most queue pressure right now.</p>
              <div className="mt-4 space-y-3">
                {queueMix.length ? queueMix.map((item) => (
                  <div key={item.label} className="rounded-[1.1rem] bg-white px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold capitalize text-stone-900">{item.label}</p>
                      <span className="rounded-full bg-stone-100 px-3 py-1 text-[11px] font-semibold text-stone-700">{item.count}</span>
                    </div>
                  </div>
                )) : <div className="rounded-[1.1rem] bg-white px-4 py-3 text-sm text-stone-500">No request types are currently visible in the queue.</div>}
              </div>
            </article>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Customer servicing approval queue"
        description="Recovered banking operations now includes an executable branch queue for customer transfer-adjacent requests, card controls, scheduled payments, and statement-export approvals."
      >
        <div className="space-y-4">
          {queueMessage ? (
            <div className="rounded-[1.2rem] bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{queueMessage}</div>
          ) : null}
          {pendingApprovals.length ? (
            pendingApprovals.slice(0, 8).map((approval) => (
              <article key={approval.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-lg font-semibold text-stone-900">{approval.title}</h3>
                      <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(approval.state)}`}>{approval.state}</span>
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-stone-600">{approval.entityType.replace("_", " ")}</span>
                    </div>
                    <p className="mt-2 text-sm leading-7 text-stone-500">{approval.detail}</p>
                    <div className="mt-3 flex flex-wrap gap-3 text-[11px] uppercase tracking-[0.16em] text-stone-400">
                      <span>Customer: {customerNameById[approval.customerId] ?? approval.customerId}</span>
                      <span>Approval role: {approval.approvalRole}</span>
                      <span>Requested {formatRelativeIso(approval.requestedAt)}</span>
                      <span>Route: {approval.route}</span>
                      <span>
                        Owner: {approval.entityType === "statement_export"
                          ? "Reporting desk"
                          : approval.route.includes("/transfers") || approval.title.toLowerCase().includes("transfer")
                            ? "Branch operations"
                            : approval.entityType === "scheduled_bill"
                              ? "Payments desk"
                              : approval.entityType === "card_control"
                                ? "Card controls"
                                : "Customer servicing"}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 lg:justify-end">
                    <button
                      type="button"
                      onClick={() => resolveApproval(approval.id, "approve")}
                      disabled={busyApprovalId === approval.id}
                      className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busyApprovalId === approval.id ? "Working…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => resolveApproval(approval.id, "reject")}
                      disabled={busyApprovalId === approval.id}
                      className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-stone-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
              {queueLoading ? "Loading customer approval queue…" : "No pending customer-servicing approvals are currently visible in the branch queue."}
            </article>
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Active banking work queues"
        description="Recovered operations are anchored to current operator workflows and product surfaces so the page remains useful in static preview."
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="space-y-4">
            {pendingActions.slice(0, 6).map((action) => (
              <article key={action.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                      <Building2 size={18} />
                    </span>
                    <div>
                      <h3 className="text-base font-semibold text-stone-900">{action.title}</h3>
                      <p className="text-sm text-stone-500">{action.domainKey}</p>
                    </div>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(action.status)}`}>{action.status}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-stone-500">{action.detail}</p>
              </article>
            ))}
          </div>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <h3 className="text-lg font-semibold text-stone-900">Relevant product surfaces</h3>
            <p className="mt-2 text-sm leading-7 text-stone-500">Products currently exposed by the bank platform that align with the recovered banking-operations domain.</p>
            <div className="mt-4 space-y-3">
              {products.slice(0, 6).map((product) => (
                <div key={product.key} className="rounded-[1.1rem] bg-white px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-stone-900">{product.title}</p>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-stone-500">{product.summary}</p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </SectionCard>
    </AdminWorkspaceLayout>
  );
}

export function AdminAnalyticsPage() {
  const { products, exports, customers, services, loading, error } = useAdminData();

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered admin module"
      title="Analytics and platform intelligence"
      description="This page restores the extracted analytics view by combining product coverage, exports, customer mix, and service telemetry from the active platform."
      actions={
        <Link href="/admin/users" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          Review user access <ArrowRight size={16} />
        </Link>
      }
    >
      <SectionCard
        title="Administrative analytics snapshot"
        description="These indicators translate the extracted dashboard’s analytics intent into the current 54link-dev platform data model."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Products</p>
              <BadgeCheck className="h-5 w-5 text-emerald-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{products.length}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Customers</p>
              <Users className="h-5 w-5 text-sky-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{customers.length}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Export jobs</p>
              <Download className="h-5 w-5 text-violet-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{exports.length}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-500">Healthy services</p>
              <Activity className="h-5 w-5 text-amber-600" />
            </div>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{services.filter((service) => service.status === "healthy").length}</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="Exports and operational data products"
        description="Recovered analytics often converges on what the bank can export, audit, and operationalize."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            {exports.slice(0, 6).map((job) => (
              <article key={job.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-stone-900">{job.title}</h3>
                    <p className="text-sm text-stone-500">{job.domainKey} · {job.format.toUpperCase()}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(job.status)}`}>{job.status}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-stone-500">Created {formatRelativeIso(job.createdAt)} · {job.rowCount} rows · requested by {job.requestedByRole}</p>
              </article>
            ))}
            {!exports.length && (
              <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
                {loading ? "Loading export metrics…" : error ?? "No export activity is currently available."}
              </article>
            )}
          </div>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <h3 className="text-lg font-semibold text-stone-900">Product distribution</h3>
            <p className="mt-2 text-sm leading-7 text-stone-500">This is a live approximation of the extracted analytics surface using the product catalog already available in the active platform.</p>
            <div className="mt-4 space-y-3">
              {products.slice(0, 6).map((product) => (
                <div key={product.key} className="rounded-[1.1rem] bg-white px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-stone-900">{product.title}</p>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-stone-500">{product.summary}</p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </SectionCard>
    </AdminWorkspaceLayout>
  );
}

export function AdminUsersPage() {
  const { roles, customers, authContext, loading, error } = useAdminData();

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered admin module"
      title="Users and role administration"
      description="This page restores the extracted users module by combining the active authorization context with current role profiles and customer supervision records."
      actions={
        <Link href="/admin" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          Return to overview <ArrowRight size={16} />
        </Link>
      }
    >
      <SectionCard
        title="Authorization context"
        description="Recovered user management starts with who can currently see and operate the main-bank surface."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Issuer</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{authContext?.issuer ?? "54link-dev"}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Role</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{authContext?.role ?? "operations"}</p>
          </article>
          <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-stone-400">Visible domains</p>
            <p className="mt-2 text-xl font-semibold text-stone-900">{authContext?.visibleDomains?.length ?? 0}</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="Role profiles"
        description="The active platform’s authorization model becomes the backing store for the recovered admin users surface."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {roles.slice(0, 8).map((role) => (
            <article key={role.role} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                  <UserCog size={18} />
                </span>
                <div>
                  <h3 className="text-lg font-semibold text-stone-900">{role.title}</h3>
                  <p className="text-sm text-stone-500">{role.role}</p>
                </div>
              </div>
              <p className="mt-3 text-sm leading-7 text-stone-500">{role.description}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {role.permissions.slice(0, 5).map((capability) => (
                  <span key={capability} className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-stone-600">
                    {capability}
                  </span>
                ))}
              </div>
            </article>
          ))}
          {!roles.length && (
            <article className="lg:col-span-2 rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5 text-sm text-stone-500">
              {loading ? "Loading role administration…" : error ?? "No role profiles are currently available."}
            </article>
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Customer supervision visibility"
        description="Recovered user management also needs to show who is being supervised and serviced across the bank platform."
      >
        <div className="grid gap-4 xl:grid-cols-2">
          {customers.slice(0, 6).map((customer) => (
            <article key={customer.id} className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-stone-900 text-white">
                    <Users size={16} />
                  </span>
                  <div>
                    <h3 className="text-base font-semibold text-stone-900">{customer.name}</h3>
                    <p className="text-sm text-stone-500">{customer.segment}</p>
                  </div>
                </div>
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone(customer.status)}`}>{customer.status}</span>
              </div>
              <p className="mt-3 text-sm leading-6 text-stone-500">{customer.location}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">Relationship manager: {customer.relationshipManager}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </AdminWorkspaceLayout>
  );
}
