import { Zap, RefreshCw, Play, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface ChaosExperiment {
  id: string;
  name: string;
  type: "latency" | "fault-injection" | "pod-kill" | "network-partition";
  targetService: string;
  status: "idle" | "running" | "completed";
  lastRun: string;
  blastRadius: "Low" | "Med" | "High";
}

const TYPE_STYLES: Record<string, string> = {
  latency: "bg-amber-100 text-amber-700",
  "fault-injection": "bg-red-100 text-red-700",
  "pod-kill": "bg-orange-100 text-orange-700",
  "network-partition": "bg-purple-100 text-purple-700",
};

const BLAST_STYLES: Record<string, string> = {
  Low: "bg-green-100 text-green-700",
  Med: "bg-amber-100 text-amber-700",
  High: "bg-red-100 text-red-700",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  idle: <Clock className="w-4 h-4 text-gray-400" />,
  running: <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="w-4 h-4 text-green-500" />,
};

const ChaosEngineeringConsole: React.FC = () => {
  const [experiments, setExperiments] = useState<ChaosExperiment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [activeExp, setActiveExp] = useState<ChaosExperiment | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logLines]);

  useEffect(() => { fetchExperiments(); }, []);

  const fetchExperiments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/chaos/experiments`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setExperiments(Array.isArray(d.experiments) ? d.experiments : []); }
      else { setError("Failed to load chaos experiments."); }
    } catch { setError("Failed to load chaos experiments."); }
    finally { setLoading(false); }
  };

  const runExperiment = async (exp: ChaosExperiment) => {
    setConfirmId(null);
    setActiveExp({ ...exp, status: "running" });
    setLogLines([]);
    setExperiments(prev => prev.map(e => e.id === exp.id ? { ...e, status: "running" } : e));
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/chaos/experiments/${exp.id}/run`, { method: "POST", headers: getTenantHeadersFromStorage() });
      if (!res.ok) throw new Error();
      const d = await res.json().catch(() => ({}));
      // Render only server-reported log lines — never simulated output.
      if (Array.isArray(d.logs)) setLogLines(d.logs);
      setExperiments(prev => prev.map(e => e.id === exp.id ? { ...e, status: "completed" } : e));
      setActiveExp(prev => prev ? { ...prev, status: "completed" } : null);
    } catch {
      setExperiments(prev => prev.map(e => e.id === exp.id ? { ...e, status: "idle" } : e));
      setActiveExp(prev => prev ? { ...prev, status: "idle" } : null);
      setError("Failed to run experiment. No experiment was executed.");
    }
  };

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchExperiments()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Zap className="w-7 h-7 text-red-500" /> Chaos Engineering Console
          </h1>
          <p className="text-gray-500 text-sm mt-1">Run controlled failure experiments to validate system resilience</p>
        </div>
        <button onClick={fetchExperiments} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Idle", value: experiments.filter(e => e.status === "idle").length, color: "text-gray-600" },
          { label: "Running", value: experiments.filter(e => e.status === "running").length, color: "text-blue-600" },
          { label: "Completed", value: experiments.filter(e => e.status === "completed").length, color: "text-green-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Experiments</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="pb-3 pr-4">Name</th>
                <th className="pb-3 pr-4">Type</th>
                <th className="pb-3 pr-4">Target Service</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Last Run</th>
                <th className="pb-3 pr-4">Blast Radius</th>
                <th className="pb-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map(exp => (
                <tr key={exp.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4 font-medium text-gray-800">{exp.name}</td>
                  <td className="py-3 pr-4"><span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_STYLES[exp.type]}`}>{exp.type}</span></td>
                  <td className="py-3 pr-4 text-gray-500 font-mono text-xs">{exp.targetService}</td>
                  <td className="py-3 pr-4"><span className="flex items-center gap-1">{STATUS_ICON[exp.status]}<span className="capitalize text-gray-600">{exp.status}</span></span></td>
                  <td className="py-3 pr-4 text-gray-500">{exp.lastRun}</td>
                  <td className="py-3 pr-4"><span className={`text-xs px-2 py-0.5 rounded-full ${BLAST_STYLES[exp.blastRadius]}`}>{exp.blastRadius}</span></td>
                  <td className="py-3">
                    {exp.status !== "running" && (
                      <button onClick={() => setConfirmId(exp.id)} className="flex items-center gap-1 text-xs px-3 py-1 bg-red-50 hover:bg-red-100 text-red-600 rounded">
                        <Play className="w-3 h-3" /> Run
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {confirmId && (() => {
        const exp = experiments.find(e => e.id === confirmId)!;
        return (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 shadow-xl w-full max-w-md">
              <div className="flex items-center gap-3 mb-4">
                <AlertTriangle className="w-6 h-6 text-amber-500" />
                <h3 className="font-semibold text-gray-900">Confirm Experiment</h3>
              </div>
              <p className="text-sm text-gray-600 mb-2">You are about to run <span className="font-semibold">{exp.name}</span> targeting <span className="font-mono text-xs bg-gray-100 px-1 rounded">{exp.targetService}</span>.</p>
              <p className="text-sm text-gray-600 mb-6">Blast radius: <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${BLAST_STYLES[exp.blastRadius]}`}>{exp.blastRadius}</span>. This may cause real service disruption.</p>
              <div className="flex gap-3">
                <button onClick={() => runExperiment(exp)} className="flex-1 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">Confirm &amp; Run</button>
                <button onClick={() => setConfirmId(null)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
              </div>
            </div>
          </div>
        );
      })()}

      {activeExp && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800 flex items-center gap-2">
              {STATUS_ICON[activeExp.status]} Live Feed — {activeExp.name}
            </h2>
            <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${activeExp.status === "running" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"}`}>{activeExp.status}</span>
          </div>
          <div ref={logRef} className="bg-gray-900 rounded-lg p-4 h-48 overflow-y-auto font-mono text-xs text-green-400 space-y-1">
            {logLines.map((line, i) => <div key={i}>{line}</div>)}
            {activeExp.status === "running" && <div className="animate-pulse">▋</div>}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChaosEngineeringConsole;
