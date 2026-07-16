import {
    Activity,
    Download,
    FileText,
    Search,
    User,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { getTenantHeaders } from "../../services/tenant/getTenantHeaders";
import { tenantService } from "../../services/tenant/tenantService";

interface AuditLog {
  id: string;
  actor_id: string;
  event_type: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  timestamp: string;
  event_data: {
    path?: string;
    method?: string;
    status_code?: number;
    email?: string;
    payee?: string;
    payer?: string;
    amount?: string;
    transaction_id?: string;
    [key: string]: unknown;
  };
  tenant_id: string;
}

const AuditLogs: React.FC = () => {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedAction, setSelectedAction] = useState("All");
  const [dateRange, setDateRange] = useState({ start: "", end: "" });

  useEffect(() => {
    const fetchAuditLogs = async () => {
      try {
        setLoading(true);
        setError(null);

        const tenantConfig = tenantService.getTenantConfig();
        const tenantId =
          tenantConfig?.tenant_id ||
          import.meta.env.VITE_TENANT_ID ||
          localStorage.getItem("tenant_id") ||
          localStorage.getItem("tenantId");

        if (!tenantId) {
          throw new Error("Tenant ID not found");
        }

        const baseUrl =
          import.meta.env.VITE_API_URL || "https://54agent.upi.dev";
        const response = await fetch(
          `${baseUrl}/audit/audits/tenant/${tenantId}`,
          {
            headers: {
              "Content-Type": "application/json",
              ...getTenantHeaders(tenantConfig),
              ...(localStorage.getItem("auth_token")
                ? {
                    Authorization: `Bearer ${localStorage.getItem("auth_token")}`,
                  }
                : {}),
            },
          },
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch audit logs: ${response.statusText}`);
        }

        const data = await response.json();
        setAuditLogs(Array.isArray(data) ? data : []);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to fetch audit logs";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchAuditLogs();
  }, []);

  const actionTypes = useMemo(
    () => ["All", ...Array.from(new Set(auditLogs.map((l) => l.event_type)))],
    [auditLogs],
  );

  const filteredLogs = auditLogs.filter((log) => {
    const matchesSearch =
      log.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.event_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (log.event_data.path &&
        log.event_data.path
          .toLowerCase()
          .includes(searchTerm.toLowerCase())) ||
      (log.event_data.email &&
        log.event_data.email
          .toLowerCase()
          .includes(searchTerm.toLowerCase())) ||
      (log.event_data.transaction_id &&
        log.event_data.transaction_id
          .toLowerCase()
          .includes(searchTerm.toLowerCase()));

    const matchesAction =
      selectedAction === "All" || log.event_type === selectedAction;

    const matchesDateRange =
      (!dateRange.start ||
        new Date(log.timestamp) >= new Date(dateRange.start)) &&
      (!dateRange.end ||
        new Date(log.timestamp) <= new Date(`${dateRange.end}T23:59:59`));

    return matchesSearch && matchesAction && matchesDateRange;
  });

  const getEventTypeBadgeColor = (eventType: string) => {
    const colors: Record<string, string> = {
      LOGIN: "bg-purple-100 text-purple-800",
      LOGOUT: "bg-gray-100 text-gray-800",
      TRANSFER: "bg-blue-100 text-blue-800",
      CREATE: "bg-green-100 text-green-800",
      UPDATE: "bg-yellow-100 text-yellow-800",
      DELETE: "bg-red-100 text-red-800",
      WITHDRAWAL: "bg-orange-100 text-orange-800",
      DEPOSIT: "bg-emerald-100 text-emerald-800",
    };
    return colors[eventType.toUpperCase()] || "bg-gray-100 text-gray-800";
  };

  const stats = {
    total: auditLogs.length,
    today: auditLogs.filter((log) => {
      const today = new Date();
      const logDate = new Date(log.timestamp);
      return logDate.toDateString() === today.toDateString();
    }).length,
    loginEvents: auditLogs.filter((log) => log.event_type === "LOGIN").length,
    uniqueUsers: new Set(auditLogs.map((log) => log.actor_id)).size,
  };

  const exportLogs = () => {
    alert("Exporting audit logs...");
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Audit Logs</h1>
          <p className="text-gray-500 mt-1">
            Track all system activities and user actions
          </p>
        </div>
        <button
          onClick={exportLogs}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          Export Logs
        </button>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Logs</p>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {loading ? "..." : stats.total}
              </p>
            </div>
            <FileText className="w-10 h-10 text-[var(--tenant-primary-color,#004F71)]" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Today</p>
              <p className="text-2xl font-bold text-green-600 mt-2">
                {loading ? "..." : stats.today}
              </p>
            </div>
            <Activity className="w-10 h-10 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Login Events</p>
              <p className="text-2xl font-bold text-red-600 mt-2">
                {loading ? "..." : stats.loginEvents}
              </p>
            </div>
            <Activity className="w-10 h-10 text-red-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Unique Users</p>
              <p className="text-2xl font-bold text-purple-600 mt-2">
                {loading ? "..." : stats.uniqueUsers}
              </p>
            </div>
            <User className="w-10 h-10 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              {actionTypes.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </div>
          <div>
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) =>
                setDateRange((prev) => ({ ...prev, start: e.target.value }))
              }
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            />
          </div>
          <div>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) =>
                setDateRange((prev) => ({ ...prev, end: e.target.value }))
              }
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Event Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tenant ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td
                    className="px-6 py-6 text-sm text-gray-500 text-center"
                    colSpan={5}
                  >
                    Loading audit logs...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td
                    className="px-6 py-6 text-sm text-gray-500 text-center"
                    colSpan={5}
                  >
                    No audit logs found
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="text-sm">
                        <p className="font-medium text-gray-900">
                          {new Date(log.timestamp).toLocaleDateString()}
                        </p>
                        <p className="text-gray-500">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-mono text-gray-700 truncate max-w-[180px]">
                        {log.id}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getEventTypeBadgeColor(log.event_type)}`}
                      >
                        {log.event_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {log.tenant_id}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 max-w-xs">
                      {log.event_data.path && (
                        <div className="truncate">
                          <span className="font-medium">{log.event_data.method}</span>{" "}
                          {log.event_data.path}
                        </div>
                      )}
                      {log.event_data.status_code !== undefined && (
                        <div>Status: {log.event_data.status_code}</div>
                      )}
                      {log.event_data.email && (
                        <div>Email: {log.event_data.email}</div>
                      )}
                      {log.event_data.transaction_id && (
                        <div>Transaction: {log.event_data.transaction_id}</div>
                      )}
                      {log.event_data.amount && (
                        <div>Amount: ₦{log.event_data.amount}</div>
                      )}
                      {log.event_data.payer && log.event_data.payee && (
                        <div>
                          {log.event_data.payer} → {log.event_data.payee}
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="bg-white px-6 py-4 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing <span className="font-medium">1</span> to{" "}
            <span className="font-medium">{filteredLogs.length}</span> of{" "}
            <span className="font-medium">{auditLogs.length}</span> results
          </div>
          <div className="flex gap-2">
            <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
              Previous
            </button>
            <button className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]">
              1
            </button>
            <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuditLogs;
