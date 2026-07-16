import {
  BarChart3,
  CheckCircle,
  RefreshCw,
  Star,
  TrendingUp,
  Trophy,
  Wallet,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { gamificationApi, loyaltyApi } from "../utils/api";

const fmt = (n, cur = "NGN") =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: cur,
    maximumFractionDigits: 0,
  }).format(n || 0);

export default function Performance() {
  const agentId = localStorage.getItem("agentId") || localStorage.getItem("keycloakId");

  const [metrics, setMetrics] = useState(null);
  const [loyalty, setLoyalty] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState(30);

  const loadData = async () => {
    if (!agentId) {
      setError("Agent ID not found. Please log in again.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [perfData, loyaltyData] = await Promise.allSettled([
        gamificationApi.getPerformanceMetrics(agentId, period),
        loyaltyApi.getAccount(agentId),
      ]);
      if (perfData.status === "fulfilled") setMetrics(perfData.value);
      if (loyaltyData.status === "fulfilled") setLoyalty(loyaltyData.value);
    } catch (e) {
      setError(e?.message ?? "Failed to load performance data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [period]);

  const TIER_COLORS = {
    bronze: "text-orange-600 bg-orange-50 border-orange-200",
    silver: "text-gray-600 bg-gray-50 border-gray-200",
    gold: "text-yellow-600 bg-yellow-50 border-yellow-200",
    platinum: "text-cyan-600 bg-cyan-50 border-cyan-200",
    diamond: "text-purple-600 bg-purple-50 border-purple-200",
  };

  const tier = loyalty?.tier ?? loyalty?.tier_name ?? "bronze";
  const tierClass = TIER_COLORS[tier] ?? TIER_COLORS.bronze;

  const statCards = [
    {
      label: "Transaction Volume",
      value: fmt(metrics?.total_volume ?? metrics?.volume ?? 0),
      icon: Wallet,
      color: "text-blue-600 bg-blue-50",
    },
    {
      label: "Total Transactions",
      value: (metrics?.total_transactions ?? metrics?.tx_count ?? 0).toLocaleString(),
      icon: BarChart3,
      color: "text-green-600 bg-green-50",
    },
    {
      label: "Commission Earned",
      value: fmt(metrics?.total_commission ?? metrics?.commission ?? 0),
      icon: TrendingUp,
      color: "text-emerald-600 bg-emerald-50",
    },
    {
      label: "Success Rate",
      value: `${metrics?.success_rate ?? 0}%`,
      icon: CheckCircle,
      color: "text-purple-600 bg-purple-50",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-600" /> My Performance
          </h1>
          <p className="text-gray-500 text-sm mt-1">Track your transaction metrics and performance</p>
        </div>
        <div className="flex gap-2">
          {[
            { label: "7D", value: 7 },
            { label: "30D", value: 30 },
            { label: "90D", value: 90 },
          ].map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                period === p.value
                  ? "bg-blue-600 text-white"
                  : "border border-gray-300 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {p.label}
            </button>
          ))}
          <button
            onClick={loadData}
            className="flex items-center gap-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {/* Loyalty Tier Card */}
      {!loading && loyalty && (
        <div className={`border rounded-xl p-5 flex items-center gap-4 ${tierClass}`}>
          <Trophy className="w-8 h-8" />
          <div>
            <p className="font-bold text-lg capitalize">{tier} Tier</p>
            <p className="text-sm">
              {(loyalty.points ?? loyalty.total_points ?? 0).toLocaleString()} points
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-sm font-medium">Loyalty Account</p>
            {loyalty.points_to_next_tier && (
              <p className="text-xs mt-0.5">
                {loyalty.points_to_next_tier.toLocaleString()} pts to next tier
              </p>
            )}
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className={`w-10 h-10 rounded-lg ${s.color} flex items-center justify-center mb-3`}>
              <s.icon className="w-5 h-5" />
            </div>
            {loading ? (
              <div className="h-7 bg-gray-200 rounded animate-pulse mb-1" />
            ) : (
              <p className="text-xl font-bold text-gray-900">{s.value}</p>
            )}
            <p className="text-sm text-gray-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Detailed Metrics */}
      {!loading && metrics && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Detailed Metrics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { label: "Average Transaction Value", value: fmt(metrics.avg_transaction_value ?? 0) },
              { label: "Failed Transactions", value: (metrics.failed_transactions ?? 0).toLocaleString() },
              { label: "Pending Settlements", value: fmt(metrics.pending_settlement ?? 0) },
              { label: "Settled Amount", value: fmt(metrics.settled_amount ?? 0) },
              { label: "Customers Served", value: (metrics.unique_customers ?? 0).toLocaleString() },
              { label: "Rating", value: metrics.rating ? `${metrics.rating}/5.0` : "N/A" },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <span className="text-sm text-gray-600">{label}</span>
                <span className="font-medium text-gray-900">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rating */}
      {!loading && metrics?.rating && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Customer Rating</h2>
          <div className="flex items-center gap-3">
            <div className="flex">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star
                  key={i}
                  className={`w-6 h-6 ${i < Math.floor(metrics.rating) ? "text-yellow-500 fill-yellow-500" : "text-gray-300"}`}
                />
              ))}
            </div>
            <span className="text-2xl font-bold text-gray-900">{metrics.rating}</span>
            <span className="text-gray-500">/ 5.0</span>
          </div>
        </div>
      )}

      {!loading && !metrics && (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3" />
          <p>No performance data available for the selected period</p>
        </div>
      )}
    </div>
  );
}
