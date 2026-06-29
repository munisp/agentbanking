import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  CreditCard,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../utils/api";
import { getTenantHeadersFromStorage } from "../../services/tenant";

// Mock Data — kept only as fallback shape reference for charts
const mockTransactionData = [
  { month: "Jan", transactions: 0, revenue: 0, users: 0 },
  { month: "Feb", transactions: 0, revenue: 0, users: 0 },
  { month: "Mar", transactions: 0, revenue: 0, users: 0 },
  { month: "Apr", transactions: 0, revenue: 0, users: 0 },
  { month: "May", transactions: 0, revenue: 0, users: 0 },
  { month: "Jun", transactions: 0, revenue: 0, users: 0 },
];

const mockTransactionTypes = [
  { name: "Transfers", value: 45, color: "var(--tenant-primary-color,#004F71)" },
  { name: "Withdrawals", value: 25, color: "#10B981" },
  { name: "Deposits", value: 20, color: "#F59E0B" },
  { name: "Bill Payments", value: 10, color: "#EF4444" },
];

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


const parseTransactionDate = (txn: any) => {
  const raw = txn?.completed_at || txn?.created_at || txn?.timestamp;
  if (!raw) return null;
  if (typeof raw === "string") {
    return new Date(raw.includes("T") ? raw : raw.replace(" ", "T"));
  }
  return new Date(raw);
};

const getTransactionTypeLabel = (txn: any) => {
  const tag = (txn?.tag || "").toString().toLowerCase();
  const note = (txn?.note || "").toString().toLowerCase();

  if (tag === "transfer" || note.includes("transfer")) return "Transfer";
  if (tag === "withdrawal" || note.includes("withdrawal")) return "Withdrawal";
  if (tag === "deposit" || note.includes("deposit")) return "Deposit";
  if (tag === "bill_payment" || note.includes("bill payment"))
    return "Bill Payment";
  if (tag === "airtime_purchase" || note.includes("airtime"))
    return "Airtime Purchase";
  if (tag === "data_bundle" || note.includes("data bundle"))
    return "Data Bundle";

  return "Transfer";
};

const normalizeStatus = (status?: string) => {
  const value = (status || "").toLowerCase().trim();

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

const formatTransactionAmount = (txn: Transaction) =>
  Number(txn.amount || 0) || 0;

const parseDashboardTransactionDate = (txn: Transaction) => {
  const raw = txn.completed_at || txn.created_at || txn.updated_at;
  if (!raw) {
    return null;
  }

  return new Date(raw.includes("T") ? raw : raw.replace(" ", "T"));
};

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<"7d" | "30d" | "90d">("30d");

  // Live counts fetched from the API
  const [agentCount, setAgentCount] = useState<number | null>(null);
  const [customerCount, setCustomerCount] = useState<number | null>(null);
  const [adminCount, setAdminCount] = useState<number | null>(null);
  const [liveAgents, setLiveAgents] = useState<
    { name: string; status: string; agent_role: string }[]
  >([]);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Transaction data
  const [transactionData, setTransactionData] =
    useState<any[]>(mockTransactionData);
  const [transactionTypes, setTransactionTypes] =
    useState<any[]>(mockTransactionTypes);
  const [recentTransactions, setRecentTransactions] =
    useState<Transaction[]>([]);

  const loadData = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();

      const [agentsResp, customersResp, adminsResp, transactionsResp] =
        await Promise.allSettled([
          api.getAgents(),
          api.getCustomers(),
          api.getAdmins(),
          fetch(`https://54agent.upi.dev/ledger/txn/?page=1&limit=10`, {
            headers: {
              ...tenantHeaders,
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }).then(async (res) => {
            if (!res.ok) {
              throw new Error(`${res.status} ${res.statusText}`);
            }
            return res.json();
          }),
        ]);

      if (agentsResp.status === "fulfilled") {
        const agents = agentsResp.value.agents ?? [];
        setAgentCount(agents.length);
        setLiveAgents(agents.slice(0, 5));
      }
      if (customersResp.status === "fulfilled") {
        setCustomerCount((customersResp.value.users ?? []).length);
      }
      if (adminsResp.status === "fulfilled") {
        setAdminCount((adminsResp.value.admins ?? []).length);
      }

      if (transactionsResp.status === "fulfilled") {
        const data = transactionsResp.value as TransactionsResponse;
        const transactions = Array.isArray(data.transactions)
          ? data.transactions
          : [];

        const sortedRecentTransactions = [...transactions].sort((a, b) => {
          const timeA = parseTransactionDate(a)?.getTime() || 0;
          const timeB = parseTransactionDate(b)?.getTime() || 0;
          return timeB - timeA;
        });

        setRecentTransactions(sortedRecentTransactions);

        // Keep the dashboard trends derived from live transaction records.
        const monthlyData = processMonthlyTransactions(transactions);
        setTransactionData(monthlyData);

        // Use mock transaction type data for dashboard chart
        setTransactionTypes(mockTransactionTypes);
      }
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  // Helper function to process monthly transaction data
  const processMonthlyTransactions = (transactions: any[]) => {
    const monthNames = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    const monthlyStats: Record<
      string,
      { transactions: number; revenue: number }
    > = {};

    // Initialize last 6 months
    const now = new Date();
    for (let i = 5; i >= 0; i--) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const monthKey = monthNames[date.getMonth()];
      monthlyStats[monthKey] = { transactions: 0, revenue: 0 };
    }

    // Process transactions
    transactions.forEach((txn: any) => {
      if (txn.created_at || txn.timestamp) {
        const date = new Date(txn.created_at || txn.timestamp);
        const monthKey = monthNames[date.getMonth()];

        if (monthlyStats[monthKey]) {
          monthlyStats[monthKey].transactions += 1;
          monthlyStats[monthKey].revenue += Number(
            txn.amount || txn.credit || 0,
          );
        }
      }
    });

    // Convert to array
    return Object.keys(monthlyStats).map((month) => ({
      month,
      transactions: monthlyStats[month].transactions,
      revenue: monthlyStats[month].revenue,
    }));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => loadData();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-NG").format(value);
  };

  const getStatusColor = (status: string) => {
    switch ((status || "").toLowerCase()) {
      case "success":
      case "completed":
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

  return (
    <div className="space-y-8 p-6">
      {/* Header with gradient background */}
      <div className="bg-gradient-to-r  from-[var(--tenant-primary-color,#00196a)] via-[var(--tenant-primary-color,#00196a)] to-[var(--tenant-secondary-color,#69BC5E)]  rounded-2xl shadow-xl p-8 text-white">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold mb-2">Dashboard Overview</h1>
            <p className="text-white opacity-90 text-lg">
              Welcome back! Here's what's happening with your platform today.
            </p>
          </div>
          <div className="flex gap-3">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as any)}
              className="px-4 py-2.5 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white focus:ring-2 focus:ring-white/50 focus:border-transparent"
            >
              <option value="7d" className="text-gray-900">
                Last 7 Days
              </option>
              <option value="30d" className="text-gray-900">
                Last 30 Days
              </option>
              <option value="90d" className="text-gray-900">
                Last 90 Days
              </option>
            </select>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="px-5 py-2.5 bg-white rounded-xl hover:bg-gray-50 transition-all flex items-center gap-2 disabled:opacity-50 font-semibold shadow-lg hover:shadow-xl"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            >
              <RefreshCw
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {fetchError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
          Could not load live data: {fetchError}
        </div>
      )}

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Agents"
          value={agentCount !== null ? formatNumber(agentCount) : "—"}
          change={null}
          icon={Users}
          iconBg="bg-[rgba(0,79,113,0.05)]0"
        />
        <MetricCard
          title="Total Customers"
          value={
            customerCount !== null ? `10${formatNumber(customerCount)}` : "—"
          }
          change={null}
          icon={Users}
          iconBg="bg-purple-500"
        />
        <MetricCard
          title="Total Admins"
          value={adminCount !== null ? formatNumber(adminCount) : "—"}
          change={null}
          icon={Activity}
          iconBg="bg-orange-500"
        />
        <MetricCard
          title="Platform Status"
          value="Development"
          change={null}
          icon={CreditCard}
          iconBg="bg-green-500"
        />
      </div>

      {/* Charts Row */}
      {/* <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"> */}
      {/* Transaction Trends */}
      {/* <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
          <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5" style={{color: 'var(--tenant-primary-color,#004F71)'}} />
            Transaction Trends
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={transactionData}>
              <defs>
                <linearGradient
                  id="colorTransactions"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="5%" stopColor="var(--tenant-primary-color,#004F71)" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="var(--tenant-primary-color,#004F71)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="transactions"
                stroke="var(--tenant-primary-color,#004F71)"
                fillOpacity={1}
                fill="url(#colorTransactions)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div> */}

      {/* Revenue by Month */}
      {/* <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
          <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Banknote className="w-5 h-5 text-green-600" />
            Revenue Overview
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={transactionData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Bar dataKey="revenue" fill="#10B981" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div> */}

      {/* Transaction Types & Top Agents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transaction Distribution */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
          <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-purple-600" />
            Transaction Types
          </h3>
          {transactionTypes.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={transactionTypes}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {transactionTypes.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              <div className="text-center">
                <CreditCard className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No transaction data</p>
              </div>
            </div>
          )}
        </div>

        {/* Live Agents */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 lg:col-span-2 hover:shadow-xl transition-shadow">
          <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Users className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
            Recent Agents
          </h3>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 text-white opacity-70 animate-spin" />
            </div>
          ) : liveAgents.length > 0 ? (
            <div className="space-y-3">
              {liveAgents.map((agent, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl border border-gray-100 hover:border-[rgba(0,79,113,0.2)] hover:shadow-md transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-700 text-white rounded-full flex items-center justify-center font-bold shadow-md">
                      {(agent.name ?? "?")[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{agent.name}</p>
                      <p className="text-sm text-gray-500 capitalize">
                        {agent.agent_role}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium capitalize ${
                      agent.status === "active"
                        ? "bg-green-100 text-green-700"
                        : agent.status === "suspended"
                          ? "bg-red-100 text-red-700"
                          : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {agent.status ?? "pending"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No agents found.</p>
          )}
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden hover:shadow-xl transition-shadow">
        <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-blue-50">
          <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
            Recent Transactions
          </h3>
        </div>
        {loading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 text-white opacity-70 animate-spin mx-auto mb-2" />
            <p className="text-gray-500">Loading transactions...</p>
          </div>
        ) : recentTransactions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Transaction ID
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {recentTransactions.map((txn, index) => {
                  const type =
                    txn.payer === "MINT_ACCOUNT"
                      ? "deposit"
                      : txn.payee === "MINT_ACCOUNT"
                        ? "withdrawal"
                        : "transfer";

                  return (
                    <tr
                      key={txn.id || index}
                      className="hover:bg-[rgba(0,79,113,0.05)] transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-[rgba(0,79,113,0.08)] flex items-center justify-center text-[rgba(0,79,113,1)]">
                            <Activity className="w-4 h-4" />
                          </div>
                          <div>
                            <p className="text-sm font-mono font-semibold text-gray-900">
                              {txn.transaction_id || txn.id || "N/A"}
                            </p>
                            <p className="text-xs text-gray-500">
                              {txn.note || "-"}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 capitalize">
                        {type}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                        {txn.currency} {parseFloat(txn.amount).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full capitalize ${getStatusColor(
                            txn.status,
                          )}`}
                        >
                          {txn.status || "N/A"}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {new Date(
                          txn.created_at.replace(" ", "T"),
                        ).toLocaleString("en-NG", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">
            <Activity className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="font-medium">No transactions found</p>
            <p className="text-sm mt-1">
              Transactions will appear here once agents start processing
              payments.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

// Metric Card Component
interface MetricCardProps {
  title: string;
  value: string;
  change: number | null;
  icon: React.ComponentType<{ className?: string }>;
  iconBg: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  icon: Icon,
  iconBg,
}) => {
  const isPositive = change !== null && change >= 0;

  return (
    <div className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 p-6 border border-gray-100 hover:border-[rgba(0,79,113,0.2)] transform hover:-translate-y-1">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            {title}
          </p>
          <p className="text-3xl font-bold text-gray-900 mt-3 mb-4">{value}</p>
          {change !== null && (
            <div
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ${
                isPositive
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {isPositive ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
              <span>{Math.abs(change)}%</span>
            </div>
          )}
        </div>
        {/* <div className={`${iconBg} p-4 rounded-2xl shadow-md`}>
          <Icon className="w-7 h-7 text-white" />
        </div> */}
      </div>
    </div>
  );
};

export default Dashboard;
