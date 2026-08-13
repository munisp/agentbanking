import { CheckCircle, Clock, XCircle, FileText, Users, ShieldCheck } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

type Tab = "Operations" | "Finance" | "HR" | "Compliance";

interface OpsData { uptime: number; incidents: number; slaHealth: string }
interface FinanceData { revenue: number; collections: number; payouts: number; }
interface HRData { headcount: number; newJoins: number; churn: number; trainingCompletion: number }
interface ComplianceData { openViolations: number; upcomingFilings: number; auditStatus: string }
interface Approval { id: string; type: string; requester: string; amount?: number; submitted: string; status: "pending" }

const fmt = (n: number) => n >= 1e9 ? `₦${(n / 1e9).toFixed(1)}B` : `₦${(n / 1e6).toFixed(1)}M`;

const ManagementPortal: React.FC = () => {
  const [tab, setTab] = useState<Tab>("Operations");
  const [ops, setOps] = useState<OpsData | null>(null);
  const [fin, setFin] = useState<FinanceData | null>(null);
  const [hr, setHr] = useState<HRData | null>(null);
  const [comp, setComp] = useState<ComplianceData | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/portals/api/v1/management/overview`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setOps(d.ops ?? null); setFin(d.finance ?? null);
        setHr(d.hr ?? null); setComp(d.compliance ?? null);
        setApprovals(d.approvals ?? []);
      } else { setError("Failed to load management overview."); }
    } catch { setError("Failed to load management overview."); }
    finally { setLoading(false); }
  };

  const tabs: Tab[] = ["Operations", "Finance", "HR", "Compliance"];

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchAll()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Management Portal</h1>
        <p className="text-gray-500 text-sm mt-1">Operational, financial and compliance overview for management</p>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="flex gap-2 border-b border-gray-200">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-indigo-600 text-indigo-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        {tab === "Operations" && !ops && (
          <p className="text-sm text-gray-500">No operations data available.</p>
        )}
        {tab === "Operations" && ops && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { label: "Platform Uptime", value: `${ops.uptime}%`, sub: "Last 30 days", color: "text-emerald-600" },
              { label: "Open Incidents", value: ops.incidents, sub: "Unresolved", color: "text-red-500" },
              { label: "SLA Health", value: ops.slaHealth, sub: "Overall status", color: "text-blue-600" },
            ].map(({ label, value, sub, color }) => (
              <div key={label} className="border border-gray-100 rounded-xl p-5">
                <p className="text-sm text-gray-500">{label}</p>
                <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                <p className="text-xs text-gray-400 mt-1">{sub}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "Finance" && !fin && (
          <p className="text-sm text-gray-500">No finance data available.</p>
        )}
        {tab === "Finance" && fin && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { label: "Revenue MTD", value: fmt(fin.revenue), icon: FileText },
              { label: "Collections MTD", value: fmt(fin.collections), icon: CheckCircle },
              { label: "Payouts MTD", value: fmt(fin.payouts), icon: Clock },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="border border-gray-100 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-2"><Icon className="w-4 h-4 text-indigo-500" /><p className="text-sm text-gray-500">{label}</p></div>
                <p className="text-2xl font-bold text-gray-900">{value}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "HR" && !hr && (
          <p className="text-sm text-gray-500">No HR data available.</p>
        )}
        {tab === "HR" && hr && (
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-6">
            {[
              { label: "Total Headcount", value: hr.headcount.toLocaleString(), color: "text-indigo-600" },
              { label: "New Joins (MTD)", value: hr.newJoins, color: "text-emerald-600" },
              { label: "Churn (MTD)", value: hr.churn, color: "text-red-500" },
              { label: "Training Completion", value: `${hr.trainingCompletion}%`, color: "text-blue-600" },
            ].map(({ label, value, color }) => (
              <div key={label} className="border border-gray-100 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-1"><Users className="w-4 h-4 text-gray-400" /><p className="text-sm text-gray-500">{label}</p></div>
                <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "Compliance" && !comp && (
          <p className="text-sm text-gray-500">No compliance data available.</p>
        )}
        {tab === "Compliance" && comp && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { label: "Open Violations", value: comp.openViolations, color: "text-red-500", icon: XCircle },
              { label: "Upcoming Filings", value: comp.upcomingFilings, color: "text-amber-600", icon: Clock },
              { label: "Audit Status", value: comp.auditStatus, color: "text-blue-600", icon: ShieldCheck },
            ].map(({ label, value, color, icon: Icon }) => (
              <div key={label} className="border border-gray-100 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><p className="text-sm text-gray-500">{label}</p></div>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Approval Queue</h2>
        <div className="space-y-3">
          {approvals.map(a => (
            <div key={a.id} className="flex items-center justify-between p-3 border border-gray-100 rounded-xl">
              <div>
                <p className="text-sm font-medium text-gray-800">{a.type}</p>
                <p className="text-xs text-gray-400">{a.requester} · {a.submitted}{a.amount ? ` · ₦${a.amount.toLocaleString()}` : ""}</p>
              </div>
              <div className="flex gap-2">
                <button className="text-xs px-3 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg">Approve</button>
                <button className="text-xs px-3 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg">Reject</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ManagementPortal;
