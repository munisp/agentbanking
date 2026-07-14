import { AlertCircle, CheckCircle, Plus, RefreshCw, Search } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../utils/api";

type RuleAction = "full_refund" | "partial_refund" | "deny" | "escalate" | "merchant_credit";

type AutoRule = {
  id: string;
  name: string;
  dispute_type: string;
  threshold_amount: number;
  action: RuleAction;
  active: boolean;
};

const ACTION_COLOR: Record<RuleAction, string> = {
  full_refund: "text-green-600",
  partial_refund: "text-[var(--tenant-primary-color,#004F71)]",
  deny: "text-red-600",
  escalate: "text-amber-600",
  merchant_credit: "text-purple-600",
};

const DisputeAutoRules: React.FC = () => {
  const [rules, setRules] = useState<AutoRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);

  const [name, setName] = useState("");
  const [disputeType, setDisputeType] = useState("duplicate");
  const [thresholdAmount, setThresholdAmount] = useState("10000");
  const [action, setAction] = useState<RuleAction>("full_refund");
  const [active, setActive] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const res = await api.listDisputeAutoRules();
      const payload = res && typeof res === "object" ? (res as { rules?: AutoRule[]; data?: AutoRule[] }) : {};
      setRules(payload.rules ?? payload.data ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load auto-resolution rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const stats = useMemo(() => {
    const total = rules.length;
    const activeCount = rules.filter((r) => r.active).length;
    const inactiveCount = total - activeCount;
    const refundRules = rules.filter((r) => ["full_refund", "partial_refund"].includes(r.action)).length;
    return { total, activeCount, inactiveCount, refundRules };
  }, [rules]);

  const submit = async () => {
    if (!name.trim()) { setError("Rule name is required"); return; }
    try {
      setSaving(true);
      await api.upsertDisputeAutoRule({ name: name.trim(), dispute_type: disputeType, threshold_amount: Number(thresholdAmount || 0), action, active });
      setSuccess("Rule saved successfully");
      setName(""); setDisputeType("duplicate"); setThresholdAmount("10000"); setAction("full_refund"); setActive(true);
      setShowForm(false);
      await load();
    } catch (err: any) {
      setError(err?.message || "Failed to save rule");
    } finally {
      setSaving(false);
    }
  };

  const toggleRule = async (rule: AutoRule) => {
    try {
      await api.upsertDisputeAutoRule({ id: rule.id, name: rule.name, dispute_type: rule.dispute_type, threshold_amount: rule.threshold_amount, action: rule.action, active: !rule.active });
      await load();
    } catch (err: any) {
      setError(err?.message || "Failed to update rule status");
    }
  };

  const filtered = rules.filter((r) => !search || r.name.toLowerCase().includes(search.toLowerCase()) || r.dispute_type.toLowerCase().includes(search.toLowerCase()) || r.action.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dispute Auto Rules</h1>
          <p className="text-sm text-gray-500 mt-1">Configure rule-based automation for dispute outcomes</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] text-sm font-medium">
          <Plus size={16} />
          New Rule
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />{error}<button onClick={() => setError("")} className="ml-auto">×</button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />{success}<button onClick={() => setSuccess("")} className="ml-auto">×</button>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Rules", value: stats.total, color: "text-gray-900" },
          { label: "Active Rules", value: stats.activeCount, color: "text-green-600" },
          { label: "Inactive Rules", value: stats.inactiveCount, color: "text-gray-500" },
          { label: "Refund Rules", value: stats.refundRules, color: "text-[var(--tenant-primary-color,#004F71)]" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Full Refund Rules", value: rules.filter((r) => r.action === "full_refund").length, color: "text-green-600" },
          { label: "Escalation Rules", value: rules.filter((r) => r.action === "escalate").length, color: "text-amber-600" },
          { label: "Deny Rules", value: rules.filter((r) => r.action === "deny").length, color: "text-red-600" },
          { label: "Merchant Credit Rules", value: rules.filter((r) => r.action === "merchant_credit").length, color: "text-purple-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Create New Rule</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Rule name" className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            <select value={disputeType} onChange={(e) => setDisputeType(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
              {["chargeback", "reversal", "failed_credit", "duplicate", "unauthorized"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input type="number" value={thresholdAmount} onChange={(e) => setThresholdAmount(e.target.value)} placeholder="Threshold amount (NGN)" className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            <select value={action} onChange={(e) => setAction(e.target.value as RuleAction)} className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
              {["full_refund", "partial_refund", "deny", "escalate", "merchant_credit"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <label className="inline-flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="w-4 h-4" />
              Active
            </label>
          </div>
          <div className="flex gap-3">
            <button onClick={submit} disabled={saving} className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]">
              {saving ? "Saving..." : "Save Rule"}
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold text-gray-900">Records</h2>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-sm w-56" />
            </div>
            <button onClick={load} disabled={loading} className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {["Name", "Dispute Type", "Threshold", "Action", "Status", "Toggle"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                {rules.length === 0 ? "Data loaded — connect to live database for full records" : "No matching records"}
              </td></tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-900 font-medium">{r.name}</td>
                  <td className="px-4 py-3 text-gray-600 capitalize">{r.dispute_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">{new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(r.threshold_amount || 0)}</td>
                  <td className="px-4 py-3"><span className={`font-semibold text-xs ${ACTION_COLOR[r.action]}`}>{r.action}</span></td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${r.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {r.active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleRule(r)} className={`text-xs font-medium hover:underline ${r.active ? "text-red-600" : "text-green-600"}`}>
                      {r.active ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

function mockRules(): AutoRule[] {
  return [
    { id: "1", name: "Auto refund duplicates under 10k", dispute_type: "duplicate", threshold_amount: 10000, action: "full_refund", active: true },
    { id: "2", name: "Escalate unauthorized above 25k", dispute_type: "unauthorized", threshold_amount: 25000, action: "escalate", active: true },
  ];
}

export default DisputeAutoRules;
