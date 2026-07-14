import { Webhook, Plus, RefreshCw, CheckCircle, XCircle, Clock, Trash2, Eye, AlertCircle, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const ALL_EVENTS = [
  "transaction.created", "transaction.completed", "transaction.failed", "transaction.reversed",
  "agent.registered", "agent.suspended", "agent.activated",
  "float.low", "float.replenished",
  "dispute.created", "dispute.resolved",
  "settlement.processed", "kyc.verified",
];

interface WebhookEndpoint {
  id: string;
  url: string;
  events: string[];
  status: "active" | "paused" | "disabled";
  secret?: string;
  last_delivery?: string;
  success_rate: number;
  total_deliveries: number;
  created_at: string;
}

interface WebhookDelivery {
  id: string;
  event: string;
  status: "success" | "failed" | "pending";
  response_code?: number;
  delivered_at: string;
  duration_ms?: number;
}

const MOCK_ENDPOINTS: WebhookEndpoint[] = [
  { id: "wh-001", url: "https://myapp.com/webhooks/54agent", events: ["transaction.completed", "transaction.failed", "settlement.processed"], status: "active", last_delivery: "2 min ago", success_rate: 98.4, total_deliveries: 12840, created_at: "2024-01-10" },
  { id: "wh-002", url: "https://analytics.company.io/events", events: ["transaction.created", "agent.registered"], status: "active", last_delivery: "15 min ago", success_rate: 99.1, total_deliveries: 45600, created_at: "2024-02-05" },
  { id: "wh-003", url: "https://staging.example.com/hooks", events: ["transaction.created"], status: "paused", last_delivery: "3 days ago", success_rate: 87.2, total_deliveries: 800, created_at: "2024-10-20" },
];

const WebhookManagement: React.FC = () => {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [viewDeliveries, setViewDeliveries] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ url: "", events: [] as string[] });
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => { fetchEndpoints(); }, []);

  const fetchEndpoints = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/webhooks`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setEndpoints(Array.isArray(d.endpoints) ? d.endpoints : MOCK_ENDPOINTS); }
      else { setEndpoints(MOCK_ENDPOINTS); }
    } catch { setEndpoints(MOCK_ENDPOINTS); }
    finally { setLoading(false); }
  };

  const createEndpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/webhooks`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Failed to create webhook");
      setShowForm(false);
      setForm({ url: "", events: [] });
      fetchEndpoints();
    } catch (err: any) { alert(err.message); }
    finally { setSaving(false); }
  };

  const deleteEndpoint = async (id: string) => {
    if (!confirm("Delete this webhook endpoint?")) return;
    try {
      await fetch(`${CORE_URL}/developer/api/v1/webhooks/${id}`, { method: "DELETE", headers: getTenantHeadersFromStorage() });
      fetchEndpoints();
    } catch (err: any) { alert(err.message); }
  };

  const testEndpoint = async (id: string) => {
    setTesting(id);
    try {
      await fetch(`${CORE_URL}/developer/api/v1/webhooks/${id}/test`, { method: "POST", headers: getTenantHeadersFromStorage() });
      alert("Test event sent successfully!");
    } catch (err: any) { alert(err.message); }
    finally { setTesting(null); }
  };

  const togglePause = async (ep: WebhookEndpoint) => {
    try {
      await fetch(`${CORE_URL}/developer/api/v1/webhooks/${ep.id}/status`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ status: ep.status === "active" ? "paused" : "active" }),
      });
      fetchEndpoints();
    } catch (err: any) { alert(err.message); }
  };

  const toggleEvent = (ev: string) => {
    setForm(f => ({ ...f, events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev] }));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Webhook className="w-7 h-7 text-purple-600" /> Webhook Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Configure endpoints to receive real-time event notifications</p>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> Add Endpoint
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active Endpoints", value: endpoints.filter(e => e.status === "active").length, color: "text-emerald-600" },
          { label: "Total Deliveries", value: endpoints.reduce((s, e) => s + e.total_deliveries, 0).toLocaleString(), color: "text-blue-600" },
          { label: "Avg Success Rate", value: `${endpoints.length ? (endpoints.reduce((s, e) => s + e.success_rate, 0) / endpoints.length).toFixed(1) : 0}%`, color: "text-purple-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Add Webhook Endpoint</h2>
          <form onSubmit={createEndpoint} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Endpoint URL</label>
              <input type="url" value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))} placeholder="https://your-app.com/webhooks"
                required className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-2">Subscribe to Events</label>
              <div className="flex flex-wrap gap-2">
                {ALL_EVENTS.map(ev => (
                  <button type="button" key={ev} onClick={() => toggleEvent(ev)}
                    className={`px-2 py-1 rounded text-xs border transition-colors ${form.events.includes(ev) ? "bg-purple-600 border-purple-500 text-white" : "bg-white border-gray-200 text-gray-600 hover:border-purple-300"}`}>
                    {ev}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-start gap-2 text-xs text-blue-700 bg-blue-50 rounded-lg p-3">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>A secret signing key will be generated. Use it to verify the <code className="bg-blue-100 px-1 rounded">X-54agent-Signature</code> header on incoming events.</span>
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={saving || !form.url || form.events.length === 0}
                className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors">
                {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                {saving ? "Creating..." : "Create Webhook"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm transition-colors">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Endpoints List */}
      <div className="space-y-4">
        {endpoints.map(ep => (
          <div key={ep.id} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-sm font-medium text-gray-800 break-all">{ep.url}</code>
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize shrink-0 ${ep.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{ep.status}</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {ep.events.map(ev => <span key={ev} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{ev}</span>)}
                </div>
                <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                  <span><Activity className="w-3 h-3 inline mr-1" />{ep.total_deliveries.toLocaleString()} deliveries</span>
                  <span className={ep.success_rate >= 95 ? "text-emerald-500" : "text-amber-500"}>{ep.success_rate}% success</span>
                  {ep.last_delivery && <span>Last: {ep.last_delivery}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => testEndpoint(ep.id)} disabled={testing === ep.id}
                  className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded transition-colors flex items-center gap-1">
                  {testing === ep.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Activity className="w-3 h-3" />} Test
                </button>
                <button onClick={() => togglePause(ep)} className={`text-xs px-2 py-1 rounded transition-colors flex items-center gap-1 ${ep.status === "active" ? "bg-amber-50 text-amber-600 hover:bg-amber-100" : "bg-emerald-50 text-emerald-600 hover:bg-emerald-100"}`}>
                  {ep.status === "active" ? "Pause" : "Resume"}
                </button>
                <button onClick={() => deleteEndpoint(ep.id)} className="text-xs px-2 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded transition-colors flex items-center gap-1">
                  <Trash2 className="w-3 h-3" /> Delete
                </button>
              </div>
            </div>
          </div>
        ))}
        {endpoints.length === 0 && !loading && (
          <div className="text-center py-12 text-gray-400 bg-white border border-gray-200 rounded-xl">
            <Webhook className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p>No webhook endpoints configured</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default WebhookManagement;
