import { useState, useEffect } from "react";
import { FileCheck, RefreshCw, Search, RotateCcw, XCircle } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";
const TRAINING_URL = import.meta.env.VITE_AGENT_BANKING_URL || "https://54agent.upi.dev";

interface CertStats {
  active: number;
  expiringSoon: number;
  revoked: number;
  renewalRate: string;
}

interface Certificate {
  id: string;
  certificate_number: string;
  agent_id: string;
  course_title: string;
  status: string;
  score: number | null;
  is_cbn_required: boolean;
  issued_at: string | null;
  expires_at: string | null;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  revoked: "bg-red-500/20 text-red-400",
  renewed: "bg-blue-500/20 text-blue-400",
  expired: "bg-yellow-500/20 text-yellow-400",
};

export default function ComplianceCertManager() {
  const [stats, setStats] = useState<CertStats>({ active: 0, expiringSoon: 0, revoked: 0, renewalRate: "0%" });
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/certs/dashboard`, {
        headers: getTenantHeadersFromStorage(),
      });
      if (res.ok) {
        const d = await res.json();
        setStats(d.stats ?? { active: 0, expiringSoon: 0, revoked: 0, renewalRate: "0%" });
        setCerts(Array.isArray(d.certificates) ? d.certificates : []);
      }
    } catch { }
    finally { setLoading(false); }
  };

  const handleAction = async (certId: string, action: "revoke" | "renew") => {
    setActionId(certId);
    try {
      await fetch(`${TRAINING_URL}/training/api/v1/training/certificates/${certId}/${action}`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
      });
      await load();
    } catch { }
    finally { setActionId(null); }
  };

  const filtered = certs.filter(c => {
    const matchSearch = !search ||
      c.certificate_number.toLowerCase().includes(search.toLowerCase()) ||
      c.course_title?.toLowerCase().includes(search.toLowerCase()) ||
      c.agent_id.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const kpis = [
    { label: "Active Certs", value: stats.active.toLocaleString() },
    { label: "Expiring Soon", value: stats.expiringSoon },
    { label: "Revoked", value: stats.revoked },
    { label: "Renewal Rate", value: stats.renewalRate },
  ];

  return (
    <div className="min-h-screen bg-[#0a0e17] text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <FileCheck className="w-6 h-6 text-blue-400" />
              Compliance Certs
            </h1>
            <p className="text-gray-400 text-sm mt-1">KYC/AML certificate tracking and renewal</p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-4 py-2 bg-[#141a2a] border border-gray-700 hover:border-gray-500 rounded-lg text-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="bg-[#141a2a] border border-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-xs uppercase tracking-wider">{kpi.label}</p>
              <p className="text-2xl font-bold mt-1 text-white">{kpi.value}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-3 mb-4 flex-wrap">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search by cert number, course, agent..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 bg-[#141a2a] border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-72"
            />
          </div>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-[#141a2a] border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="revoked">Revoked</option>
            <option value="renewed">Renewed</option>
            <option value="expired">Expired</option>
          </select>
        </div>

        <div className="bg-[#141a2a] border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between">
            <h3 className="font-semibold">Certificates ({filtered.length})</h3>
            {loading && <RefreshCw className="w-4 h-4 animate-spin text-gray-400" />}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Certificate #", "Course", "Agent ID", "Score", "CBN Required", "Issued", "Expires", "Status", "Actions"].map(col => (
                    <th key={col} className="text-left p-3 text-gray-400 font-medium">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-6 text-center text-gray-500">
                      {loading ? "Loading..." : "No certificates found"}
                    </td>
                  </tr>
                ) : filtered.map(c => (
                  <tr key={c.id} className="border-b border-gray-800/50 hover:bg-[#1a2035] transition-colors">
                    <td className="p-3 font-mono text-blue-400">{c.certificate_number}</td>
                    <td className="p-3 text-gray-200">{c.course_title || "—"}</td>
                    <td className="p-3 font-mono text-gray-400 text-xs">{c.agent_id.slice(0, 8)}…</td>
                    <td className="p-3">{c.score != null ? `${c.score.toFixed(1)}%` : "—"}</td>
                    <td className="p-3">
                      {c.is_cbn_required
                        ? <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">Yes</span>
                        : <span className="text-xs text-gray-500">No</span>}
                    </td>
                    <td className="p-3 text-gray-400">{c.issued_at ? new Date(c.issued_at).toLocaleDateString() : "—"}</td>
                    <td className="p-3 text-gray-400">{c.expires_at ? new Date(c.expires_at).toLocaleDateString() : "—"}</td>
                    <td className="p-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${STATUS_STYLE[c.status] ?? "bg-gray-500/20 text-gray-400"}`}>
                        {c.status}
                      </span>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        {c.status === "active" && (
                          <button
                            onClick={() => handleAction(c.id, "revoke")}
                            disabled={actionId === c.id}
                            title="Revoke"
                            className="p-1 text-red-400 hover:bg-red-500/20 rounded disabled:opacity-40"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                        {(c.status === "revoked" || c.status === "expired") && (
                          <button
                            onClick={() => handleAction(c.id, "renew")}
                            disabled={actionId === c.id}
                            title="Renew"
                            className="p-1 text-blue-400 hover:bg-blue-500/20 rounded disabled:opacity-40"
                          >
                            <RotateCcw className="w-4 h-4" />
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
      </div>
    </div>
  );
}
