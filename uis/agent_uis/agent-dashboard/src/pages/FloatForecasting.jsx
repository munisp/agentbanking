import { TrendingUp, AlertTriangle, CheckCircle, RefreshCw, Banknote, ArrowUpRight, Clock, Filter } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const RISK_CONFIG = {
  critical: { color: "text-red-400", bg: "bg-red-900/30", border: "border-red-700/50", bar: "bg-red-500" },
  high:     { color: "text-orange-400", bg: "bg-orange-900/30", border: "border-orange-700/50", bar: "bg-orange-500" },
  medium:   { color: "text-yellow-400", bg: "bg-yellow-900/30", border: "border-yellow-700/50", bar: "bg-yellow-500" },
  low:      { color: "text-emerald-400", bg: "bg-emerald-900/30", border: "border-emerald-700/50", bar: "bg-emerald-500" },
};

const FloatForecasting = () => {
  const [period, setPeriod] = useState("7");
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [riskFilter, setRiskFilter] = useState("all");
  const [replenishTarget, setReplenishTarget] = useState(null);
  const [replenishAmt, setReplenishAmt] = useState("");
  const [replenishing, setReplenishing] = useState(false);

  useEffect(() => { fetchForecast(); }, [period]);

  const fetchForecast = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/network-operations/api/v1/cash-positions/forecast?days=${period}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setAgents(Array.isArray(data.agents) ? data.agents : Array.isArray(data) ? data : []);
      } else {
        setAgents([]);
      }
    } catch { setAgents([]); }
    finally { setLoading(false); }
  };

  const triggerReplenishment = async () => {
    if (!replenishTarget || !replenishAmt) return;
    setReplenishing(true);
    try {
      await fetch(`${CORE_BANKING_URL}/float-management/api/v1/replenishment`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: replenishTarget.id, amount: parseFloat(replenishAmt), priority: replenishTarget.risk === "critical" ? "urgent" : "normal" }),
      });
      setReplenishTarget(null);
      setReplenishAmt("");
      fetchForecast();
    } catch (err) { alert(err.message); }
    finally { setReplenishing(false); }
  };

  const filtered = agents.filter(a => riskFilter === "all" || a.risk === riskFilter);
  const criticalCount = agents.filter(a => a.risk === "critical").length;
  const highCount = agents.filter(a => a.risk === "high").length;
  const totalShortfall = agents.reduce((s, a) => s + (a.shortfall || 0), 0);

  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 rounded-lg"><TrendingUp className="w-6 h-6 text-blue-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Float Forecasting</h1>
              <p className="text-gray-400 text-sm">Predict agent float shortfalls and trigger replenishments</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Forecast period:</span>
            {["7", "14", "30"].map(d => (
              <button key={d} onClick={() => setPeriod(d)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${period === d ? "bg-blue-600 text-white" : "bg-gray-50 text-gray-400 hover:bg-gray-700"}`}>
                {d}d
              </button>
            ))}
            <button onClick={fetchForecast} className="p-1.5 bg-gray-50 hover:bg-gray-700 rounded-lg transition-colors">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Critical Risk", value: criticalCount, color: "text-red-400" },
            { label: "High Risk", value: highCount, color: "text-orange-400" },
            { label: "Total Shortfall", value: `₦${(totalShortfall / 1000).toFixed(0)}K`, color: "text-yellow-400" },
            { label: "Agents Monitored", value: agents.length, color: "text-blue-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
              <p className="text-xs text-gray-400">{label}</p>
              <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Risk Filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-gray-500" />
          {["all", "critical", "high", "medium", "low"].map(f => {
            const cfg = RISK_CONFIG[f] || { color: "text-gray-400" };
            return (
              <button key={f} onClick={() => setRiskFilter(f)}
                className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-colors border ${riskFilter === f ? (f === "all" ? "bg-blue-600 border-blue-500 text-white" : `${cfg.bg} ${cfg.border} ${cfg.color}`) : "bg-gray-50 border-gray-200 text-gray-400 hover:border-gray-500"}`}>
                {f} {f !== "all" && `(${agents.filter(a => a.risk === f).length})`}
              </button>
            );
          })}
        </div>

        {/* Agent Cards */}
        {loading ? (
          <div className="text-center py-12 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Calculating forecasts...</div>
        ) : (
          <div className="space-y-3">
            {filtered.map((agent, i) => {
              const cfg = RISK_CONFIG[agent.risk] || RISK_CONFIG.low;
              const coveragePct = Math.min(100, (agent.currentFloat / agent.predictedNeed) * 100);
              return (
                <div key={agent.id || i} className={`border rounded-xl p-4 ${cfg.border} ${cfg.bg}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-semibold">{agent.name}</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.border} ${cfg.color} bg-black/20 capitalize`}>{agent.risk}</span>
                      </div>
                      <p className="text-xs text-gray-400">{agent.id} · {agent.location}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-gray-400">Shortfall</p>
                      <p className={`text-lg font-bold ${agent.shortfall > 0 ? "text-red-400" : "text-emerald-400"}`}>
                        {agent.shortfall > 0 ? `₦${agent.shortfall.toLocaleString()}` : "Sufficient"}
                      </p>
                    </div>
                  </div>

                  {/* Coverage bar */}
                  <div className="mt-3 mb-2">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Current: ₦{agent.currentFloat.toLocaleString()}</span>
                      <span>Predicted need: ₦{agent.predictedNeed.toLocaleString()}</span>
                    </div>
                    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${cfg.bar}`} style={{ width: `${coveragePct}%` }} />
                    </div>
                    <p className="text-right text-xs text-gray-600 mt-0.5">{coveragePct.toFixed(0)}% covered</p>
                  </div>

                  <div className="flex items-center justify-between text-xs text-gray-500 mt-1">
                    <span><Clock className="w-3 h-3 inline mr-1" />Last replenished: {agent.lastReplenished}</span>
                    <span>Avg daily vol: ₦{(agent.avgDailyVolume || 0).toLocaleString()}</span>
                    {agent.shortfall > 0 && (
                      <button onClick={() => { setReplenishTarget(agent); setReplenishAmt(String(agent.shortfall)); }}
                        className="flex items-center gap-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-xs font-medium transition-colors">
                        <Banknote className="w-3 h-3" /> Replenish
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Replenishment Modal */}
        {replenishTarget && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-50 border border-gray-200 rounded-2xl p-6 w-full max-w-md">
              <h2 className="font-bold text-lg mb-1">Trigger Replenishment</h2>
              <p className="text-gray-400 text-sm mb-4">{replenishTarget.name} · {replenishTarget.location}</p>
              <div className="mb-4">
                <label className="block text-xs text-gray-400 mb-1">Amount (₦)</label>
                <input type="number" value={replenishAmt} onChange={e => setReplenishAmt(e.target.value)}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-3 text-white text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="flex gap-2">
                <button onClick={triggerReplenishment} disabled={replenishing}
                  className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
                  {replenishing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ArrowUpRight className="w-4 h-4" />}
                  {replenishing ? "Sending..." : "Confirm Replenishment"}
                </button>
                <button onClick={() => { setReplenishTarget(null); setReplenishAmt(""); }} className="px-4 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FloatForecasting;
