import React, { useState } from "react";
import { Trophy, RefreshCw, Star, Award, Zap, Users } from "lucide-react";

const MOCK = {
  stats: { totalAgents: 248, activeStreaks: 87, badgesAwarded: 1420, pointsIssued: 284000, avgLevel: 4.2, leaderChanges: 12 },
  leaderboard: [
    { rank: 1, name: "Adebayo Ogundimu", points: 9840, level: 8, badges: 14, streak: 28, tier: "Platinum" },
    { rank: 2, name: "Chioma Nwosu", points: 9120, level: 8, badges: 12, streak: 21, tier: "Platinum" },
    { rank: 3, name: "Emeka Okafor", points: 8750, level: 7, badges: 11, streak: 14, tier: "Gold" },
    { rank: 4, name: "Fatima Ibrahim", points: 8100, level: 7, badges: 10, streak: 7, tier: "Gold" },
    { rank: 5, name: "Seun Bakare", points: 7560, level: 6, badges: 9, streak: 5, tier: "Gold" },
  ],
  recentBadges: [
    { agent: "Adebayo Ogundimu", badge: "Century Club", icon: "🏆", awardedAt: "2025-01-20T14:00:00Z" },
    { agent: "Chioma Nwosu", badge: "Speed Demon", icon: "⚡", awardedAt: "2025-01-19T11:00:00Z" },
    { agent: "Emeka Okafor", badge: "Consistency King", icon: "👑", awardedAt: "2025-01-18T09:00:00Z" },
    { agent: "Fatima Ibrahim", badge: "Float Master", icon: "💧", awardedAt: "2025-01-17T16:00:00Z" },
  ],
};

const TIER_COLORS: Record<string, string> = {
  Platinum: "bg-purple-100 text-purple-700",
  Gold: "bg-amber-100 text-amber-700",
  Silver: "bg-gray-100 text-gray-600",
  Bronze: "bg-orange-100 text-orange-700",
};

export default function AgentGamification() {
  const [data] = useState<typeof MOCK>(MOCK);
  const [search, setSearch] = useState("");

  const filtered = data.leaderboard.filter(a => !search || a.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Trophy className="h-7 w-7 text-amber-500" />Agent Gamification</h1>
          <p className="text-gray-500 text-sm mt-1">Leaderboards, badges, achievements, and performance streaks</p>
        </div>
        <div className="flex gap-2">
          <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 w-48" />
          <button onClick={() => {}} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className="w-4 h-4" />Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        {[
          { label: "Total Agents", value: data.stats.totalAgents, color: "text-gray-800", icon: Users },
          { label: "Active Streaks", value: data.stats.activeStreaks, color: "text-orange-600", icon: Zap },
          { label: "Badges Awarded", value: data.stats.badgesAwarded, color: "text-purple-600", icon: Award },
          { label: "Points Issued", value: data.stats.pointsIssued.toLocaleString(), color: "text-blue-600", icon: Star },
          { label: "Avg Level", value: data.stats.avgLevel, color: "text-emerald-600", icon: Trophy },
          { label: "Leader Changes", value: data.stats.leaderChanges, color: "text-amber-600", icon: Trophy },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm text-center">
            <Icon className={`w-5 h-5 mx-auto mb-1 ${color}`} />
            <p className={`text-xl font-bold ${color}`}>{value}</p>
            <p className="text-[10px] text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <h2 className="font-semibold text-gray-800 mb-3">Leaderboard</h2>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b border-gray-100">{["#", "Agent", "Tier", "Points", "Level", "Badges", "Streak"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map(a => (
                  <tr key={a.rank} className="hover:bg-gray-50/50">
                    <td className="py-3 px-4 font-bold text-gray-400">{a.rank}</td>
                    <td className="py-3 px-4 font-medium text-gray-800">{a.name}</td>
                    <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full ${TIER_COLORS[a.tier] ?? "bg-gray-100 text-gray-600"}`}>{a.tier}</span></td>
                    <td className="py-3 px-4 text-blue-600 font-mono">{a.points.toLocaleString()}</td>
                    <td className="py-3 px-4 text-purple-600 font-bold">Lv.{a.level}</td>
                    <td className="py-3 px-4 text-amber-600">{a.badges}</td>
                    <td className="py-3 px-4"><span className="flex items-center gap-1 text-orange-600"><Zap className="w-3 h-3" />{a.streak}d</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h2 className="font-semibold text-gray-800 mb-3">Recent Badges</h2>
          <div className="space-y-3">
            {data.recentBadges.map((b, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-3">
                <span className="text-2xl">{b.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800 text-sm">{b.badge}</p>
                  <p className="text-xs text-gray-500">{b.agent}</p>
                </div>
                <p className="text-xs text-gray-400 shrink-0">{new Date(b.awardedAt).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
