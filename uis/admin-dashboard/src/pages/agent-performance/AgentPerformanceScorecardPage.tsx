import React, { useState } from "react";
import { Award, Search, TrendingUp, Star } from "lucide-react";

const MOCK = {
  summary: { totalAgents: 248, topPerformers: 42, avgScore: 76, totalCommission: 14280000 },
  agents: [
    { name: "Adebayo Ogundimu", territory: "Lagos Island", role: "Senior Agent", score: 96, txnCount: 1840, commission: 284000 },
    { name: "Chioma Nwosu", territory: "Abuja FCT", role: "Senior Agent", score: 93, txnCount: 1720, commission: 261000 },
    { name: "Emeka Okafor", territory: "Port Harcourt", role: "Agent", score: 88, txnCount: 1520, commission: 228000 },
    { name: "Fatima Ibrahim", territory: "Kano", role: "Agent", score: 82, txnCount: 1280, commission: 192000 },
    { name: "Oluwaseun Bakare", territory: "Ibadan", role: "Agent", score: 74, txnCount: 1090, commission: 163000 },
    { name: "Amaka Eze", territory: "Enugu", role: "Agent", score: 68, txnCount: 920, commission: 138000 },
  ],
};

const scoreColor = (s: number) => s >= 80 ? "text-emerald-600" : s >= 60 ? "text-amber-600" : "text-red-600";
const scoreBg = (s: number) => s >= 80 ? "bg-emerald-100" : s >= 60 ? "bg-amber-100" : "bg-red-100";
const scoreBar = (s: number) => s >= 80 ? "bg-emerald-500" : s >= 60 ? "bg-amber-500" : "bg-red-500";

export default function AgentPerformanceScorecardPage() {
  const [data] = useState<typeof MOCK>(MOCK);
  const [search, setSearch] = useState("");

  const agents = data.agents.filter(a => !search || a.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Award className="w-7 h-7 text-blue-600" />Agent Performance Scorecard</h1>
        <p className="text-gray-500 text-sm mt-1">Track agent KPIs, transaction volumes, and commission performance</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Agents", value: data.summary.totalAgents, color: "text-gray-800" },
          { label: "Top Performers", value: data.summary.topPerformers, color: "text-emerald-600" },
          { label: "Avg Score", value: `${data.summary.avgScore}%`, color: "text-amber-600" },
          { label: "Total Commission", value: `₦${(data.summary.totalCommission / 1e6).toFixed(1)}M`, color: "text-blue-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Search className="w-4 h-4 text-gray-400" />
        <input placeholder="Search agents..." value={search} onChange={e => setSearch(e.target.value)} className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-64" />
      </div>

      <div className="space-y-3">
        {agents.map((agent, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 ${scoreBg(agent.score)}`}>
                <span className={`text-lg font-bold ${scoreColor(agent.score)}`}>{agent.score}</span>
              </div>
              <div>
                <p className="font-medium text-gray-800">{agent.name}</p>
                <p className="text-sm text-gray-500">{agent.territory} · {agent.role}</p>
                <div className="flex gap-4 mt-1 text-xs text-gray-400">
                  <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3" />{agent.txnCount.toLocaleString()} txns</span>
                  <span className="flex items-center gap-1"><Star className="w-3 h-3" />₦{agent.commission.toLocaleString()} earned</span>
                </div>
              </div>
            </div>
            <div className="text-right min-w-[120px]">
              <div className="w-32 bg-gray-100 rounded-full h-2">
                <div className={`h-2 rounded-full ${scoreBar(agent.score)}`} style={{ width: `${agent.score}%` }} />
              </div>
              <p className={`text-xs mt-1 ${scoreColor(agent.score)}`}>{agent.score >= 80 ? "Excellent" : agent.score >= 60 ? "Good" : "Needs Improvement"}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
