import { Star, RefreshCw, TrendingUp, TrendingDown, User } from "lucide-react";
import React, { useState } from "react";

interface CreditProfile {
  agent_id: string;
  agent_name: string;
  credit_score: number;
  tier: "AAA" | "AA" | "A" | "BBB" | "BB" | "B" | "CCC" | "D";
  float_limit: number;
  loan_eligible: boolean;
  payment_history_score: number;
  volume_score: number;
  kyc_score: number;
  last_updated: string;
  trend: "improving" | "stable" | "declining";
}

const MOCK_PROFILES: CreditProfile[] = [
  { agent_id: "AGT-0023", agent_name: "Tunde Bakare", credit_score: 820, tier: "AA", float_limit: 500000, loan_eligible: true, payment_history_score: 95, volume_score: 88, kyc_score: 100, last_updated: "2024-11-29", trend: "improving" },
  { agent_id: "AGT-0045", agent_name: "Ngozi Adeleke", credit_score: 755, tier: "A", float_limit: 350000, loan_eligible: true, payment_history_score: 82, volume_score: 79, kyc_score: 100, last_updated: "2024-11-29", trend: "stable" },
  { agent_id: "AGT-0087", agent_name: "Grace Okoro", credit_score: 612, tier: "BBB", float_limit: 150000, loan_eligible: false, payment_history_score: 70, volume_score: 65, kyc_score: 80, last_updated: "2024-11-28", trend: "stable" },
  { agent_id: "AGT-0112", agent_name: "Emeka Nwosu", credit_score: 480, tier: "BB", float_limit: 50000, loan_eligible: false, payment_history_score: 55, volume_score: 48, kyc_score: 75, last_updated: "2024-11-28", trend: "declining" },
  { agent_id: "AGT-0055", agent_name: "Fatima Aliyu", credit_score: 890, tier: "AAA", float_limit: 1000000, loan_eligible: true, payment_history_score: 98, volume_score: 95, kyc_score: 100, last_updated: "2024-11-29", trend: "stable" },
];

const TIER_COLORS: Record<string, string> = {
  AAA: "bg-emerald-100 text-emerald-800", AA: "bg-emerald-100 text-emerald-700",
  A: "bg-blue-100 text-blue-700", BBB: "bg-blue-100 text-blue-600",
  BB: "bg-amber-100 text-amber-700", B: "bg-orange-100 text-orange-700",
  CCC: "bg-red-100 text-red-700", D: "bg-red-100 text-red-800",
};

const scoreColor = (score: number) => score >= 750 ? "text-emerald-600" : score >= 650 ? "text-blue-600" : score >= 500 ? "text-amber-600" : "text-red-600";

const CreditRatingSystem: React.FC = () => {
  const [profiles, setProfiles] = useState<CreditProfile[]>(MOCK_PROFILES);
  const [loading] = useState(false);
  const [search, setSearch] = useState("");

  const recalculate = (agentId: string) => {
    setProfiles(prev => prev.map(p => p.agent_id === agentId ? { ...p, last_updated: new Date().toISOString().split("T")[0] } : p));
  };

  const filtered = profiles.filter(p => !search || p.agent_name.toLowerCase().includes(search.toLowerCase()) || p.agent_id.includes(search));
  const avgScore = profiles.length ? Math.round(profiles.reduce((s, p) => s + p.credit_score, 0) / profiles.length) : 0;
  const loanEligible = profiles.filter(p => p.loan_eligible).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Star className="w-7 h-7 text-yellow-600" /> Credit Rating System
          </h1>
          <p className="text-gray-500 text-sm mt-1">Agent credit scores, float limits and loan eligibility based on performance</p>
        </div>
        <button onClick={() => setProfiles(MOCK_PROFILES)} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Average Score", value: avgScore, color: scoreColor(avgScore) },
          { label: "Loan Eligible", value: `${loanEligible}/${profiles.length}`, color: "text-emerald-600" },
          { label: "Declining", value: profiles.filter(p => p.trend === "declining").length, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="relative">
        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search agents..."
          className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Agent", "Score", "Rating", "Float Limit", "Payment History", "Volume", "KYC", "Trend", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : filtered.map(p => (
              <tr key={p.agent_id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4">
                  <p className="font-medium">{p.agent_name}</p>
                  <p className="text-xs text-gray-400">{p.agent_id}</p>
                </td>
                <td className="py-3 px-4">
                  <span className={`text-lg font-bold ${scoreColor(p.credit_score)}`}>{p.credit_score}</span>
                </td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded font-bold ${TIER_COLORS[p.tier]}`}>{p.tier}</span></td>
                <td className="py-3 px-4 font-medium">₦{(p.float_limit / 1000).toFixed(0)}k</td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-gray-100 rounded-full h-1.5"><div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${p.payment_history_score}%` }} /></div>
                    <span className="text-xs text-gray-500">{p.payment_history_score}</span>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-gray-100 rounded-full h-1.5"><div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${p.volume_score}%` }} /></div>
                    <span className="text-xs text-gray-500">{p.volume_score}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-center">
                  <span className={`text-xs font-medium ${p.kyc_score === 100 ? "text-emerald-600" : "text-amber-600"}`}>{p.kyc_score}</span>
                </td>
                <td className="py-3 px-4">
                  {p.trend === "improving" && <span className="flex items-center gap-1 text-xs text-emerald-600"><TrendingUp className="w-3 h-3" />Up</span>}
                  {p.trend === "stable" && <span className="flex items-center gap-1 text-xs text-gray-500">— Stable</span>}
                  {p.trend === "declining" && <span className="flex items-center gap-1 text-xs text-red-600"><TrendingDown className="w-3 h-3" />Down</span>}
                </td>
                <td className="py-3 px-4">
                  <button onClick={() => recalculate(p.agent_id)} className="text-xs px-2 py-1 bg-yellow-50 text-yellow-700 hover:bg-yellow-100 rounded flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> Recalc
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CreditRatingSystem;
