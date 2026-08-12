import { Layers, Search, RefreshCw, Trash2, TrendingUp } from "lucide-react";
import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface CacheNamespace {
  namespace: string;
  keys: number;
  avgTTL: number;
  hitRate: number;
}

interface MemoryPoint {
  time: string;
  memoryMB: number;
}

interface CacheSummary {
  hitRate: number;
  missRate: number;
  totalKeys: number;
  memoryUsedMB: number;
}

const CacheManagementDashboard: React.FC = () => {
  const [summary, setSummary] = useState<CacheSummary | null>(null);
  const [namespaces, setNamespaces] = useState<CacheNamespace[]>([]);
  const [memoryData, setMemoryData] = useState<MemoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [flushTarget, setFlushTarget] = useState<string | null>(null);
  const [keyPattern, setKeyPattern] = useState("");
  const [lookupResult, setLookupResult] = useState<string | null>(null);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/cache`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setSummary(d.summary ?? []);
        setNamespaces(Array.isArray(d.namespaces) ? d.namespaces : []);
        setMemoryData(Array.isArray(d.memory) ? d.memory : []);
      } else { setError("Failed to load cache data."); }
    } catch { setError("Failed to load cache data."); }
    finally { setLoading(false); }
  };

  const handleFlush = async (ns: string) => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/cache/${ns}/flush`, {
        method: "DELETE",
        headers: getTenantHeadersFromStorage(),
      });
      setFlushTarget(null);
      fetchData();
    } catch { setFlushTarget(null); fetchData(); }
  };

  const handleLookup = async () => {
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/cache/lookup?pattern=${encodeURIComponent(keyPattern)}`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setLookupResult(`Found ${d.count ?? 0} keys`); }
      else { setLookupResult("Lookup failed — cache service unavailable."); }
    } catch { setLookupResult("Lookup failed — cache service unavailable."); }
  };

  const filtered = namespaces.filter(n => n.namespace.includes(search));

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
            <Layers className="w-7 h-7 text-indigo-600" /> Cache Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Redis cache namespaces, hit rates and memory</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Hit Rate", value: summary ? `${summary.hitRate}%` : "—", color: "text-emerald-600" },
          { label: "Miss Rate", value: summary ? `${summary.missRate}%` : "—", color: "text-red-500" },
          { label: "Total Keys", value: summary ? summary.totalKeys.toLocaleString() : "—", color: "text-blue-600" },
          { label: "Memory Used", value: summary ? `${summary.memoryUsedMB} MB` : "—", color: "text-purple-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><TrendingUp className="w-4 h-4 text-indigo-500" /> Memory Usage Trend</h2>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={memoryData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Area type="monotone" dataKey="memoryMB" stroke="#8b5cf6" fill="#ede9fe" name="Memory (MB)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="font-semibold text-gray-900">Cache Namespaces</h2>
          <div className="relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter namespace..."
              className="pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Namespace", "Keys", "Avg TTL (s)", "Hit Rate", "Action"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(ns => (
                <tr key={ns.namespace} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-gray-800">{ns.namespace}</td>
                  <td className="py-2 px-3 text-gray-700">{ns.keys.toLocaleString()}</td>
                  <td className="py-2 px-3 text-gray-600">{ns.avgTTL}</td>
                  <td className="py-2 px-3">
                    <span className={`font-semibold text-xs ${ns.hitRate >= 90 ? "text-emerald-600" : ns.hitRate >= 75 ? "text-blue-600" : "text-amber-600"}`}>
                      {ns.hitRate}%
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    {flushTarget === ns.namespace ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-red-600">Confirm?</span>
                        <button onClick={() => handleFlush(ns.namespace)} className="text-xs px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600">Yes</button>
                        <button onClick={() => setFlushTarget(null)} className="text-xs px-2 py-1 bg-gray-100 rounded">No</button>
                      </div>
                    ) : (
                      <button onClick={() => setFlushTarget(ns.namespace)} className="flex items-center gap-1 text-xs px-2 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded">
                        <Trash2 className="w-3 h-3" /> Flush
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-3">Key Lookup Tool</h2>
        <div className="flex gap-2">
          <input value={keyPattern} onChange={e => setKeyPattern(e.target.value)} placeholder="e.g. session:* or kyc-profiles:AGT-*"
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <button onClick={handleLookup} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
            <Search className="w-4 h-4" /> Lookup
          </button>
        </div>
        {lookupResult && <p className="mt-2 text-sm text-gray-600">{lookupResult}</p>}
      </div>
    </div>
  );
};

export default CacheManagementDashboard;
