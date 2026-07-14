import {
    AlertCircle,
    CheckCircle,
    Clock,
    Filter,
    MapPin,
    RefreshCw,
    Search,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api, GeofenceViolation } from "../../utils/api";

const GeofenceViolations: React.FC = () => {
  const [violations, setViolations] = useState<GeofenceViolation[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<"active" | "all">("active");
  const [daysFilter, setDaysFilter] = useState(365);
  const [search, setSearch] = useState("");

  // Selected violation for details/resolution
  const [selectedViolation, setSelectedViolation] =
    useState<GeofenceViolation | null>(null);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolveNotes, setResolveNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    loadViolations();
    loadStats();
  }, [statusFilter, daysFilter]);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadViolations();
      loadStats();
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, statusFilter, daysFilter]);

  const loadViolations = async () => {
    setLoading(true);
    setError(null);
    try {
      const data =
        statusFilter === "active"
          ? await api.getActiveViolations({
              hours: daysFilter * 24,
              limit: 200,
            })
          : await api.getAllViolations({ days: daysFilter, limit: 200 });

      setViolations(data.violations);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load violations",
      );
      console.error("Error loading violations:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getViolationStats({ days: daysFilter });
      setStats(data);
    } catch (err) {
      console.error("Error loading stats:", err);
    }
  };

  const handleResolve = async () => {
    if (!selectedViolation) return;

    setResolving(true);
    try {
      await api.resolveViolation(selectedViolation.id, resolveNotes);
      setShowResolveModal(false);
      setResolveNotes("");
      setSelectedViolation(null);
      loadViolations();
      loadStats();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to resolve violation",
      );
    } finally {
      setResolving(false);
    }
  };

  const filteredViolations = violations.filter((v) => {
    const matchesSearch =
      v.device_id.toLowerCase().includes(search.toLowerCase()) ||
      v.agent_id.toLowerCase().includes(search.toLowerCase()) ||
      v.geofence_name?.toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  const getTimeSince = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Geofence Violations
          </h1>
          <p className="text-gray-500 mt-1">
            Monitor POS device movements outside allowed areas
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (30s)
          </label>
          <button
            onClick={() => {
              loadViolations();
              loadStats();
            }}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2 text-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: "Total Violations",
              value: stats.total_violations,
              icon: AlertCircle,
              color: "text-gray-500",
            },
            {
              label: "Active",
              value: stats.active_violations,
              icon: XCircle,
              color: "text-red-500",
            },
            {
              label: "Resolved",
              value: stats.resolved_violations,
              icon: CheckCircle,
              color: "text-green-500",
            },
            {
              label: "Last " + daysFilter + " Days",
              value: stats.period_days + "d",
              icon: Clock,
              color: "text-[var(--tenant-primary-color,#002082)]",
            },
          ].map((stat) => (
            <div key={stat.label} className="bg-white rounded-xl shadow p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">
                    {stat.label}
                  </p>
                  <p className="text-2xl font-bold text-gray-900 mt-1">
                    {stat.value}
                  </p>
                </div>
                <stat.icon className={`w-10 h-10 ${stat.color}`} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by device, agent, or location..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as "active" | "all")
            }
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value="active">Active Only</option>
            <option value="all">All Violations</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-400" />
          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>
      </div>

      {/* Violations Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 border-b border-red-200">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="w-4 h-4" />
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {[
                  "Status",
                  "Device ID",
                  "Agent",
                  "Location",
                  "Distance",
                  "Time",
                  "Actions",
                ].map((col) => (
                  <th
                    key={col}
                    className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && filteredViolations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <RefreshCw className="w-8 h-8 mx-auto mb-2 text-gray-400 animate-spin" />
                    <p className="text-gray-500">Loading violations...</p>
                  </td>
                </tr>
              ) : filteredViolations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                    <p className="text-lg font-medium text-gray-900">
                      No violations found
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      All POS devices are within their geofence boundaries
                    </p>
                  </td>
                </tr>
              ) : (
                filteredViolations.map((violation) => (
                  <tr
                    key={violation.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      {violation.was_resolved ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          <CheckCircle className="w-3 h-3" />
                          Resolved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          <XCircle className="w-3 h-3" />
                          Active
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-semibold text-gray-900">
                        {violation.device_id}
                      </p>
                      <p className="text-xs text-gray-500">
                        {violation.geofence_name || "Unnamed geofence"}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-700">
                        {violation.agent_id}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-start gap-1 text-sm text-gray-600">
                        <MapPin className="w-3 h-3 mt-0.5 flex-shrink-0" />
                        <div>
                          <p>{violation.current_latitude.toFixed(4)},</p>
                          <p>{violation.current_longitude.toFixed(4)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-red-600">
                          {violation.distance_from_center_km.toFixed(2)} km
                        </p>
                        <p className="text-xs text-gray-500">
                          Limit: {violation.radius_km.toFixed(2)} km
                        </p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-700">
                        {getTimeSince(violation.violation_time)}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(violation.violation_time).toLocaleString()}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setSelectedViolation(violation);
                            setShowResolveModal(true);
                          }}
                          disabled={violation.was_resolved}
                          className="text-sm text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] font-medium disabled:text-gray-400 disabled:cursor-not-allowed"
                        >
                          {violation.was_resolved ? "View" : "Resolve"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Resolve Modal */}
      {showResolveModal && selectedViolation && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {selectedViolation.was_resolved
                    ? "Violation Details"
                    : "Resolve Violation"}
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Device: {selectedViolation.device_id}
                </p>
              </div>
              <button
                onClick={() => {
                  setShowResolveModal(false);
                  setResolveNotes("");
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase">
                    Agent ID
                  </p>
                  <p className="text-sm text-gray-900 mt-1">
                    {selectedViolation.agent_id}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase">
                    Distance
                  </p>
                  <p className="text-sm text-gray-900 mt-1">
                    {selectedViolation.distance_from_center_km.toFixed(2)} km
                    (limit: {selectedViolation.radius_km.toFixed(2)} km)
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase">
                    Violation Time
                  </p>
                  <p className="text-sm text-gray-900 mt-1">
                    {new Date(
                      selectedViolation.violation_time,
                    ).toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase">
                    Status
                  </p>
                  <p className="text-sm text-gray-900 mt-1">
                    {selectedViolation.was_resolved ? "Resolved" : "Active"}
                  </p>
                </div>
              </div>

              {selectedViolation.resolved_at && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-xs font-medium text-green-700">
                    Resolved at:{" "}
                    {new Date(selectedViolation.resolved_at).toLocaleString()}
                  </p>
                  {selectedViolation.admin_notes && (
                    <p className="text-sm text-green-800 mt-2">
                      {selectedViolation.admin_notes}
                    </p>
                  )}
                </div>
              )}

              {!selectedViolation.was_resolved && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Resolution Notes (optional)
                  </label>
                  <textarea
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                    rows={3}
                    placeholder="Add notes about how this was resolved..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
              )}
            </div>

            {!selectedViolation.was_resolved && (
              <div className="border-t border-gray-200 px-6 py-4 flex gap-3">
                <button
                  onClick={() => {
                    setShowResolveModal(false);
                    setResolveNotes("");
                  }}
                  disabled={resolving}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleResolve}
                  disabled={resolving}
                  className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {resolving ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Resolving...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Mark as Resolved
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GeofenceViolations;
