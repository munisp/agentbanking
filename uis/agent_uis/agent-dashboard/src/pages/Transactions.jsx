import {
    Activity,
    ArrowDownRight,
    ArrowUpRight,
    X as CloseIcon,
    Download,
    Eye,
    FileText,
    Filter,
    Printer,
    Receipt,
    RefreshCw,
    Search,
    TrendingUp,
} from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi, agentApi, authHeaders, inventoryApi } from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const Transactions = () => {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [transactions, setTransactions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [userAccountNumbers, setUserAccountNumbers] = useState([]);
  const receiptRef = useRef(null);

  const fetchTransactions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const keycloakId = user?.keycloakId;
      if (keycloakId) {
        // Fetch agent profile (same as Dashboard)
        await agentApi.getAgentByKeycloakId(keycloakId);

        // Fetch account details (same as Dashboard)
        let accountNumber = null;
        const accountNums = [];
        try {
          const accountResp =
            await accountApi.getAccountByKeycloakId(keycloakId);
          const account = accountResp.account ?? accountResp;
          accountNumber = account?.account_number;
          if (accountNumber) accountNums.push(accountNumber);
        } catch (accountErr) {
          console.error("Account fetch error:", accountErr);
        }

        // Fetch stores (same as Dashboard)
        let stores = [];
        try {
          const storesResp = await inventoryApi.getStores(keycloakId);
          stores = Array.isArray(storesResp.data)
            ? storesResp.data
            : Array.isArray(storesResp)
              ? storesResp
              : [];

          // Collect store account numbers for credit/debit detection
          stores.forEach((store) => {
            if (store.account_number) accountNums.push(store.account_number);
          });
        } catch (storesErr) {
          console.error("Stores fetch error:", storesErr);
        }

        setUserAccountNumbers(accountNums);

        const allTransactions = [];

        // Fetch agent account transactions (same as Dashboard)
        if (accountNumber) {
          try {
            const res = await fetch(
              `${CORE_BANKING_URL}/ledger/txn/account-number/${accountNumber}?limit=50&page=1`,
              { headers: { ...authHeaders() } },
            );
            if (res.ok) {
              const data = await res.json();
              const agentTxns = (data.transactions || []).map((txn) => ({
                ...txn,
                source: "My Account",
                sourceType: "agent",
              }));
              allTransactions.push(...agentTxns);
            }
          } catch (txnErr) {
            console.error("Agent transactions fetch error:", txnErr);
          }
        }

        // Fetch store transactions (same as Dashboard)
        const storeTransactionPromises = stores.map(async (store) => {
          if (store.account_number) {
            try {
              const res = await fetch(
                `${CORE_BANKING_URL}/ledger/txn/account-number/${store.account_number}?limit=50&page=1`,
                { headers: { ...authHeaders() } },
              );
              if (res.ok) {
                const data = await res.json();
                return (data.transactions || []).map((txn) => ({
                  ...txn,
                  source: store.name,
                  sourceType: "store",
                  storeId: store.id,
                }));
              }
            } catch (err) {
              console.error(
                `Transactions fetch error for store ${store.id}:`,
                err,
              );
            }
          }
          return [];
        });

        const storeTransactionsArrays = await Promise.all(
          storeTransactionPromises,
        );
        storeTransactionsArrays.forEach((txns) =>
          allTransactions.push(...txns),
        );

        // Sort newest first (same as Dashboard)
        allTransactions.sort(
          (a, b) => new Date(b.created_at) - new Date(a.created_at),
        );

        setTransactions(allTransactions);
      } else {
        setTransactions([]);
      }
    } catch (err) {
      console.error("Transactions fetch error:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Mirror Dashboard: only run when user is available
  useEffect(() => {
    if (user) fetchTransactions();
  }, [user]);

  const getTransactionType = (txn) => {
    if (userAccountNumbers.includes(txn.payee_account_number)) return "credit";
    if (userAccountNumbers.includes(txn.payer_account_number)) return "debit";
    return "unknown";
  };

  const filteredTransactions = useMemo(() => {
    return transactions.filter((txn) => {
      const matchesSearch =
        !searchQuery ||
        txn.transaction_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.note?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.payer?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.payee?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        txn.payer_account_number?.includes(searchQuery) ||
        txn.payee_account_number?.includes(searchQuery);

      const matchesStatus =
        statusFilter === "all" ||
        txn.status?.toLowerCase() === statusFilter.toLowerCase();

      const type = getTransactionType(txn);
      const matchesType = typeFilter === "all" || type === typeFilter;

      return matchesSearch && matchesStatus && matchesType;
    });
  }, [transactions, searchQuery, statusFilter, typeFilter, userAccountNumbers]);

  const stats = useMemo(() => {
    const totalAmount = filteredTransactions.reduce(
      (sum, t) => sum + parseFloat(t.amount || 0),
      0,
    );
    const completed = filteredTransactions.filter(
      (t) =>
        t.status?.toLowerCase() === "success" ||
        t.status?.toLowerCase() === "completed",
    ).length;
    const failed = filteredTransactions.filter(
      (t) =>
        t.status?.toLowerCase() === "failed" ||
        t.status?.toLowerCase() === "error",
    ).length;
    const pending = filteredTransactions.filter(
      (t) =>
        t.status?.toLowerCase() === "pending" ||
        t.status?.toLowerCase() === "processing",
    ).length;

    return {
      totalAmount,
      completed,
      failed,
      pending,
      successRate:
        filteredTransactions.length > 0
          ? Math.round((completed / filteredTransactions.length) * 100)
          : 0,
    };
  }, [filteredTransactions]);

  const getTypeIcon = (txn) => {
    const type = getTransactionType(txn);
    if (type === "credit")
      return <ArrowDownRight className="h-5 w-5 text-green-600" />;
    if (type === "debit")
      return <ArrowUpRight className="h-5 w-5 text-red-600" />;
    return <Activity className="h-5 w-5 text-blue-600" />;
  };

  const getTypeColor = (txn) => {
    const type = getTransactionType(txn);
    if (type === "credit") return "bg-green-100";
    if (type === "debit") return "bg-red-100";
    return "bg-blue-100";
  };

  const getStatusColor = (status) => {
    const s = status?.toLowerCase();
    if (s === "success" || s === "completed")
      return "bg-green-100 text-green-800";
    if (s === "failed" || s === "error") return "bg-red-100 text-red-800";
    if (s === "pending" || s === "processing")
      return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  const handleViewReceipt = (transaction) => {
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
              <title>Receipt - ${selectedTransaction?.transaction_id}</title>
              <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .receipt-content { max-width: 600px; margin: 0 auto; }
                @media print { button { display: none; } }
              </style>
            </head>
            <body><div class="receipt-content">${printContent}</div></body>
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
      transaction_id: selectedTransaction.transaction_id,
      amount: selectedTransaction.amount,
      currency: selectedTransaction.currency,
      status: selectedTransaction.status,
      payer: selectedTransaction.payer,
      payee: selectedTransaction.payee,
      payer_account_number: selectedTransaction.payer_account_number,
      payee_account_number: selectedTransaction.payee_account_number,
      note: selectedTransaction.note,
      created_at: selectedTransaction.created_at,
    };
    const blob = new Blob([JSON.stringify(receiptData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `receipt-${selectedTransaction.transaction_id}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Transactions
          </h1>
          <p className="text-gray-600 mt-1">
            View and manage all your transactions
          </p>
        </div>
        <button className="inline-flex items-center justify-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors w-full sm:w-auto">
          <Download className="h-5 w-5 mr-2" />
          Export
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          Failed to load transactions: {error}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Transactions</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">
            {filteredTransactions.length}
          </p>
          <p className="text-xs text-gray-500 mt-1">All time</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Volume</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            ₦{(stats.totalAmount / 1000).toFixed(1)}K
          </p>
          <p className="text-xs text-gray-500 mt-1">All transactions</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Success Rate</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {stats.successRate}%
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {stats.completed} successful
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Failed</p>
          <p className="text-2xl font-bold text-red-600 mt-1">{stats.failed}</p>
          <p className="text-xs text-gray-500 mt-1">{stats.pending} pending</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by transaction ID, account, or note..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <div className="flex items-center space-x-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full sm:w-auto px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">All Statuses</option>
              <option value="success">Success</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className="flex items-center space-x-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full sm:w-auto px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">All Types</option>
              <option value="credit">Credits (Money In)</option>
              <option value="debit">Debits (Money Out)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="md:hidden divide-y divide-gray-100 max-h-[60vh] overflow-scroll">
          {filteredTransactions.map((txn) => {
            const type = getTransactionType(txn);
            return (
              <div key={txn.id} className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center min-w-0 gap-2">
                    <div className={`p-2 ${getTypeColor(txn)} rounded-lg`}>
                      {getTypeIcon(txn)}
                    </div>
                    <div className="min-w-0">
                      <p className="font-mono text-xs font-medium text-gray-900 truncate">
                        {txn.transaction_id}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {txn.note || "No note"}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(txn.status)}`}
                  >
                    {txn.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-gray-500">Type</p>
                    <p className="text-gray-800 capitalize font-medium">
                      {type}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Amount</p>
                    <p className="text-gray-900 font-semibold">
                      {txn.currency}{" "}
                      {parseFloat(txn.amount || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">From</p>
                    <p className="text-gray-700 font-mono truncate">
                      {txn.payer_account_number || "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">To</p>
                    <p className="text-gray-700 font-mono truncate">
                      {txn.payee_account_number || "-"}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500">
                    {new Date(
                      txn.created_at?.replace(" ", "T"),
                    ).toLocaleString()}
                  </p>
                  <button
                    onClick={() => handleViewReceipt(txn)}
                    className="text-blue-600 hover:text-blue-900 text-xs font-medium inline-flex items-center gap-1"
                  >
                    <Eye className="w-4 h-4" />
                    View
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="hidden md:block overflow-x-auto max-h-[60vh] overflow-scroll">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Transaction ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  From Account
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  To Account
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredTransactions.map((txn) => {
                const type = getTransactionType(txn);
                return (
                  <tr key={txn.id} className="hover:bg-gray-50 cursor-pointer">
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <div
                          className={`p-2 ${getTypeColor(txn)} rounded-lg mr-3`}
                        >
                          {getTypeIcon(txn)}
                        </div>
                        <div>
                          <p className="font-mono text-sm font-medium text-gray-900">
                            {txn.transaction_id}
                          </p>
                          <p className="text-xs text-gray-500">
                            {txn.note || "No note"}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 capitalize">
                      {type}
                    </td>
                    <td className="px-6 py-4">
                      <p className="font-semibold text-gray-900">
                        {txn.currency}{" "}
                        {parseFloat(txn.amount || 0).toLocaleString()}
                      </p>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(txn.status)}`}
                      >
                        {txn.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-gray-600">
                      {txn.payer_account_number || "-"}
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-gray-600">
                      {txn.payee_account_number || "-"}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <p>
                        {new Date(
                          txn.created_at?.replace(" ", "T"),
                        ).toLocaleDateString()}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(
                          txn.created_at?.replace(" ", "T"),
                        ).toLocaleTimeString()}
                      </p>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium">
                      <button
                        onClick={() => handleViewReceipt(txn)}
                        className="text-blue-600 hover:text-blue-900 flex items-center gap-1"
                      >
                        <Eye className="w-4 h-4" />
                        View
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {filteredTransactions.length === 0 && !isLoading && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {error
              ? "Could not load transactions."
              : "No transactions found matching your criteria."}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <RefreshCw className="h-8 w-8 text-blue-400 animate-spin mx-auto mb-2" />
          <p className="text-gray-500">Loading transactions...</p>
        </div>
      )}

      {/* Receipt Modal */}
      {showReceiptModal && selectedTransaction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Receipt className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Transaction Receipt
                  </h2>
                  <p className="text-sm text-gray-500">
                    {selectedTransaction.transaction_id}
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 p-4 rounded-lg col-span-2">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Transaction ID
                  </p>
                  <p className="text-sm font-semibold text-gray-900 font-mono">
                    {selectedTransaction.transaction_id}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    From Account
                  </p>
                  <p className="text-sm font-semibold text-gray-900 font-mono">
                    {selectedTransaction.payer_account_number ||
                      selectedTransaction.payer ||
                      "-"}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    To Account
                  </p>
                  <p className="text-sm font-semibold text-gray-900 font-mono">
                    {selectedTransaction.payee_account_number ||
                      selectedTransaction.payee ||
                      "-"}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase mb-1">Type</p>
                  <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full capitalize bg-blue-100 text-blue-800">
                    {getTransactionType(selectedTransaction)}
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
                    {new Date(
                      selectedTransaction.created_at?.replace(" ", "T"),
                    ).toLocaleString()}
                  </p>
                </div>
                {selectedTransaction.note && (
                  <div className="bg-gray-50 p-4 rounded-lg col-span-2">
                    <p className="text-xs text-gray-500 uppercase mb-1">Note</p>
                    <p className="text-sm text-gray-900">
                      {selectedTransaction.note}
                    </p>
                  </div>
                )}
              </div>

              <div className="border-t-2 border-gray-300 pt-6 mb-6">
                <div className="flex justify-between items-center">
                  <span className="text-lg font-bold text-gray-900">
                    Total Amount
                  </span>
                  <span className="text-2xl font-bold text-green-600">
                    {selectedTransaction.currency}{" "}
                    {parseFloat(
                      selectedTransaction.amount || 0,
                    ).toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                <p className="text-sm text-blue-900">
                  Thank you for your business!
                </p>
                <p className="text-xs text-blue-700 mt-1">
                  This is a computer-generated receipt and requires no signature
                </p>
              </div>
            </div>

            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex gap-3">
              <button
                onClick={handlePrintReceipt}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
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

export default Transactions;
