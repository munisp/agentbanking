import {
  AlertCircle,
  ArrowRight,
  CheckCircle,
  Clock,
  Plus,
  RefreshCw,
  Settings2,
  Trash2,
} from "lucide-react";
import React, { useEffect, useState } from "react";

type SettlementServiceStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

interface SettlementServiceRecord {
  id: number;
  settlement_date: string;
  status: SettlementServiceStatus;
  amount: number;
  currency: string;
  transaction_count: number;
  external_reference_id?: string;
  created_at: string;
  updated_at: string;
  logs: Array<{
    id: number;
    settlement_id: number;
    timestamp: string;
    level: "INFO" | "WARNING" | "ERROR" | "DEBUG";
    message: string;
    details?: string;
  }>;
}

const SETTLEMENT_BASE_URL =
  import.meta.env.VITE_SETTLEMENT_API_URL ||
  import.meta.env.VITE_AGENT_API_URL ||
  "https://54agent.upi.dev";

function settlementHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function settlementRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const candidates = [
    `${SETTLEMENT_BASE_URL}/commission/api/v1${path}`,
  ];

  let lastError = "Request failed";
  for (const url of candidates) {
    try {
      const res = await fetch(url, options);
      const json = await res.json();
      if (!res.ok) {
        lastError =
          json?.detail || json?.message || `${res.status} ${res.statusText}`;
        continue;
      }
      return json as T;
    } catch {
      lastError = "Network error";
    }
  }

  throw new Error(lastError);
}

const settlementApi = {
  list: (params: {
    status_filter?: SettlementServiceStatus;
    currency_filter?: string;
    skip?: number;
    limit?: number;
  }) => {
    const qp = new URLSearchParams({
      skip: String(params.skip ?? 0),
      limit: String(params.limit ?? 100),
      ...(params.status_filter && { status_filter: params.status_filter }),
      ...(params.currency_filter && {
        currency_filter: params.currency_filter,
      }),
    }).toString();
    return settlementRequest<SettlementServiceRecord[]>(
      `/settlements?${qp}`,
      { headers: settlementHeaders() },
    );
  },
  get: (id: number) =>
    settlementRequest<SettlementServiceRecord>(`/settlements/${id}`, {
      headers: settlementHeaders(),
    }),
  create: (data: {
    settlement_date: string;
    amount: number;
    currency: string;
    transaction_count?: number;
    external_reference_id?: string;
  }) =>
    settlementRequest<SettlementServiceRecord>("/settlements", {
      method: "POST",
      headers: settlementHeaders(),
      body: JSON.stringify(data),
    }),
  update: (
    id: number,
    data: {
      status?: SettlementServiceStatus;
      amount?: number;
      transaction_count?: number;
      external_reference_id?: string;
    },
  ) =>
    settlementRequest<SettlementServiceRecord>(`/settlements/${id}`, {
      method: "PUT",
      headers: settlementHeaders(),
      body: JSON.stringify(data),
    }),
  process: (id: number) =>
    settlementRequest<SettlementServiceRecord>(
      `/settlements/${id}/process`,
      { method: "POST", headers: settlementHeaders() },
    ),
};

interface SettlementStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  total_amount: number;
}

type SettlementPayoutMode = "IMMEDIATE" | "CYCLE_END";
type SettlementCycleUnit = "DAILY" | "WEEKLY" | "MONTHLY";
type SettlementEntityType = "AGENT" | "SUPER_AGENT" | "SPECIFIC_AGENT";

interface SettlementPolicyConfig {
  default_mode: SettlementPayoutMode;
  cycle_unit: SettlementCycleUnit;
  cycle_value: number;
}

interface SettlementPayoutRule {
  id: string;
  rule_name: string;
  entity_type: SettlementEntityType;
  entity_identifier?: string;
  payout_mode: SettlementPayoutMode;
  cycle_unit?: SettlementCycleUnit;
  cycle_value?: number;
  min_amount?: number;
  max_amount?: number;
  is_active: boolean;
  created_at: string;
}

const POLICY_STORAGE_KEY = "settlement_payment_policy_v1";
const RULES_STORAGE_KEY = "settlement_payment_rules_v1";

const DEFAULT_POLICY: SettlementPolicyConfig = {
  default_mode: "CYCLE_END",
  cycle_unit: "DAILY",
  cycle_value: 1,
};

const randomId = () => Math.random().toString(36).slice(2, 10);

function readJson<T>(storageKey: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(storageKey: string, value: unknown) {
  localStorage.setItem(storageKey, JSON.stringify(value));
}

const STATUS_CONFIG: Record<
  SettlementServiceStatus,
  { label: string; color: string }
> = {
  PENDING: { label: "Pending", color: "bg-amber-100 text-amber-700" },
  PROCESSING: { label: "Processing", color: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]" },
  COMPLETED: { label: "Completed", color: "bg-green-100 text-green-700" },
  FAILED: { label: "Failed", color: "bg-red-100 text-red-700" },
  CANCELLED: { label: "Cancelled", color: "bg-gray-100 text-gray-600" },
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
  }).format(n || 0);

const SettlementBatchProcessor: React.FC = () => {
  const [settlements, setSettlements] = useState<SettlementServiceRecord[]>(
    [],
  );
  const [stats, setStats] = useState<SettlementStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newSettlementDate, setNewSettlementDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [newAmount, setNewAmount] = useState(0);
  const [newCurrency, setNewCurrency] = useState("NGN");
  const [newTransactionCount, setNewTransactionCount] = useState(0);
  const [newExternalRef, setNewExternalRef] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "ALL" | SettlementServiceStatus
  >("ALL");
  const [currencyFilter, setCurrencyFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState<
    "OVERVIEW" | "DETAILS" | "HISTORY" | "SETTINGS"
  >("OVERVIEW");
  const [selectedRecord, setSelectedRecord] =
    useState<SettlementServiceRecord | null>(null);
  const [updateStatus, setUpdateStatus] =
    useState<SettlementServiceStatus>("PENDING");
  const [policyConfig, setPolicyConfig] =
    useState<SettlementPolicyConfig>(DEFAULT_POLICY);
  const [rules, setRules] = useState<SettlementPayoutRule[]>([]);
  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleEntityType, setNewRuleEntityType] =
    useState<SettlementEntityType>("AGENT");
  const [newRuleEntityIdentifier, setNewRuleEntityIdentifier] = useState("");
  const [newRulePayoutMode, setNewRulePayoutMode] =
    useState<SettlementPayoutMode>("CYCLE_END");
  const [newRuleCycleUnit, setNewRuleCycleUnit] =
    useState<SettlementCycleUnit>("DAILY");
  const [newRuleCycleValue, setNewRuleCycleValue] = useState(1);
  const [newRuleMinAmount, setNewRuleMinAmount] = useState<number | "">("");
  const [newRuleMaxAmount, setNewRuleMaxAmount] = useState<number | "">("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadSettlements();
  }, [statusFilter, currencyFilter]);

  useEffect(() => {
    const savedPolicy = readJson<SettlementPolicyConfig>(
      POLICY_STORAGE_KEY,
      DEFAULT_POLICY,
    );
    const savedRules = readJson<SettlementPayoutRule[]>(RULES_STORAGE_KEY, []);
    setPolicyConfig(savedPolicy);
    setRules(savedRules);
  }, []);

  const loadSettlements = async () => {
    try {
      setLoading(true);
      setError("");
      const raw = await settlementApi.list({
        limit: 200,
        ...(statusFilter !== "ALL" ? { status_filter: statusFilter } : {}),
        ...(currencyFilter.trim()
          ? { currency_filter: currencyFilter.trim().toUpperCase() }
          : {}),
      });

      const data: SettlementServiceRecord[] = Array.isArray(raw)
        ? raw
        : (raw as any)?.settlements ?? (raw as any)?.data ?? [];

      setSettlements(data);
      const s: SettlementStats = {
        total: data.length,
        pending: data.filter((item) => item.status?.toUpperCase() === "PENDING").length,
        processing: data.filter((item) => item.status?.toUpperCase() === "PROCESSING").length,
        completed: data.filter((item) => item.status?.toUpperCase() === "COMPLETED").length,
        failed: data.filter((item) => item.status?.toUpperCase() === "FAILED").length,
        total_amount: data.reduce((sum, item) => sum + item.amount, 0),
      };
      setStats(s);
    } catch (err: any) {
      setError(err.message || "Failed to load settlements");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSettlement = async () => {
    if (newAmount <= 0) {
      setError("Amount must be greater than zero");
      return;
    }

    try {
      setCreating(true);
      await settlementApi.create({
        settlement_date: new Date(newSettlementDate).toISOString(),
        amount: Number(newAmount),
        currency: newCurrency.trim().toUpperCase(),
        transaction_count: Number(newTransactionCount),
        external_reference_id: newExternalRef.trim() || undefined,
      });
      setSuccess("Settlement created successfully");
      setShowCreateModal(false);
      await loadSettlements();
    } catch (err: any) {
      setError(err.message || "Failed to create settlement");
    } finally {
      setCreating(false);
    }
  };

  const handleProcessSettlement = async (settlementId: number) => {
    try {
      setActionId(settlementId);
      await settlementApi.process(settlementId);
      setSuccess("Settlement moved to PROCESSING");
      await loadSettlements();
      if (selectedRecord?.id === settlementId) {
        const latest = await settlementApi.get(settlementId);
        setSelectedRecord(latest);
        setUpdateStatus(latest.status);
      }
    } catch (err: any) {
      setError(err.message || "Failed to process settlement");
    } finally {
      setActionId(null);
    }
  };

  const openRecord = async (id: number) => {
    try {
      const detail = await settlementApi.get(id);
      setSelectedRecord(detail);
      setUpdateStatus(detail.status);
    } catch (err: any) {
      setError(err.message || "Failed to load settlement details");
    }
  };

  const handleUpdateStatus = async () => {
    if (!selectedRecord) return;

    try {
      setActionId(selectedRecord.id);
      const updated = await settlementApi.update(selectedRecord.id, {
        status: updateStatus,
      });
      setSelectedRecord(updated);
      setSuccess(`Settlement status updated to ${updateStatus}`);
      await loadSettlements();
    } catch (err: any) {
      setError(err.message || "Failed to update settlement status");
    } finally {
      setActionId(null);
    }
  };

  const handleSavePolicy = () => {
    if (
      policyConfig.default_mode === "CYCLE_END" &&
      policyConfig.cycle_value <= 0
    ) {
      setError("Cycle value must be greater than zero");
      return;
    }

    writeJson(POLICY_STORAGE_KEY, policyConfig);
    setSuccess("Settlement payment policy saved");
  };

  const resetRuleDraft = () => {
    setNewRuleName("");
    setNewRuleEntityType("AGENT");
    setNewRuleEntityIdentifier("");
    setNewRulePayoutMode("CYCLE_END");
    setNewRuleCycleUnit("DAILY");
    setNewRuleCycleValue(1);
    setNewRuleMinAmount("");
    setNewRuleMaxAmount("");
  };

  const handleAddRule = () => {
    if (!newRuleName.trim()) {
      setError("Rule name is required");
      return;
    }

    if (
      newRuleEntityType === "SPECIFIC_AGENT" &&
      !newRuleEntityIdentifier.trim()
    ) {
      setError("Specific agent identifier is required");
      return;
    }

    if (newRulePayoutMode === "CYCLE_END" && newRuleCycleValue <= 0) {
      setError("Cycle value must be greater than zero");
      return;
    }

    const minAmount =
      newRuleMinAmount === "" ? undefined : Number(newRuleMinAmount);
    const maxAmount =
      newRuleMaxAmount === "" ? undefined : Number(newRuleMaxAmount);

    if (
      minAmount !== undefined &&
      maxAmount !== undefined &&
      minAmount > maxAmount
    ) {
      setError("Minimum amount cannot be greater than maximum amount");
      return;
    }

    const nextRule: SettlementPayoutRule = {
      id: randomId(),
      rule_name: newRuleName.trim(),
      entity_type: newRuleEntityType,
      entity_identifier: newRuleEntityIdentifier.trim() || undefined,
      payout_mode: newRulePayoutMode,
      cycle_unit:
        newRulePayoutMode === "CYCLE_END" ? newRuleCycleUnit : undefined,
      cycle_value:
        newRulePayoutMode === "CYCLE_END"
          ? Number(newRuleCycleValue)
          : undefined,
      min_amount: minAmount,
      max_amount: maxAmount,
      is_active: true,
      created_at: new Date().toISOString(),
    };

    const updatedRules = [nextRule, ...rules];
    setRules(updatedRules);
    writeJson(RULES_STORAGE_KEY, updatedRules);
    setSuccess("Settlement rule added");
    resetRuleDraft();
  };

  const handleToggleRule = (ruleId: string) => {
    const updatedRules = rules.map((rule) =>
      rule.id === ruleId ? { ...rule, is_active: !rule.is_active } : rule,
    );
    setRules(updatedRules);
    writeJson(RULES_STORAGE_KEY, updatedRules);
  };

  const handleDeleteRule = (ruleId: string) => {
    const updatedRules = rules.filter((rule) => rule.id !== ruleId);
    setRules(updatedRules);
    writeJson(RULES_STORAGE_KEY, updatedRules);
    setSuccess("Settlement rule removed");
  };

  const searched = settlements.filter((item) => {
    const needle = searchTerm.trim().toLowerCase();
    if (!needle) return true;
    return (
      String(item.id).includes(needle) ||
      item.status.toLowerCase().includes(needle) ||
      item.currency.toLowerCase().includes(needle) ||
      (item.external_reference_id || "").toLowerCase().includes(needle)
    );
  });

  const renderRulesTable = () => (
    <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-sm font-semibold text-gray-900">
          Configured Entity Rules
        </p>
        <p className="text-xs text-gray-500">
          Rule priority is top-down. The first matching active rule is applied.
        </p>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {[
              "Rule",
              "Entity",
              "Payout",
              "Amount Range",
              "Status",
              "Actions",
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
          {rules.length === 0 ? (
            <tr>
              <td
                colSpan={6}
                className="px-4 py-8 text-center text-gray-400"
              >
                No entity settlement rules configured
              </td>
            </tr>
          ) : (
            rules.map((rule) => (
              <tr key={rule.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{rule.rule_name}</p>
                  <p className="text-xs text-gray-400">
                    Created {new Date(rule.created_at).toLocaleString()}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p className="text-gray-700">
                    {rule.entity_type.replace("_", " ")}
                  </p>
                  <p className="text-xs text-gray-400">
                    {rule.entity_identifier || "All in scope"}
                  </p>
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {rule.payout_mode === "IMMEDIATE"
                    ? "Immediate"
                    : `Every ${rule.cycle_value} ${String(rule.cycle_unit || "").toLowerCase()}`}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {rule.min_amount ?? "-"} to {rule.max_amount ?? "-"}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggleRule(rule.id)}
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      rule.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {rule.is_active ? "Active" : "Inactive"}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="inline-flex items-center gap-1 px-2 py-1 border border-red-300 text-red-600 rounded text-xs hover:bg-red-50"
                  >
                    <Trash2 size={11} />
                    Delete
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Settlement Batch Processor
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage and monitor settlement batch processor operations
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadSettlements}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]"
          >
            <Plus size={14} />
            New Entry
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { id: "OVERVIEW", label: "Overview" },
          { id: "DETAILS", label: "Details" },
          { id: "HISTORY", label: "History" },
          { id: "SETTINGS", label: "Settings" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() =>
              setActiveTab(
                tab.id as "OVERVIEW" | "DETAILS" | "HISTORY" | "SETTINGS",
              )
            }
            className={`px-4 py-2 rounded-full text-xs font-medium border transition-colors ${
              activeTab === tab.id
                ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {[
            {
              label: "Total Records",
              value: stats.total,
              color: "text-gray-900",
            },
            {
              label: "Active Items",
              value: stats.processing,
              color: "text-gray-900",
            },
            {
              label: "Success Rate",
              value: stats.total
                ? `${((stats.completed / stats.total) * 100).toFixed(1)}%`
                : "0%",
              color: "text-green-600",
            },
            {
              label: "Alerts",
              value: stats.failed,
              color: "text-amber-600",
            },
            {
              label: "Pending",
              value: stats.pending,
              color: "text-gray-700",
            },
            {
              label: "Total Amount",
              value: fmt(stats.total_amount),
              color: "text-cyan-700",
            },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-white rounded-lg p-4 border border-gray-200"
            >
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className={`text-2xl font-semibold mt-2 ${s.color}`}>
                {s.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
          <button
            onClick={() => setError("")}
            className="ml-auto text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />
          {success}
          <button
            onClick={() => setSuccess("")}
            className="ml-auto text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}

      {activeTab === "OVERVIEW" && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-900">
              Recent Activity
            </p>
            <button
              onClick={loadSettlements}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg text-xs border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-60"
            >
              Refresh
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["ID", "Description", "Status", "Date", "Action"].map((h) => (
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
              {loading ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-gray-400"
                  >
                    Loading...
                  </td>
                </tr>
              ) : settlements.slice(0, 8).length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-gray-400"
                  >
                    No records found
                  </td>
                </tr>
              ) : (
                settlements.slice(0, 8).map((item) => {
                  const statusKey = item.status?.toUpperCase() as SettlementServiceStatus;
                  const cfg = STATUS_CONFIG[statusKey] ?? { label: item.status, color: "bg-gray-100 text-gray-600" };
                  return (
                    <tr key={item.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs text-gray-800">
                        REC-{item.id}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {item.transaction_count} transactions batched for
                        settlement
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cfg.color}`}
                        >
                          {cfg.label.toLowerCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {new Date(
                          item.updated_at || item.created_at,
                        ).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => openRecord(item.id)}
                          className="text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {(activeTab === "DETAILS" || activeTab === "HISTORY") && (
        <>
          <div className="bg-white rounded-xl p-4 border border-gray-200 flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Status</label>
              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(
                    e.target.value as "ALL" | SettlementServiceStatus,
                  )
                }
                className="border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
              >
                <option value="ALL">All</option>
                <option value="PENDING">Pending</option>
                <option value="PROCESSING">Processing</option>
                <option value="COMPLETED">Completed</option>
                <option value="FAILED">Failed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Currency</label>
              <input
                value={currencyFilter}
                onChange={(e) => setCurrencyFilter(e.target.value)}
                placeholder="NGN"
                maxLength={3}
                className="border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm uppercase text-gray-700"
              />
            </div>
            <div className="flex flex-col gap-1 min-w-[260px] flex-1">
              <label className="text-xs text-gray-500">Records</label>
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by id, status, currency, external ref"
                className="border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
              />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {[
                    "ID",
                    "Settlement Date",
                    "Currency",
                    "Transactions",
                    "Amount",
                    "Status",
                    "External Ref",
                    "Actions",
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
                {loading ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-gray-400"
                    >
                      Loading...
                    </td>
                  </tr>
                ) : searched.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-gray-400"
                    >
                      No settlements found
                    </td>
                  </tr>
                ) : (
                  searched.map((item) => {
                    const statusKey = item.status?.toUpperCase() as SettlementServiceStatus;
                    const cfg = STATUS_CONFIG[statusKey] ?? { label: item.status, color: "bg-gray-100 text-gray-600" };
                    return (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <button
                            onClick={() => openRecord(item.id)}
                            className="font-mono text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline"
                          >
                            #{item.id}
                          </button>
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {new Date(item.settlement_date).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {item.currency}
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {item.transaction_count}
                        </td>
                        <td className="px-4 py-3 font-semibold text-gray-900">
                          {fmt(item.amount)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cfg.color}`}
                          >
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                          {item.external_reference_id || "-"}
                        </td>
                        <td className="px-4 py-3">
                          {item.status?.toUpperCase() === "PENDING" &&
                            activeTab === "DETAILS" && (
                              <button
                                onClick={() =>
                                  handleProcessSettlement(item.id)
                                }
                                disabled={actionId === item.id}
                                className="flex items-center gap-1 px-2 py-1 bg-[var(--tenant-primary-color,#004F71)] text-white rounded text-xs hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] disabled:opacity-50"
                              >
                                <ArrowRight size={10} />
                                Process
                              </button>
                            )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {activeTab === "SETTINGS" && (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Settings2 size={14} className="text-gray-500" />
                <p className="text-sm font-semibold text-gray-900">
                  Default Settlement Payment Policy
                </p>
              </div>
              <p className="text-xs text-gray-500">
                Choose immediate settlement or end-of-cycle settlement as the
                default.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="md:col-span-1">
                  <label className="text-xs text-gray-500">Payout Mode</label>
                  <select
                    value={policyConfig.default_mode}
                    onChange={(e) =>
                      setPolicyConfig((prev) => ({
                        ...prev,
                        default_mode: e.target.value as SettlementPayoutMode,
                      }))
                    }
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                  >
                    <option value="IMMEDIATE">
                      Immediate after every transaction
                    </option>
                    <option value="CYCLE_END">End of cycle</option>
                  </select>
                </div>
                {policyConfig.default_mode === "CYCLE_END" && (
                  <>
                    <div>
                      <label className="text-xs text-gray-500">
                        Cycle Unit
                      </label>
                      <select
                        value={policyConfig.cycle_unit}
                        onChange={(e) =>
                          setPolicyConfig((prev) => ({
                            ...prev,
                            cycle_unit: e.target.value as SettlementCycleUnit,
                          }))
                        }
                        className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                      >
                        <option value="DAILY">Day</option>
                        <option value="WEEKLY">Week</option>
                        <option value="MONTHLY">Month</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500">
                        Cycle Interval
                      </label>
                      <input
                        type="number"
                        min={1}
                        value={policyConfig.cycle_value}
                        onChange={(e) =>
                          setPolicyConfig((prev) => ({
                            ...prev,
                            cycle_value: Number(e.target.value),
                          }))
                        }
                        className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                      />
                    </div>
                  </>
                )}
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleSavePolicy}
                  className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]"
                >
                  Save Policy
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-gray-500" />
                <p className="text-sm font-semibold text-gray-900">
                  Entity Settlement Rules
                </p>
              </div>
              <p className="text-xs text-gray-500">
                Create payout rules for agent groups or specific agents.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Rule Name</label>
                  <input
                    value={newRuleName}
                    onChange={(e) => setNewRuleName(e.target.value)}
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                    placeholder="Example: Super agent weekly settlements"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Entity Type</label>
                  <select
                    value={newRuleEntityType}
                    onChange={(e) =>
                      setNewRuleEntityType(
                        e.target.value as SettlementEntityType,
                      )
                    }
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                  >
                    <option value="AGENT">All agents</option>
                    <option value="SUPER_AGENT">All super agents</option>
                    <option value="SPECIFIC_AGENT">Specific agent</option>
                  </select>
                </div>
                {newRuleEntityType === "SPECIFIC_AGENT" && (
                  <div className="md:col-span-2">
                    <label className="text-xs text-gray-500">
                      Agent Identifier
                    </label>
                    <input
                      value={newRuleEntityIdentifier}
                      onChange={(e) =>
                        setNewRuleEntityIdentifier(e.target.value)
                      }
                      className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                      placeholder="Agent ID or keycloak_id"
                    />
                  </div>
                )}
                <div>
                  <label className="text-xs text-gray-500">Payout Mode</label>
                  <select
                    value={newRulePayoutMode}
                    onChange={(e) =>
                      setNewRulePayoutMode(
                        e.target.value as SettlementPayoutMode,
                      )
                    }
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                  >
                    <option value="IMMEDIATE">Immediate</option>
                    <option value="CYCLE_END">End of cycle</option>
                  </select>
                </div>
                {newRulePayoutMode === "CYCLE_END" && (
                  <>
                    <div>
                      <label className="text-xs text-gray-500">
                        Cycle Unit
                      </label>
                      <select
                        value={newRuleCycleUnit}
                        onChange={(e) =>
                          setNewRuleCycleUnit(
                            e.target.value as SettlementCycleUnit,
                          )
                        }
                        className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                      >
                        <option value="DAILY">Day</option>
                        <option value="WEEKLY">Week</option>
                        <option value="MONTHLY">Month</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500">
                        Cycle Interval
                      </label>
                      <input
                        type="number"
                        min={1}
                        value={newRuleCycleValue}
                        onChange={(e) =>
                          setNewRuleCycleValue(Number(e.target.value))
                        }
                        className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                      />
                    </div>
                  </>
                )}
                <div>
                  <label className="text-xs text-gray-500">
                    Min Amount (optional)
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={newRuleMinAmount}
                    onChange={(e) =>
                      setNewRuleMinAmount(
                        e.target.value === "" ? "" : Number(e.target.value),
                      )
                    }
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">
                    Max Amount (optional)
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={newRuleMaxAmount}
                    onChange={(e) =>
                      setNewRuleMaxAmount(
                        e.target.value === "" ? "" : Number(e.target.value),
                      )
                    }
                    className="w-full border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm text-gray-700"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleAddRule}
                  className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]"
                >
                  Add Rule
                </button>
              </div>
            </div>
          </div>
          {renderRulesTable()}
        </>
      )}

      {activeTab === "HISTORY" && renderRulesTable()}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">
              Create Settlement
            </h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Settlement Date
              </label>
              <input
                type="date"
                value={newSettlementDate}
                onChange={(e) => setNewSettlementDate(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Amount
                </label>
                <input
                  type="number"
                  min={0}
                  value={newAmount}
                  onChange={(e) => setNewAmount(Number(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Currency
                </label>
                <input
                  value={newCurrency}
                  onChange={(e) => setNewCurrency(e.target.value)}
                  maxLength={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm uppercase"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Transaction Count
              </label>
              <input
                type="number"
                min={0}
                value={newTransactionCount}
                onChange={(e) =>
                  setNewTransactionCount(Number(e.target.value))
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                External Reference
              </label>
              <input
                value={newExternalRef}
                onChange={(e) => setNewExternalRef(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                placeholder="Optional"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCreateSettlement}
                disabled={creating}
                className="flex-1 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create Settlement"}
              </button>
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedRecord && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex justify-between items-start">
              <h3 className="text-lg font-bold text-gray-900">
                Settlement Details
              </h3>
              <button
                onClick={() => setSelectedRecord(null)}
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                ×
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                { label: "Settlement ID", value: selectedRecord.id },
                { label: "Status", value: selectedRecord.status },
                {
                  label: "Settlement Date",
                  value: new Date(
                    selectedRecord.settlement_date,
                  ).toLocaleString(),
                },
                { label: "Currency", value: selectedRecord.currency },
                { label: "Amount", value: fmt(selectedRecord.amount) },
                {
                  label: "Transaction Count",
                  value: selectedRecord.transaction_count,
                },
                {
                  label: "External Reference",
                  value: selectedRecord.external_reference_id || "-",
                },
                {
                  label: "Created",
                  value: new Date(selectedRecord.created_at).toLocaleString(),
                },
              ].map((item) => (
                <div key={item.label} className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">{item.label}</p>
                  <p className="font-semibold mt-1">{item.value}</p>
                </div>
              ))}
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Settings2 size={14} className="text-gray-500" />
                <p className="text-sm font-semibold text-gray-700">
                  Update Settlement Status
                </p>
              </div>
              <div className="flex gap-2">
                <select
                  value={updateStatus}
                  onChange={(e) =>
                    setUpdateStatus(e.target.value as SettlementServiceStatus)
                  }
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="PENDING">PENDING</option>
                  <option value="PROCESSING">PROCESSING</option>
                  <option value="COMPLETED">COMPLETED</option>
                  <option value="FAILED">FAILED</option>
                  <option value="CANCELLED">CANCELLED</option>
                </select>
                <button
                  onClick={handleUpdateStatus}
                  disabled={actionId === selectedRecord.id}
                  className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettlementBatchProcessor;
