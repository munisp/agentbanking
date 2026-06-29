import { GitBranch, RefreshCw, TrendingUp, AlertTriangle, CheckCircle, XCircle, ChevronUp, ChevronDown } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface CanaryDeploy {
  id: string;
  service: string;
  version: string;
  canary_percentage: number;
  status: "running" | "promoting" | "rolling_back" | "completed" | "failed";
  error_rate_baseline: number;
  error_rate_canary: number;
  latency_baseline_ms: number;
  latency_canary_ms: number;
  started_at: string;
  promoted_at?: string;
}

const MOCK_DEPLOYS: CanaryDeploy[] = [
  { id: "can-001", service: "payment-hub", version: "v2.14.1", canary_percentage: 10, status: "running", error_rate_baseline: 0.12, error_rate_canary: 0.09, latency_baseline_ms: 142, latency_canary_ms: 118, started_at: "2024-11-29 10:00" },
  { id: "can-002", service: "auth-service", version: "v1.8.3", canary_percentage: 25, status: "promoting", error_rate_baseline: 0.05, error_rate_canary: 0.04, latency_baseline_ms: 88, latency_canary_ms: 72, started_at: "2024-11-28 14:00" },
  { id: "can-003", service: "float-management", version: "v3.2.0", canary_percentage: 5, status: "rolling_back", error_rate_baseline: 0.08, error_rate_canary: 1.45, latency_baseline_ms: 220, latency_canary_ms: 890, started_at: "2024-11-29 08:30" },
  { id: "can-004", service: "notification-service", version: "v1.5.2", canary_percentage: 100, status: "completed", error_rate_baseline: 0.15, error_rate_canary: 0.12, latency_baseline_ms: 95, latency_canary_ms: 88, started_at: "2024-11-27 09:00", promoted_at: "2024-11-28 09:00" },
];

const STATUS_STYLES: Record<string, string> = {
  running: "bg-blue-100 text-blue-700", promoting: "bg-emerald-100 text-emerald-700",
  rolling_back: "bg-red-100 text-red-700", completed: "bg-gray-100 text-gray-600",
  failed: "bg-red-100 text-red-800",
};

const CanaryRelease: React.FC = () => {
  const [deploys, setDeploys] = useState<CanaryDeploy[]>([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState<string | null>(null);

  

  useEffect(() => { fetchDeploys(); }, []);

  const fetchDeploys = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/canary-releases`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setDeploys(Array.isArray(d.releases) ? d.releases : MOCK_DEPLOYS); }
    } catch { }
    finally { setLoading(false); }
  };

  const adjustCanary = async (id: string, action: "promote" | "rollback" | "increase" | "decrease") => {
    setUpdating(id);
    try {
      await fetch(`${CORE_URL}/ops/api/v1/canary-releases/${id}/${action}`, { method: "POST", headers: getTenantHeadersFromStorage() });
      fetchDeploys();
    } catch (err: any) { alert(err.message); }
    finally { setUpdating(null); }
  };

  const active = deploys.filter(d => d.status === "running" || d.status === "promoting").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch className="w-7 h-7 text-teal-600" /> Canary Releases
          </h1>
          <p className="text-gray-500 text-sm mt-1">Progressive traffic shifting for safe production deployments</p>
        </div>
        <button onClick={fetchDeploys} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active Canaries", value: active, color: "text-blue-600" },
          { label: "Rolling Back", value: deploys.filter(d => d.status === "rolling_back").length, color: "text-red-600" },
          { label: "Completed Today", value: deploys.filter(d => d.status === "completed").length, color: "text-emerald-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        {deploys.map(d => {
          const errorDelta = d.error_rate_canary - d.error_rate_baseline;
          const latencyDelta = d.latency_canary_ms - d.latency_baseline_ms;
          const isHealthy = errorDelta <= 0.2 && latencyDelta <= 50;
          return (
            <div key={d.id} className={`bg-white border rounded-xl p-5 shadow-sm ${d.status === "rolling_back" ? "border-red-300" : "border-gray-200"}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-gray-900">{d.service}</h3>
                    <code className="text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">{d.version}</code>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[d.status]}`}>{d.status.replace("_", " ")}</span>
                    {!isHealthy && d.status === "running" && (
                      <span className="flex items-center gap-1 text-xs text-red-600"><AlertTriangle className="w-3 h-3" />Unhealthy</span>
                    )}
                  </div>
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>Canary traffic: {d.canary_percentage}%</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div className="bg-teal-500 h-2 rounded-full transition-all" style={{ width: `${d.canary_percentage}%` }} />
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-4 mt-3 text-xs">
                    {[
                      { label: "Error Rate (baseline)", value: `${d.error_rate_baseline}%`, neutral: true },
                      { label: "Error Rate (canary)", value: `${d.error_rate_canary}%`, good: d.error_rate_canary <= d.error_rate_baseline },
                      { label: "Latency (baseline)", value: `${d.latency_baseline_ms}ms`, neutral: true },
                      { label: "Latency (canary)", value: `${d.latency_canary_ms}ms`, good: d.latency_canary_ms <= d.latency_baseline_ms },
                    ].map(({ label, value, neutral, good }) => (
                      <div key={label} className="bg-gray-50 rounded-lg p-2">
                        <p className="text-gray-400">{label}</p>
                        <p className={`font-bold mt-0.5 ${neutral ? "text-gray-700" : good ? "text-emerald-600" : "text-red-600"}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  {d.status === "running" && (
                    <>
                      <button onClick={() => adjustCanary(d.id, "increase")} disabled={updating === d.id} className="text-xs px-2 py-1 bg-teal-50 text-teal-600 hover:bg-teal-100 rounded flex items-center gap-1"><ChevronUp className="w-3 h-3" />Increase</button>
                      <button onClick={() => adjustCanary(d.id, "promote")} disabled={updating === d.id} className="text-xs px-2 py-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 rounded flex items-center gap-1"><CheckCircle className="w-3 h-3" />Promote</button>
                      <button onClick={() => adjustCanary(d.id, "rollback")} disabled={updating === d.id} className="text-xs px-2 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded flex items-center gap-1"><XCircle className="w-3 h-3" />Rollback</button>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CanaryRelease;
