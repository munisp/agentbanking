/**
 * Offline Transaction Utilities
 * Helper functions for common offline transaction operations
 */

/**
 * Create an offline-ready transaction data object
 */
export const createOfflineTransactionData = (type, details) => {
  return {
    type,
    timestamp: new Date().toISOString(),
    status: "pending",
    ...details,
  };
};

/**
 * Format transaction status for display
 */
export const getStatusDisplay = (status) => {
  const statusMap = {
    pending: { label: "Pending", color: "blue", icon: "⏳" },
    failed: { label: "Failed", color: "red", icon: "❌" },
    synced: { label: "Synced", color: "green", icon: "✓" },
  };
  return statusMap[status] || { label: "Unknown", color: "gray", icon: "?" };
};

/**
 * Format offline transaction for display in transaction list
 */
export const formatOfflineTransaction = (transaction) => {
  const status = getStatusDisplay(transaction.status);
  return {
    ...transaction,
    displayStatus: status.label,
    statusColor: status.color,
    statusIcon: status.icon,
    isOffline: true,
    formattedAmount: `₦${parseFloat(transaction.amount || 0).toLocaleString("en-NG", {
      minimumFractionDigits: 2,
    })}`,
  };
};

/**
 * Merge online and offline transactions for combined history
 */
export const mergeTransactionHistory = (onlineTransactions, offlineTransactions) => {
  const merged = [
    ...onlineTransactions.map((t) => ({ ...t, isOffline: false })),
    ...offlineTransactions.map((t) => formatOfflineTransaction(t)),
  ];

  // Sort by date (newest first)
  return merged.sort((a, b) => {
    const dateA = new Date(a.createdAt || a.timestamp || 0);
    const dateB = new Date(b.createdAt || b.timestamp || 0);
    return dateB - dateA;
  });
};

/**
 * Calculate total of offline pending transactions
 */
export const calculateOfflinePendingTotal = (transactions) => {
  return transactions
    .filter((t) => t.status === "pending")
    .reduce((sum, t) => sum + (parseFloat(t.amount) || 0), 0);
};

/**
 * Group transactions by status
 */
export const groupTransactionsByStatus = (transactions) => {
  return {
    pending: transactions.filter((t) => t.status === "pending"),
    synced: transactions.filter((t) => t.status === "synced"),
    failed: transactions.filter((t) => t.status === "failed"),
  };
};

/**
 * Get retry-eligible transactions
 */
export const getRetryEligibleTransactions = (transactions) => {
  return transactions.filter(
    (t) => t.status === "failed" && (t.retryCount || 0) < 3
  );
};

/**
 * Format error message for display
 */
export const formatErrorMessage = (error) => {
  if (typeof error === "string") return error;
  if (error?.message) return error.message;
  if (error?.response?.data?.message)
    return error.response.data.message;
  return "An error occurred";
};

/**
 * Detect if user is likely to go offline (using Network Information API)
 */
export const getNetworkInfo = () => {
  if (!navigator?.connection) {
    return {
      effectiveType: "unknown",
      downlink: null,
      rtt: null,
      saveData: false,
    };
  }

  const conn = navigator.connection;
  return {
    effectiveType: conn.effectiveType, // '4g', '3g', '2g', 'slow-2g'
    downlink: conn.downlink,
    rtt: conn.rtt,
    saveData: conn.saveData,
  };
};

/**
 * Check if network is likely to be unstable
 */
export const isNetworkUnstable = () => {
  const info = getNetworkInfo();
  return (
    info.effectiveType === "2g" ||
    info.effectiveType === "slow-2g" ||
    (info.rtt && info.rtt > 400) // High round-trip time
  );
};

/**
 * Get time remaining until auto-retry
 */
export const getRetryTimeRemaining = (transaction, baseRetryDelay = 5000) => {
  const retryCount = transaction.retryCount || 0;
  const exponentialDelay = baseRetryDelay * Math.pow(2, retryCount);
  const createdAt = new Date(transaction.createdAt || transaction.timestamp);
  const retryAt = new Date(createdAt.getTime() + exponentialDelay);
  const now = new Date();

  if (retryAt <= now) return 0;

  const remaining = Math.ceil((retryAt - now) / 1000);
  return remaining;
};

/**
 * Format time remaining for display
 */
export const formatTimeRemaining = (seconds) => {
  if (seconds <= 0) return "Now";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)}m`;
  return `${Math.ceil(seconds / 3600)}h`;
};

/**
 * Create sync function wrapper with common error handling
 */
export const createSyncFunction = (apiEndpoint, transformData = (d) => d) => {
  return async (transaction) => {
    const response = await fetch(apiEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-tenant-id": localStorage.getItem("tenant_id") || "",
        "x-keycloak-id": localStorage.getItem("keycloakId") || "",
      },
      body: JSON.stringify(transformData(transaction)),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || response.statusText);
    }

    return response.json();
  };
};

/**
 * Batch sync with rate limiting
 */
export const createBatchSyncFunction = (
  apiEndpoint,
  batchSize = 5,
  delayMs = 1000
) => {
  return async (transactions) => {
    const batches = [];
    for (let i = 0; i < transactions.length; i += batchSize) {
      batches.push(transactions.slice(i, i + batchSize));
    }

    const results = [];
    for (let i = 0; i < batches.length; i++) {
      const batch = batches[i];
      if (i > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }

      for (const transaction of batch) {
        try {
          const response = await fetch(apiEndpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-tenant-id": localStorage.getItem("tenant_id") || "",
              "x-keycloak-id": localStorage.getItem("keycloakId") || "",
            },
            body: JSON.stringify(transaction),
          });

          if (response.ok) {
            results.push({ id: transaction.id, success: true });
          } else {
            results.push({ id: transaction.id, success: false });
          }
        } catch (error) {
          results.push({ id: transaction.id, success: false });
        }
      }
    }

    return results;
  };
};

export default {
  createOfflineTransactionData,
  getStatusDisplay,
  formatOfflineTransaction,
  mergeTransactionHistory,
  calculateOfflinePendingTotal,
  groupTransactionsByStatus,
  getRetryEligibleTransactions,
  formatErrorMessage,
  getNetworkInfo,
  isNetworkUnstable,
  getRetryTimeRemaining,
  formatTimeRemaining,
  createSyncFunction,
  createBatchSyncFunction,
};
