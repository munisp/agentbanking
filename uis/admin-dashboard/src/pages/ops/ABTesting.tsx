import { SplitSquareHorizontal, RefreshCw, Plus, Play, Square, TrendingUp, BarChart3 } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface ABTest {
  id: string;
  name: string;
  description: string;
  status: "draft" | "running" | "paused" | "concluded";
  variants: { name: string; allocation: number; conversions: number; visitors: number }[];
  metric: string;
  start_date?: string;
  end_date?: string;
  winner?: string;
}

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600", running: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700", concluded: "bg-purple-100 text-purple-700",
};

const ABTesting: React.FC = () => {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", metric: "conversion_rate" });

  useEffect(() => { fetchTests(); }, []);

  const fetchTests = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/ab-tests`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setTests(Array.isArray(d.tests) ? d.tests : []);  } else { setError("Failed to load A/B tests."); }
    } catch { setError("Failed to load A/B tests."); }
    finally { setLoading(false); }
  };

  const updateStatus = async (id: string, status: string) => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/ab-tests/${id}/status`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchTests();
    } catch (err: any) { alert(err.message); }
  };

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchTests()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <SplitSquareHorizontal className="w-7 h-7 text-indigo-600" /> A/B Testing
          </h1>
          <p className="text-gray-500 text-sm mt-1">Controlled experiments to validate product and UI changes</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
          <Plus className="w-4 h-4" /> New Experiment
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Running", value: tests.filter(t => t.status === "running").length, color: "text-blue-600" },
          { label: "Concluded", value: tests.filter(t => t.status === "concluded").length, color: "text-purple-600" },
          { label: "Draft", value: tests.filter(t => t.status === "draft").length, color: "text-gray-500" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Create A/B Test</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Test Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Primary Metric</label>
              <select value={form.metric} onChange={e => setForm(f => ({ ...f, metric: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="conversion_rate">Conversion Rate</option>
                <option value="click_rate">Click Rate</option>
                <option value="completion_rate">Completion Rate</option>
                <option value="agent_satisfaction">Agent Satisfaction</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div className="flex gap-2">
              <button onClick={async () => {
                try {
                  await fetch(`${CORE_URL}/ops/api/v1/ab-tests`, {
                    method: "POST",
                    headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
                    body: JSON.stringify(form),
                  });
                  setShowForm(false); fetchTests();
                } catch { alert("Failed to create test. Please try again."); }
              }} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">Create</button>
              <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {tests.map(test => (
          <div key={test.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-gray-900">{test.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[test.status]}`}>{test.status}</span>
                  {test.winner && <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full">Winner: {test.winner}</span>}
                </div>
                <p className="text-sm text-gray-500">{test.description}</p>
                <p className="text-xs text-gray-400 mt-1">Metric: <span className="font-medium text-gray-600">{test.metric}</span></p>
              </div>
              <div className="flex items-center gap-2">
                {test.status === "draft" && <button onClick={() => updateStatus(test.id, "running")} className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded flex items-center gap-1"><Play className="w-3 h-3" /> Start</button>}
                {test.status === "running" && <button onClick={() => updateStatus(test.id, "paused")} className="text-xs px-2 py-1 bg-amber-50 text-amber-600 hover:bg-amber-100 rounded flex items-center gap-1"><Square className="w-3 h-3" /> Pause</button>}
                {test.status === "running" && <button onClick={() => updateStatus(test.id, "concluded")} className="text-xs px-2 py-1 bg-purple-50 text-purple-600 hover:bg-purple-100 rounded">Conclude</button>}
                {test.status === "paused" && <button onClick={() => updateStatus(test.id, "running")} className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded flex items-center gap-1"><Play className="w-3 h-3" /> Resume</button>}
              </div>
            </div>
            <div className="space-y-3">
              {test.variants.map(v => {
                const rate = v.visitors > 0 ? ((v.conversions / v.visitors) * 100).toFixed(1) : "0.0";
                const maxVisitors = Math.max(...test.variants.map(vv => vv.visitors), 1);
                return (
                  <div key={v.name}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-gray-700">{v.name}</span>
                      <span className="text-gray-500">{v.visitors.toLocaleString()} visitors · <span className="font-semibold text-indigo-600">{rate}%</span> rate</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${(v.visitors / maxVisitors) * 100}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ABTesting;
