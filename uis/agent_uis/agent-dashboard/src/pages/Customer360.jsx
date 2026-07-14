import { User, Phone, Mail, MapPin, RefreshCw, Search, TrendingUp, Clock, CreditCard, Shield, Star, MessageSquare } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const Customer360 = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [customer, setCustomer] = useState(null);
  const [txHistory, setTxHistory] = useState([]);
  const [error, setError] = useState("");

  const searchCustomer = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setError("");
    setCustomer(null);
    setTxHistory([]);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/user/api/v1/customers/search?q=${encodeURIComponent(searchQuery)}`, { headers: authHeaders() });
      if (!res.ok) { setError("Customer not found"); return; }
      const data = await res.json();
      const cust = data.customer || data.customers?.[0] || data;
      setCustomer(cust);
      if (cust?.id || cust?.keycloak_id) fetchCustomerTx(cust.id || cust.keycloak_id);
    } catch { setError("Search failed. Try again."); }
    finally { setSearching(false); }
  };

  const fetchCustomerTx = async (customerId) => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/ledger/api/v1/transactions?customer_id=${customerId}&limit=10`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setTxHistory(Array.isArray(data.transactions) ? data.transactions : Array.isArray(data) ? data : []);
      }
    } catch { setTxHistory([]); }
  };

  const riskColor = (risk) => ({ low: "text-emerald-400", medium: "text-amber-400", high: "text-red-400" })[risk] || "text-gray-400";
  const kycColor = (status) => ({ verified: "text-emerald-400", pending: "text-amber-400", rejected: "text-red-400" })[status] || "text-gray-400";

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg"><User className="w-6 h-6 text-blue-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Customer 360°</h1>
            <p className="text-gray-400 text-sm">Complete customer profile and transaction history</p>
          </div>
        </div>

        {/* Search */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && searchCustomer()}
              placeholder="Search by phone, name, account number, or BVN"
              className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button onClick={searchCustomer} disabled={searching}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-xl text-sm font-medium flex items-center gap-2 transition-colors">
            {searching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {searching ? "Searching..." : "Search"}
          </button>
        </div>

        {error && <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">{error}</div>}

        {/* Customer Profile */}
        {customer && (
          <div className="space-y-4">
            {/* Identity Card */}
            <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 bg-blue-600/20 rounded-full flex items-center justify-center text-blue-400 text-xl font-bold shrink-0">
                  {(customer.first_name || customer.name || "?").charAt(0).toUpperCase()}
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold">{[customer.first_name, customer.last_name].filter(Boolean).join(" ") || customer.name || "Unknown"}</h2>
                  <p className="text-gray-400 text-sm">ID: {customer.id?.slice(0, 20) || "—"}</p>
                  <div className="flex flex-wrap gap-3 mt-2 text-sm">
                    {customer.phone && <span className="flex items-center gap-1 text-gray-600"><Phone className="w-3.5 h-3.5 text-gray-500" />{customer.phone}</span>}
                    {customer.email && <span className="flex items-center gap-1 text-gray-600"><Mail className="w-3.5 h-3.5 text-gray-500" />{customer.email}</span>}
                    {customer.city && <span className="flex items-center gap-1 text-gray-600"><MapPin className="w-3.5 h-3.5 text-gray-500" />{customer.city}</span>}
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-2 py-1 rounded-full border capitalize ${customer.status === "active" ? "border-emerald-700/30 bg-emerald-900/30 text-emerald-400" : "border-red-700/30 bg-red-900/30 text-red-400"}`}>
                    {customer.status || "active"}
                  </span>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "KYC Status", value: customer.kyc_status || "pending", color: kycColor(customer.kyc_status) },
                { label: "Risk Level", value: customer.risk_level || "low", color: riskColor(customer.risk_level) },
                { label: "Account Balance", value: customer.balance ? `₦${parseFloat(customer.balance).toLocaleString()}` : "N/A", color: "text-blue-400" },
                { label: "Total Transactions", value: txHistory.length, color: "text-purple-400" },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-3">
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className={`text-base font-bold mt-1 capitalize ${color}`}>{value}</p>
                </div>
              ))}
            </div>

            {/* Additional Details */}
            <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
              <h3 className="font-semibold mb-3 text-sm text-gray-600">Account Details</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Account Number", customer.account_number || "—"],
                  ["BVN", customer.bvn ? customer.bvn.replace(/.(?=.{4})/g, "*") : "—"],
                  ["Tier", customer.tier || "basic"],
                  ["Joined", customer.created_at ? new Date(customer.created_at).toLocaleDateString() : "—"],
                  ["Last Active", customer.last_active ? new Date(customer.last_active).toLocaleDateString() : "—"],
                  ["NPS Score", customer.nps_score ?? "—"],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="font-medium capitalize">{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Transactions */}
            <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
              <div className="flex items-center gap-2 p-4 border-b border-gray-200">
                <Clock className="w-4 h-4 text-gray-400" />
                <h3 className="font-medium text-sm">Recent Transactions</h3>
              </div>
              {txHistory.length === 0 ? (
                <div className="p-8 text-center text-gray-500 text-sm">No transactions found</div>
              ) : (
                <ul className="divide-y divide-gray-200">
                  {txHistory.slice(0, 8).map((tx, i) => (
                    <li key={tx.id || i} className="flex items-center justify-between px-4 py-3">
                      <div>
                        <p className="text-sm font-medium capitalize">{(tx.type || tx.transaction_type || "transaction").replace(/_/g, " ")}</p>
                        <p className="text-xs text-gray-500">{new Date(tx.created_at || Date.now()).toLocaleDateString()}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold">₦{parseFloat(tx.amount || 0).toLocaleString()}</p>
                        <span className={`text-xs ${tx.status === "success" ? "text-emerald-400" : tx.status === "failed" ? "text-red-400" : "text-amber-400"}`}>{tx.status || "—"}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!customer && !error && (
          <div className="text-center py-16 text-gray-500">
            <User className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">Search for a customer</p>
            <p className="text-sm mt-1">Enter phone number, name, account number or BVN</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Customer360;
