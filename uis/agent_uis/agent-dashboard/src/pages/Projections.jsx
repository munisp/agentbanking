import {
    BarChart3,
    Calendar,
    DollarSign,
    LineChart,
    Target,
    TrendingUp,
} from "lucide-react";
import React, { useState } from "react";

const Projections = () => {
  const [selectedPeriod, setSelectedPeriod] = useState("monthly");
  const [selectedBusiness, setSelectedBusiness] = useState("all");

  const businesses = [
    { id: "all", name: "All Businesses" },
    { id: "business1", name: "Tani Store - Ikeja" },
    { id: "business2", name: "Tani Mart - Lekki" },
    { id: "business3", name: "Tani Express - VI" },
    { id: "business4", name: "Tani Shop - Yaba" },
  ];

  const performanceMetrics = [
    {
      label: "Monthly Target",
      value: "₦5,000,000",
      achieved: 4850000,
      target: 5000000,
      percentage: 97,
    },
    {
      label: "Quarterly Target",
      value: "₦15,000,000",
      achieved: 12500000,
      target: 15000000,
      percentage: 83,
    },
    {
      label: "Annual Target",
      value: "₦60,000,000",
      achieved: 48000000,
      target: 60000000,
      percentage: 80,
    },
  ];

  const projectionData = {
    currentMonth: {
      actual: 4850000,
      projected: 5200000,
      target: 5000000,
    },
    nextMonth: {
      projected: 5500000,
      target: 5000000,
    },
    growth: 15,
  };

  const monthlyBreakdown = [
    { month: "Jan", actual: 4200000, projected: 4500000, target: 4500000 },
    { month: "Feb", actual: 4850000, projected: 5200000, target: 5000000 },
    { month: "Mar", actual: 0, projected: 5500000, target: 5000000 },
    { month: "Apr", actual: 0, projected: 5800000, target: 5500000 },
  ];

  const topPerformers = [
    {
      business: "Tani Store - Ikeja",
      revenue: 1850000,
      growth: 25,
      targetAchieved: 105,
    },
    {
      business: "Tani Express - VI",
      revenue: 1420000,
      growth: 18,
      targetAchieved: 98,
    },
    {
      business: "Tani Mart - Lekki",
      revenue: 1280000,
      growth: 12,
      targetAchieved: 92,
    },
    {
      business: "Tani Shop - Yaba",
      revenue: 300000,
      growth: 8,
      targetAchieved: 75,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Sales Projections & Targets
          </h1>
          <p className="text-gray-600 mt-1">
            Track performance and forecast future sales
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors">
          <Target className="h-5 w-5 mr-2" />
          Set New Target
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Period
            </label>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annually">Annually</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Business
            </label>
            <select
              value={selectedBusiness}
              onChange={(e) => setSelectedBusiness(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {performanceMetrics.map((metric, index) => (
          <div key={index} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600">{metric.label}</p>
              <Target className="h-5 w-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            </div>
            <p className="text-2xl font-bold text-gray-900 mb-2">
              {metric.value}
            </p>
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                className={`h-2 rounded-full ${
                  metric.percentage >= 100
                    ? "bg-green-500"
                    : metric.percentage >= 80
                      ? "bg-[var(--tenant-primary-color,#002082)]"
                      : "bg-yellow-500"
                }`}
                style={{ width: `${Math.min(metric.percentage, 100)}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>₦{(metric.achieved / 1000000).toFixed(1)}M achieved</span>
              <span
                className={
                  metric.percentage >= 100
                    ? "text-green-600 font-medium"
                    : metric.percentage >= 80
                      ? "font-medium"
                      : "text-yellow-600 font-medium"
                }
                style={
                  metric.percentage >= 80 && metric.percentage < 100
                    ? { color: "var(--tenant-primary-color,#002082)" }
                    : {}
                }
              >
                {metric.percentage}%
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Current vs Projected */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Month Analysis */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Current Month (February)
            </h2>
            <Calendar className="h-5 w-5 text-gray-400" />
          </div>
          <div className="space-y-4">
            <div
              className="flex justify-between items-center p-4 rounded-lg"
              style={{ backgroundColor: "rgba(0,79,113,0.05)" }}
            >
              <div>
                <p className="text-sm text-gray-600">Actual Revenue</p>
                <p className="text-xl font-bold" style={{ color: "var(--tenant-primary-color,#002082)" }}>
                  ₦{(projectionData.currentMonth.actual / 1000000).toFixed(2)}M
                </p>
              </div>
              <BarChart3 className="h-8 w-8" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            </div>
            <div className="flex justify-between items-center p-4 bg-green-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">
                  Projected (End of Month)
                </p>
                <p className="text-xl font-bold text-green-600">
                  ₦
                  {(projectionData.currentMonth.projected / 1000000).toFixed(2)}
                  M
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-600" />
            </div>
            <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Monthly Target</p>
                <p className="text-xl font-bold text-gray-900">
                  ₦{(projectionData.currentMonth.target / 1000000).toFixed(1)}M
                </p>
              </div>
              <Target className="h-8 w-8 text-gray-600" />
            </div>
          </div>
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">
                On track to exceed target by
              </span>
              <span className="text-lg font-bold text-green-600">+4%</span>
            </div>
          </div>
        </div>

        {/* Next Month Forecast */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Next Month (March)
            </h2>
            <LineChart className="h-5 w-5 text-gray-400" />
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-4 bg-purple-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Projected Revenue</p>
                <p className="text-xl font-bold text-purple-600">
                  ₦{(projectionData.nextMonth.projected / 1000000).toFixed(2)}M
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-purple-600" />
            </div>
            <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Target</p>
                <p className="text-xl font-bold text-gray-900">
                  ₦{(projectionData.nextMonth.target / 1000000).toFixed(1)}M
                </p>
              </div>
              <Target className="h-8 w-8 text-gray-600" />
            </div>
            <div className="flex justify-between items-center p-4 bg-green-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Expected Growth</p>
                <p className="text-xl font-bold text-green-600">
                  +{projectionData.growth}%
                </p>
              </div>
              <DollarSign className="h-8 w-8 text-green-600" />
            </div>
          </div>
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-sm text-gray-600 mb-2">
              Based on current trends and historical data
            </p>
            <div className="text-xs text-gray-500">
              Confidence Level:{" "}
              <span className="font-medium text-green-600">High (85%)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Business Performance Rankings */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Business Performance Rankings
          </h2>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {topPerformers.map((performer, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-4">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white ${
                      index === 0
                        ? "bg-yellow-500"
                        : index === 1
                          ? "bg-gray-400"
                          : index === 2
                            ? "bg-orange-600"
                            : "bg-[var(--tenant-primary-color,#002082)]"
                    }`}
                  >
                    {index + 1}
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">
                      {performer.business}
                    </p>
                    <p className="text-sm text-gray-500">
                      Revenue: ₦{performer.revenue.toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center space-x-4">
                    <div>
                      <p className="text-xs text-gray-500">Growth</p>
                      <p className="text-sm font-semibold text-green-600">
                        +{performer.growth}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Target</p>
                      <p
                        className={`text-sm font-semibold ${
                          performer.targetAchieved >= 100
                            ? "text-green-600"
                            : performer.targetAchieved >= 80
                              ? ""
                              : "text-yellow-600"
                        }`}
                        style={
                          performer.targetAchieved >= 80 &&
                          performer.targetAchieved < 100
                            ? { color: "var(--tenant-primary-color,#002082)" }
                            : {}
                        }
                      >
                        {performer.targetAchieved}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Monthly Trend Chart Placeholder */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          4-Month Trend Analysis
        </h2>
        <div className="h-64 flex items-end justify-around border-b border-l border-gray-300 p-4">
          {monthlyBreakdown.map((month, index) => (
            <div
              key={index}
              className="flex-1 flex flex-col items-center space-y-2"
            >
              <div className="w-full flex justify-center items-end space-x-1 h-48">
                {month.actual > 0 && (
                  <div
                    className="w-8 bg-blue-500 rounded-t"
                    style={{ height: `${(month.actual / 6000000) * 100}%` }}
                    title={`Actual: ₦${month.actual.toLocaleString()}`}
                  ></div>
                )}
                <div
                  className="w-8 bg-green-400 rounded-t"
                  style={{ height: `${(month.projected / 6000000) * 100}%` }}
                  title={`Projected: ₦${month.projected.toLocaleString()}`}
                ></div>
                <div
                  className="w-8 bg-gray-300 rounded-t"
                  style={{ height: `${(month.target / 6000000) * 100}%` }}
                  title={`Target: ₦${month.target.toLocaleString()}`}
                ></div>
              </div>
              <span className="text-sm font-medium text-gray-700">
                {month.month}
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-center space-x-6 mt-4 text-sm">
          <div className="flex items-center">
            <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
            <span className="text-gray-600">Actual</span>
          </div>
          <div className="flex items-center">
            <div className="w-4 h-4 bg-green-400 rounded mr-2"></div>
            <span className="text-gray-600">Projected</span>
          </div>
          <div className="flex items-center">
            <div className="w-4 h-4 bg-gray-300 rounded mr-2"></div>
            <span className="text-gray-600">Target</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Projections;
