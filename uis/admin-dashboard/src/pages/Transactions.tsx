import {
    Activity,
    ArrowDownRight,
    ArrowUpRight,
    Download,
    FileText,
    RefreshCw,
    Search,
    TrendingUp,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { getTenantHeadersFromStorage } from "../services/tenant";

interface Transaction {
  id: string;
  amount: string;
  ledger_id: string;
  status: string;
  transaction_id: string;
  created_at: string;
  completed_at: string | null;
  currency: string;
  deleted_at: string | null;
  note: string;
  payer: string;
  payer_account_number: string;
  payee_account_number: string;
  tag: string;
  payee: string;
  tenant_id: string;
  updated_at: string;
}

interface TransactionsResponse {
  message: string;
  transactions: Transaction[];
}

interface MetricsResponse {
  metrics: {
    total_count: number;
    total_volume: number;
  };
}

const Transactions: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<{
    total_count: number;
    total_volume: number;
  } | null>(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);

  // Fetch transaction metrics
  const fetchMetrics = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      const res = await fetch(`https://54agent.upi.dev/ledger/txn/metrics`, {
        headers: {
          ...tenantHeaders,
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });
      if (res.ok) {
        const data: MetricsResponse = await res.json();
        setMetrics(data.metrics);
      }
    } catch (err) {
      console.error("Metrics fetch error:", err);
    }
  };

  // Fetch transactions with pagination
  const fetchTransactions = async (setLoading = true) => {
    if (setLoading) {
      setIsLoading(true);
      setError(null);
    }
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      console.log(
        "Admin Dashboard - Fetching transactions with headers:",
        tenantHeaders,
      );
      const res = await fetch(
        `https://54agent.upi.dev/ledger/txn/?page=${page}&limit=${limit}`,
        {
          headers: {
            ...tenantHeaders,
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        },
      );
      console.log("Admin Dashboard - Transactions API response:", res.status);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: TransactionsResponse = await res.json();

      // Response structure: { message: "success", transactions: [...] }
      const transactionsData: Transaction[] = Array.isArray(data.transactions)
        ? data.transactions
        : [];

      console.log(
        "Admin Dashboard - Loaded transactions:",
        transactionsData.length,
      );
      setTransactions(transactionsData);
    } catch (err: any) {
      console.error("Transactions fetch error:", err);
      if (setLoading) {
        setError(err.message);
        setTransactions([]);
      }
    } finally {
      if (setLoading) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchMetrics();
    // Refresh metrics every 30 seconds
    const metricsInterval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(metricsInterval);
  }, []);

  useEffect(() => {
    fetchTransactions(true);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchTransactions(false), 10000);
    return () => clearInterval(interval);
  }, [page, limit]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((txn) => {
      const matchesSearch =
        !searchQuery ||
        txn.id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.transaction_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.note?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.payer?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.payee?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.amount?.includes(searchQuery);

      const matchesStatus =
        statusFilter === "all" ||
        txn.status?.toLowerCase() === statusFilter.toLowerCase();

      // Derive type from payer/payee (if payer is MINT_ACCOUNT, it's a deposit; if payee is MINT_ACCOUNT, it's a withdrawal)
      const derivedType =
        txn.payer === "MINT_ACCOUNT"
          ? "deposit"
          : txn.payee === "MINT_ACCOUNT"
            ? "withdrawal"
            : "transfer";
      const matchesType =
        typeFilter === "all" ||
        derivedType?.toLowerCase() === typeFilter.toLowerCase();

      return matchesSearch && matchesStatus && matchesType;
    });
  }, [transactions, searchQuery, statusFilter, typeFilter]);

  const stats = useMemo(() => {
    return {
      totalVolume: filteredTransactions.reduce(
        (sum, t) => sum + parseFloat(t.amount || "0"),
        0,
      ),
      successRate:
        filteredTransactions.length > 0
          ? Math.round(
              (filteredTransactions.filter((t) => t.status === "success")
                .length /
                filteredTransactions.length) *
                100,
            )
          : 0,
    };
  }, [filteredTransactions]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "success") return "bg-green-100 text-green-800";
    if (statusLower === "failed") return "bg-red-100 text-red-800";
    if (statusLower === "pending") return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  const getTypeIcon = (payer: string, payee: string) => {
    if (payer === "MINT_ACCOUNT")
      return <ArrowDownRight className="h-5 w-5 text-green-600" />;
    if (payee === "MINT_ACCOUNT")
      return <ArrowUpRight className="h-5 w-5 text-red-600" />;
    return <Activity className="h-5 w-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />;
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Transactions
          </h1>
          <p className="text-gray-600 mt-1">View all transaction records</p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]">
          <Download className="h-5 w-5 mr-2" />
          Export
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Transactions</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--tenant-primary-color,#002082)" }}>
            {metrics?.total_count || filteredTransactions.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Volume</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            ₦{((metrics?.total_volume || stats.totalVolume) / 1000).toFixed(1)}K
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Success Rate</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {stats.successRate}%
          </p>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search transactions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-3 border border-gray-300 rounded-lg"
        >
          <option value="all">All Statuses</option>
          <option value="success">Success</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-4 py-3 border border-gray-300 rounded-lg"
        >
          <option value="all">All Types</option>
          <option value="deposit">Deposits</option>
          <option value="withdrawal">Withdrawals</option>
          <option value="transfer">Transfers</option>
        </select>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="text-center py-12">
            <RefreshCw className="h-8 w-8 text-blue-400 animate-spin mx-auto mb-2" />
            <p className="text-gray-500">Loading...</p>
          </div>
        ) : filteredTransactions.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No transactions found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Transaction ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredTransactions.map((txn) => {
                  const type =
                    txn.payer === "MINT_ACCOUNT"
                      ? "deposit"
                      : txn.payee === "MINT_ACCOUNT"
                        ? "withdrawal"
                        : "transfer";
                  return (
                    <tr key={txn.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <div className="p-2 bg-blue-100 rounded-lg mr-3">
                            {getTypeIcon(txn.payer, txn.payee)}
                          </div>
                          <div>
                            <p className="font-mono text-sm">
                              {txn.transaction_id}
                            </p>
                            <p className="text-xs text-gray-500">
                              {txn.note || "-"}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm capitalize">{type}</td>
                      <td className="px-6 py-4 font-semibold">
                        {txn.currency} {parseFloat(txn.amount).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                            txn.status,
                          )}`}
                        >
                          {txn.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {new Date(
                          txn.created_at.replace(" ", "T"),
                        ).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Transactions;
