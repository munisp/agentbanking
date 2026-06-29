import { Archive, Play, RefreshCw, CheckCircle, Clock } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

type StorageTarget = "S3" | "cold-storage";
type EntityType = "transactions" | "audit-logs" | "kyc-docs";

interface ArchivalPolicy {
  entityType: EntityType;
  retentionDays: number;
  archiveAfterDays: number;
  storageTarget: StorageTarget;
  lastRun: string;
  recordsArchived: number;
}

interface ArchiveJob {
  name: string;
  started: string;
  completed: string;
  recordsMoved: number;
  sizeMB: number;
}

const MOCK_POLICIES: ArchivalPolicy[] = [
  { entityType: "transactions", retentionDays: 365, archiveAfterDays: 180, storageTarget: "S3", lastRun: "2026-05-01 02:00", recordsArchived: 142800 },
  { entityType: "audit-logs", retentionDays: 730, archiveAfterDays: 365, storageTarget: "cold-storage", lastRun: "2026-04-30 03:00", recordsArchived: 980200 },
  { entityType: "kyc-docs", retentionDays: 2555, archiveAfterDays: 730, storageTarget: "S3", lastRun: "2026-04-15 01:00", recordsArchived: 12400 },
];

const MOCK_JOBS: ArchiveJob[] = [
  { name: "transactions-archive-20260501", started: "2026-05-01 02:00", completed: "2026-05-01 02:48", recordsMoved: 142800, sizeMB: 2840 },
  { name: "audit-logs-archive-20260430", started: "2026-04-30 03:00", completed: "2026-04-30 04:21", recordsMoved: 980200, sizeMB: 9802 },
  { name: "kyc-docs-archive-20260415", started: "2026-04-15 01:00", completed: "2026-04-15 01:12", recordsMoved: 12400, sizeMB: 18600 },
];

const ENTITY_STYLES: Record<EntityType, string> = {
  "transactions": "bg-blue-100 text-blue-700",
  "audit-logs": "bg-amber-100 text-amber-700",
  "kyc-docs": "bg-purple-100 text-purple-700",
};

const STORAGE_STYLES: Record<StorageTarget, string> = {
  "S3": "bg-emerald-100 text-emerald-700",
  "cold-storage": "bg-gray-100 text-gray-600",
};

const ArchivalAdmin: React.FC = () => {
  const [policies, setPolicies] = useState<ArchivalPolicy[]>([]);
  const [jobs, setJobs] = useState<ArchiveJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningPolicy, setRunningPolicy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/archival`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setPolicies(Array.isArray(d.policies) ? d.policies : MOCK_POLICIES);
        setJobs(Array.isArray(d.jobs) ? d.jobs : MOCK_JOBS);
      } else { setPolicies(MOCK_POLICIES); setJobs(MOCK_JOBS); }
    } catch { setPolicies(MOCK_POLICIES); setJobs(MOCK_JOBS); }
    finally { setLoading(false); }
  };

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3500); };

  const handleRunNow = async (entityType: string) => {
    setRunningPolicy(entityType);
    try {
      await fetch(`${CORE_URL}/ops/api/v1/archival/${entityType}/run`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      showToast(`Archive job started for ${entityType}`);
      fetchData();
    } catch { showToast(`Archive job triggered for ${entityType} (demo)`); }
    finally { setRunningPolicy(null); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Archive className="w-7 h-7 text-indigo-600" /> Archival Admin
          </h1>
          <p className="text-gray-500 text-sm mt-1">Manage data retention and archival policies</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {toast && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle className="w-4 h-4" /> {toast}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Archival Policies</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Entity Type", "Retention (days)", "Archive After (days)", "Storage Target", "Last Run", "Records Archived", "Action"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {policies.map(policy => (
                <tr key={policy.entityType} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ENTITY_STYLES[policy.entityType]}`}>{policy.entityType}</span>
                  </td>
                  <td className="py-3 px-3 text-gray-700">{policy.retentionDays}</td>
                  <td className="py-3 px-3 text-gray-700">{policy.archiveAfterDays}</td>
                  <td className="py-3 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STORAGE_STYLES[policy.storageTarget]}`}>{policy.storageTarget}</span>
                  </td>
                  <td className="py-3 px-3 text-gray-500 text-xs flex items-center gap-1"><Clock className="w-3 h-3" />{policy.lastRun}</td>
                  <td className="py-3 px-3 text-gray-700">{policy.recordsArchived.toLocaleString()}</td>
                  <td className="py-3 px-3">
                    <button onClick={() => handleRunNow(policy.entityType)} disabled={runningPolicy === policy.entityType}
                      className="flex items-center gap-1 text-xs px-3 py-1.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded-lg font-medium disabled:opacity-60">
                      <Play className="w-3 h-3" /> {runningPolicy === policy.entityType ? "Running..." : "Run Now"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Archive Job History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Job Name", "Started", "Completed", "Records Moved", "Size (MB)"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.map(job => (
                <tr key={job.name} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-gray-700 text-xs">{job.name}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{job.started}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{job.completed}</td>
                  <td className="py-2 px-3 text-gray-700">{job.recordsMoved.toLocaleString()}</td>
                  <td className="py-2 px-3 text-gray-700">{job.sizeMB.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ArchivalAdmin;
