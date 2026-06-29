import { Key, Plus, Copy, Trash2, RefreshCw, Eye, EyeOff, CheckCircle, Activity } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  full_key?: string;
  scopes: string[];
  status: "active" | "revoked" | "expired";
  last_used?: string;
  usage_count: number;
  created_at: string;
  expires_at?: string;
}

const ALL_SCOPES = ["transactions:read", "transactions:write", "agents:read", "merchants:read", "reports:read", "webhooks:manage", "compliance:read", "settlements:read"];

const MOCK_KEYS: ApiKey[] = [
  { id: "key-001", name: "Production App", key_prefix: "sk_live_abc1", scopes: ["transactions:read", "reports:read"], status: "active", last_used: "2 hours ago", usage_count: 45230, created_at: "2024-01-15" },
  { id: "key-002", name: "Analytics Dashboard", key_prefix: "sk_live_def2", scopes: ["transactions:read", "reports:read", "agents:read"], status: "active", last_used: "Just now", usage_count: 12800, created_at: "2024-03-10" },
  { id: "key-003", name: "Legacy Integration", key_prefix: "sk_live_ghi3", scopes: ["transactions:read"], status: "revoked", usage_count: 5000, created_at: "2023-11-20" },
];

const ApiKeyManagement: React.FC = () => {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [newKey, setNewKey] = useState<ApiKey | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [revealedId, setRevealedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", scopes: [] as string[], expires_days: "" });
  const [creating, setCreating] = useState(false);

  useEffect(() => { fetchKeys(); }, []);

  const fetchKeys = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/api-keys`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setKeys(Array.isArray(d.keys) ? d.keys : MOCK_KEYS); }
      else { setKeys(MOCK_KEYS); }
    } catch { setKeys(MOCK_KEYS); }
    finally { setLoading(false); }
  };

  const createKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name) return;
    setCreating(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/api-keys`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Failed to create key");
      const data = await res.json();
      setNewKey(data.key || { ...form, id: "new-" + Date.now(), key_prefix: "sk_live_****", full_key: data.full_key || "sk_live_xxxxxxxxxxxx", status: "active", usage_count: 0, created_at: new Date().toISOString() });
      setShowForm(false);
      fetchKeys();
    } catch (err: any) { alert(err.message); }
    finally { setCreating(false); }
  };

  const revokeKey = async (id: string) => {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    try {
      await fetch(`${CORE_URL}/developer/api/v1/api-keys/${id}/revoke`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchKeys();
    } catch (err: any) { alert(err.message); }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleScope = (scope: string) => {
    setForm(f => ({ ...f, scopes: f.scopes.includes(scope) ? f.scopes.filter(s => s !== scope) : [...f.scopes, scope] }));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Key className="w-7 h-7 text-blue-600" /> API Key Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Manage API credentials for platform integrations</p>
        </div>
        <button onClick={() => { setShowForm(true); setNewKey(null); }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> Create API Key
        </button>
      </div>

      {/* New Key Display */}
      {newKey && newKey.full_key && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            <h3 className="font-semibold text-emerald-800">API Key Created</h3>
          </div>
          <p className="text-sm text-emerald-700 mb-3">Copy this key now — it will not be shown again.</p>
          <div className="flex items-center gap-2 bg-white border border-emerald-300 rounded-lg p-3">
            <code className="text-sm font-mono text-gray-800 flex-1 break-all">{newKey.full_key}</code>
            <button onClick={() => copyToClipboard(newKey.full_key!, "new")} className="shrink-0 p-1 text-emerald-600 hover:text-emerald-800">
              {copiedId === "new" ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>
      )}

      {/* Create Form */}
      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Create New API Key</h2>
          <form onSubmit={createKey} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Key Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Production App"
                required className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-2">Scopes</label>
              <div className="flex flex-wrap gap-2">
                {ALL_SCOPES.map(scope => (
                  <button type="button" key={scope} onClick={() => toggleScope(scope)}
                    className={`px-2 py-1 rounded text-xs border transition-colors ${form.scopes.includes(scope) ? "bg-blue-600 border-blue-500 text-white" : "bg-white border-gray-200 text-gray-600 hover:border-blue-300"}`}>
                    {scope}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Expires in (days, optional)</label>
              <input type="number" value={form.expires_days} onChange={e => setForm(f => ({ ...f, expires_days: e.target.value }))} placeholder="Never expires"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={creating}
                className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors">
                {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                {creating ? "Creating..." : "Create Key"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm transition-colors">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Keys List */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h3 className="font-medium text-gray-700">API Keys ({keys.length})</h3>
          <button onClick={fetchKeys} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
        <div className="divide-y divide-gray-50">
          {keys.map(k => (
            <div key={k.id} className="p-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-100 rounded-lg"><Key className="w-4 h-4 text-gray-600" /></div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm">{k.name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${k.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{k.status}</span>
                  </div>
                  <p className="text-xs text-gray-400 font-mono mt-0.5">{k.key_prefix}••••••••••••</p>
                  <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-2">
                    <Activity className="w-3 h-3" />{k.usage_count.toLocaleString()} calls · {k.last_used ? `Last used ${k.last_used}` : "Never used"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex flex-wrap gap-1 max-w-48">
                  {k.scopes.slice(0, 2).map(s => <span key={s} className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">{s}</span>)}
                  {k.scopes.length > 2 && <span className="text-xs text-gray-400">+{k.scopes.length - 2}</span>}
                </div>
                {k.status === "active" && (
                  <button onClick={() => revokeKey(k.id)} className="text-xs px-2 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded transition-colors flex items-center gap-1">
                    <Trash2 className="w-3 h-3" /> Revoke
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ApiKeyManagement;
