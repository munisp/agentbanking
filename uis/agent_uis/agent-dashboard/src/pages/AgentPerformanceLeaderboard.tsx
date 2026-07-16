import { useState, useEffect } from "react";
import { Trophy, RefreshCw, Search, TrendingUp } from "lucide-react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

type Agent = { id: string; rank: number; name: string; region: string; txCount: number; volume: number; commission: number; rating: number; trend: string };

export default function AgentPerformanceLeaderboard() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/performance/api/v1/leaderboard?limit=50`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setAgents(Array.isArray(data.agents) ? data.agents : Array.isArray(data) ? data : []);
      } else setAgents([]);
    } catch { setAgents([]); }
    finally { setLoading(false); }
  };

  const filtered = agents.filter(a => !search || a.name?.toLowerCase().includes(search.toLowerCase()) || a.id?.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Trophy className="w-7 h-7 text-amber-500" />Agent Leaderboard</h1>
          <p className="text-gray-500 text-sm mt-1">Gamified real-time agent performance rankings</p>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Search agents..." value={search} onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56" />
          </div>
          <button onClick={load} className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 border border-gray-200 rounded-xl bg-white">
          <Trophy className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No leaderboard data available.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
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
              {filtered.map((a, i) => (
                <tr key={a.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="p-3 font-bold text-gray-400">#{i + 1}</td>
                  <td className="p-3">
                    <div className="font-medium text-gray-800">{a.name}</div>
                    <div className="text-xs text-gray-400">{a.id}</div>
                  </td>
                  <td className="p-3 text-gray-600">{a.region || "—"}</td>
                  <td className="p-3 text-right font-mono text-gray-600">{a.txCount?.toLocaleString()}</td>
                  <td className="p-3 text-right font-mono text-gray-700">₦{(a.volume / 1e6).toFixed(1)}M</td>
                  <td className="p-3 text-right font-mono text-emerald-600">₦{a.commission?.toLocaleString()}</td>
                  <td className="p-3 text-center text-amber-600">{a.rating}</td>
                  <td className="p-3 text-center">
                    <TrendingUp className={`w-4 h-4 mx-auto ${a.trend === "up" ? "text-emerald-500" : "text-red-400 rotate-180"}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
