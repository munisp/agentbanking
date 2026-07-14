import { GitBranch, Smartphone, Globe, MonitorSmartphone, MessageSquare, Wifi, RefreshCw } from "lucide-react";
import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../services/tenant";

const CORE_URL = import.meta.env.VITE_SUPPORT_COMMS_URL || import.meta.env.VITE_API_URL || "http://localhost:8011";

type ChannelStatus = "primary" | "fallback" | "disabled";

interface Channel {
  id: string;
  name: string;
  txToday: number;
  successRate: number;
  avgProcessingMs: number;
  revenueToday: number;
  status: ChannelStatus;
  fallbackTo?: string;
}

const ICONS: Record<string, React.FC<any>> = {
  USSD: Smartphone, "Mobile App": Smartphone, Web: Globe,
  POS: MonitorSmartphone, WhatsApp: MessageSquare, NFC: Wifi,
};

const MOCK_CHANNELS: Channel[] = [
  { id: "ussd", name: "USSD", txToday: 8420, successRate: 97.8, avgProcessingMs: 1200, revenueToday: 2_105_000, status: "primary", fallbackTo: "Mobile App" },
  { id: "app", name: "Mobile App", txToday: 6340, successRate: 99.4, avgProcessingMs: 480, revenueToday: 1_585_000, status: "primary" },
  { id: "web", name: "Web", txToday: 2180, successRate: 98.9, avgProcessingMs: 620, revenueToday: 545_000, status: "primary" },
  { id: "pos", name: "POS", txToday: 4910, successRate: 96.2, avgProcessingMs: 2100, revenueToday: 1_227_500, status: "primary", fallbackTo: "USSD" },
  { id: "whatsapp", name: "WhatsApp", txToday: 1240, successRate: 98.1, avgProcessingMs: 750, revenueToday: 310_000, status: "primary" },
  { id: "nfc", name: "NFC", txToday: 580, successRate: 99.8, avgProcessingMs: 180, revenueToday: 145_000, status: "fallback" },
];

const STATUS_STYLES: Record<ChannelStatus, string> = {
  primary: "bg-green-100 text-green-700",
  fallback: "bg-blue-100 text-blue-700",
  disabled: "bg-gray-100 text-gray-500",
};

const MultiChannelPaymentOrchestration: React.FC = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { fetchChannels(); }, []);

  const fetchChannels = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/api/payment-orchestration/channels`, { headers: getTenantHeadersFromStorage() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      
      // Handle different response formats
      let channelsArray: Channel[] = [];
      if (Array.isArray(data)) {
        channelsArray = data;
      } else if (data?.channels && Array.isArray(data.channels)) {
        channelsArray = data.channels;
      } else if (data?.data && Array.isArray(data.data)) {
        channelsArray = data.data;
      }
      
      // Normalize channels with default values
      const normalizedChannels = channelsArray.map(c => ({
        id: c.id || "",
        name: c.name || "Unknown",
        txToday: c.txToday ?? 0,
        successRate: c.successRate ?? 0,
        avgProcessingMs: c.avgProcessingMs ?? 0,
        revenueToday: c.revenueToday ?? 0,
        status: c.status || "primary" as ChannelStatus,
        fallbackTo: c.fallbackTo,
      }));
      
      setChannels(normalizedChannels.length > 0 ? normalizedChannels : MOCK_CHANNELS);
    } catch {
      setChannels(MOCK_CHANNELS);
    } finally {
      setLoading(false);
    }
  };

  const toggleStatus = (id: string) => {
    setChannels((prev) => prev.map((c) => {
      if (c.id !== id) return c;
      const next: ChannelStatus = c.status === "primary" ? "fallback" : c.status === "fallback" ? "disabled" : "primary";
      return { ...c, status: next };
    }));
  };

  const totalTx = channels.reduce((a, c) => a + c.txToday, 0);
  const totalRevenue = channels.reduce((a, c) => a + c.revenueToday, 0);
  const avgSuccess = channels.length ? (channels.reduce((a, c) => a + c.successRate, 0) / channels.length).toFixed(1) : "0";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Multi-Channel Payment Orchestration</h1>
          <p className="text-gray-500 mt-1">Route, monitor, and manage all payment channels</p>
        </div>
        <button onClick={fetchChannels} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Total Transactions Today</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalTx.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Total Revenue Today</p>
          <p className="text-2xl font-bold text-green-600 mt-1">₦{totalRevenue.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Avg Success Rate</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{avgSuccess}%</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Transactions by Channel</h2>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={channels} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
            <Tooltip formatter={(v: number) => [v.toLocaleString(), "Transactions"]} />
            <Bar dataKey="txToday" fill="#3B82F6" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Channel Configuration</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-100">
              <th className="pb-3">Channel</th>
              <th className="pb-3">Tx Today</th>
              <th className="pb-3">Success Rate</th>
              <th className="pb-3">Avg Processing</th>
              <th className="pb-3">Revenue</th>
              <th className="pb-3">Fallback To</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((c) => {
              const Icon = ICONS[c.name] || GitBranch;
              return (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 font-medium text-gray-900 flex items-center gap-2"><Icon size={14} className="text-gray-400" />{c.name}</td>
                  <td className="py-3 text-gray-600">{c.txToday.toLocaleString()}</td>
                  <td className="py-3">
                    <span className={`font-medium ${c.successRate >= 99 ? "text-green-600" : c.successRate >= 97 ? "text-amber-600" : "text-red-500"}`}>{c.successRate}%</span>
                  </td>
                  <td className="py-3 text-gray-600">{c.avgProcessingMs}ms</td>
                  <td className="py-3 text-gray-600">₦{c.revenueToday.toLocaleString()}</td>
                  <td className="py-3 text-gray-500 text-xs">{c.fallbackTo || "—"}</td>
                  <td className="py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[c.status]}`}>{c.status}</span></td>
                  <td className="py-3">
                    <button onClick={() => toggleStatus(c.id)} className="px-2 py-1 border border-gray-200 rounded text-xs hover:bg-gray-100">Toggle</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MultiChannelPaymentOrchestration;
