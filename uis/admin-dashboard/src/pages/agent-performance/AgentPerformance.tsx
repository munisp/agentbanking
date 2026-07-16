import React, { useMemo, useState } from "react";
import { Trophy, TrendingUp, Users, Search, ChevronLeft, ChevronRight, Medal, Star, Zap } from "lucide-react";

const MOCK_AGENTS = [
  { id: "a1", agentCode: "AG-001", name: "Adebayo Ogundimu", tier: "Platinum", status: "active", txCount: 1840, volume: 9200000, commission: 284000, successRate: 98.2 },
  { id: "a2", agentCode: "AG-002", name: "Chioma Nwosu", tier: "Platinum", status: "active", txCount: 1720, volume: 8600000, commission: 261000, successRate: 96.5 },
  { id: "a3", agentCode: "AG-003", name: "Emeka Okafor", tier: "Gold", status: "active", txCount: 1520, volume: 7600000, commission: 228000, successRate: 94.0 },
  { id: "a4", agentCode: "AG-004", name: "Fatima Ibrahim", tier: "Gold", status: "active", txCount: 1410, volume: 7050000, commission: 211000, successRate: 91.8 },
  { id: "a5", agentCode: "AG-005", name: "Oluwaseun Bakare", tier: "Gold", status: "active", txCount: 1280, volume: 6400000, commission: 192000, successRate: 89.3 },
  { id: "a6", agentCode: "AG-006", name: "Amaka Eze", tier: "Silver", status: "active", txCount: 1180, volume: 5900000, commission: 177000, successRate: 87.1 },
  { id: "a7", agentCode: "AG-007", name: "Chukwuemeka Ike", tier: "Silver", status: "active", txCount: 1090, volume: 5450000, commission: 163000, successRate: 85.6 },
  { id: "a8", agentCode: "AG-008", name: "Ngozi Obi", tier: "Silver", status: "active", txCount: 920, volume: 4600000, commission: 138000, successRate: 83.2 },
  { id: "a9", agentCode: "AG-009", name: "Tunde Adeleke", tier: "Bronze", status: "inactive", txCount: 780, volume: 3900000, commission: 117000, successRate: 79.4 },
  { id: "a10", agentCode: "AG-010", name: "Yetunde Afolabi", tier: "Bronze", status: "active", txCount: 640, volume: 3200000, commission: 96000, successRate: 76.8 },
];

const TIER_COLORS: Record<string, string> = {
  Platinum: "bg-purple-100 text-purple-700",
  Gold: "bg-amber-100 text-amber-700",
  Silver: "bg-gray-100 text-gray-600",
  Bronze: "bg-orange-100 text-orange-700",
};

const fmt = (n: number) => `₦${n.toLocaleString("en-NG")}`;

export default function AgentPerformance() {
  const [agents] = useState(MOCK_AGENTS);
  const [days, setDays] = useState(30);
  const [sortBy, setSortBy] = useState<"volume" | "txCount" | "commission" | "successRate">("volume");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const limit = 5;

  const filtered = useMemo(() => {
    let list = [...agents];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(a => a.agentCode?.toLowerCase().includes(q) || a.name?.toLowerCase().includes(q));
    }
    list.sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));
    return list;
  }, [agents, search, sortBy]);

  const totalPages = Math.ceil(filtered.length / limit);
  const paged = filtered.slice((page - 1) * limit, page * limit);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Trophy className="w-7 h-7 text-amber-500" />Agent Performance Leaderboard</h1>
          <p className="text-gray-500 text-sm mt-1">Track agent rankings by volume, transactions, commission, and success rate</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-blue-200 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-blue-600 text-xs font-medium mb-1"><Users className="w-4 h-4" />Total Agents</div>
          <p className="text-2xl font-bold text-gray-800">{filtered.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-emerald-200 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-emerald-600 text-xs font-medium mb-1"><TrendingUp className="w-4 h-4" />Top Volume</div>
          <p className="text-2xl font-bold text-gray-800">{paged[0] ? fmt(paged[0].volume) : "—"}</p>
        </div>
        <div className="bg-white rounded-xl border border-purple-200 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-purple-600 text-xs font-medium mb-1"><Medal className="w-4 h-4" />Top Commission</div>
          <p className="text-2xl font-bold text-gray-800">{paged[0] ? fmt(paged[0].commission) : "—"}</p>
        </div>
        <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-amber-600 text-xs font-medium mb-1"><Star className="w-4 h-4" />Top Success Rate</div>
          <p className="text-2xl font-bold text-gray-800">{paged[0] ? `${paged[0].successRate}%` : "—"}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Search by agent code or name..." className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <select value={days} onChange={e => { setDays(Number(e.target.value)); setPage(1); }} className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
          <select value={sortBy} onChange={e => { setSortBy(e.target.value as any); setPage(1); }} className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
            <option value="volume">Sort by Volume</option>
            <option value="txCount">Sort by Tx Count</option>
            <option value="commission">Sort by Commission</option>
            <option value="successRate">Sort by Success Rate</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-semibold text-gray-800">Rankings</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="bg-gray-50 border-b border-gray-100 text-gray-500">
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-left">Tier</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Transactions</th>
              <th className="px-3 py-2 text-right">Volume</th>
              <th className="px-3 py-2 text-right">Commission</th>
              <th className="px-3 py-2 text-right">Success Rate</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {paged.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-gray-400">No agents found</td></tr>
              ) : paged.map((a, i) => {
                const globalRank = (page - 1) * limit + i + 1;
                return (
                  <tr key={a.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-3 py-2.5">
                      {globalRank <= 3 ? (
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${globalRank === 1 ? "bg-amber-100 text-amber-700" : globalRank === 2 ? "bg-gray-200 text-gray-600" : "bg-orange-100 text-orange-700"}`}>{globalRank}</span>
                      ) : <span className="text-gray-400 pl-1.5">{globalRank}</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-gray-800">{a.name || a.agentCode}</div>
                      <div className="text-gray-400 text-[10px]">{a.agentCode}</div>
                    </td>
                    <td className="px-3 py-2.5"><span className={`text-[10px] px-2 py-0.5 rounded-full ${TIER_COLORS[a.tier] ?? "bg-gray-100 text-gray-600"}`}>{a.tier}</span></td>
                    <td className="px-3 py-2.5"><span className={`text-[10px] px-2 py-0.5 rounded-full ${a.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{a.status}</span></td>
                    <td className="px-3 py-2.5 text-right font-mono text-gray-600">{a.txCount.toLocaleString()}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-gray-600">{fmt(a.volume)}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-emerald-600">{fmt(a.commission)}</td>
                    <td className="px-3 py-2.5 text-right">
                      <span className={`font-mono ${a.successRate >= 90 ? "text-emerald-600" : a.successRate >= 70 ? "text-amber-600" : "text-red-500"}`}>{a.successRate}%</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Page {page} of {totalPages} ({filtered.length} agents)</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="p-2 border border-gray-200 rounded-lg text-gray-500 disabled:opacity-40 hover:bg-gray-50"><ChevronLeft className="w-4 h-4" /></button>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="p-2 border border-gray-200 rounded-lg text-gray-500 disabled:opacity-40 hover:bg-gray-50"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}
