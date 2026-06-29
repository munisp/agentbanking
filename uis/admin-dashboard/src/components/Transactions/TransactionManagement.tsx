import {
  ArrowUpDown,
  Banknote,
  Calendar,
  CheckCircle,
  Clock,
  X as CloseIcon,
  Download,
  Eye,
  Filter,
  Printer,
  Receipt,
  RefreshCw,
  Search,
  TrendingUp,
  XCircle,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

// Transaction interface
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

const CORE_BANKING_URL = "https://54agent.upi.dev";

// Mock chart data - replace with real data when hourly metrics API is available
const mockTransactionTrends = [
  { hour: "00:00", transfers: 45, withdrawals: 23, deposits: 12, payments: 8 },
  { hour: "04:00", transfers: 32, withdrawals: 18, deposits: 8, payments: 5 },
  {
    hour: "08:00",
    transfers: 156,
    withdrawals: 89,
    deposits: 34,
    payments: 22,
  },
  {
    hour: "12:00",
    transfers: 234,
    withdrawals: 145,
    deposits: 56,
    payments: 45,
  },
  {
    hour: "16:00",
    transfers: 198,
    withdrawals: 112,
    deposits: 45,
    payments: 38,
  },
  {
    hour: "20:00",
    transfers: 167,
    withdrawals: 98,
    deposits: 38,
    payments: 28,
  },
];

const types = ["All", "Transfer", "Withdrawal", "Deposit"];
const statuses = ["All", "completed", "pending", "failed"];

const TransactionManagement: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedType, setSelectedType] = useState("All");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [dateRange, setDateRange] = useState("today");
  const [selectedTransaction, setSelectedTransaction] = useState<any>(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(100);
  const receiptRef = useRef<HTMLDivElement>(null);

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
        "Fetching transactions from:",
        `${CORE_BANKING_URL}/ledger/txn/?page=${page}&limit=${limit}`,
      );
      const res = await fetch(
        `${CORE_BANKING_URL}/ledger/txn/?page=${page}&limit=${limit}`,
        {
          headers: {
            ...tenantHeaders,
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: TransactionsResponse = await res.json();

      const transactionsData: Transaction[] = Array.isArray(data.transactions)
        ? data.transactions
        : [];

      console.log("Loaded transactions:", transactionsData.length);
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

  const handleRefresh = () => {
    fetchTransactions(true);
  };

  useEffect(() => {
    fetchTransactions(true);
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchTransactions(false);
    }, 30000);
    return () => clearInterval(interval);
  }, [page, limit]);

  // Map transactions to display format
  const normalizeStatus = (status?: string) => {
    const value = status?.toLowerCase().trim();
    switch (value) {
      case "completed":
      case "success":
      case "successful":
      case "succeeded":
        return "completed";
      case "pending":
      case "processing":
      case "queued":
      case "in_progress":
        return "pending";
      case "failed":
      case "error":
      case "declined":
      case "reversed":
        return "failed";
      default:
        return value || "unknown";
    }
  };

  const mappedTransactions = transactions.map((txn) => {
    const type =
      txn.payer === "MINT_ACCOUNT"
        ? "Deposit"
        : txn.payee === "MINT_ACCOUNT"
          ? "Withdrawal"
          : "Transfer";

    return {
      id: txn.transaction_id,
      customer: txn.payer !== "MINT_ACCOUNT" ? txn.payer : txn.payee,
      type,
      amount: parseFloat(txn.amount || "0"),
      fee: 0, // Fee not in current API response
      status: normalizeStatus(txn.status),
      date: new Date(txn.created_at).toLocaleString(),
      agent: txn.note || "N/A",
      reference: txn.transaction_id.substring(0, 8).toUpperCase(),
      payer_account: txn.payer_account_number,
      payee_account: txn.payee_account_number,
    };
  });

  const filteredTransactions = mappedTransactions.filter((txn) => {
    const matchesSearch =
      txn.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      txn.customer.toLowerCase().includes(searchTerm.toLowerCase()) ||
      txn.reference.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = selectedType === "All" || txn.type === selectedType;
    const matchesStatus =
      selectedStatus === "All" || txn.status === selectedStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  const totalAmount = filteredTransactions.reduce(
    (sum, txn) => sum + txn.amount,
    0,
  );
  const totalFees = filteredTransactions.reduce((sum, txn) => sum + txn.fee, 0);
  const completedCount = filteredTransactions.filter(
    (t) => t.status === "completed",
  ).length;
  const pendingCount = filteredTransactions.filter(
    (t) => t.status === "pending",
  ).length;
  const failedCount = filteredTransactions.filter(
    (t) => t.status === "failed",
  ).length;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
      minimumFractionDigits: 0,
    }).format(value);
  };

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    switch (statusLower) {
      case "completed":
      case "success":
        return "bg-green-100 text-green-800";
      case "pending":
      case "processing":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
      case "error":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "Transfer":
        return "text-[var(--tenant-primary-color,#004F71)] bg-[rgba(0,79,113,0.05)]";
      case "Withdrawal":
        return "text-green-600 bg-green-50";
      case "Deposit":
        return "text-purple-600 bg-purple-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  const handleViewReceipt = (transaction: any) => {
    setSelectedTransaction(transaction);
    setShowReceiptModal(true);
  };

  const handlePrintReceipt = () => {
    if (receiptRef.current) {
      const printContent = receiptRef.current.innerHTML;
      const printWindow = window.open("", "", "height=600,width=800");
      if (printWindow) {
        printWindow.document.write(`
          <html>
            <head>
              <title>Receipt - ${selectedTransaction?.id}</title>
              <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .receipt-content { max-width: 600px; margin: 0 auto; }
                @media print {
                  button { display: none; }
                }
              </style>
            </head>
            <body>
              <div class="receipt-content">${printContent}</div>
            </body>
          </html>
        `);
        printWindow.document.close();
        printWindow.print();
      }
    }
  };

  const handleDownloadReceipt = () => {
    if (!selectedTransaction) return;

    const receiptData = {
      id: selectedTransaction.id,
      customer: selectedTransaction.customer,
      type: selectedTransaction.type,
      amount: selectedTransaction.amount,
      fee: selectedTransaction.fee,
      status: selectedTransaction.status,
      date: selectedTransaction.date,
      agent: selectedTransaction.agent,
      reference: selectedTransaction.reference,
    };

    const blob = new Blob([JSON.stringify(receiptData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `receipt-${selectedTransaction.id}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Transaction Management
          </h1>
          <p className="text-gray-500 mt-1">
            Monitor and manage all platform transactions
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Volume</p>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {formatCurrency(totalAmount)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {filteredTransactions.length} transactions
              </p>
            </div>
            <Banknote className="w-10 h-10 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Completed</p>
              <p className="text-2xl font-bold text-green-600 mt-2">
                {completedCount}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {formatCurrency(
                  filteredTransactions
                    .filter((t) => t.status === "completed")
                    .reduce((sum, t) => sum + t.amount, 0),
                )}
              </p>
            </div>
            <CheckCircle className="w-10 h-10 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Pending</p>
              <p className="text-2xl font-bold text-yellow-600 mt-2">
                {pendingCount}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {formatCurrency(
                  filteredTransactions
                    .filter((t) => t.status === "pending")
                    .reduce((sum, t) => sum + t.amount, 0),
                )}
              </p>
            </div>
            <Clock className="w-10 h-10 text-yellow-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Fees</p>
              <p className="text-2xl font-bold text-[var(--tenant-primary-color,#004F71)] mt-2">
                {formatCurrency(totalFees)}
              </p>
              <p className="text-xs text-gray-500 mt-1">Revenue generated</p>
            </div>
            <TrendingUp className="w-10 h-10 text-[var(--tenant-primary-color,#004F71)]" />
          </div>
        </div>
      </div>

      {/* Transaction Trends Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Transaction Activity (24 Hours)
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={mockTransactionTrends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="hour" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="transfers"
              stroke="var(--tenant-primary-color,#004F71)"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="withdrawals"
              stroke="#10B981"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="deposits"
              stroke="#8B5CF6"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="payments"
              stroke="#F59E0B"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search transactions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              {types.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="7days">Last 7 Days</option>
              <option value="30days">Last 30 Days</option>
              <option value="custom">Custom Range</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading and Error States */}
      {isLoading && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-[var(--tenant-primary-color,#004F71)]" />
          <p className="mt-4 text-gray-600">Loading transactions...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          Failed to load transactions: {error}
        </div>
      )}

      {/* Transactions Table */}
      {!isLoading && !error && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Transaction ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Customer
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
                    Agent
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date/Time
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredTransactions.map((txn) => (
                  <tr key={txn.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {txn.id}
                      </div>
                      <div className="text-xs text-gray-500">
                        {txn.reference}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {txn.customer}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getTypeColor(txn.type)}`}
                      >
                        {txn.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-900">
                      {formatCurrency(txn.amount)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatCurrency(txn.fee)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {txn.agent}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(txn.status)}`}
                      >
                        {txn.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {txn.date}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => handleViewReceipt(txn)}
                        className="text-[var(--tenant-primary-color,#004F71)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] flex items-center gap-1"
                      >
                        <Eye className="w-4 h-4" />
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="bg-white px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing <span className="font-medium">1</span> to{" "}
              <span className="font-medium">{filteredTransactions.length}</span>{" "}
              of{" "}
              <span className="font-medium">{filteredTransactions.length}</span>{" "}
              results
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
                Previous
              </button>
              <button className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]">
                1
              </button>
              <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Receipt Modal */}
      {showReceiptModal && selectedTransaction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-[rgba(0,79,113,0.1)] rounded-lg">
                  <Receipt className="h-6 w-6 text-[var(--tenant-primary-color,#004F71)]" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Transaction Receipt
                  </h2>
                  <p className="text-sm text-gray-500">
                    {selectedTransaction.id}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowReceiptModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <CloseIcon className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div ref={receiptRef} className="p-6">
              {/* Receipt Header */}
              <div className="text-center mb-6 pb-6 border-b-2 border-gray-300">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  Payment Receipt
                </h3>
                <p className="text-sm text-gray-500">
                  {new Date().toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              </div>

              {/* Transaction Details */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Transaction ID
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selectedTransaction.id}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Reference
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selectedTransaction.reference}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Customer
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selectedTransaction.customer}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">Agent</p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selectedTransaction.agent}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">Type</p>
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTypeColor(selectedTransaction.type)}`}
                  >
                    {selectedTransaction.type}
                  </span>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">Status</p>
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(selectedTransaction.status)}`}
                  >
                    {selectedTransaction.status}
                  </span>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg col-span-2">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Date & Time
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selectedTransaction.date}
                  </p>
                </div>
              </div>

              {/* Amount Details */}
              <div className="border-t-2 border-gray-300 pt-6 mb-6">
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Amount</span>
                    <span className="text-lg font-semibold text-gray-900">
                      {formatCurrency(selectedTransaction.amount)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Transaction Fee</span>
                    <span className="text-lg font-semibold text-gray-900">
                      {formatCurrency(selectedTransaction.fee)}
                    </span>
                  </div>
                  <div className="border-t-2 border-gray-300 pt-3 mt-3">
                    <div className="flex justify-between items-center">
                      <span className="text-lg font-bold text-gray-900">
                        Total
                      </span>
                      <span className="text-2xl font-bold text-green-600">
                        {formatCurrency(
                          selectedTransaction.amount + selectedTransaction.fee,
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Footer Note */}
              <div className="bg-[rgba(0,79,113,0.05)] border border-[rgba(0,79,113,0.2)] rounded-lg p-4 text-center">
                <p className="text-sm text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]">
                  Thank you for your business!
                </p>
                <p className="text-xs text-[var(--tenant-primary-color,#004F71)] mt-1">
                  This is a computer-generated receipt and requires no signature
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex gap-3">
              <button
                onClick={handlePrintReceipt}
                className="flex-1 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors flex items-center justify-center gap-2"
              >
                <Printer className="w-4 h-4" />
                Print Receipt
              </button>
              <button
                onClick={handleDownloadReceipt}
                className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </button>
              <button
                onClick={() => setShowReceiptModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TransactionManagement;
