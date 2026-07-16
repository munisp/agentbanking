import { Database, RefreshCw, Sliders, Trash2 } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface DBPool {
  dbName: string;
  poolSize: number;
  activeConnections: number;
  idleConnections: number;
  waitingRequests: number;
  maxOverflow: number;
}

interface PeakRecord {
  dbName: string;
  peakActive: number;
  peakTime: string;
  utilization: number;
}

const MOCK_POOLS: DBPool[] = [
  { dbName: "core-banking", poolSize: 20, activeConnections: 14, idleConnections: 6, waitingRequests: 0, maxOverflow: 10 },
  { dbName: "audit-logs", poolSize: 10, activeConnections: 3, idleConnections: 7, waitingRequests: 0, maxOverflow: 5 },
  { dbName: "kyc-store", poolSize: 15, activeConnections: 11, idleConnections: 2, waitingRequests: 3, maxOverflow: 8 },
  { dbName: "analytics", poolSize: 8, activeConnections: 8, idleConnections: 0, waitingRequests: 7, maxOverflow: 4 },
];

const MOCK_PEAKS: PeakRecord[] = [
  { dbName: "core-banking", peakActive: 18, peakTime: "2026-05-01 09:14", utilization: 90 },
  { dbName: "kyc-store", peakActive: 14, peakTime: "2026-04-30 14:22", utilization: 93 },
  { dbName: "analytics", peakActive: 8, peakTime: "2026-05-02 08:00", utilization: 100 },
  { dbName: "audit-logs", peakActive: 6, peakTime: "2026-04-28 11:05", utilization: 60 },
];

const ConnectionPoolMonitor: React.FC = () => {
  const [pools, setPools] = useState<DBPool[]>([]);
  const [peaks, setPeaks] = useState<PeakRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/connection-pools`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setPools(Array.isArray(d.pools) ? d.pools : MOCK_POOLS);
        setPeaks(Array.isArray(d.peaks) ? d.peaks : MOCK_PEAKS);
      } else { setPools(MOCK_POOLS); setPeaks(MOCK_PEAKS); }
    } catch { setPools(MOCK_POOLS); setPeaks(MOCK_PEAKS); }
    finally { setLoading(false); }
  };

  const handleAction = async (dbName: string, action: "drain" | "resize") => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/connection-pools/${dbName}/${action}`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
      });
      setActionMsg(`${action === "drain" ? "Drain" : "Resize"} initiated for ${dbName}`);
      setTimeout(() => setActionMsg(null), 3000);
      fetchData();
    } catch { setActionMsg(`${action} triggered for ${dbName} (demo)`); setTimeout(() => setActionMsg(null), 3000); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Database className="w-7 h-7 text-indigo-600" /> Connection Pool Monitor
          </h1>
          <p className="text-gray-500 text-sm mt-1">Database connection pool utilization and management</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {actionMsg && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm text-blue-700">{actionMsg}</div>
      )}

      <div className="space-y-4">
        {pools.map(pool => {
          const utilPct = Math.round((pool.activeConnections / pool.poolSize) * 100);
          const barColor = utilPct >= 90 ? "bg-red-500" : utilPct >= 70 ? "bg-amber-400" : "bg-emerald-500";
          return (
            <div key={pool.dbName} className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <h2 className="font-semibold text-gray-900 font-mono">{pool.dbName}</h2>
                <div className="flex gap-2">
                  <button onClick={() => handleAction(pool.dbName, "drain")} className="flex items-center gap-1 text-xs px-3 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg font-medium">
                    <Trash2 className="w-3 h-3" /> Drain Pool
                  </button>
                  <button onClick={() => handleAction(pool.dbName, "resize")} className="flex items-center gap-1 text-xs px-3 py-1.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded-lg font-medium">
                    <Sliders className="w-3 h-3" /> Resize Pool
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
                {[
                  { label: "Pool Size", value: pool.poolSize },
                  { label: "Active", value: pool.activeConnections },
                  { label: "Idle", value: pool.idleConnections },
                  { label: "Waiting", value: pool.waitingRequests },
                  { label: "Max Overflow", value: pool.maxOverflow },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="text-lg font-bold text-gray-800 mt-0.5">{value}</p>
                  </div>
                ))}
              </div>
              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Pool Utilization</span>
                  <span className="font-semibold text-gray-700">{utilPct}%</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2.5">
                  <div className={`${barColor} h-2.5 rounded-full transition-all`} style={{ width: `${utilPct}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Historical Peak Usage</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Database", "Peak Active", "Peak Time", "Utilization"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {peaks.map(p => (
                <tr key={p.dbName} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-gray-800">{p.dbName}</td>
                  <td className="py-2 px-3 text-gray-700 font-semibold">{p.peakActive}</td>
                  <td className="py-2 px-3 text-gray-500">{p.peakTime}</td>
                  <td className="py-2 px-3">
                    <span className={`text-xs font-semibold ${p.utilization >= 90 ? "text-red-600" : p.utilization >= 70 ? "text-amber-600" : "text-emerald-600"}`}>
                      {p.utilization}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ConnectionPoolMonitor;
