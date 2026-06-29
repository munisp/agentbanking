import { TrendingDown, RefreshCw, AlertTriangle, CheckCircle, BarChart3, Users, Zap } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const RISK_LABELS = { high: "High Risk", medium: "Medium Risk", low: "Low Risk" };
const RISK_COLORS = { high: "text-red-400 bg-red-900/30 border-red-700/50", medium: "text-amber-400 bg-amber-900/30 border-amber-700/50", low: "text-emerald-400 bg-emerald-900/30 border-emerald-700/50" };

const AgentChurnPrediction = () => {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [riskFilter, setRiskFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const [intervening, setIntervening] = useState(null);

  useEffect(() => { fetchPredictions(); }, []);

  const fetchPredictions = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/ai-ml/api/v1/churn-prediction/agents`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setPredictions(Array.isArray(data.predictions) ? data.predictions : Array.isArray(data) ? data : []);
      } else { setPredictions([]); }
    } catch { setPredictions([]); }
    finally { setLoading(false); }
  };

  const triggerIntervention = async (agentId) => {
    setIntervening(agentId);
    try {
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/retention/intervene`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, intervention_type: "outreach" }),
      });
      alert("Retention outreach triggered. The agent will be contacted.");
    } catch (err) { alert(err.message || "Intervention failed"); }
    finally { setIntervening(null); }
  };

  const filtered = predictions.filter(p => riskFilter === "all" || p.risk === riskFilter);
  const highRiskCount = predictions.filter(p => p.risk === "high").length;
  const avgChurnProb = predictions.length ? (predictions.reduce((s, p) => s + (p.churn_probability || 0), 0) / predictions.length * 100).toFixed(1) : 0;

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-600/20 rounded-lg"><TrendingDown className="w-6 h-6 text-red-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Churn Prediction</h1>
              <p className="text-gray-400 text-sm">ML model identifying agents at risk of going inactive</p>
            </div>
          </div>
          <button onClick={fetchPredictions} className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm hover:bg-gray-700 transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "High Risk Agents", value: highRiskCount, icon: AlertTriangle, color: "text-red-400" },
            { label: "Avg Churn Risk", value: `${avgChurnProb}%`, icon: BarChart3, color: "text-orange-400" },
            { label: "Total Monitored", value: predictions.length, icon: Users, color: "text-blue-400" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><span className="text-xs text-gray-400">{label}</span></div>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Risk Filter */}
        <div className="flex gap-2">
          {["all", "high", "medium", "low"].map(f => (
            <button key={f} onClick={() => setRiskFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors ${riskFilter === f ? (f === "all" ? "bg-blue-600 border-blue-500 text-white" : RISK_COLORS[f] + " border-current") : "bg-gray-50 border-gray-200 text-gray-400"}`}>
              {f} {f !== "all" && `(${predictions.filter(p => p.risk === f).length})`}
            </button>
          ))}
        </div>

        {/* Predictions List */}
        {loading ? (
          <div className="text-center py-12 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Running model...</div>
        ) : (
          <div className="space-y-3">
            {filtered.map((pred, i) => {
              const riskCls = RISK_COLORS[pred.risk] || RISK_COLORS.low;
              const pct = Math.round((pred.churn_probability || 0) * 100);
              return (
                <div key={pred.id || i} className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
                  <div className="p-4 flex items-center justify-between gap-4 cursor-pointer" onClick={() => setExpanded(expanded === pred.id ? null : pred.id)}>
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border ${riskCls}`}>{pct}%</div>
                      <div>
                        <p className="font-semibold">{pred.name}</p>
                        <p className="text-xs text-gray-500">{pred.id} · Last active: {pred.last_active}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-1 rounded-full border capitalize ${riskCls}`}>{RISK_LABELS[pred.risk]}</span>
                      <button onClick={e => { e.stopPropagation(); triggerIntervention(pred.id); }} disabled={intervening === pred.id}
                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors">
                        {intervening === pred.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                        Intervene
                      </button>
                    </div>
                  </div>

                  {/* Churn Bar */}
                  <div className="px-4 pb-1">
                    <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${pred.risk === "high" ? "bg-red-500" : pred.risk === "medium" ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>

                  {/* Expanded Factors */}
                  {expanded === pred.id && pred.factors && (
                    <div className="px-4 pb-4 pt-2 border-t border-gray-200 mt-2">
                      <p className="text-xs text-gray-400 mb-2">Risk Factors:</p>
                      <ul className="space-y-1">
                        {pred.factors.map((f, fi) => (
                          <li key={fi} className="flex items-center gap-2 text-xs text-gray-600">
                            <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />{f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentChurnPrediction;
