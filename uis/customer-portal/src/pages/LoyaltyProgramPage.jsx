/**
 * Loyalty Program — Customer loyalty tiers, points, and rewards management
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */
import { useState } from "react";

const statsQuery = { data: null, isLoading: false, refetch: () => {} };

const cardStyle = { background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" };

export default function LoyaltyProgramPage() {
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  return (
    <div style={{ padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "bold" }}>Loyalty Program</h1>
          <p style={{ color: "#6b7280", marginTop: "4px" }}>Customer loyalty tiers, points, and rewards management</p>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: "6px", outline: "none", width: "200px" }} />
          <button onClick={() => alert("Data refreshed")} style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer" }}>Refresh</button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "20px", borderBottom: "1px solid #e5e7eb" }}>
        {["overview", "details", "settings"].map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={{ padding: "8px 16px", border: "none", borderBottom: activeTab === tab ? "2px solid #2563eb" : "2px solid transparent", background: "transparent", cursor: "pointer", fontWeight: activeTab === tab ? "600" : "400", color: activeTab === tab ? "#2563eb" : "#6b7280", textTransform: "capitalize" }}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", marginBottom: "20px" }}>
            {statsQuery.isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={{ ...cardStyle, height: "100px", background: "#f3f4f6", animation: "pulse 1.5s infinite" }} />
                ))
              : statsQuery.data
              ? Object.entries(statsQuery.data).slice(0, 4).map(([key, value]) => (
                  <div key={key} style={cardStyle}>
                    <p style={{ fontSize: "13px", color: "#6b7280", textTransform: "capitalize" }}>{key.replace(/([A-Z])/g, " $1").trim()}</p>
                    <p style={{ fontSize: "24px", fontWeight: "bold", marginTop: "4px" }}>{typeof value === "number" ? value.toLocaleString() : String(value)}</p>
                  </div>
                ))
              : Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={cardStyle}>
                    <p style={{ fontSize: "13px", color: "#6b7280" }}>—</p>
                    <p style={{ fontSize: "24px", fontWeight: "bold" }}>—</p>
                  </div>
                ))}
          </div>
          <div style={cardStyle}>
            <h2 style={{ fontWeight: "600", marginBottom: "4px" }}>Loyalty Program Dashboard</h2>
            <p style={{ color: "#6b7280", fontSize: "13px", marginBottom: "16px" }}>Real-time metrics and operational data</p>
            {statsQuery.isLoading ? (
              <div style={{ height: "200px", background: "#f3f4f6", borderRadius: "8px" }} />
            ) : statsQuery.data ? (
              <div>
                {Object.entries(statsQuery.data).map(([key, value]) => (
                  <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid #f3f4f6" }}>
                    <span style={{ fontSize: "14px", fontWeight: "500", textTransform: "capitalize" }}>{key.replace(/([A-Z])/g, " $1").trim()}</span>
                    <span style={{ padding: "2px 10px", border: "1px solid #e5e7eb", borderRadius: "9999px", fontSize: "12px" }}>
                      {typeof value === "object" ? JSON.stringify(value).slice(0, 50) : typeof value === "number" ? value.toLocaleString() : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "#9ca3af" }}>No data available — connect to live services to see metrics.</p>
            )}
          </div>
        </>
      )}

      {activeTab === "details" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>Detailed View</h3>
          <p style={{ color: "#9ca3af" }}>Select items from the overview to view details.</p>
        </div>
      )}

      {activeTab === "settings" && (
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>Configuration</h3>
          <p style={{ color: "#9ca3af", marginBottom: "16px" }}>Configure Loyalty Program settings and preferences.</p>
          <button onClick={() => alert("Configuration updated")} style={{ padding: "8px 16px", border: "1px solid #d1d5db", borderRadius: "6px", background: "transparent", cursor: "pointer" }}>Save Settings</button>
        </div>
      )}
    </div>
  );
}
