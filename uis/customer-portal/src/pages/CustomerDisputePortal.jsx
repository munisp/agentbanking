/**
 * Customer Dispute Portal — Self-service dispute filing, tracking, and resolution
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const stats = { data: null, isLoading: false, refetch: () => {} };
const disputes = { data: null, isLoading: false, refetch: () => {} };
const fileMutation = { mutate: () => {}, isPending: false };
const updateMutation = { mutate: () => {}, isPending: false };
const escalateMutation = { mutate: () => {}, isPending: false };

const statusColor = {
  filed: { bg: "rgba(59,130,246,0.2)", text: "#60a5fa" },
  investigating: { bg: "rgba(245,158,11,0.2)", text: "#fbbf24" },
  resolved: { bg: "rgba(34,197,94,0.2)", text: "#4ade80" },
  escalated: { bg: "rgba(239,68,68,0.2)", text: "#f87171" },
};

const cardStyle = { background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" };

export default function CustomerDisputePortal() {
  const [activeTab, setActiveTab] = useState("overview");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [fileOpen, setFileOpen] = useState(false);
  const [fileForm, setFileForm] = useState({ transactionId: "", reason: "", description: "" });

  const filteredDisputes = (disputes.data?.disputes ?? []).filter(
    (d) =>
      !search ||
      d.id.toLowerCase().includes(search.toLowerCase()) ||
      d.customerName.toLowerCase().includes(search.toLowerCase()) ||
      d.transactionId.toLowerCase().includes(search.toLowerCase())
  );

  const isLoading = stats.isLoading || disputes.isLoading;

  const tabDisputes = activeTab === "open"
    ? filteredDisputes.filter((d) => d.status === "filed" || d.status === "investigating")
    : activeTab === "resolved"
    ? filteredDisputes.filter((d) => d.status === "resolved")
    : filteredDisputes;

  return (
    <div style={{ padding: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "8px" }}>
            🛡️ Customer Dispute Portal
          </h1>
          <p style={{ color: "#6b7280" }}>Self-service dispute filing, tracking, and resolution</p>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button onClick={() => alert("Data refreshed")} style={{ padding: "6px 12px", border: "1px solid #d1d5db", borderRadius: "6px", background: "transparent", cursor: "pointer", fontSize: "13px" }}>
            🔄 Refresh
          </button>
          <button onClick={() => setFileOpen(true)} style={{ padding: "6px 12px", background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "13px" }}>
            + File Dispute
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "12px", marginBottom: "20px" }}>
        {[
          { label: "Total Disputes", value: stats.data?.totalDisputes?.toLocaleString() ?? "—", sub: "All time" },
          { label: "Open", value: stats.data?.open ?? "—", sub: "Awaiting action", color: "#d97706" },
          { label: "Investigating", value: stats.data?.investigating ?? "—", sub: "In progress", color: "#2563eb" },
          { label: "Resolved", value: stats.data?.resolved ?? "—", sub: "Closed", color: "#16a34a" },
          { label: "SLA Compliance", value: stats.data?.slaCompliance ? `${stats.data.slaCompliance}%` : "—", sub: `Avg ${stats.data?.avgResolutionDays ?? "—"} days` },
        ].map((kpi, i) => (
          <div key={i} style={cardStyle}>
            <p style={{ fontSize: "12px", color: "#6b7280", marginBottom: "4px" }}>{kpi.label}</p>
            <div style={{ fontSize: "24px", fontWeight: "bold", color: kpi.color ?? "inherit" }}>{isLoading ? "—" : kpi.value}</div>
            <p style={{ fontSize: "11px", color: "#9ca3af", marginTop: "2px" }}>{kpi.sub}</p>
          </div>
        ))}
      </div>

      {/* Additional stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px", marginBottom: "20px" }}>
        <div style={{ ...cardStyle, background: "#f9fafb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><p style={{ fontSize: "12px", color: "#6b7280" }}>Refund Rate</p><p style={{ fontSize: "20px", fontWeight: "bold" }}>{isLoading ? "—" : `${stats.data?.refundRate ?? "—"}%`}</p></div>
          <span style={{ color: "#22c55e", fontSize: "20px" }}>↗</span>
        </div>
        <div style={{ ...cardStyle, background: "#f9fafb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><p style={{ fontSize: "12px", color: "#6b7280" }}>Escalation Rate</p><p style={{ fontSize: "20px", fontWeight: "bold" }}>{isLoading ? "—" : `${stats.data?.escalationRate ?? "—"}%`}</p></div>
          <span style={{ color: "#f59e0b", fontSize: "20px" }}>⚠️</span>
        </div>
        <div style={{ ...cardStyle, background: "#f9fafb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><p style={{ fontSize: "12px", color: "#6b7280" }}>Pending Amount</p><p style={{ fontSize: "20px", fontWeight: "bold" }}>₦{isLoading ? "—" : (stats.data?.pendingAmount ?? 0).toLocaleString()}</p></div>
          <span style={{ fontSize: "20px" }}>🛡️</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "16px", borderBottom: "1px solid #e5e7eb" }}>
        {[{ id: "overview", label: "All Disputes" }, { id: "open", label: "Open / Investigating" }, { id: "resolved", label: "Resolved" }].map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === t.id ? "2px solid #2563eb" : "2px solid transparent", background: "transparent", cursor: "pointer", fontWeight: activeTab === t.id ? "600" : "400", color: activeTab === t.id ? "#2563eb" : "#6b7280" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: 1, minWidth: "200px" }}>
          <span style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "#9ca3af" }}>🔍</span>
          <input placeholder="Search by ID, customer, or transaction..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: "100%", padding: "8px 8px 8px 32px", border: "1px solid #d1d5db", borderRadius: "6px", outline: "none", boxSizing: "border-box" }} />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", background: "#fff", cursor: "pointer" }}>
          <option value="all">All Statuses</option>
          <option value="filed">Filed</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* Disputes Table */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: "13px", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
                {["Dispute ID","Transaction","Customer","Amount","Reason","Priority","Status","SLA Deadline","Actions"].map((h) => (
                  <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: "#6b7280", fontWeight: "500", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: "32px", color: "#9ca3af" }}>Loading disputes...</td></tr>
              ) : tabDisputes.length === 0 ? (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: "32px", color: "#9ca3af" }}>No disputes found.</td></tr>
              ) : (
                tabDisputes.map((d) => {
                  const slaRemaining = d.slaDeadline ? Math.max(0, Math.ceil((d.slaDeadline - Date.now()) / 86400000)) : null;
                  const slaBreach = slaRemaining !== null && slaRemaining <= 0;
                  const sc = statusColor[d.status] ?? { bg: "rgba(107,114,128,0.2)", text: "#6b7280" };
                  return (
                    <tr key={d.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "10px 12px", fontFamily: "monospace", fontSize: "11px", fontWeight: "bold" }}>{d.id}</td>
                      <td style={{ padding: "10px 12px", fontFamily: "monospace", fontSize: "11px" }}>{d.transactionId}</td>
                      <td style={{ padding: "10px 12px" }}>{d.customerName}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontWeight: "bold" }}>₦{d.amount?.toLocaleString()}</td>
                      <td style={{ padding: "10px 12px", textTransform: "capitalize" }}>{d.reason?.replace(/_/g, " ")}</td>
                      <td style={{ padding: "10px 12px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: "9999px", fontSize: "11px", background: ["critical","high"].includes(d.priority) ? "#fee2e2" : "#f3f4f6", color: ["critical","high"].includes(d.priority) ? "#dc2626" : "#374151" }}>
                          {d.priority}
                        </span>
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        <span style={{ padding: "3px 10px", borderRadius: "9999px", fontSize: "11px", background: sc.bg, color: sc.text }}>{d.status}</span>
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: "11px" }}>
                        {slaRemaining !== null && (
                          <span style={{ color: slaBreach ? "#dc2626" : slaRemaining <= 2 ? "#f59e0b" : "#6b7280", fontWeight: slaBreach ? "bold" : "normal" }}>
                            {slaBreach ? "BREACHED" : `${slaRemaining}d remaining`}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        <div style={{ display: "flex", gap: "4px" }}>
                          {d.status === "filed" && (
                            <button disabled={updateMutation.isPending} onClick={() => updateMutation.mutate({ disputeId: d.id, status: "investigating" })} style={{ padding: "3px 8px", fontSize: "11px", border: "1px solid #d1d5db", borderRadius: "4px", background: "#fff", cursor: "pointer" }}>Investigate</button>
                          )}
                          {d.status === "investigating" && (
                            <button disabled={updateMutation.isPending} onClick={() => updateMutation.mutate({ disputeId: d.id, status: "resolved" })} style={{ padding: "3px 8px", fontSize: "11px", border: "1px solid #d1d5db", borderRadius: "4px", background: "#fff", cursor: "pointer" }}>Resolve</button>
                          )}
                          {!d.escalated && d.status !== "resolved" && (
                            <button disabled={escalateMutation.isPending} onClick={() => escalateMutation.mutate({ disputeId: d.id, reason: "Requires senior review" })} style={{ padding: "3px 8px", fontSize: "11px", border: "none", background: "transparent", color: "#dc2626", cursor: "pointer" }}>Escalate</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* File Dispute Modal */}
      {fileOpen && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", width: "480px", maxWidth: "90vw" }}>
            <h2 style={{ fontSize: "18px", fontWeight: "bold", marginBottom: "20px" }}>File New Dispute</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "13px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Transaction ID</label>
                <input placeholder="TXN-XXXXX" value={fileForm.transactionId} onChange={(e) => setFileForm((p) => ({ ...p, transactionId: e.target.value }))} style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", outline: "none", boxSizing: "border-box" }} />
              </div>
              <div>
                <label style={{ fontSize: "13px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Reason</label>
                <select value={fileForm.reason} onChange={(e) => setFileForm((p) => ({ ...p, reason: e.target.value }))} style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", background: "#fff", outline: "none" }}>
                  <option value="">Select reason</option>
                  <option value="unauthorized">Unauthorized Transaction</option>
                  <option value="duplicate">Duplicate Charge</option>
                  <option value="not_received">Service Not Received</option>
                  <option value="defective">Defective Service</option>
                  <option value="wrong_amount">Wrong Amount</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: "13px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Description</label>
                <textarea placeholder="Describe the issue in detail..." value={fileForm.description} onChange={(e) => setFileForm((p) => ({ ...p, description: e.target.value }))} rows={4} style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", outline: "none", resize: "vertical", boxSizing: "border-box" }} />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "20px" }}>
              <button onClick={() => setFileOpen(false)} style={{ padding: "8px 16px", border: "1px solid #d1d5db", borderRadius: "6px", background: "transparent", cursor: "pointer" }}>Cancel</button>
              <button
                disabled={!fileForm.transactionId || !fileForm.reason || !fileForm.description || fileMutation.isPending}
                onClick={() => { fileMutation.mutate(fileForm); setFileOpen(false); }}
                style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", opacity: (!fileForm.transactionId || !fileForm.reason || !fileForm.description) ? 0.5 : 1 }}
              >
                {fileMutation.isPending ? "Filing..." : "Submit Dispute"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
