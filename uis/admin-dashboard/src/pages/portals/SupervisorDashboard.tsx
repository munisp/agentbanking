import { Users, Wifi, WifiOff, Coffee, Megaphone, AlertCircle, TrendingUp } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface TeamSummary {
  totalAgents: number;
  activeToday: number;
  transactionsToday: number;
  floatAlerts: number;
}

interface AgentCard {
  id: string;
  name: string;
  location: string;
  status: "Online" | "Offline" | "On-Break";
  txToday: number;
  cashBalance: number;
}

interface SLABreach {
  id: string;
  agentName: string;
  issue: string;
  breachedAt: string;
}

interface PerfCompare {
  metric: string;
  myTeam: number;
  networkAvg: number;
}

const STATUS_STYLE: Record<string, string> = {
  Online: "bg-emerald-100 text-emerald-700",
  Offline: "bg-gray-100 text-gray-500",
  "On-Break": "bg-amber-100 text-amber-700",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  Online: <Wifi className="w-3 h-3" />,
  Offline: <WifiOff className="w-3 h-3" />,
  "On-Break": <Coffee className="w-3 h-3" />,
};

const SupervisorDashboard: React.FC = () => {
  const [summary, setSummary] = useState<TeamSummary | null>(null);
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [breaches, setBreaches] = useState<SLABreach[]>([]);
  const [perf, setPerf] = useState<PerfCompare[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/portals/api/v1/supervisor/team`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setSummary(d.summary ?? null);
        setAgents(d.agents ?? []);
        setBreaches(d.breaches ?? []);
        setPerf(d.performance ?? []);
      } else { setError("Failed to load team data."); }
    } catch { setError("Failed to load team data."); } finally { setLoading(false); }
  };

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchAll()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Supervisor Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Live overview of your field team performance and alerts</p>
        </div>
        <button onClick={() => alert("Broadcast sent to team")} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
          <Megaphone className="w-4 h-4" /> Send Broadcast to Team
        </button>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { label: "Agents Under Supervision", value: summary ? summary.totalAgents : "—", color: "text-indigo-600" },
          { label: "Active Today", value: summary ? summary.activeToday : "—", color: "text-emerald-600" },
          { label: "Transactions Today", value: summary ? summary.transactionsToday.toLocaleString() : "—", color: "text-blue-600" },
          { label: "Float Alerts", value: summary ? summary.floatAlerts : "—", color: "text-red-500" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-sm text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Users className="w-4 h-4 text-indigo-500" /> Agent Status Grid</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map(ag => (
            <div key={ag.id} className="border border-gray-100 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-800 text-sm">{ag.name}</span>
                <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[ag.status]}`}>
                  {STATUS_ICON[ag.status]} {ag.status}
                </span>
              </div>
              <p className="text-xs text-gray-400">{ag.location}</p>
              <div className="flex justify-between text-xs text-gray-600">
                <span>Tx today: <span className="font-semibold">{ag.txToday}</span></span>
                <span>Cash: <span className="font-semibold">₦{ag.cashBalance.toLocaleString()}</span></span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {breaches.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><AlertCircle className="w-4 h-4 text-red-500" /> SLA Breach Alerts</h2>
          <div className="space-y-3">
            {breaches.map(b => (
              <div key={b.id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-100">
                <div>
                  <p className="text-sm font-medium text-red-800">{b.agentName}</p>
                  <p className="text-xs text-red-600">{b.issue}</p>
                </div>
                <span className="text-xs text-red-400">{b.breachedAt}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><TrendingUp className="w-4 h-4 text-emerald-500" /> My Team vs Network Average</h2>
        <div className="space-y-4">
          {perf.map(p => (
            <div key={p.metric}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">{p.metric}</span>
                <span className="text-gray-400 text-xs">Team: <span className="font-semibold text-indigo-600">{p.myTeam}</span> · Avg: {p.networkAvg}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2 relative">
                <div className="bg-gray-300 h-2 rounded-full" style={{ width: `${Math.min((p.networkAvg / (p.myTeam || 1)) * 100, 100)}%` }} />
                <div className="bg-indigo-500 h-2 rounded-full absolute top-0 left-0" style={{ width: `${Math.min((p.myTeam / Math.max(p.myTeam, p.networkAvg)) * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SupervisorDashboard;
