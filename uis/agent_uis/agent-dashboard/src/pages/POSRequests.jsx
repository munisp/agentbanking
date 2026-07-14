import {
    AlertCircle,
    Ban,
    Calendar,
    CheckCircle,
    Clock,
    Eye,
    Filter,
    MapPin,
    Package,
    Plus,
    Trash2,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { posRequestApi } from "../utils/api";

const POSRequests = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");

  // Modal states
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  useEffect(() => {
    loadRequests();
  }, [statusFilter]);

  const loadRequests = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await posRequestApi.getMyRequests(
        statusFilter === "all" ? null : statusFilter,
      );
      setRequests(data);
    } catch (err) {
      setError(err.message || "Failed to load requests");
      console.error("Error loading requests:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelRequest = async (requestId) => {
    if (!window.confirm("Are you sure you want to cancel this request?"))
      return;

    try {
      await posRequestApi.cancelRequest(requestId);
      loadRequests();
    } catch (err) {
      setError(err.message || "Failed to cancel request");
    }
  };

  const getStatusConfig = (status) => {
    const configs = {
      pending: {
        color: "bg-yellow-100 text-yellow-800",
        icon: <Clock className="w-4 h-4" />,
        label: "Pending",
      },
      approved: {
        color: "bg-blue-100 text-blue-800",
        icon: <CheckCircle className="w-4 h-4" />,
        label: "Approved",
      },
      assigned: {
        color: "bg-green-100 text-green-800",
        icon: <CheckCircle className="w-4 h-4" />,
        label: "Assigned",
      },
      rejected: {
        color: "bg-red-100 text-red-800",
        icon: <XCircle className="w-4 h-4" />,
        label: "Rejected",
      },
      cancelled: {
        color: "bg-gray-100 text-gray-800",
        icon: <Ban className="w-4 h-4" />,
        label: "Cancelled",
      },
    };
    return configs[status] || configs.pending;
  };

  const stats = {
    total: requests.length,
    pending: requests.filter((r) => r.status === "pending").length,
    approved: requests.filter((r) => r.status === "approved").length,
    assigned: requests.filter((r) => r.status === "assigned").length,
  };

  return (
    <div className="min-h-screen bg-gray-50 p-3 sm:p-4 lg:p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              POS Terminal Requests
            </h1>
            <p className="text-gray-500 mt-1">
              Request POS terminals for your business locations
            </p>
          </div>
          <Link
            to="/pos/order"
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors flex items-center gap-2"
          >
            <Plus className="w-5 h-5" />
            New Request
          </Link>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[
            {
              label: "Total Requests",
              value: stats.total,
              color: "text-gray-600",
            },
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
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-white rounded-xl shadow p-4 sm:p-5"
            >
              <p className="text-sm font-medium text-gray-500">{stat.label}</p>
              <p className={`text-2xl font-bold ${stat.color} mt-1`}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        {/* Filter */}
        <div className="flex items-center gap-3">
          <Filter className="w-5 h-5 text-gray-600" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Requests</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="assigned">Assigned</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* Requests List */}
        <div className="bg-white rounded-xl shadow overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-gray-500">Loading...</div>
          ) : requests.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              <Package className="w-16 h-16 mx-auto mb-4 opacity-40" />
              <p className="text-lg font-medium">No POS requests yet</p>
              <p className="text-sm mt-1">
                Click "New Request" to request a POS terminal
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[60vh] overflow-scroll">
              {requests.map((request) => {
                const sc = getStatusConfig(request.status);
                return (
                  <div
                    key={request.id}
                    className="p-4 sm:p-6 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                          <Package
                            className="w-5 h-5"
                            style={{ color: "var(--tenant-primary-color,#002082)" }}
                          />
                          <div>
                            <h3 className="font-semibold text-gray-900">
                              {request.preferred_model || "Any POS Model"} ×
                              {request.quantity}
                            </h3>
                            <p className="text-sm text-gray-500">
                              Request ID: {request.id}
                            </p>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4 text-sm">
                          {request.business_name && (
                            <div className="flex items-center gap-2 text-gray-600">
                              <Package className="w-4 h-4" />
                              <span>{request.business_name}</span>
                            </div>
                          )}
                          {request.deployment_location && (
                            <div className="flex items-center gap-2 text-gray-600">
                              <MapPin className="w-4 h-4" />
                              <span>{request.deployment_location}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-gray-500">
                            <Calendar className="w-4 h-4" />
                            <span>
                              {new Date(request.created_at).toLocaleDateString(
                                "en-US",
                                {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                },
                              )}
                            </span>
                          </div>
                        </div>

                        {request.justification && (
                          <p className="mt-3 text-sm text-gray-600 line-clamp-2">
                            <span className="font-medium">Reason:</span>{" "}
                            {request.justification}
                          </p>
                        )}

                        {request.rejection_reason && (
                          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                            <p className="text-sm text-red-700 font-medium">
                              Rejection Reason:
                            </p>
                            <p className="text-sm text-red-600 mt-1">
                              {request.rejection_reason}
                            </p>
                          </div>
                        )}

                        {request.assigned_terminal_serial && (
                          <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                            <p className="text-sm text-green-700 font-medium">
                              Assigned Terminal:{" "}
                              {request.assigned_terminal_serial}
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col items-end gap-3 ml-4">
                        <span
                          className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${sc.color}`}
                        >
                          {sc.icon}
                          {sc.label}
                        </span>

                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedRequest(request);
                              setShowDetailsModal(true);
                            }}
                            title="View Details"
                            className="p-2 rounded-lg transition-colors"
                            style={{ color: "var(--tenant-primary-color,#002082)" }}
                            onMouseEnter={(e) =>
                              (e.currentTarget.style.backgroundColor =
                                "rgba(0,79,113,0.1)")
                            }
                            onMouseLeave={(e) =>
                              (e.currentTarget.style.backgroundColor =
                                "transparent")
                            }
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          {request.status === "pending" && (
                            <button
                              onClick={() => handleCancelRequest(request.id)}
                              title="Cancel Request"
                              className="p-2 hover:bg-red-50 rounded-lg text-red-600 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Details Modal */}
      {showDetailsModal && selectedRequest && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowDetailsModal(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-6 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start">
              <h2 className="text-2xl font-bold text-gray-900">
                Request Details
              </h2>
              <button
                onClick={() => setShowDetailsModal(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                ×
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  Status
                </label>
                <p className="font-medium mt-1 capitalize">
                  {selectedRequest.status}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  Quantity
                </label>
                <p className="font-medium mt-1">{selectedRequest.quantity}</p>
              </div>
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  Preferred Model
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.preferred_model || "Any available"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  Deployment Location
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.deployment_location || "—"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  City
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.city || "—"}
                </p>
              </div>
              <div>
                <label className="text-gray-500 text-xs font-medium">
                  State
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.state || "—"}
                </p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs font-medium">
                  Business
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.business_name || "Not specified"}
                </p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs font-medium">
                  Deployment Address
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.deployment_address || "—"}
                </p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs font-medium">
                  Justification
                </label>
                <p className="font-medium mt-1">
                  {selectedRequest.justification}
                </p>
              </div>
              <div className="col-span-2">
                <label className="text-gray-500 text-xs font-medium">
                  Requested On
                </label>
                <p className="font-medium mt-1">
                  {new Date(selectedRequest.created_at).toLocaleString()}
                </p>
              </div>
              {selectedRequest.admin_notes && (
                <div className="col-span-2">
                  <label className="text-gray-500 text-xs font-medium">
                    Admin Notes
                  </label>
                  <p className="font-medium mt-1">
                    {selectedRequest.admin_notes}
                  </p>
                </div>
              )}
              {selectedRequest.assigned_terminal_serial && (
                <div className="col-span-2 p-3 bg-green-50 rounded-lg border border-green-200">
                  <label className="text-green-700 text-xs font-medium">
                    Assigned Terminal
                  </label>
                  <p className="font-medium mt-1 text-green-900">
                    {selectedRequest.assigned_terminal_serial}
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-4 border-t border-gray-200">
              <button
                onClick={() => setShowDetailsModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSRequests;
