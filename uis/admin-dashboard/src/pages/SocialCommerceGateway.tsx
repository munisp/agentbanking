import { ShoppingBag, TrendingUp, Link2, RefreshCw } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../services/tenant";

const CORE_URL = import.meta.env.VITE_SUPPORT_COMMS_URL || import.meta.env.VITE_API_URL || "http://localhost:8011";

interface SocialChannel {
  id: string;
  name: string;
  status: "connected" | "disconnected" | "pending";
  followers: number;
  ordersToday: number;
}

interface SocialOrder {
  id: string;
  channel: string;
  customer: string;
  items: string;
  amount: number;
  status: "pending" | "processing" | "delivered";
}

interface FunnelMetric {
  label: string;
  value: number;
}

const STATUS_STYLES: Record<string, string> = {
  connected: "bg-green-100 text-green-700",
  disconnected: "bg-red-100 text-red-700",
  pending: "bg-amber-100 text-amber-700",
  delivered: "bg-green-100 text-green-700",
  processing: "bg-blue-100 text-blue-700",
};

const SocialCommerceGateway: React.FC = () => {
  const [channels, setChannels] = useState<SocialChannel[]>([]);
  const [orders, setOrders] = useState<SocialOrder[]>([]);
  const [funnel, setFunnel] = useState<FunnelMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [commissionEarned] = useState(52400);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/storefront/api/v1/social-commerce`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setChannels(Array.isArray(d.channels) ? d.channels : []);
        setOrders(Array.isArray(d.orders) ? d.orders : []);
        setFunnel(Array.isArray(d.funnel) ? d.funnel : []);
      } else { setError("Failed to load social commerce data."); }
    } catch { setError("Failed to load social commerce data."); }
    finally { setLoading(false); }
  };

  const totalOrdersToday = channels.reduce((s, c) => s + c.ordersToday, 0);

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchData()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ShoppingBag className="w-7 h-7 text-indigo-600" /> Social Commerce Gateway
          </h1>
          <p className="text-gray-500 text-sm mt-1">Manage orders and analytics from social media commerce channels</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Orders Today", value: totalOrdersToday, color: "text-indigo-600" },
          { label: "Commission Earned", value: `₦${commissionEarned.toLocaleString()}`, color: "text-green-600" },
          { label: "Conversion Rate", value: funnel.length >= 4 && funnel[0]?.value ? `${((funnel[3].value / funnel[0].value) * 100).toFixed(2)}%` : "—", color: "text-blue-600" },
          { label: "Connected Channels", value: channels.filter(c => c.status === "connected").length, color: "text-purple-600" },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><Link2 className="w-4 h-4" /> Connected Channels</h2>
          <div className="space-y-3">
            {channels.map(ch => (
              <div key={ch.id} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-900">{ch.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{ch.followers.toLocaleString()} followers · {ch.ordersToday} orders today</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_STYLES[ch.status]}`}>{ch.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><TrendingUp className="w-4 h-4" /> Conversion Funnel</h2>
          <div className="space-y-3">
            {funnel.map((step, i) => {
              const max = funnel[0]?.value ?? 1;
              const pct = Math.round((step.value / max) * 100);
              return (
                <div key={step.label}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600 font-medium">{step.label}</span>
                    <span className="text-gray-500">{step.value.toLocaleString()} {i > 0 && <span className="text-xs text-gray-400">({Math.round((step.value / funnel[i - 1].value) * 100)}% of prev)</span>}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2.5">
                    <div className="bg-indigo-500 h-2.5 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Recent Social Orders</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Order ID", "Channel", "Customer", "Items", "Amount (₦)", "Status"].map(h => (
                  <th key={h} className="text-left text-xs text-gray-500 font-medium pb-3 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {orders.map(order => (
                <tr key={order.id} className="hover:bg-gray-50">
                  <td className="py-3 pr-4 font-mono text-xs text-gray-500">{order.id}</td>
                  <td className="py-3 pr-4 text-gray-700">{order.channel}</td>
                  <td className="py-3 pr-4 font-medium text-gray-900">{order.customer}</td>
                  <td className="py-3 pr-4 text-gray-600 max-w-xs truncate">{order.items}</td>
                  <td className="py-3 pr-4 font-medium text-gray-800">₦{order.amount.toLocaleString()}</td>
                  <td className="py-3 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize font-medium ${STATUS_STYLES[order.status]}`}>{order.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SocialCommerceGateway;
