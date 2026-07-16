import React, { useEffect, useState } from "react";
import { BookOpen, RefreshCw, Download, Search, Award, Users, CheckCircle, Clock } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = `${import.meta.env.VITE_CORE_BANKING_URL}/training` || "https://54agent.upi.dev/training";

const MOCK = {
  totalCourses: 18, totalEnrolled: 1840, totalCompleted: 1430, avgPassRate: 86,
  mandatoryCourses: 6, certificationsIssued: 980, complianceTrainingRate: 92, avgCompletionTime: "4.2h",
  courses: [
    { id: "c1", title: "Agent Banking Fundamentals", type: "onboarding", enrolled: 248, completed: 220, passRate: 91, certified: true },
    { id: "c2", title: "AML/CFT for Agents", type: "compliance", enrolled: 248, completed: 198, passRate: 84, certified: true },
    { id: "c3", title: "POS Troubleshooting Guide", type: "operations", enrolled: 180, completed: 142, passRate: 88, certified: false },
    { id: "c4", title: "Fraud Prevention Essentials", type: "security", enrolled: 248, completed: 182, passRate: 80, certified: true },
    { id: "c5", title: "Customer Service Pro", type: "soft-skills", enrolled: 200, completed: 155, passRate: 94, certified: false },
  ],
};

export default function AgentTrainingAcademy() {
  const [data, setData] = useState<typeof MOCK | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/training/api/v1/academy/dashboard`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) setData(await res.json());
      else setData(MOCK);
    } catch { setData(MOCK); }
    finally { setLoading(false); }
  };

  if (loading || !data) return <div className="p-8 text-center text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto" /></div>;

  const filtered = data.courses.filter(c => !search || c.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><BookOpen className="w-7 h-7 text-blue-600" />Training Academy</h1>
          <p className="text-gray-500 text-sm mt-1">LMS with course management, certification tracking, and compliance training</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Search courses..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56" />
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
          { label: "Courses", value: data.totalCourses, color: "text-blue-600", icon: BookOpen },
          { label: "Enrolled", value: data.totalEnrolled.toLocaleString(), color: "text-gray-800", icon: Users },
          { label: "Completed", value: data.totalCompleted.toLocaleString(), color: "text-emerald-600", icon: CheckCircle },
          { label: "Pass Rate %", value: `${data.avgPassRate}%`, color: "text-amber-600", icon: Award },
          { label: "Mandatory", value: data.mandatoryCourses, color: "text-red-600", icon: BookOpen },
          { label: "Certifications", value: data.certificationsIssued, color: "text-purple-600", icon: Award },
          { label: "Compliance %", value: `${data.complianceTrainingRate}%`, color: "text-cyan-600", icon: CheckCircle },
          { label: "Avg Time", value: data.avgCompletionTime, color: "text-indigo-600", icon: Clock },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><p className="text-xs text-gray-500">{label}</p></div>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Courses</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Course", "Type", "Enrolled", "Progress", "Pass Rate", "Certified"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(c => {
                const pct = Math.round((c.completed / c.enrolled) * 100);
                return (
                  <tr key={c.id} className="hover:bg-gray-50/50">
                    <td className="py-3 px-4 font-medium text-gray-800">{c.title}</td>
                    <td className="py-3 px-4 capitalize text-gray-500">{c.type}</td>
                    <td className="py-3 px-4 text-gray-500">{c.enrolled}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct}%` }} /></div>
                        <span className="text-xs text-gray-500">{pct}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 font-medium text-amber-600">{c.passRate}%</td>
                    <td className="py-3 px-4">{c.certified ? <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Yes</span> : <span className="text-xs text-gray-400">No</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
