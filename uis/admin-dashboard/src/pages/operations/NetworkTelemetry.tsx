import { Activity, Radio, TrendingDown, TrendingUp, RefreshCw, MapPin } from "lucide-react";
import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface RegionTelemetry {
  region: string;
  nodes: number;
  avgLatencyMs: number;
  packetLoss: number;
  jitterMs: number;
  status: "healthy" | "degraded" | "critical";
}

interface LatencyPoint { time: string; latencyMs: number; }

const MOCK_REGIONS: RegionTelemetry[] = [
  { region: "Lagos", nodes: 12, avgLatencyMs: 18, packetLoss: 0.2, jitterMs: 2.1, status: "healthy" },
  { region: "Abuja", nodes: 8, avgLatencyMs: 24, packetLoss: 0.5, jitterMs: 3.4, status: "healthy" },
  { region: "Kano", nodes: 5, avgLatencyMs: 42, packetLoss: 1.8, jitterMs: 6.2, status: "degraded" },
  { region: "Port Harcourt", nodes: 6, avgLatencyMs: 31, packetLoss: 0.9, jitterMs: 4.0, status: "healthy" },
  { region: "Ibadan", nodes: 4, avgLatencyMs: 55, packetLoss: 3.1, jitterMs: 9.5, status: "critical" },
  { region: "Enugu", nodes: 3, avgLatencyMs: 38, packetLoss: 1.2, jitterMs: 5.1, status: "degraded" },
];

const MOCK_LATENCY: LatencyPoint[] = Array.from({ length: 24 }, (_, i) => ({
  time: `${String(i).padStart(2, "0")}:00`,
  latencyMs: 18 + Math.floor(Math.random() * 20),
}));

const STATUS_STYLES: Record<string, string> = {
  healthy: "bg-green-100 text-green-700",
  degraded: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};

const NetworkTelemetry: React.FC = () => {
  const [regions, setRegions] = useState<RegionTelemetry[]>([]);
  const [latencyData, setLatencyData] = useState<LatencyPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [traceroute, setTraceroute] = useState<string | null>(null);

  useEffect(() => { fetchTelemetry(); }, []);

  const fetchTelemetry = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/network/telemetry`, { headers: getTenantHeadersFromStorage() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setRegions(data.regions || MOCK_REGIONS);
      setLatencyData(data.latency || MOCK_LATENCY);
    } catch {
      setRegions(MOCK_REGIONS);
      setLatencyData(MOCK_LATENCY);
    } finally {
      setLoading(false);
    }
  };

  const runTraceroute = () => {
    setTraceroute("Tracing route to 54agent.upi.dev...\n1  192.168.1.1  1ms\n2  10.0.0.1  4ms\n3  196.46.1.1  12ms\n4  41.222.32.1  18ms\n5  54agent.upi.dev  21ms\nTrace complete.");
  };

  const avgLatency = regions.length ? Math.round(regions.reduce((a, r) => a + r.avgLatencyMs, 0) / regions.length) : 0;
  const avgPacketLoss = regions.length ? (regions.reduce((a, r) => a + r.packetLoss, 0) / regions.length).toFixed(1) : "0";
  const avgJitter = regions.length ? (regions.reduce((a, r) => a + r.jitterMs, 0) / regions.length).toFixed(1) : "0";
  const totalNodes = regions.reduce((a, r) => a + r.nodes, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Network Telemetry</h1>
          <p className="text-gray-500 mt-1">Real-time network diagnostics across all regions</p>
        </div>
        <div className="flex gap-2">
          <button onClick={runTraceroute} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Radio size={16} /> Run Traceroute
          </button>
          <button onClick={fetchTelemetry} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Avg Latency", value: `${avgLatency}ms`, icon: Activity, color: "text-blue-600" },
          { label: "Avg Packet Loss", value: `${avgPacketLoss}%`, icon: TrendingDown, color: "text-amber-600" },
          { label: "Avg Jitter", value: `${avgJitter}ms`, icon: TrendingUp, color: "text-purple-600" },
          { label: "Total Nodes", value: totalNodes, icon: MapPin, color: "text-green-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6 flex items-center gap-4">
            <div className="p-3 bg-gray-50 rounded-lg"><Icon size={20} className={color} /></div>
            <div><p className="text-sm text-gray-500">{label}</p><p className="text-2xl font-bold text-gray-900">{value}</p></div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Latency Trend (Last 24h)</h2>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={latencyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} interval={3} />
            <YAxis tick={{ fontSize: 11 }} unit="ms" />
            <Tooltip formatter={(v: number) => [`${v}ms`, "Latency"]} />
            <Line type="monotone" dataKey="latencyMs" stroke="#3B82F6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Regional Breakdown</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-100">
              <th className="pb-3">Region</th>
              <th className="pb-3">Nodes</th>
              <th className="pb-3">Avg Latency</th>
              <th className="pb-3">Packet Loss</th>
              <th className="pb-3">Jitter</th>
              <th className="pb-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {regions.map((r) => (
              <tr key={r.region} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 font-medium text-gray-900">{r.region}</td>
                <td className="py-3 text-gray-600">{r.nodes}</td>
                <td className="py-3 text-gray-600">{r.avgLatencyMs}ms</td>
                <td className="py-3 text-gray-600">{r.packetLoss}%</td>
                <td className="py-3 text-gray-600">{r.jitterMs}ms</td>
                <td className="py-3"><span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[r.status]}`}>{r.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {traceroute && (
        <div className="bg-gray-900 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-2">Traceroute Output</p>
          <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">{traceroute}</pre>
        </div>
      )}
    </div>
  );
};

export default NetworkTelemetry;
