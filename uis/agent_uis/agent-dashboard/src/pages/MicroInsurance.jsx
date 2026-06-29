import { Shield, Plus, RefreshCw, CheckCircle, Clock, XCircle, Info, Zap } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const PRODUCTS = [
  { id: "float-protect", name: "Float Protect", description: "Covers float loss from theft, robbery, or fire", premium: 500, cover: 200000, period: "monthly", icon: "🔐" },
  { id: "device-cover", name: "Device Cover", description: "Insurance for your POS terminal and mobile device", premium: 800, cover: 150000, period: "monthly", icon: "📱" },
  { id: "health-basic", name: "Agent Health Basic", description: "Basic health cover for you and spouse", premium: 1500, cover: 500000, period: "monthly", icon: "🏥" },
  { id: "income-protect", name: "Income Protection", description: "Pays daily allowance if you cannot operate", premium: 300, cover: 5000, period: "monthly", icon: "💼" },
  { id: "funeral-cover", name: "Funeral Cover", description: "Dignified funeral cover for family members", premium: 200, cover: 100000, period: "monthly", icon: "🕊️" },
];

const MicroInsurance = () => {
  const { user } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [enrolling, setEnrolling] = useState(null);
  const [tab, setTab] = useState("products"); // products | policies

  useEffect(() => {
    if (!user?.keycloakId) return;
    fetchPolicies();
  }, [user]);

  const fetchPolicies = async () => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insurance/api/v1/micro/policies?agent_id=${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setPolicies(Array.isArray(data.policies) ? data.policies : Array.isArray(data) ? data : []);
      }
    } catch { setPolicies([]); }
    finally { setLoading(false); }
  };

  const enroll = async (productId) => {
    setEnrolling(productId);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/insurance/api/v1/micro/policies`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: keycloakId, product_id: productId }),
      });
      if (!res.ok) throw new Error("Enrollment failed");
      fetchPolicies();
      setTab("policies");
    } catch (err) { alert(err.message); }
    finally { setEnrolling(null); }
  };

  const cancelPolicy = async (policyId) => {
    if (!confirm("Cancel this insurance policy?")) return;
    try {
      await fetch(`${CORE_BANKING_URL}/insurance/api/v1/micro/policies/${policyId}/cancel`, { method: "POST", headers: authHeaders() });
      fetchPolicies();
    } catch (err) { alert(err.message); }
  };

  const enrolledIds = new Set(policies.map(p => p.product_id));
  const totalMonthlyPremium = policies.filter(p => p.status === "active").reduce((s, p) => {
    const product = PRODUCTS.find(pr => pr.id === p.product_id);
    return s + (product?.premium || 0);
  }, 0);

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-600/20 rounded-lg"><Shield className="w-6 h-6 text-emerald-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Micro-Insurance</h1>
            <p className="text-gray-400 text-sm">Affordable protection products tailored for agents</p>
          </div>
          {totalMonthlyPremium > 0 && (
            <div className="ml-auto text-right">
              <p className="text-xs text-gray-500">Monthly Total</p>
              <p className="text-lg font-bold text-emerald-400">₦{totalMonthlyPremium.toLocaleString()}</p>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-200">
          {[{ id: "products", label: "Available Products" }, { id: "policies", label: `My Policies (${policies.length})` }].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.id ? "border-emerald-500 text-emerald-400" : "border-transparent text-gray-500 hover:text-gray-600"}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Products Tab */}
        {tab === "products" && (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-xs text-blue-300 bg-blue-900/20 border border-blue-700/30 rounded-lg p-3">
              <Info className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Premiums are auto-deducted from your commission account on the 1st of each month. You can cancel anytime.</span>
            </div>
            {PRODUCTS.map(product => {
              const enrolled = enrolledIds.has(product.id);
              return (
                <div key={product.id} className={`border rounded-xl p-4 transition-colors ${enrolled ? "border-emerald-700/50 bg-emerald-900/10" : "border-gray-200 bg-gray-100"}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{product.icon}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold">{product.name}</p>
                          {enrolled && <span className="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-400 rounded-full border border-emerald-700/30">Active</span>}
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">{product.description}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-gray-500">Cover</p>
                      <p className="font-bold text-sm">₦{product.cover.toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                    <div className="flex items-center gap-4 text-sm">
                      <span><span className="font-bold text-blue-400">₦{product.premium.toLocaleString()}</span> <span className="text-gray-500 text-xs">/{product.period}</span></span>
                    </div>
                    {enrolled ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3.5 h-3.5" /> Enrolled</span>
                    ) : (
                      <button onClick={() => enroll(product.id)} disabled={enrolling === product.id}
                        className="flex items-center gap-1 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors">
                        {enrolling === product.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                        {enrolling === product.id ? "Enrolling..." : "Enroll"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Policies Tab */}
        {tab === "policies" && (
          loading ? (
            <div className="text-center py-12 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading...</div>
          ) : policies.length === 0 ? (
            <div className="text-center py-16 bg-gray-100 border border-gray-200 rounded-xl text-gray-500">
              <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="font-medium">No active policies</p>
              <p className="text-sm mt-1">Browse products to get started</p>
              <button onClick={() => setTab("products")} className="mt-4 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm text-white transition-colors">Browse Products</button>
            </div>
          ) : (
            <div className="space-y-3">
              {policies.map((policy, i) => {
                const product = PRODUCTS.find(p => p.id === policy.product_id);
                const isActive = policy.status === "active";
                return (
                  <div key={policy.id || i} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-xl">{product?.icon || "🔐"}</span>
                        <div>
                          <p className="font-medium">{product?.name || policy.product_id}</p>
                          <p className="text-xs text-gray-500">Policy: {policy.policy_number || policy.id?.slice(0, 16)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="text-xs text-gray-500">Next payment</p>
                          <p className="text-sm font-medium">{policy.next_payment_date ? new Date(policy.next_payment_date).toLocaleDateString() : "1st of month"}</p>
                        </div>
                        <span className={`text-xs px-2 py-1 rounded-full border capitalize ${isActive ? "border-emerald-700/30 bg-emerald-900/30 text-emerald-400" : "border-gray-300 bg-gray-50 text-gray-400"}`}>{policy.status || "active"}</span>
                        {isActive && (
                          <button onClick={() => cancelPolicy(policy.id)} className="text-xs text-red-400 hover:text-red-300 transition-colors px-2 py-1 border border-red-700/30 rounded-lg">Cancel</button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default MicroInsurance;
