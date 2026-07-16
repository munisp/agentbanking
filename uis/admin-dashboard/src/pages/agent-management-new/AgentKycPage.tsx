import DashboardLayout from "@/components/DashboardLayout";
import { useState, useEffect } from "react";

import { complianceKycApi, api } from "@/utils/api";

const FALLBACK_PROFILES = [
  {
    agentId: "AGT-001",
    name: "Adebayo Okonkwo",
    kycLevel: 2,
    status: "complete",
    risk: 15,
    docs: 2,
    verified: 2,
  },
  {
    agentId: "AGT-002",
    name: "Fatima Bello",
    kycLevel: 1,
    status: "basic",
    risk: 40,
    docs: 1,
    verified: 1,
  },
  {
    agentId: "AGT-003",
    name: "James Mwangi",
    kycLevel: 1,
    status: "basic",
    risk: 35,
    docs: 1,
    verified: 1,
  },
  {
    agentId: "AGT-004",
    name: "Amina Diallo",
    kycLevel: 0,
    status: "incomplete",
    risk: 80,
    docs: 1,
    verified: 0,
  },
  {
    agentId: "AGT-005",
    name: "Kwame Asante",
    kycLevel: 0,
    status: "incomplete",
    risk: 90,
    docs: 0,
    verified: 0,
  },
];

const FALLBACK_DOCUMENTS: Record<
  string,
  {
    docId: string;
    type: string;
    number: string;
    status: string;
    confidence: number;
  }[]
> = {
  "AGT-001": [
    {
      docId: "DOC-001A",
      type: "NIN",
      number: "123****8901",
      status: "verified",
      confidence: 95,
    },
    {
      docId: "DOC-001B",
      type: "BVN",
      number: "223****8901",
      status: "verified",
      confidence: 98,
    },
  ],
  "AGT-002": [
    {
      docId: "DOC-002A",
      type: "NIN",
      number: "987****2101",
      status: "verified",
      confidence: 95,
    },
  ],
  "AGT-003": [
    {
      docId: "DOC-003A",
      type: "Passport",
      number: "A****5678",
      status: "verified",
      confidence: 90,
    },
  ],
  "AGT-004": [
    {
      docId: "DOC-004A",
      type: "NIN",
      number: "INVALID",
      status: "rejected",
      confidence: 0,
    },
  ],
};

/** Map a compliance-kyc record to the profile shape this UI needs */
function mapApiRecord(record: any, idx: number) {
  const documents = record.documents ?? [];
  const checks = record.checks ?? [];
  const verifiedDocs = documents.filter(
    (d: any) => d.status === "approved" || d.status === "verified"
  ).length;
  const kycLevel =
    record.kyc_level ??
    (record.status === "verified" || record.status === "complete"
      ? 2
      : verifiedDocs > 0
        ? 1
        : 0);
  const status =
    record.kyc_status ??
    record.status ??
    (kycLevel >= 2 ? "complete" : kycLevel >= 1 ? "basic" : "incomplete");
  const risk =
    record.risk_score ??
    (status === "complete" ? 15 : status === "basic" ? 38 : 80);

  return {
    agentId: record.customer_id ?? record.agent_id ?? `AGT-${String(idx + 1).padStart(3, "0")}`,
    keycloakId: record.keycloak_id ?? record.keycloakId ?? null,
    name: record.customer_name ?? record.name ?? record.customer_id ?? "Unknown",
    kycLevel,
    status,
    risk,
    docs: documents.length,
    verified: verifiedDocs,
    _raw: record,
  };
}

export default function AgentKycPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showSubmitForm, setShowSubmitForm] = useState(false);
  const [liveProfiles, setLiveProfiles] = useState<any[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const handleApprove = async (p: any) => {
    const keycloakId = p.keycloakId ?? p._raw?.keycloak_id;
    if (!keycloakId) {
      showToast("error", `Cannot approve ${p.name}: keycloak_id not available. Ensure the KYC service returns this field.`);
      return;
    }
    if (!window.confirm(`Approve agent ${p.name} (${p.agentId})?\n\nThis will activate the agent for live transactions.`)) return;
    setActionLoading(p.agentId);
    try {
      await api.approveAgent(keycloakId);
      showToast("success", `${p.name} approved successfully.`);
      // Refresh KYC list
      setIsLoading(true);
      const json: any = await complianceKycApi.listRecords(0, 50);
      const items: any[] = Array.isArray(json) ? json : json?.records ?? json?.items ?? json?.data ?? [];
      setLiveProfiles(items.length > 0 ? items.map(mapApiRecord) : null);
    } catch (err: any) {
      showToast("error", `Approval failed: ${err?.message ?? "Unknown error"}`);
    } finally {
      setActionLoading(null);
      setIsLoading(false);
    }
  };

  const handleSuspend = async (p: any) => {
    const keycloakId = p.keycloakId ?? p._raw?.keycloak_id;
    if (!keycloakId) {
      showToast("error", `Cannot suspend ${p.name}: keycloak_id not available.`);
      return;
    }
    if (!window.confirm(`Suspend agent ${p.name} (${p.agentId})?\n\nThis will block the agent from processing transactions.`)) return;
    setActionLoading(p.agentId);
    try {
      await api.suspendAgent(keycloakId);
      showToast("success", `${p.name} suspended.`);
      setLiveProfiles(prev => prev ? prev.map(lp => lp.agentId === p.agentId ? { ...lp, status: "suspended" } : lp) : prev);
    } catch (err: any) {
      showToast("error", `Suspend failed: ${err?.message ?? "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    complianceKycApi
      .listRecords(0, 50)
      .then((json: any) => {
        const items: any[] = Array.isArray(json)
          ? json
          : json?.records ?? json?.items ?? json?.data ?? [];
        if (items.length > 0) {
          setLiveProfiles(items.map(mapApiRecord));
        } else {
          setLiveProfiles(null);
        }
      })
      .catch(() => {
        setError("KYC service unavailable");
        setLiveProfiles(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const profiles = liveProfiles ?? FALLBACK_PROFILES;

  const levelColor: Record<number, string> = {
    0: "text-red-400",
    1: "text-yellow-400",
    2: "text-green-400",
    3: "text-blue-400",
  };
  const statusBg: Record<string, string> = {
    verified: "bg-green-900 text-green-300",
    rejected: "bg-red-900 text-red-300",
    pending: "bg-yellow-900 text-yellow-300",
    manual_review: "bg-blue-900 text-blue-300",
  };

  const totalAgents = profiles.length;
  const kycComplete = profiles.filter(p => p.status === "complete" || p.status === "verified").length;
  const basicKyc = profiles.filter(p => p.status === "basic").length;
  const incomplete = profiles.filter(p => p.status === "incomplete").length;
  const verificationRate =
    totalAgents > 0 ? Math.round((kycComplete / totalAgents) * 100) : 0;

  const documents: Record<string, any[]> = liveProfiles
    ? Object.fromEntries(
        liveProfiles.map((p: any) => [
          p.agentId,
          (p._raw?.documents ?? []).map((d: any, i: number) => ({
            docId: d.id ?? `DOC-${i}`,
            type: d.document_type ?? d.type ?? "Unknown",
            number: d.document_number ?? "—",
            status: d.status ?? "pending",
            confidence: d.confidence_score ?? d.confidence ?? 0,
          })),
        ])
      )
    : FALLBACK_DOCUMENTS;

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-6 flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3">
            <div className="h-8 w-8 rounded-full border-4 border-blue-500 border-t-transparent animate-spin" />
            <p className="text-sm text-gray-400">Loading KYC data…</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">
              Agent KYC Verification
            </h1>
            {liveProfiles ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-900/50 text-green-400 text-xs font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
                Live data
              </span>
            ) : null}
          </div>
          <button
            onClick={() => setShowSubmitForm(!showSubmitForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500"
          >
            + Submit Document
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-yellow-600 bg-yellow-900/30 px-4 py-3 text-sm text-yellow-300">
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            Warning: Showing sample KYC data. KYC service unavailable — real agent approvals cannot be processed.
          </div>
        )}

        <div className="grid grid-cols-5 gap-4">
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-white">
              {totalAgents}
            </div>
            <div className="text-gray-400 text-sm">Total Agents</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-green-400">
              {kycComplete}
            </div>
            <div className="text-gray-400 text-sm">KYC Complete</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-yellow-400">
              {basicKyc}
            </div>
            <div className="text-gray-400 text-sm">Basic KYC</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-red-400">
              {incomplete}
            </div>
            <div className="text-gray-400 text-sm">Incomplete</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-blue-400">{verificationRate}%</div>
            <div className="text-gray-400 text-sm">Verification Rate</div>
          </div>
        </div>

        <div className="bg-gray-800 rounded overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="text-left p-3 text-gray-300 text-sm">Agent</th>
                <th className="text-left p-3 text-gray-300 text-sm">Name</th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  KYC Level
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Status
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Risk Score
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Documents
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p: any) => (
                <tr
                  key={p.agentId}
                  className="border-t border-gray-700 hover:bg-gray-750"
                >
                  <td className="p-3 text-white font-mono text-sm">
                    {p.agentId}
                  </td>
                  <td className="p-3 text-white">{p.name}</td>
                  <td
                    className={`p-3 text-center font-bold ${levelColor[p.kycLevel] ?? "text-gray-400"}`}
                  >
                    Level {p.kycLevel}
                  </td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-1 rounded text-xs ${p.status === "complete" || p.status === "verified" ? "bg-green-900 text-green-300" : p.status === "basic" ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"}`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td
                    className={`p-3 text-center ${p.risk > 60 ? "text-red-400" : p.risk > 30 ? "text-yellow-400" : "text-green-400"}`}
                  >
                    {p.risk}
                  </td>
                  <td className="p-3 text-center text-gray-300">
                    {p.verified}/{p.docs}
                  </td>
                  <td className="p-3 text-center">
                    <div className="flex items-center justify-center gap-1.5 flex-wrap">
                      <button
                        onClick={() =>
                          setSelectedAgent(
                            selectedAgent === p.agentId ? null : p.agentId
                          )
                        }
                        className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-500"
                      >
                        {selectedAgent === p.agentId ? "Hide" : "View"}
                      </button>
                      {(p.kycLevel >= 2 || p.status === "complete" || p.status === "verified") &&
                        p.status !== "approved" && p.status !== "suspended" && (
                        <button
                          disabled={actionLoading === p.agentId}
                          onClick={() => handleApprove(p)}
                          className="px-3 py-1 bg-green-700 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {actionLoading === p.agentId ? "…" : "Approve"}
                        </button>
                      )}
                      {p.status === "approved" && (
                        <button
                          disabled={actionLoading === p.agentId}
                          onClick={() => handleSuspend(p)}
                          className="px-3 py-1 bg-red-700 text-white rounded text-sm hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {actionLoading === p.agentId ? "…" : "Suspend"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedAgent && documents[selectedAgent] && documents[selectedAgent].length > 0 && (
          <div className="bg-gray-800 rounded p-4">
            <h3 className="text-lg font-semibold text-white mb-3">
              Documents for {selectedAgent}
            </h3>
            <div className="space-y-2">
              {documents[selectedAgent].map((doc: any) => (
                <div
                  key={doc.docId}
                  className="flex items-center justify-between bg-gray-700 rounded p-3"
                >
                  <div>
                    <span className="text-white font-mono text-sm">
                      {doc.docId}
                    </span>
                    <span className="text-gray-400 ml-3">
                      {doc.type}: {doc.number}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400 text-sm">
                      Confidence: {doc.confidence}%
                    </span>
                    <span
                      className={`px-2 py-1 rounded text-xs ${statusBg[doc.status] || "bg-gray-600 text-gray-300"}`}
                    >
                      {doc.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {selectedAgent && (!documents[selectedAgent] || documents[selectedAgent].length === 0) && (
          <div className="bg-gray-800 rounded p-4">
            <h3 className="text-lg font-semibold text-white mb-3">
              Documents for {selectedAgent}
            </h3>
            <p className="text-gray-400 text-sm">No documents on record for this agent.</p>
          </div>
        )}
      </div>

      {/* Toast notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-lg px-5 py-3 text-sm font-medium shadow-lg transition-all ${
            toast.type === "success"
              ? "bg-green-700 text-white"
              : "bg-red-700 text-white"
          }`}
        >
          <span>{toast.type === "success" ? "✓" : "✕"}</span>
          <span>{toast.msg}</span>
        </div>
      )}
    </DashboardLayout>
  );
}
