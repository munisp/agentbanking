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

const STATUS_STYLES: Record<ChannelStatus, string> = {
  primary: "bg-green-100 text-green-700",
  fallback: "bg-blue-100 text-blue-700",
  disabled: "bg-gray-100 text-gray-500",
};

const mapStatus = (s: any): ChannelStatus =>
  s === "primary" || s === "fallback" || s === "disabled"
    ? s
    : s === "active"
      ? "primary"
      : s === "degraded" || s === "inactive"
        ? "fallback"
        : "primary";

const MultiChannelPaymentOrchestration: React.FC = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [simulationMode, setSimulationMode] = useState(false);

  useEffect(() => { fetchChannels(); }, []);

  const fetchChannels = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/api/payment-orchestration/channels`, { headers: getTenantHeadersFromStorage() });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Request failed: ${res.status}`);
      }
      const data = await res.json();
      setSimulationMode(Boolean(data?.simulation_mode));

      // Handle different response formats
      let channelsArray: any[] = [];
      if (Array.isArray(data)) {
        channelsArray = data;
      } else if (data?.channels && Array.isArray(data.channels)) {
        channelsArray = data.channels;
      } else if (data?.data && Array.isArray(data.data)) {
        channelsArray = data.data;
      }

      // Normalize channels with default values
      const normalizedChannels: Channel[] = channelsArray.map(c => ({
        id: c.id || "",
        name: c.name || c.channel || "Unknown",
        txToday: c.txToday ?? c.tx_today ?? 0,
        successRate: c.successRate ?? c.success_rate ?? 0,
        avgProcessingMs: c.avgProcessingMs ?? c.avg_processing_ms ?? 0,
        revenueToday: c.revenueToday ?? c.revenue_today ?? 0,
        status: mapStatus(c.status),
        fallbackTo: c.fallbackTo ?? c.fallback_to,
      }));

      // Never substitute fabricated channels when the service returns none.
      setChannels(normalizedChannels);
    } catch (e) {
      setChannels([]);
      setError(
        e instanceof Error
          ? e.message
          : "Payment channel data could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleStatus = async (id: string) => {
    const channel = channels.find((c) => c.id === id);
    if (!channel) return;
    const next: ChannelStatus = channel.status === "primary" ? "fallback" : channel.status === "fallback" ? "disabled" : "primary";
    setActionError(null);
    try {
      const res = await fetch(`${CORE_URL}/api/payment-orchestration/channels/${id}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...getTenantHeadersFromStorage(),
        },
        body: JSON.stringify({ status: next }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Request failed: ${res.status}`);
      }
      // Only reflect the change locally after the backend confirmed it.
      setChannels((prev) => prev.map((c) => (c.id === id ? { ...c, status: next } : c)));
    } catch (e) {
      setActionError(
        `Could not update status for ${channel.name}: ${
          e instanceof Error ? e.message : "unknown error"
        }`
      );
    }
  };

  const totalTx = channels.reduce((a, c) => a + c.txToday, 0);
  const totalRevenue = channels.reduce((a, c) => a + c.revenueToday, 0);
  const avgSuccess = channels.length ? (channels.reduce((a, c) => a + c.successRate, 0) / channels.length).toFixed(1) : "—";

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

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          Payment channel data could not be loaded: {error}
        </div>
      )}
      {actionError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {actionError}
        </div>
      )}
      {simulationMode && !error && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-4 py-3 text-sm">
          The orchestration service is running in simulation mode — figures shown are simulated, not live.
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Total Transactions Today</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{error ? "—" : totalTx.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Total Revenue Today</p>
          <p className="text-2xl font-bold text-green-600 mt-1">{error ? "—" : `₦${totalRevenue.toLocaleString()}`}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-sm text-gray-500">Avg Success Rate</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{error || avgSuccess === "—" ? "—" : `${avgSuccess}%`}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Transactions by Channel</h2>
        {error ? (
          <p className="text-sm text-gray-500 py-8 text-center">Chart unavailable — channel data could not be loaded.</p>
        ) : channels.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">No payment channels returned by the orchestration service.</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={channels} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
              <Tooltip formatter={(v: number) => [v.toLocaleString(), "Transactions"]} />
              <Bar dataKey="txToday" fill="#3B82F6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
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
            {error ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-gray-500">
                  Channel configuration unavailable — the orchestration service could not be reached.
                </td>
              </tr>
            ) : channels.length === 0 && !loading ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-gray-500">
                  No payment channels returned by the orchestration service.
                </td>
              </tr>
            ) : (
              channels.map((c) => {
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
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MultiChannelPaymentOrchestration;
