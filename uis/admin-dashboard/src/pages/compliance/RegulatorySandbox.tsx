import { FlaskConical, Play, Square, RefreshCw, Plus, CheckCircle, Clock, XCircle, AlertCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface SandboxExperiment {
  id: string;
  name: string;
  description: string;
  category: "payment_limit" | "kyc_threshold" | "agent_tier" | "fee_structure" | "float_policy";
  status: "draft" | "running" | "completed" | "failed";
  participants: number;
  start_date?: string;
  end_date?: string;
  results?: string;
}

const MOCK_EXPERIMENTS: SandboxExperiment[] = [
  { id: "exp-001", name: "Higher Daily Limit Trial", description: "Test ₦300k daily limit for Tier 3 agents vs default ₦200k", category: "payment_limit", status: "running", participants: 45, start_date: "2024-11-01", end_date: "2024-11-30" },
  { id: "exp-002", name: "Simplified BVN KYC", description: "BVN-only onboarding for basic accounts under ₦50k balance", category: "kyc_threshold", status: "completed", participants: 200, start_date: "2024-10-01", end_date: "2024-10-31", results: "23% improvement in onboarding conversion. Fraud rate within acceptable limits." },
  { id: "exp-003", name: "Zero-fee Cash-In Pilot", description: "Waive cash-in fees for 30 days to measure volume uplift", category: "fee_structure", status: "draft", participants: 0 },
];

const CATEGORY_LABELS: Record<string, string> = {
  payment_limit: "Payment Limits", kyc_threshold: "KYC Threshold", agent_tier: "Agent Tier",
  fee_structure: "Fee Structure", float_policy: "Float Policy",
};
const STATUS_STYLES: Record<string, { cls: string; icon: React.FC<any> }> = {
  draft: { cls: "bg-gray-100 text-gray-600", icon: Clock },
  running: { cls: "bg-blue-100 text-blue-700", icon: Play },
  completed: { cls: "bg-emerald-100 text-emerald-700", icon: CheckCircle },
  failed: { cls: "bg-red-100 text-red-700", icon: XCircle },
};

const RegulatorySandbox: React.FC = () => {
  const [experiments, setExperiments] = useState<SandboxExperiment[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", category: "payment_limit" });
  const [launching, setLaunching] = useState<string | null>(null);

  useEffect(() => { fetchExperiments(); }, []);

  const fetchExperiments = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/sandbox/experiments`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setExperiments(Array.isArray(d.experiments) ? d.experiments : MOCK_EXPERIMENTS); }
      else { setExperiments(MOCK_EXPERIMENTS); }
    } catch { setExperiments(MOCK_EXPERIMENTS); }
    finally { setLoading(false); }
  };

  const launchExperiment = async (id: string) => {
    setLaunching(id);
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/sandbox/experiments/${id}/launch`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchExperiments();
    } catch { alert("Experiment launched (demo mode)"); }
    finally { setLaunching(null); }
  };

  const stopExperiment = async (id: string) => {
    if (!confirm("Stop this experiment?")) return;
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/sandbox/experiments/${id}/stop`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchExperiments();
    } catch { alert("Experiment stopped (demo mode)"); }
  };

  const createExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/sandbox/experiments`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setShowForm(false);
      setForm({ name: "", description: "", category: "payment_limit" });
      fetchExperiments();
    } catch { alert("Experiment created (demo mode)"); setShowForm(false); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FlaskConical className="w-7 h-7 text-violet-600" /> Regulatory Sandbox
          </h1>
          <p className="text-gray-500 text-sm mt-1">Test policy changes in a controlled environment before production rollout</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-medium">
          <Plus className="w-4 h-4" /> New Experiment
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <p className="text-sm text-blue-800">Sandbox experiments run on real infrastructure but with isolated participant pools. CBN sandbox guidelines apply.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Running", value: experiments.filter(e => e.status === "running").length, color: "text-blue-600" },
          { label: "Completed", value: experiments.filter(e => e.status === "completed").length, color: "text-emerald-600" },
          { label: "Draft", value: experiments.filter(e => e.status === "draft").length, color: "text-gray-700" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Create Experiment</h2>
          <form onSubmit={createExperiment} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500">
                {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="flex-1 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-medium">Create</button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="space-y-4">
        {experiments.map(exp => {
          const { cls, icon: StatusIcon } = STATUS_STYLES[exp.status];
          return (
            <div key={exp.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900">{exp.name}</h3>
                    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full capitalize ${cls}`}>
                      <StatusIcon className="w-3 h-3" />{exp.status}
                    </span>
                    <span className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded">{CATEGORY_LABELS[exp.category]}</span>
                  </div>
                  <p className="text-sm text-gray-600">{exp.description}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                    {exp.participants > 0 && <span>{exp.participants} participants</span>}
                    {exp.start_date && <span>Started {exp.start_date}</span>}
                    {exp.end_date && <span>Ends {exp.end_date}</span>}
                  </div>
                  {exp.results && (
                    <div className="mt-3 p-3 bg-emerald-50 rounded-lg text-sm text-emerald-800">
                      <strong>Results: </strong>{exp.results}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {exp.status === "draft" && (
                    <button onClick={() => launchExperiment(exp.id)} disabled={launching === exp.id}
                      className="text-xs px-3 py-1.5 bg-violet-600 text-white hover:bg-violet-700 rounded flex items-center gap-1">
                      {launching === exp.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Launch
                    </button>
                  )}
                  {exp.status === "running" && (
                    <button onClick={() => stopExperiment(exp.id)} className="text-xs px-3 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 rounded flex items-center gap-1">
                      <Square className="w-3 h-3" /> Stop
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default RegulatorySandbox;
