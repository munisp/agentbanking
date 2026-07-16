import {
    Activity,
    AlertCircle,
    AlertTriangle,
    CheckCircle,
    DollarSign,
    Filter,
    RefreshCw,
    TrendingDown,
    TrendingUp,
    Wifi,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api } from "../../utils/api";

interface PredictionRecord {
  name: string;
  type: string;
  channel: string;
  rate: number;
  status: string;
  total_txns: number;
  confidence: string;
}

const NetworkStatusMonitor: React.FC = () => {
  const [predictions, setPredictions] = useState<PredictionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");

  useEffect(() => {
    loadData();
  }, [typeFilter, channelFilter]);

  const loadData = async () => {
    setLoading(true);
    try {
      const filters: { type?: string; channel?: string } = {};
      if (typeFilter !== "all") filters.type = typeFilter;
      if (channelFilter !== "all") filters.channel = channelFilter;

      const response = await api.getNetworkPredictions(filters);
      setPredictions(response?.predictions || []);
    } catch (err) {
      console.error("Failed to load predictions:", err);
      setPredictions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadData();
  };

  const getSuccessColor = (rate: number) => {
    if (rate >= 90) return "text-green-600 bg-green-50";
    if (rate >= 75) return "text-yellow-600 bg-yellow-50";
    if (rate >= 50) return "text-orange-600 bg-orange-50";
    return "text-red-600 bg-red-50";
  };

  const getSuccessIcon = (rate: number) => {
    if (rate >= 90) return <CheckCircle className="w-5 h-5" />;
    if (rate >= 75) return <TrendingUp className="w-5 h-5" />;
    if (rate >= 50) return <TrendingDown className="w-5 h-5" />;
    return <AlertTriangle className="w-5 h-5" />;
  };

  const formatType = (type: string) =>
    type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const formatMedium = (name: string) =>
    name
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const topPerformers = predictions
    .filter((prediction) => prediction.rate >= 90)
    .slice(0, 5);

  const averageSuccessRate =
    predictions.length > 0
      ? (
          predictions.reduce((sum, prediction) => sum + prediction.rate, 0) /
          predictions.length
        ).toFixed(1)
      : "0.0";

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
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
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

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
            {predictions.filter((prediction) => prediction.rate >= 90).length}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <AlertCircle className="w-8 h-8 text-red-600" />
            <span className="text-sm text-gray-500">Low Success</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {predictions.filter((prediction) => prediction.rate < 75).length}
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div className="flex gap-4 items-center">
          <Filter className="w-5 h-5 text-gray-500" />
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
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
            onChange={(event) => setChannelFilter(event.target.value)}
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

      {topPerformers.length > 0 && (
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-lg border border-green-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            Top Performing Channels (≥90% Success)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {topPerformers.map((prediction, index) => (
              <div
                key={`${prediction.name}-${prediction.channel}-${index}`}
                className="bg-white p-4 rounded-lg border border-green-200 shadow-sm"
              >
                <div className="font-semibold text-gray-900">
                  {formatMedium(prediction.name)}
                </div>
                <div className="text-xs text-gray-600 uppercase mt-1">
                  {prediction.channel} • {formatType(prediction.type)}
                </div>
                <div className="text-2xl font-bold text-green-600 mt-2">
                  {prediction.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
          <div className="overflow-x-auto max-h-[40vh] overflow-scroll">
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
                  .sort((left, right) => right.rate - left.rate)
                  .map((prediction, index) => (
                    <tr
                      key={`${prediction.name}-${prediction.channel}-${index}`}
                      className="hover:bg-gray-50"
                    >
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">
                          {formatMedium(prediction.name)}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatType(prediction.type)}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs uppercase font-medium text-gray-600 bg-gray-100 px-2 py-1 rounded">
                          {prediction.channel}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div
                          className={`inline-flex items-center gap-2 px-3 py-1 rounded-full font-semibold ${getSuccessColor(prediction.rate)}`}
                        >
                          {getSuccessIcon(prediction.rate)}
                          <span>{prediction.status}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {prediction.total_txns.toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            prediction.confidence === "high"
                              ? "bg-blue-100 text-blue-800"
                              : prediction.confidence === "medium"
                                ? "bg-gray-100 text-gray-800"
                                : "bg-gray-50 text-gray-600"
                          }`}
                        >
                          {prediction.confidence}
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

export default NetworkStatusMonitor;
