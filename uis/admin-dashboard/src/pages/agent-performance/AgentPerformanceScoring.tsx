import React, { useState, useMemo } from "react";
import { Trophy, TrendingUp, Award, Medal } from "lucide-react";

const mockAgents = [
  { agentId: "a1", agentCode: "AG-001", name: "Adebayo Ogundimu", overallScore: 92.5, tier: "platinum" as const, trend: "improving" as const, breakdown: { transactionVolume: { score: 95, weight: 0.25, raw: 1250 }, successRate: { score: 98.2, weight: 0.20, raw: 98.2 }, customerSatisfaction: { score: 90, weight: 0.15, raw: 4.5 }, complianceAdherence: { score: 88, weight: 0.20, raw: 88 }, uptimeReliability: { score: 96, weight: 0.10, raw: 168 }, responseTime: { score: 100, weight: 0.10, raw: 450 } } },
  { agentId: "a2", agentCode: "AG-002", name: "Chioma Nwosu", overallScore: 87.3, tier: "gold" as const, trend: "stable" as const, breakdown: { transactionVolume: { score: 82, weight: 0.25, raw: 980 }, successRate: { score: 96.5, weight: 0.20, raw: 96.5 }, customerSatisfaction: { score: 86, weight: 0.15, raw: 4.3 }, complianceAdherence: { score: 90, weight: 0.20, raw: 90 }, uptimeReliability: { score: 88, weight: 0.10, raw: 155 }, responseTime: { score: 75, weight: 0.10, raw: 2100 } } },
  { agentId: "a3", agentCode: "AG-003", name: "Emeka Okafor", overallScore: 78.1, tier: "gold" as const, trend: "improving" as const, breakdown: { transactionVolume: { score: 75, weight: 0.25, raw: 820 }, successRate: { score: 94.0, weight: 0.20, raw: 94.0 }, customerSatisfaction: { score: 80, weight: 0.15, raw: 4.0 }, complianceAdherence: { score: 72, weight: 0.20, raw: 72 }, uptimeReliability: { score: 82, weight: 0.10, raw: 142 }, responseTime: { score: 75, weight: 0.10, raw: 2500 } } },
  { agentId: "a4", agentCode: "AG-004", name: "Fatima Ibrahim", overallScore: 65.8, tier: "silver" as const, trend: "declining" as const, breakdown: { transactionVolume: { score: 60, weight: 0.25, raw: 620 }, successRate: { score: 88.0, weight: 0.20, raw: 88.0 }, customerSatisfaction: { score: 70, weight: 0.15, raw: 3.5 }, complianceAdherence: { score: 65, weight: 0.20, raw: 65 }, uptimeReliability: { score: 55, weight: 0.10, raw: 96 }, responseTime: { score: 50, weight: 0.10, raw: 4200 } } },
  { agentId: "a5", agentCode: "AG-005", name: "Oluwaseun Bakare", overallScore: 55.2, tier: "bronze" as const, trend: "stable" as const, breakdown: { transactionVolume: { score: 45, weight: 0.25, raw: 380 }, successRate: { score: 82.0, weight: 0.20, raw: 82.0 }, customerSatisfaction: { score: 60, weight: 0.15, raw: 3.0 }, complianceAdherence: { score: 58, weight: 0.20, raw: 58 }, uptimeReliability: { score: 50, weight: 0.10, raw: 88 }, responseTime: { score: 25, weight: 0.10, raw: 6000 } } },
];

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
