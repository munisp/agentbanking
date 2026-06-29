import { Shield, CheckCircle, RefreshCw, Search, Plus, FileText, AlertTriangle, Phone } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const PROVIDERS = [
  { id: "leadway", name: "Leadway Assurance", logo: "LA", types: ["life", "health", "auto", "property"] },
  { id: "aiico", name: "AIICO Insurance", logo: "AI", types: ["life", "health", "micro"] },
  { id: "mutual-benefit", name: "Mutual Benefit", logo: "MB", types: ["life", "health", "fire"] },
  { id: "custodian", name: "Custodian Insurance", logo: "CI", types: ["auto", "marine", "property"] },
  { id: "cornerstone", name: "Cornerstone Insurance", logo: "CS", types: ["health", "micro", "life"] },
];

const PLANS = {
  micro: [{ id: "m1", name: "Basic Micro", premium: 500, cover: 50000, duration: "Monthly" }, { id: "m2", name: "Standard Micro", premium: 1000, cover: 150000, duration: "Monthly" }, { id: "m3", name: "Premium Micro", premium: 2500, cover: 500000, duration: "Monthly" }],
  health: [{ id: "h1", name: "Basic Health", premium: 2000, cover: 500000, duration: "Monthly" }, { id: "h2", name: "Family Health", premium: 5000, cover: 2000000, duration: "Monthly" }],
  life: [{ id: "l1", name: "Term Life", premium: 3000, cover: 5000000, duration: "Annually" }, { id: "l2", name: "Whole Life", premium: 8000, cover: 20000000, duration: "Annually" }],
  auto: [{ id: "a1", name: "Third Party", premium: 15000, cover: 1000000, duration: "Annually" }, { id: "a2", name: "Comprehensive", premium: 45000, cover: 5000000, duration: "Annually" }],
};

const InsurancePayment = () => {
  const [step, setStep] = useState(1);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedType, setSelectedType] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [customerPhone, setCustomerPhone] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [mode, setMode] = useState("new"); // new | renew
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [recentPayments, setRecentPayments] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => { fetchRecentPayments(); }, []);

  const fetchRecentPayments = async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/payment-processing/api/v1/transactions?type=insurance&limit=8`, { headers: authHeaders() });
      if (res.ok) {
        const d = await res.json();
        setRecentPayments(Array.isArray(d.transactions) ? d.transactions : Array.isArray(d) ? d : []);
      }
    } catch { setRecentPayments([]); }
  };

  const handlePayment = async () => {
    if (!selectedPlan || !customerPhone) return;
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/payment-processing/api/v1/transactions`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: selectedPlan.premium,
          channel: "insurance",
          type: "insurance",
          provider_id: selectedProvider.id,
          insurance_type: selectedType,
          plan_id: selectedPlan.id,
          customer_phone: customerPhone,
          policy_number: mode === "renew" ? policyNumber : undefined,
          description: `${selectedProvider.name} – ${selectedPlan.name}`,
          currency: "NGN",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Payment failed");
      setSuccess(data);
      fetchRecentPayments();
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setStep(1); setSelectedProvider(null); setSelectedType(""); setSelectedPlan(null); setCustomerPhone(""); setPolicyNumber(""); setSuccess(null); };

  const filteredProviders = PROVIDERS.filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()));

  if (success) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="bg-gray-100 border border-gray-200 rounded-2xl p-10 text-center max-w-md w-full">
          <CheckCircle className="w-16 h-16 text-emerald-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-emerald-300">Payment Successful</h2>
          <p className="text-gray-400 mt-2">{success.description}</p>
          <div className="mt-4 bg-gray-50 rounded-lg p-4 text-left space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">Amount</span><span className="font-semibold">₦{parseFloat(success.amount || selectedPlan?.premium || 0).toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Reference</span><span className="text-blue-400">{success.reference || success.id}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Policy</span><span>{success.policy_number || "Pending issuance"}</span></div>
          </div>
          <button onClick={reset} className="mt-6 w-full py-3 bg-emerald-600 hover:bg-emerald-700 rounded-xl font-semibold transition-colors">New Insurance Payment</button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-600/20 rounded-lg"><Shield className="w-7 h-7 text-emerald-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Insurance Payment</h1>
            <p className="text-gray-400 text-sm">New policies & renewal premium collection</p>
          </div>
        </div>

        {/* Mode Toggle */}
        <div className="flex gap-2">
          {["new", "renew"].map(m => (
            <button key={m} onClick={() => setMode(m)} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode === m ? "bg-blue-600 text-white" : "bg-gray-50 text-gray-400 hover:bg-gray-700"}`}>
              {m === "new" ? "New Policy" : "Renew Policy"}
            </button>
          ))}
        </div>

        {/* Stepper */}
        <div className="flex items-center gap-2 text-sm">
          {[{ n: 1, label: "Provider" }, { n: 2, label: "Plan" }, { n: 3, label: "Customer" }].map(({ n, label }, i, arr) => (
            <React.Fragment key={n}>
              <div className={`flex items-center gap-2 ${step >= n ? "text-blue-400" : "text-gray-600"}`}>
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${step >= n ? "border-blue-500 bg-blue-600/30" : "border-gray-300"}`}>{n}</span>
                <span>{label}</span>
              </div>
              {i < arr.length - 1 && <div className={`flex-1 h-px ${step > n ? "bg-blue-600" : "bg-gray-700"}`} />}
            </React.Fragment>
          ))}
        </div>

        {/* Step 1: Provider */}
        {step === 1 && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search providers..." className="w-full pl-9 pr-4 py-2 bg-white border border-gray-300 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="grid grid-cols-1 gap-2">
              {filteredProviders.map(p => (
                <button key={p.id} onClick={() => { setSelectedProvider(p); setSelectedType(""); setStep(2); }}
                  className="flex items-center gap-4 p-4 bg-gray-50 border border-gray-200 hover:border-blue-500 rounded-xl transition-colors text-left">
                  <div className="w-10 h-10 bg-blue-600/20 rounded-lg flex items-center justify-center text-blue-400 font-bold text-sm">{p.logo}</div>
                  <div className="flex-1">
                    <p className="font-medium">{p.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{p.types.join(", ")}</p>
                  </div>
                  <AlertTriangle className="w-4 h-4 text-gray-600" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Plan */}
        {step === 2 && selectedProvider && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-3 mb-4">
              <button onClick={() => setStep(1)} className="text-xs text-gray-400 hover:text-white underline">← Back</button>
              <span className="text-sm font-medium text-blue-300">{selectedProvider.name}</span>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {selectedProvider.types.map(t => (
                <button key={t} onClick={() => setSelectedType(t)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${selectedType === t ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-600 hover:bg-gray-600"}`}>
                  {t}
                </button>
              ))}
            </div>
            {selectedType && PLANS[selectedType] && (
              <div className="grid grid-cols-1 gap-3">
                {PLANS[selectedType].map(plan => (
                  <button key={plan.id} onClick={() => { setSelectedPlan(plan); setStep(3); }}
                    className={`p-4 border rounded-xl text-left transition-colors hover:border-blue-500 ${selectedPlan?.id === plan.id ? "border-blue-500 bg-blue-900/20" : "border-gray-200 bg-gray-50"}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{plan.name}</p>
                        <p className="text-xs text-gray-400 mt-0.5">Cover: ₦{plan.cover.toLocaleString()} · {plan.duration}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-blue-400">₦{plan.premium.toLocaleString()}</p>
                        <p className="text-xs text-gray-500">premium</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Customer & Confirm */}
        {step === 3 && selectedPlan && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <button onClick={() => setStep(2)} className="text-xs text-gray-400 hover:text-white underline">← Back</button>
            </div>
            {mode === "renew" && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Existing Policy Number</label>
                <input value={policyNumber} onChange={e => setPolicyNumber(e.target.value)} placeholder="POL-XXXXXXXXX"
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            )}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Customer Phone Number</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input value={customerPhone} onChange={e => setCustomerPhone(e.target.value)} placeholder="+234 800 000 0000" type="tel"
                  className="w-full pl-9 bg-white border border-gray-300 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-400">Provider</span><span>{selectedProvider.name}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Plan</span><span>{selectedPlan.name}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Cover</span><span>₦{selectedPlan.cover.toLocaleString()}</span></div>
              <div className="flex justify-between text-base"><span className="font-medium">Premium</span><span className="font-bold text-blue-400">₦{selectedPlan.premium.toLocaleString()}</span></div>
            </div>
            <button onClick={handlePayment} disabled={loading || !customerPhone}
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors">
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
              {loading ? "Processing..." : `Pay ₦${selectedPlan.premium.toLocaleString()}`}
            </button>
          </div>
        )}

        {/* Recent Payments */}
        <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h3 className="font-medium flex items-center gap-2"><FileText className="w-4 h-4 text-gray-400" /> Recent Insurance Payments</h3>
            <button onClick={fetchRecentPayments} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"><RefreshCw className="w-3 h-3" /> Refresh</button>
          </div>
          {recentPayments.length === 0 ? (
            <div className="p-8 text-center text-gray-500 text-sm">No insurance payments yet</div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {recentPayments.map((tx, i) => (
                <li key={tx.id || i} className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Shield className="w-4 h-4 text-emerald-400" />
                    <div>
                      <p className="text-sm font-medium">{tx.description || "Insurance Premium"}</p>
                      <p className="text-xs text-gray-500">{tx.reference || tx.id}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-emerald-400">₦{parseFloat(tx.amount || 0).toLocaleString()}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${tx.status === "success" ? "bg-emerald-900/50 text-emerald-400" : "bg-amber-900/50 text-amber-400"}`}>{tx.status || "completed"}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default InsurancePayment;
