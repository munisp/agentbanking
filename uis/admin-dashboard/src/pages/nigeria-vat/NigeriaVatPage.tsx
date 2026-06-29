import {
    FileText,
    RefreshCw,
    Settings,
    ToggleLeft,
    ToggleRight,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { serviceIntegrationsApi } from "../../utils/api";

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)]";
const buttonClass =
  "bg-[var(--tenant-primary-color,#002082)] text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60 disabled:cursor-not-allowed";

function getCount(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  if (isRecord(value)) {
    for (const candidate of Object.values(value)) {
      if (Array.isArray(candidate)) return candidate.length;
    }
  }
  return 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return JSON.stringify(value);
}

const ResultPanel: React.FC<{ value: unknown }> = ({ value }) => {
  const rendered = useMemo(() => {
    if (value === null || value === undefined) {
      return (
        <p className="text-sm text-gray-500">Run an action to view VAT data.</p>
      );
    }
    if (Array.isArray(value)) {
      if (value.length === 0)
        return <p className="text-sm text-gray-500">No records returned.</p>;
      const keys = Array.from(
        new Set(
          value.flatMap((item) =>
            isRecord(item) ? Object.keys(item) : ["value"],
          ),
        ),
      );
      return (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {keys.map((key) => (
                  <th
                    key={key}
                    className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase"
                  >
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {value.map((item, index) => (
                <tr key={index} className="border-t">
                  {keys.map((key) => (
                    <td key={key} className="px-3 py-2 align-top text-sm">
                      {isRecord(item)
                        ? formatValue(item[key])
                        : formatValue(item)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    if (isRecord(value)) {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(value).map(([key, item]) => (
            <div key={key} className="border rounded-lg p-3 bg-gray-50">
              <div className="text-xs uppercase tracking-wide text-gray-500">
                {key}
              </div>
              <div className="text-sm font-medium break-words">
                {formatValue(item)}
              </div>
            </div>
          ))}
        </div>
      );
    }
    return (
      <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto">
        {formatValue(value)}
      </pre>
    );
  }, [value]);
  return <div>{rendered}</div>;
};

// ── Main Page ─────────────────────────────────────────────────────────────────

const NigeriaVatPage: React.FC = () => {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState<unknown>(null);
  const [businesses, setBusinesses] = useState<unknown>(null);
  const [transactions, setTransactions] = useState<unknown>(null);
  const [summary, setSummary] = useState<unknown>(null);
  const [exemptCategories, setExemptCategories] = useState<unknown>(null);

  const [entityId, setEntityId] = useState("");
  const [period, setPeriod] = useState("");

  const load = async () => {
    setError("");
    setMessage("");
    try {
      const [h, businessesResponse, transactionsResponse, exemptResponse] =
        await Promise.all([
          serviceIntegrationsApi.nigeriaVat.health(),
          serviceIntegrationsApi.nigeriaVat.listBusinesses(),
          serviceIntegrationsApi.nigeriaVat.listTransactions(),
          serviceIntegrationsApi.nigeriaVat.getExemptCategories(),
        ]);
      setHealth(h);
      setBusinesses(businessesResponse);
      setTransactions(transactionsResponse);
      setExemptCategories(exemptResponse);
      setMessage("Nigeria VAT data loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!entityId || !period) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    const loadSummary = async () => {
      try {
        const response = await serviceIntegrationsApi.nigeriaVat.getSummary(
          entityId,
          period,
        );
        if (!cancelled) setSummary(response);
      } catch {
        if (!cancelled) setSummary(null);
      }
    };
    void loadSummary();
    return () => {
      cancelled = true;
    };
  }, [entityId, period]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Nigeria VAT Management
          </h1>
          <p className="text-gray-600 mt-1">
            VAT is auto-recorded for every agent transaction. Returns are
            generated monthly.
          </p>
        </div>
        <button className={buttonClass} onClick={() => void load()}>
          <RefreshCw className="h-4 w-4 inline mr-2" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {message && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {message}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
          <p className="text-sm text-gray-600">Service Health</p>
          <p className="text-lg font-bold mt-1 text-gray-900">
            {formatValue((health as Record<string, unknown> | null)?.status)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
          <p className="text-sm text-gray-600">Businesses</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {getCount(businesses)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-purple-500">
          <p className="text-sm text-gray-600">Transactions</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {getCount(transactions)}
          </p>
        </div>
      </div>

      {/* Summary query + Exempt categories */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6 shadow space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            VAT Summary Query
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              className={inputClass}
              placeholder="Entity / Agent ID"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
            />
            <input
              className={inputClass}
              placeholder="Period (YYYY-MM)"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
            />
          </div>
          <ResultPanel value={summary} />
        </div>

        <div className="bg-white border rounded-lg p-6 shadow space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Exempt Categories
          </h2>
          <p className="text-xs text-gray-500">
            Agency banking fees are VAT-exempt under Finance Act 2020. Inventory
            sales are standard-rated at 7.5%.
          </p>
          <ResultPanel value={exemptCategories} />
        </div>
      </div>

      {/* Automation Config Panel */}
      <AutomationConfigPanel />

      {/* VAT Returns Filing */}
      <VatReturnsPanel />

      {/* Businesses */}
      <div className="bg-white border rounded-lg p-6 shadow space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Businesses with VAT Activity
        </h2>
        <ResultPanel value={businesses} />
      </div>

      {/* All transactions */}
      <div className="bg-white border rounded-lg p-6 shadow space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">
          All VAT Transactions
        </h2>
        <ResultPanel value={transactions} />
      </div>
    </div>
  );
};

// ── Automation Config Panel ───────────────────────────────────────────────────

const AutomationConfigPanel: React.FC = () => {
  const [entityId, setEntityId] = useState("");
  const [config, setConfig] = useState<{
    auto_record_vat: boolean;
    auto_generate_return: boolean;
    auto_file_firs: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    if (!entityId.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await serviceIntegrationsApi.nigeriaVat.getAutomationConfig(
        entityId.trim(),
      );
      setConfig({
        auto_record_vat: res.auto_record_vat,
        auto_generate_return: res.auto_generate_return,
        auto_file_firs: res.auto_file_firs,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  const save = async () => {
    if (!config || !entityId.trim()) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const res =
        await serviceIntegrationsApi.nigeriaVat.updateAutomationConfig(
          entityId.trim(),
          config,
        );
      setConfig({
        auto_record_vat: res.auto_record_vat,
        auto_generate_return: res.auto_generate_return,
        auto_file_firs: res.auto_file_firs,
      });
      setSuccess("Automation settings saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const Toggle: React.FC<{
    label: string;
    description: string;
    value: boolean;
    onChange: (v: boolean) => void;
    disabled?: boolean;
  }> = ({ label, description, value, onChange, disabled }) => (
    <div
      className={`flex items-start justify-between gap-4 py-3 ${disabled ? "opacity-50" : ""}`}
    >
      <div>
        <p className="text-sm font-medium text-gray-800">{label}</p>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
      </div>
      <button
        onClick={() => !disabled && onChange(!value)}
        className="shrink-0 mt-0.5"
        disabled={disabled}
      >
        {value ? (
          <ToggleRight className="h-7 w-7" style={{ color: "var(--tenant-primary-color,#002082)" }} />
        ) : (
          <ToggleLeft className="h-7 w-7 text-gray-400" />
        )}
      </button>
    </div>
  );

  return (
    <div className="bg-white border rounded-lg p-6 shadow space-y-4">
      <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
        <Settings className="h-5 w-5 text-gray-500" />
        VAT Automation Settings
      </h2>
      <p className="text-sm text-gray-500">
        Configure per-agent automation preferences. By default VAT is
        auto-recorded and returns are auto-generated — agents must explicitly
        opt in to auto-filing with FIRS.
      </p>

      <div className="flex gap-3">
        <input
          className={inputClass}
          placeholder="Agent / Entity ID"
          value={entityId}
          onChange={(e) => {
            setEntityId(e.target.value);
            setConfig(null);
          }}
        />
        <button
          className={buttonClass}
          disabled={loading || !entityId.trim()}
          onClick={load}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : "Load"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded text-sm">
          {success}
        </div>
      )}

      {config && (
        <div className="border rounded-lg p-4 space-y-1 divide-y divide-gray-100">
          <Toggle
            label="Auto-record VAT transactions"
            description="Automatically record a VAT entry for every payment transaction this agent processes."
            value={config.auto_record_vat}
            onChange={(v) => setConfig({ ...config, auto_record_vat: v })}
          />
          <Toggle
            label="Auto-generate monthly return"
            description="On the 1st of each month, automatically generate the prior month's VAT return (Form 002)."
            value={config.auto_generate_return}
            onChange={(v) =>
              setConfig({
                ...config,
                auto_generate_return: v,
                auto_file_firs: v ? config.auto_file_firs : false,
              })
            }
          />
          <Toggle
            label="Auto-file return with FIRS"
            description="Automatically submit the generated return to FIRS. Requires auto-generate to be enabled."
            value={config.auto_file_firs}
            onChange={(v) => setConfig({ ...config, auto_file_firs: v })}
            disabled={!config.auto_generate_return}
          />

          <div className="pt-3">
            {config.auto_file_firs && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700 mb-3">
                Auto-filing is enabled. Returns will be submitted to FIRS
                automatically on the 1st of each month. Ensure this agent's VAT
                registration and TIN are correct before enabling.
              </div>
            )}
            <button className={buttonClass} onClick={save} disabled={saving}>
              {saving ? (
                <>
                  <RefreshCw className="h-4 w-4 inline mr-1 animate-spin" />
                  Saving…
                </>
              ) : (
                "Save Settings"
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── VAT Returns & Filing Panel ────────────────────────────────────────────────

const VatReturnsPanel: React.FC = () => {
  const [entityId, setEntityId] = useState("");
  const [period, setPeriod] = useState("");
  const [returnId, setReturnId] = useState("");
  const [amountPaid, setAmountPaid] = useState("");
  const [paymentRef, setPaymentRef] = useState("");
  const [paymentDate, setPaymentDate] = useState("");
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [result, setResult] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const run = async (action: () => Promise<unknown>, msg: string) => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await action();
      setResult(res);
      setSuccess(msg);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const hasEntity = entityId.trim().length > 0;
  const hasReturn = returnId.trim().length > 0;

  return (
    <div className="bg-white border rounded-lg p-6 shadow space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          VAT Returns & Filing
        </h2>
        <p className="text-xs text-gray-500 mt-1">
          Returns are auto-generated monthly. Use this panel for manual
          overrides or to check status.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded text-sm">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Generate Return */}
        <div className="border rounded-lg p-4 space-y-3">
          <h3 className="font-semibold text-gray-800 text-sm">
            Generate VAT Return
          </h3>
          <p className="text-xs text-gray-400">
            Manually trigger return generation for an agent. The system does
            this automatically on the 1st.
          </p>
          <input
            className={inputClass}
            placeholder="Entity / Agent ID *"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Period (YYYY-MM) *"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          />
          <button
            className={buttonClass}
            disabled={loading || !hasEntity || !period}
            onClick={() =>
              run(
                () =>
                  serviceIntegrationsApi.nigeriaVat.generateReturn({
                    entity_id: entityId.trim(),
                    period: period.trim(),
                  }),
                "Return generated",
              )
            }
          >
            Generate Return
          </button>
        </div>

        {/* File Return */}
        <div className="border rounded-lg p-4 space-y-3">
          <h3 className="font-semibold text-gray-800 text-sm">
            File Return with FIRS
          </h3>
          <p className="text-xs text-gray-400">
            If FIRS receipt number is left blank, a system receipt is
            auto-generated.
          </p>
          <input
            className={inputClass}
            placeholder="Return ID *"
            value={returnId}
            onChange={(e) => setReturnId(e.target.value)}
          />
          <button
            className={buttonClass}
            disabled={loading || !hasReturn}
            onClick={() =>
              run(
                () =>
                  serviceIntegrationsApi.nigeriaVat.fileReturn(returnId.trim()),
                "Return filed with FIRS",
              )
            }
          >
            File Return
          </button>

          {/* Record Payment */}
          <div className="border-t pt-3 space-y-2">
            <p className="text-xs text-gray-500 font-medium">Record Payment</p>
            <input
              className={inputClass}
              placeholder="Amount paid (NGN) *"
              type="number"
              value={amountPaid}
              onChange={(e) => setAmountPaid(e.target.value)}
            />
            <input
              className={inputClass}
              placeholder="Payment reference"
              value={paymentRef}
              onChange={(e) => setPaymentRef(e.target.value)}
            />
            <input
              className={inputClass}
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
            />
            <button
              className={buttonClass}
              disabled={loading || !hasReturn || !amountPaid || !paymentDate}
              onClick={() =>
                run(
                  () =>
                    serviceIntegrationsApi.nigeriaVat.recordReturnPayment(
                      returnId.trim(),
                      {
                        amount_paid: Number(amountPaid),
                        payment_reference: paymentRef.trim() || undefined,
                        payment_date: paymentDate,
                      },
                    ),
                  "Payment recorded",
                )
              }
            >
              Record Payment
            </button>
          </div>
        </div>

        {/* Schedule CSV */}
        <div className="border rounded-lg p-4 space-y-3">
          <h3 className="font-semibold text-gray-800 text-sm">
            Get Schedule CSV
          </h3>
          <input
            className={inputClass}
            placeholder="Entity / Agent ID *"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Period (YYYY-MM) *"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          />
          <button
            className={buttonClass}
            disabled={loading || !hasEntity || !period}
            onClick={() =>
              run(
                () =>
                  serviceIntegrationsApi.nigeriaVat.getScheduleCsv(
                    entityId.trim(),
                    period.trim(),
                  ),
                "Schedule CSV loaded",
              )
            }
          >
            Get Schedule CSV
          </button>
        </div>

        {/* Annual Report */}
        <div className="border rounded-lg p-4 space-y-3">
          <h3 className="font-semibold text-gray-800 text-sm">
            Annual VAT Report
          </h3>
          <input
            className={inputClass}
            placeholder="Entity / Agent ID *"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Year (e.g. 2024) *"
            type="number"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
          <button
            className={buttonClass}
            disabled={loading || !hasEntity || !year}
            onClick={() =>
              run(
                () =>
                  serviceIntegrationsApi.nigeriaVat.getAnnualReport(
                    entityId.trim(),
                    Number(year),
                  ),
                "Annual report loaded",
              )
            }
          >
            Get Annual Report
          </button>
        </div>
      </div>

      {result !== null && (
        <div className="border-t pt-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Result</h3>
          <ResultPanel value={result} />
        </div>
      )}
    </div>
  );
};

export default NigeriaVatPage;
