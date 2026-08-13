import { BarChart2, RefreshCw, Clock, AlertTriangle, CheckCircle, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface EndpointStat {
  endpoint: string;
  calls: number;
  avgLatencyMs: number;
  errorRate: number;
}

interface DailyUsage {
  hour: string;
  requests: number;
}

interface StatusDist {
  code: string;
  count: number;
  color: string;
}

const RANGES = ["24h", "7d", "30d"] as const;

const APIAnalyticsDashboard: React.FC = () => {
  const [endpoints, setEndpoints] = useState<EndpointStat[]>([]);
  const [daily, setDaily] = useState<DailyUsage[]>([]);
  const [status, setStatus] = useState<StatusDist[]>([]);
  const [range, setRange] = useState<"24h" | "7d" | "30d">("24h");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  useEffect(() => { fetchData(); }, [range]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/analytics?range=${range}`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setEndpoints(Array.isArray(d.endpoints) ? d.endpoints : []);
        setDaily(Array.isArray(d.daily) ? d.daily : []);
        setStatus(Array.isArray(d.status) ? d.status : []);
      } else { setError("Failed to load API analytics."); }
    } catch { setError("Failed to load API analytics."); } finally {
      setLoading(false);
      setLastUpdated(new Date().toLocaleTimeString());
    }
  };

  const totalRequests = status.reduce((s, x) => s + x.count, 0);

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
            <BarChart2 className="w-7 h-7 text-blue-600" /> API Analytics Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">Monitor API traffic, latency and error rates across all endpoints</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-gray-100 rounded-lg p-1">
            {RANGES.map(r => (
              <button key={r} onClick={() => setRange(r)}
                className={`px-3 py-1 text-sm rounded-md font-medium transition-colors ${range === r ? "bg-white text-blue-600 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                {r}
              </button>
            ))}
          </div>
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Requests", value: totalRequests.toLocaleString(), icon: Activity, color: "text-blue-600" },
          { label: "Avg Latency", value: "138 ms", icon: Clock, color: "text-purple-600" },
          { label: "Error Rate", value: "0.82%", icon: AlertTriangle, color: "text-red-500" },
          { label: "Uptime", value: "99.97%", icon: CheckCircle, color: "text-emerald-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Icon className={`w-5 h-5 ${color}`} />
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Requests Over Time ({range})</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={daily} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="requests" fill="#3b82f6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Top Endpoints</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-100">
                  <th className="text-left pb-2 pr-4">Endpoint</th>
                  <th className="text-right pb-2 pr-4">Calls</th>
                  <th className="text-right pb-2 pr-4">Avg Latency</th>
                  <th className="text-right pb-2">Error Rate</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((ep, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4 font-mono text-xs text-gray-700 max-w-xs truncate">{ep.endpoint}</td>
                    <td className="py-2 pr-4 text-right font-medium text-gray-900">{ep.calls.toLocaleString()}</td>
                    <td className="py-2 pr-4 text-right text-gray-600">{ep.avgLatencyMs} ms</td>
                    <td className="py-2 text-right">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ep.errorRate > 2 ? "bg-red-100 text-red-700" : ep.errorRate > 0.5 ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"}`}>
                        {ep.errorRate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Status Code Distribution</h2>
          <div className="space-y-3">
            {status.map(s => (
              <div key={s.code}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-700 font-medium">{s.code}</span>
                  <span className="text-gray-500">{s.count.toLocaleString()}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`${s.color} h-2 rounded-full`} style={{ width: `${(s.count / totalRequests) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {lastUpdated && <p className="text-xs text-gray-400 text-right">Last updated: {lastUpdated}</p>}
    </div>
  );
};

export default APIAnalyticsDashboard;
