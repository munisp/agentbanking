import { toast } from 'sonner';
import { exportToExcel, exportToPDF } from "@/lib/exportUtils";
import { Download, Filter, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTenantBranding } from "../contexts/TenantBrandingContext";
import { auditService } from "../services/audit";
import type { AuditEventType, AuditLog } from "../types/audit";

export default function AuditTrails() {
  const { primaryColor } = useTenantBranding();
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all");
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  // Fetch audit logs on mount
  useEffect(() => {
    const fetchAuditLogs = async () => {
      try {
        setLoading(true);
        const logs = await auditService.getAuditLogs();
        setAuditLogs(logs.data ?? []);
      } catch (error) {
        console.error("Failed to fetch audit logs:", error);
        toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchAuditLogs();
  }, []);

  // Filter audit logs
  const filteredLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      const matchesSearch =
        !searchTerm ||
        log.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.actor_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.event_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        JSON.stringify(log.event_data)
          .toLowerCase()
          .includes(searchTerm.toLowerCase());

      const matchesEventType =
        eventTypeFilter === "all" ||
        log.event_type.toLowerCase() === eventTypeFilter.toLowerCase();

      return matchesSearch && matchesEventType;
    });
  }, [auditLogs, searchTerm, eventTypeFilter]);

  // Get unique event types for filter
  const eventTypes = useMemo(() => {
    const types = new Set<string>();
    auditLogs.forEach((log) => types.add(log.event_type));
    return Array.from(types).sort();
  }, [auditLogs]);

  // Statistics
  const stats = useMemo(() => {
    const eventTypeCounts: Record<string, number> = {};
    auditLogs.forEach((log) => {
      eventTypeCounts[log.event_type] =
        (eventTypeCounts[log.event_type] || 0) + 1;
    });

    return {
      total: auditLogs.length,
      eventTypeCounts,
      uniqueActors: new Set(auditLogs.map((log) => log.actor_id)).size,
    };
  }, [auditLogs]);

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // Get event type badge color
  const getEventTypeBadge = (eventType: AuditEventType) => {
    const colorMap: Record<string, string> = {
      LOGIN: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
      LOGOUT:
        "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-300",
      TRANSFER:
        "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
      WITHDRAWAL:
        "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
      DEPOSIT:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
      CREATE:
        "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
      UPDATE:
        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
      DELETE: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    };

    return (
      colorMap[eventType] ||
      "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-300"
    );
  };

  // Export handlers
  const handleExportExcel = () => {
    const exportData = filteredLogs.map((log) => ({
      ID: log.id,
      "Actor ID": log.actor_id,
      "Event Type": log.event_type,
      Timestamp: formatTimestamp(log.timestamp),
      "Event Data": JSON.stringify(log.event_data),
      "Tenant ID": log.tenant_id,
    }));

    exportToExcel(exportData, "audit-trails");
  };

  const handleExportPDF = () => {
    const columns = ["ID", "Actor", "Event", "Timestamp"];
    const exportData = filteredLogs.map((log) => ({
      ID: log.id.substring(0, 8),
      Actor: log.actor_id.substring(0, 8),
      Event: log.event_type,
      Timestamp: formatTimestamp(log.timestamp),
    }));

    exportToPDF(exportData, columns, "audit-trails", "Audit Trails Report");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Audit Trails
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          View and track all system activities and user actions
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Total Events
              </p>
              <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                {stats.total.toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Unique Users
              </p>
              <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                {stats.uniqueActors}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Event Types
              </p>
              <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                {eventTypes.length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 gap-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search audit logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-4 text-gray-900 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-400"
            />
          </div>

          {/* Event Type Filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <select
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="appearance-none rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-10 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              <option value="all">All Events</option>
              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Export Buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleExportExcel}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            <Download className="h-4 w-4" />
            Excel
          </button>
          <button
            onClick={handleExportPDF}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            <Download className="h-4 w-4" />
            PDF
          </button>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Event Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Actor ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Event Data
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <div className="flex items-center justify-center">
                      <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600"></div>
                      <span className="ml-3 text-gray-600 dark:text-gray-400">
                        Loading audit logs...
                      </span>
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <p className="text-gray-500 dark:text-gray-400">
                      No audit logs found
                    </p>
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr
                    key={log.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${getEventTypeBadge(log.event_type)}`}
                      >
                        {log.event_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                      <span className="font-mono text-xs">
                        {log.actor_id.substring(0, 8)}...
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                      <div className="max-w-xs truncate">
                        {log.event_type === "LOGIN" && log.event_data.email && (
                          <span>{log.event_data.email}</span>
                        )}
                        {log.event_type === "TRANSFER" && (
                          <span>
                            {log.event_data.amount} ({log.event_data.payer} →{" "}
                            {log.event_data.payee})
                          </span>
                        )}
                        {log.event_type !== "LOGIN" &&
                          log.event_type !== "TRANSFER" && (
                            <span className="font-mono text-xs">
                              {JSON.stringify(log.event_data).substring(0, 50)}
                              ...
                            </span>
                          )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <button
                        onClick={() => setSelectedLog(log)}
                        style={{ color: primaryColor }}
                        className="font-medium hover:underline"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Audit Log Details
              </h2>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <svg
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  ID
                </label>
                <p className="mt-1 font-mono text-sm text-gray-900 dark:text-gray-100">
                  {selectedLog.id}
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Actor ID
                </label>
                <p className="mt-1 font-mono text-sm text-gray-900 dark:text-gray-100">
                  {selectedLog.actor_id}
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Event Type
                </label>
                <p className="mt-1">
                  <span
                    className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${getEventTypeBadge(selectedLog.event_type)}`}
                  >
                    {selectedLog.event_type}
                  </span>
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Timestamp
                </label>
                <p className="mt-1 text-sm text-gray-900 dark:text-gray-100">
                  {formatTimestamp(selectedLog.timestamp)}
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Event Data
                </label>
                <pre className="mt-1 overflow-x-auto rounded-lg bg-gray-100 p-4 text-xs text-gray-900 dark:bg-gray-900 dark:text-gray-100">
                  {JSON.stringify(selectedLog.event_data, null, 2)}
                </pre>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Tenant ID
                </label>
                <p className="mt-1 font-mono text-sm text-gray-900 dark:text-gray-100">
                  {selectedLog.tenant_id}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Created At
                  </label>
                  <p className="mt-1 text-sm text-gray-900 dark:text-gray-100">
                    {formatTimestamp(selectedLog.created_at)}
                  </p>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Updated At
                  </label>
                  <p className="mt-1 text-sm text-gray-900 dark:text-gray-100">
                    {formatTimestamp(selectedLog.updated_at)}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="rounded-lg bg-gray-200 px-4 py-2 text-gray-700 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
