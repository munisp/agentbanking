import { useEffect, useState } from "react";
import { BookOpen, RefreshCw, Award, Users, TrendingUp, CheckCircle, Plus } from "lucide-react";
import { trainingApi } from "../../utils/api";

export default function AgentTrainingPage() {
  const [courses, setCourses] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [coursesData, statsData] = await Promise.allSettled([
        trainingApi.listCourses(0, 50),
        trainingApi.getStats(),
      ]);
      if (coursesData.status === "fulfilled") {
        setCourses(Array.isArray(coursesData.value) ? coursesData.value : []);
      }
      if (statsData.status === "fulfilled") setStats(statsData.value);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load training data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const statCards = [
    { label: "Total Courses", value: stats?.total_courses ?? courses.length, icon: BookOpen, color: "text-blue-500" },
    { label: "Completion Rate", value: `${Math.round((stats?.avg_pass_rate ?? 0) * 100) / 100}%`, icon: TrendingUp, color: "text-green-500" },
    { label: "Certificates Issued", value: stats?.total_certificates ?? 0, icon: Award, color: "text-yellow-500" },
    { label: "Mandatory Courses", value: stats?.mandatory_courses ?? courses.filter((c) => c.is_mandatory).length, icon: CheckCircle, color: "text-red-500" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-blue-500" /> Agent Training Academy
          </h1>
          <p className="text-muted-foreground">Courses, certifications, and CBN compliance training</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-accent text-sm"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            <Plus className="h-4 w-4" /> Create Course
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <div key={s.label} className="bg-white border rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <s.icon className={`h-5 w-5 ${s.color}`} />
              <p className="text-sm text-muted-foreground">{s.label}</p>
            </div>
            {loading ? (
              <div className="h-8 bg-gray-200 rounded animate-pulse" />
            ) : (
              <p className="text-2xl font-bold">{s.value}</p>
            )}
          </div>
        ))}
      </div>

      {/* Courses Table */}
      <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
        <div className="p-5 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Training Courses</h2>
          <span className="text-sm text-muted-foreground">{courses.length} courses</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3 font-medium">Course</th>
                <th className="text-left p-3 font-medium">Code</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Pass Threshold</th>
                <th className="text-left p-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-t">
                      <td colSpan={6} className="p-3">
                        <div className="h-8 bg-gray-200 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : courses.length === 0
                ? (
                  <tr>
                    <td colSpan={6} className="p-12 text-center text-muted-foreground">
                      No courses created yet. Click "Create Course" to get started.
                    </td>
                  </tr>
                )
                : courses.map((c: any) => (
                    <tr key={c.id} className="border-t hover:bg-gray-50">
                      <td className="p-3">
                        <div className="font-medium">{c.title ?? c.name}</div>
                        <div className="text-xs text-muted-foreground line-clamp-1">{c.description}</div>
                      </td>
                      <td className="p-3 font-mono text-xs">{c.code ?? "—"}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${c.is_mandatory ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"}`}>
                          {c.is_mandatory ? "Mandatory" : "Optional"}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${c.status === "published" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}>
                          {c.status ?? "draft"}
                        </span>
                      </td>
                      <td className="p-3">{c.passing_threshold ?? 70}%</td>
                      <td className="p-3">
                        <div className="flex gap-2">
                          {c.status !== "published" && (
                            <button
                              onClick={async () => {
                                try {
                                  await trainingApi.publishCourse(c.id);
                                  loadData();
                                } catch {}
                              }}
                              className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                            >
                              Publish
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* CBN Mandatory Courses note */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <CheckCircle className="h-5 w-5 text-blue-600 mt-0.5" />
          <div>
            <p className="font-medium text-blue-800">CBN Mandatory Training Codes</p>
            <p className="text-sm text-blue-700 mt-1">
              The following course codes are required by CBN regulations:
              <span className="font-mono ml-2">CBN-AML-001 · CBN-KYC-001 · CBN-FRAUD-001 · CBN-DATA-001 · CBN-AGENT-001</span>
            </p>
            <p className="text-xs text-blue-600 mt-1">
              Agents must complete all mandatory courses to maintain active status. Certificates expire after 365 days.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
