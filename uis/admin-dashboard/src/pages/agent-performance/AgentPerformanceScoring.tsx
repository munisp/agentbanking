import React, { useState, useMemo } from "react";
import { Trophy, TrendingUp, Award, Medal } from "lucide-react";

// No live scoring API is wired to this page yet — render an honest empty
// state instead of fabricated agent rows.
const mockAgents: any[] = [];

const TIER_COLORS: Record<string, string> = {
  platinum: "text-purple-600", gold: "text-amber-600", silver: "text-gray-500", bronze: "text-orange-600",
};
const TIER_BG: Record<string, string> = {
  platinum: "border-purple-200", gold: "border-amber-200", silver: "border-gray-200", bronze: "border-orange-200",
};

export default function AgentPerformanceScoring() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const selected = useMemo(() => mockAgents.find(a => a.agentId === selectedAgent), [selectedAgent]);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Trophy className="w-7 h-7 text-amber-500" />Agent Performance Scoring
        </h1>
        <p className="text-sm text-gray-500 mt-1">KPI-based scoring dashboard for agent performance evaluation</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(["platinum", "gold", "silver", "bronze"] as const).map(tier => (
          <div key={tier} className={`bg-white rounded-xl border p-4 shadow-sm text-center ${TIER_BG[tier]}`}>
            <Medal className={`w-6 h-6 mx-auto mb-1 ${TIER_COLORS[tier]}`} />
            <p className="text-xl font-bold text-gray-800">{mockAgents.filter(a => a.tier === tier).length}</p>
            <p className="text-xs text-gray-500 capitalize">{tier} Agents</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <Award className="w-5 h-5 text-gray-500" />
          <h2 className="font-semibold text-gray-800">Agent Leaderboard</h2>
        </div>
        <div className="divide-y divide-gray-50">
          {mockAgents.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">
              No performance data available.
            </p>
          )}
          {mockAgents.map((agent, idx) => (
            <div
              key={agent.agentId}
              className={`flex items-center gap-4 p-4 cursor-pointer transition-colors ${selectedAgent === agent.agentId ? "bg-blue-50" : "hover:bg-gray-50/50"}`}
              onClick={() => setSelectedAgent(agent.agentId === selectedAgent ? null : agent.agentId)}
            >
              <div className="text-2xl font-bold text-gray-300 w-8 text-center">#{idx + 1}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-800">{agent.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{agent.agentCode}</span>
                  <span className={`text-xs capitalize font-medium ${TIER_COLORS[agent.tier]}`}>{agent.tier}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-full max-w-xs bg-gray-100 rounded-full h-2">
                    <div className={`h-2 rounded-full ${agent.overallScore >= 80 ? "bg-emerald-500" : agent.overallScore >= 60 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${agent.overallScore}%` }} />
                  </div>
                  <span className="text-sm font-mono text-gray-600">{agent.overallScore.toFixed(1)}</span>
                </div>
              </div>
              <div className={`text-xs ${agent.trend === "improving" ? "text-emerald-600" : agent.trend === "declining" ? "text-red-500" : "text-gray-400"}`}>
                {agent.trend === "improving" ? "↑ " : agent.trend === "declining" ? "↓ " : "→ "}{agent.trend}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selected && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="font-semibold text-gray-800">KPI Breakdown — {selected.name}</h2>
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(selected.breakdown).map(([key, kpi]) => (
              <div key={key} className="p-3 rounded-xl bg-gray-50 border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700 capitalize">{key.replace(/([A-Z])/g, " $1").trim()}</span>
                  <span className="text-xs text-gray-400">Weight: {(kpi.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-1">
                  <div className={`h-2 rounded-full ${kpi.score >= 80 ? "bg-emerald-500" : kpi.score >= 60 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${kpi.score}%` }} />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Score: {kpi.score.toFixed(1)}</span>
                  <span>Raw: {typeof kpi.raw === "number" ? kpi.raw.toLocaleString() : kpi.raw}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
