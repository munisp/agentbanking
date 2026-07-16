import {
    Activity,
    AlertCircle,
    ArrowUpDown,
    Banknote,
    CheckCircle,
    Clock,
    Download,
    Filter,
    RefreshCw,
    Search,
    TrendingUp,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api } from "../utils/api";

interface Transaction {
  id: string;
  transaction_reference: string;
  transaction_type: string;
  transaction_status: string;
  transaction_amount: number;
  transaction_currency: string;
  fee_amount: number;
  commission_amount: number;
  total_amount: number;
  originator_agent_id: string;
  priority: string;
  initiated_at: string;
  completed_at?: string;
  channel: string;
}

interface TransactionListResponse {
  data: Transaction[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

interface CashPosition {
  agent_id: string;
  currency: string;
  current_balance: number;
  available_balance: number;
  reserved_balance: number;
  minimum_balance: number;
  last_updated_at: string;
}

interface SettlementBatch {
  id: string;
  batch_reference: string;
  settlement_date: string;
  status: string;
  total_transactions: number;
  total_amount: number;
  total_fees: number;
  total_commissions: number;
  net_settlement_amount: number;
  created_at: string;
}

const NetworkOperations: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [cashPosition, setCashPosition] = useState<CashPosition | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    loadTransactions();
  }, [currentPage, statusFilter, typeFilter]);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const filters: Record<string, string> = {};
      if (statusFilter !== "all") filters.status = statusFilter;
      if (typeFilter !== "all") filters.type = typeFilter;

      const response = await api.listNetworkTransactions(
        filters,
        currentPage,
        20,
      );
      setTransactions(Array.isArray(response) ? response : []);
      setTotalPages((response as any).total_pages || 1);
    } catch (error) {
      console.error("Failed to load transactions:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: "bg-green-100 text-green-800",
      pending: "bg-yellow-100 text-yellow-800",
      processing: "bg-blue-100 text-blue-800",
      failed: "bg-red-100 text-red-800",
      cancelled: "bg-gray-100 text-gray-800",
      reversed: "bg-purple-100 text-purple-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  const getStatusIcon = (status: string) => {
    const icons: Record<string, React.ReactNode> = {
      completed: <CheckCircle className="w-4 h-4" />,
      pending: <Clock className="w-4 h-4" />,
      processing: <Activity className="w-4 h-4 animate-spin" />,
      failed: <XCircle className="w-4 h-4" />,
      cancelled: <XCircle className="w-4 h-4" />,
    };
    return icons[status] || <AlertCircle className="w-4 h-4" />;
  };

  const formatTransactionType = (type: string) => {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const formatCurrency = (amount: number, currency: string = "NGN") => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency,
    }).format(amount);
  };

  const filteredTransactions = transactions.filter((tx) => {
    const searchLower = search.toLowerCase();
    return (
      tx.transaction_reference.toLowerCase().includes(searchLower) ||
      tx.id.toLowerCase().includes(searchLower) ||
      tx.originator_agent_id.toLowerCase().includes(searchLower)
    );
  });

  const stats = {
    total: transactions.length,
    completed: transactions.filter((t) => t.transaction_status === "completed")
      .length,
    pending: transactions.filter((t) => t.transaction_status === "pending")
      .length,
    failed: transactions.filter((t) => t.transaction_status === "failed")
      .length,
    totalAmount: transactions.reduce((sum, t) => sum + t.total_amount, 0),
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Network Operations
          </h1>
          <p className="text-gray-500 mt-1">
            Manage transactions, settlements, and cash positions
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={loadTransactions}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          {
            label: "Total Transactions",
            value: stats.total,
            icon: ArrowUpDown,
            color: "text-blue-500",
          },
          {
            label: "Completed",
            value: stats.completed,
            icon: CheckCircle,
            color: "text-green-500",
          },
          {
            label: "Pending",
            value: stats.pending,
            icon: Clock,
            color: "text-yellow-500",
          },
          {
            label: "Failed",
            value: stats.failed,
            icon: XCircle,
            color: "text-red-500",
          },
          {
            label: "Total Amount",
            value: formatCurrency(stats.totalAmount),
            icon: Banknote,
            color: "text-purple-500",
          },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">
                  {stat.label}
                </p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {loading ? "…" : stat.value}
                </p>
              </div>
              <stat.icon className={`w-10 h-10 ${stat.color}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by reference, ID, or agent..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All Types</option>
            <option value="cash_in">Cash In</option>
            <option value="cash_out">Cash Out</option>
            <option value="transfer">Transfer</option>
            <option value="bill_payment">Bill Payment</option>
            <option value="airtime_purchase">Airtime</option>
            <option value="data_purchase">Data</option>
          </select>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reference
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Fee
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Channel
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center">
                    <Activity
                      className="w-8 h-8 animate-spin mx-auto mb-2"
                      style={{ color: "var(--tenant-primary-color,#002082)" }}
                    />
                    <p className="text-gray-500">Loading transactions...</p>
                  </td>
                </tr>
              ) : filteredTransactions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center">
                    <AlertCircle className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                    <p className="text-gray-500">No transactions found</p>
                  </td>
                </tr>
              ) : (
                filteredTransactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {tx.transaction_reference}
                      </div>
                      <div className="text-xs text-gray-500">
                        {tx.id.slice(0, 8)}...
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-gray-900">
                        {formatTransactionType(tx.transaction_type)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-semibold text-gray-900">
                        {formatCurrency(
                          tx.transaction_amount,
                          tx.transaction_currency,
                        )}
                      </div>
                      <div className="text-xs text-gray-500">
                        Total: {formatCurrency(tx.total_amount)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatCurrency(tx.fee_amount)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                          tx.transaction_status,
                        )}`}
                      >
                        {getStatusIcon(tx.transaction_status)}
                        {tx.transaction_status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {tx.channel}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(tx.initiated_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
            <div className="flex-1 flex justify-between sm:hidden">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() =>
                  setCurrentPage(Math.min(totalPages, currentPage + 1))
                }
                disabled={currentPage === totalPages}
                className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                Next
              </button>
            </div>
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Page <span className="font-medium">{currentPage}</span> of{" "}
                  <span className="font-medium">{totalPages}</span>
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() =>
                      setCurrentPage(Math.min(totalPages, currentPage + 1))
                    }
                    disabled={currentPage === totalPages}
                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Next
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NetworkOperations;
