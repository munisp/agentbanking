import { TrendingUp, Target, RefreshCw, BarChart3 } from "lucide-react";
import React, { useEffect, useState } from "react";
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../services/tenant";

const CORE_URL = import.meta.env.VITE_SUPPORT_COMMS_URL || import.meta.env.VITE_API_URL || "http://localhost:8011";

interface ForecastPoint { month: string; actual: number | null; forecast: number; }
interface SegmentForecast { segment: string; current: number; projected: number; growth: number; }
interface Scenario { name: string; revenue: number; description: string; color: string; }

const SCENARIOS: Scenario[] = [
  { name: "Pessimistic", revenue: 24_800_000, description: "10% agent churn, flat transaction growth", color: "text-red-600 bg-red-50 border-red-200" },
  { name: "Base", revenue: 27_400_000, description: "Steady 12% MoM growth, current agent base", color: "text-blue-600 bg-blue-50 border-blue-200" },
  { name: "Optimistic", revenue: 31_100_000, description: "25% new agent onboarding, 15% volume uplift", color: "text-green-600 bg-green-50 border-green-200" },
];

const RevenueForecastingEngine: React.FC = () => {
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [segments, setSegments] = useState<SegmentForecast[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchForecast(); }, []);

  const fetchForecast = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${CORE_URL}/api/analytics/revenue-forecast?entity_id=global&metric=revenue`,
        { headers: getTenantHeadersFromStorage() }
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setForecast(Array.isArray(data.forecast) ? data.forecast : []);
      setSegments(Array.isArray(data.segments) ? data.segments : []);
    } catch { setError("Failed to load revenue forecast."); } finally {
      setLoading(false);
    }
  };

  const currentMonth = forecast.find((f) => f.actual && f.month.startsWith("May"))?.actual || 0;
  const projectedMonthEnd = forecast.find((f) => f.month.startsWith("May"))?.forecast || 0;
  const ytd = forecast.filter((f) => f.actual).reduce((a, f) => a + (f.actual || 0), 0);

  const fmt = (n: number) => `₦${(n / 1_000_000).toFixed(1)}M`;

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchForecast()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Revenue Forecasting Engine</h1>
          <p className="text-gray-500 mt-1">ML-powered revenue projections and scenario modelling</p>
        </div>
        <button onClick={fetchForecast} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Current Month Revenue", value: fmt(currentMonth), icon: TrendingUp, color: "text-blue-600" },
          { label: "Projected Month-End", value: fmt(projectedMonthEnd), icon: Target, color: "text-green-600" },
          { label: "YTD Revenue", value: fmt(ytd), icon: BarChart3, color: "text-purple-600" },
          { label: "Forecast Accuracy", value: "—", icon: TrendingUp, color: "text-amber-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6 flex items-center gap-4">
            <div className="p-3 bg-gray-50 rounded-lg"><Icon size={20} className={color} /></div>
            <div><p className="text-sm text-gray-500">{label}</p><p className="text-xl font-bold text-gray-900">{value}</p></div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Actual vs Forecast (12-Month View)</h2>
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={forecast}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => `₦${(v / 1_000_000).toFixed(0)}M`} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v: number, name: string) => [`₦${v.toLocaleString()}`, name]} />
            <Legend />
            <Bar dataKey="actual" name="Actual" fill="#3B82F6" radius={[4, 4, 0, 0]} />
            <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#10B981" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Forecast by Segment</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="pb-3">Segment</th><th className="pb-3">Current</th><th className="pb-3">Projected</th><th className="pb-3">Growth</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((s) => (
                <tr key={s.segment} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2.5 font-medium text-gray-900">{s.segment}</td>
                  <td className="py-2.5 text-gray-600">{fmt(s.current)}</td>
                  <td className="py-2.5 text-gray-600">{fmt(s.projected)}</td>
                  <td className="py-2.5 font-medium text-green-600">+{s.growth}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Scenario Modelling (Next Month)</h2>
          <div className="space-y-3">
            {SCENARIOS.map((s) => (
              <div key={s.name} className={`p-4 rounded-xl border ${s.color}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-lg font-bold">{fmt(s.revenue)}</span>
                </div>
                <p className="text-xs opacity-80">{s.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RevenueForecastingEngine;
