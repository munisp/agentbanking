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

const DisputeManagement = () => {
  const { user } = useAuth();
  const [disputes, setDisputes] = useState([]);
  const [selectedDispute, setSelectedDispute] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [newDispute, setNewDispute] = useState({
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

  // Note: Messaging functionality may need to be updated to match core banking API
  // useEffect(() => {
  //   if (selectedDispute) {
  //     loadMessages(selectedDispute.dispute_id);
  //     // Poll for new messages every 10 seconds
  //     const interval = setInterval(
  //       () => loadMessages(selectedDispute.dispute_id),
  //       10000
  //     );
  //     return () => clearInterval(interval);
  //   }
  // }, [selectedDispute]);

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

  // Note: Messaging functions commented out - core banking dispute API doesn't support messages
  // const loadMessages = async (disputeId) => {
  //   try {
  //     const response = await disputeApi.getDisputeMessages(disputeId);
  //     setMessages(response);
  //   } catch (error) {
  //     console.error("Failed to load messages:", error);
  //   }
  // };

  const handleCreateDispute = async (e) => {
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

  // Note: Messaging function commented out - core banking dispute API doesn't support messages
  // const handleSendMessage = async () => {
  //   if (!newMessage.trim() || !selectedDispute) return;
  //
  //   try {
  //     const agentId = localStorage.getItem("keycloakId") || "current-agent-id";
  //     await disputeApi.addDisputeMessage(selectedDispute.dispute_id, {
  //       sender_type: "agent",
  //       sender_id: agentId,
  //       message: newMessage,
  //     });
  //     setNewMessage("");
  //     await loadMessages(selectedDispute.dispute_id);
  //   } catch (error) {
  //     console.error("Failed to send message:", error);
  //   }
  // };

  const getStatusColor = (status) => {
    const colors = {
      open: "bg-yellow-100 text-yellow-800",
      investigating: "bg-blue-100 text-blue-800",
      resolved: "bg-green-100 text-green-800",
      closed: "bg-gray-100 text-gray-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "open":
        return <Clock className="w-5 h-5" />;
      case "investigating":
        return <AlertCircle className="w-5 h-5" />;
      case "resolved":
        return <CheckCircle className="w-5 h-5" />;
      case "closed":
        return <XCircle className="w-5 h-5" />;
      default:
        return <Clock className="w-5 h-5" />;
    }
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
                  <p className="text-xs text-gray-500">
                    {dispute.dispute_type}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Transaction: {dispute.transaction_id}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(dispute.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Dispute Details and Messages */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md overflow-hidden">
          {selectedDispute ? (
            <>
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-2xl font-bold mb-2">
                      Dispute #{selectedDispute.dispute_id}
                    </h2>
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-sm px-3 py-1 rounded-full ${getStatusColor(selectedDispute.status)}`}
                      >
                        {selectedDispute.status}
                      </span>
                      <span className="text-sm text-gray-500">
                        {selectedDispute.dispute_type}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="space-y-2 mb-4">
                  <p className="text-sm">
                    <strong>Transaction ID:</strong>{" "}
                    {selectedDispute.transaction_id}
                  </p>
                  {selectedDispute.amount && (
                    <p className="text-sm">
                      <strong>Amount:</strong> {selectedDispute.amount}
                    </p>
                  )}
                  {selectedDispute.transaction && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mt-2">
                      <p className="text-sm font-semibold text-gray-900 mb-1">
                        Transaction Details:
                      </p>
                      <p className="text-sm text-gray-700">
                        Amount: {selectedDispute.transaction.amount}{" "}
                        {selectedDispute.transaction.currency}
                      </p>
                      <p className="text-sm text-gray-700">
                        Status: {selectedDispute.transaction.status}
                      </p>
                      <p className="text-sm text-gray-700">
                        {selectedDispute.transaction.description}
                      </p>
                    </div>
                  )}
                </div>
                <p className="text-gray-700 mb-4">
                  <strong>Description:</strong> {selectedDispute.description}
                </p>
                {selectedDispute.resolution && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <p className="text-sm font-semibold text-green-900 mb-1">
                      Resolution:
                    </p>
                    <p className="text-sm text-green-800">
                      {selectedDispute.resolution}
                    </p>
                  </div>
                )}
              </div>

              {/* Note: Messaging functionality disabled - core banking dispute API doesn't support messages */}
              {/* Messages */}
              {/* <div className="flex flex-col h-[400px]">
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.sender_type === "agent" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[70%] rounded-lg p-3 ${
                          message.sender_type === "agent"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-200 text-gray-900"
                        }`}
                      >
                        <p className="text-sm">{message.message}</p>
                        <p
                          className={`text-xs mt-1 ${
                            message.sender_type === "agent"
                              ? "text-blue-100"
                              : "text-gray-500"
                          }`}
                        >
                          {new Date(message.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-4 border-t border-gray-200">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyPress={(e) =>
                        e.key === "Enter" && handleSendMessage()
                      }
                      placeholder="Type your message..."
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!newMessage.trim()}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div> */}
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select a dispute to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DisputeManagement;
