import React, { useEffect, useState } from "react";
import { BookOpen, RefreshCw, Award, Users, CheckCircle, Clock } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL =  `${import.meta.env.VITE_CORE_BANKING_URL}/training` || "https://54agent.upi.dev/training";

const MOCK = {
  stats: { totalCourses: 18, totalEnrollments: 1840, completionRate: 78, avgQuizScore: 84 },
  courses: [
    { id: "c1", title: "Agent Banking Fundamentals", category: "onboarding", enrolled: 248, completed: 220, quizScore: 88, mandatory: true, status: "active" },
    { id: "c2", title: "AML/CFT Compliance", category: "compliance", enrolled: 248, completed: 198, quizScore: 82, mandatory: true, status: "active" },
    { id: "c3", title: "POS Operations & Troubleshooting", category: "operations", enrolled: 180, completed: 142, quizScore: 91, mandatory: false, status: "active" },
    { id: "c4", title: "Customer Service Excellence", category: "soft-skills", enrolled: 200, completed: 155, quizScore: 86, mandatory: false, status: "active" },
    { id: "c5", title: "KYC Verification Procedures", category: "compliance", enrolled: 248, completed: 235, quizScore: 90, mandatory: true, status: "active" },
    { id: "c6", title: "Fraud Detection & Prevention", category: "security", enrolled: 248, completed: 178, quizScore: 79, mandatory: true, status: "active" },
  ],
};

export default function AgentTrainingPortal() {
  const [data, setData] = useState<typeof MOCK | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"overview" | "courses">("overview");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/training/api/v1/portal/dashboard`, { headers: getTenantHeadersFromStorage() });
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
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><BookOpen className="w-7 h-7 text-blue-600" />Agent Training & Certification Portal</h1>
          <p className="text-gray-500 text-sm mt-1">Courses, quizzes, and certification tracking</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Courses", value: data.stats.totalCourses, color: "text-blue-600", icon: BookOpen },
          { label: "Total Enrollments", value: data.stats.totalEnrollments.toLocaleString(), color: "text-gray-800", icon: Users },
          { label: "Completion Rate", value: `${data.stats.completionRate}%`, color: "text-emerald-600", icon: CheckCircle },
          { label: "Avg Quiz Score", value: `${data.stats.avgQuizScore}%`, color: "text-amber-600", icon: Award },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Icon className={`w-4 h-4 ${color}`} /><p className="text-xs text-gray-500">{label}</p></div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
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
          {data.courses.slice(0, 4).map(c => {
            const pct = Math.round((c.completed / c.enrolled) * 100);
            return (
              <div key={c.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium text-sm text-gray-800">{c.title}</p>
                  {c.mandatory && <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Mandatory</span>}
                </div>
                <p className="text-xs text-gray-500 mb-2 capitalize">{c.category}</p>
                <div className="w-full bg-gray-100 rounded-full h-2 mb-1">
                  <div className="h-2 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>{c.completed}/{c.enrolled} completed ({pct}%)</span>
                  <span className="text-amber-600">Quiz: {c.quizScore}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === "courses" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">{["Course", "Category", "Enrolled", "Progress", "Quiz Score", "Mandatory"].map(h => <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-gray-50">
              {data.courses.map(c => {
                const pct = Math.round((c.completed / c.enrolled) * 100);
                return (
                  <tr key={c.id} className="hover:bg-gray-50/50">
                    <td className="py-3 px-4 font-medium text-gray-800">{c.title}</td>
                    <td className="py-3 px-4 capitalize text-gray-500">{c.category}</td>
                    <td className="py-3 px-4 text-gray-500">{c.enrolled}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct}%` }} /></div>
                        <span className="text-xs text-gray-500">{pct}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-amber-600 font-medium">{c.quizScore}%</td>
                    <td className="py-3 px-4">{c.mandatory ? <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Yes</span> : <span className="text-xs text-gray-400">No</span>}</td>
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
