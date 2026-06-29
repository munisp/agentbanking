import { Smartphone, RefreshCw, RotateCcw, PowerOff, Signal } from "lucide-react";
import React, { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface SIMCard {
  id: string;
  carrier: "MTN" | "Glo" | "Airtel" | "9Mobile";
  status: "active" | "idle" | "failed";
  signalStrength: number;
  dataUsageMB: number;
  lastPing: string;
}

const MOCK_SIMS: SIMCard[] = [
  { id: "SIM-0001", carrier: "MTN", status: "active", signalStrength: 92, dataUsageMB: 1420, lastPing: "2025-05-02 10:44:30" },
  { id: "SIM-0002", carrier: "Airtel", status: "active", signalStrength: 85, dataUsageMB: 980, lastPing: "2025-05-02 10:44:31" },
  { id: "SIM-0003", carrier: "Glo", status: "idle", signalStrength: 60, dataUsageMB: 220, lastPing: "2025-05-02 10:30:05" },
  { id: "SIM-0004", carrier: "9Mobile", status: "failed", signalStrength: 0, dataUsageMB: 0, lastPing: "2025-05-01 22:10:00" },
  { id: "SIM-0005", carrier: "MTN", status: "active", signalStrength: 88, dataUsageMB: 1750, lastPing: "2025-05-02 10:44:29" },
  { id: "SIM-0006", carrier: "Airtel", status: "idle", signalStrength: 72, dataUsageMB: 540, lastPing: "2025-05-02 10:38:14" },
  { id: "SIM-0007", carrier: "Glo", status: "active", signalStrength: 78, dataUsageMB: 890, lastPing: "2025-05-02 10:44:28" },
  { id: "SIM-0008", carrier: "MTN", status: "active", signalStrength: 95, dataUsageMB: 2100, lastPing: "2025-05-02 10:44:33" },
];

const CARRIER_COLORS: Record<string, string> = {
  MTN: "#FFCC00",
  Airtel: "#E30613",
  Glo: "#00A651",
  "9Mobile": "#006633",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  idle: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
};

const SIMOrchestratorDashboard: React.FC = () => {
  const [sims, setSims] = useState<SIMCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  

  useEffect(() => { fetchSIMs(); }, []);

  const fetchSIMs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/sims`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setSims(Array.isArray(d.sims) ? d.sims : MOCK_SIMS); }
    } catch { }
    finally { setLoading(false); }
  };

  const handleAction = async (simId: string, action: "rotate" | "deactivate") => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/sims/${simId}/${action}`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      setActionMsg(`${action === "rotate" ? "Rotated" : "Deactivated"} ${simId}`);
      fetchSIMs();
    } catch {
      setActionMsg(`${action === "rotate" ? "Rotated" : "Deactivated"} ${simId} (demo mode)`);
    }
    setTimeout(() => setActionMsg(null), 3000);
  };

  const carrierCounts = ["MTN", "Glo", "Airtel", "9Mobile"].map(c => ({
    name: c,
    value: sims.filter(s => s.carrier === c).length,
  })).filter(c => c.value > 0);

  const summary = [
    { label: "Total SIMs", value: sims.length, color: "text-gray-800" },
    { label: "Active", value: sims.filter(s => s.status === "active").length, color: "text-green-600" },
    { label: "Idle", value: sims.filter(s => s.status === "idle").length, color: "text-amber-600" },
    { label: "Failed", value: sims.filter(s => s.status === "failed").length, color: "text-red-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Smartphone className="w-7 h-7 text-blue-600" /> SIM Orchestrator Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">SIM pool management, carrier telemetry and connectivity health</p>
        </div>
        <button onClick={fetchSIMs} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {actionMsg && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-2 text-green-700 text-sm">{actionMsg}</div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {summary.map(s => (
          <div key={s.label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">SIM Pool</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                  <th className="pb-3 pr-4">SIM ID</th>
                  <th className="pb-3 pr-4">Carrier</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Signal</th>
                  <th className="pb-3 pr-4">Data (MB)</th>
                  <th className="pb-3 pr-4">Last Ping</th>
                  <th className="pb-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sims.map(sim => (
                  <tr key={sim.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 pr-4 font-mono text-xs text-gray-700">{sim.id}</td>
                    <td className="py-3 pr-4">
                      <span className="text-xs font-semibold px-2 py-0.5 rounded" style={{ backgroundColor: CARRIER_COLORS[sim.carrier] + "33", color: "#374151" }}>{sim.carrier}</span>
                    </td>
                    <td className="py-3 pr-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[sim.status]}`}>{sim.status}</span></td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-1">
                        <Signal className={`w-3.5 h-3.5 ${sim.signalStrength > 70 ? "text-green-500" : sim.signalStrength > 30 ? "text-amber-500" : "text-red-500"}`} />
                        <span className="text-xs text-gray-600">{sim.signalStrength}%</span>
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-gray-600 text-xs">{sim.dataUsageMB.toLocaleString()}</td>
                    <td className="py-3 pr-4 text-gray-400 text-xs">{sim.lastPing}</td>
                    <td className="py-3">
                      <div className="flex gap-1">
                        <button onClick={() => handleAction(sim.id, "rotate")} className="flex items-center gap-1 text-xs px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded">
                          <RotateCcw className="w-3 h-3" /> Rotate
                        </button>
                        <button onClick={() => handleAction(sim.id, "deactivate")} className="flex items-center gap-1 text-xs px-2 py-1 bg-red-50 hover:bg-red-100 text-red-600 rounded">
                          <PowerOff className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Carrier Distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={carrierCounts} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {carrierCounts.map(entry => (
                  <Cell key={entry.name} fill={CARRIER_COLORS[entry.name]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default SIMOrchestratorDashboard;
