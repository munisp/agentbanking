import {
  Award,
  Crown,
  Medal,
  RefreshCw,
  Star,
  Trophy,
  Users,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { gamificationApi, loyaltyApi } from "../utils/api";

const TIER_CONFIG = {
  bronze: { color: "text-orange-600", bg: "bg-orange-100", border: "border-orange-200", label: "Bronze" },
  silver: { color: "text-gray-500", bg: "bg-gray-100", border: "border-gray-200", label: "Silver" },
  gold: { color: "text-yellow-600", bg: "bg-yellow-100", border: "border-yellow-200", label: "Gold" },
  platinum: { color: "text-cyan-600", bg: "bg-cyan-100", border: "border-cyan-200", label: "Platinum" },
  diamond: { color: "text-purple-600", bg: "bg-purple-100", border: "border-purple-200", label: "Diamond" },
};

export default function Achievements() {
  const agentId = localStorage.getItem("agentId") || localStorage.getItem("keycloakId");

  const [myAccount, setMyAccount] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [accountData, lbData] = await Promise.allSettled([
        agentId ? loyaltyApi.getAccount(agentId) : Promise.reject("No agent ID"),
        gamificationApi.getLeaderboard(20),
      ]);

      if (accountData.status === "fulfilled") {
        setMyAccount(accountData.value);
        if (agentId) {
          const actData = await loyaltyApi.getActivities(agentId, { limit: 20 }).catch(() => []);
          setActivities(Array.isArray(actData) ? actData : []);
        }
      }
      if (lbData.status === "fulfilled") {
        const data = lbData.value;
        setLeaderboard(Array.isArray(data) ? data : data?.agents ?? data?.leaderboard ?? []);
      }
    } catch (e) {
      setError(e?.message ?? "Failed to load achievements");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const tier = myAccount?.tier ?? myAccount?.tier_name ?? "bronze";
  const tierConfig = TIER_CONFIG[tier] ?? TIER_CONFIG.bronze;
  const points = myAccount?.points ?? myAccount?.total_points ?? 0;

  const myRank = leaderboard.findIndex(
    (a) => a.agent_id === agentId || a.id === agentId
  );

  const TIERS_ORDER = ["bronze", "silver", "gold", "platinum", "diamond"];
  const currentTierIdx = TIERS_ORDER.indexOf(tier);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-500" /> Achievements
          </h1>
          <p className="text-gray-500 text-sm mt-1">Your points, badges, and leaderboard ranking</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {/* Tier Card */}
      {!loading && myAccount && (
        <div className={`rounded-xl border-2 p-6 ${tierConfig.bg} ${tierConfig.border}`}>
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-full ${tierConfig.bg} border-2 ${tierConfig.border} flex items-center justify-center`}>
              <Trophy className={`w-8 h-8 ${tierConfig.color}`} />
            </div>
            <div className="flex-1">
              <p className={`text-2xl font-bold ${tierConfig.color}`}>{tierConfig.label}</p>
              <p className="text-gray-600 text-lg">{points.toLocaleString()} points</p>
              {myRank >= 0 && (
                <p className="text-sm text-gray-500 mt-0.5">Leaderboard rank: #{myRank + 1}</p>
              )}
            </div>
            <div className="text-right">
              {myAccount.points_to_next_tier && (
                <>
                  <p className="text-sm text-gray-600">Next tier</p>
                  <p className={`font-bold ${tierConfig.color}`}>
                    {myAccount.points_to_next_tier.toLocaleString()} pts needed
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Tier progress bar */}
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              {TIERS_ORDER.map((t, i) => (
                <span key={t} className={i <= currentTierIdx ? `font-semibold ${tierConfig.color}` : ""}>
                  {TIER_CONFIG[t].label}
                </span>
              ))}
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className={`h-3 rounded-full transition-all ${
                  tier === "diamond" ? "bg-purple-500" :
                  tier === "platinum" ? "bg-cyan-500" :
                  tier === "gold" ? "bg-yellow-500" :
                  tier === "silver" ? "bg-gray-400" : "bg-orange-500"
                }`}
                style={{ width: `${((currentTierIdx + 1) / TIERS_ORDER.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="h-28 bg-gray-200 rounded animate-pulse" />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {[
          { key: "overview", label: "Overview" },
          { key: "leaderboard", label: "Leaderboard" },
          { key: "history", label: "Points History" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? "border-yellow-500 text-yellow-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { label: "Total Points", value: points.toLocaleString(), icon: Star, color: "text-yellow-500 bg-yellow-50" },
            {
              label: "Leaderboard Rank",
              value: myRank >= 0 ? `#${myRank + 1}` : "—",
              icon: Trophy,
              color: "text-blue-500 bg-blue-50",
            },
            {
              label: "Current Tier",
              value: tierConfig.label,
              icon: Award,
              color: `${tierConfig.color} ${tierConfig.bg}`,
            },
          ].map((s) => (
            <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-5">
              <div className={`w-10 h-10 rounded-lg ${s.color} flex items-center justify-center mb-3`}>
                <s.icon className="w-5 h-5" />
              </div>
              {loading ? (
                <div className="h-8 bg-gray-200 rounded animate-pulse mb-1" />
              ) : (
                <p className="text-2xl font-bold text-gray-900">{s.value}</p>
              )}
              <p className="text-sm text-gray-500">{s.label}</p>
            </div>
          ))}

          {/* Tier Badges */}
          <div className="md:col-span-3 bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Medal className="w-5 h-5 text-purple-500" /> Tier Badges
            </h3>
            <div className="grid grid-cols-5 gap-3">
              {TIERS_ORDER.map((t, i) => {
                const cfg = TIER_CONFIG[t];
                const earned = i <= currentTierIdx;
                return (
                  <div
                    key={t}
                    className={`rounded-xl p-4 text-center border-2 transition-all ${
                      earned ? `${cfg.bg} ${cfg.border}` : "bg-gray-50 border-gray-200 opacity-40"
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-full mx-auto flex items-center justify-center mb-2 ${cfg.bg}`}>
                      <Trophy className={`w-5 h-5 ${cfg.color}`} />
                    </div>
                    <p className={`text-sm font-semibold ${earned ? cfg.color : "text-gray-400"}`}>{cfg.label}</p>
                    {earned && <p className="text-xs text-gray-500 mt-0.5">Achieved</p>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Leaderboard tab */}
      {activeTab === "leaderboard" && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-200 flex items-center gap-2">
            <Users className="w-5 h-5 text-gray-500" />
            <span className="font-medium text-gray-900">Agent Leaderboard</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3 font-medium text-gray-700">Rank</th>
                <th className="text-left p-3 font-medium text-gray-700">Agent</th>
                <th className="text-left p-3 font-medium text-gray-700">Points</th>
                <th className="text-left p-3 font-medium text-gray-700">Tier</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-t">
                      <td colSpan={4} className="p-3"><div className="h-8 bg-gray-200 rounded animate-pulse" /></td>
                    </tr>
                  ))
                : leaderboard.length === 0
                ? (
                  <tr>
                    <td colSpan={4} className="p-12 text-center text-gray-400">No leaderboard data yet</td>
                  </tr>
                )
                : leaderboard.map((a, idx) => {
                    const isMe = a.agent_id === agentId || a.id === agentId;
                    const agentTier = a.tier ?? a.tier_name ?? "bronze";
                    const agentCfg = TIER_CONFIG[agentTier] ?? TIER_CONFIG.bronze;
                    return (
                      <tr
                        key={a.agent_id ?? a.id ?? idx}
                        className={`border-t ${isMe ? "bg-yellow-50" : "hover:bg-gray-50"}`}
                      >
                        <td className="p-3">
                          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                            idx === 0 ? "bg-yellow-100 text-yellow-700" :
                            idx === 1 ? "bg-gray-100 text-gray-600" :
                            idx === 2 ? "bg-orange-100 text-orange-700" :
                            "bg-gray-50 text-gray-500"
                          }`}>
                            {idx + 1}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="font-medium text-gray-900">
                            {a.agent_name ?? a.name ?? `Agent ${idx + 1}`}
                            {isMe && <span className="ml-2 text-xs text-yellow-600 font-semibold">(You)</span>}
                          </span>
                        </td>
                        <td className="p-3 font-bold text-yellow-600">
                          {Number(a.points ?? a.total_points ?? 0).toLocaleString()}
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs border font-medium ${agentCfg.bg} ${agentCfg.color} ${agentCfg.border}`}>
                            {agentCfg.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>
      )}

      {/* Points History tab */}
      {activeTab === "history" && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">Points History</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="p-4"><div className="h-8 bg-gray-200 rounded animate-pulse" /></div>
                ))
              : activities.length === 0
              ? (
                <div className="p-12 text-center text-gray-400">
                  <Star className="w-10 h-10 mx-auto mb-3" />
                  <p>No points activity yet</p>
                </div>
              )
              : activities.map((a, i) => (
                  <div key={a.id ?? i} className="p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900 text-sm">{a.description ?? a.activity_type ?? "Points activity"}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {a.created_at ? new Date(a.created_at).toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" }) : "—"}
                      </p>
                    </div>
                    <span className={`font-bold text-sm ${Number(a.points_change ?? a.points ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {Number(a.points_change ?? a.points ?? 0) >= 0 ? "+" : ""}
                      {Number(a.points_change ?? a.points ?? 0).toLocaleString()} pts
                    </span>
                  </div>
                ))}
          </div>
        </div>
      )}
    </div>
  );
}
