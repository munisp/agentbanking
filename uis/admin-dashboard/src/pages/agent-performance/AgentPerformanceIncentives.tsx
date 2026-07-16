import React, { useState } from "react";
import { Gift, Download, RefreshCw, Search, Star, Trophy, Zap, TrendingUp } from "lucide-react";

const MOCK = {
  totalAgents: 248, platinumAgents: 18, goldAgents: 72, silverAgents: 98,
  totalPointsIssued: 284000, totalRewardsValue: 5680000, avgAchievement: 68, topPerformer: "Adebayo Ogundimu",
  incentives: [
    { id: "i1", name: "Q1 Volume Champion", tier: "Platinum", reward: "₦50,000 bonus", target: "₦10M volume", status: "active", achieved: 18, total: 248 },
    { id: "i2", name: "Customer Satisfaction Star", tier: "Gold", reward: "₦20,000 bonus", target: "4.5+ rating", status: "active", achieved: 72, total: 248 },
    { id: "i3", name: "Zero Dispute Award", tier: "Silver", reward: "₦10,000 bonus", target: "0 disputes/month", status: "active", achieved: 98, total: 248 },
    { id: "i4", name: "Training Completion Bonus", tier: "Bronze", reward: "500 points", target: "All mandatory courses", status: "active", achieved: 180, total: 248 },
    { id: "i5", name: "Float Efficiency Prize", tier: "Gold", reward: "₦15,000 bonus", target: "<5% idle float", status: "completed", achieved: 65, total: 248 },
  ],
};

const TIER_COLORS: Record<string, string> = {
  Platinum: "bg-purple-100 text-purple-700", Gold: "bg-amber-100 text-amber-700",
  Silver: "bg-gray-100 text-gray-600", Bronze: "bg-orange-100 text-orange-700",
};

export default function AgentPerformanceIncentives() {
  const [data] = useState<typeof MOCK>(MOCK);
  const [search, setSearch] = useState("");

  const filtered = data.incentives.filter(i => !search || i.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Gift className="w-7 h-7 text-rose-600" />Performance Incentives</h1>
          <p className="text-gray-500 text-sm mt-1">Gamified performance rewards with tier-based incentive programs</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56" />
          </div>
          <button onClick={() => {}} className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className="w-4 h-4" />Refresh
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <Download className="w-4 h-4" />Export
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Agents", value: data.totalAgents, color: "text-gray-800", icon: Star },
          { label: "Platinum", value: data.platinumAgents, color: "text-purple-600", icon: Trophy },
          { label: "Gold", value: data.goldAgents, color: "text-amber-600", icon: Star },
          { label: "Silver", value: data.silverAgents, color: "text-gray-500", icon: Star },
          { label: "Points Issued", value: data.totalPointsIssued.toLocaleString(), color: "text-blue-600", icon: Zap },
          { label: "Rewards Value", value: `₦${(data.totalRewardsValue / 1e6).toFixed(1)}M`, color: "text-emerald-600", icon: Gift },
          { label: "Avg Achievement %", value: `${data.avgAchievement}%`, color: "text-indigo-600", icon: TrendingUp },
          { label: "Top Performer", value: data.topPerformer, color: "text-orange-600", icon: Trophy },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><p className="text-xs text-gray-500">{label}</p></div>
            <p className={`text-xl font-bold truncate ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Active Incentive Programs</h2>
        <div className="space-y-4">
          {filtered.map(incentive => {
            const pct = Math.round((incentive.achieved / incentive.total) * 100);
            return (
              <div key={incentive.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                  <div>
                    <h3 className="font-medium text-gray-800">{incentive.name}</h3>
                    <p className="text-xs text-gray-500 mt-0.5">Target: {incentive.target} · Reward: {incentive.reward}</p>
                  </div>
                  <div className="flex gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${TIER_COLORS[incentive.tier] ?? "bg-gray-100 text-gray-600"}`}>{incentive.tier}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${incentive.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>{incentive.status}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div className="h-2 rounded-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-sm text-gray-600 font-mono shrink-0">{incentive.achieved}/{incentive.total} ({pct}%)</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
