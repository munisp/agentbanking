import { Shield, RefreshCw, Plus, AlertOctagon, Gauge } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface RateLimitRule {
  id: string;
  pattern: string;
  limit: number;
  window: "per-minute" | "per-hour" | "per-day";
  currentUsage: number;
}

interface ThrottledClient {
  id: string;
  identifier: string;
  endpoint: string;
  blockedAt: string;
  retryAfter: string;
}

const MOCK_RULES: RateLimitRule[] = [
  { id: "r1", pattern: "POST /transaction/api/v1/transfers", limit: 60, window: "per-minute", currentUsage: 48 },
  { id: "r2", pattern: "POST /auth/api/v1/login", limit: 10, window: "per-minute", currentUsage: 3 },
  { id: "r3", pattern: "GET /transaction/api/v1/transactions", limit: 300, window: "per-minute", currentUsage: 198 },
  { id: "r4", pattern: "POST /agent/api/v1/cash-in", limit: 50, window: "per-minute", currentUsage: 47 },
  { id: "r5", pattern: "POST /payment-hub/api/v1/bills", limit: 1000, window: "per-hour", currentUsage: 620 },
  { id: "r6", pattern: "GET /compliance/api/v1/kyc-status", limit: 5000, window: "per-hour", currentUsage: 1200 },
  { id: "r7", pattern: "POST /developer/api/v1/webhooks/test", limit: 20, window: "per-minute", currentUsage: 19 },
  { id: "r8", pattern: "*", limit: 50000, window: "per-day", currentUsage: 31000 },
];

const MOCK_THROTTLED: ThrottledClient[] = [
  { id: "t1", identifier: "IP: 196.168.4.22", endpoint: "POST /auth/api/v1/login", blockedAt: "2024-12-10 14:32:01", retryAfter: "2024-12-10 14:33:01" },
  { id: "t2", identifier: "Key: sk_live_9f3k...2xp", endpoint: "POST /agent/api/v1/cash-in", blockedAt: "2024-12-10 14:30:45", retryAfter: "2024-12-10 14:31:45" },
  { id: "t3", identifier: "IP: 41.58.120.7", endpoint: "POST /transaction/api/v1/transfers", blockedAt: "2024-12-10 14:28:10", retryAfter: "2024-12-10 14:29:10" },
];

const WINDOW_OPTIONS = ["per-minute", "per-hour", "per-day"] as const;

const APIRateLimiterDashboard: React.FC = () => {
  const [rules, setRules] = useState<RateLimitRule[]>([]);
  const [throttled, setThrottled] = useState<ThrottledClient[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ pattern: "", limit: "", window: "per-minute" as RateLimitRule["window"] });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/rate-limits`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setRules(Array.isArray(d.rules) ? d.rules : MOCK_RULES);
        setThrottled(Array.isArray(d.throttled) ? d.throttled : MOCK_THROTTLED);
      } else { setRules(MOCK_RULES); setThrottled(MOCK_THROTTLED); }
    } catch { setRules(MOCK_RULES); setThrottled(MOCK_THROTTLED); }
    finally { setLoading(false); }
  };

  const addRule = async () => {
    try {
      await fetch(`${CORE_URL}/developer/api/v1/rate-limits`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ pattern: form.pattern, limit: Number(form.limit), window: form.window }),
      });
      setShowForm(false);
      fetchData();
    } catch { setShowForm(false); fetchData(); }
  };

  const deleteRule = async (id: string) => {
    try {
      await fetch(`${CORE_URL}/developer/api/v1/rate-limits/${id}`, {
        method: "DELETE", headers: getTenantHeadersFromStorage(),
      });
      fetchData();
    } catch { fetchData(); }
  };

  const usageColor = (pct: number) => pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-blue-500";
  const usageTextColor = (pct: number) => pct >= 90 ? "text-red-700" : pct >= 70 ? "text-amber-700" : "text-blue-700";
  const usageBgColor = (pct: number) => pct >= 90 ? "bg-red-100" : pct >= 70 ? "bg-amber-100" : "bg-blue-100";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-7 h-7 text-blue-600" /> API Rate Limiter
          </h1>
          <p className="text-gray-500 text-sm mt-1">Configure and monitor rate limiting rules across all API endpoints</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">
            <Plus className="w-4 h-4" /> Add Rule
          </button>
          <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active Rules", value: rules.length, color: "text-blue-600" },
          { label: "Near Limit (>90%)", value: rules.filter(r => (r.currentUsage / r.limit) * 100 >= 90).length, color: "text-red-600" },
          { label: "Throttled Now", value: throttled.length, color: "text-amber-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">New Rate Limit Rule</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Endpoint Pattern</label>
              <input value={form.pattern} onChange={e => setForm(f => ({ ...f, pattern: e.target.value }))} placeholder="e.g. POST /api/v1/transfers"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Request Limit</label>
              <input type="number" value={form.limit} onChange={e => setForm(f => ({ ...f, limit: e.target.value }))} placeholder="e.g. 100"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Window</label>
              <select value={form.window} onChange={e => setForm(f => ({ ...f, window: e.target.value as RateLimitRule["window"] }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {WINDOW_OPTIONS.map(w => <option key={w} value={w}>{w}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={addRule} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">Save Rule</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2"><Gauge className="w-4 h-4 text-blue-500" /> Active Rate Limit Rules</h2>
        <div className="space-y-4">
          {rules.map(rule => {
            const pct = Math.round((rule.currentUsage / rule.limit) * 100);
            return (
              <div key={rule.id} className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2 gap-4">
                  <span className="font-mono text-xs text-gray-700 truncate flex-1">{rule.pattern}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-gray-500">{rule.limit} req / {rule.window.replace("per-", "")}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${usageBgColor(pct)} ${usageTextColor(pct)}`}>{pct}% used</span>
                    <button onClick={() => deleteRule(rule.id)} className="text-xs px-2 py-1 text-red-500 hover:bg-red-50 rounded">Remove</button>
                  </div>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`${usageColor(pct)} h-2 rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <p className="text-xs text-gray-400 mt-1">{rule.currentUsage.toLocaleString()} / {rule.limit.toLocaleString()} requests</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2"><AlertOctagon className="w-4 h-4 text-red-500" /> Currently Throttled Clients</h2>
        {throttled.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No clients currently throttled</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-100">
                <th className="text-left pb-2 pr-4">Identifier</th>
                <th className="text-left pb-2 pr-4">Endpoint</th>
                <th className="text-left pb-2 pr-4">Blocked At</th>
                <th className="text-left pb-2">Retry After</th>
              </tr>
            </thead>
            <tbody>
              {throttled.map(c => (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-700">{c.identifier}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-600">{c.endpoint}</td>
                  <td className="py-2 pr-4 text-xs text-gray-500">{c.blockedAt}</td>
                  <td className="py-2 text-xs text-amber-600 font-medium">{c.retryAfter}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default APIRateLimiterDashboard;
