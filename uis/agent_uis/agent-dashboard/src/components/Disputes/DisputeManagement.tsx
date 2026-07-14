import {
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { disputeApi } from "../../utils/api";
import { useAuth } from "../../hooks/useAuth";

interface Dispute {
  id: number;
  dispute_id: string;
  customer_id: string;
  transaction_id: string;
  dispute_type: string;
  tenant_id: string;
  amount: string;
  description: string;
  status: string;
  resolution?: string;
  created_at: string;
  transaction?: {
    id: string;
    amount: string;
    currency: string;
    description: string;
    status: string;
    created_at: string;
  };
}

interface NewDispute {
  transaction_id: string;
  dispute_type: string;
  description: string;
}

const DisputeManagement: React.FC = () => {
  const { user } = useAuth() as { user: { keycloakId?: string } | null };
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [newDispute, setNewDispute] = useState<NewDispute>({
    transaction_id: "",
    dispute_type: "transaction_error",
    description: "",
  });

  const disputeTypes = [
    { value: "transaction_error", label: "Transaction Error" },
    { value: "unauthorized_charge", label: "Unauthorized Charge" },
    { value: "incorrect_amount", label: "Incorrect Amount" },
    { value: "service_not_received", label: "Service Not Received" },
    { value: "duplicate_transaction", label: "Duplicate Transaction" },
    { value: "other", label: "Other" },
  ];

  useEffect(() => {
    if (!user?.keycloakId) return;
    loadDisputes();
  }, [user]);

  const loadDisputes = async () => {
    if (!user?.keycloakId) return;
    try {
      setLoading(true);
      const response = await disputeApi.getDisputes();
      setDisputes(response || []);
    } catch (error) {
      console.error("Failed to load disputes:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      await disputeApi.createDispute(newDispute);
      setNewDispute({
        transaction_id: "",
        dispute_type: "transaction_error",
        description: "",
      });
      setShowCreateForm(false);
      await loadDisputes();
    } catch (error) {
      console.error("Failed to create dispute:", error);
      alert("Failed to create dispute. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      open: "bg-yellow-100 text-yellow-800",
      investigating: "bg-blue-100 text-blue-800",
      resolved: "bg-green-100 text-green-800",
      closed: "bg-gray-100 text-gray-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "open":
        return <Clock className="w-5 h-5 text-yellow-600" />;
      case "investigating":
        return <AlertCircle className="w-5 h-5 text-blue-600" />;
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
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(num);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">My Disputes</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          {showCreateForm ? "Cancel" : "Create New Dispute"}
        </button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Disputes</div>
          <div className="text-2xl font-bold text-gray-900">
            {disputes.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Open</div>
          <div className="text-2xl font-bold text-yellow-600">
            {disputes.filter((d) => d.status === "open").length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Investigating</div>
          <div className="text-2xl font-bold text-blue-600">
            {disputes.filter((d) => d.status === "investigating").length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Resolved</div>
          <div className="text-2xl font-bold text-green-600">
            {disputes.filter((d) => d.status === "resolved").length}
          </div>
        </div>
      </div>

      {showCreateForm && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Create New Dispute</h2>
          <form onSubmit={handleCreateDispute}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Transaction ID
                </label>
                <input
                  type="text"
                  value={newDispute.transaction_id}
                  onChange={(e) =>
                    setNewDispute({
                      ...newDispute,
                      transaction_id: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                  placeholder="Enter transaction ID to dispute"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Dispute Type
                </label>
                <select
                  value={newDispute.dispute_type}
                  onChange={(e) =>
                    setNewDispute({
                      ...newDispute,
                      dispute_type: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {disputeTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={newDispute.description}
                  onChange={(e) =>
                    setNewDispute({
                      ...newDispute,
                      description: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  rows={4}
                  required
                  placeholder="Provide detailed information about the dispute"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
              >
                {loading ? "Creating..." : "Submit Dispute"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Disputes List */}
        <div className="lg:col-span-1 bg-white rounded-lg shadow-md overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">All Disputes</h2>
          </div>
          <div className="overflow-y-auto max-h-[600px]">
            {loading && disputes.length === 0 ? (
              <div className="p-4 text-center text-gray-500">Loading...</div>
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
                      ? "bg-blue-50"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-sm">
                      {dispute.dispute_id}
                    </h3>
                    {getStatusIcon(dispute.status)}
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${getStatusColor(dispute.status)}`}
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
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(dispute.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Dispute Details */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md overflow-hidden">
          {selectedDispute ? (
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold mb-2">
                    {selectedDispute.dispute_id}
                  </h2>
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-sm px-3 py-1 rounded-full ${getStatusColor(selectedDispute.status)}`}
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
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Description</h3>
                <p className="text-gray-700">{selectedDispute.description}</p>
              </div>

              {/* Transaction Details */}
              {selectedDispute.transaction && (
                <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
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
                        {selectedDispute.transaction.currency || "USD"}
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

              {/* Resolution */}
              {selectedDispute.resolution && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-green-900 mb-2">
                    Resolution
                  </h3>
                  <p className="text-sm text-green-800">
                    {selectedDispute.resolution}
                  </p>
                </div>
              )}

              {/* Timeline */}
              <div className="mt-6">
                <h3 className="text-lg font-semibold mb-3">Timeline</h3>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-2 h-2 bg-blue-600 rounded-full mt-2"></div>
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
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[400px] text-gray-500">
              Select a dispute to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DisputeManagement;
