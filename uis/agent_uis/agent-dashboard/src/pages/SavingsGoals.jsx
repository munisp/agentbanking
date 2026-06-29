import { Target, Plus, TrendingUp, CheckCircle, Clock, RefreshCw, Trash2, PiggyBank, Award } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const GOAL_ICONS = { emergency: "🛡️", equipment: "💻", travel: "✈️", education: "🎓", housing: "🏠", business: "💼", vehicle: "🚗", wedding: "💍", other: "🎯" };

const SavingsGoals = () => {
  const { user } = useAuth();
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [contributing, setContributing] = useState(null);
  const [contribAmount, setContribAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", target_amount: "", category: "other", target_date: "", auto_save: false, auto_amount: "" });

  useEffect(() => { if (user?.keycloakId) fetchGoals(); }, [user?.keycloakId]);

  const fetchGoals = async () => {
    setLoading(true);
    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;
      const res = await fetch(`${CORE_BANKING_URL}/savings/api/v1/savings/goals?agent_id=${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setGoals(Array.isArray(data.goals) ? data.goals : Array.isArray(data) ? data : []);
      }
    } catch { setGoals([]); }
    finally { setLoading(false); }
  };

  const createGoal = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/savings/api/v1/savings/goals`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, agent_id: keycloakId, target_amount: parseFloat(form.target_amount), auto_amount: form.auto_save ? parseFloat(form.auto_amount) : undefined }),
      });
      if (!res.ok) throw new Error("Failed to create savings goal");
      setShowForm(false);
      setForm({ name: "", target_amount: "", category: "other", target_date: "", auto_save: false, auto_amount: "" });
      fetchGoals();
    } catch (err) { alert(err.message); }
    finally { setSaving(false); }
  };

  const contribute = async (goalId) => {
    if (!contribAmount || isNaN(parseFloat(contribAmount))) return;
    try {
      const res = await fetch(`${CORE_BANKING_URL}/savings/api/v1/savings/goals/${goalId}/contribute`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ amount: parseFloat(contribAmount) }),
      });
      if (!res.ok) throw new Error("Contribution failed");
      setContributing(null);
      setContribAmount("");
      fetchGoals();
    } catch (err) { alert(err.message); }
  };

  const deleteGoal = async (id) => {
    if (!confirm("Delete this savings goal?")) return;
    try {
      await fetch(`${CORE_BANKING_URL}/savings/api/v1/savings/goals/${id}`, { method: "DELETE", headers: authHeaders() });
      fetchGoals();
    } catch (err) { alert(err.message); }
  };

  const totalSaved = goals.reduce((s, g) => s + parseFloat(g.current_amount || 0), 0);
  const totalTarget = goals.reduce((s, g) => s + parseFloat(g.target_amount || 0), 0);
  const completedGoals = goals.filter(g => parseFloat(g.current_amount || 0) >= parseFloat(g.target_amount || 0)).length;

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-600/20 rounded-lg"><Target className="w-6 h-6 text-emerald-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Savings Goals</h1>
              <p className="text-gray-400 text-sm">Set targets and track your savings progress</p>
            </div>
          </div>
          <button onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors">
            <Plus className="w-4 h-4" /> New Goal
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Total Saved", value: `₦${totalSaved.toLocaleString()}`, icon: PiggyBank, color: "text-emerald-400" },
            { label: "Total Target", value: `₦${totalTarget.toLocaleString()}`, icon: Target, color: "text-blue-400" },
            { label: "Completed", value: `${completedGoals}/${goals.length}`, icon: Award, color: "text-yellow-400" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="text-xs text-gray-400">{label}</span>
              </div>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Create Form */}
        {showForm && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
            <h2 className="font-semibold mb-4">New Savings Goal</h2>
            <form onSubmit={createGoal} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Goal Name</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Emergency Fund, New Phone"
                  required className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Target Amount (₦)</label>
                  <input type="number" value={form.target_amount} onChange={e => setForm(f => ({ ...f, target_amount: e.target.value }))} placeholder="0"
                    required className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Category</label>
                  <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                    {Object.keys(GOAL_ICONS).map(k => <option key={k} value={k}>{GOAL_ICONS[k]} {k.charAt(0).toUpperCase() + k.slice(1)}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Target Date (optional)</label>
                <input type="date" value={form.target_date} onChange={e => setForm(f => ({ ...f, target_date: e.target.value }))}
                  className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.auto_save} onChange={e => setForm(f => ({ ...f, auto_save: e.target.checked }))} className="rounded" />
                <span className="text-sm text-gray-600">Enable auto-save from commissions</span>
              </label>
              {form.auto_save && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Auto-save Amount per transaction (₦)</label>
                  <input type="number" value={form.auto_amount} onChange={e => setForm(f => ({ ...f, auto_amount: e.target.value }))} placeholder="e.g. 500"
                    className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
                </div>
              )}
              <div className="flex gap-2">
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2">
                  {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                  {saving ? "Creating..." : "Create Goal"}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Goals List */}
        {loading ? (
          <div className="text-center py-12 text-gray-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading goals...</div>
        ) : goals.length === 0 ? (
          <div className="text-center py-16 text-gray-500 bg-gray-100 border border-gray-200 rounded-xl">
            <Target className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No savings goals yet</p>
            <p className="text-sm mt-1">Create a goal to start tracking your savings</p>
          </div>
        ) : (
          <div className="space-y-4">
            {goals.map((goal, i) => {
              const current = parseFloat(goal.current_amount || 0);
              const target = parseFloat(goal.target_amount || 1);
              const pct = Math.min(100, (current / target) * 100);
              const completed = current >= target;
              const daysLeft = goal.target_date ? Math.ceil((new Date(goal.target_date) - new Date()) / 86400000) : null;
              return (
                <div key={goal.id || i} className={`bg-gray-100 border rounded-xl p-5 ${completed ? "border-emerald-700/50" : "border-gray-200"}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{GOAL_ICONS[goal.category] || "🎯"}</span>
                      <div>
                        <p className="font-semibold">{goal.name}</p>
                        <p className="text-xs text-gray-500 capitalize">{goal.category}{goal.auto_save ? " · Auto-save on" : ""}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {completed && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3 h-3" /> Complete</span>}
                      {daysLeft !== null && !completed && (
                        <span className={`text-xs flex items-center gap-1 ${daysLeft < 7 ? "text-red-400" : daysLeft < 30 ? "text-amber-400" : "text-gray-400"}`}>
                          <Clock className="w-3 h-3" /> {daysLeft}d left
                        </span>
                      )}
                      <button onClick={() => deleteGoal(goal.id)} className="text-gray-600 hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>₦{current.toLocaleString()} saved</span>
                      <span>₦{target.toLocaleString()} target</span>
                    </div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${completed ? "bg-emerald-500" : pct > 60 ? "bg-blue-500" : pct > 30 ? "bg-yellow-500" : "bg-orange-500"}`}
                        style={{ width: `${pct}%` }} />
                    </div>
                    <p className="text-right text-xs text-gray-500 mt-0.5">{pct.toFixed(1)}%</p>
                  </div>

                  {/* Contribute */}
                  {!completed && (
                    contributing === goal.id ? (
                      <div className="flex gap-2">
                        <input type="number" value={contribAmount} onChange={e => setContribAmount(e.target.value)} placeholder="Amount to add"
                          className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500" autoFocus />
                        <button onClick={() => contribute(goal.id)} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-xs font-medium transition-colors">Add</button>
                        <button onClick={() => { setContributing(null); setContribAmount(""); }} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs transition-colors">Cancel</button>
                      </div>
                    ) : (
                      <button onClick={() => setContributing(goal.id)}
                        className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors">
                        <Plus className="w-3 h-3" /> Add funds
                      </button>
                    )
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default SavingsGoals;
