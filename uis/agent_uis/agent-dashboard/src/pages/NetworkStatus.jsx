import {
    Activity,
    AlertCircle,
    AlertTriangle,
    Banknote,
    CheckCircle,
    DollarSign,
    Filter,
    RefreshCw,
    TrendingDown,
    TrendingUp,
    Wifi,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { networkOperationsApi } from "../utils/api";

const NetworkStatus = () => {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");

  useEffect(() => {
    loadData();
  }, [typeFilter, channelFilter]);

  const loadData = async () => {
    setLoading(true);
    try {
      const filters = {};
      if (typeFilter !== "all") filters.type = typeFilter;
      if (channelFilter !== "all") filters.channel = channelFilter;

      const res = await networkOperationsApi.getPredictions(filters);
      setPredictions(res.predictions || []);
    } catch (err) {
      console.error("Failed to load predictions:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadData();
  };

  const getSuccessColor = (rate) => {
    if (rate >= 90) return "text-green-600 bg-green-50";
    if (rate >= 75) return "text-yellow-600 bg-yellow-50";
    if (rate >= 50) return "text-orange-600 bg-orange-50";
    return "text-red-600 bg-red-50";
  };

  const getSuccessIcon = (rate) => {
    if (rate >= 90) return <CheckCircle className="w-5 h-5" />;
    if (rate >= 75) return <TrendingUp className="w-5 h-5" />;
    if (rate >= 50) return <TrendingDown className="w-5 h-5" />;
    return <AlertTriangle className="w-5 h-5" />;
  };

  const formatType = (type) =>
    type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const formatMedium = (name) =>
    name
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  // Get top performers by transaction type
  const topPerformers = predictions.filter((p) => p.rate >= 90).slice(0, 5);

  const averageSuccessRate =
    predictions.length > 0
      ? (
          predictions.reduce((sum, p) => sum + p.rate, 0) / predictions.length
        ).toFixed(1)
      : 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Wifi className="w-7 h-7" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Network Status & Predictions
          </h1>
          <p className="text-gray-600 mt-1">
            Real-time channel success rate monitoring
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <DollarSign className="w-8 h-8" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            <span className="text-sm text-gray-500">Active Channels</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {predictions.length}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <CheckCircle className="w-8 h-8 text-green-600" />
            <span className="text-sm text-gray-500">Avg Success Rate</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {averageSuccessRate}%
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="w-8 h-8 text-emerald-600" />
            <span className="text-sm text-gray-500">High Success</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {predictions.filter((p) => p.rate >= 90).length}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <AlertCircle className="w-8 h-8 text-red-600" />
            <span className="text-sm text-gray-500">Low Success</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {predictions.filter((p) => p.rate < 75).length}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div className="flex gap-4 items-center">
          <Filter className="w-5 h-5 text-gray-500" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Transaction Types</option>
            <option value="transfer">Transfer</option>
            <option value="withdrawal">Withdrawal</option>
            <option value="airtime">Airtime</option>
            <option value="data">Data</option>
            <option value="bill_payment">Bill Payment</option>
          </select>

          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Channels</option>
            <option value="pos">POS Terminal</option>
            <option value="ussd">USSD</option>
            <option value="web">Web Portal</option>
            <option value="app">Mobile App</option>
          </select>
        </div>
      </div>

      {/* Top Performers */}
      {topPerformers.length > 0 && (
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-lg border border-green-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            Top Performing Channels (≥90% Success)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {topPerformers.map((pred, idx) => (
              <div
                key={idx}
                className="bg-white p-4 rounded-lg border border-green-200 shadow-sm"
              >
                <div className="font-semibold text-gray-900">
                  {formatMedium(pred.name)}
                </div>
                <div className="text-xs text-gray-600 uppercase mt-1">
                  {pred.channel} • {formatType(pred.type)}
                </div>
                <div className="text-2xl font-bold text-green-600 mt-2">
                  {pred.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Predictions Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Channel Success Rates
          </h2>
        </div>

        {loading && (
          <div className="flex justify-center items-center py-12">
            <Activity
              className="w-8 h-8 animate-spin"
              style={{ color: "var(--tenant-primary-color,#002082)" }}
            />
          </div>
        )}

        {!loading && predictions.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No predictions available. Try adjusting your filters.
          </div>
        )}

        {!loading && predictions.length > 0 && (
          <div className="overflow-x-auto max-h-[60vh] overflow-scroll">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Provider
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Channel
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Success Rate
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Transactions
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Confidence
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {predictions
                  .sort((a, b) => b.rate - a.rate)
                  .map((pred, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">
                          {formatMedium(pred.name)}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatType(pred.type)}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs uppercase font-medium text-gray-600 bg-gray-100 px-2 py-1 rounded">
                          {pred.channel}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div
                          className={`inline-flex items-center gap-2 px-3 py-1 rounded-full font-semibold ${getSuccessColor(pred.rate)}`}
                        >
                          {getSuccessIcon(pred.rate)}
                          <span>{pred.status}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {pred.total_txns.toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            pred.confidence === "high"
                              ? "bg-blue-100 text-blue-800"
                              : pred.confidence === "medium"
                                ? "bg-gray-100 text-gray-800"
                                : "bg-gray-50 text-gray-600"
                          }`}
                        >
                          {pred.confidence}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default NetworkStatus;
//       .split("_")
//       .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
//       .join(" ");

//   const formatCurrency = (amount, currency = "NGN") =>
//     new Intl.NumberFormat("en-NG", { style: "currency", currency }).format(
//       amount || 0,
//     );

//   const filtered = transactions.filter((tx) => {
//     const q = search.toLowerCase();
//     return (
//       (tx.transaction_reference || "").toLowerCase().includes(q) ||
//       (tx.id || "").toLowerCase().includes(q) ||
//       (tx.originator_agent_id || "").toLowerCase().includes(q)
//     );
//   });

//   const stats = {
//     total: totalCount,
//     completed: transactions.filter((t) => t.transaction_status === "completed")
//       .length,
//     pending: transactions.filter((t) => t.transaction_status === "pending")
//       .length,
//     failed: transactions.filter((t) => t.transaction_status === "failed")
//       .length,
//     totalAmount: transactions.reduce((s, t) => s + (t.total_amount || 0), 0),
//   };

//   return (
//     <div className="space-y-6 p-6">
//       {/* Header */}
//       <div className="flex justify-between items-center">
//         <div>
//           <h1 className="text-3xl font-bold text-gray-900">
//             Network Operations
//           </h1>
//           <p className="text-gray-500 mt-1">
//             Your transactions and float position
//           </p>
//         </div>
//         <button
//           onClick={handleRefresh}
//           disabled={loading}
//           className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
//         >
//           <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
//           Refresh
//         </button>
//       </div>

//       {/* Cash Position Card */}
//       {!cashLoading && cashPosition && (
//         <div className="bg-linear-to-r from-blue-600 to-blue-700 rounded-xl p-6 text-white">
//           <div className="flex items-center justify-between mb-4">
//             <h2 className="text-lg font-semibold">Float / Cash Position</h2>
//             <DollarSign className="w-8 h-8 opacity-75" />
//           </div>
//           <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
//             <div>
//               <p className="text-blue-200 text-xs mb-1">Current Balance</p>
//               <p className="text-2xl font-bold">
//                 {formatCurrency(
//                   cashPosition.current_balance,
//                   cashPosition.currency,
//                 )}
//               </p>
//             </div>
//             <div>
//               <p className="text-blue-200 text-xs mb-1">Available Balance</p>
//               <p className="text-xl font-semibold">
//                 {formatCurrency(
//                   cashPosition.available_balance,
//                   cashPosition.currency,
//                 )}
//               </p>
//             </div>
//             <div>
//               <p className="text-blue-200 text-xs mb-1">Reserved</p>
//               <p className="text-xl font-semibold">
//                 {formatCurrency(
//                   cashPosition.reserved_balance,
//                   cashPosition.currency,
//                 )}
//               </p>
//             </div>
//             <div>
//               <p className="text-blue-200 text-xs mb-1">Minimum Required</p>
//               <p className="text-xl font-semibold">
//                 {formatCurrency(
//                   cashPosition.minimum_balance,
//                   cashPosition.currency,
//                 )}
//               </p>
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Stats */}
//       <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
//         {[
//           {
//             label: "Total Transactions",
//             value: stats.total,
//             icon: ArrowUpDown,
//             color: "text-blue-500",
//           },
//           {
//             label: "Completed",
//             value: stats.completed,
//             icon: CheckCircle,
//             color: "text-green-500",
//           },
//           {
//             label: "Pending",
//             value: stats.pending,
//             icon: Clock,
//             color: "text-yellow-500",
//           },
//           {
//             label: "Failed",
//             value: stats.failed,
//             icon: XCircle,
//             color: "text-red-500",
//           },
//           {
//             label: "Page Amount",
//             value: formatCurrency(stats.totalAmount),
//             icon: Banknote,
//             color: "text-purple-500",
//           },
//         ].map((stat) => (
//           <div key={stat.label} className="bg-white rounded-xl shadow p-5">
//             <div className="flex items-center justify-between">
//               <div>
//                 <p className="text-sm font-medium text-gray-500">
//                   {stat.label}
//                 </p>
//                 <p className="text-2xl font-bold text-gray-900 mt-1">
//                   {loading ? "…" : stat.value}
//                 </p>
//               </div>
//               <stat.icon className={`w-10 h-10 ${stat.color}`} />
//             </div>
//           </div>
//         ))}
//       </div>

//       {/* Filters */}
//       <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
//         <div className="relative flex-1 min-w-50">
//           <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
//           <input
//             type="text"
//             placeholder="Search by reference, ID, or agent…"
//             value={search}
//             onChange={(e) => setSearch(e.target.value)}
//             className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
//           />
//         </div>
//         <div className="flex items-center gap-2">
//           <Filter className="w-4 h-4 text-gray-400" />
//           <select
//             value={statusFilter}
//             onChange={(e) => {
//               setCurrentPage(1);
//               setStatusFilter(e.target.value);
//             }}
//             className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
//           >
//             <option value="all">All Status</option>
//             <option value="completed">Completed</option>
//             <option value="pending">Pending</option>
//             <option value="processing">Processing</option>
//             <option value="failed">Failed</option>
//             <option value="cancelled">Cancelled</option>
//           </select>
//           <select
//             value={typeFilter}
//             onChange={(e) => {
//               setCurrentPage(1);
//               setTypeFilter(e.target.value);
//             }}
//             className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
//           >
//             <option value="all">All Types</option>
//             <option value="cash_in">Cash In</option>
//             <option value="cash_out">Cash Out</option>
//             <option value="transfer">Transfer</option>
//             <option value="bill_payment">Bill Payment</option>
//             <option value="airtime_purchase">Airtime</option>
//             <option value="data_purchase">Data</option>
//             <option value="merchant_payment">Merchant Payment</option>
//           </select>
//         </div>
//       </div>

//       {/* Transactions Table */}
//       <div className="bg-white rounded-xl shadow overflow-hidden">
//         <div className="overflow-x-auto">
//           <table className="w-full">
//             <thead className="bg-gray-50 border-b border-gray-200">
//               <tr>
//                 {[
//                   "Reference",
//                   "Type",
//                   "Amount",
//                   "Fee",
//                   "Status",
//                   "Channel",
//                   "Date",
//                 ].map((h) => (
//                   <th
//                     key={h}
//                     className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
//                   >
//                     {h}
//                   </th>
//                 ))}
//               </tr>
//             </thead>
//             <tbody className="bg-white divide-y divide-gray-200">
//               {loading ? (
//                 <tr>
//                   <td colSpan={7} className="px-6 py-8 text-center">
//                     <Activity className="w-8 h-8 animate-spin mx-auto text-blue-600 mb-2" />
//                     <p className="text-gray-500">Loading transactions…</p>
//                   </td>
//                 </tr>
//               ) : filtered.length === 0 ? (
//                 <tr>
//                   <td colSpan={7} className="px-6 py-8 text-center">
//                     <TrendingUp className="w-8 h-8 mx-auto text-gray-400 mb-2" />
//                     <p className="text-gray-500">No transactions found</p>
//                   </td>
//                 </tr>
//               ) : (
//                 filtered.map((tx) => (
//                   <tr
//                     key={tx.id}
//                     className="hover:bg-gray-50 transition-colors"
//                   >
//                     <td className="px-6 py-4 whitespace-nowrap">
//                       <div className="text-sm font-medium text-gray-900">
//                         {tx.transaction_reference}
//                       </div>
//                       <div className="text-xs text-gray-500">
//                         {(tx.id || "").slice(0, 8)}…
//                       </div>
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
//                       {formatType(tx.transaction_type || "")}
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap">
//                       <div className="text-sm font-semibold text-gray-900">
//                         {formatCurrency(
//                           tx.transaction_amount,
//                           tx.transaction_currency,
//                         )}
//                       </div>
//                       <div className="text-xs text-gray-500">
//                         Total: {formatCurrency(tx.total_amount)}
//                       </div>
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
//                       {formatCurrency(tx.fee_amount)}
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap">
//                       <span
//                         className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(tx.transaction_status)}`}
//                       >
//                         {getStatusIcon(tx.transaction_status)}
//                         {tx.transaction_status}
//                       </span>
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
//                       {tx.channel}
//                     </td>
//                     <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
//                       {tx.initiated_at
//                         ? new Date(tx.initiated_at).toLocaleString()
//                         : "—"}
//                     </td>
//                   </tr>
//                 ))
//               )}
//             </tbody>
//           </table>
//         </div>

//         {/* Pagination */}
//         {totalPages > 1 && (
//           <div className="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
//             <p className="text-sm text-gray-700">
//               Page <span className="font-medium">{currentPage}</span> of{" "}
//               <span className="font-medium">{totalPages}</span>
//               {" · "}
//               <span className="font-medium">{totalCount}</span> total
//             </p>
//             <nav className="inline-flex rounded-md shadow-sm -space-x-px">
//               <button
//                 onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
//                 disabled={currentPage === 1}
//                 className="relative inline-flex items-center px-3 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
//               >
//                 Previous
//               </button>
//               <button
//                 onClick={() =>
//                   setCurrentPage(Math.min(totalPages, currentPage + 1))
//                 }
//                 disabled={currentPage === totalPages}
//                 className="relative inline-flex items-center px-3 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
//               >
//                 Next
//               </button>
//             </nav>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// };

// export default NetworkStatus;
