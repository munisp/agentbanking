import { AlertCircle, ArrowRight, MapPin, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, GeofenceViolation } from "../../utils/api";

interface ViolationsWidgetProps {
  onViolationClick?: (violation: GeofenceViolation) => void;
}

const ViolationsWidget: React.FC<ViolationsWidgetProps> = ({
  onViolationClick,
}) => {
  const navigate = useNavigate();
  const [violations, setViolations] = useState<GeofenceViolation[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [violationsData, statsData] = await Promise.all([
        api.getActiveViolations({ hours: 8760, limit: 5 }),
        api.getViolationStats({ days: 365 }),
      ]);
      setViolations(violationsData.violations);
      setStats(statsData);
    } catch (err) {
      console.error("Error loading violations:", err);
    } finally {
      setLoading(false);
    }
  };

  const getTimeSince = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    return `${diffHours}h ago`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/2"></div>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <h3 className="text-lg font-bold text-gray-900">
            Geofence Violations
          </h3>
          {stats && stats.active_violations > 0 && (
            <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-full">
              {stats.active_violations}
            </span>
          )}
        </div>
        <button
          onClick={() => navigate("/pos-management/violations")}
          className="text-sm text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] font-medium flex items-center gap-1"
        >
          View All
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 divide-x divide-gray-100 border-b border-gray-200">
          {[
            { label: "Total (1yr)", value: stats.total_violations },
            { label: "Active", value: stats.active_violations },
            { label: "Resolved", value: stats.resolved_violations },
          ].map((stat) => (
            <div key={stat.label} className="px-4 py-3">
              <p className="text-xs text-gray-500 font-medium">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Recent Violations */}
      <div className="divide-y divide-gray-100">
        {violations.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <div className="w-12 h-12 bg-green-100 rounded-full mx-auto mb-3 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-900">All Clear!</p>
            <p className="text-xs text-gray-500 mt-1">
              No active violations in the last year
            </p>
          </div>
        ) : (
          violations.map((violation) => (
            <div
              key={violation.id}
              onClick={() => onViolationClick?.(violation)}
              className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1">
                  <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <XCircle className="w-5 h-5 text-red-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {violation.device_id}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      Agent: {violation.agent_id}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <MapPin className="w-3 h-3" />
                        <span>
                          {violation.distance_from_center_km.toFixed(2)} km away
                        </span>
                      </div>
                      <span className="text-gray-300">•</span>
                      <span className="text-xs text-gray-500">
                        {getTimeSince(violation.violation_time)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      {violations.length > 0 && (
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
          <button
            onClick={() => navigate("/pos-management/violations")}
            className="w-full text-sm text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] font-medium py-1"
          >
            View all violations →
          </button>
        </div>
      )}
    </div>
  );
};

export default ViolationsWidget;
