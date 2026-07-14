import { useState, useEffect } from "react";
import { Clock, RefreshCw, Plus, Search, Play, Pause, Trash2 } from "lucide-react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

type Schedule = {
  id: string | number;
  name: string;
  schedule: string;
  last_run: string;
  status: string;
  recipients?: number;
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  warning: "bg-red-500/20 text-red-400",
  completed: "bg-blue-500/20 text-blue-400",
};

export default function ReportScheduler() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "details" | "history" | "settings">("overview");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/reports/schedules`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSchedules(Array.isArray(data.schedules) ? data.schedules : Array.isArray(data) ? data : []);
      } else {
        setSchedules([]);
      }
    } catch {
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSchedule = async (id: string | number, currentStatus: string) => {
    const action = currentStatus === "active" ? "pause" : "resume";
    try {
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/reports/schedules/${id}/${action}`, {
        method: "POST",
        headers: authHeaders(),
      });
      load();
    } catch { /* ignore */ }
  };

  const deleteSchedule = async (id: string | number) => {
    if (!confirm("Delete this schedule?")) return;
    try {
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/reports/schedules/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      load();
    } catch { /* ignore */ }
  };

  const filtered = schedules.filter(r =>
    !search ||
    String(r.name || "").toLowerCase().includes(search.toLowerCase()) ||
    String(r.id || "").toLowerCase().includes(search.toLowerCase())
  );

  const activeCount = schedules.filter(s => s.status === "active").length;
  const todayCount = schedules.filter(s => s.last_run?.startsWith(new Date().toISOString().slice(0, 10))).length;
  const failedCount = schedules.filter(s => s.status === "warning").length;
  const totalRecipients = schedules.reduce((sum, s) => sum + (s.recipients || 0), 0);

  return (
    <div className="min-h-screen bg-[#0a0e17] text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Clock className="w-6 h-6 text-blue-400" />
              Report Scheduler
            </h1>
            <p className="text-gray-400 text-sm mt-1">Cron-based report generation and email delivery</p>
          </div>
          <div className="flex gap-2">
            <button onClick={load} className="p-2 bg-[#141a2a] border border-gray-700 rounded-lg hover:bg-gray-700 transition-colors">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
              <Plus className="w-4 h-4" /> New Schedule
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: "Active Schedules", value: activeCount },
            { label: "Reports Today", value: todayCount },
            { label: "Failed", value: failedCount },
            { label: "Recipients", value: totalRecipients },
          ].map((kpi, i) => (
            <div key={i} className="bg-[#141a2a] border border-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-xs uppercase tracking-wider">{kpi.label}</p>
              <p className="text-2xl font-bold mt-1 text-white">{kpi.value}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-2 mb-4">
          {(["overview", "details", "history", "settings"] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${activeTab === tab ? "bg-blue-600 text-white" : "bg-[#141a2a] text-gray-400 hover:text-white"}`}>
              {tab}
            </button>
          ))}
        </div>

        <div className="mb-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input type="text" placeholder="Search schedules..." value={search} onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-[#141a2a] border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500" />
          </div>
        </div>

        <div className="bg-[#141a2a] border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between">
            <h3 className="font-semibold">Schedules ({filtered.length})</h3>
          </div>

          {loading ? (
            <div className="text-center py-12 text-gray-500">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading schedules...
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Clock className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>No report schedules found.</p>
              <p className="text-sm mt-1">Create a schedule to automate report delivery.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="text-left p-3 text-gray-400 font-medium">Report Name</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Schedule</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Last Run</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Status</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <tr key={row.id} className="border-b border-gray-800/50 hover:bg-[#1a2035] transition-colors">
                      <td className="p-3 font-mono text-blue-400">{row.name || row.id}</td>
                      <td className="p-3 text-gray-300">{row.schedule || "—"}</td>
                      <td className="p-3 text-gray-400">{row.last_run || "Never"}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${STATUS_COLORS[row.status] || "bg-gray-500/20 text-gray-400"}`}>
                          {row.status}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="flex gap-2">
                          <button onClick={() => toggleSchedule(row.id, row.status)}
                            className="p-1 text-gray-400 hover:text-white transition-colors" title={row.status === "active" ? "Pause" : "Resume"}>
                            {row.status === "active" ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                          </button>
                          <button onClick={() => deleteSchedule(row.id)}
                            className="p-1 text-gray-400 hover:text-red-400 transition-colors" title="Delete">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
