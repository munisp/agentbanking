import {
  Award,
  BookOpen,
  CheckCircle,
  Clock,
  PlayCircle,
  RefreshCw,
  Shield,
  Star,
  XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { trainingApi } from "../utils/api";

export default function Training() {
  const agentId = localStorage.getItem("agentId") || localStorage.getItem("keycloakId");

  const [dashboard, setDashboard] = useState(null);
  const [courses, setCourses] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [complianceStatus, setComplianceStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("courses");

  const loadData = async () => {
    if (!agentId) {
      setError("Agent ID not found. Please log in again.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [dashData, coursesData, certsData, compData] = await Promise.allSettled([
        trainingApi.getAgentDashboard(agentId),
        trainingApi.listCourses(0, 50),
        trainingApi.getCertificates(agentId),
        trainingApi.getComplianceStatus(agentId),
      ]);
      if (dashData.status === "fulfilled") setDashboard(dashData.value);
      if (coursesData.status === "fulfilled") setCourses(Array.isArray(coursesData.value) ? coursesData.value : []);
      if (certsData.status === "fulfilled") setCertificates(Array.isArray(certsData.value) ? certsData.value : []);
      if (compData.status === "fulfilled") setComplianceStatus(compData.value);
    } catch (e) {
      setError(e?.message ?? "Failed to load training data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const enrollments = dashboard?.enrollments ?? [];
  const completedCount = enrollments.filter((e) => e.status === "completed").length;
  const inProgressCount = enrollments.filter((e) => e.status === "in_progress").length;
  const isCompliant = complianceStatus?.is_compliant ?? false;

  const handleEnroll = async (courseId) => {
    if (!agentId) return;
    try {
      await trainingApi.enrollCourse(agentId, courseId);
      loadData();
    } catch (e) {
      alert(e?.message ?? "Enrollment failed");
    }
  };

  const handleEnrollMandatory = async () => {
    if (!agentId) return;
    try {
      await trainingApi.enrollMandatory(agentId);
      loadData();
    } catch (e) {
      alert(e?.message ?? "Enrollment failed");
    }
  };

  const getEnrollment = (courseId) =>
    enrollments.find((e) => e.course_id === courseId || e.course?.id === courseId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-blue-600" /> Training Academy
          </h1>
          <p className="text-gray-500 text-sm mt-1">Complete your CBN-required courses and earn certifications</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {/* Compliance Banner */}
      {!loading && complianceStatus && (
        <div className={`rounded-xl p-4 flex items-center gap-3 ${isCompliant ? "bg-green-50 border border-green-200" : "bg-yellow-50 border border-yellow-200"}`}>
          {isCompliant ? (
            <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
          ) : (
            <Shield className="w-6 h-6 text-yellow-600 flex-shrink-0" />
          )}
          <div className="flex-1">
            <p className={`font-medium ${isCompliant ? "text-green-800" : "text-yellow-800"}`}>
              {isCompliant ? "CBN Compliance: All mandatory training complete" : "Action Required: Incomplete mandatory CBN training"}
            </p>
            {!isCompliant && complianceStatus.missing_courses?.length > 0 && (
              <p className="text-sm text-yellow-700 mt-0.5">
                Missing: {complianceStatus.missing_courses.join(", ")}
              </p>
            )}
          </div>
          {!isCompliant && (
            <button
              onClick={handleEnrollMandatory}
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm font-medium hover:bg-yellow-700 flex-shrink-0"
            >
              Enroll Now
            </button>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Enrolled", value: enrollments.length, icon: BookOpen, color: "text-blue-600 bg-blue-50" },
          { label: "Completed", value: completedCount, icon: CheckCircle, color: "text-green-600 bg-green-50" },
          { label: "In Progress", value: inProgressCount, icon: Clock, color: "text-yellow-600 bg-yellow-50" },
          { label: "Certificates", value: certificates.length, icon: Award, color: "text-purple-600 bg-purple-50" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className={`w-10 h-10 rounded-lg ${s.color} flex items-center justify-center mb-3`}>
              <s.icon className="w-5 h-5" />
            </div>
            {loading ? (
              <div className="h-7 bg-gray-200 rounded animate-pulse mb-1" />
            ) : (
              <p className="text-2xl font-bold text-gray-900">{s.value}</p>
            )}
            <p className="text-sm text-gray-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {[
          { key: "courses", label: "Available Courses" },
          { key: "my-courses", label: "My Courses" },
          { key: "certificates", label: "Certificates" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Available Courses */}
      {activeTab === "courses" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="bg-white border border-gray-200 rounded-xl p-5">
                  <div className="h-24 bg-gray-200 rounded animate-pulse" />
                </div>
              ))
            : courses.length === 0
            ? (
              <div className="col-span-2 bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
                <BookOpen className="w-12 h-12 mx-auto mb-3" />
                <p>No courses available yet</p>
              </div>
            )
            : courses.map((course) => {
                const enrollment = getEnrollment(course.id);
                return (
                  <div key={course.id} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        {course.is_mandatory && (
                          <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-medium">Mandatory</span>
                        )}
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full font-medium font-mono">{course.code}</span>
                      </div>
                      {enrollment ? (
                        <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                          enrollment.status === "completed" ? "bg-green-100 text-green-700" :
                          enrollment.status === "in_progress" ? "bg-yellow-100 text-yellow-700" :
                          "bg-gray-100 text-gray-700"
                        }`}>
                          {enrollment.status}
                        </span>
                      ) : (
                        <span className={`w-2 h-2 rounded-full ${course.status === "published" ? "bg-green-500" : "bg-gray-400"}`} />
                      )}
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">{course.title}</h3>
                    <p className="text-sm text-gray-500 mb-4 line-clamp-2">{course.description}</p>
                    {enrollment && enrollment.progress_pct != null && (
                      <div className="mb-4">
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                          <span>Progress</span>
                          <span>{Math.round(enrollment.progress_pct)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${enrollment.progress_pct}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Pass: {course.passing_threshold ?? 70}%</span>
                      {!enrollment ? (
                        <button
                          onClick={() => handleEnroll(course.id)}
                          disabled={course.status !== "published"}
                          className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <PlayCircle className="w-4 h-4" /> Enroll
                        </button>
                      ) : enrollment.status === "completed" ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> Completed
                        </span>
                      ) : (
                        <button className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700">
                          <PlayCircle className="w-4 h-4" /> Continue
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
        </div>
      )}

      {/* My Courses */}
      {activeTab === "my-courses" && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left p-4 font-medium text-gray-700">Course</th>
                <th className="text-left p-4 font-medium text-gray-700">Status</th>
                <th className="text-left p-4 font-medium text-gray-700">Progress</th>
                <th className="text-left p-4 font-medium text-gray-700">Enrolled</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="border-b">
                      <td colSpan={4} className="p-4"><div className="h-8 bg-gray-200 rounded animate-pulse" /></td>
                    </tr>
                  ))
                : enrollments.length === 0
                ? (
                  <tr>
                    <td colSpan={4} className="p-12 text-center text-gray-400">
                      You haven't enrolled in any courses yet
                    </td>
                  </tr>
                )
                : enrollments.map((e) => (
                    <tr key={e.id ?? e.course_id} className="border-b hover:bg-gray-50">
                      <td className="p-4 font-medium text-gray-900">{e.course?.title ?? e.course_id ?? "—"}</td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          e.status === "completed" ? "bg-green-100 text-green-700" :
                          e.status === "in_progress" ? "bg-yellow-100 text-yellow-700" :
                          "bg-gray-100 text-gray-700"
                        }`}>
                          {e.status}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className="w-24 bg-gray-200 rounded-full h-2">
                            <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${e.progress_pct ?? 0}%` }} />
                          </div>
                          <span className="text-xs text-gray-500">{Math.round(e.progress_pct ?? 0)}%</span>
                        </div>
                      </td>
                      <td className="p-4 text-gray-500">
                        {e.enrolled_at ? new Date(e.enrolled_at).toLocaleDateString() : "—"}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Certificates */}
      {activeTab === "certificates" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="bg-white border border-gray-200 rounded-xl p-5">
                  <div className="h-24 bg-gray-200 rounded animate-pulse" />
                </div>
              ))
            : certificates.length === 0
            ? (
              <div className="col-span-2 bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
                <Award className="w-12 h-12 mx-auto mb-3" />
                <p>No certificates yet. Complete a course to earn one.</p>
              </div>
            )
            : certificates.map((cert) => {
                const isExpired = cert.expires_at && new Date(cert.expires_at) < new Date();
                return (
                  <div key={cert.id} className="bg-white border border-gray-200 rounded-xl p-5">
                    <div className="flex items-start gap-4">
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${isExpired ? "bg-red-100" : "bg-yellow-100"}`}>
                        {isExpired ? <XCircle className="w-6 h-6 text-red-600" /> : <Award className="w-6 h-6 text-yellow-600" />}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900">{cert.course?.title ?? `Certificate ${cert.id?.slice(0, 8)}`}</h3>
                        <p className="text-xs text-gray-500 mt-0.5 font-mono">{cert.certificate_number}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                          <span>Issued: {cert.issued_at ? new Date(cert.issued_at).toLocaleDateString() : "—"}</span>
                          <span>Expires: {cert.expires_at ? new Date(cert.expires_at).toLocaleDateString() : "Never"}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                          <span className="text-xs text-gray-600">Score: {cert.score ?? "—"}%</span>
                        </div>
                      </div>
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium flex-shrink-0 ${isExpired ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                        {isExpired ? "Expired" : "Valid"}
                      </span>
                    </div>
                  </div>
                );
              })}
        </div>
      )}
    </div>
  );
}
