import { AlertTriangle, RefreshCw, Send, FileText, CheckCircle, Clock, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface SuspiciousReport {
  id: string;
  report_type: "STR" | "CTR" | "SATR";
  subject_name: string;
  subject_account: string;
  amount: number;
  currency: string;
  transaction_date: string;
  reason: string;
  status: "draft" | "submitted" | "acknowledged" | "rejected";
  submitted_at?: string;
  reference?: string;
}

const TYPE_COLORS: Record<string, string> = { STR: "bg-red-100 text-red-700", CTR: "bg-amber-100 text-amber-700", SATR: "bg-orange-100 text-orange-700" };
const STATUS_STYLES: Record<string, { cls: string; icon: React.FC<any> }> = {
  draft: { cls: "bg-gray-100 text-gray-600", icon: Clock },
  submitted: { cls: "bg-blue-100 text-blue-700", icon: Send },
  acknowledged: { cls: "bg-emerald-100 text-emerald-700", icon: CheckCircle },
  rejected: { cls: "bg-red-100 text-red-700", icon: XCircle },
};

const NFIUReporting: React.FC = () => {
  const [reports, setReports] = useState<SuspiciousReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ report_type: "STR", subject_name: "", subject_account: "", amount: "", reason: "" });

  useEffect(() => { fetchReports(); }, []);

  const fetchReports = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/nfiu-reports`, { headers: getTenantHeadersFromStorage() });
      if (!res.ok) throw new Error(`Failed to load NFIU reports (HTTP ${res.status})`);
      const d = await res.json();
      setReports(Array.isArray(d.reports) ? d.reports : []);
    } catch (e: any) {
      setReports([]);
      setLoadError(e?.message || "Failed to load NFIU reports.");
    } finally { setLoading(false); }
  };

  const submitToNFIU = async (id: string) => {
    setSubmitting(id);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/nfiu-reports/${id}/submit`, { method: "POST", headers: getTenantHeadersFromStorage() });
      if (!res.ok) throw new Error(`Submission failed (HTTP ${res.status})`);
      await fetchReports();
      alert("Report submitted to NFIU successfully.");
    } catch (e: any) {
      alert(`Failed to submit report to NFIU: ${e?.message || "Unknown error"}`);
    } finally { setSubmitting(null); }
  };

  const createReport = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/nfiu-reports`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, amount: Number(form.amount), currency: "NGN", transaction_date: new Date().toISOString().split("T")[0] }),
      });
      if (!res.ok) throw new Error(`Failed to create report (HTTP ${res.status})`);
      setShowForm(false);
      setForm({ report_type: "STR", subject_name: "", subject_account: "", amount: "", reason: "" });
      fetchReports();
    } catch (err: any) {
      alert(`Failed to create report: ${err?.message || "Unknown error"}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-7 h-7 text-orange-600" /> NFIU Reporting
          </h1>
          <p className="text-gray-500 text-sm mt-1">Suspicious Transaction Reports (STR), Currency Transaction Reports (CTR), and SATR filings</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium">
          <FileText className="w-4 h-4" /> New Report
        </button>
      </div>

      {loadError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700">Failed to load NFIU reports</p>
            <p className="text-xs text-red-600">{loadError}</p>
          </div>
          <button onClick={fetchReports} className="ml-auto text-xs px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg">
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "STR Filed", value: reports.filter(r => r.report_type === "STR").length, color: "text-red-600" },
          { label: "CTR Filed", value: reports.filter(r => r.report_type === "CTR").length, color: "text-amber-600" },
          { label: "Pending Submission", value: reports.filter(r => r.status === "draft").length, color: "text-gray-700" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{loadError ? "—" : value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Create New Report</h2>
          <form onSubmit={createReport} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Report Type</label>
                <select value={form.report_type} onChange={e => setForm(f => ({ ...f, report_type: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500">
                  <option>STR</option><option>CTR</option><option>SATR</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Amount (₦)</label>
                <input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Subject Name</label>
                <input value={form.subject_name} onChange={e => setForm(f => ({ ...f, subject_name: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Account Number</label>
                <input value={form.subject_account} onChange={e => setForm(f => ({ ...f, subject_account: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Reason / Narrative</label>
              <textarea value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} required rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="flex-1 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium">Save Draft</button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Type", "Subject", "Amount", "Date", "Reason", "Status", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={7} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : loadError ? (
              <tr><td colSpan={7} className="text-center py-10 text-red-500 text-sm">Unable to load reports. Use Retry above.</td></tr>
            ) : reports.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400 text-sm">No NFIU reports on file.</td></tr>
            ) : reports.map(r => {
              const StatusIcon = STATUS_STYLES[r.status].icon;
              return (
                <tr key={r.id} className="hover:bg-gray-50/50">
                  <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full font-bold ${TYPE_COLORS[r.report_type]}`}>{r.report_type}</span></td>
                  <td className="py-3 px-4">
                    <p className="font-medium">{r.subject_name}</p>
                    <p className="text-xs text-gray-400 font-mono">{r.subject_account}</p>
                  </td>
                  <td className="py-3 px-4 font-medium">₦{r.amount.toLocaleString()}</td>
                  <td className="py-3 px-4 text-gray-500">{r.transaction_date}</td>
                  <td className="py-3 px-4 text-gray-600 max-w-48 truncate">{r.reason}</td>
                  <td className="py-3 px-4">
                    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full capitalize w-fit ${STATUS_STYLES[r.status].cls}`}>
                      <StatusIcon className="w-3 h-3" />{r.status}
                    </span>
                    {r.reference && <p className="text-xs text-gray-400 mt-0.5">{r.reference}</p>}
                  </td>
                  <td className="py-3 px-4">
                    {r.status === "draft" && (
                      <button onClick={() => submitToNFIU(r.id)} disabled={submitting === r.id}
                        className="text-xs px-2 py-1 bg-orange-50 text-orange-600 hover:bg-orange-100 rounded flex items-center gap-1">
                        {submitting === r.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />} Submit
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default NFIUReporting;
