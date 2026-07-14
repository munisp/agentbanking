import { MapPin, RefreshCw, Search, TrendingUp, Users, Activity, AlertTriangle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const STATUS_CONFIG = {
  active:      { label: "Active",      color: "text-emerald-400", bg: "bg-emerald-900/30", border: "border-emerald-700/50", bar: "bg-emerald-500" },
  warning:     { label: "Warning",     color: "text-amber-400",   bg: "bg-amber-900/30",   border: "border-amber-700/50",   bar: "bg-amber-500" },
  underserved: { label: "Underserved", color: "text-red-400",     bg: "bg-red-900/30",     border: "border-red-700/50",     bar: "bg-red-500" },
};

const TerritoryHeatmap = () => {
  const [territories, setTerritories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => { fetchTerritories(); }, []);

  const fetchTerritories = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/geospatial/api/v1/territories/heatmap`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setTerritories(Array.isArray(data.territories) ? data.territories : Array.isArray(data) ? data : []);
      } else { setTerritories([]); }
    } catch { setTerritories([]); }
    finally { setLoading(false); }
  };

  const filtered = territories
    .filter(t => statusFilter === "all" || t.status === statusFilter)
    .filter(t => !search || t.name.toLowerCase().includes(search.toLowerCase()) || t.id.toLowerCase().includes(search.toLowerCase()));

  const kpis = [
    { label: "Active Territories", value: territories.filter(t => t.status === "active").length, icon: MapPin, color: "text-blue-400" },
    { label: "Coverage Avg", value: `${Math.round(territories.reduce((s, t) => s + (t.coverage || 0), 0) / Math.max(1, territories.length))}%`, icon: Activity, color: "text-emerald-400" },
    { label: "Total Volume", value: `₦${(territories.reduce((s, t) => s + (t.volume || 0), 0) / 1e6).toFixed(1)}M`, icon: TrendingUp, color: "text-purple-400" },
    { label: "Underserved", value: territories.filter(t => t.status === "underserved").length, icon: AlertTriangle, color: "text-red-400" },
  ];

  return (
    <div className="min-h-screen bg-[#0a0e17] text-white p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <MapPin className="w-7 h-7 text-blue-400" />
            <div>
              <h1 className="text-2xl font-bold">Territory Heatmap</h1>
              <p className="text-gray-400 text-sm">Geographic performance visualization across agent territories</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchTerritories} className="flex items-center gap-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:bg-gray-700 transition-colors">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {kpis.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="text-xs text-gray-400">{label}</span>
              </div>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-700">
          {["overview", "details", "performance"].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 capitalize transition-colors ${activeTab === t ? "border-blue-500 text-blue-400" : "border-transparent text-gray-500 hover:text-gray-300"}`}>
              {t}
            </button>
          ))}
        </div>

        {/* Search & Filter */}
        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search territories..."
              className="w-full pl-9 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex gap-1">
            {["all", "active", "warning", "underserved"].map(f => {
              const cfg = STATUS_CONFIG[f] || {};
              return (
                <button key={f} onClick={() => setStatusFilter(f)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium capitalize transition-colors border ${statusFilter === f ? (f === "all" ? "bg-blue-600 border-blue-500 text-white" : `${cfg.bg} ${cfg.border} ${cfg.color}`) : "bg-gray-800 border-gray-700 text-gray-400"}`}>
                  {f}
                </button>
              );
            })}
          </div>
        </div>

        {/* Heatmap Visual (CSS-based grid) */}
        {activeTab === "overview" && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
            <h3 className="font-medium mb-4 text-sm text-gray-300">Territory Heat Grid</h3>
            <div className="grid grid-cols-5 gap-2">
              {filtered.map((t, i) => {
                const intensity = Math.round((t.volume || 0) / 1e5);
                const opacity = Math.min(90, Math.max(20, intensity));
                const cfg = STATUS_CONFIG[t.status] || STATUS_CONFIG.active;
                return (
                  <div key={t.id || i} title={`${t.name}: ₦${(t.volume || 0).toLocaleString()}`}
                    className={`aspect-square rounded-lg border ${cfg.border} flex flex-col items-center justify-center cursor-pointer hover:scale-105 transition-transform text-center p-1`}
                    style={{ background: `rgba(59,130,246,${opacity / 100})` }}>
                    <p className="text-xs font-bold text-white">{t.name.split("–")[0].trim()}</p>
                    <p className="text-xs text-blue-200 mt-0.5">{t.agents}a</p>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-gray-600 mt-3">Colour intensity represents transaction volume. Hover for details.</p>
          </div>
        )}

        {/* Details Table */}
        {(activeTab === "details" || activeTab === "performance") && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 bg-gray-800">
                  <th className="text-left py-3 px-4 text-gray-400 font-medium">Territory</th>
                  <th className="text-left py-3 px-4 text-gray-400 font-medium">Agents</th>
                  <th className="text-left py-3 px-4 text-gray-400 font-medium">Volume</th>
                  <th className="text-left py-3 px-4 text-gray-400 font-medium">Coverage</th>
                  {activeTab === "performance" && <th className="text-left py-3 px-4 text-gray-400 font-medium">Performance</th>}
                  <th className="text-left py-3 px-4 text-gray-400 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {loading ? (
                  <tr><td colSpan={6} className="text-center py-10 text-gray-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto" /></td></tr>
                ) : filtered.map((t, i) => {
                  const cfg = STATUS_CONFIG[t.status] || STATUS_CONFIG.active;
                  return (
                    <tr key={t.id || i} className="hover:bg-gray-700/30 transition-colors">
                      <td className="py-3 px-4">
                        <p className="font-medium">{t.name}</p>
                        <p className="text-xs text-gray-500">{t.id}</p>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1"><Users className="w-3 h-3 text-gray-400" />{t.agents}</div>
                      </td>
                      <td className="py-3 px-4">₦{(t.volume / 1e6).toFixed(1)}M</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div className={`h-full ${cfg.bar}`} style={{ width: `${t.coverage}%` }} />
                          </div>
                          <span>{t.coverage}%</span>
                        </div>
                      </td>
                      {activeTab === "performance" && (
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                              <div className="h-full bg-purple-500" style={{ width: `${t.performance}%` }} />
                            </div>
                            <span>{t.performance}%</span>
                          </div>
                        </td>
                      )}
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2 py-1 rounded-full ${cfg.bg} ${cfg.color} ${cfg.border} border capitalize`}>{t.status}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TerritoryHeatmap;
