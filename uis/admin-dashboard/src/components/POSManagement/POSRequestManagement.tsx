import {
    Ban,
    Calendar,
    CheckCheck,
    CheckCircle,
    Clock,
    Eye,
    FileText,
    Filter,
    MapPin,
    Package,
    Search,
    Truck,
    User,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import {
    api,
    POSRequestRecord,
    POSRequestStats,
    POSTerminal,
} from "../../utils/api";

const POSRequestManagement: React.FC = () => {
  const [requests, setRequests] = useState<POSRequestRecord[]>([]);
  const [stats, setStats] = useState<POSRequestStats | null>(null);
  const [terminals, setTerminals] = useState<POSTerminal[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [selectedRequest, setSelectedRequest] =
    useState<POSRequestRecord | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [reviewAction, setReviewAction] = useState<"approve" | "reject">(
    "approve",
  );
  const [adminNotes, setAdminNotes] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [selectedTerminalId, setSelectedTerminalId] = useState("");

  useEffect(() => {
    loadRequests();
    loadStats();
    loadAvailableTerminals();
  }, [statusFilter]);

  const loadRequests = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAllPOSRequests(
        statusFilter === "all" ? undefined : statusFilter,
      );
      setRequests(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load requests");
      console.error("Error loading requests:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getPOSRequestStats();
      setStats(data);
    } catch (err) {
      console.error("Error loading stats:", err);
    }
  };

  const loadAvailableTerminals = async () => {
    try {
      const data = await api.getPOSTerminals();
      // Filter for unassigned or inactive terminals
      const available = data.filter(
        (t) => !t.assigned_to || t.status === "Inactive",
      );
      setTerminals(available);
    } catch (err) {
      console.error("Error loading terminals:", err);
    }
  };

  const handleReview = async () => {
    if (!selectedRequest) return;

    try {
      await api.reviewPOSRequest(selectedRequest.id, {
        action: reviewAction,
        admin_notes: adminNotes,
        rejection_reason:
          reviewAction === "reject" ? rejectionReason : undefined,
      });

      setShowReviewModal(false);
      setAdminNotes("");
      setRejectionReason("");
      loadRequests();
      loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to review request");
    }
  };

  const handleAssign = async () => {
    if (!selectedRequest || !selectedTerminalId) return;

    const terminal = terminals.find((t) => t.id === selectedTerminalId);
    if (!terminal) return;

    try {
      await api.assignTerminalToPOSRequest(selectedRequest.id, {
        terminal_id: terminal.id,
        terminal_serial: terminal.serial_number,
        admin_notes: adminNotes,
      });

      // Also update the terminal to link it to the business/agent
      if (selectedRequest.business_id) {
        await api.linkPOSTerminalToBusiness(
          terminal.id,
          selectedRequest.business_id,
        );
      }

      await api.updatePOSTerminal(terminal.id, {
        assigned_to:
          selectedRequest.agent_name || selectedRequest.agent_keycloak_id,
        status: "Active",
        location: selectedRequest.deployment_location || terminal.location,
      });

      setShowAssignModal(false);
      setSelectedTerminalId("");
      setAdminNotes("");
      loadRequests();
      loadStats();
      loadAvailableTerminals();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to assign terminal",
      );
    }
  };

  const filteredRequests = requests.filter((req) => {
    const matchesSearch =
      req.agent_name?.toLowerCase().includes(search.toLowerCase()) ||
      req.agent_email?.toLowerCase().includes(search.toLowerCase()) ||
      req.business_name?.toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; icon: React.ReactNode }> = {
      pending: {
        color: "bg-yellow-100 text-yellow-800",
        icon: <Clock className="w-3 h-3" />,
      },
      approved: {
        color: "bg-[rgba(0,79,113,0.1)] text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]",
        icon: <CheckCircle className="w-3 h-3" />,
      },
      assigned: {
        color: "bg-green-100 text-green-800",
        icon: <CheckCheck className="w-3 h-3" />,
      },
      rejected: {
        color: "bg-red-100 text-red-800",
        icon: <XCircle className="w-3 h-3" />,
      },
      cancelled: {
        color: "bg-gray-100 text-gray-800",
        icon: <Ban className="w-3 h-3" />,
      },
    };
    return configs[status] || configs.pending;
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">POS Requests</h1>
        <p className="text-gray-500 mt-1">
          Review and process agent POS terminal requests
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { label: "Total", value: stats.total, color: "text-gray-600" },
            {
              label: "Pending",
              value: stats.pending,
              color: "text-yellow-600",
            },
            {
              label: "Approved",
              value: stats.approved,
              color: "text-[var(--tenant-primary-color,#002082)]",
            },
            {
              label: "Assigned",
              value: stats.assigned,
              color: "text-green-600",
            },
            { label: "Rejected", value: stats.rejected, color: "text-red-600" },
          ].map((stat) => (
            <div key={stat.label} className="bg-white rounded-xl shadow p-5">
              <p className="text-sm font-medium text-gray-500">{stat.label}</p>
              <p className={`text-2xl font-bold ${stat.color} mt-1`}>
                {stat.value}
              </p>
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
            placeholder="Search by agent, email, or business..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="assigned">Assigned</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {[
                  "Agent",
                  "Business",
                  "Model",
                  "Quantity",
                  "Location",
                  "Status",
                  "Requested",
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
              {filteredRequests.map((request) => {
                const sc = getStatusConfig(request.status);
                return (
                  <tr
                    key={request.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {request.agent_name || "N/A"}
                          </p>
                          <p className="text-xs text-gray-500">
                            {request.agent_email}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {request.business_name || "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {request.preferred_model || "Any"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {request.quantity}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-gray-600">
                        <MapPin className="w-3 h-3" />
                        {request.city || request.deployment_location || "—"}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${sc.color}`}
                      >
                        {sc.icon}
                        {request.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {request.created_at
                        ? new Date(request.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setSelectedRequest(request)}
                          title="View Details"
                          className="p-1.5 hover:bg-[rgba(0,79,113,0.05)] rounded-lg text-[var(--tenant-primary-color,#002082)] transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {request.status === "pending" && (
                          <button
                            onClick={() => {
                              setSelectedRequest(request);
                              setShowReviewModal(true);
                            }}
                            title="Review"
                            className="p-1.5 hover:bg-green-50 rounded-lg text-green-600 transition-colors"
                          >
                            <CheckCircle className="w-4 h-4" />
                          </button>
                        )}
                        {request.status === "approved" && (
                          <button
                            onClick={() => {
                              setSelectedRequest(request);
                              setShowAssignModal(true);
                            }}
                            title="Assign Terminal"
                            className="p-1.5 hover:bg-purple-50 rounded-lg text-purple-600 transition-colors"
                          >
                            <Truck className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredRequests.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Package className="w-12 h-12 mx-auto mb-2 opacity-40" />
            <p>No POS requests found</p>
          </div>
        )}
      </div>

      {/* Review Modal */}
      {showReviewModal && selectedRequest && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <h2 className="text-lg font-bold text-gray-900">
              Review POS Request
            </h2>

            <div className="space-y-3 text-sm">
              <div>
                <span className="text-gray-500">Agent:</span>{" "}
                <span className="font-medium">
                  {selectedRequest.agent_name}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Model:</span>{" "}
                <span className="font-medium">
                  {selectedRequest.preferred_model || "Any"}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Justification:</span>
                <p className="mt-1 text-gray-700">
                  {selectedRequest.justification || "No justification provided"}
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setReviewAction("approve")}
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                  reviewAction === "approve"
                    ? "bg-green-100 text-green-700 border-2 border-green-500"
                    : "bg-gray-100 text-gray-700 border-2 border-transparent"
                }`}
              >
                <CheckCircle className="w-4 h-4 inline mr-1" />
                Approve
              </button>
              <button
                onClick={() => setReviewAction("reject")}
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                  reviewAction === "reject"
                    ? "bg-red-100 text-red-700 border-2 border-red-500"
                    : "bg-gray-100 text-gray-700 border-2 border-transparent"
                }`}
              >
                <XCircle className="w-4 h-4 inline mr-1" />
                Reject
              </button>
            </div>

            {reviewAction === "reject" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rejection Reason *
                </label>
                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={3}
                  placeholder="Explain why this request is being rejected..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Admin Notes (Optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={2}
                placeholder="Add any internal notes..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => {
                  setShowReviewModal(false);
                  setAdminNotes("");
                  setRejectionReason("");
                }}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReview}
                disabled={reviewAction === "reject" && !rejectionReason}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Submit Review
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Terminal Modal */}
      {showAssignModal && selectedRequest && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <h2 className="text-lg font-bold text-gray-900">
              Assign Terminal to Request
            </h2>

            <div className="space-y-3 text-sm bg-gray-50 p-3 rounded-lg">
              <div>
                <span className="text-gray-500">Agent:</span>{" "}
                <span className="font-medium">
                  {selectedRequest.agent_name}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Business:</span>{" "}
                <span className="font-medium">
                  {selectedRequest.business_name || "—"}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Preferred Model:</span>{" "}
                <span className="font-medium">
                  {selectedRequest.preferred_model || "Any"}
                </span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select Terminal *
              </label>
              <select
                value={selectedTerminalId}
                onChange={(e) => setSelectedTerminalId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
              >
                <option value="">Choose a terminal...</option>
                {terminals.map((terminal) => (
                  <option key={terminal.id} value={terminal.id}>
                    {terminal.serial_number} - {terminal.model} (
                    {terminal.status})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-500">
                {terminals.length} available terminal(s)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes (Optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={2}
                placeholder="Add assignment notes..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => {
                  setShowAssignModal(false);
                  setSelectedTerminalId("");
                  setAdminNotes("");
                }}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAssign}
                disabled={!selectedTerminalId}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Assign Terminal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Request Details Modal */}
      {selectedRequest && !showReviewModal && !showAssignModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedRequest(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-6 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start">
              <h2 className="text-lg font-bold text-gray-900">
                Request Details
              </h2>
              <button
                onClick={() => setSelectedRequest(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <label className="text-gray-500 text-xs">Agent Name</label>
                <p className="font-medium">
                  {selectedRequest.agent_name || "—"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs">Agent Email</label>
                <p className="font-medium">
                  {selectedRequest.agent_email || "—"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs">Business</label>
                <p className="font-medium">
                  {selectedRequest.business_name || "—"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs">Status</label>
                <p className="font-medium capitalize">
                  {selectedRequest.status}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs">Preferred Model</label>
                <p className="font-medium">
                  {selectedRequest.preferred_model || "Any"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs">Quantity</label>
                <p className="font-medium">{selectedRequest.quantity}</p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs">
                  Deployment Location
                </label>
                <p className="font-medium">
                  {selectedRequest.deployment_location || "—"}
                </p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs">Justification</label>
                <p className="font-medium">
                  {selectedRequest.justification || "No justification provided"}
                </p>
              </div>
              {selectedRequest.rejection_reason && (
                <div className="col-span-2">
                  <label className="text-gray-500 text-xs">
                    Rejection Reason
                  </label>
                  <p className="font-medium text-red-600">
                    {selectedRequest.rejection_reason}
                  </p>
                </div>
              )}
              {selectedRequest.assigned_terminal_serial && (
                <div className="col-span-2">
                  <label className="text-gray-500 text-xs">
                    Assigned Terminal
                  </label>
                  <p className="font-medium">
                    {selectedRequest.assigned_terminal_serial}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSRequestManagement;
