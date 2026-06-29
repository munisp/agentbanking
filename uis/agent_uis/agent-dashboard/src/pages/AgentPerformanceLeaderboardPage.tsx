import { useState, useMemo, useEffect } from "react";
import {
  Trophy, TrendingUp, TrendingDown, Medal, Star, Search,
  Download, Crown, Award, RefreshCw,
} from "lucide-react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

function formatNaira(n: number) {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", minimumFractionDigits: 0 }).format(n);
}

type Agent = {
  id: string;
  rank: number;
  name: string;
  region: string;
  txCount: number;
  volume: number;
  commission: number;
  rating: number;
  trend: "up" | "down";
  badge: "gold" | "silver" | "bronze";
};

export default function AgentPerformanceLeaderboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [regionFilter, setRegionFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"volume" | "txCount" | "commission" | "rating">("volume");
  const [period, setPeriod] = useState("month");

  useEffect(() => { load(); }, [period]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `https://54agent.upi.dev/performance/api/v1/agents/leaderboard?days=30&sort_by=volume&limit=50`,
        { headers: authHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        setAgents(Array.isArray(data.agents) ? data.agents : Array.isArray(data) ? data : []);
      } else {
        setAgents([]);
      }
    } catch {
      setAgents([]);
    } finally {
      setLoading(false);
    }
  };

  const regions = [...new Set(agents.map(a => a.region).filter(Boolean))];

  const filtered = useMemo(() => {
    let result = [...agents];
    if (search) result = result.filter(a => a.name?.toLowerCase().includes(search.toLowerCase()) || a.id?.includes(search));
    if (regionFilter !== "all") result = result.filter(a => a.region === regionFilter);
    result.sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));
    return result.map((a, i) => ({ ...a, rank: i + 1 }));
  }, [agents, search, regionFilter, sortBy]);

  const badgeIcon = (badge: string) => {
    if (badge === "gold") return <Crown className="h-4 w-4 text-yellow-500" />;
    if (badge === "silver") return <Medal className="h-4 w-4 text-gray-400" />;
    return <Award className="h-4 w-4 text-amber-700" />;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-500" /> Agent Performance Leaderboard
          </h1>
          <p className="text-sm text-gray-500">Top performing agents ranked by transaction volume</p>
        </div>
        <div className="flex gap-2">
          {["week", "month", "quarter", "year"].map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${period === p ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 hover:bg-gray-50"}`}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
          <button onClick={load} className="p-2 border border-gray-200 rounded-md hover:bg-gray-50">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading leaderboard...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 border border-gray-200 rounded-xl bg-white">
          <Trophy className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">No agents found</p>
          <p className="text-sm mt-1">Data will appear once agents are active for this period.</p>
        </div>
      ) : (
        <>
          {/* Top 3 Podium */}
          <div className="grid grid-cols-3 gap-4">
            {filtered.slice(0, 3).map((agent, i) => (
              <div key={agent.id} className={`rounded-xl border p-5 text-center shadow-sm ${i === 0 ? "bg-yellow-50 border-yellow-300" : "bg-white border-gray-200"}`}>
                <div className="flex justify-center mb-2">{badgeIcon(agent.badge)}</div>
                <div className="text-3xl font-bold mb-1 text-gray-800">#{agent.rank}</div>
                <div className="font-semibold text-gray-800">{agent.name}</div>
                <div className="text-xs text-gray-500 mb-2">{agent.id} — {agent.region}</div>
                <div className="text-lg font-bold text-blue-600">{formatNaira(agent.volume)}</div>
                <div className="text-xs text-gray-500">{agent.txCount?.toLocaleString()} transactions</div>
                <div className="flex items-center justify-center gap-1 mt-2">
                  {Array.from({ length: 5 }).map((_, s) => (
                    <Star key={s} className={`h-3 w-3 ${s < Math.floor(agent.rating || 0) ? "text-yellow-500 fill-yellow-500" : "text-gray-300"}`} />
                  ))}
                  <span className="text-xs ml-1 text-gray-500">{agent.rating}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input type="text" placeholder="Search agents..." value={search} onChange={e => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            {regions.length > 0 && (
              <select value={regionFilter} onChange={e => setRegionFilter(e.target.value)}
                className="px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white">
                <option value="all">All Regions</option>
                {regions.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            )}
            <select value={sortBy} onChange={e => setSortBy(e.target.value as any)}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white">
              <option value="volume">Sort by Volume</option>
              <option value="txCount">Sort by Transactions</option>
              <option value="commission">Sort by Commission</option>
              <option value="rating">Sort by Rating</option>
            </select>
            <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 text-sm">
              <Download className="h-4 w-4" /> Export
            </button>
          </div>

          {/* Full Table */}
          <div className="rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-500">Rank</th>
                  <th className="text-left p-3 font-medium text-gray-500">Agent</th>
                  <th className="text-left p-3 font-medium text-gray-500">Region</th>
                  <th className="text-right p-3 font-medium text-gray-500">Transactions</th>
                  <th className="text-right p-3 font-medium text-gray-500">Volume</th>
                  <th className="text-right p-3 font-medium text-gray-500">Commission</th>
                  <th className="text-center p-3 font-medium text-gray-500">Rating</th>
                  <th className="text-center p-3 font-medium text-gray-500">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map(agent => (
                  <tr key={agent.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="p-3 font-bold">
                      <div className="flex items-center gap-2">
                        {agent.rank <= 3 ? badgeIcon(agent.badge) : <span className="text-gray-400">#{agent.rank}</span>}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="font-medium text-gray-800">{agent.name}</div>
                      <div className="text-xs text-gray-400">{agent.id}</div>
                    </td>
                    <td className="p-3 text-gray-600">{agent.region}</td>
                    <td className="p-3 text-right font-mono text-gray-600">{agent.txCount?.toLocaleString()}</td>
                    <td className="p-3 text-right font-mono font-medium text-gray-700">{formatNaira(agent.volume)}</td>
                    <td className="p-3 text-right font-mono text-emerald-600">{formatNaira(agent.commission)}</td>
                    <td className="p-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                        <span className="text-gray-600">{agent.rating}</span>
                      </div>
                    </td>
                    <td className="p-3 text-center">
                      {agent.trend === "up"
                        ? <TrendingUp className="h-4 w-4 text-emerald-500 mx-auto" />
                        : <TrendingDown className="h-4 w-4 text-red-500 mx-auto" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
