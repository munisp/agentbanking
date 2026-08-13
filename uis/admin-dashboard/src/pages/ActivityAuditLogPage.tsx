import { trpc } from "@/lib/trpc";
/**
 * Sprint 52 — Activity Audit Log
 * F04: Comprehensive audit trail with search, filter, and export
 */
// @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
import { DashboardLayout } from "@/components/DashboardLayout";
import { PageErrorBoundary } from "@/components/ErrorBoundary";
import { useState, useMemo } from "react";
import {
  Search,
  Download,
  Clock,
  User,
  Shield,
  Activity,
  FileText,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
} from "lucide-react";

function AuditLogContent() {
  const [search, setSearch] = useState("");
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const {
    data: liveData,
    isLoading,
    isError,
    error,
  } = trpc.activityAuditLog.list.useQuery(undefined, {
    retry: 1,
  });
  const [actionFilter, setActionFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedLog, setSelectedLog] = useState<any | null>(null);

  const auditLogs = useMemo(
    () => (Array.isArray(liveData) ? (liveData as any[]) : []),
    [liveData]
  );
  const hasData = auditLogs.length > 0;

  const filtered = useMemo(() => {
    return auditLogs.filter(log => {
      if (
        search &&
        !JSON.stringify(log).toLowerCase().includes(search.toLowerCase())
      )
        return false;
      if (actionFilter !== "all" && log.action !== actionFilter) return false;
      if (statusFilter !== "all" && log.status !== statusFilter) return false;
      return true;
    });
  }, [auditLogs, search, actionFilter, statusFilter]);

  const actions = [...new Set(auditLogs.map(l => l.action))];
  const statuses = [...new Set(auditLogs.map(l => l.status))];

  const statusIcon = (s: string) => {
    if (s === "success")
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (s === "warning")
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    if (s === "error") return <XCircle className="h-4 w-4 text-red-500" />;
    return <Activity className="h-4 w-4 text-muted-foreground" />;
  };

  if (isError) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/20 p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-2" />
          <h2 className="text-lg font-semibold text-red-700 dark:text-red-400">
            Failed to load audit log
          </h2>
          <p className="text-sm text-red-600 dark:text-red-400 mt-1">
            {error?.message || "An unexpected error occurred."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Activity Audit Log</h1>
          <p className="text-sm text-muted-foreground">
            Complete audit trail of all system actions
          </p>
        </div>
        <button
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md border hover:bg-accent text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={filtered.length === 0}
          title={
            filtered.length === 0
              ? "No audit data available to export"
              : "Export audit log as CSV"
          }
          onClick={() => {
            if (filtered.length === 0) return;
            const csv = [
              "Timestamp,Actor,Role,Action,Resource,ID,Details,IP,Status",
              ...filtered.map(
                l =>
                  `"${l.timestamp}","${l.actor}","${l.actorRole}","${l.action}","${l.resource}","${l.resourceId}","${l.details}","${l.ip}","${l.status}"`
              ),
            ].join("\n");
            const blob = new Blob([csv], { type: "text/csv" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "audit-log.csv";
            a.click();
          }}
        >
          <Download className="h-4 w-4" /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-md border bg-background text-sm"
          />
        </div>
        <select
          value={actionFilter}
          onChange={e => setActionFilter(e.target.value)}
          className="px-3 py-2 rounded-md border bg-background text-sm"
        >
          <option value="all">All Actions</option>
          {actions.map(a => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-md border bg-background text-sm"
        >
          <option value="all">All Statuses</option>
          {statuses.map(s => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          {
            label: "Total Events",
            value: auditLogs.length,
            icon: FileText,
          },
          {
            label: "Successful",
            value: auditLogs.filter(l => l.status === "success").length,
            icon: CheckCircle,
          },
          {
            label: "Warnings",
            value: auditLogs.filter(l => l.status === "warning").length,
            icon: AlertTriangle,
          },
          {
            label: "Failures",
            value: auditLogs.filter(l => l.status === "error").length,
            icon: XCircle,
          },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <stat.icon className="h-4 w-4" /> {stat.label}
            </div>
            <div className="text-2xl font-bold">
              {isLoading ? "…" : stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Log Table */}
      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Time</th>
              <th className="text-left p-3 font-medium">Actor</th>
              <th className="text-left p-3 font-medium">Action</th>
              <th className="text-left p-3 font-medium">Resource</th>
              <th className="text-left p-3 font-medium">Details</th>
              <th className="text-left p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td
                  colSpan={7}
                  className="p-6 text-center text-muted-foreground"
                >
                  Loading audit log…
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="p-6 text-center text-muted-foreground"
                >
                  {hasData
                    ? "No log entries match the current filters."
                    : "No audit log entries available."}
                </td>
              </tr>
            ) : (
              filtered.map(log => (
                <tr key={log.id} className="border-t hover:bg-muted/30">
                  <td className="p-3 whitespace-nowrap">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1">
                      {log.actorRole === "system" ? (
                        <Shield className="h-3 w-3" />
                      ) : (
                        <User className="h-3 w-3" />
                      )}
                      <span className="truncate max-w-[120px]">{log.actor}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        log.action === "DELETE"
                          ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                          : log.action === "CREATE"
                            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                            : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      }`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-xs">
                    {log.resource}/{log.resourceId}
                  </td>
                  <td className="p-3 max-w-[250px] truncate">{log.details}</td>
                  <td className="p-3">{statusIcon(log.status)}</td>
                  <td className="p-3">
                    <button
                      onClick={() => setSelectedLog(log)}
                      className="p-1 rounded hover:bg-accent"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSelectedLog(null)}
        >
          <div
            className="bg-card rounded-lg p-6 max-w-lg w-full mx-4 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Audit Log Detail</h3>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-muted-foreground hover:text-foreground"
              >
                &times;
              </button>
            </div>
            <div className="space-y-3 text-sm">
              {Object.entries(selectedLog).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-muted-foreground capitalize">
                    {k.replace(/([A-Z])/g, " $1")}
                  </span>
                  <span className="font-mono text-right max-w-[250px] truncate">
                    {String(v)}
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

export default function ActivityAuditLogPage() {
  return (
    <DashboardLayout>
      <PageErrorBoundary>
        <AuditLogContent />
      </PageErrorBoundary>
    </DashboardLayout>
  );
}
