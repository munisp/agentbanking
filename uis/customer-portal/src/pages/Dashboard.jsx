import {
  ArrowDownLeft,
  ArrowUpRight,
  PiggyBank,
  QrCode,
  Receipt,
  Send,
  Smartphone,
  TrendingUp,
  Wallet,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import StorefrontAdsBanner from "../components/StorefrontAdsBanner";
import { useAuth } from "../hooks/useAuth";
import { accountApi, userApi } from "../utils/api";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const Dashboard = () => {
  const { user } = useAuth();
  const [accountSummary, setAccountSummary] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDashboardData();
  }, [user?.keycloakId]);

  const loadDashboardData = async () => {
    if (!user?.keycloakId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      // Demo mode: use mock data
      if (DEMO_MODE) {
        setAccountSummary({
          available_balance: 125450.75,
          savings_balance: 50000.0,
          monthly_transactions: 48320.5,
        });

        setRecentTransactions([
          {
            id: "tx-001",
            type: "credit",
            description: "Salary Payment",
            amount: 150000,
            created_at: new Date(
              Date.now() - 2 * 24 * 60 * 60 * 1000,
            ).toISOString(),
          },
          {
            id: "tx-002",
            type: "debit",
            description: "Grocery Shopping",
            amount: 8500,
            created_at: new Date(
              Date.now() - 3 * 24 * 60 * 60 * 1000,
            ).toISOString(),
          },
          {
            id: "tx-003",
            type: "debit",
            description: "Electricity Bill",
            amount: 12000,
            created_at: new Date(
              Date.now() - 5 * 24 * 60 * 60 * 1000,
            ).toISOString(),
          },
          {
            id: "tx-004",
            type: "credit",
            description: "Refund",
            amount: 3500,
            created_at: new Date(
              Date.now() - 7 * 24 * 60 * 60 * 1000,
            ).toISOString(),
          },
          {
            id: "tx-005",
            type: "debit",
            description: "Transfer to Savings",
            amount: 20000,
            created_at: new Date(
              Date.now() - 10 * 24 * 60 * 60 * 1000,
            ).toISOString(),
          },
        ]);

        setLoading(false);
        return;
      }

      // Fetch account details by keycloak ID
      const accountResponse = await accountApi.getByKeycloakId(user.keycloakId);
      const account =
        accountResponse.account || accountResponse.data || accountResponse;

      setAccountSummary({
        available_balance: account.balance ?? account.available_balance ?? 0,
        savings_balance: account.savings_balance ?? 0,
        monthly_transactions: account.monthly_transactions ?? 0,
        accountNumber: account.account_number ?? account.accountNumber ?? null,
        currency: account.currency ?? "NGN",
      });

      // Fetch recent transactions
      const accountNumber = account.account_number ?? account.accountNumber;
      if (accountNumber) {
        const txResponse = await userApi.getTransactions(accountNumber, {
          limit: "50",
          page: "1",
        });
        setRecentTransactions(
          Array.isArray(txResponse?.transactions) ? txResponse.transactions : [],
        );
      } else {
        setRecentTransactions([]);
      }
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setError(err.message);
      // Set empty defaults on error
      setAccountSummary({
        available_balance: 0,
        savings_balance: 0,
        monthly_transactions: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const getTransactionType = (tx) => {
    const accountNumber = String(accountSummary?.accountNumber || "");
    if (!accountNumber) return "debit";

    if (String(tx?.payee_account_number || "") === accountNumber) {
      return "credit";
    }

    if (String(tx?.payer_account_number || "") === accountNumber) {
      return "debit";
    }

    return "debit";
  };

  const getTransactionDescription = (tx) => {
    return tx?.note || tx?.tag || "Transfer";
  };

  const getTransactionAmount = (tx) => {
    const value = Number.parseFloat(String(tx?.amount ?? 0));
    return Number.isNaN(value) ? 0 : value;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-6">
      {error && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Header with gradient background */}
      <div className="bg-linear-to-r from-green-600 via-emerald-600 to-teal-600 rounded-2xl shadow-xl p-8 text-white">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold mb-2">
              Welcome back, {user?.name || "Customer"}
            </h1>
            <p className="text-green-100 text-lg">
              Here's your account overview
            </p>
          </div>
          {accountSummary?.accountNumber && (
            <div className="bg-white/10 backdrop-blur-sm border border-white/30 rounded-xl px-6 py-4">
              <p className="text-green-100 text-sm font-medium mb-1">
                Account Number
              </p>
              <p className="text-2xl font-bold font-mono tracking-wider">
                {accountSummary.accountNumber}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Storefront Ads Banner */}
      <StorefrontAdsBanner maxAds={5} />

      {/* Account Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 p-6 border border-gray-100 hover:border-green-200 transform hover:-translate-y-1">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Available Balance
              </p>
              <p className="text-3xl font-bold text-gray-900">
                ₦{accountSummary?.available_balance?.toLocaleString() || "0.00"}
              </p>
            </div>
            <div className="bg-linear-to-br from-green-500 to-green-600 p-4 rounded-2xl shadow-md">
              <Wallet className="w-7 h-7 text-white" />
            </div>
          </div>
        </div>

        {/* <div className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 p-6 border border-gray-100 hover:border-blue-200 transform hover:-translate-y-1">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Savings Balance
              </p>
              <p className="text-3xl font-bold text-gray-900">
                ₦{accountSummary?.savings_balance?.toLocaleString() || "0.00"}
              </p>
            </div>
            <div className="bg-linear-to-br from-blue-500 to-blue-600 p-4 rounded-2xl shadow-md">
              <PiggyBank className="w-7 h-7 text-white" />
            </div>
          </div>
        </div> */}

        <div className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 p-6 border border-gray-100 hover:border-purple-200 transform hover:-translate-y-1">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                This Month
              </p>
              <p className="text-3xl font-bold text-gray-900">
                ₦
                {accountSummary?.monthly_transactions?.toLocaleString() ||
                  "0.00"}
              </p>
            </div>
            <div className="bg-linear-to-br from-purple-500 to-purple-600 p-4 rounded-2xl shadow-md">
              <TrendingUp className="w-7 h-7 text-white" />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      {/* <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button className="flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 hover:border-green-300 hover:bg-green-50 transition-all transform hover:-translate-y-1 hover:shadow-md">
            <Send className="w-10 h-10 text-green-600 mb-3" />
            <span className="text-sm font-semibold text-gray-700">
              Send Money
            </span>
          </button>
          <button className="flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-all transform hover:-translate-y-1 hover:shadow-md">
            <Receipt className="w-10 h-10 text-blue-600 mb-3" />
            <span className="text-sm font-semibold text-gray-700">
              Pay Bills
            </span>
          </button>
          <button className="flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 hover:border-purple-300 hover:bg-purple-50 transition-all transform hover:-translate-y-1 hover:shadow-md">
            <Smartphone className="w-10 h-10 text-purple-600 mb-3" />
            <span className="text-sm font-semibold text-gray-700">
              Buy Airtime
            </span>
          </button>
          <button className="flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-all transform hover:-translate-y-1 hover:shadow-md">
            <QrCode className="w-10 h-10 text-orange-600 mb-3" />
            <span className="text-sm font-semibold text-gray-700">Scan QR</span>
          </button>
        </div>
      </div> */}

      {/* Recent Transactions */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            Recent Transactions
          </h2>
          <a
            href="/transactions"
            className="text-sm text-green-600 hover:text-green-700 font-semibold hover:underline"
          >
            View all →
          </a>
        </div>

        {recentTransactions.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No recent transactions
          </p>
        ) : (
          <div className="space-y-4">
            {recentTransactions.slice(0, 5).map((tx, index) => {
              const txType = getTransactionType(tx);
              const txAmount = getTransactionAmount(tx);
              return (
              <div
                key={tx.id || index}
                className="flex items-center justify-between p-4 border-b border-gray-100 last:border-0 hover:bg-gray-50 rounded-lg transition-colors"
              >
                <div className="flex items-center">
                  <div
                    className={`p-2 rounded-full ${txType === "credit" ? "bg-green-100" : "bg-red-100"}`}
                  >
                    {txType === "credit" ? (
                      <ArrowDownLeft className="w-5 h-5 text-green-600" />
                    ) : (
                      <ArrowUpRight className="w-5 h-5 text-red-600" />
                    )}
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-900">
                      {getTransactionDescription(tx)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(tx.completed_at || tx.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-sm font-semibold ${txType === "credit" ? "text-green-600" : "text-red-600"}`}
                >
                  {txType === "credit" ? "+" : "-"}₦
                  {Math.abs(txAmount).toLocaleString()}
                </span>
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
