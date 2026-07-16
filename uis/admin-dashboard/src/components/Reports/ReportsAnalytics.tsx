import {
    Activity,
    Banknote,
    BarChart3,
    Calendar,
    Download,
    FileText,
    Filter,
    TrendingUp,
    Users,
} from "lucide-react";
import React, { useState } from "react";
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

const mockRevenueData = [
  { month: "Jan", revenue: 245000, transactions: 1200, fees: 12000 },
  { month: "Feb", revenue: 198000, transactions: 980, fees: 9800 },
  { month: "Mar", revenue: 380000, transactions: 1850, fees: 18500 },
  { month: "Apr", revenue: 308000, transactions: 1520, fees: 15200 },
  { month: "May", revenue: 450000, transactions: 2200, fees: 22000 },
  { month: "Jun", revenue: 420000, transactions: 2050, fees: 20500 },
];

const mockUserGrowth = [
  { month: "Jan", newUsers: 120, activeUsers: 2400, churnedUsers: 14 },
  { month: "Feb", newUsers: 95, activeUsers: 2481, churnedUsers: 8 },
  { month: "Mar", newUsers: 180, activeUsers: 2653, churnedUsers: 12 },
  { month: "Apr", newUsers: 145, activeUsers: 2786, churnedUsers: 9 },
  { month: "May", newUsers: 210, activeUsers: 2987, churnedUsers: 11 },
  { month: "Jun", newUsers: 189, activeUsers: 3165, churnedUsers: 7 },
];

const mockRegionalData = [
  { region: "Lagos", value: 35, amount: 1750000, color: "var(--tenant-primary-color,#004F71)" },
  { region: "Abuja", value: 25, amount: 1250000, color: "#10B981" },
  { region: "Port Harcourt", value: 20, amount: 1000000, color: "#F59E0B" },
  { region: "Kano", value: 12, amount: 600000, color: "#EF4444" },
  { region: "Others", value: 8, amount: 400000, color: "#8B5CF6" },
];

const mockTransactionTypes = [
  { type: "Transfers", count: 4500, percentage: 45, revenue: 2250000 },
  { type: "Withdrawals", count: 2500, percentage: 25, revenue: 1250000 },
  { type: "Deposits", count: 2000, percentage: 20, revenue: 1000000 },
  { type: "Bill Payments", count: 1000, percentage: 10, revenue: 500000 },
];

const mockTopCustomers = [
  {
    name: "John Doe",
    transactions: 234,
    revenue: 456000,
    lastTransaction: "2 hours ago",
  },
  {
    name: "Jane Smith",
    transactions: 189,
    revenue: 378000,
    lastTransaction: "5 hours ago",
  },
  {
    name: "Bob Johnson",
    transactions: 156,
    revenue: 312000,
    lastTransaction: "1 day ago",
  },
  {
    name: "Alice Brown",
    transactions: 145,
    revenue: 290000,
    lastTransaction: "2 days ago",
  },
  {
    name: "Charlie Wilson",
    transactions: 132,
    revenue: 264000,
    lastTransaction: "3 days ago",
  },
];

const ReportsAnalytics: React.FC = () => {
  const [reportType, setReportType] = useState("revenue");
  const [timeRange, setTimeRange] = useState("6months");

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
      minimumFractionDigits: 0,
    }).format(value);
  };

  const totalRevenue = mockRevenueData.reduce(
    (sum, item) => sum + item.revenue,
    0,
  );
  const totalTransactions = mockRevenueData.reduce(
    (sum, item) => sum + item.transactions,
    0,
  );
  const totalFees = mockRevenueData.reduce((sum, item) => sum + item.fees, 0);
  const totalUsers = mockUserGrowth[mockUserGrowth.length - 1].activeUsers;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Reports & Analytics
          </h1>
          <p className="text-gray-500 mt-1">
            Comprehensive business insights and performance metrics
          </p>
        </div>
        <div className="flex gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
          >
            <option value="30days">Last 30 Days</option>
            <option value="3months">Last 3 Months</option>
            <option value="6months">Last 6 Months</option>
            <option value="year">Last Year</option>
          </select>
          <button className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export Report
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white opacity-90 text-sm">Total Revenue</p>
              <p className="text-3xl font-bold mt-2">
                {formatCurrency(totalRevenue)}
              </p>
              <p className="text-white opacity-90 text-xs mt-2">
                ↑ 15.3% from last period
              </p>
            </div>
            <Banknote className="w-12 h-12 text-white opacity-80" />
          </div>
        </div>
        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg shadow p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">Total Transactions</p>
              <p className="text-3xl font-bold mt-2">
                {totalTransactions.toLocaleString()}
              </p>
              <p className="text-green-100 text-xs mt-2">
                ↑ 8.7% from last period
              </p>
            </div>
            <Activity className="w-12 h-12 text-green-200" />
          </div>
        </div>
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg shadow p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">Active Users</p>
              <p className="text-3xl font-bold mt-2">
                {totalUsers.toLocaleString()}
              </p>
              <p className="text-purple-100 text-xs mt-2">
                ↑ 12.4% from last period
              </p>
            </div>
            <Users className="w-12 h-12 text-purple-200" />
          </div>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg shadow p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-orange-100 text-sm">Total Fees</p>
              <p className="text-3xl font-bold mt-2">
                {formatCurrency(totalFees)}
              </p>
              <p className="text-orange-100 text-xs mt-2">
                ↑ 10.2% from last period
              </p>
            </div>
            <TrendingUp className="w-12 h-12 text-orange-200" />
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Revenue Trend
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={mockRevenueData}>
              <defs>
                <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--tenant-primary-color,#004F71)" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="var(--tenant-primary-color,#004F71)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="var(--tenant-primary-color,#004F71)"
                fillOpacity={1}
                fill="url(#colorRevenue)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* User Growth */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            User Growth
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={mockUserGrowth}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="newUsers"
                stroke="#10B981"
                strokeWidth={2}
                name="New Users"
              />
              <Line
                type="monotone"
                dataKey="activeUsers"
                stroke="var(--tenant-primary-color,#004F71)"
                strokeWidth={2}
                name="Active Users"
              />
              <Line
                type="monotone"
                dataKey="churnedUsers"
                stroke="#EF4444"
                strokeWidth={2}
                name="Churned"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Regional Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Regional Distribution
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={mockRegionalData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ region, value }) => `${region} ${value}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {mockRegionalData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name, props) => [
                  formatCurrency(props.payload.amount),
                  name,
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Transaction Types */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Transaction Types
          </h3>
          <div className="space-y-4">
            {mockTransactionTypes.map((item, index) => (
              <div key={index} className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">
                    {item.type}
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {formatCurrency(item.revenue)}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-[var(--tenant-primary-color,#004F71)] h-2 rounded-full"
                      style={{ width: `${item.percentage}%` }}
                    ></div>
                  </div>
                  <span className="text-xs text-gray-500 w-12 text-right">
                    {item.percentage}%
                  </span>
                </div>
                <p className="text-xs text-gray-500">
                  {item.count.toLocaleString()} transactions
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Customers */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Top Customers</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Rank
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Customer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Transactions
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Revenue
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Last Transaction
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {mockTopCustomers.map((customer, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                      {index + 1}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {customer.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {customer.transactions.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm font-semibold text-gray-900">
                    {formatCurrency(customer.revenue)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {customer.lastTransaction}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ReportsAnalytics;
