import React, { useState, useEffect } from "react";
import { WifiOff, Wifi, AlertCircle } from "lucide-react";
import { useOfflineStore } from "../hooks/useOfflineStore";

/**
 * Global Offline Status Indicator
 * Can be placed in header or top bar to show connection status
 */
export const OfflineStatusIndicator = ({ showPendingCount = true }) => {
  const { isOnline, pendingTransactions } = useOfflineStore();
  const [showTooltip, setShowTooltip] = useState(false);

  const pendingCount = pendingTransactions.length;
  const failedCount = pendingTransactions.filter(
    (t) => t.status === "failed"
  ).length;

  if (isOnline && pendingCount === 0) {
    return null; // No need to show anything if everything is fine
  }

  return (
    <div className="relative">
      <button
        className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors relative"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        title={isOnline ? "Online - but has pending transactions" : "Offline"}
      >
        {isOnline ? (
          <>
            <Wifi className="w-4 h-4 text-green-600" />
            <span className="text-green-700">Online</span>
            {showPendingCount && pendingCount > 0 && (
              <span className="ml-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs font-semibold">
                {pendingCount}
              </span>
            )}
          </>
        ) : (
          <>
            <WifiOff className="w-4 h-4 text-orange-600 animate-pulse" />
            <span className="text-orange-700">Offline</span>
            {showPendingCount && pendingCount > 0 && (
              <span className="ml-1 px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full text-xs font-semibold">
                {pendingCount}
              </span>
            )}
          </>
        )}
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div
          className="absolute right-0 top-full mt-2 bg-gray-900 text-white text-xs rounded-lg p-3 w-48 shadow-lg z-50"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {isOnline ? (
                <>
                  <Wifi className="w-3 h-3 text-green-400" />
                  <span>Connected to internet</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3 h-3 text-orange-400 animate-pulse" />
                  <span>No internet connection</span>
                </>
              )}
            </div>

            {pendingCount > 0 && (
              <>
                <div className="border-t border-gray-700 pt-1 mt-1">
                  <div className="flex items-center justify-between gap-2">
                    <span>{pendingCount} pending transaction{pendingCount !== 1 ? "s" : ""}</span>
                    {failedCount > 0 && (
                      <span className="flex items-center gap-1 text-red-400">
                        <AlertCircle className="w-3 h-3" />
                        {failedCount} failed
                      </span>
                    )}
                  </div>
                  {isOnline && (
                    <p className="text-gray-400 text-xs mt-1">
                      Click the transaction queue to sync
                    </p>
                  )}
                </div>
              </>
            )}

            {!isOnline && (
              <div className="border-t border-gray-700 pt-1 mt-1 text-gray-400 text-xs">
                Transactions will be saved and synced when online
              </div>
            )}
          </div>

          {/* Tooltip arrow */}
          <div className="absolute right-4 -top-1 w-2 h-2 bg-gray-900 rotate-45"></div>
        </div>
      )}
    </div>
  );
};

/**
 * Simplified Offline Status Badge
 * Minimal version for compact layouts
 */
export const OfflineStatusBadge = () => {
  const { isOnline, pendingTransactions } = useOfflineStore();

  if (isOnline && pendingTransactions.length === 0) {
    return null;
  }

  return (
    <div
      className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
        isOnline
          ? "bg-yellow-100 text-yellow-700"
          : "bg-orange-100 text-orange-700"
      }`}
      title={
        isOnline
          ? `${pendingTransactions.length} pending`
          : "Offline - will sync when connected"
      }
    >
      {isOnline ? (
        <Wifi className="w-3 h-3" />
      ) : (
        <WifiOff className="w-3 h-3 animate-pulse" />
      )}
      {pendingTransactions.length > 0 && (
        <span>{pendingTransactions.length}</span>
      )}
    </div>
  );
};

/**
 * Full Network Status Component
 * Shows detailed network and sync information
 */
export const NetworkStatusPanel = () => {
  const { isOnline, pendingTransactions, lastSyncTime, syncInProgress } =
    useOfflineStore();

  const formatTime = (timestamp) => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins === 1) return "1 minute ago";
    if (diffMins < 60) return `${diffMins} minutes ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours === 1) return "1 hour ago";
    if (diffHours < 24) return `${diffHours} hours ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "Yesterday";
    return `${diffDays} days ago`;
  };

  const pendingCount = pendingTransactions.length;
  const syncedCount = pendingTransactions.filter(
    (t) => t.status === "synced"
  ).length;
  const failedCount = pendingTransactions.filter(
    (t) => t.status === "failed"
  ).length;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-900 mb-3">Network Status</h3>

      <div className="space-y-3">
        {/* Connection Status */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Connection:</span>
          <div className="flex items-center gap-2">
            {isOnline ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm font-medium text-green-700">Online</span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-orange-700">Offline</span>
              </>
            )}
          </div>
        </div>

        {/* Pending Transactions */}
        {pendingCount > 0 && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Pending:</span>
              <span className="text-sm font-medium text-blue-700">
                {pendingCount} transaction{pendingCount !== 1 ? "s" : ""}
              </span>
            </div>

            {syncedCount > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Synced:</span>
                <span className="text-sm font-medium text-green-700">
                  {syncedCount}
                </span>
              </div>
            )}

            {failedCount > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Failed:</span>
                <span className="text-sm font-medium text-red-700">
                  {failedCount}
                </span>
              </div>
            )}
          </>
        )}

        {/* Last Sync Time */}
        {lastSyncTime && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Last sync:</span>
            <span className="text-sm text-gray-700">{formatTime(lastSyncTime)}</span>
          </div>
        )}

        {/* Sync Status */}
        {syncInProgress && (
          <div className="flex items-center gap-2 text-sm text-blue-700">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
            <span>Syncing transactions...</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default OfflineStatusIndicator;
