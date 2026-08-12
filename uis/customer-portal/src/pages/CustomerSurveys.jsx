/**
 * Customer Surveys — Post-transaction NPS and CSAT collection
 * Migrated from NGApp — no shadcn/ui
 *
 * NOTE: The customer portal has no surveys/feedback API wired to it.
 * This page fails loud: it renders an honest unavailable state instead of
 * fabricated rows or hardcoded KPI figures.
 */
import { useState } from "react";

export default function CustomerSurveys() {
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  // No surveys data source is available to this portal.
  const records = [];
  const loadError =
    "Survey data is not available. The surveys service is not connected to this portal.";

  // No KPI aggregates are available without a data source — render "—"
  // rather than hardcoded figures.
  const kpis = [
    { label: "NPS Score", value: "—" },
    { label: "CSAT Score", value: "—" },
    { label: "Responses", value: "—" },
    { label: "Response Rate", value: "—" },
  ];

  const columns = ["Survey ID", "Customer", "NPS", "CSAT", "Date"];

  const filtered = records.filter(
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
                <tr>
                  <td
                    colSpan={columns.length}
                    style={{ padding: "24px", textAlign: "center", color: "#f87171" }}
                  >
                    {loadError}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
