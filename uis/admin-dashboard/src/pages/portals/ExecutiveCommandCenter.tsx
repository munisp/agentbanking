import { TrendingUp, AlertTriangle, Download, MapPin, DollarSign, Users, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface KPI {
  totalAgents: number;
  agentsMoM: number;
  transactionVolume: number;
  volumeVsYesterday: number;
  revenueMTD: number;
  revenueVsLastMonth: number;
  activeCustomers: number;
}

interface WeeklyData {
  day: string;
  revenue: number;
  transactions: number;
}

interface StateVolume {
  state: string;
  volume: number;
}

interface Alert {
  id: string;
  severity: "critical" | "high" | "medium";
  message: string;
  time: string;
}

const SEV: Record<string, string> = {
  critical: "bg-red-100 text-red-700", high: "bg-amber-100 text-amber-700", medium: "bg-yellow-50 text-yellow-700",
};

const fmt = (n: number) => n >= 1e9 ? `₦${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `₦${(n / 1e6).toFixed(1)}M` : n.toLocaleString();

const ExecutiveCommandCenter: React.FC = () => {
  const [kpi, setKpi] = useState<KPI | null>(null);
  const [weekly, setWeekly] = useState<WeeklyData[]>([]);
  const [states, setStates] = useState<StateVolume[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/portals/api/v1/executive/summary`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setKpi(d.kpi ?? null);
        setWeekly(d.weekly ?? []);
        setStates(d.states ?? []);
        setAlerts(d.alerts ?? []);
      } else { setError("Failed to load executive summary."); }
    } catch { setError("Failed to load executive summary."); } finally { setLoading(false); }
  };

  const kpiCards = [
    { label: "Total Agents", value: kpi ? kpi.totalAgents.toLocaleString() : "—", delta: kpi ? `+${kpi.agentsMoM}% MoM` : "No data", icon: Users, color: "text-indigo-600" },
    { label: "Transaction Volume (Today)", value: kpi ? fmt(kpi.transactionVolume) : "—", delta: kpi ? `+${kpi.volumeVsYesterday}% vs yesterday` : "No data", icon: Activity, color: "text-emerald-600" },
    { label: "Revenue MTD", value: kpi ? fmt(kpi.revenueMTD) : "—", delta: kpi ? `+${kpi.revenueVsLastMonth}% vs last month` : "No data", icon: DollarSign, color: "text-blue-600" },
    { label: "Active Customers", value: kpi ? kpi.activeCustomers.toLocaleString() : "—", delta: kpi ? "Registered & transacting" : "No data", icon: TrendingUp, color: "text-purple-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchAll()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Executive Command Center</h1>
          <p className="text-gray-500 text-sm mt-1">Board-level platform overview — real-time KPIs and critical signals</p>
        </div>
        <button onClick={() => alert("Exporting board report…")} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
          <Download className="w-4 h-4" /> Export Board Report
        </button>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpiCards.map(({ label, value, delta, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{label}</p>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-xs text-emerald-600 font-medium">{delta}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Weekly Revenue vs Transactions</h2>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={weekly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} tickFormatter={v => `₦${(v / 1e6).toFixed(0)}M`} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number, name: string) => name === "revenue" ? fmt(v) : v.toLocaleString()} />
              <Legend />
              <Bar yAxisId="left" dataKey="revenue" fill="#6366f1" name="Revenue" radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="transactions" stroke="#10b981" strokeWidth={2} dot={false} name="Transactions" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2"><MapPin className="w-4 h-4 text-indigo-500" /> Top 5 States by Volume</h2>
          {states.map((s, i) => {
            const max = states[0]?.volume || 1;
            return (
              <div key={s.state}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700 font-medium">#{i + 1} {s.state}</span>
                  <span className="text-gray-500">{fmt(s.volume)}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${(s.volume / max) * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><AlertTriangle className="w-4 h-4 text-red-500" /> Critical Alerts</h2>
        <div className="space-y-3">
          {alerts.map(a => (
            <div key={a.id} className="flex items-start justify-between gap-4 p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${SEV[a.severity]}`}>{a.severity}</span>
                <span className="text-sm text-gray-700">{a.message}</span>
              </div>
              <span className="text-xs text-gray-400 whitespace-nowrap">{a.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ExecutiveCommandCenter;
