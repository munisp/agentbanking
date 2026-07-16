/**
 * Customer Feedback & NPS System
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const statsQuery = { data: null, isLoading: false, refetch: () => {} };

export default function CustomerFeedbackNps() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  const stats = statsQuery.data;

  const statCards = [
    { label: "Total Feedback", value: stats?.totalFeedback != null ? String(stats.totalFeedback) : "—" },
    { label: "Avg Rating", value: stats?.avgRating != null ? String(stats.avgRating) : "—" },
    { label: "NPS Score", value: stats?.npsScore != null ? String(stats.npsScore) : "—" },
    { label: "Promoters", value: stats?.promoters != null ? String(stats.promoters) : "—" },
  ];

  const cardStyle = { background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" };

  return (
    <div style={{ padding: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: "bold" }}>Customer Feedback & NPS System</h1>
          <p style={{ color: "#6b7280", marginTop: "4px" }}>Post-transaction surveys, NPS scoring, sentiment analysis</p>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", outline: "none", width: "200px" }}
          />
          <button
            onClick={() => alert("Data refreshed")}
            style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer" }}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        {statCards.map((card, i) => (
          <div key={i} style={cardStyle}>
            <p style={{ fontSize: "12px", color: "#6b7280", marginBottom: "8px" }}>{card.label}</p>
            <div style={{ fontSize: "24px", fontWeight: "bold" }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "16px", borderBottom: "1px solid #e5e7eb" }}>
        {["overview", "details", "settings"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 16px", border: "none", borderBottom: activeTab === tab ? "2px solid #2563eb" : "2px solid transparent",
              background: "transparent", cursor: "pointer", fontWeight: activeTab === tab ? "600" : "400",
              color: activeTab === tab ? "#2563eb" : "#6b7280", textTransform: "capitalize"
            }}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "16px" }}>Summary</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
            {stats
              ? Object.entries(stats).map(([key, value]) => (
                  <div key={key} style={{ padding: "12px", borderRadius: "8px", background: "#f9fafb" }}>
                    <div style={{ fontSize: "12px", color: "#6b7280" }}>{key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}</div>
                    <div style={{ fontSize: "18px", fontWeight: "600", marginTop: "4px" }}>
                      {typeof value === "number" ? value.toLocaleString() : typeof value === "object" ? JSON.stringify(value) : String(value)}
                    </div>
                  </div>
                ))
              : <p style={{ color: "#9ca3af" }}>No data available — connect to live services to see metrics.</p>}
          </div>
        </div>
      )}

      {activeTab === "details" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "16px" }}>Detailed View</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#eff6ff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", fontWeight: "500" }}>{i + 1}</div>
                  <div>
                    <div style={{ fontWeight: "500" }}>Item {i + 1}</div>
                    <div style={{ fontSize: "12px", color: "#6b7280" }}>Updated {i + 1}h ago</div>
                  </div>
                </div>
                <span style={{ padding: "2px 10px", borderRadius: "9999px", fontSize: "12px", background: ["#dbeafe", "#f3f4f6", "#f0fdf4"][i % 3], color: ["#1d4ed8", "#374151", "#15803d"][i % 3] }}>
                  {["Active", "Pending", "Completed"][i % 3]}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "settings" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "16px" }}>Configuration</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
            <div>
              <label style={{ fontSize: "14px", fontWeight: "500" }}>Setting 1</label>
              <input placeholder="Value" style={{ display: "block", marginTop: "4px", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", width: "100%", boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: "14px", fontWeight: "500" }}>Setting 2</label>
              <input placeholder="Value" style={{ display: "block", marginTop: "4px", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", width: "100%", boxSizing: "border-box" }} />
            </div>
          </div>
          <button onClick={() => alert("Settings saved")} style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer" }}>
            Save Settings
          </button>
        </div>
      )}
    </div>
  );
}
