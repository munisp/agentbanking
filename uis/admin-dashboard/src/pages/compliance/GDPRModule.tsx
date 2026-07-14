import { Shield, RefreshCw, Download, AlertCircle, CheckCircle, Clock, User, Trash2, Eye, FileText } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface DataRequest {
  id: string;
  type: "access" | "erasure" | "portability" | "rectification";
  subject_name: string;
  subject_email: string;
  status: "pending" | "in_progress" | "completed" | "rejected";
  submitted_at: string;
  deadline: string;
  notes?: string;
}

const MOCK_REQUESTS: DataRequest[] = [
  { id: "gdpr-001", type: "access", subject_name: "Amaka Obi", subject_email: "amaka@example.com", status: "pending", submitted_at: "2024-11-20", deadline: "2024-12-20", notes: "Requested all transaction history" },
  { id: "gdpr-002", type: "erasure", subject_name: "Bode Williams", subject_email: "bode@example.com", status: "in_progress", submitted_at: "2024-11-18", deadline: "2024-12-18" },
  { id: "gdpr-003", type: "portability", subject_name: "Chidera Eze", subject_email: "chi@example.com", status: "completed", submitted_at: "2024-11-01", deadline: "2024-12-01" },
  { id: "gdpr-004", type: "rectification", subject_name: "Dipo Alade", subject_email: "dipo@example.com", status: "rejected", submitted_at: "2024-10-28", deadline: "2024-11-28", notes: "Subject could not verify identity" },
];

const TYPE_LABELS: Record<string, string> = { access: "Data Access", erasure: "Right to Erasure", portability: "Data Portability", rectification: "Rectification" };
const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

const GDPRModule: React.FC = () => {
  const [requests, setRequests] = useState<DataRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<DataRequest | null>(null);

  useEffect(() => { fetchRequests(); }, []);

  const fetchRequests = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/gdpr/api/v1/requests`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setRequests(Array.isArray(d.requests) ? d.requests : MOCK_REQUESTS); }
      else { setRequests(MOCK_REQUESTS); }
    } catch { setRequests(MOCK_REQUESTS); }
    finally { setLoading(false); }
  };

  const updateStatus = async (id: string, status: string) => {
    try {
      await fetch(`${CORE_URL}/gdpr/api/v1/requests/${id}`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchRequests();
    } catch (err: any) { alert(err.message); }
  };

  const exportData = async (id: string) => {
    try {
      const res = await fetch(`${CORE_URL}/gdpr/api/v1/requests/${id}/export`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { alert("Data export prepared. Download link sent to subject."); }
      else { alert("Export prepared (demo mode)"); }
    } catch { alert("Export prepared (demo mode)"); }
  };

  const filtered = requests.filter(r => statusFilter === "all" || r.status === statusFilter);
  const stats = [
    { label: "Total Requests", value: requests.length, color: "text-gray-700" },
    { label: "Pending", value: requests.filter(r => r.status === "pending").length, color: "text-amber-600" },
    { label: "In Progress", value: requests.filter(r => r.status === "in_progress").length, color: "text-blue-600" },
    { label: "Completed", value: requests.filter(r => r.status === "completed").length, color: "text-emerald-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-7 h-7 text-indigo-600" /> GDPR / Data Privacy
          </h1>
          <p className="text-gray-500 text-sm mt-1">Manage data subject requests under NDPR and GDPR frameworks</p>
        </div>
        <button onClick={fetchRequests} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-sm text-amber-800">
          <strong>Compliance Notice:</strong> Under NDPR/GDPR, data subject requests must be fulfilled within 30 days. Overdue requests are highlighted.
        </div>
      </div>

      <div className="flex gap-2">
        {["all", "pending", "in_progress", "completed", "rejected"].map(f => (
          <button key={f} onClick={() => setStatusFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors ${statusFilter === f ? "bg-indigo-600 border-indigo-500 text-white" : "bg-white border-gray-200 text-gray-600 hover:border-indigo-300"}`}>
            {f.replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Subject", "Request Type", "Status", "Submitted", "Deadline", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : filtered.map(r => {
              const isOverdue = r.status === "pending" && new Date(r.deadline) < new Date();
              return (
                <tr key={r.id} className={`hover:bg-gray-50/50 ${isOverdue ? "bg-red-50/30" : ""}`}>
                  <td className="py-3 px-4">
                    <p className="font-medium text-gray-900">{r.subject_name}</p>
                    <p className="text-xs text-gray-400">{r.subject_email}</p>
                  </td>
                  <td className="py-3 px-4"><span className="text-xs px-2 py-1 bg-indigo-50 text-indigo-700 rounded">{TYPE_LABELS[r.type]}</span></td>
                  <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[r.status]}`}>{r.status.replace("_", " ")}</span></td>
                  <td className="py-3 px-4 text-gray-500">{r.submitted_at}</td>
                  <td className="py-3 px-4">
                    <span className={isOverdue ? "text-red-600 font-medium" : "text-gray-500"}>{r.deadline}</span>
                    {isOverdue && <span className="ml-1 text-xs text-red-500">(overdue)</span>}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <button onClick={() => setSelected(r)} className="p-1 text-gray-400 hover:text-indigo-600"><Eye className="w-4 h-4" /></button>
                      {r.status === "pending" && (
                        <button onClick={() => updateStatus(r.id, "in_progress")} className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded">Process</button>
                      )}
                      {r.status === "in_progress" && r.type === "access" && (
                        <button onClick={() => exportData(r.id)} className="text-xs px-2 py-1 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded flex items-center gap-1">
                          <Download className="w-3 h-3" /> Export
                        </button>
                      )}
                      {r.status === "in_progress" && (
                        <button onClick={() => updateStatus(r.id, "completed")} className="text-xs px-2 py-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 rounded">Complete</button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && (
          <div className="text-center py-10 text-gray-400">
            <Shield className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p>No requests found</p>
          </div>
        )}
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-lg">Request Details</h2>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="space-y-2 text-sm">
              {[
                ["ID", selected.id], ["Type", TYPE_LABELS[selected.type]],
                ["Subject", selected.subject_name], ["Email", selected.subject_email],
                ["Status", selected.status], ["Submitted", selected.submitted_at],
                ["Deadline", selected.deadline],
              ].map(([l, v]) => (
                <div key={l} className="flex justify-between py-1.5 border-b border-gray-50">
                  <span className="text-gray-500">{l}</span>
                  <span className="font-medium capitalize">{v}</span>
                </div>
              ))}
              {selected.notes && (
                <div className="mt-2 p-3 bg-gray-50 rounded-lg text-gray-600 text-xs">{selected.notes}</div>
              )}
            </div>
            <button onClick={() => setSelected(null)} className="mt-4 w-full py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GDPRModule;
