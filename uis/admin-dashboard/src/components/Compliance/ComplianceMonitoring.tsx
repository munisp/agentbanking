import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Download,
  Eye,
  FileText,
  RefreshCw,
  Shield,
  TrendingUp,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { complianceKycApi } from "../../utils/api";

const ComplianceMonitoring: React.FC = () => {
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [records, setRecords] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [recordsResp, summaryResp] = await Promise.allSettled([
        complianceKycApi.listRecords(0, 200),
        complianceKycApi.getSummary(),
      ]);
      if (recordsResp.status === "fulfilled") {
        const r = recordsResp.value;
        setRecords(Array.isArray(r) ? r : r?.records ?? []);
      }
      if (summaryResp.status === "fulfilled") {
        setSummary(summaryResp.value);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load compliance data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const approved = records.filter((r) => r.status === "approved" || r.status === "verified");
  const pending = records.filter((r) =>
    ["pending", "in_review"].includes(r.status)
  );
  const highRisk = records.filter((r) => r.risk_level === "high");
  const rejected = records.filter((r) => r.status === "rejected");

  // Prefer summary data from the dedicated endpoint, fall back to local record calc
  const totalFromSummary = summary?.total ?? records.length;
  const approvedFromSummary = summary?.approved ?? approved.length;
  const kycCompliance =
    summary?.compliance_rate_pct ??
    (records.length > 0
      ? Math.round((approved.length / records.length) * 100 * 10) / 10
      : 0);

  const alerts = highRisk
    .concat(records.filter((r) => r.status === "on_hold"))
    .slice(0, 10)
    .map((r) => ({
      id: r.id,
      type: r.risk_level === "high" ? "High Risk KYC Record" : "KYC On Hold",
      severity: r.risk_level === "high" ? "high" : "medium",
      description: r.notes ?? `Customer ID: ${r.customer_id}`,
      customer: r.customer_id,
      date: r.updated_at ?? r.created_at ?? "",
      status: r.status,
    }));

  const filteredAlerts =
    filterSeverity === "all"
      ? alerts
      : alerts.filter((a) => a.severity === filterSeverity);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "high": return "bg-red-100 text-red-800";
      case "medium": return "bg-yellow-100 text-yellow-800";
      case "low": return "bg-blue-100 text-blue-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "approved": return "bg-green-100 text-green-800";
      case "pending": return "bg-yellow-100 text-yellow-800";
      case "in_review": return "bg-blue-100 text-blue-800";
      case "rejected": return "bg-red-100 text-red-800";
      case "on_hold": return "bg-orange-100 text-orange-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Compliance Monitoring
          </h1>
          <p className="text-gray-500 mt-1">
            AML/KYC compliance and regulatory monitoring
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Compliance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-600">KYC Compliance</h3>
            <Shield className="w-8 h-8 text-[var(--tenant-primary-color,#002082)]" />
          </div>
          {loading ? (
            <div className="h-8 bg-gray-200 rounded animate-pulse" />
          ) : (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-gray-900">{kycCompliance}%</span>
                <span className="text-sm text-green-600 flex items-center">
                  <TrendingUp className="w-4 h-4 mr-1" />
                </span>
              </div>
              <div className="mt-4 bg-gray-200 rounded-full h-2">
                <div className="bg-[var(--tenant-primary-color,#002082)] h-2 rounded-full" style={{ width: `${kycCompliance}%` }} />
              </div>
              <p className="text-xs text-gray-500 mt-2">{approvedFromSummary} / {totalFromSummary} approved</p>
            </>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-600">Pending Reviews</h3>
            <CheckCircle className="w-8 h-8 text-yellow-500" />
          </div>
          {loading ? (
            <div className="h-8 bg-gray-200 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">{summary?.pending ?? pending.length}</span>
              <span className="text-sm text-gray-500">records</span>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-600">High Risk Flagged</h3>
            <Activity className="w-8 h-8 text-red-500" />
          </div>
          {loading ? (
            <div className="h-8 bg-gray-200 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">{summary?.high_risk ?? highRisk.length}</span>
              <span className="text-sm text-gray-500">records</span>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-600">BVN Verified</h3>
            <FileText className="w-8 h-8 text-orange-500" />
          </div>
          {loading ? (
            <div className="h-8 bg-gray-200 rounded animate-pulse" />
          ) : (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-gray-900">
                  {summary?.bvn_verification?.success_rate_pct ?? 0}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {summary?.bvn_verification?.passed ?? 0} / {summary?.bvn_verification?.attempted ?? 0} verified
              </p>
            </>
          )}
        </div>
      </div>

      {/* Tier Breakdown (shown only when summary data available) */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { label: "Tier 1 — No KYC", count: summary.tier_breakdown?.tier_1_no_kyc ?? 0, color: "bg-gray-400", limit: "₦20k/day" },
            { label: "Tier 2 — BVN Pending", count: summary.tier_breakdown?.tier_2_bvn_pending ?? 0, color: "bg-yellow-400", limit: "₦200k/day" },
            { label: "Tier 3 — Fully Verified", count: summary.tier_breakdown?.tier_3_fully_verified ?? 0, color: "bg-green-500", limit: "No limit" },
          ].map(({ label, count, color, limit }) => (
            <div key={label} className="bg-white rounded-lg shadow p-4 flex items-center gap-4">
              <div className={`w-3 h-10 rounded-full ${color}`} />
              <div>
                <p className="text-sm font-semibold text-gray-800">{label}</p>
                <p className="text-2xl font-bold text-gray-900">{count}</p>
                <p className="text-xs text-gray-500">{limit}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Compliance Alerts */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900">
            Compliance Alerts
            {filteredAlerts.length > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">
                {filteredAlerts.length}
              </span>
            )}
          </h3>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value="all">All Severity</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <div className="divide-y divide-gray-200">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="p-6">
                <div className="h-12 bg-gray-200 rounded animate-pulse" />
              </div>
            ))
          ) : filteredAlerts.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-400" />
              <p>No compliance alerts at this time</p>
            </div>
          ) : (
            filteredAlerts.map((alert) => (
              <div key={alert.id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <AlertTriangle className="w-6 h-6 text-orange-500 mt-1" />
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h4 className="text-base font-semibold text-gray-900">{alert.type}</h4>
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(alert.severity)}`}>
                          {alert.severity}
                        </span>
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(alert.status)}`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 mb-2">{alert.description}</p>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>Customer: {alert.customer}</span>
                        {alert.date && <><span>•</span><span>{new Date(alert.date).toLocaleDateString()}</span></>}
                      </div>
                    </div>
                  </div>
                  <button className="ml-4 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] text-sm">
                    Review
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Reviews */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Pending KYC Reviews</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="p-6"><div className="h-10 bg-gray-200 rounded animate-pulse" /></div>
              ))
            ) : pending.length === 0 ? (
              <div className="p-8 text-center text-gray-400">No pending reviews</div>
            ) : (
              pending.slice(0, 20).map((review) => (
                <div key={review.id} className="p-4 hover:bg-gray-50">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900">{review.customer_id}</h4>
                      <p className="text-sm text-gray-600">{review.risk_level ?? "standard"} risk</p>
                    </div>
                    <button className="text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] text-sm flex items-center gap-1">
                      <Eye className="w-4 h-4" />
                      Review
                    </button>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500 mt-2">
                    <span>Status: {review.status}</span>
                    {review.created_at && (
                      <><span>•</span><span>Created: {new Date(review.created_at).toLocaleDateString()}</span></>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* KYC Summary */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900">KYC Status Summary</h3>
            <button className="text-[var(--tenant-primary-color,#002082)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] text-sm flex items-center gap-1">
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
          <div className="p-6 space-y-4">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-8 bg-gray-200 rounded animate-pulse" />
              ))
            ) : (
              [
                { label: "Approved", count: summary?.approved ?? approved.length, color: "bg-green-500" },
                { label: "Pending", count: summary?.pending ?? pending.length, color: "bg-yellow-500" },
                { label: "High Risk", count: summary?.high_risk ?? highRisk.length, color: "bg-red-500" },
                { label: "Rejected", count: summary?.rejected ?? rejected.length, color: "bg-gray-500" },
              ].map(({ label, count, color }) => {
                const total = summary?.total ?? records.length;
                return (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${color}`} />
                    <span className="text-sm text-gray-700">{label}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className={`${color} h-2 rounded-full`}
                        style={{ width: total > 0 ? `${(count / total) * 100}%` : "0%" }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-gray-900 w-8 text-right">{count}</span>
                  </div>
                </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComplianceMonitoring;
