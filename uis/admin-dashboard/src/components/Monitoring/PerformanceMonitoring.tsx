import {
    Activity,
    AlertTriangle,
    CheckCircle,
    Database,
    RefreshCw,
    Server,
    TrendingUp,
    Zap,
} from "lucide-react";
import React, { useState } from "react";
import {
    Area,
    AreaChart,
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

const mockSystemMetrics = {
  cpuUsage: 45.2,
  memoryUsage: 62.5,
  diskUsage: 75.3,
  networkIn: 125.4,
  networkOut: 89.7,
  uptime: 99.98,
};

const mockCPUData = [
  { time: "00:00", usage: 35 },
  { time: "04:00", usage: 25 },
  { time: "08:00", usage: 55 },
  { time: "12:00", usage: 65 },
  { time: "16:00", usage: 52 },
  { time: "20:00", usage: 45 },
];

const mockMemoryData = [
  { time: "00:00", usage: 50 },
  { time: "04:00", usage: 48 },
  { time: "08:00", usage: 62 },
  { time: "12:00", usage: 70 },
  { time: "16:00", usage: 65 },
  { time: "20:00", usage: 62 },
];

const mockServices = [
  {
    name: "API Gateway",
    status: "healthy",
    uptime: 99.99,
    responseTime: 45,
    requests: 125000,
  },
  {
    name: "Database",
    status: "healthy",
    uptime: 99.95,
    responseTime: 12,
    requests: 89000,
  },
  {
    name: "Authentication",
    status: "healthy",
    uptime: 99.98,
    responseTime: 32,
    requests: 45000,
  },
  {
    name: "Payment Service",
    status: "degraded",
    uptime: 98.5,
    responseTime: 156,
    requests: 34000,
  },
  {
    name: "Notification Service",
    status: "healthy",
    uptime: 99.92,
    responseTime: 67,
    requests: 67000,
  },
  {
    name: "Analytics",
    status: "healthy",
    uptime: 99.85,
    responseTime: 89,
    requests: 23000,
  },
];

const mockAPIEndpoints = [
  {
    endpoint: "/api/v1/transactions",
    calls: 45000,
    avgTime: 45,
    errors: 12,
    status: "healthy",
  },
  {
    endpoint: "/api/v1/users",
    calls: 23000,
    avgTime: 32,
    errors: 5,
    status: "healthy",
  },
  {
    endpoint: "/api/v1/accounts",
    calls: 18000,
    avgTime: 38,
    errors: 8,
    status: "healthy",
  },
  {
    endpoint: "/api/v1/payments",
    calls: 34000,
    avgTime: 156,
    errors: 234,
    status: "degraded",
  },
  {
    endpoint: "/api/v1/reports",
    calls: 8000,
    avgTime: 189,
    errors: 3,
    status: "healthy",
  },
];

const PerformanceMonitoring: React.FC = () => {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1000);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-100 text-green-800";
      case "degraded":
        return "bg-yellow-100 text-yellow-800";
      case "critical":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "degraded":
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case "critical":
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      default:
        return <Activity className="w-5 h-5 text-gray-500" />;
    }
  };

  const getMetricColor = (value: number, threshold: number) => {
    if (value < threshold * 0.7) return "text-green-600";
    if (value < threshold * 0.9) return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Performance Monitoring
          </h1>
          <p className="text-gray-500 mt-1">
            Real-time system performance and health metrics
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw
            className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </div>

      {/* System Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">CPU Usage</p>
            <Activity className="w-5 h-5 text-[var(--tenant-primary-color,#002082)]" />
          </div>
          <p
            className={`text-2xl font-bold ${getMetricColor(mockSystemMetrics.cpuUsage, 100)}`}
          >
            {mockSystemMetrics.cpuUsage}%
          </p>
          <div className="mt-3 bg-gray-200 rounded-full h-2">
            <div
              className="bg-[var(--tenant-primary-color,#002082)] h-2 rounded-full"
              style={{ width: `${mockSystemMetrics.cpuUsage}%` }}
            ></div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Memory</p>
            <Database className="w-5 h-5 text-purple-500" />
          </div>
          <p
            className={`text-2xl font-bold ${getMetricColor(mockSystemMetrics.memoryUsage, 100)}`}
          >
            {mockSystemMetrics.memoryUsage}%
          </p>
          <div className="mt-3 bg-gray-200 rounded-full h-2">
            <div
              className="bg-purple-600 h-2 rounded-full"
              style={{ width: `${mockSystemMetrics.memoryUsage}%` }}
            ></div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Disk Usage</p>
            <Server className="w-5 h-5 text-orange-500" />
          </div>
          <p
            className={`text-2xl font-bold ${getMetricColor(mockSystemMetrics.diskUsage, 100)}`}
          >
            {mockSystemMetrics.diskUsage}%
          </p>
          <div className="mt-3 bg-gray-200 rounded-full h-2">
            <div
              className="bg-orange-600 h-2 rounded-full"
              style={{ width: `${mockSystemMetrics.diskUsage}%` }}
            ></div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Network In</p>
            <TrendingUp className="w-5 h-5 text-green-500" />
          </div>
          <p className="text-2xl font-bold text-green-600">
            {mockSystemMetrics.networkIn}
          </p>
          <p className="text-xs text-gray-500 mt-1">MB/s</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Network Out</p>
            <TrendingUp className="w-5 h-5 text-[var(--tenant-primary-color,#002082)]" />
          </div>
          <p className="text-2xl font-bold text-[var(--tenant-primary-color,#002082)]">
            {mockSystemMetrics.networkOut}
          </p>
          <p className="text-xs text-gray-500 mt-1">MB/s</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Uptime</p>
            <Zap className="w-5 h-5 text-yellow-500" />
          </div>
          <p className="text-2xl font-bold text-green-600">
            {mockSystemMetrics.uptime}%
          </p>
          <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
        </div>
      </div>

      {/* Performance Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            CPU Usage (24 Hours)
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={mockCPUData}>
              <defs>
                <linearGradient id="colorCPU" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--tenant-primary-color,#002082)" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="var(--tenant-primary-color,#002082)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="usage"
                stroke="var(--tenant-primary-color,#002082)"
                fillOpacity={1}
                fill="url(#colorCPU)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Memory Usage (24 Hours)
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={mockMemoryData}>
              <defs>
                <linearGradient id="colorMemory" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="usage"
                stroke="#8B5CF6"
                fillOpacity={1}
                fill="url(#colorMemory)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Service Status */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Service Health
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Service
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Uptime
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Response Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Requests
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {mockServices.map((service, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(service.status)}
                      <span className="ml-3 text-sm font-medium text-gray-900">
                        {service.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(service.status)}`}
                    >
                      {service.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {service.uptime}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {service.responseTime}ms
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {service.requests.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* API Endpoints Performance */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            API Endpoints Performance
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Endpoint
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Calls
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Avg Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Errors
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {mockAPIEndpoints.map((endpoint, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                    {endpoint.endpoint}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {endpoint.calls.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {endpoint.avgTime}ms
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600">
                    {endpoint.errors}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(endpoint.status)}`}
                    >
                      {endpoint.status}
                    </span>
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

export default PerformanceMonitoring;
