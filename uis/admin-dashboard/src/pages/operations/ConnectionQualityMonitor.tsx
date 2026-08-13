import { Wifi, WifiOff, AlertTriangle, RefreshCw, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface AgentConnectivity {
  agentId: string;
  location: string;
  qualityScore: "Excellent" | "Good" | "Poor" | "Offline";
  lastSeen: string;
}

interface QualityPoint {
  time: string;
  latency: number;
  packetLoss: number;
}

interface MetricSummary {
  avgLatency: number;
  packetLoss: number;
  jitter: number;
  successRate: number;
}

const QUALITY_STYLES: Record<string, string> = {
  Excellent: "bg-emerald-100 text-emerald-700",
  Good: "bg-blue-100 text-blue-700",
  Poor: "bg-amber-100 text-amber-700",
  Offline: "bg-red-100 text-red-700",
};

const ConnectionQualityMonitor: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [agents, setAgents] = useState<AgentConnectivity[]>([]);
  const [chartData, setChartData] = useState<QualityPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/connection-quality`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setMetrics(d.metrics ?? null);
        setAgents(Array.isArray(d.agents) ? d.agents : []);
        setChartData(Array.isArray(d.chart) ? d.chart : []);
      } else { setError("Failed to load connection quality data."); }
    } catch { setError("Failed to load connection quality data."); } finally { setLoading(false); }
  };

  const poorAgents = agents.filter(a => a.qualityScore === "Poor" || a.qualityScore === "Offline");

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchData()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Wifi className="w-7 h-7 text-indigo-600" /> Connection Quality Monitor
          </h1>
          <p className="text-gray-500 text-sm mt-1">Real-time agent network quality metrics</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Avg Latency", value: metrics ? `${metrics.avgLatency} ms` : "—", color: "text-blue-600" },
          { label: "Packet Loss", value: metrics ? `${metrics.packetLoss} %` : "—", color: "text-amber-600" },
          { label: "Jitter", value: metrics ? `${metrics.jitter} ms` : "—", color: "text-purple-600" },
          { label: "Success Rate", value: metrics ? `${metrics.successRate} %` : "—", color: "text-emerald-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {poorAgents.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-amber-800 text-sm">Connectivity Issues Detected</p>
            <p className="text-amber-700 text-xs mt-0.5">{poorAgents.map(a => a.agentId).join(", ")} — Poor or Offline connectivity</p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><Activity className="w-4 h-4 text-indigo-500" /> Quality Trend (Last 1h)</h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Area type="monotone" dataKey="latency" stroke="#6366f1" fill="#e0e7ff" name="Latency (ms)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><WifiOff className="w-4 h-4 text-indigo-500" /> Agent Connectivity Map</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Agent ID", "Location", "Quality Score", "Last Seen"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agents.map(a => (
                <tr key={a.agentId} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono font-medium text-gray-800">{a.agentId}</td>
                  <td className="py-2 px-3 text-gray-600">{a.location}</td>
                  <td className="py-2 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${QUALITY_STYLES[a.qualityScore]}`}>{a.qualityScore}</span>
                  </td>
                  <td className="py-2 px-3 text-gray-500">{a.lastSeen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ConnectionQualityMonitor;
