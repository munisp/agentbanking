import { Gauge, Play, RefreshCw, Users, Zap, Clock, AlertCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface TestRun {
  id: string;
  name: string;
  date: string;
  peakRPS: number;
  p95ms: number;
  errorPct: number;
  virtualUsers: number;
  durationSec: number;
}

interface LatencyPoint {
  t: string;
  p50: number;
  p95: number;
  p99: number;
}

const MOCK_RUNS: TestRun[] = [
  { id: "lt-001", name: "Baseline — Payment API", date: "2025-04-28", peakRPS: 420, p95ms: 182, errorPct: 0.4, virtualUsers: 200, durationSec: 300 },
  { id: "lt-002", name: "Stress — Auth Service", date: "2025-04-25", peakRPS: 850, p95ms: 374, errorPct: 2.1, virtualUsers: 500, durationSec: 600 },
  { id: "lt-003", name: "Soak — Ledger Write", date: "2025-04-20", peakRPS: 210, p95ms: 143, errorPct: 0.1, virtualUsers: 100, durationSec: 3600 },
  { id: "lt-004", name: "Spike — Transfer Endpoint", date: "2025-05-01", peakRPS: 1200, p95ms: 612, errorPct: 5.8, virtualUsers: 1000, durationSec: 60 },
];

const generateLatencyData = (): LatencyPoint[] =>
  Array.from({ length: 20 }, (_, i) => ({
    t: `${i * 15}s`,
    p50: 80 + Math.round(Math.sin(i * 0.5) * 20 + Math.random() * 15),
    p95: 160 + Math.round(Math.sin(i * 0.5) * 40 + Math.random() * 30),
    p99: 280 + Math.round(Math.sin(i * 0.5) * 60 + Math.random() * 50),
  }));

const MOCK_LATENCY = generateLatencyData();

const LoadTestDashboard: React.FC = () => {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ targetUrl: "https://54agent.upi.dev/api/v1/transfer", virtualUsers: "200", durationSec: "300" });
  const latest = runs[runs.length - 1] ?? MOCK_RUNS[0];

  

  useEffect(() => { fetchRuns(); }, []);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/load-tests`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setRuns(Array.isArray(d.runs) ? d.runs : MOCK_RUNS); }
    } catch { }
    finally { setLoading(false); }
  };

  const startTest = async () => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/load-tests`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setShowForm(false);
      fetchRuns();
    } catch { alert("Load test queued (demo mode)"); setShowForm(false); }
  };

  const summaryCards = [
    { label: "Virtual Users", value: latest.virtualUsers.toLocaleString(), icon: <Users className="w-5 h-5 text-indigo-500" />, color: "text-indigo-600" },
    { label: "Peak RPS", value: latest.peakRPS.toLocaleString(), icon: <Zap className="w-5 h-5 text-amber-500" />, color: "text-amber-600" },
    { label: "p95 Latency", value: `${latest.p95ms} ms`, icon: <Clock className="w-5 h-5 text-blue-500" />, color: "text-blue-600" },
    { label: "Error Rate", value: `${latest.errorPct}%`, icon: <AlertCircle className="w-5 h-5 text-red-500" />, color: latest.errorPct > 2 ? "text-red-600" : "text-green-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Gauge className="w-7 h-7 text-indigo-600" /> Load Test Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">Performance benchmarks and historical test comparisons</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchRuns} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
          <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
            <Play className="w-4 h-4" /> New Load Test
          </button>
        </div>
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wide">Latest Test — {latest.name}</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {summaryCards.map(card => (
            <div key={card.label} className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-2 mb-2">{card.icon}<p className="text-xs text-gray-500">{card.label}</p></div>
              <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Latency Profile — Last Test Run</h2>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={MOCK_LATENCY}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="t" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit="ms" />
            <Tooltip formatter={(v: number) => `${v}ms`} />
            <Line type="monotone" dataKey="p50" stroke="#6366f1" strokeWidth={2} dot={false} name="p50" />
            <Line type="monotone" dataKey="p95" stroke="#f59e0b" strokeWidth={2} dot={false} name="p95" />
            <Line type="monotone" dataKey="p99" stroke="#ef4444" strokeWidth={2} dot={false} name="p99" />
          </LineChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-2 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-indigo-500" /> p50</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-amber-500" /> p95</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-red-500" /> p99</span>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Historical Test Comparison</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="pb-3 pr-4">Test Name</th>
                <th className="pb-3 pr-4">Date</th>
                <th className="pb-3 pr-4">VUs</th>
                <th className="pb-3 pr-4">Peak RPS</th>
                <th className="pb-3 pr-4">p95 ms</th>
                <th className="pb-3">Error %</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4 font-medium text-gray-800">{run.name}</td>
                  <td className="py-3 pr-4 text-gray-500">{run.date}</td>
                  <td className="py-3 pr-4 text-gray-700">{run.virtualUsers}</td>
                  <td className="py-3 pr-4 text-gray-700">{run.peakRPS.toLocaleString()}</td>
                  <td className="py-3 pr-4 text-gray-700">{run.p95ms}</td>
                  <td className="py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${run.errorPct > 2 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>{run.errorPct}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 shadow-xl w-full max-w-md">
            <h3 className="font-semibold text-gray-900 mb-4">Configure Load Test</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Target URL</label>
                <input value={form.targetUrl} onChange={e => setForm(f => ({ ...f, targetUrl: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Virtual Users</label>
                  <input type="number" value={form.virtualUsers} onChange={e => setForm(f => ({ ...f, virtualUsers: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Duration (sec)</label>
                  <input type="number" value={form.durationSec} onChange={e => setForm(f => ({ ...f, durationSec: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={startTest} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">Start Test</button>
                <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LoadTestDashboard;
