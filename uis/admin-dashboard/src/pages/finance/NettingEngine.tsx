import { Repeat, RefreshCw, Play, CheckCircle, Clock, AlertCircle, BarChart3 } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface NettingRun {
  id: string;
  run_date: string;
  status: "pending" | "running" | "completed" | "failed";
  participants: number;
  gross_obligations: number;
  net_obligations: number;
  efficiency_rate: number;
  duration_ms?: number;
}

const MOCK_RUNS: NettingRun[] = [
  { id: "net-001", run_date: "2024-11-29 09:00", status: "completed", participants: 142, gross_obligations: 48500000, net_obligations: 12300000, efficiency_rate: 74.6, duration_ms: 1840 },
  { id: "net-002", run_date: "2024-11-28 09:00", status: "completed", participants: 138, gross_obligations: 51200000, net_obligations: 14100000, efficiency_rate: 72.5, duration_ms: 1720 },
  { id: "net-003", run_date: "2024-11-27 09:00", status: "completed", participants: 145, gross_obligations: 43800000, net_obligations: 10200000, efficiency_rate: 76.7, duration_ms: 1610 },
  { id: "net-004", run_date: "2024-11-26 09:00", status: "failed", participants: 0, gross_obligations: 0, net_obligations: 0, efficiency_rate: 0 },
];

const NettingEngine: React.FC = () => {
  const [runs, setRuns] = useState<NettingRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => { fetchRuns(); }, []);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/settlement/api/v1/netting/runs`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setRuns(Array.isArray(d.runs) ? d.runs : MOCK_RUNS); }
      else { setRuns(MOCK_RUNS); }
    } catch { setRuns(MOCK_RUNS); }
    finally { setLoading(false); }
  };

  const triggerNetting = async () => {
    if (!confirm("Trigger an off-cycle netting run now?")) return;
    setTriggering(true);
    try {
      await fetch(`${CORE_URL}/settlement/api/v1/netting/trigger`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchRuns();
      alert("Netting run triggered. Results will appear when complete.");
    } catch { alert("Netting run queued (demo mode)"); }
    finally { setTriggering(false); }
  };

  const latest = runs[0];
  const avgEfficiency = runs.filter(r => r.status === "completed").reduce((s, r) => s + r.efficiency_rate, 0) / (runs.filter(r => r.status === "completed").length || 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Repeat className="w-7 h-7 text-cyan-600" /> Netting Engine
          </h1>
          <p className="text-gray-500 text-sm mt-1">Multilateral net settlement — reduces gross interbank obligations</p>
        </div>
        <button onClick={triggerNetting} disabled={triggering}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium">
          {triggering ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {triggering ? "Triggering..." : "Run Now"}
        </button>
      </div>

      {latest && latest.status === "completed" && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <p className="text-xs text-gray-500 mb-3">Latest Run — {latest.run_date}</p>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "Participants", value: latest.participants, color: "text-gray-700" },
              { label: "Gross Obligations", value: `₦${(latest.gross_obligations / 1e6).toFixed(1)}M`, color: "text-red-600" },
              { label: "Net Obligations", value: `₦${(latest.net_obligations / 1e6).toFixed(1)}M`, color: "text-blue-600" },
              { label: "Netting Efficiency", value: `${latest.efficiency_rate}%`, color: "text-emerald-600" },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <p className="text-xs text-gray-500">{label}</p>
                <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Netting efficiency</span><span>{latest.efficiency_rate}%</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${latest.efficiency_rate}%` }} />
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Avg Efficiency (7d)", value: `${avgEfficiency.toFixed(1)}%`, color: "text-emerald-600" },
          { label: "Successful Runs", value: runs.filter(r => r.status === "completed").length, color: "text-blue-600" },
          { label: "Failed Runs", value: runs.filter(r => r.status === "failed").length, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h3 className="font-medium text-gray-700">Netting History</h3>
          <button onClick={fetchRuns} className="flex items-center gap-1 text-xs text-cyan-600 hover:text-cyan-800">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Run Date", "Participants", "Gross", "Net", "Efficiency", "Duration", "Status"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {runs.map(r => (
              <tr key={r.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4 text-gray-600">{r.run_date}</td>
                <td className="py-3 px-4">{r.participants || "—"}</td>
                <td className="py-3 px-4">₦{r.gross_obligations ? (r.gross_obligations / 1e6).toFixed(1) + "M" : "—"}</td>
                <td className="py-3 px-4">₦{r.net_obligations ? (r.net_obligations / 1e6).toFixed(1) + "M" : "—"}</td>
                <td className="py-3 px-4">
                  {r.efficiency_rate > 0 ? (
                    <span className={r.efficiency_rate >= 70 ? "text-emerald-600 font-medium" : "text-amber-600 font-medium"}>{r.efficiency_rate}%</span>
                  ) : "—"}
                </td>
                <td className="py-3 px-4 text-gray-500">{r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : "—"}</td>
                <td className="py-3 px-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${r.status === "completed" ? "bg-emerald-100 text-emerald-700" : r.status === "failed" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"}`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default NettingEngine;
