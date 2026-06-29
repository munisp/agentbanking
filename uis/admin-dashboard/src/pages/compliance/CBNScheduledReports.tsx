import { FileText, RefreshCw, Play, AlertCircle, Calendar, Plus, Trash2, X } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface ReportSchedule {
  id: string;
  name: string;
  frequency: "daily" | "weekly" | "monthly" | "quarterly";
  last_run?: string;
  next_run: string;
  status: "active" | "paused" | "failed";
  format: "pdf" | "xlsx" | "csv";
  recipients: string[];
}

const FREQ_COLORS: Record<string, string> = {
  daily: "bg-blue-100 text-blue-700",
  weekly: "bg-purple-100 text-purple-700",
  monthly: "bg-amber-100 text-amber-700",
  quarterly: "bg-indigo-100 text-indigo-700",
};

const EMPTY_FORM = { name: "", frequency: "monthly" as const, format: "pdf" as const, recipients: "" };

const CBNScheduledReports: React.FC = () => {
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchSchedules(); }, []);

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/cbn-reports/schedules`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setSchedules(Array.isArray(d.schedules) ? d.schedules : []);
      }
    } catch { }
    finally { setLoading(false); }
  };

  const runNow = async (id: string) => {
    setRunning(id);
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/cbn-reports/${id}/run`, { method: "POST", headers: getTenantHeadersFromStorage() });
      await fetchSchedules();
    } catch { }
    finally { setRunning(null); }
  };

  const togglePause = async (s: ReportSchedule) => {
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/cbn-reports/${s.id}/status`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ status: s.status === "active" ? "paused" : "active" }),
      });
      fetchSchedules();
    } catch { }
  };

  const deleteSchedule = async (id: string) => {
    if (!confirm("Delete this schedule?")) return;
    setDeleting(id);
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/cbn-reports/schedules/${id}`, {
        method: "DELETE",
        headers: getTenantHeadersFromStorage(),
      });
      setSchedules(prev => prev.filter(s => s.id !== id));
    } catch { }
    finally { setDeleting(null); }
  };

  const createSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const recipients = form.recipients.split(",").map(r => r.trim()).filter(Boolean);
      const res = await fetch(`${CORE_URL}/compliance/api/v1/cbn-reports/schedules`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, recipients }),
      });
      if (res.ok) {
        setShowForm(false);
        setForm(EMPTY_FORM);
        fetchSchedules();
      }
    } catch { }
    finally { setSaving(false); }
  };

  const active = schedules.filter(s => s.status === "active").length;
  const failed = schedules.filter(s => s.status === "failed").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Calendar className="w-7 h-7 text-blue-600" /> CBN Scheduled Reports
          </h1>
          <p className="text-gray-500 text-sm mt-1">Automated regulatory report generation and submission</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchSchedules} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
          <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus className="w-4 h-4" /> New Schedule
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active Schedules", value: active, color: "text-emerald-600" },
          { label: "Failed", value: failed, color: "text-red-600" },
          { label: "Total Reports", value: schedules.length, color: "text-gray-700" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {failed > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="text-sm text-red-800">
            <strong>{failed} report schedule(s) have failed.</strong> Review and re-run to maintain compliance.
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Report Name", "Frequency", "Last Run", "Next Run", "Format", "Status", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={7} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : schedules.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400">No schedules yet. Click "New Schedule" to create one.</td></tr>
            ) : schedules.map(s => (
              <tr key={s.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4">
                  <p className="font-medium text-gray-900">{s.name}</p>
                  <p className="text-xs text-gray-400">{(s.recipients || []).join(", ")}</p>
                </td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${FREQ_COLORS[s.frequency]}`}>{s.frequency}</span></td>
                <td className="py-3 px-4 text-gray-500 text-xs">{s.last_run ? new Date(s.last_run).toLocaleString() : "—"}</td>
                <td className="py-3 px-4 text-gray-500 text-xs">{s.next_run ? new Date(s.next_run).toLocaleString() : "—"}</td>
                <td className="py-3 px-4"><span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded uppercase">{s.format}</span></td>
                <td className="py-3 px-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${s.status === "active" ? "bg-emerald-100 text-emerald-700" : s.status === "failed" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>
                    {s.status}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <button onClick={() => runNow(s.id)} disabled={running === s.id}
                      className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded flex items-center gap-1 disabled:opacity-50">
                      {running === s.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Run
                    </button>
                    <button onClick={() => togglePause(s)}
                      className={`text-xs px-2 py-1 rounded ${s.status === "active" ? "bg-amber-50 text-amber-600 hover:bg-amber-100" : "bg-emerald-50 text-emerald-600 hover:bg-emerald-100"}`}>
                      {s.status === "active" ? "Pause" : "Resume"}
                    </button>
                    <button onClick={() => deleteSchedule(s.id)} disabled={deleting === s.id}
                      className="text-xs px-2 py-1 bg-red-50 text-red-500 hover:bg-red-100 rounded flex items-center gap-1 disabled:opacity-50">
                      {deleting === s.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2"><FileText className="w-5 h-5 text-blue-600" />New Report Schedule</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={createSchedule} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Report Name *</label>
                <input
                  required
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Monthly AML Report"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Frequency *</label>
                  <select
                    value={form.frequency}
                    onChange={e => setForm(f => ({ ...f, frequency: e.target.value as typeof form.frequency }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Format *</label>
                  <select
                    value={form.format}
                    onChange={e => setForm(f => ({ ...f, format: e.target.value as typeof form.format }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="pdf">PDF</option>
                    <option value="xlsx">XLSX</option>
                    <option value="csv">CSV</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Recipients (comma-separated emails)</label>
                <input
                  value={form.recipients}
                  onChange={e => setForm(f => ({ ...f, recipients: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="compliance@bank.com, cbn@bank.com"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={saving} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
                  {saving && <RefreshCw className="w-3 h-3 animate-spin" />} Create Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CBNScheduledReports;
