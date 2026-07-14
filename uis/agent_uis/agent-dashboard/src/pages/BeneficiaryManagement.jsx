import { Users, Plus, Trash2, Star, StarOff, Search, RefreshCw, Send, Edit2, CheckCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const BANKS = ["Access Bank", "GTBank", "Zenith Bank", "First Bank", "UBA", "Fidelity Bank", "FCMB", "Sterling Bank", "Union Bank", "Polaris Bank", "Wema Bank", "Kuda Bank", "OPay", "PalmPay", "Moniepoint"];

const BeneficiaryManagement = () => {
  const { user } = useAuth();
  const [beneficiaries, setBeneficiaries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState("all"); // all | starred
  const [resolving, setResolving] = useState(false);
  const [resolvedName, setResolvedName] = useState("");
  const [form, setForm] = useState({ name: "", account_number: "", bank_name: "", bank_code: "", phone: "", nickname: "", is_starred: false });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (user?.keycloakId) fetchBeneficiaries(); }, [user?.keycloakId]);

  const fetchBeneficiaries = async () => {
    setLoading(true);
    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/beneficiaries/${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setBeneficiaries(Array.isArray(data.beneficiaries) ? data.beneficiaries : Array.isArray(data) ? data : []);
      }
    } catch { setBeneficiaries([]); }
    finally { setLoading(false); }
  };

  const resolveAccount = async () => {
    if (form.account_number.length < 10 || !form.bank_code) return;
    setResolving(true);
    setResolvedName("");
    try {
      const res = await fetch(`${CORE_BANKING_URL}/payment-hub/api/v1/parties/lookup?account=${form.account_number}&bank=${form.bank_code}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const name = data.account_name || data.name || "";
        setResolvedName(name);
        if (name) setForm(f => ({ ...f, name }));
      }
    } catch { setResolvedName(""); }
    finally { setResolving(false); }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const keycloakId = user?.keycloakId;
      const url = editId
        ? `${CORE_BANKING_URL}/agent/api/v1/beneficiaries/${keycloakId}/${editId}`
        : `${CORE_BANKING_URL}/agent/api/v1/beneficiaries/${keycloakId}`;
      const res = await fetch(url, {
        method: editId ? "PUT" : "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Failed to save beneficiary");
      setShowForm(false);
      setEditId(null);
      setForm({ name: "", account_number: "", bank_name: "", bank_code: "", phone: "", nickname: "", is_starred: false });
      setResolvedName("");
      fetchBeneficiaries();
    } catch (err) {
      alert(err.message);
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Remove this beneficiary?")) return;
    try {
      const keycloakId = user?.keycloakId;
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/beneficiaries/${keycloakId}/${id}`, { method: "DELETE", headers: authHeaders() });
      fetchBeneficiaries();
    } catch (err) { alert(err.message); }
  };

  const toggleStar = async (b) => {
    try {
      const keycloakId = user?.keycloakId;
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/beneficiaries/${keycloakId}/${b.id}`, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...b, is_starred: !b.is_starred }),
      });
      fetchBeneficiaries();
    } catch { }
  };

  const openEdit = (b) => {
    setForm({ name: b.name || "", account_number: b.account_number || "", bank_name: b.bank_name || "", bank_code: b.bank_code || "", phone: b.phone || "", nickname: b.nickname || "", is_starred: b.is_starred || false });
    setEditId(b.id);
    setShowForm(true);
  };

  const filtered = beneficiaries
    .filter(b => filter === "starred" ? b.is_starred : true)
    .filter(b => !searchQuery || [b.name, b.account_number, b.bank_name, b.nickname].some(f => f?.toLowerCase().includes(searchQuery.toLowerCase())));

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 rounded-lg"><Users className="w-6 h-6 text-blue-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Beneficiaries</h1>
              <p className="text-gray-400 text-sm">Manage saved transfer recipients</p>
            </div>
          </div>
          <button onClick={() => { setShowForm(true); setEditId(null); setForm({ name: "", account_number: "", bank_name: "", bank_code: "", phone: "", nickname: "", is_starred: false }); setResolvedName(""); }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors">
            <Plus className="w-4 h-4" /> Add Beneficiary
          </button>
        </div>

        {/* Search & Filter */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search beneficiaries..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex gap-1 bg-gray-50 border border-gray-200 rounded-lg p-1">
            {["all", "starred"].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded text-xs font-medium capitalize transition-colors ${filter === f ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"}`}>{f}</button>
            ))}
          </div>
        </div>

        {/* Add/Edit Form */}
        {showForm && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-4">
            <h2 className="font-semibold">{editId ? "Edit Beneficiary" : "Add New Beneficiary"}</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Account Number</label>
                  <input value={form.account_number} onChange={e => { setForm(f => ({ ...f, account_number: e.target.value })); setResolvedName(""); }} onBlur={resolveAccount}
                    placeholder="0000000000" maxLength={10}
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Bank</label>
                  <select value={form.bank_name} onChange={e => setForm(f => ({ ...f, bank_name: e.target.value, bank_code: e.target.value.toLowerCase().replace(/\s/g, "-") }))}
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">Select bank</option>
                    {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>
              </div>
              {resolving && <p className="text-xs text-blue-400 flex items-center gap-1"><RefreshCw className="w-3 h-3 animate-spin" /> Resolving account name...</p>}
              {resolvedName && <p className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> {resolvedName}</p>}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Account Name</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Full name"
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Nickname (optional)</label>
                  <input value={form.nickname} onChange={e => setForm(f => ({ ...f, nickname: e.target.value }))} placeholder="e.g. Mum"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Phone (optional)</label>
                  <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="+2348..."
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_starred} onChange={e => setForm(f => ({ ...f, is_starred: e.target.checked }))} className="rounded" />
                <span className="text-sm text-gray-600">Mark as favourite</span>
              </label>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2">
                  {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                  {saving ? "Saving..." : editId ? "Update" : "Save Beneficiary"}
                </button>
                <button type="button" onClick={() => { setShowForm(false); setEditId(null); }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Beneficiary List */}
        <div className="space-y-2">
          {loading ? (
            <div className="text-center py-10 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-gray-500 bg-gray-100 border border-gray-200 rounded-xl">
              <Users className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>{searchQuery ? "No beneficiaries match your search" : "No beneficiaries added yet"}</p>
            </div>
          ) : (
            filtered.map((b, i) => (
              <div key={b.id || i} className="flex items-center gap-4 p-4 bg-gray-100 border border-gray-200 rounded-xl hover:border-gray-300 transition-colors">
                <div className="w-10 h-10 bg-blue-600/20 rounded-full flex items-center justify-center text-blue-400 font-bold text-sm shrink-0">
                  {(b.name || "?").charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{b.nickname || b.name}</p>
                  {b.nickname && <p className="text-xs text-gray-500 truncate">{b.name}</p>}
                  <p className="text-xs text-gray-500">{b.account_number} · {b.bank_name}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => toggleStar(b)} className="text-gray-500 hover:text-yellow-400 transition-colors">
                    {b.is_starred ? <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" /> : <StarOff className="w-4 h-4" />}
                  </button>
                  <button onClick={() => openEdit(b)} className="text-gray-500 hover:text-blue-400 transition-colors"><Edit2 className="w-4 h-4" /></button>
                  <button onClick={() => handleDelete(b.id)} className="text-gray-500 hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
                  <a href={`/transfer?beneficiary=${encodeURIComponent(JSON.stringify({ account: b.account_number, bank: b.bank_code, name: b.name }))}`}
                    className="flex items-center gap-1 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded-lg text-xs font-medium transition-colors">
                    <Send className="w-3 h-3" /> Send
                  </a>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex justify-center">
          <button onClick={fetchBeneficiaries} className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
      </div>
    </div>
  );
};

export default BeneficiaryManagement;
