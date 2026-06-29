import { useState, useMemo, useEffect } from "react";
import {
  Trophy, TrendingUp, TrendingDown, Medal, Star, Search,
  Download, Crown, Award, RefreshCw
} from "lucide-react";
import { performanceApi } from "../../utils/api";

function formatNaira(n: number) {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", minimumFractionDigits: 0 }).format(n);
}

function LeaderboardContent() {
  const [search, setSearch] = useState("");
  const [regionFilter, setRegionFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"volume" | "txCount" | "commission" | "rating">("volume");
  const [period, setPeriod] = useState<"week" | "month" | "quarter" | "year">("month");
  const [agents, setAgents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const periodDays: Record<string, number> = { week: 7, month: 30, quarter: 90, year: 365 };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await performanceApi.getLeaderboard({
        days: periodDays[period],
        sortBy,
        limit: 50,
      });
      const list = Array.isArray(data) ? data : data?.agents ?? data?.leaderboard ?? data?.results ?? [];
      setAgents(list);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load performance data");
      setAgents([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [period]);

  const regions = useMemo(() => [...new Set(agents.map((a) => a.region).filter(Boolean))], [agents]);

  const filtered = useMemo(() => {
    let result = [...agents];
    if (search) {
      result = result.filter(
        (a) =>
          (a.agent_name ?? a.name ?? "").toLowerCase().includes(search.toLowerCase()) ||
          (a.agent_id ?? a.id ?? "").toString().includes(search)
      );
    }
    if (regionFilter !== "all") result = result.filter((a) => a.region === regionFilter);
    result.sort((a, b) => {
      const getVal = (x: any) => {
        if (sortBy === "volume") return Number(x.total_volume ?? x.volume ?? 0);
        if (sortBy === "txCount") return Number(x.total_transactions ?? x.tx_count ?? 0);
        if (sortBy === "commission") return Number(x.total_commission ?? x.commission ?? 0);
        if (sortBy === "rating") return Number(x.rating ?? 0);
        return 0;
      };
      return getVal(b) - getVal(a);
    });
    return result.map((a, i) => ({ ...a, rank: i + 1 }));
  }, [agents, search, regionFilter, sortBy]);

  const getBadge = (rank: number) => {
    if (rank === 1) return <Crown className="h-4 w-4 text-yellow-500" />;
    if (rank === 2) return <Medal className="h-4 w-4 text-gray-400" />;
    if (rank === 3) return <Award className="h-4 w-4 text-amber-700" />;
    return null;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-500" /> Agent Performance Leaderboard
          </h1>
          <p className="text-sm text-muted-foreground">Top performing agents ranked by transaction volume</p>
        </div>
        <div className="flex gap-2">
          {(["week", "month", "quarter", "year"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium ${period === p ? "bg-primary text-primary-foreground" : "border hover:bg-accent"}`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
          <button
            onClick={loadData}
            className="px-3 py-1.5 rounded-md text-xs font-medium border hover:bg-accent flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Top 3 Podium */}
      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {filtered.slice(0, 3).map((agent, i) => (
            <div
              key={agent.agent_id ?? agent.id ?? i}
              className={`rounded-lg border p-5 text-center ${i === 0 ? "bg-yellow-50 dark:bg-yellow-900/10 border-yellow-300 dark:border-yellow-800" : "bg-card"}`}
            >
              <div className="flex justify-center mb-2">{getBadge(agent.rank)}</div>
              <div className="text-3xl font-bold mb-1">#{agent.rank}</div>
              <div className="font-semibold">{agent.agent_name ?? agent.name ?? `Agent ${i + 1}`}</div>
              <div className="text-xs text-muted-foreground mb-2">
                {agent.agent_id ?? agent.id} {agent.region ? `— ${agent.region}` : ""}
              </div>
              <div className="text-lg font-bold text-primary">
                {formatNaira(Number(agent.total_volume ?? agent.volume ?? 0))}
              </div>
              <div className="text-xs text-muted-foreground">
                {Number(agent.total_transactions ?? agent.tx_count ?? 0).toLocaleString()} transactions
              </div>
            </div>
          ))}
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-5 bg-card">
              <div className="h-28 bg-muted rounded animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-md border bg-background text-sm"
          />
        </div>
        {regions.length > 0 && (
          <select
            value={regionFilter}
            onChange={(e) => setRegionFilter(e.target.value)}
            className="px-3 py-2 rounded-md border bg-background text-sm"
          >
            <option value="all">All Regions</option>
            {regions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        )}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="px-3 py-2 rounded-md border bg-background text-sm"
        >
          <option value="volume">Sort by Volume</option>
          <option value="txCount">Sort by Transactions</option>
          <option value="commission">Sort by Commission</option>
          <option value="rating">Sort by Rating</option>
        </select>
        <button className="inline-flex items-center gap-2 px-3 py-2 rounded-md border hover:bg-accent text-sm">
          <Download className="h-4 w-4" /> Export
        </button>
      </div>

      {/* Full Table */}
      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Rank</th>
              <th className="text-left p-3 font-medium">Agent</th>
              <th className="text-left p-3 font-medium">Region</th>
              <th className="text-right p-3 font-medium">Transactions</th>
              <th className="text-right p-3 font-medium">Volume</th>
              <th className="text-right p-3 font-medium">Commission</th>
              <th className="text-center p-3 font-medium">Rating</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-t">
                    <td colSpan={7} className="p-3">
                      <div className="h-8 bg-muted rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              : filtered.length === 0
              ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center text-muted-foreground">
                    No performance data available for this period
                  </td>
                </tr>
              )
              : filtered.map((agent) => (
                  <tr key={agent.agent_id ?? agent.id ?? agent.rank} className="border-t hover:bg-muted/30">
                    <td className="p-3 font-bold">
                      <div className="flex items-center gap-2">
                        {agent.rank <= 3 ? getBadge(agent.rank) : <span className="text-muted-foreground">#{agent.rank}</span>}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="font-medium">{agent.agent_name ?? agent.name ?? `Agent ${agent.rank}`}</div>
                      <div className="text-xs text-muted-foreground">{agent.agent_id ?? agent.id ?? ""}</div>
                    </td>
                    <td className="p-3">{agent.region ?? "—"}</td>
                    <td className="p-3 text-right font-mono">
                      {Number(agent.total_transactions ?? agent.tx_count ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3 text-right font-mono font-medium">
                      {formatNaira(Number(agent.total_volume ?? agent.volume ?? 0))}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {formatNaira(Number(agent.total_commission ?? agent.commission ?? 0))}
                    </td>
                    <td className="p-3 text-center">
                      {agent.rating ? (
                        <div className="flex items-center justify-center gap-1">
                          <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                          <span>{agent.rating}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AgentPerformanceLeaderboardPage() {
  return <LeaderboardContent />;
}
