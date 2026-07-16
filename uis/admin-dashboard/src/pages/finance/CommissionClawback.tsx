import { RotateCcw, RefreshCw, Plus, AlertTriangle, CheckCircle, Clock, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface ClawbackCase {
  id: string;
  agent_id: string;
  agent_name: string;
  reason: "fraud" | "reversal" | "policy_violation" | "error" | "duplicate";
  amount: number;
  original_commission_date: string;
  status: "pending_approval" | "approved" | "executed" | "disputed" | "cancelled";
  notes?: string;
  created_at: string;
}

const MOCK_CASES: ClawbackCase[] = [
  { id: "clb-001", agent_id: "AGT-0023", agent_name: "Tunde Bakare", reason: "reversal", amount: 12500, original_commission_date: "2024-11-01", status: "approved", notes: "Commission on reversed transaction TXN-112", created_at: "2024-11-28" },
  { id: "clb-002", agent_id: "AGT-0087", agent_name: "Grace Okoro", reason: "fraud", amount: 45000, original_commission_date: "2024-10-15", status: "pending_approval", notes: "Agent involved in suspected collusion fraud case", created_at: "2024-11-27" },
  { id: "clb-003", agent_id: "AGT-0112", agent_name: "Emeka Nwosu", reason: "duplicate", amount: 8800, original_commission_date: "2024-11-10", status: "executed", created_at: "2024-11-20" },
  { id: "clb-004", agent_id: "AGT-0055", agent_name: "Fatima Aliyu", reason: "policy_violation", amount: 22000, original_commission_date: "2024-11-05", status: "disputed", notes: "Agent disputes — claims transactions were legitimate", created_at: "2024-11-22" },
];

const REASON_LABELS: Record<string, string> = {
  fraud: "Fraud", reversal: "Transaction Reversal", policy_violation: "Policy Violation",
  error: "System Error", duplicate: "Duplicate Payment",
};
const STATUS_STYLES: Record<string, string> = {
  pending_approval: "bg-amber-100 text-amber-700", approved: "bg-blue-100 text-blue-700",
  executed: "bg-emerald-100 text-emerald-700", disputed: "bg-orange-100 text-orange-700",
  cancelled: "bg-gray-100 text-gray-600",
};

const CommissionClawback: React.FC = () => {
  const [cases, setCases] = useState<ClawbackCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ agent_id: "", agent_name: "", reason: "reversal", amount: "", notes: "" });
  const [processing, setProcessing] = useState<string | null>(null);

  useEffect(() => { fetchCases(); }, []);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/commission/api/v1/clawbacks`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setCases(Array.isArray(d.cases) ? d.cases : MOCK_CASES); }
      else { setCases(MOCK_CASES); }
    } catch { setCases(MOCK_CASES); }
    finally { setLoading(false); }
  };

  const approveClawback = async (id: string) => {
    setProcessing(id);
    try {
      await fetch(`${CORE_URL}/commission/api/v1/clawbacks/${id}/approve`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchCases();
    } catch (err: any) { alert(err.message); }
    finally { setProcessing(null); }
  };

  const executeClawback = async (id: string) => {
    if (!confirm("Execute this clawback? This will debit the agent's commission balance.")) return;
    setProcessing(id);
    try {
      await fetch(`${CORE_URL}/commission/api/v1/clawbacks/${id}/execute`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchCases();
    } catch (err: any) { alert(err.message); }
    finally { setProcessing(null); }
  };

  const createCase = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch(`${CORE_URL}/commission/api/v1/clawbacks`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, amount: Number(form.amount), original_commission_date: new Date().toISOString().split("T")[0] }),
      });
      setShowForm(false);
      fetchCases();
    } catch { alert("Case created (demo mode)"); setShowForm(false); }
  };

  const totalPending = cases.filter(c => c.status === "pending_approval").reduce((s, c) => s + c.amount, 0);
  const totalExecuted = cases.filter(c => c.status === "executed").reduce((s, c) => s + c.amount, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <RotateCcw className="w-7 h-7 text-rose-600" /> Commission Clawback
          </h1>
          <p className="text-gray-500 text-sm mt-1">Recover incorrectly paid agent commissions due to fraud, reversals or policy violations</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-medium">
          <Plus className="w-4 h-4" /> Initiate Clawback
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Pending Approval", value: `₦${totalPending.toLocaleString()}`, color: "text-amber-600" },
          { label: "Recovered (Executed)", value: `₦${totalExecuted.toLocaleString()}`, color: "text-emerald-600" },
          { label: "Disputed", value: cases.filter(c => c.status === "disputed").length, color: "text-orange-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Initiate Clawback</h2>
          <form onSubmit={createCase} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Agent ID</label>
                <input value={form.agent_id} onChange={e => setForm(f => ({ ...f, agent_id: e.target.value }))} required placeholder="AGT-XXXX"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Agent Name</label>
                <input value={form.agent_name} onChange={e => setForm(f => ({ ...f, agent_name: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Reason</label>
                <select value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500">
                  {Object.entries(REASON_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Amount (₦)</label>
                <input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Notes</label>
              <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500" />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="flex-1 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-medium">Submit for Approval</button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Agent", "Reason", "Amount", "Status", "Notes", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : cases.map(c => (
              <tr key={c.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4">
                  <p className="font-medium">{c.agent_name}</p>
                  <p className="text-xs text-gray-400">{c.agent_id}</p>
                </td>
                <td className="py-3 px-4"><span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded">{REASON_LABELS[c.reason]}</span></td>
                <td className="py-3 px-4 font-semibold text-rose-600">₦{c.amount.toLocaleString()}</td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[c.status]}`}>{c.status.replace("_", " ")}</span></td>
                <td className="py-3 px-4 text-gray-500 text-xs max-w-40 truncate">{c.notes || "—"}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-2">
                    {c.status === "pending_approval" && (
                      <button onClick={() => approveClawback(c.id)} disabled={processing === c.id}
                        className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded">Approve</button>
                    )}
                    {c.status === "approved" && (
                      <button onClick={() => executeClawback(c.id)} disabled={processing === c.id}
                        className="text-xs px-2 py-1 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded">Execute</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CommissionClawback;
