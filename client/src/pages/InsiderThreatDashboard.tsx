/**
 * InsiderThreatDashboard — Security Operations Center for Insider Threats
 * Route: /admin/insider-threat  (protected — admin + compliance roles)
 *
 * Sections:
 *  1. Threat Overview KPIs — alerts by severity, blocked agents, risk score distribution
 *  2. Pending Approvals — maker-checker workflow queue
 *  3. Threat Alerts Feed — real-time insider threat detections
 *  4. Audit Chain Status — hash-chain integrity verification
 *  5. Permission Conflicts — separation of duties violations
 *  6. Staff Activity Heatmap — behavioral patterns
 */
import { useState } from "react";
import { trpc } from "../lib/trpc";
import { toast } from "sonner";

type Severity = "critical" | "high" | "medium" | "low";
type AlertStatus = "active" | "investigating" | "resolved" | "dismissed";

interface ThreatAlert {
  id: string;
  threat_type: string;
  severity: Severity;
  agent_id: number;
  agent_code: string;
  description: string;
  evidence: Record<string, unknown>;
  risk_score: number;
  timestamp: string;
  recommended_action: string;
  auto_blocked: boolean;
}

interface ApprovalRequest {
  id: string;
  type: string;
  requestedBy: number;
  requestedByCode: string;
  amount: number;
  currency: string;
  resource: string;
  resourceId: string;
  status: string;
  requiredApprovals: number;
  approvals: Array<{ agentCode: string; timestamp: string }>;
  expiresAt: string;
  createdAt: string;
}

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#ca8a04",
  low: "#16a34a",
};

const SEVERITY_BG: Record<Severity, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-green-100 text-green-800 border-green-200",
};

export default function InsiderThreatDashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "approvals" | "alerts" | "audit" | "permissions">("overview");
  const [stepUpToken, setStepUpToken] = useState<string | null>(null);

  // Fetch dashboard data
  const dashboardQuery = trpc.insiderThreatManagement.getDashboard.useQuery(undefined, {
    refetchInterval: 30000,
  });

  // Fetch pending approvals
  const approvalsQuery = trpc.insiderThreatManagement.listPendingApprovals.useQuery(undefined, {
    refetchInterval: 10000,
  });

  // Fetch alerts
  const alertsQuery = trpc.insiderThreatManagement.getAlerts.useQuery(
    { limit: 100 },
    { refetchInterval: 15000 }
  );

  // Fetch audit chain status
  const verifyAuditQuery = trpc.insiderThreatManagement.verifyAuditChain.useQuery(undefined, {
    enabled: activeTab === "audit",
  });

  // Mutations
  const approveRequestMut = trpc.insiderThreatManagement.approveRequest.useMutation({
    onSuccess: () => {
      toast.success("Approval granted");
      approvalsQuery.refetch();
    },
    onError: (err: any) => toast.error(err.message),
  });

  const rejectRequestMut = trpc.insiderThreatManagement.rejectRequest.useMutation({
    onSuccess: () => {
      toast.success("Request rejected");
      approvalsQuery.refetch();
    },
    onError: (err: any) => toast.error(err.message),
  });

  const requestStepUpMut = trpc.insiderThreatManagement.requestStepUp.useMutation({
    onSuccess: (data: any) => {
      setStepUpToken(data.token);
      toast.success("Step-up authentication verified (5 min validity)");
    },
    onError: (err: any) => toast.error(err.message),
  });

  // Derived state
  const dashboardData = dashboardQuery.data as any;
  const pendingApprovals: ApprovalRequest[] = (approvalsQuery.data as any)?.approvals ?? [];
  const alerts: ThreatAlert[] = (alertsQuery.data as any)?.alerts ?? [];
  const auditStatus = (verifyAuditQuery.data as any) ?? null;

  const detection = dashboardData?.detection ?? {
    total_alerts: 0,
    alerts_by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
    blocked_agents: 0,
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Insider Threat Management</h1>
          <p className="text-sm text-gray-500 mt-1">Security operations — separation of duties, approval workflows, behavioral monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${detection.blocked_agents > 0 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
            {detection.blocked_agents > 0 ? `${detection.blocked_agents} Blocked` : "All Clear"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {(["overview", "approvals", "alerts", "audit", "permissions"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === "approvals" && pendingApprovals.length > 0 && (
                <span className="ml-1 bg-orange-500 text-white text-xs rounded-full px-2 py-0.5">
                  {pendingApprovals.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <KPICard
              title="Critical Alerts"
              value={detection.alerts_by_severity?.critical ?? 0}
              color="text-red-600"
              bg="bg-red-50"
            />
            <KPICard
              title="High Alerts"
              value={detection.alerts_by_severity?.high ?? 0}
              color="text-orange-600"
              bg="bg-orange-50"
            />
            <KPICard
              title="Pending Approvals"
              value={pendingApprovals.length}
              color="text-indigo-600"
              bg="bg-indigo-50"
            />
            <KPICard
              title="Blocked Agents"
              value={detection.blocked_agents}
              color="text-red-600"
              bg="bg-red-50"
            />
          </div>

          {/* Thresholds Info */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Approval Thresholds</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-green-50 rounded-lg">
                <div className="text-sm font-medium text-green-700">Tier 1 — Standard</div>
                <div className="text-xs text-green-600">₦0 – ₦500,000</div>
                <div className="text-xs text-green-600 mt-1">No additional approval</div>
              </div>
              <div className="p-3 bg-yellow-50 rounded-lg">
                <div className="text-sm font-medium text-yellow-700">Tier 2 — Dual Control</div>
                <div className="text-xs text-yellow-600">₦500,001 – ₦5,000,000</div>
                <div className="text-xs text-yellow-600 mt-1">1 additional approver</div>
              </div>
              <div className="p-3 bg-red-50 rounded-lg">
                <div className="text-sm font-medium text-red-700">Tier 3 — Compliance Review</div>
                <div className="text-xs text-red-600">₦5,000,001+</div>
                <div className="text-xs text-red-600 mt-1">2 approvers + 30-min cooling</div>
              </div>
            </div>
          </div>

          {/* Separation of Duties Summary */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Separation of Duties Rules</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>No agent can approve their own reversal, loan, commission, or float adjustment</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Financial Maker and Financial Approver roles are mutually exclusive</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Self-permission assignment is blocked</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Step-up authentication required for all approval actions</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Admin sessions timeout after 15 minutes of inactivity</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Approvals Tab */}
      {activeTab === "approvals" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Pending Approval Requests</h2>
            {!stepUpToken && (
              <StepUpAuthButton onAuthenticate={(password) => requestStepUpMut.mutate({ password })} />
            )}
            {stepUpToken && (
              <span className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded-full">
                Step-up verified ✓
              </span>
            )}
          </div>

          {pendingApprovals.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No pending approvals</div>
          ) : (
            pendingApprovals.map(approval => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                stepUpToken={stepUpToken}
                onApprove={(id) => {
                  if (!stepUpToken) {
                    toast.error("Step-up authentication required");
                    return;
                  }
                  approveRequestMut.mutate({ requestId: id, stepUpToken });
                }}
                onReject={(id, reason) => rejectRequestMut.mutate({ requestId: id, reason })}
              />
            ))
          )}
        </div>
      )}

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold mb-4">Insider Threat Alerts</h2>
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No alerts detected</div>
          ) : (
            alerts.map((alert, i) => (
              <AlertCard key={alert.id ?? i} alert={alert} />
            ))
          )}
        </div>
      )}

      {/* Audit Tab */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold mb-4">Audit Chain Integrity</h2>
          {auditStatus && (
            <div className={`p-4 rounded-lg border ${auditStatus.valid ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
              <div className="flex items-center gap-2">
                <span className={`text-xl ${auditStatus.valid ? "text-green-600" : "text-red-600"}`}>
                  {auditStatus.valid ? "🔒" : "⚠️"}
                </span>
                <div>
                  <div className={`font-semibold ${auditStatus.valid ? "text-green-800" : "text-red-800"}`}>
                    {auditStatus.valid ? "Chain Intact" : "TAMPERING DETECTED"}
                  </div>
                  <div className="text-sm text-gray-600">{auditStatus.message}</div>
                  <div className="text-xs text-gray-500 mt-1">Total entries: {auditStatus.total_entries}</div>
                </div>
              </div>
            </div>
          )}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-900 mb-2">How it works</h3>
            <p className="text-sm text-gray-600">
              Every privileged action is recorded in a SHA-256 hash chain. Each entry contains the hash of the
              previous entry, creating a tamper-evident log. If any record is modified or deleted, the chain
              verification will detect the inconsistency. Entries are also forwarded in real-time to an external
              SIEM for independent verification.
            </p>
          </div>
        </div>
      )}

      {/* Permissions Tab */}
      {activeTab === "permissions" && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold mb-4">Granular Permission Model</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <RoleCard
              role="Agent Operator"
              permissions={["Create Cash-In", "Create Cash-Out", "View Transactions"]}
              incompatible={["Financial Approver", "System Admin"]}
            />
            <RoleCard
              role="Financial Maker"
              permissions={["Create Loans", "Create Reversals", "Create Commissions", "Create FX"]}
              incompatible={["Financial Approver"]}
            />
            <RoleCard
              role="Financial Approver"
              permissions={["Approve Reversals", "Approve Loans", "Approve Commissions", "Approve FX"]}
              incompatible={["Financial Maker"]}
            />
            <RoleCard
              role="Compliance Officer"
              permissions={["View Audit Log", "Export Data", "View Reports"]}
              incompatible={["Financial Maker", "Financial Approver"]}
            />
            <RoleCard
              role="System Admin"
              permissions={["Manage Agents", "Manage Roles", "System Config"]}
              incompatible={["Financial Maker", "Financial Approver"]}
            />
            <RoleCard
              role="Break Glass (Emergency)"
              permissions={["Emergency Override Access (time-limited, fully audited)"]}
              incompatible={[]}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-Components ───────────────────────────────────────────────────────────

function KPICard({ title, value, color, bg }: { title: string; value: number; color: string; bg: string }) {
  return (
    <div className={`${bg} rounded-lg p-4 border`}>
      <div className="text-sm text-gray-600">{title}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function ApprovalCard({
  approval,
  stepUpToken,
  onApprove,
  onReject,
}: {
  approval: ApprovalRequest;
  stepUpToken: string | null;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
}) {
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium text-gray-900">{approval.type.replace(/_/g, " ")}</div>
          <div className="text-sm text-gray-500">
            Requested by: <span className="font-mono">{approval.requestedByCode}</span>
          </div>
          <div className="text-sm text-gray-500">
            Amount: <span className="font-semibold">₦{approval.amount.toLocaleString()}</span> {approval.currency}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {approval.approvals.length}/{approval.requiredApprovals} approvals • Expires {new Date(approval.expiresAt).toLocaleString()}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onApprove(approval.id)}
            disabled={!stepUpToken}
            className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Approve
          </button>
          <button
            onClick={() => setShowReject(!showReject)}
            className="px-3 py-1.5 bg-red-600 text-white text-sm rounded-md hover:bg-red-700"
          >
            Reject
          </button>
        </div>
      </div>
      {showReject && (
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
            placeholder="Rejection reason (min 5 chars)"
            className="flex-1 px-3 py-1.5 border rounded-md text-sm"
          />
          <button
            onClick={() => {
              if (rejectReason.length >= 5) {
                onReject(approval.id, rejectReason);
                setShowReject(false);
                setRejectReason("");
              }
            }}
            disabled={rejectReason.length < 5}
            className="px-3 py-1.5 bg-red-600 text-white text-sm rounded-md disabled:opacity-50"
          >
            Confirm
          </button>
        </div>
      )}
    </div>
  );
}

function AlertCard({ alert }: { alert: ThreatAlert }) {
  return (
    <div className={`rounded-lg border p-4 ${SEVERITY_BG[alert.severity]}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase`}>
            {alert.severity}
          </span>
          <span className="font-medium text-sm">{alert.threat_type.replace(/_/g, " ")}</span>
        </div>
        <span className="text-xs text-gray-500">{new Date(alert.timestamp).toLocaleString()}</span>
      </div>
      <div className="mt-2 text-sm">{alert.description}</div>
      <div className="mt-1 text-xs text-gray-600">
        Agent: <span className="font-mono">{alert.agent_code}</span> • Risk Score: {alert.risk_score}/100
        {alert.auto_blocked && <span className="ml-2 text-red-700 font-bold">AUTO-BLOCKED</span>}
      </div>
      <div className="mt-2 text-xs text-gray-500 italic">
        Recommended: {alert.recommended_action}
      </div>
    </div>
  );
}

function StepUpAuthButton({ onAuthenticate }: { onAuthenticate: (password: string) => void }) {
  const [showModal, setShowModal] = useState(false);
  const [password, setPassword] = useState("");

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
      >
        Authenticate for Approvals
      </button>
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="font-semibold text-lg mb-2">Step-Up Authentication</h3>
            <p className="text-sm text-gray-500 mb-4">
              Re-enter your password to verify your identity for approval actions.
            </p>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password"
              className="w-full px-3 py-2 border rounded-md mb-4"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-600 text-sm">
                Cancel
              </button>
              <button
                onClick={() => {
                  onAuthenticate(password);
                  setShowModal(false);
                  setPassword("");
                }}
                disabled={!password}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md disabled:opacity-50"
              >
                Verify
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function RoleCard({
  role,
  permissions,
  incompatible,
}: {
  role: string;
  permissions: string[];
  incompatible: string[];
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="font-semibold text-gray-900 mb-2">{role}</div>
      <div className="space-y-1">
        {permissions.map(p => (
          <div key={p} className="text-xs text-gray-600 flex items-center gap-1">
            <span className="text-green-500">✓</span> {p}
          </div>
        ))}
      </div>
      {incompatible.length > 0 && (
        <div className="mt-2 pt-2 border-t">
          <div className="text-xs text-red-600 font-medium">Cannot hold simultaneously:</div>
          {incompatible.map(r => (
            <div key={r} className="text-xs text-red-500 flex items-center gap-1">
              <span>✗</span> {r}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
