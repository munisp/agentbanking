import { useEffect, useMemo, useState } from "react";
import { Link } from "wouter";
import { AlertTriangle, ArrowRight, BadgeCheck, Building2, CheckCircle2, Layers3, RefreshCw, ShieldCheck } from "lucide-react";

import AdminWorkspaceLayout from "@/components/AdminWorkspaceLayout";
import {
  approvePartnerOnboardingApproval,
  getPartnerOnboardingRecords,
  rejectPartnerOnboardingApproval,
  type OperatorRole,
  type PartnerApprovalRecord,
  type PartnerOnboardingRecord,
} from "@/lib/partnerOnboarding";

function tone(stage: string) {
  if (["launch_ready", "launched", "approved"].includes(stage)) return "bg-emerald-100 text-emerald-700";
  if (["rejected", "restricted"].includes(stage)) return "bg-rose-100 text-rose-700";
  return "bg-amber-100 text-amber-700";
}

const roleOptions: OperatorRole[] = ["operations", "compliance", "treasury", "branch"];

export default function PartnerOnboardingAdminPage() {
  const [partners, setPartners] = useState<PartnerOnboardingRecord[]>([]);
  const [approvals, setApprovals] = useState<PartnerApprovalRecord[]>([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState<string>("");
  const [actingRole, setActingRole] = useState<OperatorRole>("operations");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyApprovalId, setBusyApprovalId] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await getPartnerOnboardingRecords();
      setPartners(response.items);
      setApprovals(response.approvals);
      setSelectedPartnerId((current) => current || response.items[0]?.id || "");
      setError(null);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to load partner onboarding records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const selectedPartner = useMemo(
    () => partners.find((partner) => partner.id === selectedPartnerId) ?? partners[0] ?? null,
    [partners, selectedPartnerId],
  );

  const selectedApprovals = useMemo(
    () => approvals.filter((approval) => approval.partnerId === selectedPartner?.id),
    [approvals, selectedPartner?.id],
  );

  const summary = useMemo(() => {
    const total = partners.length || 1;
    return {
      total: partners.length,
      submitted: partners.filter((partner) => partner.submittedAt).length,
      blocked: partners.filter((partner) => partner.blockers.length > 0).length,
      ready: partners.filter((partner) => partner.stage === "launch_ready" || partner.stage === "launched").length,
      avgReadiness: Math.round(partners.reduce((sum, partner) => sum + partner.readinessScore, 0) / total),
    };
  }, [partners]);

  const resolveApproval = async (approvalId: string, decision: "approve" | "reject") => {
    if (!selectedPartner) return;
    setBusyApprovalId(approvalId);
    try {
      if (decision === "approve") {
        await approvePartnerOnboardingApproval(selectedPartner.id, approvalId, `Approved by ${actingRole} desk.`, actingRole, `${actingRole}.desk`);
      } else {
        await rejectPartnerOnboardingApproval(selectedPartner.id, approvalId, `Rejected by ${actingRole} desk pending remediation.`, actingRole, `${actingRole}.desk`);
      }
      await refresh();
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to resolve approval.");
    } finally {
      setBusyApprovalId(null);
    }
  };

  return (
    <AdminWorkspaceLayout
      eyebrow="White-label partner operations"
      title="Partner onboarding command center"
      description="Review partner applications, inspect readiness blockers, and resolve staged approvals for compliance, commercial, operations, and launch sign-off."
      actions={
        <>
          <div className="inline-flex items-center rounded-full bg-white/10 px-3 py-2 text-sm text-white">
            Acting as
            <select
              value={actingRole}
              onChange={(event) => setActingRole(event.target.value as OperatorRole)}
              className="ml-2 rounded-full border border-white/20 bg-transparent px-3 py-1 text-white outline-none"
            >
              {roleOptions.map((role) => (
                <option key={role} value={role} className="text-stone-900">
                  {role}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-emerald-900"
          >
            <RefreshCw size={16} /> Refresh
          </button>
          <Link href="/partner/onboarding" className="inline-flex items-center gap-2 rounded-full border border-white/30 px-4 py-2 text-sm font-semibold text-white">
            Open partner self-service <ArrowRight size={16} />
          </Link>
        </>
      }
    >
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {[
          { label: "Partner applications", value: summary.total, icon: Building2 },
          { label: "Submitted", value: summary.submitted, icon: Layers3 },
          { label: "Blocked", value: summary.blocked, icon: AlertTriangle },
          { label: "Launch ready", value: summary.ready, icon: CheckCircle2 },
          { label: "Average readiness", value: `${summary.avgReadiness}%`, icon: BadgeCheck },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-[1.6rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                <Icon size={20} />
              </div>
              <p className="mt-4 text-sm text-stone-500">{item.label}</p>
              <p className="mt-2 text-3xl font-semibold text-stone-900">{item.value}</p>
            </div>
          );
        })}
      </section>

      <section className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="rounded-[1.8rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-stone-900">Pipeline</h2>
              <p className="mt-2 text-sm leading-6 text-stone-500">Select a partner application to inspect details, blockers, and staged approvals.</p>
            </div>
            <Link href="/partner/onboarding" className="text-sm font-semibold text-emerald-700">
              New draft
            </Link>
          </div>
          <div className="mt-5 space-y-3">
            {loading ? <p className="text-sm text-stone-500">Loading partner applications…</p> : null}
            {!loading && partners.length === 0 ? <p className="text-sm text-stone-500">No partner applications are available yet.</p> : null}
            {partners.map((partner) => (
              <button
                key={partner.id}
                type="button"
                onClick={() => setSelectedPartnerId(partner.id)}
                className={`w-full rounded-[1.4rem] border px-4 py-4 text-left ${selectedPartner?.id === partner.id ? "border-emerald-300 bg-emerald-50" : "border-stone-200 bg-stone-50"}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-base font-semibold text-stone-900">{partner.partnerName}</p>
                    <p className="mt-1 text-sm text-stone-500">{partner.legalEntity}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(partner.stage)}`}>{partner.stage.replaceAll("_", " ")}</span>
                </div>
                <div className="mt-4 flex items-center justify-between text-sm text-stone-500">
                  <span>{partner.region}</span>
                  <span>{partner.readinessScore}% ready</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          {selectedPartner ? (
            <>
              <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-stone-400">Selected partner</p>
                    <h2 className="mt-2 text-3xl font-semibold text-stone-900">{selectedPartner.partnerName}</h2>
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-stone-500">
                      {selectedPartner.legalEntity} is configured for the {selectedPartner.partnerType} partner track with tenant scope <span className="font-semibold text-stone-700">{selectedPartner.tenantId}</span>.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[1.2rem] bg-stone-50 px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Stage</p>
                      <p className="mt-2 text-lg font-semibold text-stone-900">{selectedPartner.stage.replaceAll("_", " ")}</p>
                    </div>
                    <div className="rounded-[1.2rem] bg-stone-50 px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Readiness</p>
                      <p className="mt-2 text-lg font-semibold text-stone-900">{selectedPartner.readinessScore}%</p>
                    </div>
                  </div>
                </div>
                <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-[1.3rem] bg-stone-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Primary contact</p>
                    <p className="mt-2 font-semibold text-stone-900">{selectedPartner.primaryContact.name || "Missing"}</p>
                    <p className="mt-1 text-sm text-stone-500">{selectedPartner.primaryContact.email || "No email yet"}</p>
                  </div>
                  <div className="rounded-[1.3rem] bg-stone-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Operations contact</p>
                    <p className="mt-2 font-semibold text-stone-900">{selectedPartner.operationsContact.name || "Missing"}</p>
                    <p className="mt-1 text-sm text-stone-500">{selectedPartner.operationsContact.email || "No email yet"}</p>
                  </div>
                  <div className="rounded-[1.3rem] bg-stone-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Commercial model</p>
                    <p className="mt-2 font-semibold text-stone-900">{selectedPartner.commercial.plan}</p>
                    <p className="mt-1 text-sm text-stone-500">{selectedPartner.commercial.billingModel}</p>
                  </div>
                  <div className="rounded-[1.3rem] bg-stone-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Compliance</p>
                    <p className="mt-2 font-semibold text-stone-900">{selectedPartner.compliance.kybStatus.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-sm text-stone-500">{selectedPartner.compliance.submittedDocumentCount}/{selectedPartner.compliance.requiredDocumentCount} docs</p>
                  </div>
                </div>
              </section>

              <section className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="text-emerald-700" size={20} />
                    <h3 className="text-xl font-semibold text-stone-900">Approval lanes</h3>
                  </div>
                  <div className="mt-5 space-y-4">
                    {selectedApprovals.length === 0 ? <p className="text-sm text-stone-500">This partner has not submitted the onboarding application yet.</p> : null}
                    {selectedApprovals.map((approval) => (
                      <div key={approval.id} className="rounded-[1.3rem] border border-stone-200 p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="font-semibold text-stone-900">{approval.title}</p>
                            <p className="mt-1 text-sm leading-6 text-stone-500">{approval.detail}</p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone(approval.state)}`}>{approval.state}</span>
                        </div>
                        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.18em] text-stone-400">
                          <span>Required role: {approval.requiredRole}</span>
                          <span>Requested: {new Date(approval.requestedAt).toLocaleDateString()}</span>
                        </div>
                        {approval.resolutionNote ? <p className="mt-3 text-sm text-stone-600">{approval.resolutionNote}</p> : null}
                        {approval.state === "pending" ? (
                          <div className="mt-4 flex flex-wrap gap-3">
                            <button
                              type="button"
                              disabled={busyApprovalId === approval.id}
                              onClick={() => void resolveApproval(approval.id, "approve")}
                              className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                            >
                              Approve as {actingRole}
                            </button>
                            <button
                              type="button"
                              disabled={busyApprovalId === approval.id}
                              onClick={() => void resolveApproval(approval.id, "reject")}
                              className="rounded-full border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
                            >
                              Reject as {actingRole}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="text-amber-600" size={20} />
                    <h3 className="text-xl font-semibold text-stone-900">Readiness blockers</h3>
                  </div>
                  <div className="mt-5 space-y-3">
                    {selectedPartner.blockers.length === 0 ? <p className="text-sm text-emerald-700">No blockers are currently open for this partner.</p> : null}
                    {selectedPartner.blockers.map((blocker) => (
                      <div key={blocker} className="rounded-[1.2rem] bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        {blocker}
                      </div>
                    ))}
                  </div>
                  <div className="mt-6 rounded-[1.4rem] bg-stone-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Requested modules</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedPartner.requestedModules.map((module) => (
                        <span key={module} className="rounded-full bg-white px-3 py-2 text-sm text-stone-700 shadow-sm">
                          {module.replaceAll("_", " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="mt-6 rounded-[1.4rem] bg-stone-950 p-4 text-white">
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-200/80">White-label profile</p>
                    <p className="mt-3 text-lg font-semibold">{selectedPartner.branding.displayName}</p>
                    <p className="mt-2 text-sm text-stone-300">{selectedPartner.branding.loginHeadline}</p>
                    <div className="mt-4 flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-stone-300">
                      <span>{selectedPartner.branding.primaryColor}</span>
                      <span>{selectedPartner.branding.accentColor}</span>
                    </div>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
              <p className="text-sm text-stone-500">No partner application is selected yet.</p>
            </section>
          )}

          {error ? (
            <section className="rounded-[1.4rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </section>
          ) : null}
        </div>
      </section>
    </AdminWorkspaceLayout>
  );
}
