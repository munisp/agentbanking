import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trophy, RefreshCw, Medal, Target, Award, Star } from "lucide-react";
import { gamificationApi } from "../../utils/api";

const TIER_COLORS: Record<string, string> = {
  bronze: "bg-orange-800/30 text-orange-400 border-orange-600/30",
  silver: "bg-zinc-500/30 text-zinc-300 border-zinc-500/30",
  gold: "bg-yellow-600/30 text-yellow-400 border-yellow-600/30",
  platinum: "bg-cyan-600/30 text-cyan-400 border-cyan-600/30",
  diamond: "bg-purple-600/30 text-purple-400 border-purple-600/30",
};

export default function AgentGamificationPage() {
  const [tab, setTab] = useState<"leaderboard" | "achievements" | "badges">("leaderboard");
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [achievements, setAchievements] = useState<any[]>([]);
  const [badges, setBadges] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [lb, statsData, badgeData, achieveData] = await Promise.allSettled([
        gamificationApi.getLeaderboard(50),
        gamificationApi.getStats(),
        gamificationApi.listBadges(),
        gamificationApi.listAchievements(),
      ]);

      if (lb.status === "fulfilled") {
        const data = lb.value;
        setLeaderboard(Array.isArray(data) ? data : data?.agents ?? data?.leaderboard ?? []);
      }
      if (statsData.status === "fulfilled") setStats(statsData.value);
      if (badgeData.status === "fulfilled") setBadges(Array.isArray(badgeData.value) ? badgeData.value : []);
      if (achieveData.status === "fulfilled") setAchievements(Array.isArray(achieveData.value) ? achieveData.value : []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load gamification data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-400" /> Agent Gamification & Achievements
          </h1>
          <div className="flex gap-2 mt-2 mb-1">
            <button
              onClick={() => toast.info("Use the Training Academy to configure achievements")}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-sm font-medium"
            >
              + Add Achievement
            </button>
            <button
              onClick={() => toast.info("Select an achievement from the list to edit")}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
            >
              Edit Achievement
            </button>
          </div>
          <p className="text-sm text-zinc-400 mt-1">Leaderboards, achievements, badges, and performance incentives</p>
        </div>
        <button
          onClick={() => { loadAll(); toast.success("Refreshed"); }}
          className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg text-sm"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-700/30 text-red-400 px-4 py-3 rounded-xl text-sm">
          {error} — showing loyalty tier data where available.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Agents", value: stats?.total_accounts ?? leaderboard.length, icon: Target, color: "text-blue-400" },
          { label: "Achievements Earned", value: achievements.length, icon: Star, color: "text-yellow-400" },
          { label: "Badges Awarded", value: badges.length, icon: Medal, color: "text-purple-400" },
          { label: "Top Score", value: (leaderboard[0]?.points ?? leaderboard[0]?.total_points ?? 0).toLocaleString(), icon: Trophy, color: "text-emerald-400" },
        ].map((s) => (
          <div key={s.label} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
            <div className="flex items-center gap-2">
              <s.icon className={`h-4 w-4 ${s.color}`} />
              <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            </div>
            {loading ? (
              <div className="h-8 bg-zinc-700/50 rounded animate-pulse mt-2" />
            ) : (
              <p className="text-2xl font-bold text-white mt-2">{s.value}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {(["leaderboard", "achievements", "badges"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize ${tab === t ? "bg-yellow-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "leaderboard" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium w-16">Rank</th>
                <th className="text-left p-4 font-medium">Agent</th>
                <th className="text-left p-4 font-medium">Points</th>
                <th className="text-left p-4 font-medium">Tier</th>
                <th className="text-left p-4 font-medium">Transactions</th>
                <th className="text-left p-4 font-medium">Volume</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={6} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : leaderboard.length === 0
                ? (
                  <tr>
                    <td colSpan={6} className="p-12 text-center text-zinc-500">
                      No leaderboard data available yet
                    </td>
                  </tr>
                )
                : leaderboard.map((a: any, idx: number) => (
                    <tr key={a.agent_id ?? a.id ?? idx} className="border-b border-zinc-700/30 hover:bg-zinc-700/20">
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                            idx === 0 ? "bg-yellow-500/20 text-yellow-400" :
                            idx === 1 ? "bg-zinc-400/20 text-zinc-300" :
                            idx === 2 ? "bg-orange-600/20 text-orange-400" :
                            "bg-zinc-700/50 text-zinc-400"
                          }`}
                        >
                          {idx + 1}
                        </span>
                      </td>
                      <td className="p-4 text-white font-medium">
                        {a.agent_name ?? a.name ?? `Agent ${a.agent_id ?? a.id ?? idx + 1}`}
                      </td>
                      <td className="p-4 text-yellow-400 font-bold">
                        {Number(a.points ?? a.total_points ?? 0).toLocaleString()}
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-1 rounded-full text-xs border ${TIER_COLORS[a.tier ?? a.tier_name ?? "bronze"] ?? TIER_COLORS.bronze}`}>
                          {a.tier ?? a.tier_name ?? "bronze"}
                        </span>
                      </td>
                      <td className="p-4 text-zinc-300">
                        {Number(a.total_transactions ?? a.transaction_count ?? 0).toLocaleString()}
                      </td>
                      <td className="p-4 text-emerald-400">
                        ₦{Number(a.total_volume ?? a.volume ?? 0).toLocaleString()}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "achievements" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
                  <div className="h-20 bg-zinc-700/50 rounded animate-pulse" />
                </div>
              ))
            : achievements.length === 0
            ? (
              <div className="col-span-3 p-12 text-center text-zinc-500">
                No achievements configured yet
              </div>
            )
            : achievements.map((a: any) => (
                <div key={a.id} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4 hover:border-yellow-600/30 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-yellow-600/20 rounded-lg">
                      <Award className="h-6 w-6 text-yellow-400" />
                    </div>
                    <div className="flex-1">
                      <h4 className="text-white font-medium">{a.name}</h4>
                      <p className="text-zinc-400 text-xs mt-1">{a.description}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-yellow-400 text-xs font-bold">+{a.points ?? 0} pts</span>
                        <span className="text-zinc-500 text-xs">•</span>
                        <span className="text-zinc-400 text-xs">{a.earned_count ?? 0} agents earned</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
        </div>
      )}

      {tab === "badges" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {loading
            ? Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
                  <div className="h-24 bg-zinc-700/50 rounded animate-pulse" />
                </div>
              ))
            : badges.length === 0
            ? (
              <div className="col-span-4 p-12 text-center text-zinc-500">
                <Medal className="h-12 w-12 mx-auto mb-3 text-zinc-600" />
                <p>Tier badges are Bronze, Silver, Gold, Platinum based on agent loyalty points</p>
              </div>
            )
            : badges.map((b: any) => (
                <div key={b.id} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4 text-center hover:border-purple-600/30 transition-colors">
                  <div className="mx-auto w-12 h-12 rounded-full bg-purple-600/20 flex items-center justify-center mb-2">
                    <Medal className="h-6 w-6 text-purple-400" />
                  </div>
                  <h4 className="text-white font-medium text-sm">{b.name}</h4>
                  <p className="text-zinc-400 text-xs mt-1">{b.description}</p>
                  <p className="text-purple-400 text-xs font-bold mt-2">{b.tier ?? "standard"}</p>
                </div>
              ))}
        </div>
      )}
    </div>
  );
}
