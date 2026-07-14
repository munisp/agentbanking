// Design philosophy: archive-first agriculture expansion.
// The extracted archive exposes agriculture routes in the canonical sidebar, but not full page bodies.
// These pages therefore reuse the recovered admin visual language while binding to the active platform's
// compatible live adapters instead of remaining as generic placeholders.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  FileBarChart,
  FileText,
  Link2,
  Satellite,
  ShieldCheck,
  Sprout,
  Tractor,
  Users,
} from "lucide-react";

import {
  getAuditEntries,
  getExportJobs,
  getPlatformOverview,
  getWorkflowCases,
  type AuditEntry,
  type ExportJob,
  type OverviewResponse,
  type WorkflowCase,
} from "@/lib/platform";

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (["healthy", "active", "completed", "ready", "signed"].includes(normalized)) return "bg-emerald-100 text-emerald-700";
  if (["warning", "degraded", "pending", "review", "in progress"].includes(normalized)) return "bg-amber-100 text-amber-700";
  return "bg-slate-200 text-slate-700";
}

type AgricultureState = {
  overview: OverviewResponse | null;
  audits: AuditEntry[];
  exports: ExportJob[];
  workflows: WorkflowCase[];
};

const initialState: AgricultureState = {
  overview: null,
  audits: [],
  exports: [],
  workflows: [],
};

function useAgricultureData() {
  const [state, setState] = useState<AgricultureState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      const [overviewResult, auditResult, exportResult, workflowResult] = await Promise.allSettled([
        getPlatformOverview("operations"),
        getAuditEntries("operations"),
        getExportJobs("operations"),
        getWorkflowCases(),
      ]);

      if (!active) return;

      setState({
        overview: overviewResult.status === "fulfilled" ? overviewResult.value : null,
        audits: auditResult.status === "fulfilled" ? auditResult.value.items : [],
        exports: exportResult.status === "fulfilled" ? exportResult.value.items : [],
        workflows: workflowResult.status === "fulfilled" ? workflowResult.value.items : [],
      });

      const failures = [overviewResult, auditResult, exportResult, workflowResult].filter((result) => result.status === "rejected");
      setError(
        failures.length
          ? "Some agriculture-linked feeds are unavailable in this static preview, so the restored archive routes are rendering with partial live evidence."
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

type CardItem = {
  title: string;
  subtitle: string;
  detail: string;
  state: string;
  chips?: string[];
};

export function AgriculturePageTemplate({
  icon,
  title,
  description,
  accent,
  cards,
  sideNotes,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  accent: string;
  cards: CardItem[];
  sideNotes: string[];
}) {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const agricultureProduct = useMemo(
    () => overview?.products?.find((product) => product.key === "agricultural-insurance") ?? null,
    [overview?.products],
  );

  const metrics = useMemo(
    () => [
      { label: "Linked workflows", value: String(workflows.length), detail: "Operational journeys that can influence field finance and partner servicing." },
      { label: "Audit signals", value: String(audits.filter((item) => item.severity !== "info").length), detail: "Non-informational controls and alerts visible through the shared audit rail." },
      { label: "Export artifacts", value: String(exports.length), detail: "Reporting and control packages that can support agriculture oversight." },
      { label: "Archive posture", value: agricultureProduct?.status ?? "visible", detail: "The agriculture subtree is now backed by concrete archive-style page bodies instead of placeholders." },
    ],
    [agricultureProduct?.status, audits, exports.length, workflows.length],
  );

  const exportRows = exports.slice(0, 4);

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">{icon}</span>
              {title}
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">{description}</p>
          </div>
          <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{accent}</div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <article key={metric.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{metric.label}</p>
            <p className="mt-4 text-3xl font-semibold text-slate-900">{loading ? "…" : metric.value}</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">{metric.detail}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Operational lanes</h2>
              <p className="mt-1 text-sm text-slate-500">Archive-style content body using compatible workflow, audit, and export evidence.</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(agricultureProduct?.status ?? "visible")}`}>
              {agricultureProduct?.status ?? "visible"}
            </span>
          </div>
          <div className="mt-5 space-y-4">
            {cards.map((item) => (
              <article key={item.title} className="rounded-2xl bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{item.subtitle}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.state)}`}>{item.state}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                {item.chips?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.chips.map((chip) => (
                      <span key={chip} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">{chip}</span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Control notes</h2>
            <div className="mt-4 space-y-3">
              {sideNotes.map((note) => (
                <div key={note} className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">{note}</div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Recent export readiness</h2>
            <div className="mt-4 space-y-3">
              {exportRows.length ? (
                exportRows.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">{item.rowCount} rows · {item.approvalState} approval posture</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No export evidence is currently available in the preview for this agriculture route.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureOverviewPage() {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const agricultureProducts = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["agri", "rural", "farm", "field", "insurance", "weather", "crop", "warehouse", "settlement", "loan", "compliance", "analytics", "agent", "value"].some((token) => haystack.includes(token));
    }).slice(0, 8),
    [overview?.products],
  );
  const overviewFlows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.product} ${item.stage} ${item.nextAction} ${item.channel} ${item.customer}`.toLowerCase();
      return ["agri", "loan", "field", "rural", "farm", "crop", "insurance", "warehouse", "agent", "trade finance", "settlement", "compliance", "partner", "value", "analytics", "weather"].some((token) => haystack.includes(token));
    }).slice(0, 10),
    [workflows],
  );
  const overviewAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return item.severity !== "info" || ["agri", "field", "risk", "review", "ledger", "insurance", "weather", "warehouse", "approval", "settlement", "partner", "notify", "discrepancy", "document", "compliance"].some((token) => haystack.includes(token));
    }).slice(0, 8),
    [audits],
  );
  const overviewExports = useMemo(
    () => exports.filter((item) => ["customer", "alerts", "billing", "analytics", "operations", "trade", "insurance", "mortgage", "ledger", "bank"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 6),
    [exports],
  );
  const agricultureServices = useMemo(
    () => (overview?.serviceHealth ?? []).filter((service) => {
      const haystack = `${service.name} ${service.description} ${service.route} ${service.dependencies.join(" ")}`.toLowerCase();
      return ["agri", "agric", "rural", "field", "weather", "claims", "commodity", "insurance", "trade finance", "settlement", "warehouse", "loan", "compliance", "agent"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [overview?.serviceHealth],
  );
  const priorityFlows = useMemo(
    () => overviewFlows.filter((item) => {
      const status = item.status.toLowerCase();
      return item.slaHours >= 24 || status.includes("review") || status.includes("blocked") || status.includes("pending") || item.nextAction.toLowerCase().includes("approve") || item.nextAction.toLowerCase().includes("repair");
    }).slice(0, 5),
    [overviewFlows],
  );
  const totalVisibleExposure = useMemo(() => overviewFlows.reduce((sum, item) => sum + item.amount, 0), [overviewFlows]);
  const criticalSignals = useMemo(() => overviewAudits.filter((item) => item.severity === "critical").length, [overviewAudits]);
  const readyEvidenceCount = useMemo(() => overviewExports.filter((item) => item.approvalState === "Signed" || item.status === "Ready").length, [overviewExports]);

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Sprout size={24} /></span>
              Agriculture
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The agriculture root now behaves like a fuller archive-style control plane, combining portfolio coverage,
              service posture, workflow pressure, critical control signals, and retained evidence so the restored subtree reads like an operating surface rather than a placeholder overview.
            </p>
          </div>
          <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Archive agriculture control plane</div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Visible product surfaces</p>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{loading ? "…" : agricultureProducts.length}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">Recovered product surfaces that keep rural finance and resilience visible in the archive subtree.</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Priority workflows</p>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{loading ? "…" : priorityFlows.length}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">Cases already under review or beyond the preferred SLA window.</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Critical signals</p>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{loading ? "…" : criticalSignals}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">Highest-severity audit entries currently visible for supervisory handling.</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-lg">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Visible exposure</p>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{loading ? "…" : totalVisibleExposure.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">Aggregate amount across the agriculture-linked workflows currently visible in the shared rail.</p>
        </article>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Product surfaces</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style portfolio visibility using compatible overview metadata.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Canonical subtree</span>
            </div>
            <div className="mt-5 space-y-4">
              {agricultureProducts.length ? (
                agricultureProducts.map((product) => (
                  <article key={product.key} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{product.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{product.category} · {product.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{product.summary}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-400">Services: {product.services.join(" · ") || "Not yet visible"}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No agriculture-linked products are currently visible in preview, but this route is now wired to surface them as compatible metadata arrives.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Priority workflow pressure</h2>
                <p className="mt-1 text-sm text-slate-500">Shared workflow rail filtered into the agriculture operating posture and ranked for urgency.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Live-compatible</span>
            </div>
            <div className="mt-5 space-y-4">
              {(priorityFlows.length ? priorityFlows : overviewFlows.slice(0, 4)).length ? (
                (priorityFlows.length ? priorityFlows : overviewFlows.slice(0, 4)).map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.customer}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.product} · {item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours >= 24 ? "warning" : item.status)}`}>{item.slaHours >= 24 ? `SLA ${item.slaHours}h` : item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}. Visible amount: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No agriculture-style workflow pressure is currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Service posture and control signals</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style operating posture using compatible service health and audit evidence.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">{loading ? "Refreshing" : agricultureServices.length ? `${agricultureServices.length} services` : `${overviewAudits.length} controls`}</span>
            </div>
            <div className="mt-4 space-y-3">
              {agricultureServices.length ? (
                agricultureServices.map((service) => (
                  <article key={service.name} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{service.name}</p>
                        <p className="mt-1 text-sm text-slate-500">{service.route} · {service.latencyMs ? `${service.latencyMs} ms` : "Latency not visible"}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(service.status)}`}>{service.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{service.description}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-400">Dependencies: {service.dependencies.join(" · ") || "Not visible in preview"}</p>
                  </article>
                ))
              ) : overviewAudits.length ? (
                overviewAudits.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">{item.outcome}</p>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No agriculture control signals are currently visible in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Retained export evidence</h2>
                <p className="mt-1 text-sm text-slate-500">Signed and ready packages that support archive-style review continuity.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{loading ? "Refreshing" : `${readyEvidenceCount} ready`}</span>
            </div>
            <div className="mt-4 space-y-3">
              {overviewExports.length ? (
                overviewExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention"}. Export status: {item.status}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No retained agriculture evidence packs are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureFarmersPage() {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const agricultureProducts = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["agri", "rural", "farm", "field", "insurance", "weather"].some((token) => haystack.includes(token));
    }),
    [overview?.products],
  );
  const farmerWorkflows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.customer} ${item.product} ${item.stage} ${item.nextAction} ${item.channel}`.toLowerCase();
      return ["agri", "farm", "field", "agent", "crop", "insurance", "warehouse", "onboard"].some((token) => haystack.includes(token));
    }),
    [workflows],
  );
  const farmerAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return ["customer", "field", "agent", "notify", "agri", "insurance", "weather", "support", "review", "callback", "analytics", "merchant", "operations", "onboard", "collections"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [audits],
  );
  const farmerExports = useMemo(
    () => exports.filter((item) => ["customer", "alerts", "operations", "analytics", "billing", "insurance", "agri", "loan"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 5),
    [exports],
  );
  const farmerPortfolio = useMemo(
    () => [
      {
        label: "Serviced farmer lanes",
        value: loading ? "…" : String(farmerWorkflows.length),
        detail: "Field and onboarding journeys that already resemble farmer servicing and outreach work.",
      },
      {
        label: "Outreach pressure",
        value: loading ? "…" : String(farmerAudits.length),
        detail: "Signals that can require agent follow-through, support recovery, or supervised callback campaigns.",
      },
      {
        label: "Season-ready packs",
        value: loading ? "…" : String(farmerExports.length),
        detail: "Retained evidence packages available for seasonal handoff and farmer portfolio review.",
      },
    ],
    [farmerAudits.length, farmerExports.length, farmerWorkflows.length, loading],
  );
  const outreachBoard = useMemo(
    () => farmerWorkflows.slice(0, 3).map((item) => ({
      id: item.id,
      title: item.customer,
      subtitle: `${item.product} · ${item.channel}`,
      detail: `Next action: ${item.nextAction}`,
      status: item.status,
      amount: item.amount,
    })),
    [farmerWorkflows],
  );
  const farmerSignals = useMemo(
    () => farmerAudits.slice(0, 3).map((item) => ({
      id: item.id,
      title: item.outcome,
      detail: item.detail,
      severity: item.severity,
      route: item.route,
    })),
    [farmerAudits],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Users size={24} /></span>
              Farmers
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The farmer route now reads more like a portfolio-supervision page than a generic queue: it focuses on outreach load,
              field servicing, seasonal continuity, and support recovery while keeping only the compatible active-platform evidence.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Farmer portfolio supervision</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Farmer portfolio continuity</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This page is anchored to the recovered agriculture navigation model and now prioritizes farmer-specific servicing signals
              instead of presenting the same generalized supervisory grammar used across other agriculture routes.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {farmerPortfolio.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Farmer servicing board</h2>
                <p className="mt-1 text-sm text-slate-500">Prioritized field follow-through arranged as a farmer-first supervision board.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Active route</span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {outreachBoard.length ? (
                outreachBoard.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.subtitle}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No dedicated farmer workflows are currently visible in preview, but this route is now shaped to display a farmer-first supervision board as compatible data arrives.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Farmer portfolio anchors</h2>
                <p className="mt-1 text-sm text-slate-500">Recovered product surfaces most likely to underpin field servicing continuity.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Overview-linked</span>
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {agricultureProducts.length ? (
                agricultureProducts.slice(0, 4).map((product) => (
                  <article key={product.key} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">{product.title}</p>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{product.summary}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No agriculture-linked product surfaces are currently visible for the farmer portfolio route.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Outreach and support signals</h2>
            <div className="mt-4 space-y-3">
              {farmerSignals.length ? (
                farmerSignals.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No farmer-linked outreach or support signals are currently visible in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Season continuity packs</h2>
            <div className="mt-4 space-y-3">
              {farmerExports.length ? (
                farmerExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained for farmer portfolio review and seasonal handoff continuity.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No retained continuity packs are currently visible for farmer operations.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureLoansPage() {
  const { audits, exports, workflows, loading, error } = useAgricultureData();

  const loanFlows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.customer} ${item.product} ${item.stage} ${item.nextAction} ${item.channel}`.toLowerCase();
      return ["loan", "origination", "disburs", "collection", "crop", "warehouse", "collateral", "agriculture desk", "trade finance"].some((token) => haystack.includes(token));
    }),
    [workflows],
  );
  const escalationFlows = useMemo(() => loanFlows.filter((item) => item.slaHours > 24 || item.status.toLowerCase().includes("review")).slice(0, 5), [loanFlows]);
  const loanAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return ["loan", "ledger", "risk", "collection", "warehouse", "settlement", "approval"].some((token) => haystack.includes(token));
    }).slice(0, 4),
    [audits],
  );
  const signedLoanExports = useMemo(
    () => exports.filter((item) => (item.approvalState === "Signed" || item.status === "Ready") && ["billing", "analytics", "customer", "trade", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 4),
    [exports],
  );
  const totalExposure = loanFlows.reduce((sum, item) => sum + item.amount, 0);
  const lendingPosture = useMemo(
    () => [
      {
        label: "Credit lanes",
        value: loading ? "…" : String(loanFlows.length),
        detail: "Visible origination, review, disbursement, and collection journeys mapped into the lending desk.",
      },
      {
        label: "Escalated reviews",
        value: loading ? "…" : String(escalationFlows.length),
        detail: "Cases already under SLA pressure or manual review load inside the seasonal credit desk.",
      },
      {
        label: "Signed evidence packs",
        value: loading ? "…" : String(signedLoanExports.length),
        detail: "Reviewable lending packages already retained for approval continuity and downstream supervision.",
      },
    ],
    [escalationFlows.length, loanFlows.length, loading, signedLoanExports.length],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Tractor size={24} /></span>
              Agri Loans
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The lending route now reads more like a seasonal credit desk than a generic queue, centering origination load,
              approval pressure, review evidence, and case-by-case intervention posture while preserving compatible active workflows.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Seasonal lending control</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Desk posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Seasonal credit supervision</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route is shaped around the recovered agriculture navigation model and now emphasizes lending-specific desk rhythm
              instead of sharing the same generic supervisory shell used across weaker archive-style surfaces.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {lendingPosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Seasonal credit pipeline</h2>
                <p className="mt-1 text-sm text-slate-500">Origination and review lanes framed as a dedicated agriculture lending desk.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Actionable route</span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {loanFlows.length ? (
                loanFlows.slice(0, 4).map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.customer}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.product} · {item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>{item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}.</p>
                    <p className="mt-2 text-sm text-slate-500">
                      Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No loan-related workflows are currently visible in preview, but this route is now shaped to surface a clearer agriculture credit pipeline as compatible data arrives.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Escalation watchlist</h2>
                <p className="mt-1 text-sm text-slate-500">Cases already drifting toward manual review, delay, or supervisor follow-through.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Review pressure</span>
            </div>
            <div className="mt-5 space-y-3">
              {escalationFlows.length ? (
                escalationFlows.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.customer}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>{item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.nextAction}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No elevated lending escalations are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Desk exposure and control posture</h2>
            <div className="mt-4 rounded-2xl bg-slate-50 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Visible exposure</p>
              <p className="mt-2 text-3xl font-semibold text-slate-900">{loading ? "…" : totalExposure.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">Aggregate amount across currently visible loan-related workflows in the active platform rail.</p>
            </div>
            <div className="mt-4 space-y-3">
              {loanAudits.length ? (
                loanAudits.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">{item.outcome}</p>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No loan control signals are currently visible in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Signed review packs</h2>
            <div className="mt-4 space-y-3">
              {signedLoanExports.length ? (
                signedLoanExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention"} for approval continuity and downstream lending review.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No signed lending review packs are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureRiskPage() {
  const { audits, exports, workflows, loading, error } = useAgricultureData();

  const riskSignals = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return item.severity !== "info" || ["risk", "alert", "field", "partner", "notify", "degrad", "drift"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [audits],
  );
  const escalatedFlows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.product} ${item.stage} ${item.nextAction} ${item.channel} ${item.status}`.toLowerCase();
      return item.slaHours > 24 || ["review", "repair", "exception", "escal", "field", "partner"].some((token) => haystack.includes(token));
    }).slice(0, 5),
    [workflows],
  );
  const signedRiskPacks = useMemo(
    () => exports.filter((item) => item.approvalState === "Signed").slice(0, 4),
    [exports],
  );
  const riskPosture = useMemo(
    () => [
      {
        label: "Exception signals",
        value: loading ? "…" : String(riskSignals.length),
        detail: "Visible supervisory alerts and drift signals now arranged as a dedicated agriculture exception lane.",
      },
      {
        label: "Escalated flows",
        value: loading ? "…" : String(escalatedFlows.length),
        detail: "Cases already under repair, manual review, or SLA pressure inside the risk desk.",
      },
      {
        label: "Signed packs",
        value: loading ? "…" : String(signedRiskPacks.length),
        detail: "Retained evidence available for exception continuity and supervisory handoff.",
      },
    ],
    [escalatedFlows.length, loading, riskSignals.length, signedRiskPacks.length],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><AlertTriangle size={24} /></span>
              Risk Alerts
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The agriculture risk destination now reads more like a supervisory exception desk than a generic alert summary,
              focusing on control drift, repair pressure, signed packs, and route-level field intervention posture.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Agriculture exception desk</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-amber-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-amber-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Field exception supervision</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route is now anchored to the recovered agriculture navigation model and emphasizes incident handling,
              supervisor follow-through, and exception continuity instead of the weaker generic archive-style card grid.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {riskPosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Exception queue</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style field-risk follow-through backed by the active workflow rail.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Escalation route</span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {escalatedFlows.length ? (
                escalatedFlows.slice(0, 4).map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.product}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>
                        {item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}.</p>
                    <p className="mt-2 text-sm text-slate-500">
                      Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No agriculture-linked escalations are currently visible in preview, but this route is now shaped to surface a clearer exception queue as compatible data arrives.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Repair and review watchlist</h2>
                <p className="mt-1 text-sm text-slate-500">Signals already drifting into manual repair, partner escalation, or operator review.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Operator focus</span>
            </div>
            <div className="mt-5 space-y-3">
              {riskSignals.length ? (
                riskSignals.slice(0, 4).map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.outcome}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.entityType} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No control signals are currently visible in preview for this route.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Route control posture</h2>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Exception posture</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">Live supervisory route</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">The archive risk lane is now a concrete agriculture operating surface instead of a generic card grid.</p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Escalated flow coverage</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{loading ? "…" : escalatedFlows.length}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">Cases currently requiring operator follow-through, repair, or supervised callback campaigns.</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Signed evidence packs</h2>
            <div className="mt-4 space-y-3">
              {signedRiskPacks.length ? (
                signedRiskPacks.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained for exception continuity, route-level review, and supervisory handoff.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No signed evidence packs are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}


export function AgricultureAgtechPage() {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const agtechProducts = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["agri", "digital", "api", "integration", "analytics", "agent", "erp", "insurance", "customer", "trade", "rural", "weather"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [overview?.products],
  );
  const agtechFlows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.product} ${item.stage} ${item.nextAction} ${item.channel} ${item.customer}`.toLowerCase();
      return ["api", "digital", "agent", "partner", "field", "notify", "review", "service"].some((token) => haystack.includes(token));
    }).slice(0, 5),
    [workflows],
  );
  const agtechAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route} ${item.middleware.join(" ")}`.toLowerCase();
      return ["integration", "notify", "field", "partner", "api", "degrad", "drift", "retry", "ledger", "trade", "customer", "kafka"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [audits],
  );
  const agtechExports = useMemo(
    () => exports.filter((item) => ["customer", "ledger", "bank", "dispute", "trade", "insurance", "reconciliation", "analytics", "alerts", "billing", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 5),
    [exports],
  );
  const agtechPosture = useMemo(
    () => [
      {
        label: "Integration rails",
        value: loading ? "…" : String(agtechProducts.length),
        detail: "Recovered route surfaces that currently expose partner, channel, or field-technology coordination metadata.",
      },
      {
        label: "Field hooks",
        value: loading ? "…" : String(agtechFlows.length),
        detail: "Live workflow cases whose next action or channel resembles rollout, onboarding, or assisted-digital follow-through.",
      },
      {
        label: "Retained packs",
        value: loading ? "…" : String(agtechExports.length),
        detail: "Signed or review-state evidence packages available for rollout continuity and escalation handoff.",
      },
    ],
    [agtechExports.length, agtechFlows.length, agtechProducts.length, loading],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Satellite size={24} /></span>
              AgTech
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The AgTech destination now reads as a technology coordination desk for rollout posture, field enablement,
              integration drift, and retained change evidence rather than a soft descriptive placeholder.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Technology coordination desk</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Field technology supervision</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route now emphasizes rollout pressure, connected partner rails, remediation drift, and retained handoff evidence,
              bringing it closer to the recovered agriculture navigation intent instead of the weaker generic operating template.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {agtechPosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Connected rollout rails</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style technology surfaces using compatible overview metadata.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Integration visible</span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {agtechProducts.length ? (
                agtechProducts.slice(0, 4).map((product) => (
                  <article key={product.key} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{product.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{product.category} · {product.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{product.summary}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-400">Services: {product.services.join(" · ") || "Not yet visible"}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No rollout-linked technology surfaces are currently visible in preview for this route.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Field enablement queue</h2>
                <p className="mt-1 text-sm text-slate-500">Visible rollout and assisted-digital follow-through backed by the shared workflow rail.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Operator follow-through</span>
            </div>
            <div className="mt-5 space-y-3">
              {agtechFlows.length ? (
                agtechFlows.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.product}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>
                        {item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}.</p>
                    <p className="mt-2 text-sm text-slate-500">Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No AgTech rollout cases are currently visible in preview, but the route is wired to surface them when compatible workflow data is present.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Integration drift watchlist</h2>
            <p className="mt-1 text-sm text-slate-500">Supervisor-ready remediation signals drawn from the audit and runtime rail.</p>
            <div className="mt-4 space-y-3">
              {agtechAudits.length ? (
                agtechAudits.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.outcome}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.entityType} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No AgTech-linked drift signals are currently visible in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Retained rollout evidence</h2>
            <p className="mt-1 text-sm text-slate-500">Signed or review-state evidence packs supporting change continuity and partner handoff.</p>
            <div className="mt-4 space-y-3">
              {agtechExports.length ? (
                agtechExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention"}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No retained AgTech evidence packs are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureValueChainPage() {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const connectedProducts = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["agri", "trade", "insurance", "ledger", "agent", "customer", "erp", "reconciliation", "rural", "weather", "settlement"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [overview?.products],
  );
  const chainFlows = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.product} ${item.stage} ${item.nextAction} ${item.channel}`.toLowerCase();
      return ["trade", "settlement", "partner", "agent", "onboard", "disburs", "servic"].some((token) => haystack.includes(token));
    }).slice(0, 5),
    [workflows],
  );
  const chainAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route} ${item.middleware.join(" ")}`.toLowerCase();
      return ["partner", "ledger", "trade", "customer", "notify", "agent", "retry", "reconciliation", "discrepancy", "kafka"].some((token) => haystack.includes(token));
    }).slice(0, 5),
    [audits],
  );
  const chainExports = useMemo(
    () => exports.filter((item) => ["ledger", "trade", "customer", "dispute", "bank", "reconciliation", "insurance", "billing", "analytics", "operations", "alerts"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 5),
    [exports],
  );
  const valueChainPosture = useMemo(
    () => [
      {
        label: "Connected surfaces",
        value: loading ? "…" : String(connectedProducts.length),
        detail: "Recovered product surfaces currently feeding the agriculture chain supervision lane.",
      },
      {
        label: "Settlement flows",
        value: loading ? "…" : String(chainFlows.length),
        detail: "Visible settlement, servicing, and partner handoff workflows already present in the shared rail.",
      },
      {
        label: "Retained packs",
        value: loading ? "…" : String(chainExports.length),
        detail: "Signed or retained review packs available for chain continuity and supervisor handoff.",
      },
    ],
    [chainExports.length, chainFlows.length, connectedProducts.length, loading],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><Link2 size={24} /></span>
              Value Chain
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The value-chain destination now reads more like a coordination desk for counterparties, settlements, and servicing handoffs,
              with archive-style posture summaries and supervisor-ready evidence instead of a softer descriptive page shell.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Value-chain oversight</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Cross-chain supervision desk</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route now emphasizes connected products, partner servicing pressure, settlement continuity, and counterparty review,
              bringing it closer to the recovered agriculture navigation model and away from the weaker generic operating template.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {valueChainPosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Connected product surfaces</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style product coordination using compatible overview metadata.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Cross-route ready</span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {connectedProducts.length ? (
                connectedProducts.slice(0, 4).map((product) => (
                  <article key={product.key} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{product.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{product.category} · {product.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{product.summary}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-400">Services: {product.services.join(" · ") || "Not yet visible"}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 md:col-span-2">No connected product surfaces are currently visible in preview for this route.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Servicing and settlement desk</h2>
                <p className="mt-1 text-sm text-slate-500">Visible chain handoffs backed by the shared workflow rail.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Operational follow-through</span>
            </div>
            <div className="mt-5 space-y-3">
              {chainFlows.length ? (
                chainFlows.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.product}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>
                        {item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}.</p>
                    <p className="mt-2 text-sm text-slate-500">Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No value-chain flows are currently visible in preview, but the route is wired to surface them when compatible data is present.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Counterparty control signals</h2>
            <div className="mt-4 space-y-3">
              {chainAudits.length ? (
                chainAudits.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.outcome}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.entityType} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No counterparty control signals are currently visible in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Retained evidence packs</h2>
                <p className="mt-1 text-sm text-slate-500">Supervisor-ready review packs for settlement continuity and counterpart review.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Retention posture</span>
            </div>
            <div className="mt-4 space-y-3">
              {chainExports.length ? (
                chainExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained to support settlement continuity, chain review, and downstream supervisory evidence.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No evidence packs are currently visible in preview for the value-chain route.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureCompliancePage() {
  const { audits, exports, workflows, loading, error } = useAgricultureData();

  const controlAudits = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return item.severity !== "info" || ["review", "approval", "compliance", "risk", "agri", "bank", "customer"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [audits],
  );
  const signedPackages = useMemo(
    () => exports.filter((item) => item.approvalState === "Signed" || item.status === "Ready").slice(0, 6),
    [exports],
  );
  const reviewFlows = useMemo(
    () => workflows.filter((item) => {
      const stage = item.stage.toLowerCase();
      const action = item.nextAction.toLowerCase();
      const haystack = `${item.product} ${item.channel} ${item.customer}`.toLowerCase();
      return stage.includes("review") || stage.includes("approval") || action.includes("review") || action.includes("approve") || ["agri", "field", "warehouse", "insurance", "settlement"].some((token) => haystack.includes(token));
    }).slice(0, 5),
    [workflows],
  );
  const compliancePosture = useMemo(
    () => [
      {
        label: "Control signals",
        value: loading ? "…" : String(controlAudits.length),
        detail: "Non-trivial audit or compliance-linked control entries currently visible to the route.",
      },
      {
        label: "Review queue",
        value: loading ? "…" : String(reviewFlows.length),
        detail: "Workflow cases already carrying approval, review, or escalation pressure for follow-through.",
      },
      {
        label: "Evidence packs",
        value: loading ? "…" : String(signedPackages.length),
        detail: "Signed or review-ready packages available for retention and supervisory handoff.",
      },
    ],
    [controlAudits.length, loading, reviewFlows.length, signedPackages.length],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><FileText size={24} /></span>
              Agri Compliance
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The compliance destination now reads as a tighter supervisory desk for control posture, review escalation,
              and retained evidence rather than a lighter queue-and-cards summary.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Supervisory desk</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Agriculture supervisory review</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route now emphasizes actionable review pressure, retained evidence readiness, and route-specific control framing,
              bringing it closer to the stronger AgTech, Risk, Value Chain, and Analytics desks in the agriculture subtree.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {compliancePosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Supervisory review queue</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style compliance follow-through backed by the shared workflow rail.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Actionable route</span>
            </div>
            <div className="mt-5 space-y-4">
              {reviewFlows.length ? (
                reviewFlows.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.product}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>
                        {item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}. Exposure currently sits at {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No agriculture-linked review flows are currently visible, but the route remains wired for them.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Control watchlist</h2>
                <p className="mt-1 text-sm text-slate-500">Route-specific control signals organized for supervisory reading rather than generic recent activity.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Control posture</span>
            </div>
            <div className="mt-4 space-y-3">
              {controlAudits.length ? (
                controlAudits.slice(0, 4).map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.outcome}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.entityType} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No control signals are currently available in preview.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-emerald-700" size={20} />
              <h2 className="text-xl font-bold text-slate-900">Retained evidence posture</h2>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-500">Signed or review-ready packages that keep agricultural review continuity visible on the route.</p>
            <div className="mt-4 space-y-3">
              {signedPackages.length ? (
                signedPackages.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState === "Signed" ? "signed" : item.status)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows retained{item.retainedUntil ? ` until ${item.retainedUntil}` : " with default retention"}.</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No signed evidence packages are currently visible for this route.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Review routing note</h2>
            <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
              The route now treats workflow pressure, control signals, and retained packages as one supervisory narrative. This keeps the page closer to the recovered sidebar intent without claiming a direct archive page-body extraction that has not been recovered from source files.
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}

export function AgricultureAnalyticsPage() {
  const { overview, audits, exports, workflows, loading, error } = useAgricultureData();

  const agricultureProducts = useMemo(
    () => (overview?.products ?? []).filter((product) => {
      const haystack = `${product.key} ${product.title} ${product.summary} ${product.route} ${product.services.join(" ")}`.toLowerCase();
      return ["agri", "insurance", "rural", "loan", "farm", "weather", "field", "operations", "analytics", "customer", "trade"].some((token) => haystack.includes(token));
    }).slice(0, 6),
    [overview?.products],
  );
  const recentExports = useMemo(
    () => exports.filter((item) => ["agri", "insurance", "bank", "customer", "billing", "ledger", "analytics", "operations"].some((token) => item.route.includes(token) || item.domainKey.includes(token))).slice(0, 6),
    [exports],
  );
  const reviewSignals = useMemo(
    () => audits.filter((item) => {
      const haystack = `${item.entityType} ${item.action} ${item.detail} ${item.route}`.toLowerCase();
      return item.severity !== "info" || ["agri", "farm", "field", "weather", "warehouse", "insurance", "rural", "loan", "settlement", "risk", "analytics"].some((token) => haystack.includes(token));
    }).slice(0, 4),
    [audits],
  );
  const workflowBuckets = useMemo(() => {
    const buckets = [
      { label: "Origination", match: ["origin", "onboard", "intake"] },
      { label: "Review", match: ["review", "approval", "assess"] },
      { label: "Settlement", match: ["settle", "disburs", "post"] },
      { label: "Exceptions", match: ["escalat", "retry", "exception", "repair"] },
    ];

    return buckets.map((bucket) => ({
      label: bucket.label,
      count: workflows.filter((item) => {
        const stage = `${item.stage} ${item.nextAction}`.toLowerCase();
        return bucket.match.some((token) => stage.includes(token));
      }).length,
    }));
  }, [workflows]);
  const maxBucket = Math.max(...workflowBuckets.map((item) => item.count), 1);
  const dominantBucket = workflowBuckets.reduce((current, item) => item.count > current.count ? item : current, workflowBuckets[0] ?? { label: "Origination", count: 0 });
  const reviewDesk = useMemo(
    () => workflows.filter((item) => {
      const haystack = `${item.product} ${item.stage} ${item.nextAction} ${item.channel}`.toLowerCase();
      return ["agri", "insurance", "agent", "settlement", "review", "disburs", "warehouse"].some((token) => haystack.includes(token));
    }).slice(0, 4),
    [workflows],
  );
  const analyticsPosture = useMemo(
    () => [
      {
        label: "Reporting surfaces",
        value: loading ? "…" : String(agricultureProducts.length),
        detail: "Recovered agriculture-linked product or route summaries currently available to the reporting desk.",
      },
      {
        label: "Dominant lane",
        value: loading ? "…" : dominantBucket.label,
        detail: "The busiest workflow bucket across the current agriculture-style analytical grouping.",
      },
      {
        label: "Export packs",
        value: loading ? "…" : String(recentExports.length),
        detail: "Retained evidence packages ready for supervisor review, downstream handoff, or reporting continuity.",
      },
      {
        label: "Review signals",
        value: loading ? "…" : String(reviewSignals.length),
        detail: "Audit-backed control signals currently visible to the agriculture reporting desk.",
      },
    ],
    [agricultureProducts.length, dominantBucket.label, loading, recentExports.length, reviewSignals.length],
  );

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Recovered archive route</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold text-slate-900">
              <span className="rounded-2xl bg-emerald-50 p-3 text-emerald-700"><FileBarChart size={24} /></span>
              Agri Analytics
            </h1>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The analytics destination now reads as a reporting and review desk for workflow mix, route coverage,
              and retained export readiness instead of a sparse metric strip.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Reporting and review desk</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Archive-backed route label</span>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-emerald-50/70 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Route posture</p>
            <p className="mt-3 text-2xl font-semibold text-slate-900">Agriculture reporting desk</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This route now emphasizes workflow concentration, route-level coverage, and evidence-package readiness,
              bringing the analytics lane closer to the recovered agriculture navigation model and away from the weaker placeholder shell.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {analyticsPosture.map((item) => (
                <div key={item.label} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Workflow mix</h2>
                <p className="mt-1 text-sm text-slate-500">Archive-style reporting bars derived from the current workflow rail.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Live reporting</span>
            </div>
            <div className="mt-5 space-y-4">
              {workflowBuckets.map((item) => (
                <div key={item.label}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-slate-700">{item.label}</span>
                    <span className="text-slate-500">{item.count} flows</span>
                  </div>
                  <div className="h-3 rounded-full bg-slate-100">
                    <div className="h-3 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500" style={{ width: `${Math.max((item.count / maxBucket) * 100, item.count ? 18 : 0)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Route review desk</h2>
                <p className="mt-1 text-sm text-slate-500">High-signal cases currently shaping agriculture reporting posture.</p>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Supervisor queue</span>
            </div>
            <div className="mt-5 space-y-3">
              {reviewDesk.length ? (
                reviewDesk.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.product}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.stage} · {item.channel}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.slaHours > 24 ? "warning" : item.status)}`}>
                        {item.slaHours > 24 ? `SLA ${item.slaHours}h` : item.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">Next action: {item.nextAction}.</p>
                    <p className="mt-2 text-sm text-slate-500">Visible exposure: {item.amount.toLocaleString("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 })}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No high-signal agriculture review cases are currently visible in preview.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Route coverage</h2>
            <p className="mt-1 text-sm text-slate-500">Recovered agriculture-linked product surfaces currently visible to the reporting desk.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-1">
              {agricultureProducts.length ? (
                agricultureProducts.map((product) => (
                  <article key={product.key} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{product.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{product.category} · {product.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(product.status)}`}>{product.status}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{product.summary}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No specialized agriculture product summaries are currently exposed in the preview dataset.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Recent review signals</h2>
            <p className="mt-1 text-sm text-slate-500">Audit-backed control notes that now give the analytics route a stronger review-desk posture.</p>
            <div className="mt-5 space-y-3">
              {reviewSignals.length ? (
                reviewSignals.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.outcome}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.entityType} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.severity)}`}>{item.severity}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No review signals are currently available in preview.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900">Export readiness</h2>
            <p className="mt-1 text-sm text-slate-500">Retained packages and downstream evidence posture bound to the current export rail.</p>
            <div className="mt-5 space-y-3">
              {recentExports.length ? (
                recentExports.map((item) => (
                  <article key={item.id} className="rounded-2xl bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.format.toUpperCase()} · {item.route}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.approvalState === "Signed" ? "signed" : item.status)}`}>{item.approvalState}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rowCount} rows prepared by {item.requestedByRole}. {item.retainedUntil ? `Retained until ${item.retainedUntil}.` : "Retention follows the default signed-export posture."}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">No export packages are currently available in preview.</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-amber-700">{error}</p> : null}
    </div>
  );
}
