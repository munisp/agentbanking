import { Calculator, ArrowRight, RefreshCw, Info } from "lucide-react";
import React, { useState } from "react";

const FEE_RULES = {
  cash_in:     [{ max: 5000, fee: 25 }, { max: 10000, fee: 35 }, { max: 20000, fee: 55 }, { max: 50000, fee: 75 }, { max: 100000, fee: 105 }, { max: 200000, fee: 165 }, { max: 500000, fee: 225 }, { max: Infinity, fee: 300 }],
  cash_out:    [{ max: 5000, fee: 50 }, { max: 10000, fee: 75 }, { max: 20000, fee: 105 }, { max: 50000, fee: 130 }, { max: 100000, fee: 175 }, { max: 200000, fee: 250 }, { max: 500000, fee: 325 }, { max: Infinity, fee: 400 }],
  transfer:    [{ max: 5000, fee: 10 }, { max: 50000, fee: 25 }, { max: Infinity, fee: 50 }],
  bill_payment:[{ max: Infinity, pct: 0.5, min: 50, max_fee: 500 }],
  airtime:     [{ max: Infinity, pct: 0.5, min: 0, max_fee: 50 }],
  data:        [{ max: Infinity, pct: 0.5, min: 0, max_fee: 50 }],
  insurance:   [{ max: Infinity, pct: 1.5, min: 0, max_fee: 2000 }],
  nano_loan:   [{ max: 5000, fee: 250 }, { max: 10000, fee: 400 }, { max: 20000, fee: 700 }, { max: 50000, fee: 1500 }],
};

const COMMISSION_RATES = { cash_in: 0.003, cash_out: 0.006, transfer: 0.002, bill_payment: 0.01, airtime: 0.02, data: 0.02, insurance: 0.05, nano_loan: 0.005 };

function calcFee(type, amount) {
  const rules = FEE_RULES[type];
  if (!rules) return 0;
  for (const r of rules) {
    if (amount <= r.max) {
      if (r.fee !== undefined) return r.fee;
      if (r.pct !== undefined) return Math.min(r.max_fee || Infinity, Math.max(r.min || 0, amount * r.pct / 100));
    }
  }
  return 0;
}

const TX_TYPES = [
  { id: "cash_in", label: "Cash In", color: "text-emerald-400" },
  { id: "cash_out", label: "Cash Out", color: "text-blue-400" },
  { id: "transfer", label: "Transfer", color: "text-purple-400" },
  { id: "bill_payment", label: "Bill Payment", color: "text-yellow-400" },
  { id: "airtime", label: "Airtime", color: "text-pink-400" },
  { id: "data", label: "Data", color: "text-cyan-400" },
  { id: "insurance", label: "Insurance", color: "text-orange-400" },
  { id: "nano_loan", label: "Nano Loan", color: "text-red-400" },
];

const RateCalculator = () => {
  const [txType, setTxType] = useState("cash_out");
  const [amount, setAmount] = useState("");
  const [agentTier, setAgentTier] = useState("silver"); // bronze | silver | gold | platinum
  const [result, setResult] = useState(null);

  const TIER_MULTIPLIERS = { bronze: 1, silver: 1.1, gold: 1.25, platinum: 1.5 };

  const calculate = () => {
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) return;
    const fee = calcFee(txType, amt);
    const commRate = (COMMISSION_RATES[txType] || 0) * TIER_MULTIPLIERS[agentTier];
    const commission = amt * commRate;
    const customerPays = amt + fee;
    const agentEarns = commission;
    setResult({ fee, commission: agentEarns, customerPays, agentEarns, commRate: (commRate * 100).toFixed(2) });
  };

  const selectedType = TX_TYPES.find(t => t.id === txType);

  return (
    <div className="p-6">
      <div className="max-w-lg mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg"><Calculator className="w-6 h-6 text-blue-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Rate Calculator</h1>
            <p className="text-gray-400 text-sm">Estimate fees and commission before a transaction</p>
          </div>
        </div>

        {/* Transaction Type */}
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-2">Transaction Type</label>
          <div className="grid grid-cols-4 gap-2">
            {TX_TYPES.map(t => (
              <button key={t.id} onClick={() => { setTxType(t.id); setResult(null); }}
                className={`py-2 px-1 rounded-lg text-xs font-medium border transition-colors ${txType === t.id ? "border-blue-500 bg-blue-900/30 text-white" : "border-gray-200 bg-gray-100 text-gray-400 hover:border-gray-300"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Agent Tier */}
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-2">Your Tier</label>
          <div className="grid grid-cols-4 gap-2">
            {["bronze", "silver", "gold", "platinum"].map(t => {
              const colors = { bronze: "border-orange-700 bg-orange-900/20 text-orange-300", silver: "border-gray-500 bg-gray-700/30 text-gray-600", gold: "border-yellow-600 bg-yellow-900/20 text-yellow-300", platinum: "border-purple-500 bg-purple-900/20 text-purple-300" };
              return (
                <button key={t} onClick={() => { setAgentTier(t); setResult(null); }}
                  className={`py-2 rounded-lg text-xs font-medium border transition-colors capitalize ${agentTier === t ? colors[t] : "border-gray-200 bg-gray-100 text-gray-500"}`}>
                  {t}
                </button>
              );
            })}
          </div>
        </div>

        {/* Amount Input */}
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-2">Amount (₦)</label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 font-medium">₦</span>
            <input type="number" value={amount} onChange={e => { setAmount(e.target.value); setResult(null); }}
              onKeyDown={e => e.key === "Enter" && calculate()}
              placeholder="0.00"
              className="w-full pl-8 bg-gray-50 border border-gray-300 rounded-xl px-4 py-4 text-2xl font-bold text-gray-900 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>

        <button onClick={calculate} disabled={!amount}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors">
          <Calculator className="w-5 h-5" /> Calculate
        </button>

        {/* Result */}
        {result && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-gray-200">
              <h3 className="font-semibold">Breakdown</h3>
              <span className={`text-sm font-medium ${selectedType?.color}`}>{selectedType?.label}</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-400">Transaction Amount</span><span>₦{parseFloat(amount).toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Service Fee</span><span className="text-red-400">+ ₦{result.fee.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
              <div className="flex justify-between font-medium border-t border-gray-200 pt-2"><span>Customer Pays</span><span className="text-lg">₦{result.customerPays.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
            </div>
            <div className="bg-emerald-900/20 border border-emerald-700/30 rounded-lg p-3 mt-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-emerald-300 mb-0.5">Your Commission ({result.commRate}%)</p>
                  <p className="text-xl font-bold text-emerald-400">₦{result.agentEarns.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                </div>
                <ArrowRight className="w-5 h-5 text-emerald-400" />
              </div>
              <p className="text-xs text-gray-500 mt-1">Credited to your commission account after transaction settlement</p>
            </div>
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <Info className="w-3 h-3 mt-0.5 shrink-0" />
              <p>Rates shown for {agentTier.charAt(0).toUpperCase() + agentTier.slice(1)} tier. Actual fees may vary based on your contract.</p>
            </div>
          </div>
        )}

        {/* Fee Schedule Reference */}
        <details className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <summary className="px-4 py-3 text-sm font-medium text-gray-600 cursor-pointer hover:bg-gray-100">View Full Fee Schedule</summary>
          <div className="px-4 pb-4">
            <table className="w-full text-xs mt-2">
              <thead><tr className="border-b border-gray-200"><th className="text-left py-2 text-gray-400">Amount Range</th><th className="text-right py-2 text-gray-400">Cash Out Fee</th><th className="text-right py-2 text-gray-400">Cash In Fee</th></tr></thead>
              <tbody className="divide-y divide-gray-200">
                {FEE_RULES.cash_out.map((r, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-gray-600">{i === 0 ? `Up to ₦${r.max.toLocaleString()}` : `₦${(FEE_RULES.cash_out[i-1].max + 1).toLocaleString()} – ${r.max === Infinity ? "above" : "₦" + r.max.toLocaleString()}`}</td>
                    <td className="py-1.5 text-right text-red-400">₦{r.fee}</td>
                    <td className="py-1.5 text-right text-blue-400">₦{FEE_RULES.cash_in[i]?.fee || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </div>
  );
};

export default RateCalculator;
