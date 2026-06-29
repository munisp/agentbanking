import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  RefreshCw,
  X,
  Wifi,
  WifiOff,
  Trash2,
} from "lucide-react";
import { useOfflineStore } from "../hooks/useOfflineStore";

export const OfflineTransactionQueue = ({ onSync, isLoading = false }) => {
  const {
    isOnline,
    pendingTransactions,
    lastSyncTime,
    syncInProgress,
  } = useOfflineStore();
  const [expanded, setExpanded] = useState(false);
  const [showDetails, setShowDetails] = useState(null);

  if (pendingTransactions.length === 0 && isOnline) return null;

  const formatTime = (timestamp) => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const failedCount = pendingTransactions.filter(
    (t) => t.status === "failed"
  ).length;
  const successCount = pendingTransactions.filter(
    (t) => t.status === "synced"
  ).length;

  return (
    <div className="fixed bottom-4 right-4 max-w-md z-40">
      {/* Offline Status Banner */}
      {!isOnline && (
        <div className="mb-3 bg-amber-50 border-l-4 border-amber-500 p-4 rounded-lg shadow-lg">
          <div className="flex items-start">
            <WifiOff className="w-5 h-5 text-amber-600 mt-0.5 mr-3 shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900 text-sm">
                You're Offline
              </h3>
              <p className="text-xs text-amber-800 mt-1">
                Transactions will be saved and synced when you're back online.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Pending Transactions Queue */}
      {pendingTransactions.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg border border-gray-200">
          {/* Header */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 active:bg-gray-100 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="relative">
                <Clock className="w-5 h-5 text-blue-600" />
                {pendingTransactions.length > 0 && (
                  <div className="absolute -top-1 -right-1 bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-semibold">
                    {pendingTransactions.length}
                  </div>
                )}
              </div>
              <div className="text-left">
                <p className="font-semibold text-gray-900 text-sm">
                  {pendingTransactions.length} Pending Transaction
                  {pendingTransactions.length !== 1 ? "s" : ""}
                </p>
                {isOnline && (
                  <p className="text-xs text-gray-500">
                    Last synced: {formatTime(lastSyncTime)}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isOnline && onSync && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSync();
                  }}
                  disabled={syncInProgress || isLoading}
                  className="p-2 hover:bg-blue-100 rounded text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Sync now"
                >
                  <RefreshCw
                    className={`w-4 h-4 ${syncInProgress ? "animate-spin" : ""}`}
                  />
                </button>
              )}
              <svg
                className={`w-5 h-5 text-gray-400 transition-transform ${
                  expanded ? "rotate-180" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 14l-7 7m0 0l-7-7m7 7V3"
                />
              </svg>
            </div>
          </button>

          {/* Expanded Content */}
          {expanded && (
            <div className="border-t border-gray-200">
              {/* Stats */}
              {(successCount > 0 || failedCount > 0) && (
                <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex gap-4 text-xs">
                  {successCount > 0 && (
                    <div className="flex items-center gap-1 text-green-700">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{successCount} synced</span>
                    </div>
                  )}
                  {failedCount > 0 && (
                    <div className="flex items-center gap-1 text-red-700">
                      <AlertCircle className="w-4 h-4" />
                      <span>{failedCount} failed</span>
                    </div>
                  )}
                </div>
              )}

              {/* Transaction List */}
              <div className="max-h-96 overflow-y-auto">
                {pendingTransactions.map((txn) => (
                  <div key={txn.id} className="border-b border-gray-100 last:border-0">
                    <button
                      onClick={() =>
                        setShowDetails(
                          showDetails === txn.id ? null : txn.id
                        )
                      }
                      className="w-full px-4 py-3 hover:bg-gray-50 transition-colors text-left"
                    >
                      <div className="flex items-start gap-3">
                        {txn.status === "synced" ? (
                          <CheckCircle2 className="w-4 h-4 text-green-600 mt-1 shrink-0" />
                        ) : txn.status === "failed" ? (
                          <AlertCircle className="w-4 h-4 text-red-600 mt-1 shrink-0" />
                        ) : (
                          <Clock className="w-4 h-4 text-blue-600 mt-1 shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-gray-900 text-sm truncate">
                              {txn.type || "Transaction"}
                            </p>
                            <span
                              className={`text-xs px-2 py-1 rounded-full shrink-0 ${
                                txn.status === "synced"
                                  ? "bg-green-100 text-green-800"
                                  : txn.status === "failed"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {txn.status}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {formatTime(txn.createdAt)}
                          </p>
                          {txn.amount && (
                            <p className="text-sm font-semibold text-gray-900 mt-1">
                              ₦{parseFloat(txn.amount).toLocaleString("en-NG", {
                                minimumFractionDigits: 2,
                              })}
                            </p>
                          )}
                        </div>
                      </div>
                    </button>

                    {/* Details */}
                    {showDetails === txn.id && (
                      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 text-xs space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-gray-600">ID:</span>
                            <p className="font-mono text-gray-900 break-all mt-0.5">
                              {txn.id}
                            </p>
                          </div>
                          {txn.recipient && (
                            <div>
                              <span className="text-gray-600">Recipient:</span>
                              <p className="text-gray-900 mt-0.5">
                                {txn.recipient}
                              </p>
                            </div>
                          )}
                        </div>
                        {txn.description && (
                          <div>
                            <span className="text-gray-600">Description:</span>
                            <p className="text-gray-900 mt-0.5">
                              {txn.description}
                            </p>
                          </div>
                        )}
                        {txn.lastError && (
                          <div className="bg-red-50 p-2 rounded border border-red-200">
                            <span className="text-red-700">Error:</span>
                            <p className="text-red-600 mt-0.5 break-words">
                              {txn.lastError}
                            </p>
                          </div>
                        )}
                        <div className="text-gray-600 pt-2 border-t border-gray-200">
                          Retries: {txn.retryCount || 0}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Action Buttons */}
              <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex gap-2">
                {isOnline && onSync && (
                  <button
                    onClick={onSync}
                    disabled={syncInProgress || isLoading}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                  >
                    <RefreshCw
                      className={`w-4 h-4 ${syncInProgress ? "animate-spin" : ""}`}
                    />
                    {syncInProgress ? "Syncing..." : "Sync Now"}
                  </button>
                )}
                <button
                  onClick={() => setExpanded(false)}
                  className="flex-1 px-3 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded hover:bg-gray-300 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default OfflineTransactionQueue;
