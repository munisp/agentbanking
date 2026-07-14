import {
    AlertTriangle,
    CheckCircle,
    Clock,
    Filter,
    MapPin,
    RefreshCw,
    Search,
    X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api, GeofenceViolation } from "../../utils/api";

const GeofenceViolationsMonitor: React.FC = () => {
  const [violations, setViolations] = useState<GeofenceViolation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "active" | "resolved"
  >("active");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedViolation, setSelectedViolation] =
    useState<GeofenceViolation | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  // Load violations
  const loadViolations = async () => {
    setLoading(true);
    setError(null);
    try {
      let data;
      if (statusFilter === "active") {
        data = await api.getActiveViolations({ hours: 8760, limit: 100 });
      } else {
        const resolved = statusFilter === "resolved" ? true : undefined;
        data = await api.getAllViolations({ days: 365, resolved, limit: 100 });
      }
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

  // Auto-refresh every 30 seconds
  useEffect(() => {
    loadViolations();

    if (autoRefresh) {
      const interval = setInterval(loadViolations, 30000);
      return () => clearInterval(interval);
    }
  }, [statusFilter, autoRefresh]);

  // Handle resolving violation
  const handleResolve = async () => {
    if (!selectedViolation) return;

    setResolving(true);
    try {
      await api.resolveViolation(selectedViolation.id, resolveNotes);
      setSelectedViolation(null);
      setResolveNotes("");
      loadViolations();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to resolve violation",
      );
    } finally {
      setResolving(false);
    }
  };

  // Calculate time ago
  const timeAgo = (timestamp: string): string => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now.getTime() - time.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Calculate badge color
  const getBadgeColor = (distanceKm: number, radiusKm: number): string => {
    const exceededBy = ((distanceKm - radiusKm) / radiusKm) * 100;
    if (exceededBy > 100) return "bg-red-600 text-white";
    if (exceededBy > 50) return "bg-orange-500 text-white";
    return "bg-yellow-500 text-white";
  };

  // Filter violations
  const filteredViolations = violations.filter((v) => {
    const matchesSearch =
      v.device_id?.toLowerCase().includes(search.toLowerCase()) ||
      v.agent_id?.toLowerCase().includes(search.toLowerCase()) ||
      v.geofence_name?.toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  // Stats
  const stats = {
    total: violations.length,
    active: violations.filter((v) => !v.was_resolved).length,
    resolved: violations.filter((v) => v.was_resolved).length,
    criticalDistance: violations.filter(
      (v) => !v.was_resolved && v.distance_from_center_km - v.radius_km > 5,
    ).length,
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Geofence Violations Monitor
          </h1>
          <p className="text-gray-500 mt-1">
            Real-time tracking of POS devices outside allowed areas
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-[var(--tenant-primary-color,#002082)] focus:ring-[var(--tenant-secondary-color,#6CC049)]"
            />
            Auto-refresh (30s)
          </label>
          <button
            onClick={loadViolations}
            disabled={loading}
            className="p-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Violations",
            value: stats.total,
            icon: AlertTriangle,
            color: "text-gray-500",
          },
          {
            label: "Active",
            value: stats.active,
            icon: Clock,
            color: "text-orange-500",
          },
          {
            label: "Resolved",
            value: stats.resolved,
            icon: CheckCircle,
            color: "text-green-500",
          },
          {
            label: "Critical (>5km)",
            value: stats.criticalDistance,
            icon: AlertTriangle,
            color: "text-red-500",
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
              setStatusFilter(e.target.value as "all" | "active" | "resolved")
            }
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value="active">Active Only</option>
            <option value="all">All Violations</option>
            <option value="resolved">Resolved Only</option>
          </select>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Violations Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {loading && filteredViolations.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-500">Loading violations...</span>
          </div>
        ) : filteredViolations.length === 0 ? (
          <div className="text-center py-12">
            <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
            <p className="text-gray-500">
              {statusFilter === "active"
                ? "No active violations - all devices within boundaries!"
                : "No violations found"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {[
                    "Device / Agent",
                    "Location Name",
                    "Distance Outside",
                    "Current Position",
                    "Violation Time",
                    "Status",
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
                {filteredViolations.map((violation) => {
                  const outsideBy =
                    violation.distance_from_center_km - violation.radius_km;
                  return (
                    <tr
                      key={violation.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {violation.device_id}
                          </p>
                          <p className="text-xs text-gray-500">
                            Agent: {violation.agent_id}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-gray-400" />
                          <span className="text-sm text-gray-700">
                            {violation.geofence_name || "Unnamed Location"}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getBadgeColor(
                            violation.distance_from_center_km,
                            violation.radius_km,
                          )}`}
                        >
                          <AlertTriangle className="w-3 h-3" />
                          {outsideBy.toFixed(2)} km outside
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs text-gray-600 font-mono">
                          {violation.current_latitude.toFixed(6)},
                        </p>
                        <p className="text-xs text-gray-600 font-mono">
                          {violation.current_longitude.toFixed(6)}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm text-gray-900">
                            {timeAgo(violation.violation_time)}
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(
                              violation.violation_time,
                            ).toLocaleDateString()}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {violation.was_resolved ? (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            <CheckCircle className="w-3 h-3" />
                            Resolved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                            <Clock className="w-3 h-3" />
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {!violation.was_resolved && (
                          <button
                            onClick={() => setSelectedViolation(violation)}
                            className="text-sm text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] font-medium"
                          >
                            Resolve
                          </button>
                        )}
                        {violation.was_resolved && violation.admin_notes && (
                          <span className="text-xs text-gray-500">
                            {violation.admin_notes}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Resolve Modal */}
      {selectedViolation && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
            {/* Modal Header */}
            <div className="border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">
                Resolve Geofence Violation
              </h2>
              <button
                onClick={() => setSelectedViolation(null)}
                className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg p-2 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-500">Device:</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {selectedViolation.device_id}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Location:</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {selectedViolation.geofence_name}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Distance Outside:</span>
                    <span className="ml-2 font-medium text-orange-600">
                      {(
                        selectedViolation.distance_from_center_km -
                        selectedViolation.radius_km
                      ).toFixed(2)}{" "}
                      km
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Time:</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {timeAgo(selectedViolation.violation_time)}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Resolution Notes (optional)
                </label>
                <textarea
                  value={resolveNotes}
                  onChange={(e) => setResolveNotes(e.target.value)}
                  placeholder="e.g., Agent confirmed device returned to store, false alarm, etc."
                  rows={3}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="border-t border-gray-200 px-6 py-4 flex gap-3">
              <button
                onClick={() => setSelectedViolation(null)}
                disabled={resolving}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                disabled={resolving}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
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
          </div>
        </div>
      )}
    </div>
  );
};

export default GeofenceViolationsMonitor;
