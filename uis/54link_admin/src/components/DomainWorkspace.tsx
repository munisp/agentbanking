import { useEffect, useMemo, useState } from "react";
import { type LucideIcon, AlertTriangle, ArrowRightLeft, Database, Download, FileClock, ShieldCheck } from "lucide-react";

import ProductShell from "@/components/ProductShell";
import { Button } from "@/components/ui/button";
import {
  createExportJob,
  formatRelativeIso,
  getAuditEntries,
  getAuthContext,
  getExportJobs,
  getOperatorActions,
  updateOperatorActionStatus,
  type AuditEntry,
  type AuthContextResponse,
  type ExportJob,
  type OperatorAction,
  type OperatorRole,
  type OverviewResponse,
  type ProductSurface,
  type ServiceHealth,
} from "@/lib/platform";

type DomainMetric = {
  label: string;
  value: string;
  detail: string;
  tone?: "healthy" | "degraded" | "down" | "neutral";
};

type DomainCollectionItem = {
  title: string;
  subtitle: string;
  state: string;
  detail: string;
  chips?: string[];
};

type DomainActionItem = {
  title: string;
  detail: string;
  state: string;
};

type DomainWorkspaceProps = {
  overview: OverviewResponse | null;
  eyebrow: string;
  title: string;
  summary: string;
  serviceNames: string[];
  heroIcon: LucideIcon;
  accentLabel: string;
  metrics: DomainMetric[];
  collectionTitle: string;
  collectionSummary: string;
  collectionItems: DomainCollectionItem[];
  collectionEmpty: string;
  actionTitle: string;
  actionSummary: string;
  actionItems: DomainActionItem[];
  actionEmpty: string;
  domainKey?: string;
  domainRoute?: string;
  defaultRole?: OperatorRole;
  allowedRoles?: OperatorRole[];
  exportTitle?: string;
  exportFormat?: "csv" | "json" | "xlsx";
};

function toneClass(tone: DomainMetric["tone"] = "neutral") {
  switch (tone) {
    case "healthy":
      return "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
    case "degraded":
      return "border-amber-300/35 bg-amber-300/10 text-amber-50";
    case "down":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    default:
      return "border-white/10 bg-white/[0.03] text-stone-100";
  }
}

function stateTone(state: string) {
  const normalized = state.toLowerCase();
  if (["healthy", "active", "connected", "operational", "ready", "posted", "cleared", "done"].includes(normalized)) {
    return "border-emerald-400/30 bg-emerald-500/10 text-emerald-200";
  }

  if (["degraded", "warning", "review", "pending", "queued", "retrying", "attention", "in progress"].includes(normalized)) {
    return "border-amber-300/35 bg-amber-300/10 text-amber-100";
  }

  if (["down", "failed", "blocked", "critical"].includes(normalized)) {
    return "border-rose-400/35 bg-rose-500/10 text-rose-100";
  }

  return "border-white/10 bg-white/5 text-stone-100";
}

function resolveProducts(overview: OverviewResponse | null): ProductSurface[] {
  return overview?.products ?? [];
}

function resolveServices(overview: OverviewResponse | null, serviceNames: string[]): ServiceHealth[] {
  const configured = overview?.serviceHealth ?? [];
  return configured.filter((service) => serviceNames.includes(service.name));
}

function inferDomainKey(title: string) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
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

function toCsvRow(values: Array<string | number | null | undefined>) {
  return values.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",");
}

function nextActionState(status: OperatorAction["status"]): OperatorAction["status"] {
  if (status === "Pending") {
    return "In progress";
  }

  if (status === "In progress") {
    return "Done";
  }

  return "Done";
}

const exportScopeDomainMap: Partial<Record<string, string[]>> = {
  customers: ["customer-operations"],
  workflows: ["customer-operations", "trade-finance", "dispute-management", "mortgage-servicing", "education-loans", "esusu-groups", "virtual-accounts"],
  actions: ["customer-operations", "trade-finance", "dispute-management", "erpnext-sync", "mortgage-servicing", "education-loans", "esusu-groups", "virtual-accounts"],
  disputes: ["dispute-management"],
  mortgage: ["mortgage-servicing"],
  "education-loans": ["education-loans"],
  esusu: ["esusu-groups"],
  "virtual-accounts": ["virtual-accounts"],
  "trade-finance": ["trade-finance"],
  ledger: ["ledger-reconciliation"],
  reconciliation: ["ledger-reconciliation"],
  insurance: ["agricultural-insurance"],
  compliance: ["agricultural-insurance", "dispute-management", "islamic-banking"],
  audit: ["ledger-reconciliation", "dispute-management", "agricultural-insurance", "islamic-banking", "esusu-groups", "virtual-accounts"],
  "teller-sessions": ["teller-operations"],
};

export default function DomainWorkspace({
  overview,
  eyebrow,
  title,
  summary,
  serviceNames,
  heroIcon: HeroIcon,
  accentLabel,
  metrics,
  collectionTitle,
  collectionSummary,
  collectionItems,
  collectionEmpty,
  actionTitle,
  actionSummary,
  actionItems,
  actionEmpty,
  domainKey,
  domainRoute,
  defaultRole = "operations",
  allowedRoles,
  exportTitle,
  exportFormat = "csv",
}: DomainWorkspaceProps) {
  const products = resolveProducts(overview);
  const services = resolveServices(overview, serviceNames);
  const effectiveDomainKey = domainKey || inferDomainKey(title);
  const effectiveRoute = domainRoute || products.find((product) => product.title === title)?.route || "/";

  const [liveActions, setLiveActions] = useState<OperatorAction[]>([]);
  const [auditItems, setAuditItems] = useState<AuditEntry[]>([]);
  const [exportItems, setExportItems] = useState<ExportJob[]>([]);
  const [authContext, setAuthContext] = useState<AuthContextResponse | null>(null);
  const [loadingRail, setLoadingRail] = useState(false);
  const [railError, setRailError] = useState<string | null>(null);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [busyExport, setBusyExport] = useState(false);

  useEffect(() => {
    let active = true;
    setLoadingRail(true);
    setRailError(null);

    void (async () => {
      try {
        const [actionResponse, auditResponse, exportResponse, authContextResponse] = await Promise.all([
          getOperatorActions(effectiveDomainKey, defaultRole),
          getAuditEntries(defaultRole, effectiveDomainKey),
          getExportJobs(defaultRole),
          getAuthContext(defaultRole),
        ]);

        if (!active) {
          return;
        }

        setLiveActions(actionResponse.items ?? []);
        setAuditItems(auditResponse.items ?? []);
        setExportItems(exportResponse.items ?? []);
        setAuthContext(authContextResponse ?? null);
      } catch (error) {
        if (!active) {
          return;
        }

        setRailError(error instanceof Error ? error.message : "Unable to load the operational control rail.");
      } finally {
        if (active) {
          setLoadingRail(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [defaultRole, effectiveDomainKey]);

  const visibleExportItems = useMemo(
    () => exportItems.filter((item) => item.domainKey === effectiveDomainKey || item.route === effectiveRoute).slice(0, 4),
    [effectiveDomainKey, effectiveRoute, exportItems],
  );
  const nextPendingAction = useMemo(
    () => liveActions.find((item) => item.status !== "Done") ?? null,
    [liveActions],
  );
  const signedEvidenceItems = useMemo(
    () => visibleExportItems.filter((item) => item.approvalState === "Signed" || item.status === "Ready"),
    [visibleExportItems],
  );
  const allowedDomainKeys = authContext?.visibleDomains ?? [];
  const activePermissions = authContext?.permissions ?? [];
  const activeExportScopes = authContext?.exportScopes ?? [];
  const personaAllowsDomain = !allowedRoles?.length || allowedRoles.includes(defaultRole);
  const canOperateDomain = personaAllowsDomain && (!allowedDomainKeys.length || allowedDomainKeys.includes(effectiveDomainKey));
  const canAdvanceWorkflow = activePermissions.includes("workflow.advance");
  const canCreateExports = activeExportScopes.some((scope) => exportScopeDomainMap[scope]?.includes(effectiveDomainKey));
  const canDownloadEvidence = canCreateExports || activePermissions.includes("export.audit") || activePermissions.includes("ledger.read");
  const criticalAuditCount = useMemo(() => auditItems.filter((item) => item.severity === "critical").length, [auditItems]);
  const warningAuditCount = useMemo(() => auditItems.filter((item) => item.severity === "warning").length, [auditItems]);
  const retainedDeliveryItems = useMemo(
    () =>
      visibleExportItems
        .filter((item) => Boolean(item.retainedUntil || item.signedBy?.length || item.approvalChain?.length))
        .slice(0, 3),
    [visibleExportItems],
  );

  const servicePosture = useMemo(() => {
    if (services.some((service) => service.status === "down")) {
      return "down" as const;
    }

    if (services.some((service) => service.status === "degraded")) {
      return "degraded" as const;
    }

    if (services.some((service) => service.status === "healthy")) {
      return "healthy" as const;
    }

    return "neutral" as const;
  }, [services]);
  const railSummaryMetrics = useMemo<DomainMetric[]>(
    () => [
      {
        label: "Open actions",
        value: String(liveActions.filter((item) => item.status !== "Done").length),
        detail: nextPendingAction ? `Next owner ${nextPendingAction.owner} · ${nextPendingAction.status}` : "No pending operator actions are currently attached to this routed surface.",
        tone: nextPendingAction ? (nextPendingAction.status === "Pending" || nextPendingAction.status === "In progress" ? "degraded" : "healthy") : "neutral",
      },
      {
        label: "Audit events",
        value: String(auditItems.length),
        detail: auditItems.length ? `Latest ${auditItems[0]?.action.replaceAll("_", " ") ?? "event"} · ${formatRelativeIso(auditItems[0]?.timestamp)}` : "No retained audit evidence has been returned yet for this domain.",
        tone: auditItems.some((item) => item.severity === "critical") ? "down" : auditItems.some((item) => item.severity === "warning") ? "degraded" : "neutral",
      },
      {
        label: "Ready exports",
        value: String(signedEvidenceItems.length),
        detail: signedEvidenceItems.length ? `${signedEvidenceItems[0]?.title ?? "Evidence pack"} is available for download and review.` : "No signed or ready export evidence is attached to this domain yet.",
        tone: signedEvidenceItems.length ? "healthy" : "neutral",
      },
      {
        label: "Service posture",
        value: services.length ? services.map((service) => service.status).join(" · ") : "unknown",
        detail: services.length ? `${services.length} linked services currently shape this routed workspace.` : "No linked services were matched for this routed workspace.",
        tone: servicePosture,
      },
    ],
    [auditItems, liveActions, nextPendingAction, servicePosture, services, signedEvidenceItems],
  );

  async function handleAdvanceAction(action: OperatorAction) {
    if (!canOperateDomain || !canAdvanceWorkflow) {
      setRailError("The active persona does not have permission to advance workflow actions for this routed banking workspace.");
      return;
    }

    const nextStatus = nextActionState(action.status);
    setBusyActionId(action.id);
    setRailError(null);

    try {
      const updated = await updateOperatorActionStatus(action.id, nextStatus, defaultRole);
      setLiveActions((current) => current.map((item) => (item.id === action.id ? updated : item)));
    } catch (error) {
      setRailError(error instanceof Error ? error.message : "Unable to update the selected operator action.");
    } finally {
      setBusyActionId(null);
    }
  }

  async function handleCreateExport() {
    if (!canOperateDomain || !canCreateExports) {
      setRailError("The active persona cannot generate exports for this routed banking workspace.");
      return;
    }

    setBusyExport(true);
    setRailError(null);

    try {
      const created = await createExportJob(
        {
          domainKey: effectiveDomainKey,
          title: exportTitle || `${title} control export`,
          format: exportFormat,
          route: effectiveRoute,
          rowCount: Math.max(liveActions.length, collectionItems.length, auditItems.length, 1),
        },
        defaultRole,
      );

      setExportItems((current) => [created, ...current]);
    } catch (error) {
      setRailError(error instanceof Error ? error.message : "Unable to create the export package for this workspace.");
    } finally {
      setBusyExport(false);
    }
  }

  async function handleAdvanceNextAction() {
    if (!nextPendingAction) {
      return;
    }

    await handleAdvanceAction(nextPendingAction);
  }

  function handleDownloadSignedEvidence() {
    if (!canOperateDomain || !canDownloadEvidence) {
      setRailError("The active persona cannot download retained evidence for this routed banking workspace.");
      return;
    }

    const evidence = (signedEvidenceItems.length ? signedEvidenceItems : visibleExportItems).map((item) => ({
      id: item.id,
      title: item.title,
      route: item.route,
      domainKey: item.domainKey,
      format: item.format,
      status: item.status,
      approvalState: item.approvalState,
      approvalChain: item.approvalChain ?? [],
      signedBy: item.signedBy ?? [],
      requestedByRole: item.requestedByRole,
      rowCount: item.rowCount,
      retainedUntil: item.retainedUntil ?? null,
      createdAt: item.createdAt,
    }));

    const jsonPayload = {
      title,
      domainKey: effectiveDomainKey,
      route: effectiveRoute,
      generatedAt: new Date().toISOString(),
      evidenceCount: evidence.length,
      evidence,
    };

    const csvLines = [
      toCsvRow(["Title", "Route", "Format", "Status", "Approval State", "Rows", "Requested By", "Retained Until"]),
      ...evidence.map((item) =>
        toCsvRow([
          item.title,
          item.route,
          item.format.toUpperCase(),
          item.status,
          item.approvalState,
          item.rowCount,
          item.requestedByRole,
          item.retainedUntil ?? "default retention",
        ]),
      ),
    ].join("\n");

    downloadTextFile(`${effectiveDomainKey}-signed-evidence.json`, JSON.stringify(jsonPayload, null, 2), "application/json;charset=utf-8");
    downloadTextFile(`${effectiveDomainKey}-signed-evidence.csv`, csvLines, "text/csv;charset=utf-8");
  }

  return (
    <ProductShell products={products} services={services} eyebrow={eyebrow} title={title} summary={summary}>
      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <section className="space-y-4">
          <article className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20">
            <div className="flex items-center gap-3 text-amber-200">
              <HeroIcon size={18} />
              <p className="text-xs uppercase tracking-[0.25em]">{accentLabel}</p>
            </div>
            <p className="mt-4 text-sm leading-7 text-stone-300">{summary}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-300">
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">Domain key: {effectiveDomainKey}</span>
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">Route: {effectiveRoute}</span>
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">Role: {defaultRole}</span>
            </div>
            <p className="mt-4 text-sm leading-7 text-stone-400">Updated {formatRelativeIso(overview?.asOf)}</p>
          </article>

          <div className="grid gap-4 sm:grid-cols-2">
            {metrics.map((metric) => (
              <article key={metric.label} className={`rounded-[1.6rem] border p-5 ${toneClass(metric.tone)}`}>
                <p className="text-xs uppercase tracking-[0.22em] text-current/80">{metric.label}</p>
                <strong className="mt-4 block font-serif text-4xl text-white">{metric.value}</strong>
                <p className="mt-3 text-sm leading-7 text-current/90">{metric.detail}</p>
              </article>
            ))}
          </div>

          <article className="rounded-[1.8rem] border border-white/10 bg-stone-950/60 p-5 shadow-lg shadow-black/20">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Live rail summary</p>
                <h3 className="mt-3 font-serif text-3xl text-white">Runtime-backed operating posture</h3>
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.24em] text-stone-200">
                shared platform rail
              </span>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              {railSummaryMetrics.map((metric) => (
                <article key={metric.label} className={`rounded-[1.5rem] border p-4 ${toneClass(metric.tone)}`}>
                  <p className="text-xs uppercase tracking-[0.22em] text-current/80">{metric.label}</p>
                  <strong className="mt-3 block text-lg text-white">{metric.value}</strong>
                  <p className="mt-2 text-sm leading-6 text-current/90">{metric.detail}</p>
                </article>
              ))}
            </div>
            {!canOperateDomain ? (
              <div className="mt-4 rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4 text-sm leading-7 text-stone-300">
                The active persona can still review the routed workspace summary, but operational controls remain restricted until a role with visibility for <span className="font-semibold text-white">{effectiveDomainKey}</span>{allowedRoles?.length ? <> and one of the permitted personas ({allowedRoles.join(", ")})</> : null} is selected.
              </div>
            ) : null}
          </article>

          <article className="rounded-[1.8rem] border border-amber-300/20 bg-amber-300/10 p-5 shadow-lg shadow-black/20">
            <div className="flex items-start gap-3">
              <span className="mt-1 inline-flex h-10 w-10 items-center justify-center rounded-full bg-amber-300/20 text-amber-100">
                <AlertTriangle size={18} />
              </span>
              <div>
                <h3 className="text-lg font-semibold text-white">Implementation note</h3>
                <p className="mt-2 text-sm leading-7 text-amber-50/90">
                  This surface now loads live operator actions, audit items, and export jobs for the routed domain instead of remaining a purely descriptive placeholder. Where deeper product CRUD is not yet present, the route still exposes operational evidence and executable control actions through the shared platform rail.
                </p>
              </div>
            </div>
          </article>
        </section>

        <section className="space-y-4">
          <article className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">{collectionSummary}</p>
                <h3 className="mt-3 font-serif text-3xl text-white">{collectionTitle}</h3>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.24em] text-stone-200">
                <Database size={12} /> visible surface
              </span>
            </div>
            <div className="mt-5 space-y-3">
              {collectionItems.length === 0 ? (
                <div className="rounded-[1.4rem] border border-dashed border-white/15 bg-stone-950/40 p-5 text-sm leading-7 text-stone-300">
                  {collectionEmpty}
                </div>
              ) : (
                collectionItems.map((item) => (
                  <article key={`${item.title}-${item.subtitle}`} className="rounded-[1.3rem] border border-white/10 bg-stone-950/55 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{item.title}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.2em] text-stone-500">{item.subtitle}</p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${stateTone(item.state)}`}>
                        {item.state}
                      </span>
                    </div>
                    <p className="mt-4 text-sm leading-7 text-stone-300">{item.detail}</p>
                    {item.chips?.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {item.chips.map((chip) => (
                          <span key={chip} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
                            {chip}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </article>

          <article className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Operational controls</p>
                <h3 className="mt-3 font-serif text-3xl text-white">{actionTitle}</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                  onClick={handleAdvanceNextAction}
                  disabled={!nextPendingAction || busyActionId !== null || !canOperateDomain || !canAdvanceWorkflow}
                >
                  <ArrowRightLeft className="mr-2 h-4 w-4" />
                  {nextPendingAction ? "Advance next action" : "No pending actions"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="border-emerald-300/30 bg-emerald-300/10 text-emerald-100 hover:bg-emerald-300/20"
                  onClick={handleDownloadSignedEvidence}
                  disabled={visibleExportItems.length === 0 || !canOperateDomain || !canDownloadEvidence}
                >
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Download signed evidence
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="border-amber-300/30 bg-amber-300/10 text-amber-100 hover:bg-amber-300/20"
                  onClick={handleCreateExport}
                  disabled={busyExport || !canOperateDomain || !canCreateExports}
                >
                  <Download className="mr-2 h-4 w-4" />
                  {busyExport ? "Creating export..." : "Create export package"}
                </Button>
              </div>
            </div>
            <p className="mt-3 text-sm leading-7 text-stone-300">{actionSummary}</p>
            {railError ? <p className="mt-4 rounded-2xl border border-rose-400/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{railError}</p> : null}
            {loadingRail ? <p className="mt-4 text-sm text-stone-400">Loading operator actions, audit evidence, and export history…</p> : null}
            <div className="mt-5 space-y-3">
              {liveActions.length > 0
                ? liveActions.map((item) => (
                    <article key={item.id} className="rounded-[1.3rem] border border-white/10 bg-stone-950/55 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="max-w-2xl">
                          <p className="text-sm font-semibold text-white">{item.title}</p>
                          <p className="mt-2 text-sm leading-7 text-stone-300">{item.detail}</p>
                          <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">
                            Owner: {item.owner} · Due {formatRelativeIso(item.due)}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${stateTone(item.status)}`}>
                            {item.status}
                          </span>
                          {item.status !== "Done" ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                              onClick={() => handleAdvanceAction(item)}
                              disabled={busyActionId === item.id || !canOperateDomain || !canAdvanceWorkflow}
                            >
                              {busyActionId === item.id ? "Updating..." : `Mark ${nextActionState(item.status)}`}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  ))
                : actionItems.length > 0
                  ? actionItems.map((item) => (
                      <article key={item.title} className="rounded-[1.3rem] border border-white/10 bg-stone-950/55 p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="max-w-2xl">
                            <p className="text-sm font-semibold text-white">{item.title}</p>
                            <p className="mt-2 text-sm leading-7 text-stone-300">{item.detail}</p>
                          </div>
                          <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${stateTone(item.state)}`}>
                            {item.state}
                          </span>
                        </div>
                      </article>
                    ))
                  : (
                    <div className="rounded-[1.4rem] border border-dashed border-white/15 bg-stone-950/40 p-5 text-sm leading-7 text-stone-300">
                      {actionEmpty}
                    </div>
                  )}
            </div>
            <div className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-amber-200">
              <ArrowRightLeft size={16} />
              Routed product exposure now includes executable operator actions and export workflow creation through the shared platform API rail.
            </div>
          </article>

          <article className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Audit and delivery evidence</p>
                <h3 className="mt-3 font-serif text-3xl text-white">Live operational history</h3>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.24em] text-stone-200">
                <FileClock size={12} /> evidence rail
              </span>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <article className={`rounded-[1.3rem] border p-4 ${toneClass(criticalAuditCount ? "down" : warningAuditCount ? "degraded" : "neutral")}`}>
                <p className="text-xs uppercase tracking-[0.22em] text-current/80">Audit coverage</p>
                <strong className="mt-3 block text-lg text-white">{auditItems.length}</strong>
                <p className="mt-2 text-sm leading-6 text-current/90">
                  {criticalAuditCount
                    ? `${criticalAuditCount} critical event${criticalAuditCount === 1 ? "" : "s"} require escalation review.`
                    : warningAuditCount
                      ? `${warningAuditCount} warning event${warningAuditCount === 1 ? "" : "s"} remain in the retained audit set.`
                      : "No critical or warning audit events are currently attached to this routed workflow."}
                </p>
              </article>
              <article className={`rounded-[1.3rem] border p-4 ${toneClass(signedEvidenceItems.length ? "healthy" : "neutral")}`}>
                <p className="text-xs uppercase tracking-[0.22em] text-current/80">Signed delivery</p>
                <strong className="mt-3 block text-lg text-white">{signedEvidenceItems.length}</strong>
                <p className="mt-2 text-sm leading-6 text-current/90">
                  {signedEvidenceItems.length
                    ? `${signedEvidenceItems[0]?.title ?? "Latest package"} is currently the newest signed or ready evidence pack.`
                    : "No signed delivery artifact has been retained yet for this routed workflow."}
                </p>
              </article>
              <article className={`rounded-[1.3rem] border p-4 ${toneClass(retainedDeliveryItems.length ? "healthy" : "neutral")}`}>
                <p className="text-xs uppercase tracking-[0.22em] text-current/80">Retention entries</p>
                <strong className="mt-3 block text-lg text-white">{retainedDeliveryItems.length}</strong>
                <p className="mt-2 text-sm leading-6 text-current/90">
                  {retainedDeliveryItems.length
                    ? `${retainedDeliveryItems[0]?.approvalChain?.length ?? 0} approval checkpoints are preserved on the newest retained delivery record.`
                    : "Retention and signing metadata will appear here once delivery artifacts begin flowing through the shared export rail."}
                </p>
              </article>
              <article className={`rounded-[1.3rem] border p-4 ${toneClass(visibleExportItems.length ? "healthy" : "neutral")}`}>
                <p className="text-xs uppercase tracking-[0.22em] text-current/80">Export history</p>
                <strong className="mt-3 block text-lg text-white">{visibleExportItems.length}</strong>
                <p className="mt-2 text-sm leading-6 text-current/90">
                  {visibleExportItems.length
                    ? `${visibleExportItems[0]?.format.toUpperCase() ?? "Package"} exports are now retained alongside audit evidence for this routed workspace.`
                    : "Create the first export package to begin a retained delivery trail for this domain."}
                </p>
              </article>
            </div>
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Recent audit events</p>
                {auditItems.length ? (
                  auditItems.slice(0, 4).map((item) => (
                    <article key={item.id} className="rounded-[1.3rem] border border-white/10 bg-stone-950/55 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-white">{item.action.replaceAll("_", " ")}</p>
                          <p className="mt-2 text-sm leading-7 text-stone-300">{item.outcome}</p>
                          <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">{item.entityType} · {formatRelativeIso(item.timestamp)}</p>
                        </div>
                        <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${stateTone(item.severity)}`}>
                          {item.severity}
                        </span>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.3rem] border border-dashed border-white/15 bg-stone-950/40 p-4 text-sm leading-7 text-stone-300">
                    No domain-filtered audit entries have been returned yet for this routed surface.
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Export packages</p>
                {visibleExportItems.length ? (
                  visibleExportItems.map((item) => (
                    <article key={item.id} className="rounded-[1.3rem] border border-white/10 bg-stone-950/55 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-white">{item.title}</p>
                          <p className="mt-2 text-sm leading-7 text-stone-300">
                            {item.format.toUpperCase()} · {item.rowCount} rows · {item.approvalState}
                          </p>
                          <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">Created {formatRelativeIso(item.createdAt)}</p>
                        </div>
                        <a
                          href={item.downloadUrl}
                          className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.24em] text-stone-100 transition hover:bg-white/10"
                        >
                          Download
                        </a>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[1.3rem] border border-dashed border-white/15 bg-stone-950/40 p-4 text-sm leading-7 text-stone-300">
                    No export jobs have been recorded yet for this domain. Use the control above to create the first routed export package.
                  </div>
                )}

                <div className="pt-2">
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Retention and delivery trail</p>
                  <div className="mt-3 space-y-3">
                    {retainedDeliveryItems.length ? (
                      retainedDeliveryItems.map((item) => (
                        <article key={`${item.id}-retention`} className="rounded-[1.3rem] border border-white/10 bg-stone-950/45 p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-white">{item.title}</p>
                              <p className="mt-2 text-sm leading-7 text-stone-300">
                                {item.signedBy?.length ? `Signed by ${item.signedBy.join(", ")}` : "Awaiting signer details"} · {item.approvalChain?.length ?? 0} approval checkpoint{(item.approvalChain?.length ?? 0) === 1 ? "" : "s"}
                              </p>
                              <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">
                                Retained {item.retainedUntil ? formatRelativeIso(item.retainedUntil) : "under default policy"}
                              </p>
                            </div>
                            <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${stateTone(item.approvalState)}`}>
                              {item.approvalState}
                            </span>
                          </div>
                        </article>
                      ))
                    ) : (
                      <div className="rounded-[1.3rem] border border-dashed border-white/15 bg-stone-950/40 p-4 text-sm leading-7 text-stone-300">
                        Signed deliveries, approval chains, and retention windows will appear here once routed export artifacts begin moving through the approval flow.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-amber-200">
              <ShieldCheck size={16} />
              Domain routes now surface operational history and delivery artifacts instead of static explanatory cards alone.
            </div>
          </article>
        </section>
      </div>
    </ProductShell>
  );
}
