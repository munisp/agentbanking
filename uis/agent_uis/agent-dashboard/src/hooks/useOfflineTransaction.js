import { useState, useCallback } from "react";
import { useOfflineStore } from "./useOfflineStore";

/**
 * Hook for handling offline transactions
 * Provides methods to create and manage offline transactions
 */
export function useOfflineTransaction() {
  const {
    isOnline,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    syncTransactions,
    allTransactions,
    pendingTransactions,
  } = useOfflineStore();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Create an offline transaction when offline
   * When online, attempts real transaction first, then falls back to offline
   */
  const createTransaction = useCallback(
    async (transactionData, onlineAction = null) => {
      setIsCreating(true);
      setError(null);

      try {
        // If online and have online action, try that first
        if (isOnline && onlineAction) {
          try {
            const result = await onlineAction();
            return { success: true, online: true, data: result };
          } catch (err) {
            // Fall through to offline storage if online action fails
            console.warn("Online transaction failed, saving offline:", err);
          }
        }

        // Save offline
        const offlineTransaction = await addTransaction({
          ...transactionData,
          timestamp: new Date().toISOString(),
        });

        return {
          success: true,
          offline: true,
          id: offlineTransaction.id,
          data: offlineTransaction,
          message: "Transaction saved offline. Will sync when online.",
        };
      } catch (err) {
        setError(err.message);
        return {
          success: false,
          error: err.message,
        };
      } finally {
        setIsCreating(false);
      }
    },
    [isOnline, addTransaction]
  );

  /**
   * Retry a failed transaction
   */
  const retryTransaction = useCallback(
    async (transactionId, onlineAction) => {
      try {
        if (isOnline && onlineAction) {
          await onlineAction();
          await updateTransaction(transactionId, {
            status: "synced",
            syncedAt: new Date().toISOString(),
          });
        }
        return { success: true };
      } catch (err) {
        setError(err.message);
        return { success: false, error: err.message };
      }
    },
    [isOnline, updateTransaction]
  );

  /**
   * Sync all pending transactions
   */
  const syncAll = useCallback(
    async (syncFunction) => {
      const result = await syncTransactions(syncFunction);
      return result;
    },
    [syncTransactions]
  );

  /**
   * Get transaction status
   */
  const getTransactionStatus = useCallback(
    (transactionId) => {
      const transaction = allTransactions.find((t) => t.id === transactionId);
      return transaction || null;
    },
    [allTransactions]
  );

  /**
   * Get transaction history including offline transactions
   */
  const getTransactionHistory = useCallback(() => {
    return allTransactions
      .sort(
        (a, b) =>
          new Date(b.createdAt || b.timestamp) -
          new Date(a.createdAt || a.timestamp)
      )
      .map((txn) => ({
        ...txn,
        isOffline: !txn.syncedAt,
        isFailed: txn.status === "failed",
      }));
  }, [allTransactions]);

  return {
    isOnline,
    isCreating,
    error,
    createTransaction,
    retryTransaction,
    syncAll,
    getTransactionStatus,
    getTransactionHistory,
    pendingTransactions,
    allTransactions,
    deleteTransaction,
    updateTransaction,
  };
}

export default useOfflineTransaction;
