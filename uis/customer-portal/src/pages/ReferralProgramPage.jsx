/**
 * Referral Program — Agent referral tracking, reward tiers, and incentive management
 * Migrated from NGApp — tRPC stubs, no shadcn/ui
 */

const referrals = { data: null, isLoading: false, refetch: () => {} };
const rewards = { data: null, isLoading: false, refetch: () => {} };
const tiers = { data: null, isLoading: false, refetch: () => {} };
const analytics = { data: null, isLoading: false, refetch: () => {} };

const cardStyle = { background: "#fff", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" };

export default function ReferralProgramPage() {
  return (
    <div style={{ padding: "24px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: "bold" }}>Referral Program</h1>
        <p style={{ color: "#6b7280" }}>Agent referral tracking, reward tiers, and incentive management</p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        {[
          { label: "Total Referrals", value: analytics.data?.totalReferrals ?? 0 },
          { label: "Conversion Rate", value: `${analytics.data?.conversionRate ?? 0}%` },
          { label: "Bonus Paid", value: `NGN ${(analytics.data?.totalBonusPaid ?? 0).toLocaleString()}` },
          { label: "Qualified", value: analytics.data?.qualified ?? 0 },
        ].map((kpi, i) => (
          <div key={i} style={cardStyle}>
            <p style={{ fontSize: "13px", color: "#6b7280", marginBottom: "4px" }}>{kpi.label}</p>
            <p style={{ fontSize: "24px", fontWeight: "bold" }}>{kpi.value}</p>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", marginBottom: "24px" }}>
        {/* Reward Tiers */}
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>🏆 Reward Tiers</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {tiers.data?.tiers?.length ? tiers.data.tiers.map((t) => (
              <div key={t.id} style={{ border: "1px solid #e5e7eb", borderRadius: "6px", padding: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <p style={{ fontWeight: "600" }}>{t.name}</p>
                  <p style={{ fontSize: "12px", color: "#6b7280" }}>{t.minReferrals}+ referrals · {t.description}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p style={{ fontSize: "18px", fontWeight: "bold", color: "#2563eb" }}>NGN {t.rewardAmount?.toLocaleString()}</p>
                  <span style={{ padding: "2px 8px", background: "#dbeafe", color: "#1d4ed8", borderRadius: "9999px", fontSize: "11px" }}>{t.type}</span>
                </div>
              </div>
            )) : <p style={{ color: "#9ca3af" }}>No tiers available</p>}
          </div>
        </div>

        {/* Recent Rewards */}
        <div style={cardStyle}>
          <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>🎁 Recent Rewards</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {rewards.data?.leaderboard?.length ? rewards.data.leaderboard.map((r) => (
              <div key={r.id} style={{ border: "1px solid #e5e7eb", borderRadius: "6px", padding: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <p style={{ fontWeight: "600" }}>{r.referrerName}</p>
                  <p style={{ fontSize: "12px", color: "#6b7280" }}>{r.tier} · {r.reason}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p style={{ fontWeight: "bold" }}>NGN {r.amount?.toLocaleString()}</p>
                  <span style={{ padding: "2px 8px", background: r.status === "paid" ? "#d1fae5" : "#f3f4f6", color: r.status === "paid" ? "#065f46" : "#374151", borderRadius: "9999px", fontSize: "11px" }}>{r.status}</span>
                </div>
              </div>
            )) : <p style={{ color: "#9ca3af" }}>No rewards available</p>}
          </div>
        </div>
      </div>

      {/* Recent Referrals */}
      <div style={cardStyle}>
        <h3 style={{ fontWeight: "600", marginBottom: "12px" }}>👥 Recent Referrals</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: "13px", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                {["Referrer","Referred","Code","Status","Converted","Date"].map((h) => (
                  <th key={h} style={{ padding: "8px", textAlign: "left", color: "#6b7280", fontWeight: "500" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {referrals.data?.referrals?.length ? referrals.data.referrals.map((r) => (
                <tr key={r.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "8px" }}>{r.referrerName}</td>
                  <td style={{ padding: "8px" }}>{r.referredName}</td>
                  <td style={{ padding: "8px", fontFamily: "monospace", fontSize: "11px" }}>{r.code}</td>
                  <td style={{ padding: "8px" }}>
                    <span style={{ padding: "2px 8px", borderRadius: "9999px", fontSize: "11px", background: r.status === "converted" ? "#d1fae5" : r.status === "pending" ? "#f3f4f6" : "#fee2e2", color: r.status === "converted" ? "#065f46" : r.status === "pending" ? "#374151" : "#dc2626" }}>
                      {r.status}
                    </span>
                  </td>
                  <td style={{ padding: "8px" }}>{r.converted ? "Yes" : "No"}</td>
                  <td style={{ padding: "8px", fontSize: "12px", color: "#6b7280" }}>{new Date(r.createdAt).toLocaleString()}</td>
                </tr>
              )) : (
                <tr><td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#9ca3af" }}>No referrals yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
