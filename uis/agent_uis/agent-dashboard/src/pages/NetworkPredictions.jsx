import {
    Activity,
    AlertTriangle,
    CheckCircle,
    Filter,
    RefreshCw,
    TrendingDown,
    TrendingUp,
    Wifi,
    WifiOff,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { networkOperationsApi } from "../utils/api";

const NetworkPredictions = () => {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");

  useEffect(() => {
    loadPredictions();
  }, [typeFilter, channelFilter]);

  const loadPredictions = async () => {
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

  const getSuccessColor = (rate) => {
    if (rate >= 90) return "bg-green-100 text-green-800 border-green-200";
    if (rate >= 75) return "bg-yellow-100 text-yellow-800 border-yellow-200";
    if (rate >= 50) return "bg-orange-100 text-orange-800 border-orange-200";
    return "bg-red-100 text-red-800 border-red-200";
  };

  const getSuccessIcon = (rate) => {
    if (rate >= 90) return <CheckCircle className="w-5 h-5 text-green-600" />;
    if (rate >= 75) return <TrendingUp className="w-5 h-5 text-yellow-600" />;
    if (rate >= 50) return <TrendingDown className="w-5 h-5 text-orange-600" />;
    return <AlertTriangle className="w-5 h-5 text-red-600" />;
  };

  const getConfidenceBadge = (confidence) => {
    const colors = {
      high: "bg-blue-100 text-blue-800",
      medium: "bg-gray-100 text-gray-800",
      low: "bg-gray-50 text-gray-600",
    };
    return colors[confidence] || colors.low;
  };

  const formatTransactionType = (type) => {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const formatMediumName = (name) => {
    return name
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const groupByType = () => {
    const grouped = {};
    predictions.forEach((pred) => {
      if (!grouped[pred.type]) {
        grouped[pred.type] = [];
      }
      grouped[pred.type].push(pred);
    });
    return grouped;
  };

  const groupedPredictions = groupByType();

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Wifi className="w-8 h-8 text-blue-600" />
              Network Predictions
            </h1>
            <p className="text-gray-600 mt-2">
              Real-time success rate predictions for banking and telecom
              transactions
            </p>
          </div>
          <button
            onClick={loadPredictions}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-4 bg-white p-4 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">Filters:</span>
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Types</option>
            <option value="transfer">Transfer</option>
            <option value="withdrawal">Withdrawal</option>
            <option value="airtime">Airtime</option>
            <option value="data">Data</option>
            <option value="bill_payment">Bill Payment</option>
            <option value="balance_inquiry">Balance Inquiry</option>
          </select>

          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Channels</option>
            <option value="pos">POS Terminal</option>
            <option value="ussd">USSD</option>
            <option value="web">Web Portal</option>
            <option value="app">Mobile App</option>
          </select>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-12">
          <Activity className="w-8 h-8 text-blue-600 animate-spin" />
        </div>
      )}

      {/* Empty State */}
      {!loading && predictions.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <WifiOff className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No Predictions Available
          </h3>
          <p className="text-gray-600">
            No data available for the selected filters. Try adjusting your
            filters.
          </p>
        </div>
      )}

      {/* Predictions by Type */}
      {!loading && predictions.length > 0 && (
        <div className="space-y-6">
          {Object.entries(groupedPredictions).map(([type, typePredictions]) => (
            <div
              key={type}
              className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden"
            >
              <div className="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-4 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900">
                  {formatTransactionType(type)}
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                  {typePredictions.length} provider
                  {typePredictions.length !== 1 ? "s" : ""} available
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
                {typePredictions
                  .sort((a, b) => b.rate - a.rate)
                  .map((prediction, idx) => (
                    <div
                      key={idx}
                      className={`border-2 rounded-lg p-4 transition-all hover:shadow-md ${getSuccessColor(prediction.rate)}`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-semibold text-lg">
                            {formatMediumName(prediction.name)}
                          </h3>
                          <p className="text-xs uppercase tracking-wide mt-1 opacity-75">
                            {prediction.channel}
                          </p>
                        </div>
                        {getSuccessIcon(prediction.rate)}
                      </div>

                      <div className="mb-3">
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-bold">
                            {prediction.status}
                          </span>
                          <span className="text-sm opacity-75">
                            success rate
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        <span className="opacity-75">
                          {prediction.total_txns} transactions
                        </span>
                        <span
                          className={`px-2 py-1 rounded-full ${getConfidenceBadge(prediction.confidence)}`}
                        >
                          {prediction.confidence} confidence
                        </span>
                      </div>

                      {/* Progress Bar */}
                      <div className="mt-3 bg-white bg-opacity-50 rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full bg-current transition-all duration-300"
                          style={{ width: `${prediction.rate}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      {!loading && predictions.length > 0 && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-sm text-gray-600 mb-1">Total Providers</div>
            <div className="text-2xl font-bold text-gray-900">
              {predictions.length}
            </div>
          </div>
          <div className="bg-green-50 p-4 rounded-lg shadow-sm border border-green-200">
            <div className="text-sm text-green-800 mb-1">
              High Success (&gt;90%)
            </div>
            <div className="text-2xl font-bold text-green-900">
              {predictions.filter((p) => p.rate >= 90).length}
            </div>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg shadow-sm border border-yellow-200">
            <div className="text-sm text-yellow-800 mb-1">Medium (75-89%)</div>
            <div className="text-2xl font-bold text-yellow-900">
              {predictions.filter((p) => p.rate >= 75 && p.rate < 90).length}
            </div>
          </div>
          <div className="bg-red-50 p-4 rounded-lg shadow-sm border border-red-200">
            <div className="text-sm text-red-800 mb-1">Low (&lt;75%)</div>
            <div className="text-2xl font-bold text-red-900">
              {predictions.filter((p) => p.rate < 75).length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NetworkPredictions;
