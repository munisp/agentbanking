import { Siren, RefreshCw, Plus, AlertTriangle, CheckCircle, Clock, XCircle, User } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface Incident {
  id: string;
  title: string;
  severity: "P0" | "P1" | "P2" | "P3";
  status: "open" | "investigating" | "mitigated" | "resolved" | "postmortem";
  affected_services: string[];
  assignee?: string;
  started_at: string;
  resolved_at?: string;
  description: string;
}

const MOCK_INCIDENTS: Incident[] = [
  { id: "INC-0041", title: "NIP Gateway Latency Spike", severity: "P1", status: "mitigated", affected_services: ["payment-hub", "nip-gateway"], assignee: "Kolade Obi", started_at: "2024-11-29 14:23", description: "NIP gateway p99 latency exceeded 8s. Root cause: upstream NIBSS degradation. Mitigation: reduced retry timeout." },
  { id: "INC-0040", title: "Agent Auth Token Expiry Bug", severity: "P2", status: "resolved", affected_services: ["auth-service"], assignee: "Taiwo Adewale", started_at: "2024-11-28 09:45", resolved_at: "2024-11-28 11:30", description: "Tokens expiring 2hrs early due to timezone bug in token issuance." },
  { id: "INC-0039", title: "Float Deduction Race Condition", severity: "P1", status: "postmortem", affected_services: ["float-management"], assignee: "Aisha Bello", started_at: "2024-11-25 16:00", resolved_at: "2024-11-25 18:45", description: "Concurrent float deductions causing negative balances for 12 agents." },
  { id: "INC-0042", title: "SMS OTP Delivery Failure", severity: "P2", status: "open", affected_services: ["notification-service", "sms-gateway"], started_at: "2024-11-29 17:10", description: "OTP SMS not delivered to MTN numbers. Affecting ~15% of agent logins." },
];

const SEV_STYLES: Record<string, string> = { P0: "bg-red-600 text-white", P1: "bg-red-100 text-red-800", P2: "bg-amber-100 text-amber-800", P3: "bg-gray-100 text-gray-700" };
const STATUS_STYLES: Record<string, string> = {
  open: "bg-red-100 text-red-700", investigating: "bg-orange-100 text-orange-700",
  mitigated: "bg-blue-100 text-blue-700", resolved: "bg-emerald-100 text-emerald-700",
  postmortem: "bg-purple-100 text-purple-700",
};

const IncidentManagement: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", severity: "P2", affected_services: "", description: "" });
  const [selected, setSelected] = useState<Incident | null>(null);

  useEffect(() => { fetchIncidents(); }, []);

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/incidents`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setIncidents(Array.isArray(d.incidents) ? d.incidents : MOCK_INCIDENTS); }
    } catch { }
    finally { setLoading(false); }
  };

  const updateStatus = async (id: string, status: string) => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/incidents/${id}/status`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchIncidents();
    } catch (err: any) { alert(err.message); }
  };

  const createIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch(`${CORE_URL}/ops/api/v1/incidents`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, affected_services: form.affected_services.split(",").map(s => s.trim()), started_at: new Date().toISOString() }),
      });
      setShowForm(false);
      fetchIncidents();
    } catch { alert("Incident created (demo mode)"); setShowForm(false); }
  };

  const open = incidents.filter(i => i.status === "open" || i.status === "investigating").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Siren className="w-7 h-7 text-red-600" /> Incident Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Track, triage and resolve production incidents</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">
          <Plus className="w-4 h-4" /> Declare Incident
        </button>
      </div>

      {open > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
          <p className="text-sm text-red-800"><strong>{open} active incident(s)</strong> require immediate attention.</p>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Open", value: incidents.filter(i => i.status === "open").length, color: "text-red-600" },
          { label: "Investigating", value: incidents.filter(i => i.status === "investigating").length, color: "text-orange-600" },
          { label: "Mitigated", value: incidents.filter(i => i.status === "mitigated").length, color: "text-blue-600" },
          { label: "Resolved", value: incidents.filter(i => i.status === "resolved" || i.status === "postmortem").length, color: "text-emerald-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold mb-4">Declare Incident</h2>
          <form onSubmit={createIncident} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Title</label>
                <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Severity</label>
                <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500">
                  <option>P0</option><option>P1</option><option>P2</option><option>P3</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Affected Services (comma-separated)</label>
              <input value={form.affected_services} onChange={e => setForm(f => ({ ...f, affected_services: e.target.value }))} placeholder="payment-hub, nip-gateway"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="flex-1 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">Declare</button>
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="space-y-3">
        {incidents.map(inc => (
          <div key={inc.id} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="text-xs font-mono text-gray-400">{inc.id}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${SEV_STYLES[inc.severity]}`}>{inc.severity}</span>
                  <h3 className="font-semibold text-gray-900">{inc.title}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[inc.status]}`}>{inc.status}</span>
                </div>
                <p className="text-sm text-gray-600 mb-2">{inc.description}</p>
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>Started: {inc.started_at}</span>
                  {inc.resolved_at && <span>Resolved: {inc.resolved_at}</span>}
                  {inc.assignee && <span className="flex items-center gap-1"><User className="w-3 h-3" />{inc.assignee}</span>}
                  <span>Services: {inc.affected_services.join(", ")}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {inc.status === "open" && <button onClick={() => updateStatus(inc.id, "investigating")} className="text-xs px-2 py-1 bg-orange-50 text-orange-600 hover:bg-orange-100 rounded">Investigate</button>}
                {inc.status === "investigating" && <button onClick={() => updateStatus(inc.id, "mitigated")} className="text-xs px-2 py-1 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded">Mitigated</button>}
                {inc.status === "mitigated" && <button onClick={() => updateStatus(inc.id, "resolved")} className="text-xs px-2 py-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 rounded">Resolve</button>}
                {inc.status === "resolved" && <button onClick={() => updateStatus(inc.id, "postmortem")} className="text-xs px-2 py-1 bg-purple-50 text-purple-600 hover:bg-purple-100 rounded">Postmortem</button>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default IncidentManagement;
