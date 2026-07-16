import { CreditCard, Plus, Eye, EyeOff, Copy, Lock, Unlock, Trash2, RefreshCw, CheckCircle, AlertTriangle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const CARD_COLORS = ["from-blue-600 to-blue-900", "from-purple-600 to-purple-900", "from-emerald-600 to-emerald-900", "from-orange-600 to-orange-900", "from-pink-600 to-pink-900"];

const VirtualCards = () => {
  const { user } = useAuth();
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [revealedCard, setRevealedCard] = useState(null);
  const [copiedField, setCopiedField] = useState("");
  const [form, setForm] = useState({ label: "", currency: "NGN", spending_limit: "", purpose: "general" });

  useEffect(() => { fetchCards(); }, []);

  const fetchCards = async () => {
    setLoading(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/card/api/v1/virtual-cards?agent_id=${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setCards(Array.isArray(data.cards) ? data.cards : Array.isArray(data) ? data : []);
      }
    } catch { setCards([]); }
    finally { setLoading(false); }
  };

  const createCard = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/card/api/v1/virtual-cards`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, agent_id: keycloakId, spending_limit: parseFloat(form.spending_limit) || undefined }),
      });
      if (!res.ok) throw new Error("Failed to create card");
      setShowForm(false);
      setForm({ label: "", currency: "NGN", spending_limit: "", purpose: "general" });
      fetchCards();
    } catch (err) { alert(err.message); }
    finally { setCreating(false); }
  };

  const toggleFreeze = async (card) => {
    try {
      const newStatus = card.status === "frozen" ? "active" : "frozen";
      await fetch(`${CORE_BANKING_URL}/card/api/v1/virtual-cards/${card.id}/status`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchCards();
    } catch (err) { alert(err.message); }
  };

  const terminateCard = async (id) => {
    if (!confirm("Permanently terminate this card? This cannot be undone.")) return;
    try {
      await fetch(`${CORE_BANKING_URL}/card/api/v1/virtual-cards/${id}`, { method: "DELETE", headers: authHeaders() });
      fetchCards();
    } catch (err) { alert(err.message); }
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(""), 2000);
  };

  const formatCardNumber = (num, revealed) => {
    if (!num) return "•••• •••• •••• ••••";
    if (!revealed) return `•••• •••• •••• ${num.slice(-4)}`;
    return num.replace(/(.{4})/g, "$1 ").trim();
  };

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-600/20 rounded-lg"><CreditCard className="w-6 h-6 text-purple-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Virtual Cards</h1>
              <p className="text-gray-400 text-sm">Issue & manage virtual debit cards</p>
            </div>
          </div>
          <button onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors">
            <Plus className="w-4 h-4" /> New Card
          </button>
        </div>

        {/* Create Card Form */}
        {showForm && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
            <h2 className="font-semibold mb-4">Create Virtual Card</h2>
            <form onSubmit={createCard} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Card Label</label>
                <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} placeholder="e.g. Online Shopping, Travel"
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Currency</label>
                  <select value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500">
                    <option value="NGN">NGN - Naira</option>
                    <option value="USD">USD - Dollar</option>
                    <option value="GBP">GBP - Pound</option>
                    <option value="EUR">EUR - Euro</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Spending Limit</label>
                  <input type="number" value={form.spending_limit} onChange={e => setForm(f => ({ ...f, spending_limit: e.target.value }))} placeholder="No limit"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Purpose</label>
                <select value={form.purpose} onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-500">
                  {["general", "online_shopping", "travel", "subscriptions", "business", "payroll"].map(p => (
                    <option key={p} value={p}>{p.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={creating}
                  className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors">
                  {creating ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                  {creating ? "Creating..." : "Create Card"}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Cards Grid */}
        {loading ? (
          <div className="text-center py-12 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading cards...</div>
        ) : cards.length === 0 ? (
          <div className="text-center py-16 text-gray-500 bg-gray-100 border border-gray-200 rounded-xl">
            <CreditCard className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No virtual cards yet</p>
            <p className="text-sm mt-1">Create your first virtual card above</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cards.map((card, i) => {
              const isRevealed = revealedCard === card.id;
              const colorClass = CARD_COLORS[i % CARD_COLORS.length];
              return (
                <div key={card.id || i} className={`relative bg-gradient-to-br ${colorClass} rounded-2xl p-5 shadow-xl overflow-hidden`}>
                  {card.status === "frozen" && (
                    <div className="absolute inset-0 bg-gray-50 flex items-center justify-center rounded-2xl z-10">
                      <div className="text-center">
                        <Lock className="w-8 h-8 mx-auto mb-2 text-blue-300" />
                        <p className="text-sm font-medium text-blue-300">Card Frozen</p>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-medium opacity-80">{card.label || card.purpose || "Virtual Card"}</span>
                    <CreditCard className="w-6 h-6 opacity-70" />
                  </div>
                  <div className="mb-4">
                    <p className="text-lg font-mono tracking-wider">{formatCardNumber(card.card_number, isRevealed)}</p>
                  </div>
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-xs opacity-70">CARDHOLDER</p>
                      <p className="text-sm font-medium">{card.cardholder_name || user?.name || "Agent"}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs opacity-70">EXPIRES</p>
                      <p className="text-sm font-medium">{card.expiry || "12/27"}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs opacity-70">CVV</p>
                      <p className="text-sm font-mono">{isRevealed ? (card.cvv || "•••") : "•••"}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button onClick={() => setRevealedCard(isRevealed ? null : card.id)}
                      className="flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 rounded text-xs transition-colors">
                      {isRevealed ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      {isRevealed ? "Hide" : "Reveal"}
                    </button>
                    {isRevealed && card.card_number && (
                      <button onClick={() => copyToClipboard(card.card_number, card.id + "-num")}
                        className="flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 rounded text-xs transition-colors">
                        {copiedField === card.id + "-num" ? <CheckCircle className="w-3 h-3 text-emerald-300" /> : <Copy className="w-3 h-3" />}
                        Copy
                      </button>
                    )}
                    <button onClick={() => toggleFreeze(card)}
                      className="flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 rounded text-xs transition-colors ml-auto">
                      {card.status === "frozen" ? <Unlock className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                      {card.status === "frozen" ? "Unfreeze" : "Freeze"}
                    </button>
                    <button onClick={() => terminateCard(card.id)}
                      className="flex items-center gap-1 px-2 py-1 bg-red-500/20 hover:bg-red-500/40 rounded text-xs text-red-300 transition-colors">
                      <Trash2 className="w-3 h-3" /> Terminate
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default VirtualCards;
