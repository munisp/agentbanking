import { useState } from "react";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  Filter,
  RefreshCw,
  Search,
} from "lucide-react";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  info: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

export default function RealtimeTxMonitorPage() {
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedAlert, setSelectedAlert] = useState<any>(null);
  // NOTE: No real-time transaction monitoring backend is reachable from this
  // dashboard (the tRPC client is a migration stub and no REST endpoint for
  // tx alerts exists). Fail loud: render an explicit unavailable state and
  // never fire success toasts for actions no backend performed.
  const MONITOR_UNAVAILABLE_MESSAGE =
    "Real-time transaction monitoring is unavailable — the alert service is not connected.";
  const alertsQuery = {data: null, isLoading: false, refetch: () => {}};
  const statsQuery = {data: null, isLoading: false, refetch: () => {}};
  const ackMutation = {
    mutate: () => { toast.error(MONITOR_UNAVAILABLE_MESSAGE); },
    mutateAsync: async () => { toast.error(MONITOR_UNAVAILABLE_MESSAGE); },
    isPending: false, isLoading: false,
  } as any;
  const dismissMutation = {
    mutate: () => { toast.error(MONITOR_UNAVAILABLE_MESSAGE); },
    mutateAsync: async () => { toast.error(MONITOR_UNAVAILABLE_MESSAGE); },
    isPending: false, isLoading: false,
  } as any;

  const alerts = (alertsQuery.data ?? []).filter((a: any) => {
    if (
      search &&
      !a.alert_type?.toLowerCase().includes(search.toLowerCase()) &&
      !a.description?.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    if (severityFilter !== "all" && a.severity !== severityFilter) return false;
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity className="h-6 w-6 text-emerald-400" />
            Real-Time Transaction Monitor
          </h1>
          {/* CRUD Actions */}
          <div className="flex gap-2 mb-4">
            <button
              disabled
              title={MONITOR_UNAVAILABLE_MESSAGE}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium opacity-50 cursor-not-allowed"
            >
              + Create Alert Rule
            </button>
            <button
              disabled
              title={MONITOR_UNAVAILABLE_MESSAGE}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium opacity-50 cursor-not-allowed"
            >
              ✏️ Edit Alert
            </button>
            <button
              disabled
              title={MONITOR_UNAVAILABLE_MESSAGE}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium opacity-50 cursor-not-allowed"
            >
              🗑️ Delete Alert
            </button>
          </div>
          <p className="text-sm text-zinc-400 mt-1">
            Live transaction alerts, velocity monitoring, and anomaly detection
          </p>
        </div>
        <button
          onClick={() => {
            alertsQuery.refetch();
            statsQuery.refetch();
            toast.error(MONITOR_UNAVAILABLE_MESSAGE);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
        {MONITOR_UNAVAILABLE_MESSAGE}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          {
            label: "Total Alerts",
            value: stats?.totalAlerts ?? "—",
            icon: AlertTriangle,
            color: "text-yellow-400",
          },
          {
            label: "Critical",
            value: stats?.critical ?? "—",
            icon: XCircle,
            color: "text-red-400",
          },
          {
            label: "High",
            value: stats?.high ?? "—",
            icon: AlertTriangle,
            color: "text-orange-400",
          },
          {
            label: "Acknowledged",
            value: stats?.acknowledged ?? "—",
            icon: CheckCircle,
            color: "text-emerald-400",
          },
          {
            label: "Pending",
            value: stats?.pending ?? "—",
            icon: Activity,
            color: "text-blue-400",
          },
        ].map((s: any) => (
          <div
            key={s.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <s.icon className={`h-4 w-4 ${s.color}`} />
              <p className="text-xs text-zinc-400 uppercase tracking-wider">
                {s.label}
              </p>
            </div>
            <p className="text-2xl font-bold text-white mt-2">
              {typeof s.value === "number" ? s.value.toLocaleString() : s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search alerts..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <select
          value={severityFilter}
          onChange={(e: any) => setSeverityFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e: any) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {/* Alerts Table */}
      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Severity</th>
                <th className="text-left p-4 font-medium">Alert Type</th>
                <th className="text-left p-4 font-medium">Description</th>
                <th className="text-left p-4 font-medium">Amount</th>
                <th className="text-left p-4 font-medium">Status</th>
                <th className="text-left p-4 font-medium">Time</th>
                <th className="text-left p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {alertsQuery.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-700/30">
                    <td colSpan={7} className="p-4">
                      <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-zinc-500">
                    {MONITOR_UNAVAILABLE_MESSAGE}
                  </td>
                </tr>
              ) : (
                alerts.map((alert: any) => (
                  <tr
                    key={alert.id}
                    className="border-b border-zinc-700/30 hover:bg-zinc-700/20 transition-colors"
                  >
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium border ${SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.info}`}
                      >
                        {alert.severity}
                      </span>
                    </td>
                    <td className="p-4 text-white font-medium">
                      {alert.alert_type?.replace(/_/g, " ")}
                    </td>
                    <td className="p-4 text-zinc-300 max-w-[300px] truncate">
                      {alert.description}
                    </td>
                    <td className="p-4 text-white font-mono">
                      ₦{Number(alert.amount || 0).toLocaleString()}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${alert.status === "active" ? "bg-red-500/20 text-red-400" : alert.status === "acknowledged" ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-500/20 text-zinc-400"}`}
                      >
                        {alert.status}
                      </span>
                    </td>
                    <td className="p-4 text-zinc-400 text-xs">
                      {alert.created_at
                        ? new Date(alert.created_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="p-4">
                      <div className="flex gap-1">
                        <button
                          onClick={() => setSelectedAlert(alert)}
                          className="p-1.5 hover:bg-zinc-700 rounded-lg"
                          title="View Details"
                        >
                          <Eye className="h-4 w-4 text-zinc-400" />
                        </button>
                        {alert.status === "active" && (
                          <>
                            <button
                              onClick={() =>
                                ackMutation.mutate({ id: alert.id })
                              }
                              className="p-1.5 hover:bg-emerald-700/30 rounded-lg"
                              title="Acknowledge"
                            >
                              <CheckCircle className="h-4 w-4 text-emerald-400" />
                            </button>
                            <button
                              onClick={() =>
                                dismissMutation.mutate({ id: alert.id })
                              }
                              className="p-1.5 hover:bg-red-700/30 rounded-lg"
                              title="Dismiss"
                            >
                              <XCircle className="h-4 w-4 text-red-400" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Alert Detail Modal */}
      {selectedAlert && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedAlert(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Alert Details</h3>
              <button
                onClick={() => setSelectedAlert(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedAlert).map(([key, value]) => (
                <div
                  key={key}
                  className="flex justify-between border-b border-zinc-800 pb-2"
                >
                  <span className="text-zinc-400 text-sm">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-white text-sm font-mono max-w-[250px] truncate">
                    {String(value ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
