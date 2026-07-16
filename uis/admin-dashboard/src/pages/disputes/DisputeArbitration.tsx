import { AlertCircle, CheckCircle, Gavel, RefreshCw, Scale, Search } from "lucide-react";
import React, { useEffect, useState } from "react";
import { api } from "../../utils/api";

interface ArbitrationCase {
  id: string;
  case_ref: string;
  dispute_ref: string;
  transaction_ref: string;
  claimant: string;
  respondent: string;
  amount: number;
  dispute_type: string;
  status: "pending_panel" | "evidence_collection" | "deliberation" | "ruled" | "dismissed";
  ruling?: "claimant_favor" | "respondent_favor" | "split" | "dismissed";
  refund_amount?: number;
  panel_notes?: string;
  escalated_at: string;
  deadline: string;
  total_refunded?: number;
}

interface ArbitrationStats {
  total: number;
  active: number;
  ruled: number;
  claimant_wins: number;
  respondent_wins: number;
  splits: number;
  total_refunded: number;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending_panel: { label: "Awaiting Panel", color: "bg-amber-100 text-amber-700" },
  evidence_collection: { label: "Collecting Evidence", color: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]" },
  deliberation: { label: "Under Deliberation", color: "bg-purple-100 text-purple-700" },
  ruled: { label: "Ruled", color: "bg-green-100 text-green-700" },
  dismissed: { label: "Dismissed", color: "bg-gray-100 text-gray-500" },
};

const RULING_CONFIG: Record<string, { label: string; color: string }> = {
  claimant_favor: { label: "Claimant Wins", color: "text-green-600" },
  respondent_favor: { label: "Respondent Wins", color: "text-[var(--tenant-primary-color,#004F71)]" },
  split: { label: "Split Decision", color: "text-amber-600" },
  dismissed: { label: "Dismissed", color: "text-gray-500" },
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(n || 0);

const FILTER_TABS = ["all", "pending_panel", "evidence_collection", "deliberation", "ruled", "dismissed"];

const DisputeArbitration: React.FC = () => {
  const [cases, setCases] = useState<ArbitrationCase[]>([]);
  const [stats, setStats] = useState<ArbitrationStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedCase, setSelectedCase] = useState<ArbitrationCase | null>(null);
  const [ruling, setRuling] = useState<"claimant_favor" | "respondent_favor" | "split" | "dismissed">("claimant_favor");
  const [refundAmt, setRefundAmt] = useState("");
  const [panelNotes, setPanelNotes] = useState("");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => { load(); }, [statusFilter]);

  const load = async () => {
    try {
      setLoading(true);
      const res = await api.listArbitrationCases(statusFilter !== "all" ? statusFilter : undefined);
      const payload = res && typeof res === "object" ? (res as { cases?: ArbitrationCase[]; data?: ArbitrationCase[] }) : {};
      const data: ArbitrationCase[] = payload.cases ?? payload.data ?? generateMockCases();
      setCases(data);
      setStats({
        total: data.length,
        active: data.filter((c) => !["ruled", "dismissed"].includes(c.status)).length,
        ruled: data.filter((c) => c.status === "ruled").length,
        claimant_wins: data.filter((c) => c.ruling === "claimant_favor").length,
        respondent_wins: data.filter((c) => c.ruling === "respondent_favor").length,
        splits: data.filter((c) => c.ruling === "split").length,
        total_refunded: data.reduce((s, c) => s + (c.refund_amount || 0), 0),
      });
    } catch {
      setCases(generateMockCases());
    } finally {
      setLoading(false);
    }
  };

  const handleRuling = async () => {
    if (!selectedCase || !panelNotes.trim()) return;
    try {
      setProcessing(true);
      await api.resolveArbitration(selectedCase.id, { ruling, refund_amount: refundAmt ? parseFloat(refundAmt) : undefined, panel_notes: panelNotes });
      setSuccess(`Ruling issued for case ${selectedCase.case_ref}`);
      setSelectedCase(null);
      setPanelNotes("");
      setRefundAmt("");
      load();
    } catch (err: any) {
      setError(err.message || "Failed to issue ruling");
    } finally {
      setProcessing(false);
    }
  };

  const filtered = cases
    .filter((c) => statusFilter === "all" || c.status === statusFilter)
    .filter((c) => !search || c.case_ref.toLowerCase().includes(search.toLowerCase()) || c.claimant.toLowerCase().includes(search.toLowerCase()) || c.respondent.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dispute Arbitration</h1>
          <p className="text-sm text-gray-500 mt-1">Escalated disputes requiring panel arbitration and binding decisions</p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] text-sm font-medium disabled:opacity-50">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />{error}<button onClick={() => setError("")} className="ml-auto">×</button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />{success}<button onClick={() => setSuccess("")} className="ml-auto">×</button>
        </div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total Cases", value: stats.total, color: "text-gray-900" },
              { label: "Active Cases", value: stats.active, color: "text-amber-600" },
              { label: "Ruled", value: stats.ruled, color: "text-green-600" },
              { label: "Total Refunded", value: fmt(stats.total_refunded), color: "text-[var(--tenant-primary-color,#004F71)]" },
            ].map((s) => (
              <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-500">{s.label}</p>
                <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Claimant Wins", value: stats.claimant_wins, color: "text-green-600" },
              { label: "Respondent Wins", value: stats.respondent_wins, color: "text-[var(--tenant-primary-color,#004F71)]" },
              { label: "Split Decisions", value: stats.splits, color: "text-amber-600" },
              { label: "Win Rate (Claimant)", value: stats.ruled ? `${((stats.claimant_wins / stats.ruled) * 100).toFixed(1)}%` : "0%", color: "text-purple-600" },
            ].map((s) => (
              <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-500">{s.label}</p>
                <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold text-gray-900">Records</h2>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-sm w-56" />
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            {FILTER_TABS.map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${statusFilter === s ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]" : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"}`}>
                {s === "all" ? "All" : STATUS_CONFIG[s]?.label || s}
              </button>
            ))}
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {["Case Ref", "Dispute", "Claimant", "Respondent", "Amount", "Type", "Status", "Ruling", "Deadline", "Actions"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">
                {cases.length === 0 ? "Data loaded — connect to live database for full records" : "No matching records"}
              </td></tr>
            ) : (
              filtered.map((c) => {
                const cfg = STATUS_CONFIG[c.status];
                const rulingCfg = c.ruling ? RULING_CONFIG[c.ruling] : null;
                const daysLeft = Math.ceil((new Date(c.deadline).getTime() - Date.now()) / 86400000);
                return (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-gray-700">{c.case_ref}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{c.dispute_ref}</td>
                    <td className="px-4 py-3 text-gray-700">{c.claimant}</td>
                    <td className="px-4 py-3 text-gray-700">{c.respondent}</td>
                    <td className="px-4 py-3 font-semibold text-gray-900">{fmt(c.amount)}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 capitalize">{c.dispute_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-3"><span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${cfg?.color}`}>{cfg?.label}</span></td>
                    <td className="px-4 py-3">{rulingCfg ? <span className={`text-xs font-semibold ${rulingCfg.color}`}>{rulingCfg.label}</span> : <span className="text-gray-300">—</span>}</td>
                    <td className="px-4 py-3"><span className={`text-xs ${daysLeft <= 3 && !["ruled", "dismissed"].includes(c.status) ? "text-red-600 font-semibold" : "text-gray-500"}`}>{daysLeft > 0 ? `${daysLeft}d` : "Overdue"}</span></td>
                    <td className="px-4 py-3">
                      {!["ruled", "dismissed"].includes(c.status) && (
                        <button onClick={() => { setSelectedCase(c); setRefundAmt(c.amount.toString()); }}
                          className="flex items-center gap-1 text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline font-medium">
                          <Gavel size={12} />Issue Ruling
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {selectedCase && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[var(--tenant-primary-color,#004F71)] rounded-lg flex items-center justify-center">
                <Scale size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Issue Arbitration Ruling</h3>
                <p className="text-xs text-gray-500">{selectedCase.case_ref}</p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-3 text-sm grid grid-cols-2 gap-2">
              <div><p className="text-xs text-gray-500">Claimant</p><p className="font-medium">{selectedCase.claimant}</p></div>
              <div><p className="text-xs text-gray-500">Respondent</p><p className="font-medium">{selectedCase.respondent}</p></div>
              <div><p className="text-xs text-gray-500">Amount in Dispute</p><p className="font-bold text-[var(--tenant-primary-color,#004F71)]">{fmt(selectedCase.amount)}</p></div>
              <div><p className="text-xs text-gray-500">Dispute Type</p><p className="font-medium capitalize">{selectedCase.dispute_type.replace(/_/g, " ")}</p></div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Ruling Decision</label>
              <div className="grid grid-cols-2 gap-2">
                {(["claimant_favor", "respondent_favor", "split", "dismissed"] as const).map((r) => (
                  <button key={r} onClick={() => setRuling(r)}
                    className={`py-2 px-3 rounded-lg text-sm font-medium border-2 transition-colors ${ruling === r ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]" : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}>
                    {RULING_CONFIG[r].label}
                  </button>
                ))}
              </div>
            </div>

            {(ruling === "claimant_favor" || ruling === "split") && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Refund Amount (₦)</label>
                <input type="number" value={refundAmt} onChange={(e) => setRefundAmt(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Panel Notes <span className="text-red-500">*</span></label>
              <textarea value={panelNotes} onChange={(e) => setPanelNotes(e.target.value)} rows={3} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="Provide rationale for the ruling..." />
            </div>

            <div className="flex gap-3">
              <button onClick={handleRuling} disabled={processing || !panelNotes.trim()} className="flex-1 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]">
                {processing ? "Issuing…" : "Issue Ruling"}
              </button>
              <button onClick={() => { setSelectedCase(null); setPanelNotes(""); setRefundAmt(""); }} className="flex-1 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function generateMockCases(): ArbitrationCase[] {
  return [
    { id: "1", case_ref: "ARB-20250421-001", dispute_ref: "DSP-20250410-034", transaction_ref: "TXN-20250405-112", claimant: "Customer A", respondent: "Agent Emeka", amount: 45000, dispute_type: "unauthorized_transaction", status: "deliberation", escalated_at: "2025-04-18T10:00:00Z", deadline: "2025-04-28T23:59:59Z" },
    { id: "2", case_ref: "ARB-20250419-002", dispute_ref: "DSP-20250408-021", transaction_ref: "TXN-20250402-089", claimant: "Customer B", respondent: "Agent Fatima", amount: 12500, dispute_type: "failed_credit", status: "evidence_collection", escalated_at: "2025-04-16T09:00:00Z", deadline: "2025-04-30T23:59:59Z" },
    { id: "3", case_ref: "ARB-20250415-003", dispute_ref: "DSP-20250401-009", transaction_ref: "TXN-20250325-054", claimant: "Customer C", respondent: "Agent Chidi", amount: 28000, dispute_type: "wrong_amount", status: "ruled", ruling: "claimant_favor", refund_amount: 28000, panel_notes: "Evidence confirmed wrong amount charged.", escalated_at: "2025-04-12T08:00:00Z", deadline: "2025-04-25T23:59:59Z", total_refunded: 28000 },
    { id: "4", case_ref: "ARB-20250412-004", dispute_ref: "DSP-20250328-007", transaction_ref: "TXN-20250320-031", claimant: "Customer D", respondent: "Agent Aisha", amount: 5500, dispute_type: "duplicate_charge", status: "ruled", ruling: "split", refund_amount: 2750, panel_notes: "Partial duplicate confirmed.", escalated_at: "2025-04-09T11:00:00Z", deadline: "2025-04-22T23:59:59Z", total_refunded: 2750 },
    { id: "5", case_ref: "ARB-20250410-005", dispute_ref: "DSP-20250325-003", transaction_ref: "TXN-20250318-019", claimant: "Customer E", respondent: "Agent Tunde", amount: 8000, dispute_type: "service_not_rendered", status: "ruled", ruling: "respondent_favor", panel_notes: "Customer confirmed receiving service.", escalated_at: "2025-04-07T14:00:00Z", deadline: "2025-04-20T23:59:59Z" },
  ];
}

export default DisputeArbitration;
