import { Shield, RefreshCw, Play, AlertTriangle, Edit2, Check, X } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

interface RetentionPolicy {
  id: string;
  entityType: string;
  retentionDays: number;
  legalBasis: "CBN" | "NDPR" | "GDPR";
  archivePolicy: "delete" | "archive";
  lastEnforced: string;
  nextRun: string;
}

interface ExpiryAlert {
  id: string;
  entityType: string;
  recordCount: number;
  expiresIn: number;
}

const MOCK_POLICIES: RetentionPolicy[] = [
  { id: "p1", entityType: "Transactions", retentionDays: 2555, legalBasis: "CBN", archivePolicy: "archive", lastEnforced: "2026-04-30", nextRun: "2026-05-07" },
  { id: "p2", entityType: "KYC Documents", retentionDays: 1825, legalBasis: "CBN", archivePolicy: "archive", lastEnforced: "2026-04-28", nextRun: "2026-05-05" },
  { id: "p3", entityType: "Audit Logs", retentionDays: 3650, legalBasis: "NDPR", archivePolicy: "archive", lastEnforced: "2026-04-25", nextRun: "2026-05-02" },
  { id: "p4", entityType: "Customer Data", retentionDays: 1095, legalBasis: "NDPR", archivePolicy: "delete", lastEnforced: "2026-04-30", nextRun: "2026-05-07" },
  { id: "p5", entityType: "Session Logs", retentionDays: 180, legalBasis: "GDPR", archivePolicy: "delete", lastEnforced: "2026-04-29", nextRun: "2026-05-06" },
  { id: "p6", entityType: "Failed Login Attempts", retentionDays: 90, legalBasis: "NDPR", archivePolicy: "delete", lastEnforced: "2026-04-30", nextRun: "2026-05-07" },
];

const MOCK_ALERTS: ExpiryAlert[] = [
  { id: "a1", entityType: "Session Logs", recordCount: 14520, expiresIn: 7 },
  { id: "a2", entityType: "Customer Data", recordCount: 320, expiresIn: 14 },
  { id: "a3", entityType: "Failed Login Attempts", recordCount: 8900, expiresIn: 22 },
];

const BASIS_COLORS: Record<string, string> = {
  CBN: "bg-green-100 text-green-700",
  NDPR: "bg-blue-100 text-blue-700",
  GDPR: "bg-purple-100 text-purple-700",
};

const DataRetentionPolicy: React.FC = () => {
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [alerts, setAlerts] = useState<ExpiryAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<RetentionPolicy>>({});
  const [runningId, setRunningId] = useState<string | null>(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/retention-policies`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setPolicies(Array.isArray(d.policies) ? d.policies : MOCK_POLICIES);
        setAlerts(Array.isArray(d.alerts) ? d.alerts : MOCK_ALERTS);
      } else { setPolicies(MOCK_POLICIES); setAlerts(MOCK_ALERTS); }
    } catch { setPolicies(MOCK_POLICIES); setAlerts(MOCK_ALERTS); }
    finally { setLoading(false); }
  };

  const handleRunNow = async (id: string) => {
    setRunningId(id);
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/retention-policies/${id}/enforce`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      fetchData();
    } catch { }
    finally { setRunningId(null); }
  };

  const handleSaveEdit = async (id: string) => {
    try {
      await fetch(`${CORE_URL}/compliance/api/v1/retention-policies/${id}`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(editValues),
      });
      setPolicies(p => p.map(pol => pol.id === id ? { ...pol, ...editValues } : pol));
    } catch { setPolicies(p => p.map(pol => pol.id === id ? { ...pol, ...editValues } : pol)); }
    setEditingId(null);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-7 h-7 text-indigo-600" /> Data Retention Policy
          </h1>
          <p className="text-gray-500 text-sm mt-1">Manage data lifecycle, enforce retention schedules and compliance obligations</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {alerts.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            <h2 className="font-semibold text-amber-800">Upcoming Expiry Alerts (Next 30 Days)</h2>
          </div>
          <div className="space-y-2">
            {alerts.map(alert => (
              <div key={alert.id} className="flex items-center justify-between text-sm">
                <span className="text-amber-700 font-medium">{alert.entityType}</span>
                <span className="text-amber-600">{alert.recordCount.toLocaleString()} records expire in <strong>{alert.expiresIn} days</strong></span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Retention Policies</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Entity Type", "Retention (Days)", "Legal Basis", "Archive Policy", "Last Enforced", "Next Run", "Actions"].map(h => (
                  <th key={h} className="text-left text-xs text-gray-500 font-medium pb-3 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {policies.map(policy => (
                <tr key={policy.id} className="hover:bg-gray-50">
                  <td className="py-3 pr-4 font-medium text-gray-900">{policy.entityType}</td>
                  <td className="py-3 pr-4">
                    {editingId === policy.id
                      ? <input type="number" value={editValues.retentionDays ?? policy.retentionDays}
                          onChange={e => setEditValues(v => ({ ...v, retentionDays: Number(e.target.value) }))}
                          className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
                      : policy.retentionDays.toLocaleString()}
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${BASIS_COLORS[policy.legalBasis]}`}>{policy.legalBasis}</span>
                  </td>
                  <td className="py-3 pr-4">
                    {editingId === policy.id
                      ? <select value={editValues.archivePolicy ?? policy.archivePolicy}
                          onChange={e => setEditValues(v => ({ ...v, archivePolicy: e.target.value as "delete" | "archive" }))}
                          className="border border-gray-300 rounded px-2 py-1 text-sm">
                          <option value="archive">Archive</option>
                          <option value="delete">Delete</option>
                        </select>
                      : <span className={`capitalize text-xs px-2 py-0.5 rounded-full ${policy.archivePolicy === "delete" ? "bg-red-50 text-red-600" : "bg-teal-50 text-teal-700"}`}>{policy.archivePolicy}</span>}
                  </td>
                  <td className="py-3 pr-4 text-gray-500">{policy.lastEnforced}</td>
                  <td className="py-3 pr-4 text-gray-500">{policy.nextRun}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      {editingId === policy.id ? (
                        <>
                          <button onClick={() => handleSaveEdit(policy.id)} className="p-1 text-green-600 hover:bg-green-50 rounded"><Check className="w-4 h-4" /></button>
                          <button onClick={() => setEditingId(null)} className="p-1 text-gray-500 hover:bg-gray-100 rounded"><X className="w-4 h-4" /></button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => { setEditingId(policy.id); setEditValues({ retentionDays: policy.retentionDays, archivePolicy: policy.archivePolicy }); }}
                            className="p-1 text-indigo-600 hover:bg-indigo-50 rounded"><Edit2 className="w-4 h-4" /></button>
                          <button onClick={() => handleRunNow(policy.id)}
                            className="flex items-center gap-1 text-xs px-2 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded">
                            <Play className={`w-3 h-3 ${runningId === policy.id ? "animate-pulse" : ""}`} /> Run Now
                          </button>
                        </>
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
  );
};

export default DataRetentionPolicy;
