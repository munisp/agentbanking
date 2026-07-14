/**
 * Customer Wallet Management — View balance, transaction history, limits
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const balance = { data: null, isLoading: false, refetch: () => {} };
const profile = { data: null, isLoading: false, refetch: () => {} };
const txns = { data: null, isLoading: false, refetch: () => {} };
const stats = { data: null, isLoading: false, refetch: () => {} };

const formatCurrency = (n) =>
  `₦${Number(n).toLocaleString("en-NG", { minimumFractionDigits: 2 })}`;

export default function CustomerWallet() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const limit = 20;

  const totalPages = Math.ceil((txns.data?.total ?? 0) / limit);
  const filteredTxns = (txns.data?.items ?? []).filter((t) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      t.type?.toLowerCase().includes(q) ||
      t.reference?.toLowerCase().includes(q) ||
      t.status?.toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ minHeight: "100vh", background: "#020817", color: "#fff", padding: "24px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "8px" }}>
          💳 Customer Wallet
        </h1>
        <p style={{ color: "#94a3b8", fontSize: "14px", marginTop: "4px" }}>
          Manage your wallet balance, view transactions, and track spending
        </p>
      </div>

      {/* Balance & Limits */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        <div style={{ gridColumn: "span 2", background: "linear-gradient(135deg, rgba(30,58,138,0.4), rgba(30,64,175,0.2))", border: "1px solid rgba(29,78,216,0.4)", borderRadius: "12px", padding: "24px" }}>
          <div style={{ color: "#60a5fa", fontSize: "12px", fontWeight: "500", marginBottom: "8px" }}>💳 Wallet Balance</div>
          <div style={{ fontSize: "36px", fontWeight: "bold" }}>
            {balance.data ? formatCurrency(balance.data.walletBalance) : "—"}
          </div>
          <div style={{ color: "#64748b", fontSize: "12px", marginTop: "8px" }}>
            {profile.data?.firstName} {profile.data?.lastName} · {profile.data?.phone}
          </div>
        </div>
        <div style={{ background: "linear-gradient(135deg, rgba(20,83,45,0.4), rgba(22,101,52,0.2))", border: "1px solid rgba(21,128,61,0.4)", borderRadius: "12px", padding: "16px" }}>
          <div style={{ color: "#4ade80", fontSize: "12px", fontWeight: "500" }}>🛡️ Daily Limit</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: "4px" }}>
            {balance.data ? formatCurrency(balance.data.dailyLimit) : "—"}
          </div>
        </div>
        <div style={{ background: "linear-gradient(135deg, rgba(88,28,135,0.4), rgba(107,33,168,0.2))", border: "1px solid rgba(126,34,206,0.4)", borderRadius: "12px", padding: "16px" }}>
          <div style={{ color: "#c084fc", fontSize: "12px", fontWeight: "500" }}>📈 Monthly Limit</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: "4px" }}>
            {balance.data ? formatCurrency(balance.data.monthlyLimit) : "—"}
          </div>
        </div>
      </div>

      {/* Stats */}
      {stats.data && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px", marginBottom: "24px" }}>
          <div style={{ background: "rgba(15,23,42,0.5)", border: "1px solid #334155", borderRadius: "8px", padding: "12px", textAlign: "center" }}>
            <div style={{ color: "#64748b", fontSize: "12px" }}>Total Transactions</div>
            <div style={{ fontSize: "18px", fontWeight: "bold" }}>{stats.data.txCount}</div>
          </div>
          <div style={{ background: "rgba(15,23,42,0.5)", border: "1px solid #334155", borderRadius: "8px", padding: "12px", textAlign: "center" }}>
            <div style={{ color: "#64748b", fontSize: "12px" }}>Total Volume</div>
            <div style={{ fontSize: "18px", fontWeight: "bold" }}>{formatCurrency(stats.data.volume)}</div>
          </div>
        </div>
      )}

      {/* Transaction Search */}
      <div style={{ background: "rgba(15,23,42,0.5)", border: "1px solid #334155", borderRadius: "12px" }}>
        <div style={{ padding: "16px", borderBottom: "1px solid #334155" }}>
          <h3 style={{ fontSize: "14px", fontWeight: "600" }}>Transaction History</h3>
        </div>
        <div style={{ padding: "16px" }}>
          <div style={{ position: "relative", marginBottom: "16px" }}>
            <span style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#64748b" }}>🔍</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by type, reference, or status..."
              style={{ width: "100%", paddingLeft: "36px", padding: "8px 8px 8px 36px", background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#fff", outline: "none", boxSizing: "border-box" }}
            />
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155", color: "#64748b" }}>
                  <th style={{ padding: "8px 12px", textAlign: "left" }}>Date</th>
                  <th style={{ padding: "8px 12px", textAlign: "left" }}>Type</th>
                  <th style={{ padding: "8px 12px", textAlign: "left" }}>Reference</th>
                  <th style={{ padding: "8px 12px", textAlign: "right" }}>Amount</th>
                  <th style={{ padding: "8px 12px", textAlign: "left" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {txns.isLoading ? (
                  <tr><td colSpan={5} style={{ textAlign: "center", padding: "32px", color: "#64748b" }}>Loading...</td></tr>
                ) : filteredTxns.length === 0 ? (
                  <tr><td colSpan={5} style={{ textAlign: "center", padding: "32px", color: "#64748b" }}>No transactions found</td></tr>
                ) : (
                  filteredTxns.map((t) => (
                    <tr key={t.id} style={{ borderBottom: "1px solid rgba(51,65,85,0.5)" }}>
                      <td style={{ padding: "8px 12px", color: "#94a3b8" }}>{new Date(t.createdAt).toLocaleDateString()}</td>
                      <td style={{ padding: "8px 12px" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <span style={{ color: t.type?.includes("deposit") || t.type?.includes("in") ? "#4ade80" : "#f87171" }}>
                            {t.type?.includes("deposit") || t.type?.includes("in") ? "↙" : "↗"}
                          </span>
                          {t.type}
                        </span>
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#64748b", fontSize: "10px" }}>{t.reference}</td>
                      <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "monospace" }}>{formatCurrency(t.amount)}</td>
                      <td style={{ padding: "8px 12px" }}>
                        <span style={{
                          padding: "2px 8px",
                          borderRadius: "9999px",
                          fontSize: "10px",
                          border: `1px solid ${t.status === "completed" ? "#16a34a" : t.status === "pending" ? "#ca8a04" : "#dc2626"}`,
                          color: t.status === "completed" ? "#4ade80" : t.status === "pending" ? "#facc15" : "#f87171"
                        }}>
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "8px" }}>
              <span style={{ fontSize: "12px", color: "#64748b" }}>Page {page} of {totalPages}</span>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  style={{ padding: "4px 12px", background: "transparent", border: "1px solid #334155", borderRadius: "6px", color: "#cbd5e1", cursor: page <= 1 ? "not-allowed" : "pointer", opacity: page <= 1 ? 0.5 : 1 }}
                >
                  ‹
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  style={{ padding: "4px 12px", background: "transparent", border: "1px solid #334155", borderRadius: "6px", color: "#cbd5e1", cursor: page >= totalPages ? "not-allowed" : "pointer", opacity: page >= totalPages ? 0.5 : 1 }}
                >
                  ›
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
