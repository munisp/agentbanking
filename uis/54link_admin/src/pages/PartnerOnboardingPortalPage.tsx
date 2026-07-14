import { useEffect, useMemo, useState } from "react";
import { Link } from "wouter";
import { ArrowRight, Building2, CheckCircle2, Globe2, Layers3, Palette, Save } from "lucide-react";

import {
  createPartnerOnboardingDraft,
  getPartnerOnboardingRecords,
  submitPartnerOnboarding,
  updatePartnerOnboardingDraft,
  type PartnerChecklistItem,
  type PartnerOnboardingRecord,
} from "@/lib/partnerOnboarding";

const moduleCatalog = [
  "digital_onboarding",
  "cards",
  "transfers",
  "savings",
  "loans",
  "notifications",
  "campaign_onboarding",
  "partner_referrals",
] as const;

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[1.7rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)] sm:p-6">
      <div>
        <h2 className="text-2xl font-semibold text-stone-900">{title}</h2>
        <p className="mt-2 text-sm leading-7 text-stone-500">{description}</p>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export default function PartnerOnboardingPortalPage() {
  const [partners, setPartners] = useState<PartnerOnboardingRecord[]>([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState<string>("");
  const [draft, setDraft] = useState<PartnerOnboardingRecord | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await getPartnerOnboardingRecords();
      setPartners(response.items);
      const nextId = selectedPartnerId || response.items[0]?.id || "";
      setSelectedPartnerId(nextId);
      const selected = response.items.find((item) => item.id === nextId) ?? response.items[0] ?? null;
      setDraft(selected);
      setError(null);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to load partner onboarding workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const selected = partners.find((item) => item.id === selectedPartnerId) ?? partners[0] ?? null;
    setDraft(selected ? JSON.parse(JSON.stringify(selected)) : null);
  }, [partners, selectedPartnerId]);

  const canSubmit = useMemo(() => Boolean(draft && draft.partnerName && draft.primaryContact.email && draft.operationsContact.email), [draft]);

  const mutateChecklist = (key: string, completed: boolean) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            checklist: current.checklist.map((item) => (item.key === key ? { ...item, completed } : item)),
          }
        : current,
    );
  };

  const mutateModules = (moduleKey: string, enabled: boolean) => {
    setDraft((current) => {
      if (!current) return current;
      const requestedModules = enabled
        ? Array.from(new Set([...current.requestedModules, moduleKey]))
        : current.requestedModules.filter((item) => item !== moduleKey);
      return { ...current, requestedModules };
    });
  };

  const saveDraft = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const response = draft.id
        ? await updatePartnerOnboardingDraft(draft.id, draft, "operations", "partner.portal")
        : await createPartnerOnboardingDraft(draft, "operations", "partner.portal");
      setStatus(`Saved onboarding draft for ${response.partner.partnerName}.`);
      await refresh();
      setSelectedPartnerId(response.partner.id);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to save onboarding draft.");
    } finally {
      setSaving(false);
    }
  };

  const submitDraft = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const response = await submitPartnerOnboarding(draft.id, "operations", "partner.portal");
      setStatus(`Submitted onboarding application for ${response.partner.partnerName}.`);
      await refresh();
      setSelectedPartnerId(response.partner.id);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to submit onboarding application.");
    } finally {
      setSaving(false);
    }
  };

  const createNewDraft = async () => {
    setSaving(true);
    try {
      const response = await createPartnerOnboardingDraft({ partnerName: "New White-Label Partner" }, "operations", "partner.portal");
      setStatus("Created a new partner onboarding draft.");
      await refresh();
      setSelectedPartnerId(response.partner.id);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to create a new onboarding draft.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(13,148,136,0.12),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#ecfeff_100%)] text-stone-900">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] bg-gradient-to-br from-stone-950 via-teal-950 to-cyan-700 px-6 py-6 text-white shadow-[0_24px_80px_rgba(15,23,42,0.22)] sm:px-8 lg:px-10 lg:py-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-4xl">
              <p className="text-xs uppercase tracking-[0.32em] text-cyan-200/80">White-label partner self-service</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-[2.7rem]">Partner onboarding workspace</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-cyan-50/85 sm:text-base">
                Complete company setup, branding preferences, requested modules, compliance packet progress, and launch checklist items from one self-service workspace.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={() => void createNewDraft()} className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-teal-900">
                <Building2 size={16} /> New draft
              </button>
              <Link href="/admin/onboarding" className="inline-flex items-center gap-2 rounded-full border border-white/25 px-4 py-2 text-sm font-semibold text-white">
                Open admin review <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </header>

        <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="rounded-[1.8rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-stone-900">Your drafts</h2>
                <p className="mt-2 text-sm leading-6 text-stone-500">Switch between white-label partner applications or create a new draft.</p>
              </div>
            </div>
            <div className="mt-5 space-y-3">
              {loading ? <p className="text-sm text-stone-500">Loading drafts…</p> : null}
              {partners.map((partner) => (
                <button
                  key={partner.id}
                  type="button"
                  onClick={() => setSelectedPartnerId(partner.id)}
                  className={`w-full rounded-[1.3rem] border px-4 py-4 text-left ${partner.id === draft?.id ? "border-teal-300 bg-teal-50" : "border-stone-200 bg-stone-50"}`}
                >
                  <p className="font-semibold text-stone-900">{partner.partnerName}</p>
                  <p className="mt-1 text-sm text-stone-500">{partner.stage.replaceAll("_", " ")}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-400">{partner.readinessScore}% ready</p>
                </button>
              ))}
            </div>
          </aside>

          <main className="space-y-6">
            {draft ? (
              <>
                <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {[
                    { label: "Stage", value: draft.stage.replaceAll("_", " "), icon: Layers3 },
                    { label: "Readiness", value: `${draft.readinessScore}%`, icon: CheckCircle2 },
                    { label: "Requested modules", value: draft.requestedModules.length, icon: Globe2 },
                    { label: "Documents", value: `${draft.compliance.submittedDocumentCount}/${draft.compliance.requiredDocumentCount}`, icon: Palette },
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.label} className="rounded-[1.6rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
                        <div className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-teal-50 text-teal-700">
                          <Icon size={20} />
                        </div>
                        <p className="mt-4 text-sm text-stone-500">{item.label}</p>
                        <p className="mt-2 text-2xl font-semibold text-stone-900">{item.value}</p>
                      </div>
                    );
                  })}
                </section>

                <Section title="Organization profile" description="Capture the partner identity, legal entity, contacts, and region used across onboarding, settlement, and launch operations.">
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Partner name</span>
                      <input value={draft.partnerName} onChange={(event) => setDraft({ ...draft, partnerName: event.target.value })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Legal entity</span>
                      <input value={draft.legalEntity} onChange={(event) => setDraft({ ...draft, legalEntity: event.target.value })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Primary contact email</span>
                      <input value={draft.primaryContact.email} onChange={(event) => setDraft({ ...draft, primaryContact: { ...draft.primaryContact, email: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Operations contact email</span>
                      <input value={draft.operationsContact.email} onChange={(event) => setDraft({ ...draft, operationsContact: { ...draft.operationsContact, email: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                  </div>
                </Section>

                <Section title="Commercial and compliance setup" description="Define commercial terms, settlement details, and compliance document progress before submission for staged approvals.">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Billing model</span>
                      <input value={draft.commercial.billingModel} onChange={(event) => setDraft({ ...draft, commercial: { ...draft.commercial, billingModel: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Settlement bank</span>
                      <input value={draft.commercial.settlementBank} onChange={(event) => setDraft({ ...draft, commercial: { ...draft.commercial, settlementBank: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Settlement account number</span>
                      <input value={draft.commercial.settlementAccountNumber} onChange={(event) => setDraft({ ...draft, commercial: { ...draft.commercial, settlementAccountNumber: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Required documents</span>
                      <input type="number" value={draft.compliance.requiredDocumentCount} onChange={(event) => setDraft({ ...draft, compliance: { ...draft.compliance, requiredDocumentCount: Number(event.target.value) } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Submitted documents</span>
                      <input type="number" value={draft.compliance.submittedDocumentCount} onChange={(event) => setDraft({ ...draft, compliance: { ...draft.compliance, submittedDocumentCount: Number(event.target.value) } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Compliance notes</span>
                      <input value={draft.compliance.notes || ""} onChange={(event) => setDraft({ ...draft, compliance: { ...draft.compliance, notes: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                  </div>
                </Section>

                <Section title="White-label branding and requested modules" description="Capture the branded customer-facing surface and choose the modules that should be provisioned for launch.">
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Display name</span>
                      <input value={draft.branding.displayName} onChange={(event) => setDraft({ ...draft, branding: { ...draft.branding, displayName: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Support email</span>
                      <input value={draft.branding.supportEmail} onChange={(event) => setDraft({ ...draft, branding: { ...draft.branding, supportEmail: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Primary color</span>
                      <input value={draft.branding.primaryColor} onChange={(event) => setDraft({ ...draft, branding: { ...draft.branding, primaryColor: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                    <label className="space-y-2 text-sm text-stone-600">
                      <span>Accent color</span>
                      <input value={draft.branding.accentColor} onChange={(event) => setDraft({ ...draft, branding: { ...draft.branding, accentColor: event.target.value } })} className="w-full rounded-2xl border border-stone-200 px-4 py-3 outline-none" />
                    </label>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-3">
                    {moduleCatalog.map((moduleKey) => {
                      const active = draft.requestedModules.includes(moduleKey);
                      return (
                        <button
                          key={moduleKey}
                          type="button"
                          onClick={() => mutateModules(moduleKey, !active)}
                          className={`rounded-full px-4 py-2 text-sm font-semibold ${active ? "bg-teal-600 text-white" : "bg-stone-100 text-stone-700"}`}
                        >
                          {moduleKey.replaceAll("_", " ")}
                        </button>
                      );
                    })}
                  </div>
                </Section>

                <Section title="Launch checklist and blockers" description="Complete the operational checklist before submitting for staged approvals and launch review.">
                  <div className="grid gap-3 md:grid-cols-2">
                    {draft.checklist.map((item: PartnerChecklistItem) => (
                      <label key={item.key} className="flex items-center gap-3 rounded-[1.2rem] bg-stone-50 px-4 py-3 text-sm text-stone-700">
                        <input type="checkbox" checked={item.completed} onChange={(event) => mutateChecklist(item.key, event.target.checked)} className="h-4 w-4 rounded border-stone-300" />
                        <span>{item.label}</span>
                      </label>
                    ))}
                  </div>
                  <div className="mt-5 rounded-[1.4rem] bg-stone-950 p-4 text-white">
                    <p className="text-xs uppercase tracking-[0.2em] text-cyan-200/80">Current blockers</p>
                    <div className="mt-3 space-y-2">
                      {draft.blockers.length === 0 ? <p className="text-sm text-emerald-300">No blockers are currently open.</p> : null}
                      {draft.blockers.map((blocker) => (
                        <p key={blocker} className="text-sm text-stone-300">
                          {blocker}
                        </p>
                      ))}
                    </div>
                  </div>
                </Section>

                <section className="flex flex-wrap gap-3">
                  <button type="button" onClick={() => void saveDraft()} disabled={saving} className="inline-flex items-center gap-2 rounded-full bg-teal-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">
                    <Save size={16} /> Save draft
                  </button>
                  <button type="button" onClick={() => void submitDraft()} disabled={!canSubmit || saving} className="inline-flex items-center gap-2 rounded-full border border-teal-200 px-5 py-3 text-sm font-semibold text-teal-700 disabled:opacity-60">
                    Submit for review <ArrowRight size={16} />
                  </button>
                </section>
              </>
            ) : (
              <Section title="No draft selected" description="Create a new draft to begin the partner onboarding flow.">
                <button type="button" onClick={() => void createNewDraft()} className="rounded-full bg-teal-600 px-5 py-3 text-sm font-semibold text-white">
                  Create new partner draft
                </button>
              </Section>
            )}

            {status ? <div className="rounded-[1.4rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{status}</div> : null}
            {error ? <div className="rounded-[1.4rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
          </main>
        </div>
      </div>
    </div>
  );
}
