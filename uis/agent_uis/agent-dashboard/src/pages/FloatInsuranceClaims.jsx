import { Shield, Plus, RefreshCw, Search, Download, CheckCircle, Clock, XCircle, AlertTriangle, FileText } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const STATUS_CONFIG = {
  pending:    { color: "text-amber-400",  bg: "bg-amber-900/30",  icon: Clock },
  approved:   { color: "text-blue-400",   bg: "bg-blue-900/30",   icon: CheckCircle },
  rejected:   { color: "text-red-400",    bg: "bg-red-900/30",    icon: XCircle },
  processing: { color: "text-purple-400", bg: "bg-purple-900/30", icon: RefreshCw },
  paid:       { color: "text-emerald-400",bg: "bg-emerald-900/30",icon: CheckCircle },
};

const CLAIM_TYPES = ["theft", "armed_robbery", "fire", "flood", "system_failure", "fraud", "other"];

const FloatInsuranceClaims = () => {
  const { user } = useAuth();
  const [claims, setClaims] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ claim_type: "theft", incident_date: "", float_amount_lost: "", description: "", police_report_number: "" });

  useEffect(() => {
    if (!user?.keycloakId) return;
    fetchClaims();
    fetchStats();
  }, [user]);

  const fetchStats = async () => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insurance/api/v1/float-claims/stats?agent_id=${keycloakId}`, { headers: authHeaders() });
      if (res.ok) setStats(await res.json());
    } catch { }
  };

  const fetchClaims = async () => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insurance/api/v1/float-claims?agent_id=${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setClaims(Array.isArray(data.claims) ? data.claims : Array.isArray(data) ? data : []);
      }
    } catch { setClaims([]); }
    finally { setLoading(false); }
  };

  const submitClaim = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/insurance/api/v1/float-claims`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, agent_id: keycloakId, float_amount_lost: parseFloat(form.float_amount_lost) }),
      });
      if (!res.ok) throw new Error("Claim submission failed");
      setShowForm(false);
      setForm({ claim_type: "theft", incident_date: "", float_amount_lost: "", description: "", police_report_number: "" });
      fetchClaims();
      fetchStats();
    } catch (err) { alert(err.message); }
    finally { setSubmitting(false); }
  };

  const filtered = claims.filter(c => !searchTerm || JSON.stringify(c).toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-600/20 rounded-lg"><Shield className="w-6 h-6 text-emerald-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Float Insurance Claims</h1>
              <p className="text-gray-400 text-sm">Claim for lost or stolen float funds</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchClaims} className="flex items-center gap-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm hover:bg-gray-700 transition-colors">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
            <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors">
              <Plus className="w-4 h-4" /> New Claim
            </button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Total Claims", value: stats.totalClaims ?? "—", color: "text-blue-400" },
              { label: "Approved", value: stats.approvedClaims ?? "—", color: "text-emerald-400" },
              { label: "Pending", value: stats.pendingClaims ?? "—", color: "text-amber-400" },
              { label: "Total Paid", value: stats.totalPaidAmount ? `₦${parseFloat(stats.totalPaidAmount).toLocaleString()}` : "—", color: "text-purple-400" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-400">{label}</p>
                <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}

        {/* New Claim Form */}
        {showForm && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
            <h2 className="font-semibold mb-4">Submit Insurance Claim</h2>
            <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg p-3 mb-4 flex items-start gap-2 text-xs text-amber-300">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Claims require a police report for incidents above ₦50,000. Processing takes 3–5 business days.</span>
            </div>
            <form onSubmit={submitClaim} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Incident Type</label>
                  <select value={form.claim_type} onChange={e => setForm(f => ({ ...f, claim_type: e.target.value }))}
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                    {CLAIM_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Incident Date</label>
                  <input type="date" value={form.incident_date} onChange={e => setForm(f => ({ ...f, incident_date: e.target.value }))} required
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Float Amount Lost (₦)</label>
                <input type="number" value={form.float_amount_lost} onChange={e => setForm(f => ({ ...f, float_amount_lost: e.target.value }))} placeholder="0.00" required
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Police Report Number (if applicable)</label>
                <input value={form.police_report_number} onChange={e => setForm(f => ({ ...f, police_report_number: e.target.value }))} placeholder="PR-XXXXXXXXX"
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Incident Description</label>
                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={3} required
                  placeholder="Describe what happened..."
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              </div>
              <div className="flex gap-2">
                <button type="submit" disabled={submitting}
                  className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors">
                  {submitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                  {submitting ? "Submitting..." : "Submit Claim"}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="px-4 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Search claims..."
            className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
        </div>

        {/* Claims Table */}
        <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h3 className="font-medium flex items-center gap-2"><FileText className="w-4 h-4 text-gray-400" /> My Claims</h3>
            <span className="text-xs text-gray-500">{filtered.length} claims</span>
          </div>
          {loading ? (
            <div className="p-10 text-center text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="p-10 text-center text-gray-500">
              <Shield className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>{searchTerm ? "No claims match your search" : "No insurance claims filed yet"}</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filtered.map((claim, i) => {
                const cfg = STATUS_CONFIG[claim.status] || STATUS_CONFIG.pending;
                const Icon = cfg.icon;
                return (
                  <div key={claim.id || i} className="p-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${cfg.bg}`}><Icon className={`w-4 h-4 ${cfg.color}`} /></div>
                      <div>
                        <p className="font-medium text-sm capitalize">{(claim.claim_type || "unknown").replace(/_/g, " ")}</p>
                        <p className="text-xs text-gray-500">{claim.id?.slice(0, 16) || "—"} · {new Date(claim.incident_date || claim.created_at || Date.now()).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-sm">₦{parseFloat(claim.float_amount_lost || 0).toLocaleString()}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color} capitalize`}>{claim.status || "pending"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FloatInsuranceClaims;
