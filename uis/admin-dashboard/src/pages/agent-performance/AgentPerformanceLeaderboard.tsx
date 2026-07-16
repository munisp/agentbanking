import React, { useState, useEffect } from "react";
import { Trophy, RefreshCw, TrendingUp, Users, Medal, Star, AlertTriangle } from "lucide-react";
import { performanceApi } from "../../utils/api";

const FALLBACK_MOCK = {
  stats: { totalAgents: 248, topPerformers: 42, avgScore: 76, totalCommission: 14280000 },
  leaders: [
    { rank: 1, name: "Adebayo Ogundimu", code: "AG-001", score: 96, txns: 1840, commission: 284000, tier: "Platinum" },
    { rank: 2, name: "Chioma Nwosu", code: "AG-002", score: 93, txns: 1720, commission: 261000, tier: "Platinum" },
    { rank: 3, name: "Emeka Okafor", code: "AG-003", score: 91, txns: 1650, commission: 248000, tier: "Gold" },
    { rank: 4, name: "Fatima Ibrahim", code: "AG-004", score: 88, txns: 1520, commission: 228000, tier: "Gold" },
    { rank: 5, name: "Oluwaseun Bakare", code: "AG-005", score: 85, txns: 1410, commission: 211000, tier: "Gold" },
    { rank: 6, name: "Amaka Eze", code: "AG-006", score: 82, txns: 1280, commission: 192000, tier: "Silver" },
    { rank: 7, name: "Chukwuemeka Ike", code: "AG-007", score: 79, txns: 1180, commission: 177000, tier: "Silver" },
    { rank: 8, name: "Ngozi Obi", code: "AG-008", score: 77, txns: 1090, commission: 163000, tier: "Silver" },
  ],
};

const TIER_COLORS: Record<string, string> = {
  Platinum: "bg-purple-100 text-purple-700",
  Gold: "bg-amber-100 text-amber-700",
  Silver: "bg-gray-100 text-gray-600",
  Bronze: "bg-orange-100 text-orange-700",
};

/** Derive tier from total volume or commission rank */
function deriveTier(rank: number): string {
  if (rank <= 2) return "Platinum";
  if (rank <= 5) return "Gold";
  if (rank <= 10) return "Silver";
  return "Bronze";
}

/** Map a leaderboard API record to the shape this component uses */
function mapApiLeader(item: any, index: number) {
  const txns = Number(item.total_transactions ?? item.tx_count ?? item.txns ?? 0);
  const commission = Number(item.total_commission ?? item.commission ?? 0);
  const volume = Number(item.total_volume ?? item.volume ?? 0);
  // Derive a 0-100 score from volume if not provided directly
  const score = Number(item.score ?? item.performance_score ?? 0);
  return {
    rank: index + 1,
    name: item.agent_name ?? item.name ?? `Agent ${index + 1}`,
    code: item.agent_id ?? item.id ?? `AG-${String(index + 1).padStart(3, "0")}`,
    score,
    txns,
    commission,
    volume,
    tier: item.tier ?? deriveTier(index + 1),
  };
}

export default function AgentPerformanceLeaderboard() {
  const [liveData, setLiveData] = useState<typeof FALLBACK_MOCK | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setIsLoading(true);
    setError(null);
    performanceApi
      .getLeaderboard({ days: 30, limit: 50 })
      .then((resp: any) => {
        const rawList: any[] = Array.isArray(resp)
          ? resp
          : resp?.agents ?? resp?.leaderboard ?? resp?.results ?? resp?.data ?? [];

        if (rawList.length === 0) {
          setLiveData(null);
          return;
        }

        const leaders = rawList.map(mapApiLeader);
        const totalCommission = leaders.reduce((s, l) => s + l.commission, 0);
        const avgScore = leaders.length > 0
          ? Math.round(leaders.reduce((s, l) => s + l.score, 0) / leaders.length)
          : 0;
        const topPerformers = leaders.filter(l => l.score >= 80).length;

        setLiveData({
          stats: {
            totalAgents: rawList.length,
            topPerformers,
            avgScore,
            totalCommission,
          },
          leaders,
        });
      })
      .catch(() => {
        setError("Performance service unavailable");
        setLiveData(null);
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const data = liveData ?? FALLBACK_MOCK;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Trophy className="w-7 h-7 text-amber-500" />Agent Leaderboard
            </h1>
            {liveData && !isLoading ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                Live data
              </span>
            ) : null}
          </div>
          <p className="text-gray-500 text-sm mt-1">Gamified real-time agent performance rankings</p>
        </div>
        <button
          onClick={loadData}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Warning: Showing cached data. Performance service unavailable.
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Agents", value: isLoading ? "…" : data.stats.totalAgents, color: "text-gray-800", icon: Users },
          { label: "Top Performers", value: isLoading ? "…" : data.stats.topPerformers, color: "text-amber-600", icon: Trophy },
          { label: "Avg Score", value: isLoading ? "…" : `${data.stats.avgScore}%`, color: "text-blue-600", icon: Star },
          { label: "Total Commission", value: isLoading ? "…" : `₦${(data.stats.totalCommission / 1e6).toFixed(1)}M`, color: "text-emerald-600", icon: TrendingUp },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><p className="text-xs text-gray-500">{label}</p></div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Rankings</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center">
              <div className="inline-block h-8 w-8 rounded-full border-4 border-amber-400 border-t-transparent animate-spin" />
              <p className="text-gray-400 text-sm mt-3">Loading leaderboard…</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  {["#", "Agent", "Tier", "Score", "Transactions", "Commission"].map(h => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.leaders.map(a => (
                  <tr key={a.rank} className="hover:bg-gray-50/50">
                    <td className="py-3 px-4">
                      {a.rank <= 3 ? (
                        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                          a.rank === 1 ? "bg-amber-100 text-amber-700" :
                          a.rank === 2 ? "bg-gray-200 text-gray-600" :
                          "bg-orange-100 text-orange-700"
                        }`}><Medal className="w-3.5 h-3.5" /></span>
                      ) : <span className="text-gray-400 font-mono pl-1">{a.rank}</span>}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-gray-800">{a.name}</div>
                      <div className="text-xs text-gray-400">{a.code}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${TIER_COLORS[a.tier] ?? "bg-gray-100 text-gray-600"}`}>{a.tier}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-100 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${a.score >= 90 ? "bg-emerald-500" : a.score >= 75 ? "bg-amber-500" : "bg-red-500"}`}
                            style={{ width: `${Math.min(a.score, 100)}%` }}
                          />
                        </div>
                        <span className="font-mono text-xs text-gray-700">{a.score || "—"}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-600 font-mono">{a.txns.toLocaleString()}</td>
                    <td className="py-3 px-4 text-emerald-600 font-mono">₦{a.commission.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
