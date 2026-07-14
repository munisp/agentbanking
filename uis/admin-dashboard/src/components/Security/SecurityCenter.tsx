import {
    Activity,
    AlertTriangle,
    CheckCircle,
    Eye,
    RefreshCw,
    Shield,
    Trash2,
    X,
} from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import { serviceIntegrationsApi } from "../../utils/api";

type AlertStatus =
  | "NEW"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "FALSE_POSITIVE"
  | "ARCHIVED";
type AlertSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

interface SecurityAlert {
  id: string;
  alert_id: string;
  title: string;
  severity: AlertSeverity;
  status: AlertStatus;
  source: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

interface ActivityLog {
  id: string;
  user_id: string;
  action: string;
  notes?: string;
  timestamp: string;
}

const SEVERITY_BADGE: Record<AlertSeverity, string> = {
  CRITICAL: "bg-red-100 text-red-800 border border-red-200",
  HIGH: "bg-orange-100 text-orange-800 border border-orange-200",
  MEDIUM: "bg-yellow-100 text-yellow-700 border border-yellow-200",
  LOW: "bg-blue-100 text-blue-700 border border-blue-200",
  INFO: "bg-gray-100 text-gray-600 border border-gray-200",
};

const STATUS_BADGE: Record<AlertStatus, string> = {
  NEW: "bg-red-50 text-red-600",
  IN_PROGRESS: "bg-yellow-50 text-yellow-700",
  RESOLVED: "bg-green-50 text-green-700",
  FALSE_POSITIVE: "bg-gray-50 text-gray-500",
  ARCHIVED: "bg-gray-100 text-gray-400",
};

const fmtDate = (d: string) =>
  new Date(d).toLocaleString("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
  });

const SecurityCenter: React.FC = () => {
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selectedAlert, setSelectedAlert] = useState<SecurityAlert | null>(
    null,
  );
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterSeverity, setFilterSeverity] = useState<string>("");

  // Create alert form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newAlertId, setNewAlertId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newSeverity, setNewSeverity] = useState<AlertSeverity>("MEDIUM");
  const [newSource, setNewSource] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await serviceIntegrationsApi.securityMonitoring.listAlerts({
        status: filterStatus || undefined,
        severity: filterSeverity || undefined,
        limit: 100,
      });
      setAlerts((data as SecurityAlert[]) ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterSeverity]);

  useEffect(() => {
    void loadAlerts();
  }, [loadAlerts]);

  const openAlert = async (alert: SecurityAlert) => {
    setSelectedAlert(alert);
    setLogsLoading(true);
    try {
      const data = await serviceIntegrationsApi.securityMonitoring.getLogs(
        alert.id,
      );
      setLogs((data as ActivityLog[]) ?? []);
    } catch {
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const updateStatus = async (alertId: string, status: AlertStatus) => {
    setError("");
    try {
      await serviceIntegrationsApi.securityMonitoring.updateAlert(alertId, {
        status,
      });
      setSuccess(`Alert marked as ${status}`);
      if (selectedAlert?.id === alertId) {
        setSelectedAlert((prev) => (prev ? { ...prev, status } : prev));
      }
      void loadAlerts();
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const deleteAlert = async (alertId: string) => {
    if (!window.confirm("Delete this alert? This cannot be undone.")) return;
    setError("");
    try {
      await serviceIntegrationsApi.securityMonitoring.deleteAlert(alertId);
      setSuccess("Alert deleted");
      if (selectedAlert?.id === alertId) setSelectedAlert(null);
      void loadAlerts();
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const createAlert = async () => {
    if (!newAlertId || !newTitle || !newSource) return;
    setCreating(true);
    setError("");
    try {
      await serviceIntegrationsApi.securityMonitoring.createAlert({
        alert_id: newAlertId,
        title: newTitle,
        severity: newSeverity,
        source: newSource,
        description: newDescription || undefined,
      });
      setSuccess("Alert created");
      setShowCreateForm(false);
      setNewAlertId("");
      setNewTitle("");
      setNewSource("");
      setNewDescription("");
      void loadAlerts();
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;
  const highCount = alerts.filter((a) => a.severity === "HIGH").length;
  const newCount = alerts.filter((a) => a.status === "NEW").length;
  const resolvedCount = alerts.filter((a) => a.status === "RESOLVED").length;

  const inputClass =
    "border border-gray-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)]";
  const btnPrimary =
    "bg-[var(--tenant-primary-color,#002082)] text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60";
  const btnSecondary =
    "border border-gray-300 text-gray-700 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-50";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="h-6 w-6 text-[var(--tenant-primary-color,#002082)]" />
            Security Monitoring
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            Real-time security alerts and incident tracking
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className={btnSecondary}
            onClick={() => setShowCreateForm(true)}
          >
            + New Alert
          </button>
          <button
            className={btnPrimary}
            onClick={() => void loadAlerts()}
            disabled={loading}
          >
            <RefreshCw
              className={`h-4 w-4 inline mr-1 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          {success}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Alerts",
            value: alerts.length,
            color: "border-blue-500",
            icon: Activity,
          },
          {
            label: "Critical",
            value: criticalCount,
            color: "border-red-500",
            icon: AlertTriangle,
          },
          {
            label: "High",
            value: highCount,
            color: "border-orange-500",
            icon: AlertTriangle,
          },
          {
            label: "New / Unresolved",
            value: newCount,
            color: "border-yellow-500",
            icon: Eye,
          },
        ].map(({ label, value, color, icon: Icon }) => (
          <div
            key={label}
            className={`bg-white rounded-lg shadow p-4 border-l-4 ${color}`}
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{label}</p>
              <Icon className="h-4 w-4 text-gray-400" />
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white border rounded-lg p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Status
          </label>
          <select
            className={inputClass + " w-40"}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All</option>
            {(
              [
                "NEW",
                "IN_PROGRESS",
                "RESOLVED",
                "FALSE_POSITIVE",
                "ARCHIVED",
              ] as AlertStatus[]
            ).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Severity
          </label>
          <select
            className={inputClass + " w-40"}
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
          >
            <option value="">All</option>
            {(
              ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] as AlertSeverity[]
            ).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Alerts List */}
        <div className="bg-white border rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">
              Alerts ({alerts.length})
            </h2>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              Loading alerts…
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No alerts found.
            </div>
          ) : (
            <div className="divide-y max-h-[520px] overflow-y-auto">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${selectedAlert?.id === alert.id ? "bg-blue-50" : ""}`}
                  onClick={() => void openAlert(alert)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 text-sm truncate">
                        {alert.title}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {alert.source} · {fmtDate(alert.created_at)}
                      </p>
                    </div>
                    <div className="flex gap-1.5 shrink-0">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_BADGE[alert.severity]}`}
                      >
                        {alert.severity}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[alert.status]}`}
                      >
                        {alert.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Alert Detail */}
        <div className="bg-white border rounded-lg shadow">
          {!selectedAlert ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              Select an alert to view details.
            </div>
          ) : (
            <div className="flex flex-col h-full">
              <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900 text-sm truncate">
                  {selectedAlert.title}
                </h2>
                <button
                  onClick={() => setSelectedAlert(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-4 space-y-4 flex-1 overflow-y-auto">
                <div className="flex flex-wrap gap-2">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_BADGE[selectedAlert.severity]}`}
                  >
                    {selectedAlert.severity}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[selectedAlert.status]}`}
                  >
                    {selectedAlert.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-gray-500">Source</p>
                    <p className="font-medium">{selectedAlert.source}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Alert ID</p>
                    <p className="font-medium font-mono text-xs">
                      {selectedAlert.alert_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Created</p>
                    <p className="font-medium">
                      {fmtDate(selectedAlert.created_at)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Updated</p>
                    <p className="font-medium">
                      {fmtDate(selectedAlert.updated_at)}
                    </p>
                  </div>
                </div>

                {selectedAlert.description && (
                  <p className="text-sm text-gray-700 bg-gray-50 rounded p-3">
                    {selectedAlert.description}
                  </p>
                )}

                {/* Status actions */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                    Update Status
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        "IN_PROGRESS",
                        "RESOLVED",
                        "FALSE_POSITIVE",
                        "ARCHIVED",
                      ] as AlertStatus[]
                    )
                      .filter((s) => s !== selectedAlert.status)
                      .map((s) => (
                        <button
                          key={s}
                          className={btnSecondary}
                          onClick={() => void updateStatus(selectedAlert.id, s)}
                        >
                          {s === "RESOLVED" && (
                            <CheckCircle className="h-3 w-3 inline mr-1 text-green-600" />
                          )}
                          {s}
                        </button>
                      ))}
                    <button
                      className="border border-red-200 text-red-600 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50"
                      onClick={() => void deleteAlert(selectedAlert.id)}
                    >
                      <Trash2 className="h-3 w-3 inline mr-1" />
                      Delete
                    </button>
                  </div>
                </div>

                {/* Activity logs */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                    Activity Log
                  </p>
                  {logsLoading ? (
                    <p className="text-sm text-gray-400">Loading…</p>
                  ) : logs.length === 0 ? (
                    <p className="text-sm text-gray-400">No activity yet.</p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {logs.map((log) => (
                        <div
                          key={log.id}
                          className="text-xs bg-gray-50 rounded p-2 border"
                        >
                          <span className="font-semibold text-gray-700">
                            {log.action}
                          </span>
                          {log.notes && (
                            <span className="text-gray-500">
                              {" "}
                              — {log.notes}
                            </span>
                          )}
                          <span className="text-gray-400 ml-2">
                            {fmtDate(log.timestamp)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Alert Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Create Security Alert
              </h3>
              <button
                onClick={() => setShowCreateForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              <input
                className={inputClass}
                placeholder="Alert ID (unique source ID) *"
                value={newAlertId}
                onChange={(e) => setNewAlertId(e.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Title *"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Source (e.g. Wazuh, OpenAppSec) *"
                value={newSource}
                onChange={(e) => setNewSource(e.target.value)}
              />
              <select
                className={inputClass}
                value={newSeverity}
                onChange={(e) =>
                  setNewSeverity(e.target.value as AlertSeverity)
                }
              >
                {(
                  [
                    "CRITICAL",
                    "HIGH",
                    "MEDIUM",
                    "LOW",
                    "INFO",
                  ] as AlertSeverity[]
                ).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <textarea
                className={inputClass}
                placeholder="Description (optional)"
                rows={3}
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                className={btnSecondary}
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
              <button
                className={btnPrimary}
                disabled={creating || !newAlertId || !newTitle || !newSource}
                onClick={() => void createAlert()}
              >
                {creating ? "Creating…" : "Create Alert"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SecurityCenter;
