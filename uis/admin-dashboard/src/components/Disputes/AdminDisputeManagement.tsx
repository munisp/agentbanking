import {
    AlertCircle,
    CheckCircle,
    Clock,
    FileText,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api, Dispute, DisputeStats } from "../../utils/api";

const AdminDisputeManagement: React.FC = () => {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [resolution, setResolution] = useState("");
  const [stats, setStats] = useState<DisputeStats | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDisputes();
    loadStats();
  }, [statusFilter]);

  useEffect(() => {
    if (selectedDispute) {
      setResolution(selectedDispute.resolution || "");
    }
  }, [selectedDispute]);

  const normalizeDisputes = (response: unknown): Dispute[] => {
    if (Array.isArray(response)) return response as Dispute[];
    const r = response as any;
    return (r?.disputes ?? r?.data ?? r?.results ?? []) as Dispute[];
  };

  const loadDisputes = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getTenantDisputes();
      const allDisputes = normalizeDisputes(response);

      const filtered =
        statusFilter === "all"
          ? allDisputes
          : allDisputes.filter((d: Dispute) => d.status === statusFilter);

      setDisputes(filtered);
    } catch (err: any) {
      const msg = err?.message || "Failed to load disputes";
      setError(msg);
      console.error("Failed to load disputes:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.getTenantDisputes();
      const allDisputes = normalizeDisputes(response);

      const stats: DisputeStats = {
        total: allDisputes.length,
        open: allDisputes.filter((d: Dispute) => d.status === "open").length,
        investigating: allDisputes.filter(
          (d: Dispute) => d.status === "investigating",
        ).length,
        resolved: allDisputes.filter((d: Dispute) => d.status === "resolved")
          .length,
        closed: allDisputes.filter((d: Dispute) => d.status === "closed")
          .length,
        total_amount: allDisputes
          .reduce(
            (sum: number, d: Dispute) => sum + parseFloat(d.amount || "0"),
            0,
          )
          .toFixed(2),
      };

      setStats(stats);
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  };

  const handleResolveDispute = async () => {
    if (!selectedDispute || !resolution.trim()) {
      alert("Please enter a resolution message");
      return;
    }

    try {
      await api.resolveDispute(selectedDispute.dispute_id, resolution);
      await loadDisputes();
      await loadStats();
      alert("Dispute resolved successfully");
      setSelectedDispute(null);
      setResolution("");
    } catch (error) {
      console.error("Failed to resolve dispute:", error);
      alert("Failed to resolve dispute. Please try again.");
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      open: "bg-yellow-100 text-yellow-800 border-yellow-300",
      investigating:
        "bg-[rgba(0,79,113,0.1)] text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] border-[rgba(0,79,113,0.3)]",
      resolved: "bg-green-100 text-green-800 border-green-300",
      closed: "bg-gray-100 text-gray-800 border-gray-300",
    };
    return colors[status] || "bg-gray-100 text-gray-800 border-gray-300";
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "open":
        return <Clock className="w-5 h-5 text-yellow-600" />;
      case "investigating":
        return <AlertCircle className="w-5 h-5 text-[var(--tenant-primary-color,#002082)]" />;
      case "resolved":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "closed":
        return <XCircle className="w-5 h-5 text-gray-600" />;
      default:
        return <FileText className="w-5 h-5" />;
    }
  };

  const formatCurrency = (amount: string | number) => {
    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(num);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">
        Dispute Management
      </h1>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-600">Total</p>
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-gray-500 mt-1">
              {formatCurrency(stats.total_amount)}
            </p>
          </div>
          <div className="bg-yellow-50 rounded-lg shadow p-4 border border-yellow-200">
            <p className="text-sm text-yellow-800">Open</p>
            <p className="text-2xl font-bold text-yellow-900">{stats.open}</p>
          </div>
          <div className="bg-[rgba(0,79,113,0.05)] rounded-lg shadow p-4 border border-[rgba(0,79,113,0.2)]">
            <p className="text-sm text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]">Investigating</p>
            <p className="text-2xl font-bold text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]">
              {stats.investigating}
            </p>
          </div>
          <div className="bg-green-50 rounded-lg shadow p-4 border border-green-200">
            <p className="text-sm text-green-800">Resolved</p>
            <p className="text-2xl font-bold text-green-900">
              {stats.resolved}
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200">
            <p className="text-sm text-gray-800">Closed</p>
            <p className="text-2xl font-bold text-gray-900">{stats.closed}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-700">
            Filter by status:
          </span>
          {["all", "open", "investigating", "resolved", "closed"].map(
            (status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1 rounded-full text-sm transition-colors ${
                  statusFilter === status
                    ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                    : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                }`}
              >
                {status}
              </button>
            ),
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Disputes List */}
        <div className="lg:col-span-1 bg-white rounded-lg shadow-md overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">
              Disputes ({disputes.length})
            </h2>
          </div>
          <div className="overflow-y-auto max-h-[700px]">
            {loading && disputes.length === 0 ? (
              <div className="p-4 text-center text-gray-500">Loading...</div>
            ) : error ? (
              <div className="p-4 text-center text-red-600 text-sm">
                {error}
              </div>
            ) : disputes.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                No disputes found
              </div>
            ) : (
              disputes.map((dispute) => (
                <div
                  key={dispute.dispute_id}
                  onClick={() => setSelectedDispute(dispute)}
                  className={`p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
                    selectedDispute?.dispute_id === dispute.dispute_id
                      ? "bg-[rgba(0,79,113,0.05)]"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-sm flex-1">
                      {dispute.dispute_id}
                    </h3>
                    {getStatusIcon(dispute.status)}
                  </div>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span
                      className={`text-xs px-2 py-1 rounded-full border ${getStatusColor(dispute.status)}`}
                    >
                      {dispute.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 mb-1">
                    {dispute.dispute_type.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs font-semibold text-gray-900">
                    {formatCurrency(dispute.amount)}
                  </p>
                  <p className="text-xs text-gray-500">
                    Customer: {dispute.customer_id.substring(0, 8)}...
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(dispute.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Dispute Details and Management */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md overflow-hidden">
          {selectedDispute ? (
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold mb-2">
                    {selectedDispute.dispute_id}
                  </h2>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span
                      className={`text-sm px-3 py-1 rounded-full border ${getStatusColor(selectedDispute.status)}`}
                    >
                      {selectedDispute.status}
                    </span>
                    <span className="text-sm text-gray-500">
                      {selectedDispute.dispute_type.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Amount */}
              <div className="mb-6">
                <div className="text-sm text-gray-600">Disputed Amount</div>
                <div className="text-3xl font-bold text-gray-900">
                  {formatCurrency(selectedDispute.amount)}
                </div>
              </div>

              {/* Description */}
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <p className="text-sm font-semibold text-gray-700 mb-2">
                  Description:
                </p>
                <p className="text-gray-700">{selectedDispute.description}</p>
                <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Customer ID:</span>
                    <p className="font-mono text-xs">
                      {selectedDispute.customer_id}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Transaction ID:</span>
                    <p className="font-mono text-xs">
                      {selectedDispute.transaction_id}
                    </p>
                  </div>
                </div>
              </div>

              {/* Transaction Details */}
              {selectedDispute.transaction && (
                <div className="mb-6 bg-[rgba(0,79,113,0.05)] border border-[rgba(0,79,113,0.2)] rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-3">
                    Transaction Details
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-gray-600">
                        Transaction ID
                      </div>
                      <div className="font-mono text-sm">
                        {selectedDispute.transaction.id}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Amount</div>
                      <div className="font-semibold">
                        {formatCurrency(selectedDispute.transaction.amount)}{" "}
                        {selectedDispute.transaction.currency || "NGN"}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Status</div>
                      <div className="text-sm">
                        {selectedDispute.transaction.status}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Date</div>
                      <div className="text-sm">
                        {new Date(
                          selectedDispute.transaction.created_at,
                        ).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  {selectedDispute.transaction.description && (
                    <div className="mt-3">
                      <div className="text-sm text-gray-600">Description</div>
                      <div className="text-sm">
                        {selectedDispute.transaction.description}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Resolution Section */}
              {selectedDispute.status !== "resolved" &&
              selectedDispute.status !== "closed" ? (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Resolution
                  </label>
                  <textarea
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent"
                    rows={4}
                    placeholder="Enter resolution details..."
                  />
                  <button
                    onClick={handleResolveDispute}
                    className="mt-3 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Resolve Dispute
                  </button>
                </div>
              ) : selectedDispute.resolution ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-green-900 mb-2">
                    Resolution
                  </h3>
                  <p className="text-sm text-green-800">
                    {selectedDispute.resolution}
                  </p>
                </div>
              ) : null}

              {/* Timeline */}
              <div className="mt-6">
                <h3 className="text-lg font-semibold mb-3">Timeline</h3>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-2 h-2 bg-[var(--tenant-primary-color,#002082)] rounded-full mt-2"></div>
                    <div>
                      <div className="text-sm font-semibold">
                        Dispute Created
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(selectedDispute.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  {selectedDispute.status === "resolved" && (
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-green-600 rounded-full mt-2"></div>
                      <div>
                        <div className="text-sm font-semibold">Resolved</div>
                        <div className="text-xs text-gray-500">
                          Status updated to resolved
                        </div>
                      </div>
                    </div>
                  )}
                  {selectedDispute.status === "closed" && (
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-gray-600 rounded-full mt-2"></div>
                      <div>
                        <div className="text-sm font-semibold">Closed</div>
                        <div className="text-xs text-gray-500">
                          Dispute was closed
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[400px] text-gray-500">
              Select a dispute to view details and manage
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDisputeManagement;
