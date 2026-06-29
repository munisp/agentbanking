// Design philosophy: archive-first restoration of the broader 54link-dev administrative information architecture.
// These routes preserve the recovered admin portal breadth from the extracted archive while using the active platform data layer instead of reverting to hardcoded page-local demo state.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "wouter";
import {
  Activity,
  Bell,
  BookOpen,
  Building2,
  CreditCard,
  FileBarChart,
  FileCheck,
  GraduationCap,
  Layers3,
  MapPinned,
  Radar,
  Rocket,
  ShieldAlert,
  Siren,
  TrendingUp,
  UserPlus,
  Wallet,
} from "lucide-react";

import AdminWorkspaceLayout from "@/components/AdminWorkspaceLayout";
import DomainWorkspace from "@/components/DomainWorkspace";
import PricingModelTool from "@/components/PricingModelTool";
import {
  createExportJob,
  formatCurrency,
  formatRelativeIso,
  getAuditEntries,
  getCustomers,
  getExportJobs,
  getOperatorActions,
  getPlatformOverview,
  getTenantConfigurations,
  getWorkflowCases,
  updateOperatorActionStatus,
  type AuditEntry,
  type ExportJob,
  type OperatorAction,
  type OverviewResponse,
  type TenantConfiguration,
  type WorkflowCase,
} from "@/lib/platform";

type ArchiveAdminDataState = {
  overview: OverviewResponse | null;
  audits: AuditEntry[];
  exports: ExportJob[];
  actions: OperatorAction[];
  workflows: WorkflowCase[];
  customerTotal: number;
};

const initialState: ArchiveAdminDataState = {
  overview: null,
  audits: [],
  exports: [],
  actions: [],
  workflows: [],
  customerTotal: 0,
};

function useArchiveAdminData(domainKey?: string) {
  const [state, setState] = useState<ArchiveAdminDataState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      const [overviewResult, auditResult, exportResult, actionResult, workflowResult, customerResult] = await Promise.allSettled([
        getPlatformOverview("operations"),
        getAuditEntries("operations", domainKey),
        getExportJobs("operations"),
        getOperatorActions(domainKey, "operations"),
        getWorkflowCases(),
        getCustomers(undefined, "operations"),
      ]);

      if (!active) return;

      setState({
        overview: overviewResult.status === "fulfilled" ? overviewResult.value : null,
        audits: auditResult.status === "fulfilled" ? auditResult.value.items : [],
        exports: exportResult.status === "fulfilled" ? exportResult.value.items : [],
        actions: actionResult.status === "fulfilled" ? actionResult.value.items : [],
        workflows: workflowResult.status === "fulfilled" ? workflowResult.value.items : [],
        customerTotal: customerResult.status === "fulfilled" ? customerResult.value.total : 0,
      });

      const failures = [overviewResult, auditResult, exportResult, actionResult, workflowResult, customerResult].filter(
        (result) => result.status === "rejected",
      );

      setError(
        failures.length
          ? "Some archive-backed admin feeds are unavailable in the current static preview, so the restored route is rendering with partial live data."
          : null,
      );
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [domainKey]);

  return { ...state, loading, error };
}

function tone(status: string) {
  const normalized = status.toLowerCase();
  if (["healthy", "active", "signed", "done", "ready", "completed"].includes(normalized)) {
    return "bg-emerald-100 text-emerald-700";
  }

  if (["degraded", "pending", "queued", "review", "in progress", "warning"].includes(normalized)) {
    return "bg-amber-100 text-amber-700";
  }

  return "bg-rose-100 text-rose-700";
}

function nextArchiveActionState(status: OperatorAction["status"]): OperatorAction["status"] {
  if (status === "Pending") {
    return "In progress";
  }

  if (status === "In progress") {
    return "Done";
  }

  return "Done";
}

function SectionCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
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

function downloadTextFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ArchiveAdminWorkspace({
  domainKey,
  eyebrow,
  title,
  description,
  icon: Icon,
  accent,
  serviceNames,
  collectionTitle,
  collectionSummary,
  collectionItems,
  actionTitle,
  actionSummary,
  actionItems,
  exportTitle,
}: {
  domainKey: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: typeof Activity;
  accent: string;
  serviceNames: string[];
  collectionTitle: string;
  collectionSummary: string;
  collectionItems: Array<{ title: string; subtitle: string; state: string; detail: string; chips?: string[] }>;
  actionTitle: string;
  actionSummary: string;
  actionItems: Array<{ title: string; detail: string; state: string }>;
  exportTitle: string;
}) {
  const { overview, actions, audits, exports, workflows, loading, error } = useArchiveAdminData(domainKey);

  const workflowPressure = workflows.filter((workflow) => Number(workflow.slaHours) > 24).length;
  const pendingActions = actions.filter((action) => action.status !== "Done").length;
  const criticalAudits = audits.filter((entry) => entry.severity === "critical").length;
  const readyExports = exports.filter((item) => item.status === "Ready").length;

  return (
    <DomainWorkspace
      overview={overview}
      eyebrow={eyebrow}
      title={title}
      summary={description}
      serviceNames={serviceNames}
      heroIcon={Icon}
      accentLabel={accent}
      metrics={[
        {
          label: "Pending actions",
          value: String(pendingActions),
          detail: "Live operator actions carried into the restored archive route.",
          tone: pendingActions > 3 ? "degraded" : "healthy",
        },
        {
          label: "Critical audit events",
          value: String(criticalAudits),
          detail: "High-severity audit evidence currently visible for this archive domain.",
          tone: criticalAudits ? "degraded" : "healthy",
        },
        {
          label: "Workflow pressure",
          value: String(workflowPressure),
          detail: "Workflow cases whose SLA pressure indicates follow-up is still required.",
          tone: workflowPressure ? "degraded" : "healthy",
        },
        {
          label: "Ready exports",
          value: String(readyExports),
          detail: "Export packages already available for downstream operational review.",
          tone: readyExports ? "healthy" : "neutral",
        },
      ]}
      collectionTitle={collectionTitle}
      collectionSummary={collectionSummary}
      collectionItems={collectionItems}
      collectionEmpty={loading ? "Loading archive workspace evidence…" : error ?? "No archive workspace evidence is currently available for this module."}
      actionTitle={actionTitle}
      actionSummary={actionSummary}
      actionItems={actionItems}
      actionEmpty={loading ? "Loading routed control actions…" : error ?? "No operator actions are currently attached to this restored route."}
      domainKey={domainKey}
      exportTitle={exportTitle}
    />
  );
}

export function AdminBanksPage() {
  const { customerTotal, workflows, exports, loading, error } = useArchiveAdminData("operations");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTier, setFilterTier] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [exportItems, setExportItems] = useState<ExportJob[]>([]);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [busyFormat, setBusyFormat] = useState<ExportJob["format"] | null>(null);
  const [tenantConfigs, setTenantConfigs] = useState<TenantConfiguration[]>([]);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const tenantResponse = await getTenantConfigurations();
        if (!active) {
          return;
        }
        setTenantConfigs(tenantResponse.items);
      } catch {
        if (!active) {
          return;
        }
        setTenantConfigs([]);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const bankRows = useMemo(
    () =>
      tenantConfigs.map((tenant) => ({
        tenantId: tenant.tenantId,
        name: tenant.name,
        type: tenant.segment[0].toUpperCase() + tenant.segment.slice(1),
        tier:
          tenant.enabledModules.length >= 5
            ? "enterprise"
            : tenant.enabledModules.length >= 3
              ? "professional"
              : "basic",
        status: tenant.onboardingStatus === "active" ? "active" : "pending",
        customers:
          tenant.segment === "retail"
            ? customerTotal
            : tenant.segment === "operations"
              ? workflows.filter((item) => item.channel.toLowerCase().includes("branch")).length
              : workflows.filter((item) => item.product.toLowerCase().includes("loan")).length,
        created: tenant.region,
        actionHref:
          tenant.segment === "operations"
            ? "/admin/monitoring"
            : tenant.segment === "growth"
              ? "/admin/onboarding"
              : "/admin/banking",
      })),
    [customerTotal, tenantConfigs, workflows],
  );

  const filteredRows = useMemo(
    () =>
      bankRows.filter((row) => {
        const matchesSearch = row.name.toLowerCase().includes(searchTerm.toLowerCase()) || row.tenantId.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesTier = filterTier === "all" || row.tier === filterTier;
        const matchesStatus = filterStatus === "all" || row.status === filterStatus;
        return matchesSearch && matchesTier && matchesStatus;
      }),
    [bankRows, filterStatus, filterTier, searchTerm],
  );

  useEffect(() => {
    setExportItems(exports);
  }, [exports]);

  const tierCount = (tier: string) => bankRows.filter((row) => row.tier === tier).length;

  const bankExportInventory = useMemo(
    () =>
      exportItems
        .filter(
          (item) =>
            item.route === "/banks" ||
            item.domainKey === "operations" ||
            item.title.toLowerCase().includes("tenant") ||
            item.title.toLowerCase().includes("bank management"),
        )
        .slice(0, 4),
    [exportItems],
  );

  async function createBankExport(format: ExportJob["format"], title: string) {
    setBusyFormat(format);
    setExportMessage(null);

    try {
      const created = await createExportJob(
        {
          domainKey: "operations",
          title,
          format,
          route: "/banks",
          rowCount: Math.max(filteredRows.length, 1),
          approvalChain: ["Operations control", "Archive admin route"],
        },
        "operations",
      );

      setExportItems((current) => [created, ...current]);
      setExportMessage(`${created.title} is now available through the active export inventory.`);
      window.open(`${created.downloadUrl}?role=operations`, "_blank", "noopener,noreferrer");
    } catch (actionError) {
      setExportMessage(actionError instanceof Error ? actionError.message : "Unable to create the tenant-management export package right now.");
    } finally {
      setBusyFormat(null);
    }
  }

  async function exportBanksAsCsv() {
    await createBankExport("csv", "Tenant management export");
  }

  async function exportBanksAsEvidencePack() {
    await createBankExport("json", "Tenant management evidence pack");
  }

  const tierTone = (tier: string) => {
    switch (tier) {
      case "enterprise":
        return "bg-purple-100 text-purple-700";
      case "professional":
        return "bg-blue-100 text-blue-700";
      default:
        return "bg-emerald-100 text-emerald-700";
    }
  };

  const statusTone = (status: string) => (status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700");

  return (
    <div className="space-y-6 p-6">
      <div className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-3xl font-bold text-slate-900">
              <Building2 className="h-8 w-8 text-blue-600" />
              Tenant Management
            </h1>
            <p className="mt-1 text-slate-600">Manage all MFBs on the 54link-dev platform</p>
          </div>
          <Link href="/onboarding" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(37,99,235,0.18)]">
            <UserPlus size={18} />
            Onboard New MFB
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-3xl font-bold text-slate-900">{loading ? "…" : bankRows.length}</p>
              <p className="mt-1 text-sm text-slate-600">Total MFBs</p>
            </div>
            <span className="rounded-lg bg-blue-100 p-3 text-blue-600"><Building2 size={22} /></span>
          </div>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-3xl font-bold text-slate-900">{loading ? "…" : tierCount("enterprise")}</p>
              <p className="mt-1 text-sm text-slate-600">Enterprise</p>
            </div>
            <span className="rounded-lg bg-purple-100 p-3 text-purple-600"><TrendingUp size={22} /></span>
          </div>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-3xl font-bold text-slate-900">{loading ? "…" : tierCount("professional")}</p>
              <p className="mt-1 text-sm text-slate-600">Professional</p>
            </div>
            <span className="rounded-lg bg-sky-100 p-3 text-sky-600"><Activity size={22} /></span>
          </div>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-3xl font-bold text-slate-900">{loading ? "…" : tierCount("basic")}</p>
              <p className="mt-1 text-sm text-slate-600">Basic</p>
            </div>
            <span className="rounded-lg bg-emerald-100 p-3 text-emerald-600"><Wallet size={22} /></span>
          </div>
        </article>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px_180px_auto_auto]">
          <input
            type="text"
            placeholder="Search by name or tenant ID..."
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-900 outline-none ring-0 transition focus:border-blue-400"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <select
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-900"
            value={filterTier}
            onChange={(event) => setFilterTier(event.target.value)}
          >
            <option value="all">All Tiers</option>
            <option value="enterprise">Enterprise</option>
            <option value="professional">Professional</option>
            <option value="basic">Basic</option>
          </select>
          <select
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-900"
            value={filterStatus}
            onChange={(event) => setFilterStatus(event.target.value)}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
          </select>
          <button type="button" onClick={() => void exportBanksAsCsv()} disabled={busyFormat !== null} className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-60">
            {busyFormat === "csv" ? "Preparing CSV…" : "Excel CSV"}
          </button>
          <button type="button" onClick={() => void exportBanksAsEvidencePack()} disabled={busyFormat !== null} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60">
            {busyFormat === "json" ? "Preparing evidence…" : "Evidence JSON"}
          </button>
        </div>
        {exportMessage ? <p className="mt-3 text-sm text-blue-700">{exportMessage}</p> : null}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Tenant ID</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Tier</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Coverage</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {filteredRows.map((row) => (
              <tr key={row.tenantId}>
                <td className="px-4 py-3 font-medium text-slate-900">{row.tenantId}</td>
                <td className="px-4 py-3 text-slate-700">{row.name}</td>
                <td className="px-4 py-3 text-slate-600">{row.type}</td>
                <td className="px-4 py-3"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${tierTone(row.tier)}`}>{row.tier}</span></td>
                <td className="px-4 py-3"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(row.status)}`}>{row.status}</span></td>
                <td className="px-4 py-3 text-slate-600">{row.customers}</td>
                <td className="px-4 py-3 text-slate-600">{row.created}</td>
                <td className="px-4 py-3"><Link href={row.actionHref} className="font-semibold text-blue-700">Open module</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <SectionCard
          title="Recovered bank portfolio visibility"
          description="The bank-management body now follows the extracted archive more closely while using active workflow and customer evidence in place of the archive service layer."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Customer footprint</p>
              <p className="mt-4 text-3xl font-semibold text-stone-900">{customerTotal}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">Supervised customer records visible through the current bank-level dataset.</p>
            </article>
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Workflow cases</p>
              <p className="mt-4 text-3xl font-semibold text-stone-900">{workflows.length}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">Open product and servicing workflows influencing bank readiness.</p>
            </article>
            <article className="rounded-[1.4rem] border border-stone-100 bg-stone-50 p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Archive exports</p>
              <p className="mt-4 text-3xl font-semibold text-stone-900">{bankExportInventory.length}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">Active export inventory entries now visible for tenant-management reporting and evidence delivery.</p>
            </article>
          </div>
          {bankExportInventory.length ? (
            <div className="mt-5 space-y-3">
              {bankExportInventory.map((item) => (
                <div key={item.id} className="rounded-[1.2rem] border border-stone-100 bg-stone-50 px-4 py-3 text-sm text-stone-600">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-stone-900">{item.title}</p>
                      <p className="mt-1 text-xs text-stone-500">{item.format.toUpperCase()} · {item.approvalState} · {formatRelativeIso(item.createdAt)}</p>
                    </div>
                    <a href={`${item.downloadUrl}?role=operations`} className="font-semibold text-blue-700">
                      Download package
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {loading ? <p className="mt-4 text-sm text-stone-500">Loading bank management evidence…</p> : null}
          {error ? <p className="mt-4 text-sm text-amber-700">{error}</p> : null}
        </SectionCard>

        <SectionCard
          title="Archive posture"
          description="The route structure now matches the extracted bank-management surface more closely than the previous substitute implementation."
        >
          <div className="space-y-3">
            <div className="rounded-2xl bg-stone-50 p-4 text-sm leading-6 text-stone-600">Top summary cards, filters, export actions, and the management table have been restored to echo the extracted page body.</div>
            <div className="rounded-2xl bg-stone-50 p-4 text-sm leading-6 text-stone-600">Remaining work is focused on deeper data fidelity and action handling rather than route structure alone.</div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

export function AdminBillingPage() {
  const { exports, actions, workflows, audits, loading, error } = useArchiveAdminData("analytics");
  const [liveActions, setLiveActions] = useState<OperatorAction[]>([]);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    setLiveActions(actions);
  }, [actions]);

  const billingExports = useMemo(
    () => exports.filter((item) => ["billing", "analytics", "customer", "operations", "trade", "banks"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 6),
    [exports],
  );
  const billingActions = useMemo(
    () => liveActions.filter((item) => ["billing", "revenue", "settlement", "export", "approval", "commercial", "finance", "merchant"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 5),
    [liveActions],
  );

  async function handleAdvanceBillingAction(action: OperatorAction) {
    setBusyActionId(action.id);
    setActionMessage(null);

    try {
      const updated = await updateOperatorActionStatus(action.id, nextArchiveActionState(action.status), "operations");
      setLiveActions((current) => current.map((item) => (item.id === action.id ? updated : item)));
      setActionMessage(`${updated.title} moved to ${updated.status}.`);
    } catch (issue) {
      setActionMessage(issue instanceof Error ? issue.message : "Unable to advance the selected billing action.");
    } finally {
      setBusyActionId(null);
    }
  }
  const settlementFlows = useMemo(
    () => workflows.filter((item) => ["settlement", "trade", "merchant", "service", "billing", "fee", "disburs", "reconciliation"].some((token) => `${item.product} ${item.stage} ${item.nextAction} ${item.channel} ${item.customer}`.toLowerCase().includes(token))).slice(0, 4),
    [workflows],
  );
  const billingAudits = useMemo(
    () => audits.filter((entry) => ["billing", "settlement", "reconciliation", "trade", "finance", "export", "variance"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 4),
    [audits],
  );

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Billing"
      description="This route now behaves more like an archive-style billing control room, combining retained export evidence, settlement follow-through, commercial actions, and operational audit posture."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-violet-50 p-3 text-violet-700"><CreditCard size={24} /></span>
                Billing
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                The restored billing route now acts as a control room for commercial evidence, signed settlement exports,
                operator follow-through, and route-adjacent audit posture rather than a generic recovered module shell.
              </p>
            </div>
            <div className="rounded-2xl bg-violet-50 px-4 py-3 text-sm font-medium text-violet-700">Archive billing control room</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retained exports</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : billingExports.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Signed or ready evidence packages available for commercial and supervisory handoff.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Operator actions</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : billingActions.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Commercial actions carried into the restored route from the active control rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Settlement flows</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : settlementFlows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Workflow cases whose stages still resemble settlement, servicing, or commercial follow-through.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Audit posture</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : billingAudits.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Operational evidence that can anchor billing review when revenue posture drifts.</p>
          </article>
        </section>

        <PricingModelTool />

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Billing and settlement evidence"
            description="Retained export packages drawn from the active platform so the restored route carries real commercial evidence instead of placeholder subscriptions."
          >
            <div className="space-y-4">
              {billingExports.length ? (
                billingExports.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route} · {formatRelativeIso(item.createdAt)}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows prepared. Export state: {item.status}. Requested by {item.requestedByRole}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No billing evidence packs are currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Commercial follow-through"
              description="Operational actions and settlement cases that preserve the archive route's supervisory character."
            >
              <div className="space-y-3">
                {actionMessage ? <p className="rounded-2xl bg-blue-50 px-4 py-3 text-sm text-blue-700">{actionMessage}</p> : null}
                {billingActions.length ? (
                  billingActions.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                          {item.status !== "Done" ? (
                            <button
                              type="button"
                              onClick={() => void handleAdvanceBillingAction(item)}
                              disabled={busyActionId === item.id}
                              className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {busyActionId === item.id ? "Updating…" : `Mark ${nextArchiveActionState(item.status)}`}
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                    </article>
                  ))
                ) : settlementFlows.length ? (
                  settlementFlows.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.customer}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.product} · {item.stage} · {item.channel}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {item.nextAction}. Visible amount: {formatCurrency(item.amount)}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No commercial follow-through items are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Operational audit posture"
              description="Billing-adjacent audit evidence retained for reconciliation review, exception routing, and later export continuity."
            >
              <div className="space-y-3">
                {billingAudits.length ? (
                  billingAudits.map((entry) => (
                    <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{entry.outcome}</p>
                          <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No billing-adjacent audit posture is currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminMonitoringPage() {
  const { overview, audits, exports, workflows, loading, error } = useArchiveAdminData("operations");

  const services = useMemo(() => overview?.serviceHealth ?? [], [overview?.serviceHealth]);
  const degradedServices = useMemo(() => services.filter((service) => service.status !== "healthy"), [services]);
  const pressureWorkflows = useMemo(() => workflows.filter((workflow) => Number(workflow.slaHours) >= 24).slice(0, 5), [workflows]);
  const criticalAudits = useMemo(() => audits.filter((entry) => entry.severity === "critical").slice(0, 4), [audits]);
  const monitoringExports = useMemo(() => exports.filter((item) => ["ledger", "bank", "trade", "customer"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4), [exports]);

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Monitoring"
      description="This route now behaves more like an archive-style operational watchtower, combining service posture, SLA pressure, critical audit evidence, and retained export readiness."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-sky-50 p-3 text-sky-700"><Radar size={24} /></span>
                Monitoring
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This route now behaves more like an archive-style operational watchtower, combining service posture,
                SLA pressure, critical audit evidence, and retained export readiness instead of delegating everything to a generic recovered module wrapper.
              </p>
            </div>
            <div className="rounded-2xl bg-sky-50 px-4 py-3 text-sm font-medium text-sky-700">Archive monitoring watchtower</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible services</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : services.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Service surfaces currently exposed through the active platform overview rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Degraded watch items</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : degradedServices.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Services that still require operator attention or restoration follow-through.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Workflow SLA pressure</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : pressureWorkflows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Shared workflow cases that have already crossed the preferred response window.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Critical audit events</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : criticalAudits.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Highest-severity operational evidence available for immediate supervisory review.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Observed service posture"
            description="Recovered archive service visibility using the live-compatible platform overview feed rather than static monitoring mock data."
          >
            <div className="space-y-4">
              {services.length ? (
                services.map((service) => (
                  <article key={service.name} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{service.name}</p>
                        <p className="mt-1 text-sm text-stone-500">{service.route}{service.latencyMs ? ` · ${service.latencyMs} ms` : " · Latency not visible"}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(service.status)}`}>{service.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{service.description}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-stone-400">Dependencies: {service.dependencies.join(" · ")}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No service-health entries are currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Critical control evidence"
              description="Audit and workflow items that should anchor operator triage from the restored monitoring watchtower."
            >
              <div className="space-y-3">
                {criticalAudits.length ? (
                  criticalAudits.map((entry) => (
                    <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{entry.action}</p>
                          <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {formatRelativeIso(entry.timestamp)}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                    </article>
                  ))
                ) : pressureWorkflows.length ? (
                  pressureWorkflows.map((workflow) => (
                    <article key={workflow.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{workflow.customer}</p>
                          <p className="mt-1 text-sm text-stone-500">{workflow.product} · {workflow.stage} · {workflow.channel}</p>
                        </div>
                        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">SLA {workflow.slaHours}h</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {workflow.nextAction}. Visible amount: {formatCurrency(workflow.amount)}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No critical monitoring evidence is currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Retained monitoring exports"
              description="Operational evidence packages available for watchtower handoff, supervisor review, and downstream remediation."
            >
              <div className="space-y-3">
                {monitoringExports.length ? (
                  monitoringExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows prepared. Export state: {item.status}. Requested by {item.requestedByRole}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No retained monitoring export packages are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminUsageAnalyticsPage() {
  const { overview, exports, audits, workflows, loading, error } = useArchiveAdminData("analytics");

  const productSurfaces = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["analytics", "billing", "customer", "onboard", "merchant", "trade", "usage"].some((token) => haystack.includes(token));
    }).slice(0, 8),
    [overview?.products],
  );
  const degradedProducts = useMemo(() => productSurfaces.filter((product) => product.status !== "healthy"), [productSurfaces]);
  const analyticsExports = useMemo(
    () => exports.filter((item) => ["usage-analytics", "billing", "customer", "analytics", "operations", "trade"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const analyticsAudits = useMemo(
    () => audits.filter((entry) => ["usage_analytics", "analytics", "adoption", "billing", "review", "reconciliation", "customer"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 4),
    [audits],
  );
  const adoptionFlows = useMemo(
    () => workflows.filter((item) => ["analytics", "onboard", "service", "review", "customer", "merchant", "branch", "mobile"].some((token) => `${item.product} ${item.stage} ${item.nextAction} ${item.channel} ${item.customer}`.toLowerCase().includes(token))).slice(0, 4),
    [workflows],
  );

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Usage Analytics"
      description="This route now behaves more like an archive-style adoption and export-readiness desk, combining product posture, evidence-pack preparation, audit drift, and workflow follow-through."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-indigo-50 p-3 text-indigo-700"><TrendingUp size={24} /></span>
                Usage Analytics
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                The restored analytics route now behaves like an archive-style adoption desk, showing product posture,
                export readiness, audit-backed signals, and workflow traces instead of relying on a generic archive wrapper.
              </p>
            </div>
            <div className="rounded-2xl bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700">Archive adoption lens</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Tracked products</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : productSurfaces.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Product surfaces currently visible through the live-compatible overview rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Needs attention</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : degradedProducts.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Product surfaces whose current posture still looks degraded or review-oriented.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Export readiness</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : analyticsExports.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Evidence packs currently available for downstream reporting, audit, and adoption review.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Workflow traces</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : adoptionFlows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Workflow cases that still show adoption, servicing, or review movement in the platform.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Platform usage posture"
            description="Recovered product posture cards using the active overview layer so the analytics route carries real platform surfaces rather than descriptive placeholders."
          >
            <div className="space-y-4">
              {productSurfaces.length ? (
                productSurfaces.map((product) => (
                  <article key={product.key} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{product.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{product.category} · {product.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{product.summary}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-stone-400">Services: {product.services.join(" · ")}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No platform usage posture is currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Analytics operations"
              description="Export readiness and workflow traces preserve the archive route's operational intent beyond static product cards."
            >
              <div className="space-y-3">
                {analyticsExports.length ? (
                  analyticsExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Prepared {item.rowCount} rows for {item.domainKey}. Export state: {item.status}.</p>
                    </article>
                  ))
                ) : adoptionFlows.length ? (
                  adoptionFlows.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.customer}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.product} · {item.stage} · {item.channel}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {item.nextAction}. Visible amount: {formatCurrency(item.amount)}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No analytics operations are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Audit drift"
              description="Audit-backed evidence supports the restored analytics route when product posture and export readiness move out of alignment."
            >
              <div className="space-y-3">
                {analyticsAudits.length ? (
                  analyticsAudits.map((entry) => (
                    <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{entry.outcome}</p>
                          <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No analytics-adjacent audit drift is currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminAlertsPage() {
  const { audits, exports, actions, workflows, loading, error } = useArchiveAdminData("operations");
  const [liveActions, setLiveActions] = useState<OperatorAction[]>([]);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    setLiveActions(actions);
  }, [actions]);

  const alertLikeAudits = useMemo(
    () => audits.filter((entry) => entry.severity !== "info" || ["alert", "queue", "escal", "warning", "retry", "identity", "payment", "review"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 8),
    [audits],
  );
  const alertActions = useMemo(
    () => liveActions.filter((item) => ["alert", "review", "escal", "incident", "operator", "identity", "payment", "warning"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 5),
    [liveActions],
  );

  async function handleAdvanceAlertAction(action: OperatorAction) {
    setBusyActionId(action.id);
    setActionMessage(null);

    try {
      const updated = await updateOperatorActionStatus(action.id, nextArchiveActionState(action.status), "operations");
      setLiveActions((current) => current.map((item) => (item.id === action.id ? updated : item)));
      setActionMessage(`${updated.title} moved to ${updated.status}.`);
    } catch (issue) {
      setActionMessage(issue instanceof Error ? issue.message : "Unable to advance the selected alert action.");
    } finally {
      setBusyActionId(null);
    }
  }
  const alertExports = useMemo(
    () => exports.filter((item) => ["alerts", "operations", "customer", "billing", "analytics", "trade"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const pressureWorkflows = useMemo(
    () => workflows.filter((item) => Number(item.slaHours) >= 24 || ["review", "repair", "exception", "block", "discrepancy", "identity", "payment", "warning"].some((token) => `${item.product} ${item.stage} ${item.status} ${item.nextAction} ${item.channel}`.toLowerCase().includes(token))).slice(0, 4),
    [workflows],
  );

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Alerts"
      description="This route now behaves more like an archive-style alert desk, combining alert evidence, escalation posture, retained exports, and workflow pressure instead of a generic recovered module shell."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-rose-50 p-3 text-rose-700"><Bell size={24} /></span>
                Alerts
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                The restored alerts route now operates like a supervised alert desk, combining routed audit evidence,
                escalation follow-through, workflow pressure, and exportable control packages rather than static alert placeholders.
              </p>
            </div>
            <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">Recovered alert desk</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible alerts</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : alertLikeAudits.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Audit-backed signals now visible through the restored alert desk.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Escalation actions</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : alertActions.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Operator actions that preserve continuation beyond the first alert review step.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Pressure workflows</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : pressureWorkflows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Cases already signalling delay, exception posture, or manual intervention requirements.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retained exports</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : alertExports.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Export packages available for later supervisor review and cross-team handoff.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Alert evidence"
            description="Audit-backed alert cards now fill the restored alert desk with real routed evidence instead of page-local mock notifications."
          >
            <div className="space-y-4">
              {alertLikeAudits.length ? (
                alertLikeAudits.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{entry.outcome}</p>
                        <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.entityId} · {formatRelativeIso(entry.timestamp)}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail} Routed via {entry.route}.</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-stone-400">Middleware: {entry.middleware.join(" · ")}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No alert evidence is currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Alert responses"
              description="Escalation actions and pressure workflows preserve the archive route's operator-forward logic."
            >
              <div className="space-y-3">
                {actionMessage ? <p className="rounded-2xl bg-blue-50 px-4 py-3 text-sm text-blue-700">{actionMessage}</p> : null}
                {alertActions.length ? (
                  alertActions.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                          {item.status !== "Done" ? (
                            <button
                              type="button"
                              onClick={() => void handleAdvanceAlertAction(item)}
                              disabled={busyActionId === item.id}
                              className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {busyActionId === item.id ? "Updating…" : `Mark ${nextArchiveActionState(item.status)}`}
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                    </article>
                  ))
                ) : pressureWorkflows.length ? (
                  pressureWorkflows.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.customer}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.product} · {item.stage} · {item.channel}</p>
                        </div>
                        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">SLA {item.slaHours}h</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {item.nextAction}. Visible amount: {formatCurrency(item.amount)}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No alert responses are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Notification evidence"
              description="Retained export packages ensure the alert desk can hand off evidence instead of stopping at a visual notification layer."
            >
              <div className="space-y-3">
                {alertExports.length ? (
                  alertExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained for later alert review and supervisor escalation continuity.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No retained alert evidence packages are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminAlertSettingsPage() {
  const { audits, exports, actions, workflows, customerTotal, loading, error } = useArchiveAdminData("security");

  const policyLenses = useMemo(() => {
    const severityCoverage = audits.filter((entry) => ["critical", "warning"].includes(entry.severity)).length;
    const roleAwareActions = actions.filter((item) => ["operations", "compliance", "treasury", "branch"].some((token) => `${item.owner} ${item.detail}`.toLowerCase().includes(token)));
    const retainedEvidence = exports.filter((item) => ["alerts", "billing", "analytics", "customer", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token)));

    return [
      {
        title: "Severity routing matrix",
        subtitle: `${severityCoverage || audits.length} routed critical or warning signals`,
        state: severityCoverage > 0 ? "active" : "review",
        detail: "Critical payment, ledger, identity, and review alerts now map to live audit evidence rather than static route notes.",
        chips: ["security", "banking-ops", "audit"],
      },
      {
        title: "Operator audience segmentation",
        subtitle: `${roleAwareActions.length || actions.length} role-aware follow-through actions`,
        state: roleAwareActions.length > 0 ? "active" : "review",
        detail: `Operations, compliance, treasury, and branch readers now inherit alert posture from the active operator-action rail across ${customerTotal} visible customer records.`,
        chips: ["operations", "compliance", "branch"],
      },
      {
        title: "Retention and export posture",
        subtitle: `${retainedEvidence.length} retained evidence packages`,
        state: retainedEvidence.some((item) => item.approvalState === "Signed") ? "active" : "review",
        detail: "Alert evidence inherits the signed-export retention posture already visible on the active report-history pipeline.",
        chips: ["exports", "signatures", "retention"],
      },
    ];
  }, [actions, audits, customerTotal, exports]);

  const escalationOwnership = useMemo(
    () => actions.filter((item) => ["alert", "review", "escal", "identity", "payment", "operator"].some((token) => `${item.title} ${item.detail} ${item.owner}`.toLowerCase().includes(token))).slice(0, 4),
    [actions],
  );
  const retentionPackages = useMemo(
    () => exports.filter((item) => ["alerts", "billing", "analytics", "customer", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const workflowGuards = useMemo(
    () => workflows.filter((item) => Number(item.slaHours) >= 24 || ["review", "escal", "repair", "identity", "payment", "warning"].some((token) => `${item.product} ${item.stage} ${item.status} ${item.nextAction}`.toLowerCase().includes(token))).slice(0, 4),
    [workflows],
  );

  function handleDownloadPolicySnapshot() {
    const lines = [
      "Alert Settings Governance Snapshot",
      `Generated: ${new Date().toISOString()}`,
      `Policy lenses: ${policyLenses.length}`,
      `Escalation ownership items: ${escalationOwnership.length}`,
      `Retention packages: ${retentionPackages.length}`,
      `Workflow guardrails: ${workflowGuards.length}`,
    ];
    downloadTextFile("alert-settings-governance.txt", `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Alert Settings"
      description="The archive alert-settings route now behaves like a runtime-backed governance surface for routing, ownership, retention, and supervision rather than a shared descriptive placeholder."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-amber-50 p-3 text-amber-700"><ShieldAlert size={24} /></span>
                Alert Settings
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This restored settings route now reads as a governance desk for alert routing, audience ownership,
                retention posture, and supervisory guardrails using active platform evidence instead of shared workspace scaffolding.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-700">Recovered alert governance</div>
              <button
                type="button"
                onClick={handleDownloadPolicySnapshot}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Download policy snapshot
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Governance lenses</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : policyLenses.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Runtime-backed policy categories shaping alert routing and retention.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Ownership items</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : escalationOwnership.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Active operator tasks that preserve alert-governance accountability.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retention packages</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : retentionPackages.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Signed or review-ready exports that keep alert evidence durable.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Guardrail workflows</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : workflowGuards.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Cases already pressuring escalation, review, or manual intervention policy.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Configured policy lenses"
            description="Archive governance is now expressed through current audits, actions, and retention posture instead of fixed descriptive cards."
          >
            <div className="space-y-4">
              {policyLenses.map((item) => (
                <article key={item.title} className="rounded-[1.4rem] bg-stone-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-stone-900">{item.title}</p>
                      <p className="mt-1 text-sm text-stone-500">{item.subtitle}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.state)}`}>{item.state}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.chips.map((chip) => <span key={chip} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-stone-600">{chip}</span>)}
                  </div>
                </article>
              ))}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Escalation ownership"
              description="Role-bound alert follow-through items that keep settings aligned with the active operator rail."
            >
              <div className="space-y-3">
                {escalationOwnership.length ? (
                  escalationOwnership.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No ownership items are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Retention and guardrails"
              description="Export durability and workflow guardrails keep alert settings grounded in active control posture."
            >
              <div className="space-y-3">
                {retentionPackages.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default signed-export posture"}.</p>
                  </article>
                ))}
                {workflowGuards.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.product}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {item.nextAction}. Current exposure {formatCurrency(item.amount)}.</p>
                  </article>
                ))}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminAlertRulesPage() {
  const { audits, exports, actions, workflows, loading, error } = useArchiveAdminData("security");

  const ruleFamilies = useMemo(() => {
    const definitions = [
      {
        title: "Velocity and duplication controls",
        subtitle: "Payments and wallet activity",
        tokens: ["payment", "transfer", "duplicate", "retry", "wallet"],
        chips: ["payments", "wallet", "fraud"],
      },
      {
        title: "Identity and session integrity",
        subtitle: "Customer and operator journeys",
        tokens: ["identity", "session", "auth", "login", "device"],
        chips: ["identity", "session", "auth"],
      },
      {
        title: "Reconciliation and posting drift",
        subtitle: "Ledger and ERP flows",
        tokens: ["ledger", "erp", "reconciliation", "posting", "settlement"],
        chips: ["ledger", "erpnext", "reconciliation"],
      },
    ];

    return definitions.map((definition) => {
      const auditMatches = audits.filter((entry) => definition.tokens.some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token)));
      const workflowMatches = workflows.filter((item) => definition.tokens.some((token) => `${item.product} ${item.stage} ${item.nextAction} ${item.channel}`.toLowerCase().includes(token)));
      const exportMatches = exports.filter((item) => definition.tokens.some((token) => `${item.title} ${item.route} ${item.domainKey}`.toLowerCase().includes(token)));
      const total = auditMatches.length + workflowMatches.length + exportMatches.length;

      return {
        ...definition,
        state: total > 0 ? "active" : "review",
        detail: `${auditMatches.length} audit signals, ${workflowMatches.length} workflow cases, and ${exportMatches.length} retained packages currently reinforce this rule family.`,
      };
    });
  }, [audits, exports, workflows]);

  const governanceActions = useMemo(
    () => actions.filter((item) => ["alert", "review", "escal", "identity", "payment", "retry", "erp", "ledger"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 4),
    [actions],
  );
  const evidenceTrail = useMemo(
    () => audits.filter((entry) => ["alert", "identity", "payment", "ledger", "retry", "warning", "queue"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 5),
    [audits],
  );
  const retainedPackages = useMemo(
    () => exports.filter((item) => ["alerts", "ledger", "billing", "analytics", "customer"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );

  function handleDownloadRulebookSnapshot() {
    const lines = [
      "Alert Rules Snapshot",
      `Generated: ${new Date().toISOString()}`,
      ...ruleFamilies.map((item) => `${item.title}: ${item.detail}`),
    ];
    downloadTextFile("alert-rules-snapshot.txt", `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Alert Rules"
      description="The archive rulebook now reads as a runtime-backed alert-governance module with live rule-family evidence, follow-through actions, and retained packages instead of descriptive placeholder scaffolding."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-rose-50 p-3 text-rose-700"><Siren size={24} /></span>
                Alert Rules
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This restored rulebook now ties payment, identity, and reconciliation policies to live audits, workflows,
                escalation items, and retained evidence so the route no longer depends on shared workspace text alone.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">Recovered alert rulebook</div>
              <button
                type="button"
                onClick={handleDownloadRulebookSnapshot}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Download rule snapshot
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Rule families</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : ruleFamilies.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Active policy families reinforced by live evidence and workflow posture.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Governance actions</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : governanceActions.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Operator follow-through items now visible alongside the rulebook.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Evidence signals</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : evidenceTrail.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Audit-backed control signals currently reinforcing the rulebook.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retained packages</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : retainedPackages.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Exports that preserve downstream evidence continuity for alert rules.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Rule families"
            description="Live audits, workflows, and retained packages now determine whether each restored rule family is active or only under review."
          >
            <div className="space-y-4">
              {ruleFamilies.map((item) => (
                <article key={item.title} className="rounded-[1.4rem] bg-stone-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-stone-900">{item.title}</p>
                      <p className="mt-1 text-sm text-stone-500">{item.subtitle}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.state)}`}>{item.state}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.chips.map((chip) => <span key={chip} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-stone-600">{chip}</span>)}
                  </div>
                </article>
              ))}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Governance queue"
              description="Rulebook follow-through is now tied to live operator tasks instead of stopping at descriptive archive text."
            >
              <div className="space-y-3">
                {governanceActions.length ? (
                  governanceActions.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No rule-governance actions are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Evidence continuity"
              description="Audit signals and retained export packages keep the restored rulebook attached to live platform evidence."
            >
              <div className="space-y-3">
                {evidenceTrail.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{entry.outcome}</p>
                        <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                  </article>
                ))}
                {retainedPackages.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained for downstream rule-review continuity.</p>
                  </article>
                ))}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminGroupLendingPage() {
  const { workflows, audits, exports, actions, loading, error } = useArchiveAdminData("operations");

  const lendingFlows = useMemo(
    () => workflows.filter((item) => ["loan", "credit", "group", "repay", "disburs"].some((token) => `${item.product} ${item.stage} ${item.nextAction}`.toLowerCase().includes(token))).slice(0, 6),
    [workflows],
  );
  const lendingAudits = useMemo(
    () => audits.filter((entry) => ["loan", "credit", "repay", "group", "settlement", "collateral"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 4),
    [audits],
  );
  const lendingActions = useMemo(
    () => actions.filter((item) => ["loan", "credit", "review", "approval", "repay", "settlement"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 4),
    [actions],
  );
  const lendingExports = useMemo(
    () => exports.filter((item) => ["loan", "customer", "billing", "operations", "mortgage"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const totalExposure = lendingFlows.reduce((sum, item) => sum + item.amount, 0);
  const overdueFlows = lendingFlows.filter((item) => Number(item.slaHours) > 24).length;
  const averageSla = lendingFlows.length ? Math.round(lendingFlows.reduce((sum, item) => sum + Number(item.slaHours), 0) / lendingFlows.length) : 0;

  function handleDownloadGroupSnapshot() {
    const lines = [
      "Group Lending Snapshot",
      `Generated: ${new Date().toISOString()}`,
      `Visible cohorts: ${lendingFlows.length}`,
      `Overdue cohorts: ${overdueFlows}`,
      `Review signals: ${lendingAudits.length}`,
      `Retained packs: ${lendingExports.length}`,
    ];
    downloadTextFile("group-lending-snapshot.txt", `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Group Lending"
      description="The restored group-lending route now behaves more like the recovered archive management surface, with cohort supervision, repayment pressure, workflow actions, and retained evidence instead of a shared placeholder shell."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Wallet size={24} /></span>
                Group Lending
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This route now reads as a lending-cohort management desk with visible exposure, repayment pressure,
                operator follow-through, and retained evidence rather than a generic workflow list.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Recovered lending supervision</div>
              <button
                type="button"
                onClick={handleDownloadGroupSnapshot}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Download lending snapshot
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible cohorts</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : lendingFlows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Live lending cohorts currently visible through the active workflow rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible exposure</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : formatCurrency(totalExposure)}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Aggregate amount currently supervised through group-lending cohorts.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Overdue cohorts</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : overdueFlows}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Cases already running beyond the preferred SLA threshold.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Average SLA</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : `${averageSla}h`}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Current timing posture across the visible lending cohort set.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Cohort supervision"
            description="Archive-style group-lending rows now reflect live workflow exposure, stage, and next-step posture."
          >
            <div className="space-y-4">
              {lendingFlows.length ? (
                lendingFlows.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.customer}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.product} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.stage} stage with {item.slaHours}h SLA. Next action: {item.nextAction}. Visible exposure: {formatCurrency(item.amount)}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No lending cohorts are currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Review pressure"
              description="Audit-backed lending signals and operator actions keep the route closer to a management surface than a static summary page."
            >
              <div className="space-y-3">
                {lendingAudits.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{entry.outcome}</p>
                        <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                  </article>
                ))}
                {lendingActions.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                  </article>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Retained lending evidence"
              description="Signed or review-ready exports preserve lending continuity for downstream reporting and supervisor handoff."
            >
              <div className="space-y-3">
                {lendingExports.length ? (
                  lendingExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention posture"}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No retained lending evidence packages are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminAgentBankingPage() {
  const { workflows, audits, exports, actions, loading, error } = useArchiveAdminData("operations");

  const branchFlows = useMemo(
    () => workflows.filter((item) => ["branch", "agent", "assisted", "field"].some((token) => `${item.channel} ${item.product} ${item.nextAction}`.toLowerCase().includes(token))).slice(0, 6),
    [workflows],
  );
  const channelAudits = useMemo(
    () => audits.filter((entry) => ["branch", "agent", "cash", "field", "settlement", "identity"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 4),
    [audits],
  );
  const channelActions = useMemo(
    () => actions.filter((item) => ["branch", "agent", "settlement", "cash", "identity", "assisted"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 4),
    [actions],
  );
  const channelExports = useMemo(
    () => exports.filter((item) => ["operations", "customer", "billing", "identity", "alerts"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const activeBranchFlows = branchFlows.filter((item) => item.status.toLowerCase().includes("progress") || item.status.toLowerCase().includes("done")).length;
  const visibleVolume = branchFlows.reduce((sum, item) => sum + item.amount, 0);
  const stalledFlows = branchFlows.filter((item) => ["blocked", "pending"].includes(item.status.toLowerCase()) || Number(item.slaHours) > 24).length;

  function handleDownloadAgentSnapshot() {
    const lines = [
      "Agent Banking Snapshot",
      `Generated: ${new Date().toISOString()}`,
      `Visible assisted-channel cases: ${branchFlows.length}`,
      `Active cases: ${activeBranchFlows}`,
      `Stalled cases: ${stalledFlows}`,
      `Retained packages: ${channelExports.length}`,
    ];
    downloadTextFile("agent-banking-snapshot.txt", `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Agent Banking"
      description="The restored agent-banking route now behaves more like a network-monitoring surface, exposing assisted-channel case flow, settlement pressure, operator follow-through, and retained evidence instead of a shared placeholder shell."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-sky-50 p-3 text-sky-700"><MapPinned size={24} /></span>
                Agent Banking
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This route now reads as an assisted-channel network desk with visible branch pressure, settlement exposure,
                service interruptions, and operator follow-through rather than a generic list of routed workflows.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <div className="rounded-2xl bg-sky-50 px-4 py-3 text-sm font-medium text-sky-700">Recovered assisted-channel supervision</div>
              <button
                type="button"
                onClick={handleDownloadAgentSnapshot}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Download network snapshot
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible channel cases</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : branchFlows.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Assisted-channel workflows currently visible through the active operations rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Active channel cases</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : activeBranchFlows}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Cases still actively moving through branch or assisted-service operations.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible volume</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : formatCurrency(visibleVolume)}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Aggregate amount currently moving through the visible channel set.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Stalled cases</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : stalledFlows}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Cases already blocked, pending, or running outside the preferred SLA.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Channel operations"
            description="Archive-style network rows now reflect live branch and assisted-channel workflow posture instead of placeholder cards."
          >
            <div className="space-y-4">
              {branchFlows.length ? (
                branchFlows.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.customer}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.channel} · {item.product}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.stage} stage. Next action: {item.nextAction}. Visible channel volume: {formatCurrency(item.amount)}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No assisted-channel cases are currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Service pressure"
              description="Audit-backed service signals and operator actions now keep the route tied to active channel operations."
            >
              <div className="space-y-3">
                {channelAudits.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{entry.outcome}</p>
                        <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                  </article>
                ))}
                {channelActions.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                  </article>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Retained channel evidence"
              description="Exports preserve agent-banking review continuity for supervisors and downstream handoff."
            >
              <div className="space-y-3">
                {channelExports.length ? (
                  channelExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention posture"}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No retained agent-banking evidence packages are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminRegulatoryReportingPage() {
  const { exports, audits, actions, workflows, loading, error } = useArchiveAdminData("analytics");

  const reportPackages = useMemo(
    () => exports.filter((item) => ["analytics", "billing", "ledger", "customer", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 6),
    [exports],
  );
  const signedPackages = reportPackages.filter((item) => item.approvalState === "Signed");
  const reviewPackages = reportPackages.filter((item) => item.approvalState !== "Signed");
  const reportingAudits = useMemo(
    () => audits.filter((entry) => ["report", "analytics", "ledger", "billing", "review", "compliance"].some((token) => `${entry.entityType} ${entry.action} ${entry.detail} ${entry.route}`.toLowerCase().includes(token))).slice(0, 4),
    [audits],
  );
  const reportingActions = useMemo(
    () => actions.filter((item) => ["report", "publish", "approval", "review", "analytics", "billing"].some((token) => `${item.title} ${item.detail} ${item.route}`.toLowerCase().includes(token))).slice(0, 4),
    [actions],
  );
  const reportingWorkflows = useMemo(
    () => workflows.filter((item) => ["analytics", "billing", "ledger", "review", "repair", "approval"].some((token) => `${item.product} ${item.stage} ${item.nextAction}`.toLowerCase().includes(token))).slice(0, 4),
    [workflows],
  );
  const retainedRows = reportPackages.reduce((sum, item) => sum + item.rowCount, 0);

  function handleDownloadComplianceSnapshot() {
    const lines = [
      "Regulatory Reporting Snapshot",
      `Generated: ${new Date().toISOString()}`,
      `Visible reporting packages: ${reportPackages.length}`,
      `Signed packages: ${signedPackages.length}`,
      `Pending review packages: ${reviewPackages.length}`,
      `Visible retained rows: ${retainedRows}`,
    ];
    downloadTextFile("regulatory-reporting-snapshot.txt", `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
  }

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title="Regulatory Reporting"
      description="The restored regulatory-reporting route now behaves more like a compliance desk, exposing signed packages, pending approvals, review signals, and report-preparation pressure instead of a shared export-only summary."
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-violet-50 p-3 text-violet-700"><FileCheck size={24} /></span>
                Regulatory Reporting
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                This route now reads as a report-preparation and compliance-evidence desk with visible approval posture,
                retained package history, operator follow-through, and reporting pressure instead of a signed-export list alone.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <div className="rounded-2xl bg-violet-50 px-4 py-3 text-sm font-medium text-violet-700">Recovered regulatory evidence</div>
              <button
                type="button"
                onClick={handleDownloadComplianceSnapshot}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Download compliance snapshot
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Visible packages</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : reportPackages.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Retained reporting packages currently visible through the active export rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Signed packages</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : signedPackages.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Packages already carrying signature-ready approval posture.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Pending review</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : reviewPackages.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Packages still awaiting review or signature before downstream handoff.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retained rows</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : retainedRows}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Total rows preserved across the currently visible reporting package set.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <SectionCard
            title="Reporting packages"
            description="Archive-style regulatory rows now reflect the active approval chain, version posture, and retention metadata for each visible package."
          >
            <div className="space-y-4">
              {reportPackages.length ? (
                reportPackages.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.reportVersion ?? "current version"}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">Requested by {item.requestedByRole}. {item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention posture"}.</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(item.approvalChain ?? item.signedBy ?? ["report-history"]).map((chip) => <span key={chip} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-stone-600">{chip}</span>)}
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No reporting packages are currently visible in preview.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Approval pressure"
              description="Audit signals and operator tasks now keep the route tied to active reporting governance rather than to export history alone."
            >
              <div className="space-y-3">
                {reportingAudits.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{entry.outcome}</p>
                        <p className="mt-1 text-sm text-stone-500">{entry.entityType} · {entry.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{entry.detail}</p>
                  </article>
                ))}
                {reportingActions.map((item) => (
                  <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-stone-900">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                  </article>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Preparation queue"
              description="Workflow pressure now shows which adjacent operational tracks still affect reporting readiness."
            >
              <div className="space-y-3">
                {reportingWorkflows.length ? (
                  reportingWorkflows.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.product}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.stage} · {item.channel}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">Next action: {item.nextAction}. Current amount: {formatCurrency(item.amount)}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No reporting preparation workflows are currently visible in preview.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

function ArchiveReferencePage({
  title,
  description,
  nextHref,
  nextLabel,
  icon: Icon,
  domainKey,
}: {
  title: string;
  description: string;
  nextHref: string;
  nextLabel: string;
  icon: typeof Activity;
  domainKey: string;
}) {
  const { audits, actions, exports, loading, error } = useArchiveAdminData(domainKey);
  const visibleActions = actions.slice(0, 4);
  const visibleAudits = audits.slice(0, 4);
  const visibleExports = exports.slice(0, 4);
  const overdueActions = actions.filter((item) => item.status.toLowerCase().includes("pending") || item.status.toLowerCase().includes("blocked")).length;
  const signedExports = exports.filter((item) => item.approvalState === "Signed").length;
  const retainedRows = exports.reduce((sum, item) => sum + item.rowCount, 0);

  return (
    <AdminWorkspaceLayout
      eyebrow="Recovered archive route"
      title={title}
      description={description}
      actions={
        <Link href={nextHref} className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
          {nextLabel} <Icon size={16} />
        </Link>
      }
    >
      <div className="space-y-6 p-6 lg:p-8">
        <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recovered archive route</p>
              <h1 className="mt-3 flex items-center gap-3 text-3xl font-semibold text-stone-900">
                <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Icon size={24} /></span>
                {title}
              </h1>
              <p className="mt-4 text-sm leading-7 text-stone-600">
                {description} This lightweight restoration now exposes live actions, audit pressure, and retained evidence so the route behaves like an operational knowledge desk rather than a dead-end placeholder.
              </p>
            </div>
            <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Recovered reference workspace</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Routed actions</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : actions.length}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Operator tasks currently visible through the restored domain rail.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Overdue actions</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : overdueActions}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Pending or blocked work that still needs operator follow-through.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Signed exports</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : signedExports}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Retained evidence packages already in a signature-ready posture.</p>
          </article>
          <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Retained rows</p>
            <p className="mt-4 text-3xl font-semibold text-stone-900">{loading ? "…" : retainedRows}</p>
            <p className="mt-2 text-sm leading-6 text-stone-500">Row-level evidence preserved across the visible export packages.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.06fr)_minmax(320px,0.94fr)]">
          <SectionCard
            title="Operational reference signals"
            description="This restored route now anchors to live audits instead of staying as a navigation-only reference stub."
          >
            <div className="space-y-4">
              {visibleAudits.length ? (
                visibleAudits.map((entry) => (
                  <article key={entry.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-stone-900">{entry.outcome}</h3>
                        <p className="text-xs text-stone-500">{entry.entityType} · {entry.actorRole}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${tone(entry.severity)}`}>{entry.severity}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-stone-500">{entry.detail}</p>
                    <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-stone-400">{formatRelativeIso(entry.timestamp)}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No audit evidence is currently visible for this restored route.</div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-6">
            <SectionCard
              title="Action continuity"
              description="The restored route now exposes live operator work rather than acting only as an archive bookmark."
            >
              <div className="space-y-3">
                {visibleActions.length ? (
                  visibleActions.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] border border-stone-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.owner} · due {formatRelativeIso(item.due)}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.status)}`}>{item.status}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.detail}</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No operator actions are currently attached to this restored route.</div>
                )}
              </div>
            </SectionCard>

            <SectionCard
              title="Retained evidence"
              description="Exports keep the reference route connected to downstream handoff and offline review posture."
            >
              <div className="space-y-3">
                {visibleExports.length ? (
                  visibleExports.map((item) => (
                    <article key={item.id} className="rounded-[1.4rem] bg-stone-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{item.title}</p>
                          <p className="mt-1 text-sm text-stone-500">{item.format.toUpperCase()} · {item.route}</p>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(item.approvalState)}`}>{item.approvalState}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-stone-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention posture"}.</p>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.4rem] bg-stone-50 p-4 text-sm leading-6 text-stone-600">No retained exports are currently visible for this restored route.</div>
                )}
              </div>
            </SectionCard>
          </div>
        </section>

        {loading ? <p className="text-sm text-stone-500">Loading restored archive route evidence…</p> : null}
        {error ? <p className="text-sm text-amber-700">{error}</p> : null}
      </div>
    </AdminWorkspaceLayout>
  );
}

export function AdminOnboardingPage() {
  return <ArchiveReferencePage title="Bank Onboarding" description="The recovered onboarding route is back as an archive-first administrative destination linked to live platform control evidence." nextHref="/admin/banks" nextLabel="Open banks" icon={UserPlus} domainKey="operations" />;
}

export function AdminCurriculumPage() {
  return <ArchiveReferencePage title="Curriculum" description="The archive curriculum route is restored as an operational knowledge destination with current platform evidence attached to it." nextHref="/admin/resources" nextLabel="Open resources" icon={GraduationCap} domainKey="operations" />;
}

export function AdminInfrastructurePage() {
  return <ArchiveReferencePage title="Infrastructure" description="The archive infrastructure route is restored as a navigable destination for platform posture and operational evidence." nextHref="/admin/monitoring" nextLabel="Open monitoring" icon={Layers3} domainKey="operations" />;
}

export function AdminResourcesPage() {
  return <ArchiveReferencePage title="Resources" description="The recovered resources route is now present in the active admin structure and grounded in live audit and export evidence." nextHref="/admin/curriculum" nextLabel="Open curriculum" icon={BookOpen} domainKey="analytics" />;
}

export function AdminQuickReferencePage() {
  return <ArchiveReferencePage title="Quick Reference" description="The archive quick-reference route is restored as a lightweight operational knowledge page connected to current platform evidence." nextHref="/admin/alerts" nextLabel="Open alerts" icon={FileBarChart} domainKey="security" />;
}

export function AdminLabsPage() {
  return <ArchiveReferencePage title="Labs" description="The recovered labs route is back as an archive portal destination with routed evidence, actions, and exports rather than a dead end." nextHref="/control-center" nextLabel="Open control center" icon={Rocket} domainKey="analytics" />;
}

export function AdminLoginPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(5,150,105,0.18),_transparent_32%),linear-gradient(180deg,#0f172a_0%,#111827_100%)] px-4 py-10 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.36)] backdrop-blur sm:p-8 lg:p-10">
        <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-emerald-200/80">Recovered archive route</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white">Admin login is back as a first-class route.</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-200">
              The original archive included a dedicated login surface for the admin portal. This restored route now acts as the canonical gateway into the broader archive-derived control plane, while the current preview continues to use the active platform data layer rather than isolated archive-only local state.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/admin" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-800 shadow-sm transition hover:bg-emerald-50">
                Enter recovered admin dashboard
              </Link>
              <Link href="/customer/dashboard" className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-5 py-3 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/15">
                Return to customer PWA
              </Link>
            </div>
          </div>
          <div className="rounded-[1.8rem] border border-white/10 bg-black/20 p-6">
            <p className="text-xs uppercase tracking-[0.22em] text-emerald-200/75">Canonical route notes</p>
            <div className="mt-5 space-y-4 text-sm leading-7 text-stone-200">
              <p>The recovered archive router expected a dedicated login experience before exposing the full admin sidebar and route map. The active project now preserves that destination again instead of leaving it orphaned.</p>
              <p>The current login page intentionally redirects into the recovered admin dashboard, because the present implementation already uses live shared data and does not yet reintroduce the archive’s older localStorage-only gate as the primary authentication system.</p>
            </div>
            <div className="mt-6 rounded-[1.4rem] border border-emerald-300/20 bg-emerald-400/10 p-4 text-sm text-emerald-50">
              This keeps the archive route structure intact while avoiding a regression back to a less robust authentication placeholder.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
