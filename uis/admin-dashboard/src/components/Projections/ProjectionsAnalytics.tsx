import {
  Banknote,
    BarChart3,
    Calendar,
    Package,
    Store,
    Target,
    TrendingUp,
    Users,
} from "lucide-react";
import React, { useState } from "react";

const ProjectionsAnalytics = () => {
  const [selectedPeriod, setSelectedPeriod] = useState("monthly");
  const [selectedMetric, setSelectedMetric] = useState("revenue");

  const overallStats = [
    {
      label: "Projected Revenue (This Month)",
      value: "₦125M",
      change: "+15%",
      icon: Banknote,
      color: "green",
    },
    {
      label: "Active Agents",
      value: "1,245",
      change: "+8%",
      icon: Users,
      color: "blue",
    },
    {
      label: "Active Stores",
      value: "3,567",
      change: "+12%",
      icon: Store,
      color: "purple",
    },
    {
      label: "Total Transactions",
      value: "45,890",
      change: "+22%",
      icon: Package,
      color: "orange",
    },
  ];

  const monthlyProjections = [
    { month: "Jan", actual: 95000000, projected: 100000000, target: 95000000 },
    {
      month: "Feb",
      actual: 108000000,
      projected: 125000000,
      target: 110000000,
    },
    { month: "Mar", actual: 0, projected: 135000000, target: 120000000 },
    { month: "Apr", actual: 0, projected: 145000000, target: 130000000 },
    { month: "May", actual: 0, projected: 155000000, target: 140000000 },
    { month: "Jun", actual: 0, projected: 165000000, target: 150000000 },
  ];

  const topPerformingRegions = [
    { region: "Lagos - Ikeja", revenue: 45000000, growth: 25, agents: 250 },
    { region: "Lagos - Lekki", revenue: 38000000, growth: 20, agents: 180 },
    { region: "Lagos - VI", revenue: 32000000, growth: 18, agents: 150 },
    { region: "Abuja - Central", revenue: 28000000, growth: 15, agents: 120 },
  ];

  const performanceTargets = [
    {
      category: "Monthly Revenue",
      current: 108000000,
      target: 110000000,
      achievement: 98,
    },
    {
      category: "Agent Acquisition",
      current: 1245,
      target: 1500,
      achievement: 83,
    },
    {
      category: "Transaction Volume",
      current: 45890,
      target: 50000,
      achievement: 92,
    },
    {
      category: "Customer Retention",
      current: 94,
      target: 95,
      achievement: 99,
    },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Projections & Analytics
          </h1>
          <p className="text-gray-600 mt-1">
            Platform-wide forecasting and performance tracking
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
          >
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="annually">Annually</option>
          </select>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {overallStats.map((stat, index) => {
          const IconComponent = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-600">{stat.label}</p>
                <div className={`p-2 bg-${stat.color}-100 rounded-lg`}>
                  <IconComponent className={`h-5 w-5 text-${stat.color}-600`} />
                </div>
              </div>
              <p className={`text-2xl font-bold text-${stat.color}-600`}>
                {stat.value}
              </p>
              <p className="text-sm text-green-600 font-medium mt-1">
                {stat.change} from last period
              </p>
            </div>
          );
        })}
      </div>

      {/* Revenue Projection Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">
            6-Month Revenue Projection
          </h2>
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center">
              <div className="w-4 h-4 bg-[rgba(0,79,113,0.05)]0 rounded mr-2"></div>
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
        <div className="h-64 flex items-end justify-around border-b border-l border-gray-300 p-4">
          {monthlyProjections.map((month, index) => (
            <div
              key={index}
              className="flex-1 flex flex-col items-center space-y-2"
            >
              <div className="w-full flex justify-center items-end space-x-1 h-48">
                {month.actual > 0 && (
                  <div
                    className="w-8 bg-[rgba(0,79,113,0.05)]0 rounded-t"
                    style={{ height: `${(month.actual / 200000000) * 100}%` }}
                    title={`Actual: ₦${(month.actual / 1000000).toFixed(0)}M`}
                  ></div>
                )}
                <div
                  className="w-8 bg-green-400 rounded-t"
                  style={{ height: `${(month.projected / 200000000) * 100}%` }}
                  title={`Projected: ₦${(month.projected / 1000000).toFixed(0)}M`}
                ></div>
                <div
                  className="w-8 bg-gray-300 rounded-t"
                  style={{ height: `${(month.target / 200000000) * 100}%` }}
                  title={`Target: ₦${(month.target / 1000000).toFixed(0)}M`}
                ></div>
              </div>
              <span className="text-sm font-medium text-gray-700">
                {month.month}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Performing Regions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <TrendingUp className="h-5 w-5 mr-2 text-green-600" />
            Top Performing Regions
          </h2>
          <div className="space-y-4">
            {topPerformingRegions.map((region, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-4">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white ${
                      index === 0
                        ? "bg-yellow-500"
                        : index === 1
                          ? "bg-gray-400"
                          : index === 2
                            ? "bg-orange-600"
                            : "bg-[var(--tenant-primary-color,#004F71)]"
                    }`}
                  >
                    {index + 1}
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{region.region}</p>
                    <p className="text-sm text-gray-500">
                      {region.agents} agents
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-green-600">
                    ₦{(region.revenue / 1000000).toFixed(1)}M
                  </p>
                  <p className="text-sm text-green-600">
                    +{region.growth}% growth
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Performance Targets */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Target className="h-5 w-5 mr-2 text-[var(--tenant-primary-color,#004F71)]" />
            Performance vs. Targets
          </h2>
          <div className="space-y-4">
            {performanceTargets.map((item, index) => (
              <div key={index}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {item.category}
                  </span>
                  <span
                    className={`text-sm font-bold ${
                      item.achievement >= 100
                        ? "text-green-600"
                        : item.achievement >= 80
                          ? "text-[var(--tenant-primary-color,#004F71)]"
                          : "text-yellow-600"
                    }`}
                  >
                    {item.achievement}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      item.achievement >= 100
                        ? "bg-green-500"
                        : item.achievement >= 80
                          ? "bg-[rgba(0,79,113,0.05)]0"
                          : "bg-yellow-500"
                    }`}
                    style={{ width: `${Math.min(item.achievement, 100)}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>
                    Current:{" "}
                    {typeof item.current === "number" && item.current > 1000
                      ? item.current.toLocaleString()
                      : item.current}
                  </span>
                  <span>
                    Target:{" "}
                    {typeof item.target === "number" && item.target > 1000
                      ? item.target.toLocaleString()
                      : item.target}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Forecast Summary */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-lg shadow p-6 text-white">
        <h2 className="text-xl font-bold mb-4">Next Quarter Forecast</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="text-white opacity-90 text-sm mb-1">Projected Revenue</p>
            <p className="text-3xl font-bold">₦445M</p>
            <p className="text-sm text-white opacity-80 mt-1">+18% growth expected</p>
          </div>
          <div>
            <p className="text-white opacity-90 text-sm mb-1">New Agents</p>
            <p className="text-3xl font-bold">425</p>
            <p className="text-sm text-white opacity-80 mt-1">34% of target</p>
          </div>
          <div>
            <p className="text-white opacity-90 text-sm mb-1">Transaction Growth</p>
            <p className="text-3xl font-bold">+28%</p>
            <p className="text-sm text-white opacity-80 mt-1">Exceeding expectations</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProjectionsAnalytics;
