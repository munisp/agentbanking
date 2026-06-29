import { ArrowDownLeft, ArrowUpRight, Receipt } from "lucide-react";
import React, { useEffect, useState } from "react";
import { accountApi, STORAGE, userApi } from "../utils/api";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const Transactions = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    loadTransactions();
  }, [filter]);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      setError(null);

      // Demo mode: use mock data
      if (DEMO_MODE) {
        const mockTransactions = [
          {
            id: "tx-001",
            type: "credit",
            description: "Salary Payment",
            amount: 150000,
            created_at: new Date(
              Date.now() - 2 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-002",
            type: "debit",
            description: "Grocery Shopping",
            amount: 8500,
            created_at: new Date(
              Date.now() - 3 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-003",
            type: "debit",
            description: "Electricity Bill",
            amount: 12000,
            created_at: new Date(
              Date.now() - 5 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-004",
            type: "credit",
            description: "Refund",
            amount: 3500,
            created_at: new Date(
              Date.now() - 7 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-005",
            type: "debit",
            description: "Transfer to Savings",
            amount: 20000,
            created_at: new Date(
              Date.now() - 10 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-006",
            type: "credit",
            description: "Freelance Work",
            amount: 45000,
            created_at: new Date(
              Date.now() - 12 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-007",
            type: "debit",
            description: "Internet Subscription",
            amount: 15000,
            created_at: new Date(
              Date.now() - 15 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
          {
            id: "tx-008",
            type: "debit",
            description: "Restaurant",
            amount: 5200,
            created_at: new Date(
              Date.now() - 18 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            status: "completed",
          },
        ];

        const filtered =
          filter === "all"
            ? mockTransactions
            : mockTransactions.filter((tx) => tx.type === filter);

        setTransactions(filtered);
        setLoading(false);
        return;
      }

      // Resolve account number from keycloak ID
      const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
      if (!keycloakId) throw new Error("Not authenticated");

      const account = await accountApi.getByKeycloakId(keycloakId);
      const accountNumber = account?.account?.account_number;
      if (!accountNumber) throw new Error("Could not resolve account number");

      const response = await userApi.getTransactions(accountNumber, {
        limit: "50",
        page: "1",
      });
      const allTxns =
        response?.transactions ||
        response?.data ||
        (Array.isArray(response) ? response : []);

      // Apply type filter client-side (ledger endpoint doesn't support type param)
      const filtered =
        filter === "all" ? allTxns : allTxns.filter((tx) => tx.type === filter);
      setTransactions(filtered);
    } catch (err) {
      console.error("Failed to load transactions:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
        <div className="flex space-x-2">
          {["all", "credit", "debit"].map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-4 py-2 text-sm rounded-md transition-colors ${
                filter === type
                  ? "bg-green-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {transactions.length === 0 ? (
          <div className="p-8 text-center">
            <Receipt className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">No transactions found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {transactions.map((tx, index) => (
              <div
                key={tx.id || index}
                className="p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div
                      className={`p-2 rounded-full ${tx.type === "credit" ? "bg-green-100" : "bg-red-100"}`}
                    >
                      {tx.type === "credit" ? (
                        <ArrowDownLeft className="w-5 h-5 text-green-600" />
                      ) : (
                        <ArrowUpRight className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <div className="ml-4">
                      <p className="text-sm font-medium text-gray-900">
                        {/* Prefer note, fallback to description/type */}
                        {tx.note || tx.description || tx.type}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(tx.created_at).toLocaleDateString()} at {new Date(tx.created_at).toLocaleTimeString()}
                      </p>
                      {/* Show payer/payee details if available */}
                      {tx.payer_name && (
                        <p className="text-xs text-gray-400">
                          From: {tx.payer_name}
                          {tx.payer_account_number ? ` (${tx.payer_account_number})` : ""}
                        </p>
                      )}
                      {tx.payee_name && (
                        <p className="text-xs text-gray-400">
                          To: {tx.payee_name}
                          {tx.payee_account_number ? ` (${tx.payee_account_number})` : ""}
                        </p>
                      )}
                      {/* Show transaction id if available */}
                      {tx.transaction_id && (
                        <p className="text-xs text-gray-300">
                          Txn ID: {tx.transaction_id}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-sm font-semibold ${tx.type === "credit" ? "text-green-600" : "text-red-600"}`}
                    >
                      {tx.type === "credit" ? "+" : "-"}
                      {tx.currency || "NGN"}
                      {Number(Math.abs(tx.amount)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                    <p
                      className={`text-xs ${tx.status === "completed" || tx.status === "success" ? "text-green-500" : "text-yellow-500"}`}
                    >
                      {tx.status}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Transactions;
