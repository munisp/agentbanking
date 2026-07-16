import {
    Activity,
    AlertCircle,
    TrendingDown,
    TrendingUp,
    Wifi,
    WifiOff,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { networkStatusApi } from "../../utils/api";

const NetworkStatusMonitor = () => {
  const [networkStatus, setNetworkStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    loadNetworkStatus();

    if (autoRefresh) {
      const interval = setInterval(loadNetworkStatus, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const loadNetworkStatus = async () => {
    try {
      setLoading(true);
      const response = await networkStatusApi.getNetworkStatus();
      setNetworkStatus(response);
    } catch (error) {
      console.error("Failed to load network status:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (successRate) => {
    if (successRate >= 90) return "text-green-600";
    if (successRate >= 70) return "text-orange-600";
    return "text-red-600";
  };

  const getStatusBgColor = (successRate) => {
    if (successRate >= 90) return "bg-green-100 border-green-300";
    if (successRate >= 70) return "bg-orange-100 border-orange-300";
    return "bg-red-100 border-red-300";
  };

  const getStatusLabel = (successRate) => {
    if (successRate >= 90) return "Healthy";
    if (successRate >= 70) return "Degraded";
    return "Down";
  };

  const getStatusIcon = (successRate) => {
    if (successRate >= 90) return <Wifi className="w-6 h-6 text-green-600" />;
    if (successRate >= 70)
      return <AlertCircle className="w-6 h-6 text-orange-600" />;
    return <WifiOff className="w-6 h-6 text-red-600" />;
  };

  const getNetworkDisplayName = (networkType) => {
    const names = {
      mastercard: "Mastercard",
      visa: "Visa",
      verve: "Verve",
      transfer: "Bank Transfer",
      deposit: "Deposit",
      withdrawal: "Withdrawal",
    };
    return names[networkType] || networkType;
  };

  const getNetworkIcon = () => {
    return <Activity className="w-8 h-8" />;
  };

  if (loading && !networkStatus) {
    return (
      <div className="flex items-center justify-center min-h-100">
        <div className="text-center">
          <Activity className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading network status...</p>
        </div>
      </div>
    );
  }

  if (!networkStatus) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-600" />
        <p className="text-red-800">Failed to load network status</p>
        <button
          onClick={loadNetworkStatus}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const overallSuccessRate =
    networkStatus.networks.reduce((sum, n) => sum + n.success_rate, 0) /
    networkStatus.networks.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Network Status</h1>
          <p className="text-sm text-gray-500 mt-1">
            Last updated:{" "}
            {new Date(networkStatus.timestamp).toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-blue-600"
            />
            Auto-refresh
          </label>
          <button
            onClick={loadNetworkStatus}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Overall Health Card */}
      <div
        className={`rounded-lg border-2 p-6 ${getStatusBgColor(overallSuccessRate)}`}
      >
        <div className="flex items-center gap-4">
          {getStatusIcon(overallSuccessRate)}
          <div className="flex-1">
            <h2 className="text-2xl font-bold">Overall Network Health</h2>
            <p
              className={`text-3xl font-bold ${getStatusColor(overallSuccessRate)}`}
            >
              {overallSuccessRate.toFixed(1)}%
            </p>
          </div>
          <div
            className={`text-xl font-bold ${getStatusColor(overallSuccessRate)}`}
          >
            {getStatusLabel(overallSuccessRate)}
          </div>
        </div>
      </div>

      {/* Network Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {networkStatus.networks.map((network) => (
          <div
            key={network.network_type}
            className={`bg-white rounded-lg shadow-md border-2 overflow-hidden ${getStatusBgColor(network.success_rate)}`}
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  {getNetworkIcon(network.network_type)}
                  <div>
                    <h3 className="text-lg font-bold">
                      {getNetworkDisplayName(network.network_type)}
                    </h3>
                    <span
                      className={`text-sm font-semibold ${getStatusColor(network.success_rate)}`}
                    >
                      {getStatusLabel(network.success_rate)}
                    </span>
                  </div>
                </div>
                {getStatusIcon(network.success_rate)}
              </div>

              {/* Success Rate Circle */}
              <div className="flex items-center justify-center mb-4">
                <div className="relative">
                  <svg className="w-32 h-32 transform -rotate-90">
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      className="text-gray-300"
                    />
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      strokeDasharray={`${network.success_rate * 3.52} 352`}
                      className={getStatusColor(network.success_rate)}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <p
                        className={`text-2xl font-bold ${getStatusColor(network.success_rate)}`}
                      >
                        {network.success_rate.toFixed(1)}%
                      </p>
                      <p className="text-xs text-gray-600">Success Rate</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Transaction Stats */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">
                    Total Transactions
                  </span>
                  <span className="font-semibold">
                    {network.total_transactions}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Successful</span>
                  <span className="font-semibold text-green-600 flex items-center gap-1">
                    <TrendingUp className="w-4 h-4" />
                    {network.successful_transactions}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Failed</span>
                  <span className="font-semibold text-red-600 flex items-center gap-1">
                    <TrendingDown className="w-4 h-4" />
                    {network.failed_transactions}
                  </span>
                </div>
                {network.avg_response_time && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Avg Response</span>
                    <span className="font-semibold">
                      {network.avg_response_time}ms
                    </span>
                  </div>
                )}
              </div>

              {/* Failure Rate Bar */}
              <div className="mt-4">
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>Failure Rate</span>
                  <span>{(100 - network.success_rate).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      network.success_rate >= 90
                        ? "bg-green-600"
                        : network.success_rate >= 70
                          ? "bg-orange-600"
                          : "bg-red-600"
                    }`}
                    style={{ width: `${network.success_rate}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Last Updated Footer */}
            <div className="bg-gray-50 px-6 py-2 text-xs text-gray-500">
              Updated: {new Date(network.last_updated).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold mb-3">Status Legend</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-green-600 rounded"></div>
            <div>
              <p className="font-semibold text-green-800">Healthy</p>
              <p className="text-sm text-gray-600">≥90% success rate</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-orange-600 rounded"></div>
            <div>
              <p className="font-semibold text-orange-800">Degraded</p>
              <p className="text-sm text-gray-600">70-89% success rate</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-red-600 rounded"></div>
            <div>
              <p className="font-semibold text-red-800">Down</p>
              <p className="text-sm text-gray-600">&lt;70% success rate</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkStatusMonitor;
