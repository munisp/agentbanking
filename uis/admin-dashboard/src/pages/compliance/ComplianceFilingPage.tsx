import React, { useEffect, useState } from "react";
import { Scale, Search, RefreshCw, Plus, Eye, Clock, FileText, Send } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-zinc-500/20 text-zinc-600",
  pending_review: "bg-yellow-500/20 text-yellow-700",
  submitted: "bg-blue-500/20 text-blue-700",
  accepted: "bg-emerald-500/20 text-emerald-700",
  rejected: "bg-red-500/20 text-red-700",
  overdue: "bg-red-500/20 text-red-700",
};

const MOCK_STATS = { totalFilings: 42, submitted: 18, pending: 12, overdue: 3 };
const MOCK_FILINGS = [
  { id: "f1", filing_type: "cbn_returns", period: "2025-Q1", due_date: "2025-04-15", status: "submitted", submitted_at: "2025-04-14T10:00:00Z" },
  { id: "f2", filing_type: "nibss_report", period: "2025-03", due_date: "2025-03-31", status: "accepted", submitted_at: "2025-03-30T09:00:00Z" },
  { id: "f3", filing_type: "aml_filing", period: "2025-Q1", due_date: "2025-04-30", status: "draft", submitted_at: null },
  { id: "f4", filing_type: "tax_return", period: "2024", due_date: "2025-03-31", status: "overdue", submitted_at: null },
  { id: "f5", filing_type: "efcc_report", period: "2025-01", due_date: "2025-02-15", status: "accepted", submitted_at: "2025-02-14T15:00:00Z" },
];

type Filing = typeof MOCK_FILINGS[number];

export default function ComplianceFilingPage() {
  const [stats, setStats] = useState(MOCK_STATS);
  const [filings, setFilings] = useState<Filing[]>(MOCK_FILINGS);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedFiling, setSelectedFiling] = useState<Filing | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ filing_type: "cbn_returns", period: "", due_date: "", description: "" });

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [sRes, fRes] = await Promise.all([
        fetch(`${CORE_URL}/compliance/api/v1/filings/stats`, { headers: getTenantHeadersFromStorage() }),
        fetch(`${CORE_URL}/compliance/api/v1/filings?limit=100`, { headers: getTenantHeadersFromStorage() }),
      ]);
      if (sRes.ok) setStats(await sRes.json());
      if (fRes.ok) setFilings(await fRes.json());
    } catch { /* use mock */ }
    finally { setLoading(false); }
  };

  const createFiling = async () => {
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/filings`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) { setShowCreate(false); load(); }
    } catch { setShowCreate(false); }
  };

  const submitFiling = async (id: string) => {
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/filings/${id}/submit`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      load();
    } catch { /* ignore */ }
  };

  const filtered = filings.filter(f => {
    if (search && !f.filing_type?.toLowerCase().includes(search.toLowerCase()) && !f.period?.includes(search)) return false;
    if (statusFilter !== "all" && f.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Scale className="h-6 w-6 text-indigo-600" />Compliance Filing & Regulatory</h1>
          <p className="text-sm text-gray-500 mt-1">CBN returns, NIBSS reports, AML filings, and regulatory compliance tracking</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm"><Plus className="h-4 w-4" />New Filing</button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Filings", value: stats.totalFilings, icon: FileText, color: "text-indigo-600" },
          { label: "Submitted", value: stats.submitted, icon: Send, color: "text-blue-600" },
          { label: "Pending", value: stats.pending, icon: Clock, color: "text-amber-600" },
          { label: "Overdue", value: stats.overdue, icon: Scale, color: "text-red-600" },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2"><s.icon className={`h-4 w-4 ${s.color}`} /><p className="text-xs text-gray-500">{s.label}</p></div>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input type="text" placeholder="Search filings..." value={search} onChange={e => setSearch(e.target.value)} className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700">
          <option value="all">All Statuses</option>
          {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-gray-50 border-b border-gray-100">
            {["Filing Type", "Period", "Due Date", "Status", "Submitted", "Actions"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-gray-50">
            {filtered.length === 0 ? (
              <tr><td colSpan={6} className="p-8 text-center text-gray-400">No filings found</td></tr>
            ) : filtered.map(f => (
              <tr key={f.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4 font-medium text-gray-800">{f.filing_type?.replace(/_/g, " ")}</td>
                <td className="py-3 px-4 text-gray-500">{f.period}</td>
                <td className="py-3 px-4 text-gray-500">{f.due_date ? new Date(f.due_date).toLocaleDateString() : "—"}</td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[f.status] || "bg-gray-100 text-gray-600"}`}>{f.status?.replace(/_/g, " ")}</span></td>
                <td className="py-3 px-4 text-gray-400 text-xs">{f.submitted_at ? new Date(f.submitted_at).toLocaleString() : "—"}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1">
                    <button onClick={() => setSelectedFiling(f)} className="p-1.5 hover:bg-gray-100 rounded-lg"><Eye className="h-4 w-4 text-gray-400" /></button>
                    {(f.status === "draft" || f.status === "pending_review") && (
                      <button onClick={() => submitFiling(f.id)} className="p-1.5 hover:bg-indigo-50 rounded-lg" title="Submit"><Send className="h-4 w-4 text-indigo-600" /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-md w-full mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-900 mb-4">New Compliance Filing</h3>
            <div className="space-y-3">
              <select value={form.filing_type} onChange={e => setForm({ ...form, filing_type: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
                {["cbn_returns", "nibss_report", "aml_filing", "tax_return", "efcc_report", "ndic_return"].map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
              <input type="text" placeholder="Period (e.g., 2026-Q1)" value={form.period} onChange={e => setForm({ ...form, period: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
              <input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
              <textarea placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={3} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none" />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">Cancel</button>
                <button onClick={createFiling} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm">Create</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedFiling && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setSelectedFiling(null)}>
          <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-gray-900">Filing Details</h3>
              <button onClick={() => setSelectedFiling(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedFiling).map(([key, value]) => (
                <div key={key} className="flex justify-between border-b border-gray-100 pb-2">
                  <span className="text-gray-500 text-sm">{key.replace(/_/g, " ")}</span>
                  <span className="text-gray-800 text-sm font-mono max-w-[250px] truncate">{String(value ?? "—")}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
