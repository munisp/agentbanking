import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Edit3,
  Info,
  Loader2,
  PercentIcon,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Trash2,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import {
  AgentBalanceRecord,
  CommissionRecord,
  CommissionRule,
  CreateCommissionRulePayload,
  SettlementRecord,
  commissionApi,
} from "../../utils/api";

interface SettlementPolicy {
  id: string;
  allow_agent_withdrawal: boolean;
  min_withdrawal_amount: number;
  auto_process_on_eod: boolean;
  eod_cutoff_hour: number;
}

interface EodAgentResult {
  agent_id: string;
  settlement_ref: string;
  total_amount: number;
  commission_count: number;
  status: string;
  error?: string;
}

interface EodResult {
  run_at: string;
  agents_processed: number;
  total_paid: number;
  succeeded: EodAgentResult[];
  failed: EodAgentResult[];
}

const fmt = (n: number, currency = "NGN") =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n || 0);

const fmtDate = (d?: string) =>
  d
    ? new Date(d).toLocaleDateString("en-NG", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "—";

const pctDisplay = (rate: number) => `${(rate * 100).toFixed(3)}%`;

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  processing: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]",
  completed: "bg-green-100 text-green-700",
  settled: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
  disputed: "bg-orange-100 text-orange-700",
};

const TX_TYPES = [
  "deposit",
  "withdrawal",
  "transfer",
  "bill_payment",
  "airtime",
  "data",
];

const AGENT_TIERS = ["agent", "super_agent", "master_agent"];

const emptyRule = (): CreateCommissionRulePayload => ({
  agent_tier: "agent",
  transaction_type: "deposit",
  min_amount: 0,
  max_amount: 999999999,
  rate: 0.001,
  flat_fee: 0,
  is_active: true,
  effective_from: new Date().toISOString().slice(0, 10),
});

const CommissionSettlement: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "rules" | "commissions" | "settlements" | "balances" | "eod"
  >("rules");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [rules, setRules] = useState<CommissionRule[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [showRuleModal, setShowRuleModal] = useState(false);
  const [editingRule, setEditingRule] = useState<CommissionRule | null>(null);
  const [ruleForm, setRuleForm] =
    useState<CreateCommissionRulePayload>(emptyRule());
  const [ruleSaving, setRuleSaving] = useState(false);
  const [ruleSaveError, setRuleSaveError] = useState<string | null>(null);

  const [settlements, setSettlements] = useState<SettlementRecord[]>([]);
  const [settlementsTotal, setSettlementsTotal] = useState(0);
  const [settlementFilter, setSettlementFilter] = useState("all");
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [confirmProcessId, setConfirmProcessId] = useState<string | null>(null);

  const [commissions, setCommissions] = useState<CommissionRecord[]>([]);
  const [commissionsTotal, setCommissionsTotal] = useState(0);
  const [commissionFilter, setCommissionFilter] = useState("all");

  const [balances, setBalances] = useState<AgentBalanceRecord[]>([]);
  const [balancesTotal, setBalancesTotal] = useState(0);

  // Settlement policy
  const [policy, setPolicy] = useState<SettlementPolicy | null>(null);
  const [policyUpdating, setPolicyUpdating] = useState(false);

  // EOD
  const [eodRunning, setEodRunning] = useState(false);
  const [eodResult, setEodResult] = useState<EodResult | null>(null);
  const [eodError, setEodError] = useState<string | null>(null);

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const flash = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesRes, settRes, commRes, balRes, policyRes] = await Promise.allSettled([
        commissionApi.listRules(false),
        commissionApi.listSettlements({ limit: 50 }),
        commissionApi.listCommissions({ limit: 50 }),
        commissionApi.listAgentBalances(1, 50),
        commissionApi.getPolicy(),
      ]);
      if (rulesRes.status === "fulfilled") setRules(rulesRes.value.rules ?? []);
      if (settRes.status === "fulfilled") {
        setSettlements(settRes.value.settlements ?? []);
        setSettlementsTotal(settRes.value.total ?? 0);
      }
      if (commRes.status === "fulfilled") {
        setCommissions(commRes.value.commissions ?? []);
        setCommissionsTotal(commRes.value.total ?? 0);
      }
      if (balRes.status === "fulfilled") {
        setBalances(balRes.value.balances ?? []);
        setBalancesTotal(balRes.value.total ?? 0);
      }
      if (policyRes.status === "fulfilled") {
        setPolicy(policyRes.value as unknown as SettlementPolicy);
      }
    } catch (err: unknown) {
      setError((err as Error)?.message ?? "Failed to load commission data");
    } finally {
      setLoading(false);
    }
  }, []);

  const handlePolicyToggle = async (field: keyof SettlementPolicy, value: boolean | number) => {
    setPolicyUpdating(true);
    try {
      const updated = await commissionApi.updatePolicy({ [field]: value });
      setPolicy(updated as unknown as SettlementPolicy);
      flash(`Policy updated`);
    } catch {
      flash("Failed to update policy");
    } finally {
      setPolicyUpdating(false);
    }
  };

  const handleRunEod = async () => {
    setEodRunning(true);
    setEodError(null);
    setEodResult(null);
    try {
      const result = await commissionApi.runEod();
      setEodResult(result as unknown as EodResult);
      flash(`EOD complete — ${(result as unknown as EodResult).agents_processed} agents processed`);
      void loadAll();
    } catch (err: unknown) {
      setEodError((err as Error)?.message ?? "EOD run failed");
    } finally {
      setEodRunning(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const openCreateRule = () => {
    setEditingRule(null);
    setRuleForm(emptyRule());
    setRuleSaveError(null);
    setShowRuleModal(true);
  };

  const openEditRule = (rule: CommissionRule) => {
    setEditingRule(rule);
    setRuleForm({
      agent_tier: rule.agent_tier,
      transaction_type: rule.transaction_type,
      min_amount: rule.min_amount,
      max_amount: rule.max_amount,
      rate: rule.rate,
      flat_fee: rule.flat_fee,
      is_active: rule.is_active,
      effective_from: rule.effective_from.slice(0, 10),
      effective_to: rule.effective_to?.slice(0, 10),
    });
    setRuleSaveError(null);
    setShowRuleModal(true);
  };

  const handleSaveRule = async () => {
  setRuleSaving(true);
  setRuleSaveError(null);

  try {
    const payload = {
      ...ruleForm,
      effective_from: new Date(ruleForm.effective_from).toISOString(),
      effective_to: ruleForm.effective_to
        ? new Date(ruleForm.effective_to).toISOString()
        : undefined,
    };

    if (editingRule) {
      const updated = await commissionApi.updateRule(
        editingRule.id,
        payload
      );
      setRules((prev) =>
        prev.map((r) => (r.id === editingRule.id ? updated : r))
      );
      flash("Commission rule updated");
    } else {
      const created = await commissionApi.createRule(payload);
      setRules((prev) => [created, ...prev]);
      flash("Commission rule created");
    }

    setShowRuleModal(false);
  } catch (err: unknown) {
    setRuleSaveError((err as Error)?.message ?? "Save failed");
  } finally {
    setRuleSaving(false);
  }
};

  const handleDeactivateRule = async (rule: CommissionRule) => {
    try {
      await commissionApi.deleteRule(rule.id);
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_active: false } : r)),
      );
      flash("Rule deactivated");
    } catch {
      // silent
    }
  };

  const handleProcess = async (id: string) => {
    setProcessingId(id);
    setConfirmProcessId(null);
    try {
      await commissionApi.processSettlement(id);
      flash("Settlement processing started");
      void loadAll();
    } catch {
      void loadAll();
    } finally {
      setProcessingId(null);
    }
  };

  const visibleRules = showInactive ? rules : rules.filter((r) => r.is_active);
  const visibleSettlements =
    settlementFilter === "all"
      ? settlements
      : settlements.filter((s) => s.status === settlementFilter);

  const totalAvailable = balances.reduce(
    (s, b) => s + (b.available_balance ?? 0),
    0,
  );
  const totalPending = balances.reduce(
    (s, b) => s + (b.pending_balance ?? 0),
    0,
  );
  const totalEarned = balances.reduce((s, b) => s + (b.total_earned ?? 0), 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-7 h-7 animate-spin text-[var(--tenant-primary-color,#004F71)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex flex-col items-center gap-4">
        <AlertTriangle className="w-10 h-10 text-red-400" />
        <p className="text-gray-600">{error}</p>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
        >
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Commission Management
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Configure commission rules, review agent settlements, and monitor
            wallet balances
          </p>
        </div>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 px-3 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Success banner */}
      {successMsg && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
          <p className="text-sm text-green-700 font-medium">{successMsg}</p>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Active Rules",
            value: rules.filter((r) => r.is_active).length,
            icon: PercentIcon,
            iconCls: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]",
          },
          {
            label: "Pending Settlements",
            value: settlements.filter((s) => s.status === "pending").length,
            icon: Clock,
            iconCls: "bg-yellow-50 text-yellow-600",
          },
          {
            label: "Total Pending Wallets",
            value: fmt(totalPending),
            icon: Wallet,
            iconCls: "bg-orange-50 text-orange-600",
          },
          {
            label: "Total Available Wallets",
            value: fmt(totalAvailable),
            icon: TrendingUp,
            iconCls: "bg-green-50 text-green-600",
          },
        ].map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3"
          >
            <div
              className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${card.iconCls}`}
            >
              <card.icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-gray-500">{card.label}</p>
              <p className="text-base font-bold text-gray-900">{card.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {(
          [
            { key: "rules", label: "Commission Rules" },
            { key: "commissions", label: "Commissions" },
            { key: "settlements", label: "Settlements" },
            { key: "balances", label: "Agent Balances" },
            { key: "eod", label: "EOD & Policy" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              activeTab === tab.key
                ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* RULES TAB */}
      {activeTab === "rules" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded"
              />
              Show inactive rules
            </label>
            <button
              onClick={openCreateRule}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
            >
              <Plus className="w-4 h-4" /> New Rule
            </button>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-start gap-3">
            <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-700">
              Rates are stored as decimals (e.g.&nbsp;0.002 = 0.2%). Per CBN
              inter-scheme rules, Cash-In pool is ₦35/txn and Cash-Out is
              ₦50/txn. Commission = amount × rate + flat_fee.
            </p>
          </div>

          {visibleRules.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center gap-3 text-center">
              <PercentIcon className="w-10 h-10 text-gray-300" />
              <p className="font-semibold text-gray-600">
                No commission rules yet
              </p>
              <button
                onClick={openCreateRule}
                className="mt-1 flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
              >
                <Plus className="w-4 h-4" /> Create First Rule
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto max-h-[65vh] overflow-y-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {[
                        "Tier",
                        "Transaction Type",
                        "Amount Range",
                        "Rate",
                        "Flat Fee",
                        "Effective From",
                        "Status",
                        "",
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {visibleRules.map((rule) => (
                      <tr
                        key={rule.id}
                        className={`hover:bg-gray-50 ${!rule.is_active ? "opacity-50" : ""}`}
                      >
                        <td className="px-4 py-3 capitalize font-medium text-gray-800">
                          {rule.agent_tier?.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 capitalize text-gray-700">
                          {rule.transaction_type?.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {fmt(rule.min_amount)} –{" "}
                          {rule.max_amount >= 999999999
                            ? "∞"
                            : fmt(rule.max_amount)}
                        </td>
                        <td className="px-4 py-3 font-bold text-[var(--tenant-primary-color,#004F71)]">
                          {pctDisplay(rule.rate)}
                        </td>
                        <td className="px-4 py-3 text-gray-500">
                          {rule.flat_fee > 0 ? fmt(rule.flat_fee) : "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {fmtDate(rule.effective_from)}
                          {rule.effective_to
                            ? ` → ${fmtDate(rule.effective_to)}`
                            : ""}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${rule.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}
                          >
                            {rule.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 justify-end">
                            <button
                              onClick={() => openEditRule(rule)}
                              className="p-1.5 text-gray-400 hover:text-[var(--tenant-primary-color,#004F71)] hover:bg-[var(--tenant-primary-color,#004F71)]/5 rounded-lg"
                              title="Edit"
                            >
                              <Edit3 className="w-4 h-4" />
                            </button>
                            {rule.is_active && (
                              <button
                                onClick={() => handleDeactivateRule(rule)}
                                className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                                title="Deactivate"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* COMMISSIONS TAB */}
      {activeTab === "commissions" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {["all", "pending", "settled", "cancelled", "disputed"].map(
              (f) => (
                <button
                  key={f}
                  onClick={() => setCommissionFilter(f)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize border transition-colors ${
                    commissionFilter === f
                      ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]"
                      : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {f === "all"
                    ? `All (${commissionsTotal})`
                    : `${f} (${commissions.filter((c) => c.status === f).length})`}
                </button>
              ),
            )}
          </div>
          {commissions.filter(
            (c) => commissionFilter === "all" || c.status === commissionFilter,
          ).length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center gap-3">
              <TrendingUp className="w-10 h-10 text-gray-300" />
              <p className="text-sm text-gray-500">No commissions found</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {[
                        "Agent ID",
                        "Txn Ref",
                        "Type",
                        "Amount",
                        "Rate",
                        "Commission",
                        "Status",
                        "Earned At",
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {commissions
                      .filter(
                        (c) =>
                          commissionFilter === "all" ||
                          c.status === commissionFilter,
                      )
                      .map((c) => (
                        <tr
                          key={c.id}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          <td className="px-4 py-3 font-mono text-xs text-gray-600">
                            {c.agent_id?.slice(0, 8)}…
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {c.transaction_ref}
                          </td>
                          <td className="px-4 py-3 capitalize">
                            {c.transaction_type}
                          </td>
                          <td className="px-4 py-3">
                            {fmt(c.amount, c.currency)}
                          </td>
                          <td className="px-4 py-3">{pctDisplay(c.rate)}</td>
                          <td className="px-4 py-3 font-semibold text-[var(--tenant-primary-color,#004F71)]">
                            {fmt(c.commission_amount, c.currency)}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[c.status] ?? "bg-gray-100 text-gray-600"}`}
                            >
                              {c.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-500">
                            {fmtDate(c.earned_at)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SETTLEMENTS TAB */}
      {activeTab === "settlements" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {["all", "pending", "processing", "completed", "failed"].map(
              (f) => (
                <button
                  key={f}
                  onClick={() => setSettlementFilter(f)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize border transition-colors ${
                    settlementFilter === f
                      ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]"
                      : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {f === "all"
                    ? `All (${settlementsTotal})`
                    : `${f} (${settlements.filter((s) => s.status === f).length})`}
                </button>
              ),
            )}
          </div>

          {visibleSettlements.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center gap-3">
              <Clock className="w-10 h-10 text-gray-300" />
              <p className="text-sm text-gray-500">No settlements found</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {[
                        "Ref",
                        "Agent ID",
                        "Amount",
                        "Method",
                        "# Commissions",
                        "Period",
                        "Status",
                        "Created",
                        "",
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {visibleSettlements.map((s) => (
                      <tr key={s.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-700">
                          {s.settlement_ref}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-500 max-w-[120px] truncate">
                          {s.agent_id}
                        </td>
                        <td className="px-4 py-3 font-bold text-gray-900 whitespace-nowrap">
                          {fmt(s.total_amount, s.currency ?? "NGN")}
                        </td>
                        <td className="px-4 py-3 capitalize text-gray-600">
                          {s.payment_method?.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-center text-gray-500">
                          {s.commission_count}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                          {fmtDate(s.start_date)} – {fmtDate(s.end_date)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[s.status] ?? STATUS_BADGE.pending}`}
                          >
                            {s.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                          {fmtDate(s.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          {s.status === "pending" &&
                            (confirmProcessId === s.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleProcess(s.id)}
                                  disabled={processingId === s.id}
                                  className="px-2 py-1 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
                                >
                                  {processingId === s.id ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <CheckCircle className="w-3 h-3" />
                                  )}
                                  Confirm
                                </button>
                                <button
                                  onClick={() => setConfirmProcessId(null)}
                                  className="px-2 py-1 border border-gray-300 text-gray-600 rounded-lg text-xs hover:bg-gray-50"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmProcessId(s.id)}
                                className="px-3 py-1 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-xs font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] whitespace-nowrap"
                              >
                                Process
                              </button>
                            ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* BALANCES TAB */}
      {activeTab === "balances" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              {
                label: "Total Available",
                value: fmt(totalAvailable),
                color: "text-green-700",
              },
              {
                label: "Total Pending",
                value: fmt(totalPending),
                color: "text-yellow-700",
              },
              {
                label: "Total Lifetime Earned",
                value: fmt(totalEarned),
                color: "text-[var(--tenant-primary-color,#004F71)]",
              },
            ].map((c) => (
              <div
                key={c.label}
                className="bg-white rounded-xl border border-gray-200 p-5"
              >
                <p className="text-xs text-gray-500">{c.label}</p>
                <p className={`text-2xl font-bold mt-1 ${c.color}`}>
                  {c.value}
                </p>
              </div>
            ))}
          </div>

          {balances.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center gap-3">
              <Wallet className="w-10 h-10 text-gray-300" />
              <p className="text-sm text-gray-500">No agent balances found</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-200">
                <span className="text-sm font-bold text-gray-800">
                  Agent Commission Wallets
                  <span className="ml-2 text-gray-400 font-normal">
                    ({balancesTotal})
                  </span>
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {[
                        "Agent ID",
                        "Pending",
                        "Available",
                        "Settled",
                        "Total Earned",
                        "Currency",
                        "Last Settled",
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {balances.map((b) => (
                      <tr key={b.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-600 max-w-[140px] truncate">
                          {b.agent_id}
                        </td>
                        <td className="px-4 py-3 text-yellow-700 font-medium whitespace-nowrap">
                          {fmt(b.pending_balance, b.currency ?? "NGN")}
                        </td>
                        <td className="px-4 py-3 text-green-700 font-bold whitespace-nowrap">
                          {fmt(b.available_balance, b.currency ?? "NGN")}
                        </td>
                        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                          {fmt(b.settled_balance, b.currency ?? "NGN")}
                        </td>
                        <td className="px-4 py-3 font-semibold text-[var(--tenant-primary-color,#004F71)] whitespace-nowrap">
                          {fmt(b.total_earned, b.currency ?? "NGN")}
                        </td>
                        <td className="px-4 py-3 text-gray-400 uppercase text-xs">
                          {b.currency ?? "NGN"}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                          {fmtDate(b.last_settlement_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* EOD & POLICY TAB */}
      {activeTab === "eod" && (
        <div className="space-y-6">
          {/* Settlement Policy */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
            <div className="flex items-center gap-2">
              <Settings className="w-5 h-5 text-[var(--tenant-primary-color,#004F71)]" />
              <h2 className="text-base font-bold text-gray-900">Settlement Policy</h2>
            </div>
            <p className="text-sm text-gray-500">
              Platform-wide controls that govern how and when agents can withdraw their commission earnings.
            </p>

            <div className="divide-y divide-gray-100">
              {/* Allow agent withdrawal */}
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-semibold text-gray-800">Allow Agent Withdrawals</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    When off, agents cannot request withdrawals from their commission wallet.
                  </p>
                </div>
                <button
                  onClick={() => handlePolicyToggle("allow_agent_withdrawal", !policy?.allow_agent_withdrawal)}
                  disabled={policyUpdating || !policy}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
                    policy?.allow_agent_withdrawal ? "bg-[var(--tenant-primary-color,#004F71)]" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      policy?.allow_agent_withdrawal ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Auto process on EOD */}
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-semibold text-gray-800">Auto-process on EOD</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    When on, EOD run automatically processes (pays out) all pending settlements.
                  </p>
                </div>
                <button
                  onClick={() => handlePolicyToggle("auto_process_on_eod", !policy?.auto_process_on_eod)}
                  disabled={policyUpdating || !policy}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
                    policy?.auto_process_on_eod ? "bg-[var(--tenant-primary-color,#004F71)]" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      policy?.auto_process_on_eod ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Minimum withdrawal */}
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-semibold text-gray-800">Minimum Withdrawal Amount (₦)</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Agents must have at least this much in pending commissions before withdrawing.
                  </p>
                </div>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={policy?.min_withdrawal_amount ?? 0}
                  onChange={(e) =>
                    handlePolicyToggle("min_withdrawal_amount", parseFloat(e.target.value) || 0)
                  }
                  disabled={policyUpdating || !policy}
                  className="w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20 disabled:opacity-50"
                />
              </div>

              {/* EOD cutoff hour */}
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-semibold text-gray-800">EOD Cutoff Hour (0–23)</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Transactions after this hour are included in the next day's EOD batch.
                  </p>
                </div>
                <input
                  type="number"
                  min="0"
                  max="23"
                  step="1"
                  value={policy?.eod_cutoff_hour ?? 23}
                  onChange={(e) =>
                    handlePolicyToggle("eod_cutoff_hour", parseInt(e.target.value) || 23)
                  }
                  disabled={policyUpdating || !policy}
                  className="w-20 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20 disabled:opacity-50"
                />
              </div>
            </div>
          </div>

          {/* EOD Run */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Play className="w-5 h-5 text-[var(--tenant-primary-color,#004F71)]" />
              <h2 className="text-base font-bold text-gray-900">End-of-Day Settlement Run</h2>
            </div>
            <p className="text-sm text-gray-500">
              Runs the EOD batch: finds every agent with pending commissions, creates a settlement
              batch for each, and processes payouts (if auto-process is enabled). This is safe to
              run manually at any time.
            </p>

            {eodError && (
              <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{eodError}</p>
              </div>
            )}

            <button
              onClick={handleRunEod}
              disabled={eodRunning}
              className="flex items-center gap-2 px-5 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {eodRunning ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Running EOD…</>
              ) : (
                <><Play className="w-4 h-4" /> Run EOD Now</>
              )}
            </button>

            {eodResult && (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Agents Processed", value: eodResult.agents_processed },
                    { label: "Succeeded", value: eodResult.succeeded.length, cls: "text-green-700" },
                    { label: "Failed", value: eodResult.failed.length, cls: "text-red-600" },
                  ].map((s) => (
                    <div key={s.label} className="bg-gray-50 rounded-lg p-4 text-center">
                      <p className="text-xs text-gray-500">{s.label}</p>
                      <p className={`text-2xl font-bold mt-1 ${s.cls ?? "text-gray-900"}`}>{s.value}</p>
                    </div>
                  ))}
                </div>

                <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-medium">Total paid out</span>
                  <span className="text-lg font-bold text-[var(--tenant-primary-color,#004F71)]">
                    {new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(eodResult.total_paid)}
                  </span>
                </div>

                {eodResult.failed.length > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg overflow-hidden">
                    <div className="px-4 py-3 border-b border-red-100">
                      <p className="text-sm font-semibold text-red-700">Failed Agents</p>
                    </div>
                    <div className="divide-y divide-red-100">
                      {eodResult.failed.map((f) => (
                        <div key={f.agent_id} className="px-4 py-3 flex items-start gap-3">
                          <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-mono text-gray-700">{f.agent_id}</p>
                            <p className="text-xs text-red-600 mt-0.5">{f.error}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {eodResult.succeeded.length > 0 && (
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 border-b border-gray-200">
                            {["Agent ID", "Ref", "Commissions", "Amount", "Status"].map((h) => (
                              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {eodResult.succeeded.map((r) => (
                            <tr key={r.agent_id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 font-mono text-xs text-gray-600 max-w-[120px] truncate">{r.agent_id}</td>
                              <td className="px-4 py-3 font-mono text-xs">{r.settlement_ref}</td>
                              <td className="px-4 py-3 text-center text-gray-500">{r.commission_count}</td>
                              <td className="px-4 py-3 font-semibold text-[var(--tenant-primary-color,#004F71)]">
                                {new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(r.total_amount)}
                              </td>
                              <td className="px-4 py-3">
                                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[r.status] ?? "bg-green-100 text-green-700"}`}>
                                  {r.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* RULE MODAL */}
      {showRuleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">
                {editingRule ? "Edit Commission Rule" : "New Commission Rule"}
              </h2>
              <button
                onClick={() => setShowRuleModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Agent Tier
                </label>
                <select
                  value={ruleForm.agent_tier}
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, agent_tier: e.target.value })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                >
                  {AGENT_TIERS.map((t) => (
                    <option key={t} value={t}>
                      {t.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Transaction Type
                </label>
                <select
                  value={ruleForm.transaction_type}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      transaction_type: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                >
                  {TX_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Rate (decimal — e.g. 0.002 = 0.2%)
                </label>
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  value={ruleForm.rate}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      rate: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
                <p className="text-xs text-gray-400 mt-1">
                  ≈ {pctDisplay(ruleForm.rate ?? 0)} of amount
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Flat Fee (₦)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={ruleForm.flat_fee ?? 0}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      flat_fee: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Min Transaction Amount (₦)
                </label>
                <input
                  type="number"
                  min="0"
                  value={ruleForm.min_amount ?? 0}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      min_amount: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Max Transaction Amount (₦)
                </label>
                <input
                  type="number"
                  min="0"
                  value={ruleForm.max_amount ?? 999999999}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      max_amount: parseFloat(e.target.value) || 999999999,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Effective From
                </label>
                <input
                  type="date"
                  value={ruleForm.effective_from}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      effective_from: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Effective To (optional)
                </label>
                <input
                  type="date"
                  value={ruleForm.effective_to ?? ""}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      effective_to: e.target.value || undefined,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#004F71)]/20"
                />
              </div>
            </div>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={ruleForm.is_active ?? true}
                onChange={(e) =>
                  setRuleForm({ ...ruleForm, is_active: e.target.checked })
                }
                className="rounded"
              />
              <span className="text-sm text-gray-700 font-medium">Active</span>
            </label>

            {ruleSaveError && (
              <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                {ruleSaveError}
              </p>
            )}

            <div className="flex gap-3 pt-1">
              <button
                onClick={() => setShowRuleModal(false)}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRule}
                disabled={ruleSaving}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {ruleSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Saving…
                  </>
                ) : editingRule ? (
                  "Save Changes"
                ) : (
                  "Create Rule"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommissionSettlement;
