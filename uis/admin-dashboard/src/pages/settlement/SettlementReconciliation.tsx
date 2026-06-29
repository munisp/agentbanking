import {
  AlertCircle,
  BookText,
  CheckCircle,
  Clock3,
  Plus,
  RefreshCw,
} from "lucide-react";
import React, { useEffect, useState } from "react";

type SettlementServiceStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

type SettlementServiceLogLevel = "INFO" | "WARNING" | "ERROR" | "DEBUG";

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
    level: SettlementServiceLogLevel;
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
  addLog: (
    id: number,
    data: {
      level: SettlementServiceLogLevel;
      message: string;
      details?: string;
    },
  ) =>
    settlementRequest(`/settlements/${id}/log`, {
      method: "POST",
      headers: settlementHeaders(),
      body: JSON.stringify(data),
    }),
};

interface ReconciliationStats {
  total: number;
  with_logs: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
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

const LOG_LEVEL_OPTIONS: SettlementServiceLogLevel[] = [
  "INFO",
  "WARNING",
  "ERROR",
  "DEBUG",
];

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
  }).format(n || 0);

const fmtDate = (value?: string) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
};

const SettlementReconciliation: React.FC = () => {
  const [records, setRecords] = useState<SettlementServiceRecord[]>([]);
  const [stats, setStats] = useState<ReconciliationStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] =
    useState<SettlementServiceRecord | null>(null);
  const [statusFilter, setStatusFilter] = useState<
    "ALL" | SettlementServiceStatus
  >("ALL");
  const [currencyFilter, setCurrencyFilter] = useState("");
  const [logMessage, setLogMessage] = useState("");
  const [logDetails, setLogDetails] = useState("");
  const [logLevel, setLogLevel] = useState<SettlementServiceLogLevel>("INFO");
  const [submittingLog, setSubmittingLog] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadRecords();
  }, [statusFilter, currencyFilter]);

  const loadRecords = async () => {
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

      setRecords(data);

      const s: ReconciliationStats = {
        total: data.length,
        with_logs: data.filter(
          (item) => item.logs && item.logs.length > 0,
        ).length,
        pending: data.filter((item) => item.status?.toUpperCase() === "PENDING").length,
        processing: data.filter((item) => item.status?.toUpperCase() === "PROCESSING").length,
        completed: data.filter((item) => item.status?.toUpperCase() === "COMPLETED").length,
        failed: data.filter((item) => item.status?.toUpperCase() === "FAILED").length,
      };
      setStats(s);
    } catch (err: any) {
      setError(err.message || "Failed to load settlements");
    } finally {
      setLoading(false);
    }
  };

  const openRecord = async (id: number) => {
    try {
      const detail = await settlementApi.get(id);
      setSelectedRecord(detail);
    } catch (err: any) {
      setError(err.message || "Failed to load settlement details");
    }
  };

  const handleCreateLog = async () => {
    if (!selectedRecord || !logMessage.trim()) return;
    try {
      setSubmittingLog(true);
      await settlementApi.addLog(selectedRecord.id, {
        level: logLevel,
        message: logMessage.trim(),
        details: logDetails.trim() || undefined,
      });
      const updated = await settlementApi.get(selectedRecord.id);
      setSelectedRecord(updated);
      setSuccess("Activity log created");
      setLogMessage("");
      setLogDetails("");
      await loadRecords();
    } catch (err: any) {
      setError(err.message || "Failed to add activity log");
    } finally {
      setSubmittingLog(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Settlement Scheduler
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Cron-based automated settlement orchestration
          </p>
        </div>
        <button
          onClick={loadRecords}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {[
            {
              label: "Total Schedules",
              value: stats.total,
              color: "text-gray-900",
            },
            {
              label: "Active Schedules",
              value: stats.processing,
              color: "text-gray-900",
            },
            {
              label: "Paused Schedules",
              value: stats.pending,
              color: "text-amber-600",
            },
            {
              label: "Total Settled 24h",
              value: fmt(records.reduce((sum, r) => sum + r.amount, 0)),
              color: "text-cyan-700",
            },
            {
              label: "Avg Success Rate",
              value: stats.total
                ? `${((stats.completed / stats.total) * 100).toFixed(1)}%`
                : "0%",
              color: "text-green-600",
            },
            {
              label: "Failed Runs 24h",
              value: stats.failed,
              color: "text-red-600",
            },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-white rounded-lg p-4 border border-gray-200"
            >
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className={`text-xl font-bold mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white rounded-xl p-4 border border-gray-200 flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">Status</label>
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
          <label className="text-xs text-gray-500 font-medium">Currency</label>
          <input
            value={currencyFilter}
            onChange={(e) => setCurrencyFilter(e.target.value)}
            className="border border-gray-300 bg-white rounded-lg px-3 py-2 text-sm uppercase text-gray-700"
            maxLength={3}
            placeholder="NGN"
          />
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError("")} className="ml-auto">
            ×
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />
          {success}
          <button onClick={() => setSuccess("")} className="ml-auto">
            ×
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {[
                "ID",
                "Settlement Date",
                "Amount",
                "Currency",
                "Transactions",
                "Status",
                "Logs",
                "Actions",
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : records.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  No records found
                </td>
              </tr>
            ) : (
              records.map((r) => {
                const statusKey = r.status?.toUpperCase() as SettlementServiceStatus;
                const cfg = STATUS_CONFIG[statusKey] ?? { label: r.status, color: "bg-gray-100 text-gray-600" };
                return (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-800">
                      #{r.id}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {fmtDate(r.settlement_date)}
                    </td>
                    <td className="px-4 py-3 font-semibold text-gray-900">
                      {fmt(r.amount)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{r.currency}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {r.transaction_count}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cfg.color}`}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {r.logs?.length || 0}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => openRecord(r.id)}
                        className="text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline font-medium"
                      >
                        View Activity
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {selectedRecord && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">
                Settlement Activity Detail
              </h3>
              <button
                onClick={() => setSelectedRecord(null)}
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                ×
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">ID</span>
                <span className="font-mono">#{selectedRecord.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Status</span>
                <span className="font-semibold">{selectedRecord.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Amount</span>
                <span className="font-semibold">
                  {fmt(selectedRecord.amount)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Currency</span>
                <span className="font-semibold">{selectedRecord.currency}</span>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <BookText size={14} className="text-gray-500" />
                <p className="text-sm font-semibold text-gray-700">
                  Activity Logs
                </p>
              </div>
              <div className="max-h-56 overflow-y-auto rounded-lg border border-gray-200 divide-y divide-gray-100">
                {(selectedRecord.logs || []).length === 0 ? (
                  <div className="p-4 text-sm text-gray-500">
                    No activity logs yet.
                  </div>
                ) : (
                  [...selectedRecord.logs]
                    .sort(
                      (a, b) =>
                        new Date(b.timestamp).getTime() -
                        new Date(a.timestamp).getTime(),
                    )
                    .map((entry) => (
                      <div key={entry.id} className="p-3">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span className="font-semibold">{entry.level}</span>
                          <span>{fmtDate(entry.timestamp)}</span>
                        </div>
                        <p className="text-sm text-gray-800 mt-1">
                          {entry.message}
                        </p>
                        {entry.details && (
                          <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">
                            {entry.details}
                          </p>
                        )}
                      </div>
                    ))
                )}
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Plus size={14} className="text-gray-500" />
                <p className="text-sm font-semibold text-gray-700">
                  Add Log Entry
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="md:col-span-1">
                  <label className="text-xs text-gray-500">Level</label>
                  <select
                    value={logLevel}
                    onChange={(e) =>
                      setLogLevel(e.target.value as SettlementServiceLogLevel)
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  >
                    {LOG_LEVEL_OPTIONS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-3">
                  <label className="text-xs text-gray-500">Message</label>
                  <input
                    value={logMessage}
                    onChange={(e) => setLogMessage(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    placeholder="Describe the settlement event"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500">
                  Details (optional)
                </label>
                <textarea
                  value={logDetails}
                  onChange={(e) => setLogDetails(e.target.value)}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Additional metadata or context"
                />
              </div>
              <button
                onClick={handleCreateLog}
                disabled={submittingLog || !logMessage.trim()}
                className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {submittingLog ? "Saving…" : "Add Log"}
              </button>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setSelectedRecord(null)}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettlementReconciliation;
