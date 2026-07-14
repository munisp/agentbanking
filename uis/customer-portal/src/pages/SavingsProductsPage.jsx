/**
 * Savings Products — Daily thrift (ajo/esusu), target savings, fixed deposits
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const products = { data: null, isLoading: false, refetch: () => {} };
const accounts = { data: null, isLoading: false, refetch: () => {} };
const transactions = { data: null, isLoading: false, refetch: () => {} };
const analytics = { data: null, isLoading: false, refetch: () => {} };

const cardStyle = { background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" };

export default function SavingsProductsPage() {
  const [tab, setTab] = useState("products");

  return (
    <div style={{ padding: "24px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: "bold" }}>Savings Products</h1>
        <p style={{ color: "#6b7280" }}>Agent-facilitated savings — daily thrift (ajo/esusu), target savings, fixed deposits</p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        {[
          { label: "Total Deposits", value: `NGN ${(analytics.data?.totalDeposits ?? 0).toLocaleString()}` },
          { label: "Active Accounts", value: analytics.data?.activeAccounts ?? 0 },
          { label: "Interest Paid", value: `NGN ${(analytics.data?.totalInterestPaid ?? 0).toLocaleString()}` },
          { label: "Active Savings Accounts", value: analytics.data?.activeAccounts ?? 0 },
        ].map((kpi, i) => (
          <div key={i} style={cardStyle}>
            <p style={{ fontSize: "13px", color: "#6b7280", marginBottom: "4px" }}>{kpi.label}</p>
            <p style={{ fontSize: "24px", fontWeight: "bold" }}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Tab Buttons */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px" }}>
        {[{ id: "products", label: "🐷 Products" }, { id: "accounts", label: "👥 Accounts" }, { id: "transactions", label: "📅 Transactions" }].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{ padding: "8px 16px", border: `1px solid ${tab === t.id ? "#2563eb" : "#d1d5db"}`, borderRadius: "6px", background: tab === t.id ? "#2563eb" : "#fff", color: tab === t.id ? "#fff" : "#374151", cursor: "pointer", fontSize: "13px", fontWeight: "500" }}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "products" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
          {products.data?.products?.length ? products.data.products.map((p) => (
            <div key={p.id} style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <h3 style={{ fontWeight: "bold" }}>{p.name}</h3>
                <span style={{ padding: "2px 8px", background: "#dbeafe", color: "#1d4ed8", borderRadius: "9999px", fontSize: "11px" }}>{p.type}</span>
              </div>
              <p style={{ fontSize: "13px", color: "#6b7280", marginBottom: "12px" }}>{p.description}</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                <div><span style={{ color: "#6b7280" }}>Min Deposit:</span><p style={{ fontWeight: "bold" }}>NGN {p.minDeposit?.toLocaleString()}</p></div>
                <div><span style={{ color: "#6b7280" }}>Interest Rate:</span><p style={{ fontWeight: "bold" }}>{p.interestRate}% p.a.</p></div>
                <div><span style={{ color: "#6b7280" }}>Lock Period:</span><p style={{ fontWeight: "bold" }}>{p.lockPeriod}</p></div>
                <div><span style={{ color: "#6b7280" }}>Frequency:</span><p style={{ fontWeight: "bold" }}>{p.frequency}</p></div>
              </div>
            </div>
          )) : <p style={{ color: "#9ca3af" }}>No products available</p>}
        </div>
      )}

      {tab === "accounts" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>Savings Accounts</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "13px", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                  {["Account","Customer","Product","Balance","Target","Status"].map((h) => (
                    <th key={h} style={{ padding: "8px", textAlign: "left", color: "#6b7280", fontWeight: "500" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accounts.data?.accounts?.length ? accounts.data.accounts.map((a) => (
                  <tr key={a.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px", fontFamily: "monospace", fontSize: "11px" }}>{a.accountNo}</td>
                    <td style={{ padding: "8px" }}>{a.customerName}</td>
                    <td style={{ padding: "8px" }}>{a.productName}</td>
                    <td style={{ padding: "8px", textAlign: "right", fontWeight: "bold" }}>NGN {a.balance?.toLocaleString()}</td>
                    <td style={{ padding: "8px", textAlign: "right" }}>NGN {a.targetAmount?.toLocaleString()}</td>
                    <td style={{ padding: "8px" }}>
                      <span style={{ padding: "2px 8px", borderRadius: "9999px", fontSize: "11px", background: a.status === "active" ? "#d1fae5" : "#f3f4f6", color: a.status === "active" ? "#065f46" : "#374151" }}>{a.status}</span>
                    </td>
                  </tr>
                )) : <tr><td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#9ca3af" }}>No accounts found</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "transactions" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>Recent Transactions</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "13px", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                  {["Account","Type","Amount","Agent","Date"].map((h) => (
                    <th key={h} style={{ padding: "8px", textAlign: "left", color: "#6b7280", fontWeight: "500" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactions.data?.accounts?.length ? transactions.data.accounts.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px", fontFamily: "monospace", fontSize: "11px" }}>{t.accountNo}</td>
                    <td style={{ padding: "8px" }}>
                      <span style={{ padding: "2px 8px", borderRadius: "9999px", fontSize: "11px", background: t.type === "deposit" ? "#d1fae5" : "#f3f4f6", color: t.type === "deposit" ? "#065f46" : "#374151" }}>{t.type}</span>
                    </td>
                    <td style={{ padding: "8px", textAlign: "right", fontWeight: "bold" }}>NGN {t.amount?.toLocaleString()}</td>
                    <td style={{ padding: "8px" }}>{t.agentName}</td>
                    <td style={{ padding: "8px", fontSize: "12px", color: "#6b7280" }}>{new Date(t.createdAt).toLocaleString()}</td>
                  </tr>
                )) : <tr><td colSpan={5} style={{ padding: "24px", textAlign: "center", color: "#9ca3af" }}>No transactions found</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
