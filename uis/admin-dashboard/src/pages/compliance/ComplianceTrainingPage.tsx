import { BookOpen, RefreshCw, Award, Clock, CheckCircle, AlertCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const MOCK = {
  stats: { totalTrainings: 24, completed: 18, inProgress: 4, overdue: 2, avgScore: 84, complianceRate: 91 },
  courses: [
    { id: "c1", name: "AML Fundamentals", category: "mandatory", status: "active", enrolled: 142, completed: 128, dueDate: "2025-03-31" },
    { id: "c2", name: "KYC Procedures v2", category: "mandatory", status: "active", enrolled: 142, completed: 135, dueDate: "2025-02-28" },
    { id: "c3", name: "Fraud Prevention 101", category: "optional", status: "active", enrolled: 89, completed: 67, dueDate: "2025-04-30" },
    { id: "c4", name: "CBN Regulation Updates", category: "mandatory", status: "overdue", enrolled: 142, completed: 72, dueDate: "2025-01-15" },
    { id: "c5", name: "Data Privacy & NDPR", category: "mandatory", status: "active", enrolled: 142, completed: 110, dueDate: "2025-05-31" },
  ],
};

export default function ComplianceTrainingPage() {
  const [data, setData] = useState<typeof MOCK | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"overview" | "courses">("overview");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/training/dashboard`, { headers: getTenantHeadersFromStorage() });
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
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><BookOpen className="w-7 h-7 text-blue-600" />Compliance Training</h1>
          <p className="text-gray-500 text-sm mt-1">Agent certification tracking and renewal management</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Trainings", value: data.stats.totalTrainings, color: "text-blue-600" },
          { label: "Completed", value: data.stats.completed, color: "text-emerald-600" },
          { label: "Overdue", value: data.stats.overdue, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="flex border-b border-gray-200 gap-1">
        {(["overview", "courses"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-colors ${tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>{t}</button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: "Compliance Rate", value: `${data.stats.complianceRate}%`, icon: CheckCircle, color: "text-emerald-600" },
            { label: "Avg Score", value: `${data.stats.avgScore}%`, icon: Award, color: "text-blue-600" },
            { label: "In Progress", value: data.stats.inProgress, icon: Clock, color: "text-amber-600" },
            { label: "Overdue", value: data.stats.overdue, icon: AlertCircle, color: "text-red-600" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-4">
              <Icon className={`w-8 h-8 ${color}`} />
              <div>
                <p className="text-xs text-gray-500">{label}</p>
                <p className={`text-xl font-bold ${color}`}>{value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "courses" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Course", "Category", "Enrolled", "Progress", "Due Date", "Status"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {data.courses.map(c => {
                const pct = Math.round((c.completed / c.enrolled) * 100);
                return (
                  <tr key={c.id} className="hover:bg-gray-50/50">
                    <td className="py-3 px-4 font-medium text-gray-800">{c.name}</td>
                    <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${c.category === "mandatory" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>{c.category}</span></td>
                    <td className="py-3 px-4 text-gray-500">{c.enrolled}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct}%` }} /></div>
                        <span className="text-xs text-gray-500">{pct}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-500">{new Date(c.dueDate).toLocaleDateString()}</td>
                    <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${c.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{c.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
