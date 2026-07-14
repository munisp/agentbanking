import { BarChart3, RefreshCw } from "lucide-react";
import React, { useMemo, useState } from "react";
import { serviceIntegrationsApi } from "../../utils/api";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  if (value instanceof Date) return value.toISOString();
  return JSON.stringify(value);
}

const DataTable: React.FC<{ rows: unknown[] }> = ({ rows }) => {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        No records returned.
      </div>
    );
  }
  const allKeys = Array.from(
    new Set(
      rows.flatMap((row) =>
        isRecord(row) ? Object.keys(row).slice(0, 8) : ["value"],
      ),
    ),
  );
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <div className="overflow-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">#</th>
              {allKeys.map((key) => (
                <th key={key} className="px-4 py-3">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">{index + 1}</td>
                {allKeys.map((key) => (
                  <td key={key} className="px-4 py-3 align-top">
                    {isRecord(row) ? formatValue(row[key]) : formatValue(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const ResultPanel: React.FC<{ value: unknown }> = ({ value }) => {
  if (value === null || value === undefined) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        No data. Run an action to view results.
      </div>
    );
  }
  if (Array.isArray(value)) return <DataTable rows={value} />;
  if (isRecord(value)) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        {Object.entries(value)
          .slice(0, 12)
          .map(([key, item]) => (
            <div key={key} className="rounded-xl border bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {key}
              </div>
              <div className="mt-1 break-words text-sm text-gray-800">
                {formatValue(item)}
              </div>
            </div>
          ))}
      </div>
    );
  }
  return (
    <div className="rounded-xl border bg-white p-4 text-sm text-gray-800 shadow-sm">
      {formatValue(value)}
    </div>
  );
};

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)]";
const btnPrimary =
  "bg-[var(--tenant-primary-color,#002082)] text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60 disabled:cursor-not-allowed";

type ActiveSection =
  | "sync_status"
  | "performance"
  | "setup_agent"
  | "sync_tx"
  | "retry_syncs"
  | "financial_summary"
  | "profit_loss"
  | "balance_sheet"
  | "cash_flow"
  | "trial_balance"
  | "customer_ledger";

const ErpNextPage: React.FC = () => {
  const [activeSection, setActiveSection] =
    useState<ActiveSection>("sync_status");
  const [agentId, setAgentId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [asOfDate, setAsOfDate] = useState("");
  const [agentName, setAgentName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [txData, setTxData] = useState(
    '{\n  "transaction_id": "",\n  "agent_id": "",\n  "amount": 0,\n  "transaction_type": "transfer"\n}',
  );
  const [result, setResult] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>, msg: string) => {
    setIsLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await action();
      setResult(res);
      setSuccess(msg);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setIsLoading(false);
    }
  };

  const hasAgent = agentId.trim().length > 0;
  const hasDateRange = hasAgent && fromDate.trim() && toDate.trim();
  const hasAsOf = hasAgent && asOfDate.trim();
  const hasSetup = hasAgent && agentName.trim() && phone.trim();

  const sections: { key: ActiveSection; label: string }[] = [
    { key: "sync_status", label: "Sync Status" },
    { key: "sync_tx", label: "Sync Transaction" },
    { key: "retry_syncs", label: "Retry Failed Syncs" },
    { key: "setup_agent", label: "Setup Agent" },
    { key: "performance", label: "Performance Report" },
    { key: "financial_summary", label: "Financial Summary" },
    { key: "profit_loss", label: "Profit & Loss" },
    { key: "balance_sheet", label: "Balance Sheet" },
    { key: "cash_flow", label: "Cash Flow" },
    { key: "trial_balance", label: "Trial Balance" },
    { key: "customer_ledger", label: "Customer Ledger" },
  ];

  const handleRun = () => {
    const erp = serviceIntegrationsApi.erpnext;
    const id = agentId.trim();
    const from = fromDate.trim();
    const to = toDate.trim();
    const aof = asOfDate.trim();
    switch (activeSection) {
      case "sync_status":
        return run(() => erp.getSyncStatus(id), "Sync status loaded");
      case "sync_tx": {
        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(txData);
        } catch {
          setError("Invalid JSON");
          return;
        }
        return run(
          () =>
            erp.syncTransaction(
              parsed as Parameters<typeof erp.syncTransaction>[0],
            ),
          "Transaction synced",
        );
      }
      case "retry_syncs":
        return run(() => erp.retryFailedSyncs(id), "Retry triggered");
      case "setup_agent":
        return run(
          () =>
            erp.setupAgent(id, {
              agent_name: agentName.trim(),
              phone: phone.trim(),
              email: email || undefined,
              vat_number: vatNumber || undefined,
            }),
          "Agent accounting set up",
        );
      case "performance":
        return run(
          () => erp.getPerformanceReport(id, from, to),
          "Performance report loaded",
        );
      case "financial_summary":
        return run(
          () =>
            erp.getFinancialSummary({
              agent_id: id,
              from_date: from,
              to_date: to,
            }),
          "Financial summary loaded",
        );
      case "profit_loss":
        return run(() => erp.getProfitLoss(id, from, to), "P&L loaded");
      case "balance_sheet":
        return run(() => erp.getBalanceSheet(id, aof), "Balance sheet loaded");
      case "cash_flow":
        return run(() => erp.getCashFlow(id, from, to), "Cash flow loaded");
      case "trial_balance":
        return run(
          () => erp.getTrialBalance(id, from, to),
          "Trial balance loaded",
        );
      case "customer_ledger":
        return run(
          () => erp.getCustomerLedger(id, from, to),
          "Customer ledger loaded",
        );
    }
  };

  const canRun = useMemo(() => {
    if (!hasAgent) return false;
    if (["sync_status", "sync_tx", "retry_syncs"].includes(activeSection))
      return true;
    if (activeSection === "setup_agent") return hasSetup;
    if (activeSection === "balance_sheet") return hasAsOf;
    return hasDateRange;
  }, [activeSection, hasAgent, hasDateRange, hasAsOf, hasSetup]);

  const needsDateRange = [
    "performance",
    "financial_summary",
    "profit_loss",
    "cash_flow",
    "trial_balance",
    "customer_ledger",
  ].includes(activeSection);
  const needsAsOf = activeSection === "balance_sheet";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-[var(--tenant-primary-color,#002082)]" />
          ERPNext Integration
        </h1>
        <p className="text-gray-500 mt-1 text-sm">
          Sync transactions, set up agent accounting, and pull financial reports
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          {success}
        </div>
      )}

      {/* Section tabs */}
      <div className="flex flex-wrap gap-2">
        {sections.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => {
              setActiveSection(key);
              setResult(null);
              setError(null);
              setSuccess(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${activeSection === key ? "bg-[var(--tenant-primary-color,#002082)] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Inputs */}
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {sections.find((s) => s.key === activeSection)?.label}
          </h2>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Agent ID *
            </label>
            <input
              className={inputClass}
              placeholder="e.g. agent-uuid"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            />
          </div>

          {activeSection === "setup_agent" && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Agent Name *
                </label>
                <input
                  className={inputClass}
                  placeholder="Full business name"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Phone *
                </label>
                <input
                  className={inputClass}
                  placeholder="+2348001234567"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Email
                </label>
                <input
                  className={inputClass}
                  placeholder="agent@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  VAT Number
                </label>
                <input
                  className={inputClass}
                  placeholder="Optional VAT/TIN"
                  value={vatNumber}
                  onChange={(e) => setVatNumber(e.target.value)}
                />
              </div>
            </>
          )}

          {activeSection === "sync_tx" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Transaction JSON *
              </label>
              <textarea
                className={inputClass}
                rows={6}
                value={txData}
                onChange={(e) => setTxData(e.target.value)}
              />
            </div>
          )}

          {needsDateRange && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  From Date *
                </label>
                <input
                  className={inputClass}
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  To Date *
                </label>
                <input
                  className={inputClass}
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </div>
            </div>
          )}

          {needsAsOf && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                As Of Date *
              </label>
              <input
                className={inputClass}
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
              />
            </div>
          )}

          <button
            className={btnPrimary}
            disabled={isLoading || !canRun}
            onClick={handleRun}
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 inline mr-1 animate-spin" />
                Loading…
              </>
            ) : (
              sections.find((s) => s.key === activeSection)?.label
            )}
          </button>
        </div>

        {/* Results */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Results</h2>
          {isLoading ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              Loading…
            </div>
          ) : (
            <ResultPanel value={result} />
          )}
        </div>
      </div>
    </div>
  );
};

export default ErpNextPage;
