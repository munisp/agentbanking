/**
 * Customer Surveys — Post-transaction NPS and CSAT collection
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const listQuery = { data: null, isLoading: false, refetch: () => {} };

export default function CustomerSurveys() {
  const mockData =
    listQuery.data ??
    Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      col1: `REF-${String(i + 1).padStart(3, "0")}`,
      col2: ["Chioma Eze","Emeka Obi","Fatima Bello","Adamu Yusuf","Grace Okonkwo","Ibrahim Musa","Joy Nwosu","Kemi Ade","Ladi Bako","Musa Dan"][i],
      col3: ["active","pending","completed","active","warning","active","completed","pending","active","completed"][i],
      col4: `${(Math.random() * 100).toFixed(1)}`,
      col5: new Date(Date.now() - i * 3600000).toLocaleString(),
    }));

  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  const kpis = [
    { label: "NPS Score", value: "+67" },
    { label: "CSAT Score", value: "4.3/5" },
    { label: "Responses", value: "8,421" },
    { label: "Response Rate", value: "34.2%" },
  ];

  const columns = ["Survey ID", "Customer", "NPS", "CSAT", "Date"];

  const filtered = mockData.filter(
    (r) =>
      r.col1.toLowerCase().includes(search.toLowerCase()) ||
      r.col2.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ minHeight: "100vh", background: "#0a0e17", color: "#fff", padding: "24px" }}>
      <div style={{ maxWidth: "1280px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h1 style={{ fontSize: "24px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "8px" }}>
              💬 Customer Surveys
            </h1>
            <p style={{ color: "#9ca3af", fontSize: "14px", marginTop: "4px" }}>Post-transaction NPS and CSAT collection</p>
          </div>
          <button style={{ padding: "8px 16px", background: "#2563eb", borderRadius: "8px", border: "none", color: "#fff", fontSize: "14px", cursor: "pointer" }}>
            New Entry
          </button>
        </div>

        {/* KPI Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", marginBottom: "24px" }}>
          {kpis.map((kpi, i) => (
            <div key={i} style={{ background: "#141a2a", border: "1px solid #1f2937", borderRadius: "8px", padding: "16px" }}>
              <p style={{ color: "#9ca3af", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>{kpi.label}</p>
              <p style={{ fontSize: "24px", fontWeight: "bold", marginTop: "4px" }}>{kpi.value}</p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          {["overview", "details", "history", "settings"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: "8px 16px", borderRadius: "8px", fontSize: "14px", fontWeight: "500", cursor: "pointer", border: "none",
                background: activeTab === tab ? "#2563eb" : "#141a2a",
                color: activeTab === tab ? "#fff" : "#9ca3af",
              }}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ marginBottom: "16px" }}>
          <input
            type="text"
            placeholder="Search records..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: "100%", maxWidth: "400px", padding: "8px 16px", background: "#141a2a", border: "1px solid #374151", borderRadius: "8px", fontSize: "14px", color: "#fff", outline: "none" }}
          />
        </div>

        {/* Table */}
        <div style={{ background: "#141a2a", border: "1px solid #1f2937", borderRadius: "8px", overflow: "hidden" }}>
          <div style={{ padding: "16px", borderBottom: "1px solid #1f2937" }}>
            <h3 style={{ fontWeight: "600" }}>Records ({filtered.length})</h3>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "14px", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #1f2937" }}>
                  {columns.map((col, i) => (
                    <th key={i} style={{ textAlign: "left", padding: "12px", color: "#9ca3af", fontWeight: "500" }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id} style={{ borderBottom: "1px solid rgba(31,41,55,0.5)" }}>
                    <td style={{ padding: "12px", fontFamily: "monospace", color: "#60a5fa" }}>{row.col1}</td>
                    <td style={{ padding: "12px" }}>{row.col2}</td>
                    <td style={{ padding: "12px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: "9999px", fontSize: "12px", fontWeight: "500",
                        background: row.col3 === "active" ? "rgba(34,197,94,0.2)" : row.col3 === "pending" ? "rgba(234,179,8,0.2)" : row.col3 === "warning" ? "rgba(239,68,68,0.2)" : "rgba(59,130,246,0.2)",
                        color: row.col3 === "active" ? "#4ade80" : row.col3 === "pending" ? "#facc15" : row.col3 === "warning" ? "#f87171" : "#60a5fa",
                      }}>
                        {row.col3}
                      </span>
                    </td>
                    <td style={{ padding: "12px" }}>{row.col4}</td>
                    <td style={{ padding: "12px", color: "#9ca3af" }}>{row.col5}</td>
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
