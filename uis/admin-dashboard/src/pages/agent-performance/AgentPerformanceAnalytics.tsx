import React, { useState } from "react";
import { BarChart3, RefreshCw, TrendingUp, Users, Star, Target } from "lucide-react";

const MOCK = {
  stats: { totalAgents: 248, activeAgents: 210, avgScore: 76, topPerformer: "Adebayo Ogundimu" },
  monthly: [
    { month: "Aug", avgScore: 71, txns: 28400, commission: 1840000 },
    { month: "Sep", avgScore: 73, txns: 31200, commission: 2010000 },
    { month: "Oct", avgScore: 74, txns: 33800, commission: 2180000 },
    { month: "Nov", avgScore: 75, txns: 36100, commission: 2340000 },
    { month: "Dec", avgScore: 78, txns: 41200, commission: 2680000 },
    { month: "Jan", avgScore: 76, txns: 38900, commission: 2520000 },
  ],
  distribution: [
    { label: "Platinum (90+)", count: 18, pct: 7 },
    { label: "Gold (75-89)", count: 72, pct: 29 },
    { label: "Silver (60-74)", count: 98, pct: 40 },
    { label: "Bronze (<60)", count: 60, pct: 24 },
  ],
};

export default function AgentPerformanceAnalytics() {
  const [data] = useState<typeof MOCK>(MOCK);
  const [tab, setTab] = useState<"overview" | "trends">("overview");

  const maxScore = Math.max(...data.monthly.map(m => m.avgScore));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><BarChart3 className="w-7 h-7 text-blue-600" />Agent Performance Analytics</h1>
          <p className="text-gray-500 text-sm mt-1">Comprehensive scoring with KPIs and benchmarking</p>
        </div>
        <button onClick={() => {}} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" />Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Agents", value: data.stats.totalAgents, color: "text-gray-800", icon: Users },
          { label: "Active Agents", value: data.stats.activeAgents, color: "text-emerald-600", icon: Users },
          { label: "Avg Score", value: `${data.stats.avgScore}%`, color: "text-blue-600", icon: Target },
          { label: "Top Performer", value: data.stats.topPerformer, color: "text-amber-600", icon: Star },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><p className="text-xs text-gray-500">{label}</p></div>
            <p className={`text-xl font-bold truncate ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="flex border-b border-gray-200 gap-1">
        {(["overview", "trends"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-colors ${tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>{t}</button>
        ))}
      </div>

      {tab === "overview" && (
        <div>
          <h2 className="font-semibold text-gray-800 mb-3">Score Distribution</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-4">
            {data.distribution.map(d => (
              <div key={d.label} className="flex items-center gap-4">
                <p className="text-sm text-gray-700 w-36 shrink-0">{d.label}</p>
                <div className="flex-1 bg-gray-100 rounded-full h-4">
                  <div className="h-4 rounded-full bg-blue-500 flex items-center justify-end pr-2 transition-all" style={{ width: `${d.pct}%` }}>
                    <span className="text-[10px] text-white font-bold">{d.pct}%</span>
                  </div>
                </div>
                <span className="text-sm text-gray-500 w-12 text-right">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "trends" && (
        <div>
          <h2 className="font-semibold text-gray-800 mb-3">Monthly Performance Trend</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-end gap-2 h-40">
              {data.monthly.map(m => (
                <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-gray-500">{m.avgScore}</span>
                  <div className="w-full bg-blue-500 rounded-t-sm transition-all" style={{ height: `${(m.avgScore / maxScore) * 100}px` }} />
                  <span className="text-xs text-gray-400">{m.month}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-gray-100 pt-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                {data.monthly.slice(-3).map(m => (
                  <div key={m.month}>
                    <p className="text-xs text-gray-400">{m.month}</p>
                    <p className="font-semibold text-gray-700">{m.txns.toLocaleString()} txns</p>
                    <p className="text-xs text-emerald-600">₦{(m.commission / 1e6).toFixed(1)}M</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
