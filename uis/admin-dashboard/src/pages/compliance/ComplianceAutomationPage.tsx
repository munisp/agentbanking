import { ShieldCheck, RefreshCw } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const MOCK = {
  overallScore: 87,
  frameworks: [
    { name: "CBN AML/CFT", compliance: 92, controls: 40, passing: 37, failing: 3 },
    { name: "NDPR", compliance: 85, controls: 28, passing: 24, failing: 4 },
    { name: "PCI-DSS Lite", compliance: 78, controls: 35, passing: 27, failing: 8 },
    { name: "ISO 27001", compliance: 90, controls: 50, passing: 45, failing: 5 },
  ],
  upcomingAudits: [
    { framework: "CBN AML/CFT", scheduledDate: "2025-01-15", auditor: "KPMG Nigeria", status: "scheduled" },
    { framework: "NDPR", scheduledDate: "2025-02-10", auditor: "Internal", status: "pending" },
  ],
  policies: [
    { id: "p1", name: "AML Policy v3", version: 3, status: "active", lastReview: "2024-10-01" },
    { id: "p2", name: "Data Retention Policy", version: 2, status: "active", lastReview: "2024-09-15" },
    { id: "p3", name: "KYC Onboarding Policy", version: 4, status: "under_review", lastReview: "2024-11-01" },
  ],
};

export default function ComplianceAutomationPage() {
  const [data, setData] = useState<typeof MOCK | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/automation/dashboard`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) setData(await res.json());
      else setData(MOCK);
    } catch { setData(MOCK); }
    finally { setLoading(false); }
  };

  if (loading || !data) return <div className="p-8 text-center text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto" /></div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-blue-600" />Compliance Automation</h1>
          <p className="text-gray-500 text-sm mt-1">Framework adherence, policy status and upcoming audit schedule</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Overall Score", value: `${data.overallScore}%`, color: data.overallScore >= 85 ? "text-emerald-600" : "text-amber-600" },
          { label: "Active Policies", value: data.policies.length, color: "text-blue-600" },
          { label: "Frameworks", value: data.frameworks.length, color: "text-purple-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Frameworks</h2>
        <div className="grid grid-cols-2 gap-4">
          {data.frameworks.map(f => (
            <div key={f.name} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium text-sm text-gray-800">{f.name}</p>
                <span className={`text-lg font-bold ${f.compliance >= 90 ? "text-emerald-600" : f.compliance >= 70 ? "text-amber-600" : "text-red-600"}`}>{f.compliance}%</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2 mb-2">
                <div className={`h-2 rounded-full ${f.compliance >= 90 ? "bg-emerald-500" : f.compliance >= 70 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${f.compliance}%` }} />
              </div>
              <p className="text-xs text-gray-400">{f.controls} controls · <span className="text-emerald-600">{f.passing} passing</span> · <span className="text-red-500">{f.failing} failing</span></p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Upcoming Audits</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Framework","Scheduled","Auditor","Status"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {data.upcomingAudits.map((a, i) => (
                <tr key={i} className="hover:bg-gray-50/50">
                  <td className="py-3 px-4 font-medium">{a.framework}</td>
                  <td className="py-3 px-4 text-gray-500">{new Date(a.scheduledDate).toLocaleDateString()}</td>
                  <td className="py-3 px-4 text-gray-600">{a.auditor}</td>
                  <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${a.status === "scheduled" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{a.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Policies</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Policy","Version","Status","Last Review"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {data.policies.map(p => (
                <tr key={p.id} className="hover:bg-gray-50/50">
                  <td className="py-3 px-4 font-medium">{p.name}</td>
                  <td className="py-3 px-4 text-gray-500">v{p.version}</td>
                  <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${p.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{p.status.replace("_", " ")}</span></td>
                  <td className="py-3 px-4 text-gray-500">{new Date(p.lastReview).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
