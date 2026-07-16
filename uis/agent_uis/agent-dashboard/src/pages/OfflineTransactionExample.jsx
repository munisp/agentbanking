/**
 * Offline Transactions Implementation Guide
 * 
 * This file shows how to integrate offline transaction support into any transaction page.
 * Follow these patterns to add offline support to other pages like Transfer, BillPayment, etc.
 */

import React, { useState, useEffect } from "react";
import { useOffline } from "../contexts/OfflineContext";
import OfflineTransactionQueue from "../components/OfflineTransactionQueue";

/**
 * Example: Offline-enabled Cash In Transaction
 * This pattern can be applied to any transaction operation
 */
export const OfflineTransactionExample = () => {
  const {
    isOnline,
    createTransaction,
    syncAll,
    getTransactionHistory,
    isCreating,
    error,
  } = useOffline();

  const [amount, setAmount] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [transactionError, setTransactionError] = useState(null);
  const [submitMessage, setSubmitMessage] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);

  /**
   * Handle transaction submission
   * Works both online and offline
   */
  const handleCashInTransaction = async (e) => {
    e.preventDefault();
    setTransactionError(null);
    setSubmitMessage(null);

    const transactionData = {
      type: "cash_in",
      amount: parseFloat(amount),
      recipientPhone,
      description: `Cash In - ${recipientPhone}`,
      status: "pending",
    };

    const onlineAction = async () => {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/agent/cash-in`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-tenant-id": localStorage.getItem("tenant_id") || "",
            "x-keycloak-id": localStorage.getItem("keycloakId") || "",
          },
          body: JSON.stringify({
            amount: parseFloat(amount),
            customer_phone: recipientPhone,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Transaction failed: ${response.statusText}`);
      }

      return await response.json();
    };

    const result = await createTransaction(transactionData, onlineAction);

    if (result.success) {
      setSubmitMessage(
        result.online
          ? `✓ Cash in successful! Reference: ${result.data?.reference || "N/A"}`
          : `✓ Cash in saved offline. Will sync when online.`
      );
      setAmount("");
      setRecipientPhone("");

      // Refresh transaction history
      setTimeout(() => getTransactionHistory(), 500);
    } else {
      setTransactionError(result.error || "Failed to process transaction");
    }
  };

  /**
   * Handle sync of pending transactions
   */
  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const syncFunction = async (transaction) => {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL}/agent/cash-in`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-tenant-id": localStorage.getItem("tenant_id") || "",
              "x-keycloak-id": localStorage.getItem("keycloakId") || "",
            },
            body: JSON.stringify({
              amount: transaction.amount,
              customer_phone: transaction.recipientPhone,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Sync failed: ${response.statusText}`);
        }

        return await response.json();
      };

      const result = await syncAll(syncFunction);
      setSubmitMessage(
        `✓ Synced ${result.synced} transaction${result.synced !== 1 ? "s" : ""}${
          result.failed > 0 ? ` (${result.failed} failed)` : ""
        }`
      );
    } catch (err) {
      setTransactionError(`Sync error: ${err.message}`);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Cash In Transaction
        </h1>
        <p className="text-gray-600 mb-8">
          {isOnline ? "✓ Online" : "⚠ Offline - Transactions will be saved locally"}
        </p>

        <form
          onSubmit={handleCashInTransaction}
          className="bg-white rounded-lg shadow p-6 mb-6"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Recipient Phone Number
              </label>
              <input
                type="tel"
                value={recipientPhone}
                onChange={(e) => setRecipientPhone(e.target.value)}
                placeholder="+234 XXX XXX XXXX"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Amount (₦)
              </label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                step="0.01"
                min="0"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
            </div>
          </div>

          {transactionError && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {transactionError}
            </div>
          )}

          {submitMessage && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
              {submitMessage}
            </div>
          )}

          <button
            type="submit"
            disabled={isCreating}
            className="mt-6 w-full px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isCreating ? "Processing..." : "Submit Cash In"}
          </button>
        </form>

        {/* Offline Transaction Queue Component */}
        <OfflineTransactionQueue
          onSync={handleSync}
          isLoading={isSyncing}
        />
      </div>
    </div>
  );
};

/**
 * INTEGRATION INSTRUCTIONS
 * ========================
 * 
 * 1. Add OfflineProvider to your App.jsx:
 *    
 *    import { OfflineProvider } from './contexts/OfflineContext';
 *    
 *    <OfflineProvider>
 *      <Routes>
 *        routes go here
 *      </Routes>
 *    </OfflineProvider>
 * 
 * 2. In any transaction page, import and use the hooks:
 * 
 *    import { useOffline } from '../contexts/OfflineContext';
 *    import OfflineTransactionQueue from '../components/OfflineTransactionQueue';
 * 
 *    const MyTransactionPage = () => {
 *      const { isOnline, createTransaction, syncAll } = useOffline();
 * 
 *      const handleSubmit = async () => {
 *        const result = await createTransaction(
 *          { type: 'transfer', amount: 100 },
 *          async () => {
 *            // Online action - make API call
 *            const res = await fetch('/api/transfer', {
 *              method: 'POST',
 *              body: JSON.stringify({ amount: 100 })
 *            });
 *            return res.json();
 *          }
 *        );
 *        // Handle result...
 *      };
 * 
 *      return (
 *        <>
 *          your form here
 *          <OfflineTransactionQueue onSync={handleSync} />
 *        </>
 *      );
 *    };
 * 
 * 3. Features automatically provided:
 *    - ✓ Automatic offline detection
 *    - ✓ Transaction queuing with IndexedDB
 *    - ✓ Automatic sync when online
 *    - ✓ Retry mechanism (3 attempts)
 *    - ✓ Transaction status tracking
 *    - ✓ UI status indicators
 * 
 * BENEFITS
 * ========
 * 
 * - Works in areas with poor connectivity
 * - No data loss during network interruptions
 * - Seamless online/offline transitions
 * - User-friendly status indicators
 * - Automatic retry mechanism
 * - Transaction history with offline markers
 */

export default OfflineTransactionExample;
