import { Zap, CheckCircle, Clock, XCircle, RefreshCw, TrendingUp, AlertTriangle, DollarSign } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const NANO_TIERS = [
  { id: "n1", label: "₦5,000", amount: 5000, fee: 250, duration: "7 days", apr: "26%" },
  { id: "n2", label: "₦10,000", amount: 10000, fee: 400, duration: "14 days", apr: "20.8%" },
  { id: "n3", label: "₦20,000", amount: 20000, fee: 700, duration: "21 days", apr: "18.3%" },
  { id: "n4", label: "₦50,000", amount: 50000, fee: 1500, duration: "30 days", apr: "15.6%" },
];

const STATUS_CONFIG = {
  pending: { color: "text-amber-400", bg: "bg-amber-900/30", icon: Clock },
  approved: { color: "text-blue-400", bg: "bg-blue-900/30", icon: CheckCircle },
  disbursed: { color: "text-emerald-400", bg: "bg-emerald-900/30", icon: CheckCircle },
  repaying: { color: "text-purple-400", bg: "bg-purple-900/30", icon: TrendingUp },
  completed: { color: "text-gray-400", bg: "bg-gray-800", icon: CheckCircle },
  rejected: { color: "text-red-400", bg: "bg-red-900/30", icon: XCircle },
  defaulted: { color: "text-red-600", bg: "bg-red-900/40", icon: AlertTriangle },
};

const NanoLoan = () => {
  const { user } = useAuth();
  const [activeLoans, setActiveLoans] = useState([]);
  const [selectedTier, setSelectedTier] = useState(null);
  const [purpose, setPurpose] = useState("");
  const [creditScore, setCreditScore] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);
  const [tab, setTab] = useState("apply"); // apply | history

  useEffect(() => {
    fetchLoans();
    fetchCreditScore();
  }, []);

  const fetchLoans = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/loan/api/v1/loans/applications/administration?type=nano`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setActiveLoans(Array.isArray(data) ? data.filter(l => l.loan_type === "nano" || (l.amount && l.amount <= 50000)) : []);
      }
    } catch { setActiveLoans([]); }
    finally { setLoading(false); }
  };

  const fetchCreditScore = async () => {
    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;
      const res = await fetch(`${CORE_BANKING_URL}/loan/api/v1/credit-score/${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setCreditScore(data.score ?? data.credit_score ?? null);
      }
    } catch { setCreditScore(null); }
  };

  const handleApply = async (e) => {
    e.preventDefault();
    if (!selectedTier) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/loan/api/v1/loans/applications`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: selectedTier.amount,
          loan_type: "nano",
          loan_purpose: purpose || "Float top-up",
          requested_term: 1,
          tier_id: selectedTier.id,
          fee: selectedTier.fee,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Application failed");
      setSuccess(data);
      fetchLoans();
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const creditColor = creditScore >= 750 ? "text-emerald-400" : creditScore >= 650 ? "text-blue-400" : creditScore >= 550 ? "text-amber-400" : "text-red-400";
  const creditLabel = creditScore >= 750 ? "Excellent" : creditScore >= 650 ? "Good" : creditScore >= 550 ? "Fair" : creditScore ? "Poor" : "N/A";

  if (success) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="bg-gray-100 border border-gray-200 rounded-2xl p-10 text-center max-w-md w-full">
          <Zap className="w-14 h-14 text-yellow-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold">Nano Loan Applied!</h2>
          <p className="text-gray-400 mt-2">Your application is being processed</p>
          <div className="mt-4 bg-gray-50 rounded-lg p-4 text-sm space-y-2 text-left">
            <div className="flex justify-between"><span className="text-gray-400">Amount</span><span className="font-bold">₦{selectedTier?.amount.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Fee</span><span>₦{selectedTier?.fee.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Duration</span><span>{selectedTier?.duration}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Ref</span><span className="text-blue-400 text-xs">{success.id || success.reference}</span></div>
          </div>
          <button onClick={() => { setSuccess(null); setSelectedTier(null); setPurpose(""); setTab("history"); }}
            className="mt-6 w-full py-3 bg-yellow-500 hover:bg-yellow-600 text-black rounded-xl font-bold transition-colors">
            View My Loans
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-500/20 rounded-lg"><Zap className="w-7 h-7 text-yellow-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Nano Loan</h1>
            <p className="text-gray-400 text-sm">Quick micro-credit for immediate float needs</p>
          </div>
          {creditScore && (
            <div className="ml-auto text-right">
              <p className="text-xs text-gray-500">Credit Score</p>
              <p className={`text-xl font-bold ${creditColor}`}>{creditScore}</p>
              <p className={`text-xs ${creditColor}`}>{creditLabel}</p>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-200">
          {["apply", "history"].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${tab === t ? "border-blue-500 text-blue-400" : "border-transparent text-gray-500 hover:text-gray-600"}`}>
              {t === "apply" ? "Apply Now" : "My Loans"}
            </button>
          ))}
        </div>

        {/* Apply Tab */}
        {tab === "apply" && (
          <form onSubmit={handleApply} className="space-y-4">
            <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-lg p-3 flex items-start gap-2 text-xs text-yellow-300">
              <Zap className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Nano loans are disbursed to your float account within minutes of approval. Repayment is automatically deducted from transactions.</span>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-3">Select Amount</label>
              <div className="grid grid-cols-2 gap-3">
                {NANO_TIERS.map(tier => (
                  <button type="button" key={tier.id} onClick={() => setSelectedTier(tier)}
                    className={`p-4 rounded-xl border text-left transition-colors ${selectedTier?.id === tier.id ? "border-yellow-500 bg-yellow-900/20" : "border-gray-200 bg-gray-100 hover:border-gray-500"}`}>
                    <p className="font-bold text-lg">{tier.label}</p>
                    <p className="text-xs text-gray-400 mt-1">Fee: ₦{tier.fee.toLocaleString()}</p>
                    <p className="text-xs text-gray-500">{tier.duration} · APR {tier.apr}</p>
                  </button>
                ))}
              </div>
            </div>

            {selectedTier && (
              <div className="bg-gray-100 border border-gray-200 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-400">You receive</span><span className="font-bold text-emerald-400">₦{selectedTier.amount.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Service fee</span><span>₦{selectedTier.fee.toLocaleString()}</span></div>
                <div className="flex justify-between font-medium"><span>Total repayment</span><span>₦{(selectedTier.amount + selectedTier.fee).toLocaleString()}</span></div>
                <div className="flex justify-between text-xs text-gray-500"><span>Duration</span><span>{selectedTier.duration}</span></div>
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-400 mb-1">Purpose (optional)</label>
              <input value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="Float top-up, emergency, etc."
                className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-yellow-500" />
            </div>

            <button type="submit" disabled={submitting || !selectedTier}
              className="w-full py-3 bg-yellow-500 hover:bg-yellow-600 text-black disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold flex items-center justify-center gap-2 transition-colors">
              {submitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              {submitting ? "Submitting..." : "Apply for Nano Loan"}
            </button>
          </form>
        )}

        {/* History Tab */}
        {tab === "history" && (
          <div className="space-y-3">
            {loading ? (
              <div className="text-center py-10 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading loans...</div>
            ) : activeLoans.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <DollarSign className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>No nano loans yet</p>
              </div>
            ) : (
              activeLoans.map((loan, i) => {
                const cfg = STATUS_CONFIG[loan.status] || STATUS_CONFIG.pending;
                const Icon = cfg.icon;
                return (
                  <div key={loan.id || i} className={`border border-gray-200 rounded-xl p-4 ${cfg.bg}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Icon className={`w-5 h-5 ${cfg.color}`} />
                        <div>
                          <p className="font-medium">₦{parseFloat(loan.amount || 0).toLocaleString()}</p>
                          <p className="text-xs text-gray-500">{loan.loan_purpose || "Nano loan"}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className={`text-xs px-2 py-1 rounded-full ${cfg.bg} ${cfg.color} border border-current/20 capitalize`}>{loan.status}</span>
                        <p className="text-xs text-gray-500 mt-1">{new Date(loan.created_at || Date.now()).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <button onClick={fetchLoans} className="w-full py-2 text-sm text-blue-400 hover:text-blue-300 flex items-center justify-center gap-2">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default NanoLoan;
