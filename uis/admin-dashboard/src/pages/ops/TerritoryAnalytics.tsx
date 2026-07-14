import { MapPin, RefreshCw, TrendingUp, TrendingDown, BarChart3, Users, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface TerritoryData {
  id: string;
  name: string;
  state: string;
  zone: "north" | "south" | "east" | "west" | "central";
  active_agents: number;
  total_agents: number;
  monthly_volume: number;
  transaction_count: number;
  avg_agent_utilization: number;
  growth_rate: number;
  top_service: string;
  coverage_gap: boolean;
}

const MOCK_TERRITORIES: TerritoryData[] = [
  { id: "TER-001", name: "Lagos Island", state: "Lagos", zone: "south", active_agents: 84, total_agents: 92, monthly_volume: 48500000, transaction_count: 12400, avg_agent_utilization: 91, growth_rate: 12.4, top_service: "Cash In", coverage_gap: false },
  { id: "TER-002", name: "Abuja Municipal", state: "FCT", zone: "central", active_agents: 62, total_agents: 70, monthly_volume: 38200000, transaction_count: 9800, avg_agent_utilization: 88, growth_rate: 8.2, top_service: "Transfer", coverage_gap: false },
  { id: "TER-003", name: "Kano Central", state: "Kano", zone: "north", active_agents: 28, total_agents: 55, monthly_volume: 12400000, transaction_count: 3200, avg_agent_utilization: 51, growth_rate: -2.1, top_service: "Bill Payment", coverage_gap: true },
  { id: "TER-004", name: "Port Harcourt", state: "Rivers", zone: "south", active_agents: 45, total_agents: 52, monthly_volume: 22100000, transaction_count: 5600, avg_agent_utilization: 86, growth_rate: 15.8, top_service: "Cash Out", coverage_gap: false },
  { id: "TER-005", name: "Enugu North", state: "Enugu", zone: "east", active_agents: 18, total_agents: 40, monthly_volume: 7800000, transaction_count: 2100, avg_agent_utilization: 45, growth_rate: -5.3, top_service: "Cash In", coverage_gap: true },
];

const ZONE_COLORS: Record<string, string> = { north: "bg-amber-100 text-amber-700", south: "bg-blue-100 text-blue-700", east: "bg-green-100 text-green-700", west: "bg-purple-100 text-purple-700", central: "bg-gray-100 text-gray-700" };

const TerritoryAnalytics: React.FC = () => {
  const [territories, setTerritories] = useState<TerritoryData[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<TerritoryData | null>(null);
  const [zoneFilter, setZoneFilter] = useState("all");

  

  useEffect(() => { fetchTerritories(); }, []);

  const fetchTerritories = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/geospatial/api/v1/territories/analytics`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setTerritories(Array.isArray(d.territories) ? d.territories : MOCK_TERRITORIES); }
    } catch { }
    finally { setLoading(false); }
  };

  const filtered = territories.filter(t => zoneFilter === "all" || t.zone === zoneFilter);
  const totalVolume = territories.reduce((s, t) => s + t.monthly_volume, 0);
  const totalAgents = territories.reduce((s, t) => s + t.active_agents, 0);
  const gapCount = territories.filter(t => t.coverage_gap).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="w-7 h-7 text-green-600" /> Territory Analytics
          </h1>
          <p className="text-gray-500 text-sm mt-1">Agent coverage, volume and growth by geographic territory</p>
        </div>
        <button onClick={fetchTerritories} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Volume", value: `₦${(totalVolume / 1e6).toFixed(0)}M`, color: "text-blue-600" },
          { label: "Active Agents", value: totalAgents, color: "text-emerald-600" },
          { label: "Coverage Gaps", value: gapCount, color: "text-red-600" },
          { label: "Territories", value: territories.length, color: "text-gray-700" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {["all", "north", "south", "east", "west", "central"].map(f => (
          <button key={f} onClick={() => setZoneFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors ${zoneFilter === f ? "bg-green-600 border-green-500 text-white" : "bg-white border-gray-200 text-gray-600"}`}>
            {f}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Territory", "Zone", "Agents", "Monthly Vol", "Transactions", "Utilization", "Growth", "Top Service", ""].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : filtered.map(t => (
              <tr key={t.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4">
                  <p className="font-medium text-gray-900">{t.name}</p>
                  <p className="text-xs text-gray-400">{t.state}</p>
                  {t.coverage_gap && <span className="text-xs text-red-500">⚠ Coverage gap</span>}
                </td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${ZONE_COLORS[t.zone]}`}>{t.zone}</span></td>
                <td className="py-3 px-4">
                  <span className="font-medium">{t.active_agents}</span>
                  <span className="text-xs text-gray-400">/{t.total_agents}</span>
                </td>
                <td className="py-3 px-4 font-medium">₦{(t.monthly_volume / 1e6).toFixed(1)}M</td>
                <td className="py-3 px-4">{t.transaction_count.toLocaleString()}</td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div className="w-12 bg-gray-100 rounded-full h-1.5">
                      <div className={`h-1.5 rounded-full ${t.avg_agent_utilization >= 70 ? "bg-emerald-500" : t.avg_agent_utilization >= 50 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${t.avg_agent_utilization}%` }} />
                    </div>
                    <span className="text-xs">{t.avg_agent_utilization}%</span>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <span className={`flex items-center gap-1 text-xs font-medium ${t.growth_rate >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {t.growth_rate >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {t.growth_rate > 0 ? "+" : ""}{t.growth_rate}%
                  </span>
                </td>
                <td className="py-3 px-4 text-gray-600 text-xs">{t.top_service}</td>
                <td className="py-3 px-4">
                  <button onClick={() => setSelected(t)} className="text-xs px-2 py-1 bg-green-50 text-green-700 hover:bg-green-100 rounded">Details</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-lg">{selected.name}</h2>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="space-y-2 text-sm">
              {[
                ["State", selected.state], ["Zone", selected.zone],
                ["Active Agents", `${selected.active_agents} / ${selected.total_agents}`],
                ["Monthly Volume", `₦${selected.monthly_volume.toLocaleString()}`],
                ["Transactions", selected.transaction_count.toLocaleString()],
                ["Utilization", `${selected.avg_agent_utilization}%`],
                ["Growth Rate", `${selected.growth_rate}%`],
                ["Top Service", selected.top_service],
                ["Coverage Gap", selected.coverage_gap ? "Yes" : "No"],
              ].map(([l, v]) => (
                <div key={l} className="flex justify-between py-1.5 border-b border-gray-50">
                  <span className="text-gray-500">{l}</span>
                  <span className="font-medium capitalize">{v}</span>
                </div>
              ))}
            </div>
            <button onClick={() => setSelected(null)} className="mt-4 w-full py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default TerritoryAnalytics;
