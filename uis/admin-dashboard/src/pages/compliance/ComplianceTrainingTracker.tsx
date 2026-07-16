import React, { useEffect, useState } from "react";
import { BookOpen, RefreshCw, Download, Search, Award, Clock, CheckCircle, AlertTriangle } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const MOCK = {
  totalTrainings: 24, completed: 18, inProgress: 4, overdue: 2,
  avgScore: 84, complianceRate: 91, certificatesActive: 156, expiringIn30Days: 12,
  recent: [
    { agent: "Adebayo Ogundimu", course: "AML Fundamentals", status: "completed", date: "2025-01-20" },
    { agent: "Chioma Nwosu", course: "KYC Procedures v2", status: "completed", date: "2025-01-19" },
    { agent: "Emeka Okafor", course: "CBN Regulation Updates", status: "in_progress", date: "2025-01-18" },
    { agent: "Fatima Ibrahim", course: "AML Fundamentals", status: "overdue", date: "2025-01-01" },
    { agent: "Seun Bakare", course: "Data Privacy & NDPR", status: "completed", date: "2025-01-17" },
  ],
};

export default function ComplianceTrainingTracker() {
  const [data, setData] = useState<typeof MOCK | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/training/tracker`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) setData(await res.json());
      else setData(MOCK);
    } catch { setData(MOCK); }
    finally { setLoading(false); }
  };

  if (loading || !data) return <div className="p-8 text-center text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto" /></div>;

  const filtered = data.recent.filter(r => !search || r.agent.toLowerCase().includes(search.toLowerCase()) || r.course.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><BookOpen className="w-7 h-7 text-blue-600" />Compliance Training Tracker</h1>
          <p className="text-gray-500 text-sm mt-1">Mandatory training completion tracking and certification management</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56" />
          </div>
          <button onClick={load} className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />Refresh
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <Download className="w-4 h-4" />Export
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Trainings", value: data.totalTrainings, color: "text-blue-600", icon: BookOpen },
          { label: "Completed", value: data.completed, color: "text-emerald-600", icon: CheckCircle },
          { label: "In Progress", value: data.inProgress, color: "text-amber-600", icon: Clock },
          { label: "Overdue", value: data.overdue, color: "text-red-600", icon: AlertTriangle },
          { label: "Avg Score", value: `${data.avgScore}%`, color: "text-purple-600", icon: Award },
          { label: "Compliance %", value: `${data.complianceRate}%`, color: "text-cyan-600", icon: CheckCircle },
          { label: "Active Certs", value: data.certificatesActive, color: "text-indigo-600", icon: Award },
          { label: "Expiring Soon", value: data.expiringIn30Days, color: "text-orange-600", icon: Clock },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1">
              <Icon className={`w-4 h-4 ${color}`} />
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Recent Activity</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Agent", "Course", "Status", "Date"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50/50">
                  <td className="py-3 px-4 font-medium text-gray-800">{r.agent}</td>
                  <td className="py-3 px-4 text-gray-600">{r.course}</td>
                  <td className="py-3 px-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                      r.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                      r.status === "in_progress" ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>{r.status.replace("_", " ")}</span>
                  </td>
                  <td className="py-3 px-4 text-gray-500 text-xs">{new Date(r.date).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
