import { FileText, RefreshCw, Download, Clock, ChevronDown } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface ReportEntry {
  id: string;
  name: string;
  framework: string;
  period: string;
  status: string;
  generatedAt: string | null;
  size: string | null;
}

interface DashboardData {
  stats: { totalReports: number; cbnReports: number; ndprReports: number; pciDssReports: number };
  reports: ReportEntry[];
}

const REPORT_TYPES = [
  { label: "Monthly Activity Report", endpoint: "/compliance/reports/monthly-activity", body: () => ({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, institution_code: "54agent", institution_name: "54agent Agent Banking", generated_by: "admin" }) },
  { label: "Quarterly Fraud Report", endpoint: "/compliance/reports/quarterly-fraud", body: () => ({ year: new Date().getFullYear(), quarter: Math.ceil((new Date().getMonth() + 1) / 3), institution_code: "54agent", institution_name: "54agent Agent Banking", generated_by: "admin" }) },
  { label: "Currency Transaction Report (CTR)", endpoint: "/compliance/reports/ctr", body: () => ({ start_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split("T")[0], end_date: new Date().toISOString().split("T")[0], institution_code: "54agent", generated_by: "admin" }) },
  { label: "Agent Network Report", endpoint: "/compliance/reports/agent-network", body: () => ({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, institution_code: "54agent", institution_name: "54agent Agent Banking", generated_by: "admin" }) },
  { label: "AML Report", endpoint: "/compliance/reports/aml", body: () => ({ start_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split("T")[0], end_date: new Date().toISOString().split("T")[0], institution_code: "54agent", generated_by: "admin" }) },
  { label: "KYC Compliance Report", endpoint: "/compliance/reports/kyc-compliance", body: () => ({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, institution_code: "54agent", generated_by: "admin" }) },
];

export default function ComplianceReporting() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showGenMenu, setShowGenMenu] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const genMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (genMenuRef.current && !genMenuRef.current.contains(e.target as Node)) {
        setShowGenMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/reports/dashboard`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) setData(await res.json());
    } catch { }
    finally { setLoading(false); }
  };

  const generateReport = async (type: typeof REPORT_TYPES[number]) => {
    setShowGenMenu(false);
    setGenerating(true);
    try {
      await fetch(`${CORE_URL}${type.endpoint}`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(type.body()),
      });
      await load();
    } catch { }
    finally { setGenerating(false); }
  };

  const downloadReport = async (reportId: string, reportName: string) => {
    setDownloading(reportId);
    try {
      const res = await fetch(`${CORE_URL}/compliance/reports/${reportId}/export/csv`, {
        headers: getTenantHeadersFromStorage(),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportName.replace(/\s+/g, "_")}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { }
    finally { setDownloading(null); }
  };

  if (loading && !data) return <div className="p-8 text-center text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto" /></div>;

  const stats = data?.stats ?? { totalReports: 0, cbnReports: 0, ndprReports: 0, pciDssReports: 0 };
  const reports = data?.reports ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><FileText className="w-7 h-7 text-indigo-600" />Automated Compliance Reporting</h1>
          <p className="text-gray-500 text-sm mt-1">CBN/NDPR/PCI-DSS report generation with scheduling</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
          <div className="relative" ref={genMenuRef}>
            <button
              onClick={() => setShowGenMenu(v => !v)}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {generating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              Generate Report
              <ChevronDown className="w-4 h-4" />
            </button>
            {showGenMenu && (
              <div className="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-10 py-1">
                {REPORT_TYPES.map(t => (
                  <button
                    key={t.endpoint}
                    onClick={() => generateReport(t)}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Reports", value: stats.totalReports, color: "text-gray-800" },
          { label: "CBN Reports", value: stats.cbnReports, color: "text-blue-600" },
          { label: "NDPR Reports", value: stats.ndprReports, color: "text-purple-600" },
          { label: "PCI-DSS Reports", value: stats.pciDssReports, color: "text-emerald-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">Report History</h2>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                {["Report", "Framework", "Period", "Status", "Generated", "Size", "Actions"].map(h => (
                  <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {reports.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-8 text-gray-400">No reports generated yet. Use "Generate Report" to create one.</td></tr>
              ) : reports.map(r => (
                <tr key={r.id} className="hover:bg-gray-50/50">
                  <td className="py-3 px-4 font-medium text-gray-800">{r.name}</td>
                  <td className="py-3 px-4"><span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">{r.framework}</span></td>
                  <td className="py-3 px-4 text-gray-500">{r.period}</td>
                  <td className="py-3 px-4">
                    {r.status === "generating" || r.status === "DRAFT"
                      ? <span className="flex items-center gap-1 text-xs text-amber-600"><Clock className="w-3 h-3" />Generating</span>
                      : <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 capitalize">{r.status.toLowerCase()}</span>
                    }
                  </td>
                  <td className="py-3 px-4 text-gray-500 text-xs">{r.generatedAt ? new Date(r.generatedAt).toLocaleString() : "—"}</td>
                  <td className="py-3 px-4 text-gray-500 text-xs">{r.size ?? "—"}</td>
                  <td className="py-3 px-4">
                    {r.status !== "generating" && r.status !== "DRAFT" ? (
                      <button
                        onClick={() => downloadReport(r.id, r.name)}
                        disabled={downloading === r.id}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                      >
                        {downloading === r.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                        Download
                      </button>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
